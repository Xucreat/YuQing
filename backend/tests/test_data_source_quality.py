"""Read-only quality indicators for data-source administration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, text

from app.db.session import SessionLocal
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource


SOURCE_KEY = "phase8c_quality_source"
SOURCE_NAME = "Phase8C Quality Source"


def test_data_source_quality_uses_collector_runs_only(client, auth_headers) -> None:
    db = SessionLocal()
    try:
        db.query(CollectorRun).filter(CollectorRun.collector_name == SOURCE_NAME).delete(synchronize_session=False)
        db.query(DataSource).filter(DataSource.key == SOURCE_KEY).delete(synchronize_session=False)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        source_result = db.execute(insert(DataSource).values(
            key=SOURCE_KEY,
            name=SOURCE_NAME,
            type="news_site",
            class_path="app.collectors.generic_site.GenericSiteCollector",
            priority=999,
            enabled=True,
        ))
        db.execute(text(
            "INSERT INTO collector_runs (collector_name, start_time, fetched_raw, created, analyzed, failed, status) "
            "VALUES (:collector_name, :start_time, :fetched_raw, :created, :analyzed, :failed, :status)"
        ), [
                {"collector_name": SOURCE_NAME, "start_time": now - timedelta(minutes=1), "status": "failed", "fetched_raw": 0, "created": 0, "analyzed": 0, "failed": 1},
                {"collector_name": SOURCE_NAME, "start_time": now - timedelta(minutes=2), "status": "error", "fetched_raw": 0, "created": 0, "analyzed": 0, "failed": 1},
                {"collector_name": SOURCE_NAME, "start_time": now - timedelta(minutes=3), "status": "success", "fetched_raw": 0, "created": 0, "analyzed": 0, "failed": 0},
                {"collector_name": SOURCE_NAME, "start_time": now - timedelta(minutes=4), "status": "success", "fetched_raw": 4, "created": 2, "analyzed": 0, "failed": 0},
        ])
        db.commit()
        source_id = source_result.inserted_primary_key[0]

        response = client.get("/api/admin/data-sources/quality?days=7", headers=auth_headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        item = next(row for row in payload["items"] if row["data_source_id"] == source_id)

        assert payload["days"] == 7
        assert item["run_count"] == 4
        assert item["success_rate"] == 0.5
        assert item["fetched_nonzero_rate"] == 0.25
        assert item["fetched_zero_rate"] == 0.75
        assert item["created_nonzero_rate"] == 0.25
        assert item["fetched_raw_total"] == 4
        assert item["created_total"] == 2
        assert item["latest_status"] == "failed"
        assert item["latest_fetched_raw"] == 0
        assert item["latest_created"] == 0
        assert item["consecutive_failed_count"] == 2
        assert item["consecutive_empty_fetch_count"] == 3
        assert item["empty_fetch_risk"] == "high"
    finally:
        db.rollback()
        db.query(CollectorRun).filter(CollectorRun.collector_name == SOURCE_NAME).delete(synchronize_session=False)
        db.query(DataSource).filter(DataSource.key == SOURCE_KEY).delete(synchronize_session=False)
        db.commit()
        db.close()
