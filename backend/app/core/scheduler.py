from __future__ import annotations
import logging
import hashlib
import json
import os
from copy import deepcopy
from collections.abc import Collection
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import bindparam, text

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.collectors.service import CollectorService, CollectorThrottled, reclaim_zombie_runs
from app.collectors.data_source_repository import (
    due_scheduled_sources,
    scheduled_enabled_sources,
)
from app.core.config import settings
from app.core.runtime_fingerprint import (
    build_scheduler_owner_fingerprint,
    format_scheduler_owner_fingerprint,
)
from app.db.session import SessionLocal, engine
from app.models.data_source import DataSource
from app.services.audit_service import log_operation
from app.services.foreign_collection_service import collect_foreign
from app.services.foreign_risk_service import ForeignRiskService
from app.services.foreign_alert_service import ForeignAlertService
from app.services.event.aggregator import auto_aggregate_after_collect
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)
scheduler = None

# ===== 采集幂等 / 调度安全加固（跨进程 scheduler 单例）=====
# 使用 PostgreSQL 会话级咨询锁（advisory lock）确保多后端实例环境下只有一个进程
# 真正启动采集/预警调度器，从根上杜绝「同一时间定时采集触发两次 -> 同文章重复入库」。
# 锁为会话级：持有连接的进程存活期间有效；进程退出/崩溃后由 PG 自动释放。
SCHEDULER_ADVISORY_LOCK_KEY = (
    int.from_bytes(
        hashlib.sha1(b"opinion-platform-scheduler-singleton").digest()[:8], "big"
    )
    & 0x7FFFFFFFFFFFFFFF  # 限制在 bigint 有符号范围内
)
_scheduler_lock_conn = None
_scheduler_source_allowlist: frozenset[str] | None = None

# ===== Phase 5：bb-browser 专用调度 lane（独立于全局 scheduler）=====
# 独立的 PG advisory lock key，保证两个 bb-browser scheduler 不会同时运行，
# 且与全局 SCHEDULER_ADVISORY_LOCK_KEY 互不冲突。
BB_BROWSER_ADVISORY_LOCK_KEY = (
    int.from_bytes(
        hashlib.sha1(b"opinion-platform-bb-browser-scheduler-singleton").digest()[:8],
        "big",
    )
    & 0x7FFFFFFFFFFFFFFF
)
# bb-browser 专用调度的 source allowlist：严格只允许 bb_browser 一个 key。
BB_BROWSER_ALLOWLIST: frozenset[str] = frozenset({"bb_browser"})
# 绝对禁止混入 bb-browser 专用调度的 MediaCrawler/微博/小红书 key。
BB_BROWSER_FORBIDDEN_KEYS: frozenset[str] = frozenset(
    {"weibo_mediacrawler", "xhs_mediacrawler", "weibo_octopus", "weibo", "m_weibo", "xiaohongshu", "xhs"}
)
_bb_browser_lock_conn = None
_bb_browser_scheduler = None
_foreign_schedule_state = {
    "enabled": False,
    "registered": False,
    "running": False,
    "last_run": None,
}

# next_collect_time / last_collect_time 是无时区(naive)列，逻辑上按 Asia/Shanghai 本地
# 时刻存储（与 PG 会话时区、foreign.py 中 datetime.now() 的约定一致）。比较与写入必须保持
# naive 本地时刻，禁止混入 offset-aware 的 UTC 值，否则触发
# "can't compare offset-naive and offset-aware datetimes"。
_SHANGHAI_TZ = timezone(timedelta(hours=8))


def _shanghai_now_naive() -> datetime:
    """Return the current Asia/Shanghai wall-clock time as a naive datetime.

    Used for both the due-check comparison and for writing next_collect_time /
    last_collect_time, so the stored value matches the convention the rest of the
    codebase (SQL-side ``now()`` and ``foreign.py``) already relies on.
    """
    return datetime.now(timezone.utc).astimezone(_SHANGHAI_TZ).replace(tzinfo=None)


def foreign_scheduler_status() -> dict:
    """Return an observable snapshot without exposing credentials or config values."""
    snapshot = deepcopy(_foreign_schedule_state)
    snapshot["enabled"] = bool(settings.foreign_collection_schedule_enabled)
    snapshot["registered"] = bool(
        scheduler is not None and scheduler.get_job("foreign_collector") is not None
    )
    return snapshot


def _foreign_config(source: DataSource) -> dict:
    try:
        value = json.loads(source.config_json or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _run_foreign_collector_job() -> None:
    """Run the opt-in foreign-only pipeline; domestic sources never enter it."""
    if not settings.foreign_collection_schedule_enabled:
        _foreign_schedule_state["enabled"] = False
        return
    if _foreign_schedule_state["running"]:
        logger.info("Foreign scheduled collect skipped: previous run is still active")
        return
    _foreign_schedule_state["running"] = True
    started = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        rows = db.query(DataSource).filter(
            DataSource.enabled.is_(True), DataSource.schedule_enabled.is_(True)
        ).all()
        now = _shanghai_now_naive()
        due = [
            row for row in rows
            if _foreign_config(row).get("is_foreign") is True
            and (row.next_collect_time is None or row.next_collect_time <= now)
        ]
        if not due:
            return
        source_ids = [row.id for row in due]
        result = collect_foreign(
            db,
            source_ids=source_ids,
            all_sources=False,
            trigger_type="scheduled",
        )
        # Advance each source only after the collection pipeline has returned.
        # A failed fetch therefore remains due and can be retried on the next tick.
        finished_at = _shanghai_now_naive()
        source_results = {
            int(item.get("source_id")): item
            for item in (result.get("source_results") or [])
        }
        for row in due:
            source_result = source_results.get(row.id) or {}
            if source_result.get("status") != "success":
                # Do not move a failed/partial source into the future.  Other
                # sources in the same scheduled batch may still advance.
                continue
            row.last_collect_time = finished_at
            row.next_collect_time = finished_at + timedelta(
                minutes=max(int(row.schedule_interval_minutes or 60), 5)
            )
        db.commit()
        created_ids = result.get("created_ids") or []
        analyzed = 0
        risk_errors = 0
        for offset in range(0, len(created_ids), 50):
            try:
                ForeignRiskService().analyze_many(db, created_ids[offset : offset + 50])
                analyzed += len(created_ids[offset : offset + 50])
            except Exception:
                risk_errors += len(created_ids[offset : offset + 50])
                logger.exception("Foreign scheduled risk analysis failed for a chunk")
        event_result = None
        if settings.foreign_event_auto_aggregation_enabled:
            try:
                from app.services.foreign_event_auto_aggregation_service import ForeignEventAutoAggregationService

                event_result = ForeignEventAutoAggregationService().aggregate(
                    db, user_id=None, dry_run=False, opinion_ids=created_ids or None
                )
            except Exception:
                logger.exception("Foreign scheduled event aggregation failed")
        alert_result = None
        if settings.foreign_alert_auto_evaluation_enabled:
            try:
                alert_result = ForeignAlertService.evaluate(
                    db, user_id=None, dry_run=False, _run_type="auto"
                )
                db.commit()
            except Exception:
                logger.exception("Foreign scheduled alert evaluation failed")
        log_operation(
            db,
            action="FOREIGN_COLLECTION_SCHEDULED",
            resource_type="foreign_collection",
            resource_id=result.get("batch_id"),
            details={
                "source_ids": source_ids,
                "trigger_type": "scheduled",
                "fetched_raw": result.get("fetched_raw", 0),
                "created": result.get("created", 0),
                "duplicate": result.get("duplicate", 0),
                "failed": result.get("failed", 0) + risk_errors,
                "analyzed": analyzed,
                "event_status": getattr(getattr(event_result, "run", None), "status", None),
                "alert_status": getattr(alert_result, "status", None),
            },
        )
        db.commit()
        _foreign_schedule_state["last_run"] = {
            "batch_id": result.get("batch_id"),
            "source_ids": source_ids,
            "trigger_type": "scheduled",
            "started_at": started.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": "success" if not result.get("failed") and not risk_errors else "partial",
            "fetched_raw": result.get("fetched_raw", 0),
            "created": result.get("created", 0),
            "duplicate": result.get("duplicate", 0),
            "failed": result.get("failed", 0) + risk_errors,
            "error_summary": None,
        }
    except Exception as exc:
        db.rollback()
        # Keep the original due state explicitly documented for callers that
        # use a session-level claim in a future scheduler implementation.
        _foreign_schedule_state["retryable"] = True
        _foreign_schedule_state["last_run"] = {
            "trigger_type": "scheduled",
            "started_at": started.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": "failed",
            "error_summary": "Foreign scheduled collection failed; source schedule remains retryable",
        }
        logger.exception("Foreign scheduled collection failed")
    finally:
        _foreign_schedule_state["running"] = False
        db.close()


def _normalize_source_allowlist(
    source_allowlist: Collection[str] | None,
) -> frozenset[str] | None:
    """Normalize an explicit source allowlist; ``None`` preserves all-source behavior."""

    if source_allowlist is None:
        return None
    return frozenset(
        str(key).strip()
        for key in source_allowlist
        if str(key).strip()
    )


def _configured_source_allowlist() -> frozenset[str] | None:
    """Read a process-scoped CSV allowlist without changing ``.env`` or the DB."""

    raw = os.getenv("SCHEDULER_SOURCE_ALLOWLIST", "").strip()
    if not raw:
        return None
    return _normalize_source_allowlist(raw.split(","))

def _scheduler_discovery_ok() -> bool:
    """dispatch 前确认数据源发现可用（DB 可读）。

    Fix-3：registry 发现降级（DB 不可达）时禁止派发采集任务，避免 claim 了
    next_collect_time 却因装配失败而漏采 / 产生悬空任务。每次实时探测
    （复用 repository 的真实查询），DB 恢复后自动解除拦截，不会死锁。
    失败仅 ERROR 日志 + 跳过，不生成假 CollectorRun、不推进周期数据。
    """
    from app.collectors.data_source_repository import enabled_sources

    db = SessionLocal()
    try:
        enabled_sources(db)
        return True
    except Exception as exc:
        logger.error(
            "Scheduler dispatch skipped: data source discovery failed (DB unreachable). error=%s",
            exc,
        )
        return False
    finally:
        db.close()


def _run_collector_job():
    """cron 模式：全量采集（受全局 CronTrigger 驱动）。

    Fix-2：候选源必须遵守 enabled=true AND schedule_enabled=true，
    与逐源 tick 模式语义一致，禁止 cron 模式绕过 schedule_enabled。
    """
    if not _scheduler_discovery_ok():
        return
    db = SessionLocal()
    try:
        if _scheduler_source_allowlist is None:
            due = scheduled_enabled_sources(db)
        else:
            due = scheduled_enabled_sources(
                db,
                include_keys=_scheduler_source_allowlist,
            )
        keys = [r["key"] for r in due]
        if not keys:
            return
        service = CollectorService(
            include_data_source_keys=set(keys),
            exclude_data_source_keys={"weibo_octopus"},
        )
        result = service.collect_and_analyze(db, trigger_type="scheduled")
        logger.info("Scheduled collect: type=%s fetched=%d created=%d analyzed=%d failed=%d", result.collector_type, result.fetched_raw, result.created, result.analyzed, result.failed)
        # 采集后自动增量聚合（异常安全，不阻断采集主流程）。
        agg = auto_aggregate_after_collect(SessionLocal)
        logger.info("Scheduled auto-aggregate: created=%d updated=%d linked=%d", agg.get("created", 0), agg.get("updated", 0), agg.get("linked", 0))
    except CollectorThrottled:
        logger.info("Scheduled collect skipped: throttled")
    except Exception:
        logger.exception("Scheduled collect failed")
    finally:
        db.close()


def _run_collector_tick(
    include_data_source_keys: Collection[str] | None = None,
):
    """Phase DataSource-Schedule-1：按源自定义频率的逐源 tick 派发。

    流程（claim-then-dispatch，全部时间走 PG now()，规避时区偏差 R3）：
      0. dispatch 前确认数据源发现可用（Fix-3：降级时不派发，避免悬空任务）；
      1. 选出「启用 + 开启自动采集 + 非 weibo_octopus + 下次采集时间已到(NULL 视为待采集)」的源
         （查询统一收敛到 data_source_repository.due_scheduled_sources）；
      2. 一次性 UPDATE 占位（last_collect_time=now(), next_collect_time=now()+各自间隔），
         避免本次 tick 后该源被重复选中；
      3. 合并为「一次」CollectorService 调用（include=到期源 key 集合）：
         - 规避政府源 5 秒防抖（M2/R1）：单次调用内 _GOV_LAST_RUN_AT 仅在批末更新，
           同 tick 的多个政府源互不触发 Throttle；
         - 禁止逐源分别调用，减少重复装配与重复入库。
    """
    if not _scheduler_discovery_ok():
        return
    db = SessionLocal()
    try:
        # §五 可靠兜底：每次 tick 开始时先回收历史僵尸运行（覆盖跨 tick / 同进程卡死场景），
        # 避免某次采集线程异常退出导致 CollectorRun 永久停留 running。
        try:
            reclaimed = reclaim_zombie_runs(db)
            if reclaimed:
                logger.warning("调度 tick 僵尸运行回收：reclaimed=%d", reclaimed)
        except Exception:
            logger.exception("调度 tick 僵尸运行回收失败（不影响本次派发）")
        source_allowlist = (
            _normalize_source_allowlist(include_data_source_keys)
            if include_data_source_keys is not None
            else _scheduler_source_allowlist
        )
        if source_allowlist is None:
            due = due_scheduled_sources(db)
        else:
            due = due_scheduled_sources(db, include_keys=source_allowlist)
        if not due:
            return
        due_ids = [r["id"] for r in due]
        due_keys = [r["key"] for r in due]
        # claim：用各行自身 schedule_interval_minutes 计算下次时间，单次语句完成
        claim_sql = """
            UPDATE data_sources
            SET last_collect_time = now(),
                next_collect_time = now() + make_interval(mins => schedule_interval_minutes)
            WHERE id = ANY(:ids)
        """
        claim_params = {"ids": due_ids}
        claim_statement = text(claim_sql)
        if source_allowlist is not None:
            claim_statement = text(
                f"{claim_sql} AND key IN :include_keys"
            ).bindparams(bindparam("include_keys", expanding=True))
            claim_params["include_keys"] = tuple(sorted(source_allowlist))
        db.execute(claim_statement, claim_params)
        db.commit()
        logger.info("Collector tick: claimed %d sources, dispatching merged collect", len(due_ids))
        service = CollectorService(
            include_data_source_keys=set(due_keys),
            exclude_data_source_keys=set(),
        )
        result = service.collect_and_analyze_concurrent(SessionLocal, trigger_type="scheduled")
        logger.info(
            "Collector tick collect: fetched=%d created=%d analyzed=%d failed=%d",
            result.fetched_raw, result.created, result.analyzed, result.failed,
        )
        agg = auto_aggregate_after_collect(SessionLocal)
        logger.info(
            "Collector tick auto-aggregate: created=%d updated=%d linked=%d",
            agg.get("created", 0), agg.get("updated", 0), agg.get("linked", 0),
        )
    except CollectorThrottled:
        logger.info("Collector tick skipped: throttled")
    except Exception:
        logger.exception("Collector tick failed")
    finally:
        db.close()


def _run_weibo_consumer_job():
    """Consume only the completed 八爪鱼 export from the independent hourly job."""
    db = SessionLocal()
    try:
        service = CollectorService(include_data_source_keys={"weibo_octopus"})
        result = service.collect_and_analyze(db, trigger_type="weibo_scheduled")
        logger.info(
            "Scheduled Weibo collect: fetched=%d upstream=%s returned=%d created=%d duplicate=%d analyzed=%d failed=%d ack=%s",
            result.fetched_raw,
            result.upstream_total,
            result.upstream_returned,
            result.created,
            result.duplicate,
            result.analyzed,
            result.failed,
            result.ack_status,
        )
        agg = auto_aggregate_after_collect(SessionLocal)
        logger.info(
            "Scheduled Weibo auto-aggregate: created=%d updated=%d linked=%d",
            agg.get("created", 0),
            agg.get("updated", 0),
            agg.get("linked", 0),
        )
    except CollectorThrottled:
        logger.info("Scheduled Weibo collect skipped: throttled")
    except Exception:
        logger.exception("Scheduled Weibo collect failed")
    finally:
        db.close()

def _run_alert_eval_job():
    """每隔固定时间自动执行预警评估，生成新预警记录（供前端轮询推送）。"""
    db = SessionLocal()
    try:
        result = AlertService.evaluate(db)
        AlertService.sync_alert_events(db)
        logger.info("Scheduled alert eval: checked=%d created=%d", result["total_checked"], result["alerts_created"])
    except Exception:
        logger.exception("Scheduled alert eval failed")
    finally:
        db.close()

def _try_acquire_scheduler_lock() -> bool:
    """尝试获取跨进程 scheduler 单例锁（PG 会话级咨询锁）。

    返回 True 表示本进程获得锁、应启动调度器；False 表示其他实例已持有锁，
    本进程应跳过调度器（其余功能不受影响）。获取失败时（如数据库暂不可用）
    保守地返回 False，避免多实例同时启动调度器产生重复采集。
    """
    global _scheduler_lock_conn
    try:
        conn = engine.connect()
        acquired = conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": SCHEDULER_ADVISORY_LOCK_KEY},
        ).scalar()
        if acquired:
            conn.commit()  # 结束事务，但咨询锁随会话保持
            _scheduler_lock_conn = conn
            return True
        conn.close()
        return False
    except Exception:
        logger.exception("获取 scheduler 单例锁失败（保守跳过调度器）")
        return False


def _release_scheduler_lock() -> None:
    """释放 scheduler 单例锁（进程退出/关闭时调用）。"""
    global _scheduler_lock_conn
    conn = _scheduler_lock_conn
    _scheduler_lock_conn = None
    if conn is None:
        return
    try:
        conn.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": SCHEDULER_ADVISORY_LOCK_KEY},
        )
        conn.commit()
    except Exception:
        logger.warning("释放 scheduler 单例锁失败（进程退出后由 PG 自动回收）", exc_info=True)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def start_scheduler(
    *,
    source_allowlist: Collection[str] | None = None,
):
    global scheduler, _scheduler_source_allowlist
    _scheduler_source_allowlist = (
        _normalize_source_allowlist(source_allowlist)
        if source_allowlist is not None
        else _configured_source_allowlist()
    )
    fingerprint = build_scheduler_owner_fingerprint()
    logger.info(
        "[SchedulerFingerprint] %s source_allowlist=%s real_run_gate=%s",
        format_scheduler_owner_fingerprint(fingerprint),
        sorted(_scheduler_source_allowlist)
        if _scheduler_source_allowlist is not None
        else None,
        bool(settings.media_crawler_real_run_gate),
    )
    if scheduler is not None:
        return
    if not (
        settings.collector_schedule_enabled
        or settings.alert_eval_enabled
        or settings.foreign_collection_schedule_enabled
    ):
        logger.info("All scheduled jobs disabled")
        return
    # 跨进程单例：仅抢到 PG 咨询锁的进程启动调度器；未抢到则跳过但正常启动。
    if not _try_acquire_scheduler_lock():
        logger.warning(
            "本进程未获得 scheduler 单例锁（其他实例已在运行调度器），"
            "跳过启动采集/预警调度器。本进程其余功能（API、手动采集等）正常。"
        )
        return
    scheduler = AsyncIOScheduler()
    if settings.collector_schedule_enabled:
        if settings.collector_schedule_mode == "per_source":
            # Phase DataSource-Schedule-1：按源自定义频率的逐源 tick
            scheduler.add_job(
                _run_collector_tick,
                trigger=IntervalTrigger(seconds=settings.collector_tick_interval_seconds),
                id="collector_tick",
                name="Per-source collector tick",
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30,
                replace_existing=True,
            )
            logger.info(
                "Scheduler: collector_schedule_mode=per_source, tick every %ds",
                settings.collector_tick_interval_seconds,
            )
        else:
            # 回滚模式：保留全局固定 cron 全量采集（兼容旧行为）
            scheduler.add_job(_run_collector_job, trigger=CronTrigger.from_crontab(settings.collector_schedule_cron), id="collector_main", name="Main collector cycle", replace_existing=True)
        scheduler.add_job(_run_weibo_consumer_job, trigger=CronTrigger.from_crontab(settings.weibo_consumer_schedule_cron), id="weibo_consumer", name="Weibo hourly consumer", replace_existing=True)
    if settings.alert_eval_enabled:
        scheduler.add_job(_run_alert_eval_job, trigger=IntervalTrigger(minutes=settings.alert_eval_interval_minutes), id="alert_eval", name="Alert auto-evaluation", replace_existing=True)
    if settings.foreign_collection_schedule_enabled:
        scheduler.add_job(
            _run_foreign_collector_job,
            trigger=IntervalTrigger(seconds=max(30, settings.foreign_collection_schedule_interval_seconds)),
            id="foreign_collector",
            name="Foreign RSS collection",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30,
            replace_existing=True,
        )
        _foreign_schedule_state["registered"] = True
    scheduler.start()
    logger.info(
        "Scheduler started (acquired advisory lock): mode=%s alert_eval_minutes=%d",
        settings.collector_schedule_mode, settings.alert_eval_interval_minutes,
    )

def stop_scheduler():
    global scheduler
    _release_scheduler_lock()
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
    _foreign_schedule_state["registered"] = False
    _foreign_schedule_state["running"] = False
    logger.info("Scheduler stopped")


# ======================================================================
# Phase 5：bb-browser 专用调度 lane（独立 advisory lock + 严格 allowlist）
# 默认关闭（bb_browser_schedule_enabled=false），fail-closed，未授权绝不派发。
# 不修改 source 62 / source 40，不改变全局 scheduler 默认行为。
# ======================================================================

def _validate_bb_browser_allowlist(allowlist) -> str | None:
    """校验 bb-browser 专用调度 allowlist（纯函数，可测试）。

    返回错误描述；None 表示合法（恰好只含 bb_browser，无未知/禁止 key）。
    """
    keys = _normalize_source_allowlist(allowlist)
    if keys is None or len(keys) == 0:
        return "allowlist 为空或缺失（fail-closed，拒绝启动）"
    if keys == BB_BROWSER_ALLOWLIST:
        return None
    forbidden = keys & BB_BROWSER_FORBIDDEN_KEYS
    if forbidden:
        return f"allowlist 混入禁止的 MediaCrawler/微博/小红书 key: {sorted(forbidden)}"
    unknown = keys - BB_BROWSER_ALLOWLIST
    if unknown:
        return f"allowlist 含未知 source key: {sorted(unknown)}"
    return f"allowlist 必须恰好只含 bb_browser，实际={sorted(keys)}"


def _validate_bb_browser_scheduler(db) -> str | None:
    """bb-browser lane 双钥匙门禁（Phase 6）。

    第一把钥匙（config）：bb_browser_schedule_enabled=true + allowlist 恰好 bb_browser。
    第二把钥匙（DB source 62 状态）：存在 / key==bb_browser / enabled==true /
    schedule_enabled==true / collection_mode==national。

    返回错误描述；None 表示通过。runtime lock/preflight 在 start_bb_browser_scheduler
    中单独校验（见 _validate_bb_browser_runtime_lock）。
    """
    # 第一把钥匙：config
    if not settings.bb_browser_schedule_enabled:
        return "未启用（bb_browser_schedule_enabled != true）"
    raw = (settings.bb_browser_schedule_allowlist or "").strip()
    if not raw:
        return "bb_browser_schedule_allowlist 缺失（fail-closed）"
    err = _validate_bb_browser_allowlist(raw.split(","))
    if err:
        return err
    # 第二把钥匙：DB source 62 状态
    row = db.query(DataSource).filter(DataSource.id == 62).first()
    if row is None:
        return "source 62 不存在"
    if row.key != "bb_browser":
        return f"source 62 的 key 不是 bb_browser（实际={row.key}）"
    if row.enabled is not True:
        return "source 62 enabled != true（fail-closed）"
    if row.schedule_enabled is not True:
        return "source 62 schedule_enabled != true（lane 启动需 source 62 显式开启自动调度）"
    try:
        cfg = json.loads(row.config_json or "{}")
    except (TypeError, ValueError):
        return "source 62 config_json 无法解析"
    if not isinstance(cfg, dict):
        return "source 62 config_json 非对象"
    if cfg.get("collection_mode") != "national":
        return f"source 62 collection_mode != national（实际={cfg.get('collection_mode')!r}）"
    return None


def _validate_bb_browser_runtime_lock(cfg: dict) -> str | None:
    """完整 runtime preflight（Phase 7 补强，第二把钥匙的一部分）。

    verify_runtime_lock 已覆盖 worker SHA256 / node CLI SHA256 / 版本 /
    platform registry SHA256 / bb-sites HEAD / exchange_root / control_root；
    此处补充 CDP 可达 / daemon 可达 / Chrome profile 路径 / config_json 与
    runtime lock 一致性。

    cfg 为 source 62 的 config_json 解析结果。返回错误描述；None 表示全部通过。
    """
    control_root = cfg.get("control_root")
    if not control_root:
        return "source 62 config 缺 control_root"
    try:
        from app.collectors.bb_browser_runtime import probe_connectivity, verify_runtime_lock
    except Exception as exc:  # noqa: BLE001
        return f"无法导入 runtime lock 校验: {exc}"
    lock_path = Path(control_root).parent / "phase2_runtime_lock.json"
    try:
        ok, diffs = verify_runtime_lock(lock_path)
    except Exception as exc:  # noqa: BLE001
        return f"runtime lock 校验异常: {exc}"
    if not ok:
        return f"runtime lock 校验失败: {diffs}"

    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"runtime lock 无法读取: {exc}"

    # config_json 与 runtime lock 一致性（关键字段逐项比对）
    for field in ("cdp_url", "daemon_url", "exchange_root", "control_root"):
        if cfg.get(field) != lock.get(field):
            return (
                f"config_json.{field} 与 runtime lock 不一致"
                f"（config={cfg.get(field)!r}, lock={lock.get(field)!r}）"
            )

    # CDP 可达（TCP 建连，不执行命令）
    cdp_url = cfg.get("cdp_url") or lock.get("cdp_url")
    if not cdp_url:
        return "缺 cdp_url（preflight_failed）"
    if not probe_connectivity(cdp_url):
        return "CDP 不可达（preflight_failed）"

    # daemon 可达
    daemon_url = cfg.get("daemon_url") or lock.get("daemon_url")
    if not daemon_url:
        return "缺 daemon_url（preflight_failed）"
    if not probe_connectivity(daemon_url):
        return "daemon 不可达（preflight_failed）"

    # Chrome profile 路径
    profile = lock.get("chrome_profile")
    if not profile:
        return "runtime lock 缺 chrome_profile"
    if not Path(profile).exists():
        return f"Chrome profile 缺失: {profile}"

    return None


def _try_acquire_bb_browser_lock() -> bool:
    """获取 bb-browser 专用调度单例锁（独立于全局 scheduler 锁）。"""
    global _bb_browser_lock_conn
    try:
        conn = engine.connect()
        acquired = conn.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": BB_BROWSER_ADVISORY_LOCK_KEY},
        ).scalar()
        if acquired:
            conn.commit()
            _bb_browser_lock_conn = conn
            return True
        conn.close()
        return False
    except Exception:
        logger.exception("获取 bb-browser 调度单例锁失败（保守跳过）")
        return False


def _release_bb_browser_lock() -> None:
    global _bb_browser_lock_conn
    conn = _bb_browser_lock_conn
    _bb_browser_lock_conn = None
    if conn is None:
        return
    try:
        conn.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": BB_BROWSER_ADVISORY_LOCK_KEY},
        )
        conn.commit()
    except Exception:
        logger.warning("释放 bb-browser 调度单例锁失败（进程退出后由 PG 自动回收）", exc_info=True)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _run_bb_browser_tick():
    """bb-browser 专用 lane 的 tick：只派发 bb_browser（复用 claim-then-dispatch）。"""
    logger.info("[bb-browser lane] tick allowlist=%s", sorted(BB_BROWSER_ALLOWLIST))
    _run_collector_tick(include_data_source_keys=BB_BROWSER_ALLOWLIST)


def start_bb_browser_scheduler():
    """启动 bb-browser 专用调度 lane（双钥匙门禁，fail-closed，默认关闭）。

    仅当两把钥匙全部通过（config + DB source 62 状态 + runtime lock/preflight）
    才启动；独立 advisory lock。
    """
    global _bb_browser_scheduler
    if _bb_browser_scheduler is not None:
        return
    if not settings.bb_browser_schedule_enabled:
        logger.info("bb-browser 专用调度未启用（bb_browser_schedule_enabled=false）")
        return
    db = SessionLocal()
    try:
        err = _validate_bb_browser_scheduler(db)
        if err is None:
            row = db.query(DataSource).filter(DataSource.id == 62).first()
            try:
                cfg = json.loads(row.config_json or "{}") if row else {}
            except (TypeError, ValueError):
                cfg = {}
            err = _validate_bb_browser_runtime_lock(cfg)
    finally:
        db.close()
    if err:
        logger.error("bb-browser 专用调度拒绝启动（fail-closed）：%s", err)
        return
    if not _try_acquire_bb_browser_lock():
        logger.warning("bb-browser 调度单例锁已被其他进程持有，跳过启动")
        return
    _bb_browser_scheduler = AsyncIOScheduler()
    _bb_browser_scheduler.add_job(
        _run_bb_browser_tick,
        trigger=IntervalTrigger(seconds=max(5, settings.bb_browser_tick_interval_seconds)),
        id="bb_browser_tick",
        name="bb-browser dedicated collector tick",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
        replace_existing=True,
    )
    _bb_browser_scheduler.start()
    logger.info(
        "bb-browser 专用调度已启动：allowlist=%s tick=%ds",
        sorted(BB_BROWSER_ALLOWLIST),
        settings.bb_browser_tick_interval_seconds,
    )


def stop_bb_browser_scheduler():
    global _bb_browser_scheduler
    _release_bb_browser_lock()
    if _bb_browser_scheduler is not None:
        _bb_browser_scheduler.shutdown(wait=False)
        _bb_browser_scheduler = None
    logger.info("bb-browser 专用调度已停止")
