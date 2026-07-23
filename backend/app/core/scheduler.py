from __future__ import annotations
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from app.collectors.service import CollectorService, CollectorThrottled
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.event.aggregator import auto_aggregate_after_collect
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)
scheduler = None

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

def start_scheduler():
    global scheduler
    if scheduler is not None:
        return
    if not (settings.collector_schedule_enabled or settings.alert_eval_enabled):
        logger.info("All scheduled jobs disabled")
        return
    scheduler = AsyncIOScheduler()
    if settings.collector_schedule_enabled:
        scheduler.add_job(_run_collector_job, trigger=CronTrigger.from_crontab(settings.collector_schedule_cron), id="collector_main", name="Main collector cycle", replace_existing=True)
    if settings.alert_eval_enabled:
        scheduler.add_job(_run_alert_eval_job, trigger=IntervalTrigger(minutes=settings.alert_eval_interval_minutes), id="alert_eval", name="Alert auto-evaluation", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started: collector_cron=%s alert_eval_minutes=%d", settings.collector_schedule_cron, settings.alert_eval_interval_minutes)

def stop_scheduler():
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler stopped")
