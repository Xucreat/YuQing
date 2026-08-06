from __future__ import annotations
import logging
import hashlib
import os
from collections.abc import Collection

from sqlalchemy import bindparam, text

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.collectors.service import CollectorService, CollectorThrottled
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
    if not (settings.collector_schedule_enabled or settings.alert_eval_enabled):
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
        logger.info("Scheduler stopped")
