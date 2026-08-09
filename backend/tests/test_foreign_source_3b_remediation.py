"""Focused Phase 3B remediation tests; all rows are isolated and cleaned up."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

from app.db.session import SessionLocal
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_run import ForeignEventRun
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_event_service import ForeignEventService


ROOT = Path(__file__).resolve().parents[2]


def _make_opinion(db, suffix: str, index: int, source: str, published_at: datetime):
    row = ForeignOpinion(
        source_key=f"remediation_{suffix}_{index}",
        source_name_snapshot=source,
        title=f"Remediation article {index}",
        summary="Foreign event fixture summary",
        content="Foreign event fixture content",
        url=f"https://remediation.invalid/{suffix}/{index}",
        published_at=published_at,
        collected_at=published_at + timedelta(minutes=1),
        matched_keywords=["China"],
        content_hash=f"{suffix}{index}".encode().hex().ljust(64, "0"),
    )
    db.add(row)
    db.flush()
    return row


def _make_event(db, title: str, opinions: list[ForeignOpinion]) -> ForeignEvent:
    event = ForeignEvent(
        title=title,
        summary="fixture",
        language="en",
        event_status="confirmed",
        risk_level="unknown",
        heat_score=999,
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        opinion_count=999,
        source_count=999,
        confidence=0.6,
        aggregation_version="foreign-event-v1",
    )
    db.add(event)
    db.flush()
    for opinion in opinions:
        db.add(
            ForeignEventOpinion(
                foreign_event_id=event.id,
                foreign_opinion_id=opinion.id,
                relation_type="primary",
            )
        )
    return event


def _cleanup(db, event_ids: list[int], opinion_ids: list[int]) -> None:
    db.query(ForeignEventAction).filter(
        (ForeignEventAction.foreign_event_id.in_(event_ids))
        | (ForeignEventAction.target_event_id.in_(event_ids))
    ).delete(synchronize_session=False)
    db.query(ForeignEventOpinion).filter(
        ForeignEventOpinion.foreign_event_id.in_(event_ids)
    ).delete(synchronize_session=False)
    db.query(ForeignRiskResult).filter(
        ForeignRiskResult.foreign_opinion_id.in_(opinion_ids)
    ).delete(synchronize_session=False)
    db.query(ForeignEvent).filter(ForeignEvent.id.in_(event_ids)).delete(
        synchronize_session=False
    )
    db.query(ForeignOpinion).filter(ForeignOpinion.id.in_(opinion_ids)).delete(
        synchronize_session=False
    )
    db.commit()


def test_merge_recomputes_counts_times_sources_and_heat_from_links():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    base = datetime(2026, 8, 8, 1, 0, tzinfo=timezone.utc)
    opinions = [
        _make_opinion(db, suffix, 1, "Fox News", base),
        _make_opinion(db, suffix, 2, "Guardian", base + timedelta(hours=2)),
        _make_opinion(db, suffix, 3, "Guardian", base + timedelta(hours=4)),
        _make_opinion(db, suffix, 4, "NYT Chinese", base + timedelta(hours=6)),
    ]
    source = _make_event(db, "source", opinions[:2])
    target = _make_event(db, "target", opinions[2:])
    for opinion, score in zip(opinions, [30, 60, 80, 40]):
        db.add(
            ForeignRiskResult(
                foreign_opinion_id=opinion.id,
                content_hash=opinion.content_hash,
                language="en",
                risk_score=score,
                risk_level="high" if score >= 70 else "medium" if score >= 40 else "low",
                sentiment="neutral",
                risk_category="fixture",
                matched_terms=[],
                explanation="fixture",
                analyzer_type="rule",
                model_name="foreign-rule",
                model_version="test-v1",
                analysis_status="completed",
                analyzed_at=opinion.published_at,
                is_current=True,
            )
        )
    db.commit()
    event_ids = [source.id, target.id]
    opinion_ids = [opinion.id for opinion in opinions]
    persisted_times = [opinion.published_at for opinion in opinions]
    try:
        merged = ForeignEventService().merge_events(
            db,
            source.id,
            target.id,
            user_id=None,
            reason="remediation fixture",
            request_id=f"merge-{suffix}",
        )
        assert merged.opinion_count == 4
        assert merged.source_count == 3
        assert merged.first_seen_at == min(persisted_times)
        assert merged.last_seen_at == max(persisted_times)
        assert merged.heat_score == 80
        assert merged.risk_level == "high"
        assert db.get(ForeignEvent, source.id).opinion_count == 0

        repeated = ForeignEventService().merge_events(
            db,
            source.id,
            target.id,
            user_id=None,
            reason="same request",
            request_id=f"merge-{suffix}",
        )
        assert repeated.id == target.id
        assert repeated.opinion_count == 4
        assert db.query(ForeignEventOpinion).filter(
            ForeignEventOpinion.foreign_event_id == target.id
        ).count() == 4
    finally:
        _cleanup(db, event_ids, opinion_ids)
        db.close()


def test_merge_deduplicates_shared_article_and_split_recomputes_metrics():
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    base = datetime(2026, 8, 8, 2, 0, tzinfo=timezone.utc)
    opinions = [
        _make_opinion(db, suffix, 1, "Fox News", base),
        _make_opinion(db, suffix, 2, "Guardian", base + timedelta(hours=1)),
        _make_opinion(db, suffix, 3, "NYT Chinese", base + timedelta(hours=2)),
    ]
    source = _make_event(db, "source", opinions[:2])
    target = _make_event(db, "target", [opinions[1], opinions[2]])
    db.commit()
    event_ids = [source.id, target.id]
    opinion_ids = [opinion.id for opinion in opinions]
    persisted_times = [opinion.published_at for opinion in opinions]
    try:
        merged = ForeignEventService().merge_events(
            db,
            source.id,
            target.id,
            user_id=None,
            reason="deduplicate fixture",
            request_id=f"merge-{suffix}",
        )
        assert merged.opinion_count == 3
        assert merged.source_count == 3

        split = ForeignEventService().split_event(
            db,
            target.id,
            [opinions[2].id],
            user_id=None,
            reason="split fixture",
            request_id=f"split-{suffix}",
        )
        assert split.opinion_count == 1
        assert split.source_count == 1
        remaining = db.get(ForeignEvent, target.id)
        assert remaining.opinion_count == 2
        assert remaining.source_count == 2
        assert remaining.first_seen_at == min(persisted_times[:2])
        assert remaining.last_seen_at == max(persisted_times[:2])
        event_ids.append(split.id)
    finally:
        _cleanup(db, event_ids, opinion_ids)
        db.close()


def test_foreign_event_remediation_contract_exposes_metrics_and_failure_state():
    service = (ROOT / "backend" / "app" / "services" / "foreign_event_service.py").read_text(encoding="utf-8")
    workspace = (ROOT / "frontend" / "src" / "views" / "ForeignWorkspace.vue").read_text(encoding="utf-8")
    assert "def recompute_foreign_event_metrics" in service
    assert '"heat_score": event.heat_score' in service
    assert '"first_seen_at": event.first_seen_at.isoformat()' in service
    assert '"last_seen_at": event.last_seen_at.isoformat()' in service
    assert "row.heat_score" in workspace
    assert "row.first_seen_at" in workspace
    assert "row.last_seen_at" in workspace
    assert "eventRunFailures" in workspace
    assert "status failed" in workspace


def test_failed_foreign_event_run_is_returned_by_scoped_api(client, auth_headers):
    db = SessionLocal()
    run = ForeignEventRun(
        scope="foreign",
        trigger_type="dry_run",
        aggregation_version="foreign-event-v1",
        status="failed",
        dry_run=True,
        failed_count=1,
        error_message="fixture failure summary",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    run_id = run.id
    try:
        response = client.get(
            "/api/foreign/event-runs",
            headers=auth_headers,
            params={"status": "failed", "size": 100},
        )
        assert response.status_code == 200, response.text
        item = next(row for row in response.json()["items"] if row["id"] == run_id)
        assert item["status"] == "failed"
        assert item["finished_at"]
        assert item["error_message"] == "fixture failure summary"
    finally:
        db.query(ForeignEventRun).filter(ForeignEventRun.id == run_id).delete()
        db.commit()
        db.close()
