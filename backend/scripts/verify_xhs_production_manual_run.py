"""Explicitly confirmed manual XHS production-run verifier.

This script never creates a DataSource and never starts the Scheduler. It
resolves only the formal ``xhs_mediacrawler`` source, runs it with
``trigger_type=manual``, and emits a small sanitized result.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


SOURCE_KEY = "xhs_mediacrawler"
COLLECTOR_NAME = "MediaCrawler[xiaohongshu]"


def _configure_runtime_environment(args: argparse.Namespace) -> None:
    if not args.confirm_real_run:
        raise ValueError("--confirm-real-run is required")
    os.environ["MEDIA_CRAWLER_ENABLE_REAL_RUN"] = "true"
    os.environ["MEDIA_CRAWLER_REAL_RUN_GATE"] = "true"
    os.environ["COLLECTOR_SCHEDULE_ENABLED"] = "false"
    os.environ["ALERT_EVAL_ENABLED"] = "false"
    for name, value in (
        ("MEDIA_CRAWLER_ROOT", args.runtime_root),
        ("MEDIA_CRAWLER_PROFILE_ROOT", args.profile_root),
        ("MEDIA_CRAWLER_CHECKOUT_ROOT", args.checkout_root),
        ("MEDIA_CRAWLER_ENTRY", args.entry),
    ):
        if value:
            os.environ[name] = value


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one explicitly confirmed manual XHS production verification"
    )
    parser.add_argument("--confirm-real-run", action="store_true")
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument("--runtime-root")
    parser.add_argument("--profile-root")
    parser.add_argument("--checkout-root")
    parser.add_argument("--entry")
    args = parser.parse_args(argv)

    try:
        _configure_runtime_environment(args)
    except ValueError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 3

    backend_root = Path(__file__).resolve().parents[1]
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from sqlalchemy import select

    from app.collectors.service import CollectorService
    from app.db.session import SessionLocal
    from app.models.collector_run import CollectorRun
    from app.models.data_source import DataSource
    from app.models.opinion import Opinion

    started = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        source = db.scalar(select(DataSource).where(DataSource.key == SOURCE_KEY))
        if source is None:
            raise RuntimeError(f"DataSource not found: {SOURCE_KEY}")
        if not source.enabled:
            raise RuntimeError(f"DataSource is disabled: {SOURCE_KEY}")
        if source.schedule_enabled:
            raise RuntimeError("refusing manual verifier while schedule_enabled=true")

        service = CollectorService(
            include_data_source_keys={SOURCE_KEY},
            exclude_data_source_keys=set(),
        )
        result = service.collect_and_analyze(db, trigger_type="manual")
        latest = db.scalar(
            select(CollectorRun)
            .where(CollectorRun.collector_name == COLLECTOR_NAME)
            .order_by(CollectorRun.id.desc())
        )
        complete_opinions = db.scalar(
            select(Opinion.id)
            .where(
                Opinion.source == "xiaohongshu",
                Opinion.source_type == "xhs_note",
                Opinion.external_id.is_not(None),
                Opinion.content.is_not(None),
                Opinion.publish_time.is_not(None),
            )
            .limit(1)
        )
        payload = {
            "status": (
                "success"
                if latest
                and latest.status == "success"
                and latest.fetched_raw > 0
                and latest.failed == 0
                and complete_opinions is not None
                else "failed"
            ),
            "source_key": SOURCE_KEY,
            "trigger_type": "manual",
            "started_at": started,
            "finished_at": datetime.now(timezone.utc),
            "collector_result": {
                "fetched_raw": result.fetched_raw,
                "created": result.created,
                "duplicate": result.duplicate,
                "failed": result.failed,
            },
            "collector_run": (
                {
                    "id": latest.id,
                    "collector_name": latest.collector_name,
                    "status": latest.status,
                    "fetched_raw": latest.fetched_raw,
                    "created": latest.created,
                    "duplicate": latest.duplicate,
                    "failed": latest.failed,
                }
                if latest
                else None
            ),
            "complete_xhs_opinion_exists": complete_opinions is not None,
            "scheduler_started": False,
        }
        print(json.dumps(payload, ensure_ascii=False, default=_json_default))
        return 0 if payload["status"] == "success" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

