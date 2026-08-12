from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.api.foreign import ForeignAIBatchPayload, _foreign_ai_batch_preview
from app.db.session import SessionLocal
from app.models.foreign_ai_batch_run import ForeignAIBatchRun
from app.models.foreign_analysis_run import ForeignAnalysisRun
from app.models.foreign_opinion import ForeignOpinion
from app.services.foreign_ai_service import ForeignAIService


def _opinion(db, suffix: str, published_at: datetime) -> ForeignOpinion:
    row = ForeignOpinion(
        source_key=f"batch-contract-{suffix}",
        source_name_snapshot="Batch contract source",
        title=f"Batch contract {suffix}",
        summary="batch contract",
        content="batch contract article",
        url=f"https://batch-contract.test/{suffix}",
        published_at=published_at,
        collected_at=published_at,
        matched_keywords=["batch"],
        content_hash=(suffix * 64)[:64],
    )
    db.add(row)
    db.flush()
    return row


def test_batch_selection_applies_time_boundary_and_current_filters():
    db = SessionLocal()
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    now = datetime.now(timezone.utc)
    try:
        inside = _opinion(db, suffix + "a", now - timedelta(days=1))
        _opinion(db, suffix + "b", now - timedelta(days=4))
        db.commit()
        payload = ForeignAIBatchPayload(
            scope="time",
            date_from=(now - timedelta(days=2)).strftime("%Y-%m-%d"),
            date_to=now.strftime("%Y-%m-%d"),
            use_current_filters=True,
            current_filters={"q": f"Batch contract {suffix}", "source": "Batch contract source", "risk_source": "rule"},
            only_unanalyzed=True,
        )
        preview = _foreign_ai_batch_preview(db, payload)
        assert inside.id in preview["opinion_ids"]
        assert preview["matched_count"] == 1
    finally:
        db.rollback()
        db.query(ForeignOpinion).filter(ForeignOpinion.source_key.like(f"batch-contract-{suffix}%")).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_analysis_run_carries_batch_run_id():
    db = SessionLocal()
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    try:
        opinion = _opinion(db, suffix, datetime.now(timezone.utc))
        batch = ForeignAIBatchRun(run_id=f"test-{suffix}", scope="count", opinion_ids=[opinion.id], total_count=1)
        db.add(batch)
        db.flush()
        service = ForeignAIService()
        run = service._new_run(db, opinion.id, batch_run_id=batch.run_id)
        db.commit()
        loaded = db.scalar(select(ForeignAnalysisRun).where(ForeignAnalysisRun.id == run.id))
        assert loaded is not None
        assert loaded.batch_run_id == batch.run_id
    finally:
        db.query(ForeignAnalysisRun).filter(ForeignAnalysisRun.batch_run_id == f"test-{suffix}").delete(synchronize_session=False)
        db.query(ForeignAIBatchRun).filter(ForeignAIBatchRun.run_id == f"test-{suffix}").delete(synchronize_session=False)
        db.query(ForeignOpinion).filter(ForeignOpinion.source_key == f"batch-contract-{suffix}").delete(synchronize_session=False)
        db.commit()
        db.close()
