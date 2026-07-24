from __future__ import annotations
import logging
import hashlib

from sqlalchemy import text

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.collectors.service import CollectorService, CollectorThrottled
from app.core.config import settings
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

def _run_collector_job():
    db = SessionLocal()
    try:
        service = CollectorService()
        result = service.collect_and_analyze(db)
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


def start_scheduler():
    global scheduler
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
        scheduler.add_job(_run_collector_job, trigger=CronTrigger.from_crontab(settings.collector_schedule_cron), id="collector_main", name="Main collector cycle", replace_existing=True)
    if settings.alert_eval_enabled:
        scheduler.add_job(_run_alert_eval_job, trigger=IntervalTrigger(minutes=settings.alert_eval_interval_minutes), id="alert_eval", name="Alert auto-evaluation", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started (acquired advisory lock): collector_cron=%s alert_eval_minutes=%d", settings.collector_schedule_cron, settings.alert_eval_interval_minutes)

def stop_scheduler():
    global scheduler
    _release_scheduler_lock()
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler stopped")
