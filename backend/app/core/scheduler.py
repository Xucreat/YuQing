from __future__ import annotations
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.collectors.service import CollectorService, CollectorThrottled
from app.core.config import settings
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
scheduler = None

def _run_collector_job():
    db = SessionLocal()
    try:
        service = CollectorService()
        result = service.collect_and_analyze(db)
        logger.info("Scheduled collect: type=%s fetched=%d created=%d analyzed=%d failed=%d", result.collector_type, result.fetched_raw, result.created, result.analyzed, result.failed)
    except CollectorThrottled:
        logger.info("Scheduled collect skipped: throttled")
    except Exception:
        logger.exception("Scheduled collect failed")
    finally:
        db.close()

def start_scheduler():
    global scheduler
    if scheduler is not None:
        return
    if not settings.collector_schedule_enabled:
        logger.info("Scheduled collection disabled")
        return
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_run_collector_job, trigger=CronTrigger.from_crontab(settings.collector_schedule_cron), id="collector_main", name="Main collector cycle", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started: cron=%s", settings.collector_schedule_cron)

def stop_scheduler():
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None
        logger.info("Scheduler stopped")
