from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

from app.api.domestic_ai_analysis import DomesticAIBatchPayload, _batch_preview, _selection
from app.db.session import SessionLocal
from app.models.alert import AlertRecord, AlertRule
from app.models.domestic_ai_alert_candidate import DomesticAIAlertCandidate
from app.models.domestic_ai_result import DomesticAIResult
from app.models.domestic_manual_review import DomesticManualReview
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.domestic_manual_review_service import (
    confirm_alert_for_review,
    confirm_event_for_review,
    ensure_domestic_manual_review,
)
from app.services.alert_service import AlertService


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _opinion(db, suffix: str, *, score: int = 30, published_at: datetime | None = None, content_type: str | None = "news") -> Opinion:
    row = Opinion(
        title=f"domestic fixture {suffix}",
        content="domestic manual review fixture content",
        source="domestic-fixture",
        url=f"https://domestic-fixture.test/{suffix}",
        region_id=1,
        risk_score=score,
        sentiment="negative",
        summary="fixture",
        keywords="事故",
        analysis_status="completed",
        content_type=content_type,
        publish_time=published_at or datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def _ai_result(db, opinion: Opinion, *, score: int = 80, status: str = "completed") -> DomesticAIResult:
    row = DomesticAIResult(
        opinion_id=opinion.id,
        content_hash=_suffix(),
        model_name="fixture",
        model_version="fixture-v1",
        status=status,
        summary="AI fixture",
        sentiment="negative",
        risk_score=score,
        keywords=["事故"],
        suggestion="fixture",
        analyzed_at=datetime.now(timezone.utc),
        is_current=status == "completed",
    )
    db.add(row)
    db.flush()
    return row


def _ai_rule(db, threshold: int = 70) -> AlertRule:
    row = AlertRule(
        name=f"domestic ai rule {_suffix()}",
        rule_type="ai_risk_score",
        risk_threshold=threshold,
        risk_level="high",
        enabled=True,
    )
    db.add(row)
    db.flush()
    return row


def _cleanup(db):
    db.execute(
        text(
            "TRUNCATE TABLE domestic_ai_alert_candidates, domestic_manual_reviews, "
            "domestic_ai_results, domestic_ai_batch_runs, alert_records, events, "
            "event_opinions, alert_rules, opinions CASCADE"
        )
    )
    db.commit()


def test_domestic_review_chain_is_idempotent_and_keeps_rule_risk():
    db = SessionLocal()
    try:
        _cleanup(db)
        opinion = _opinion(db, _suffix(), score=20)
        ai = _ai_result(db, opinion, score=90)
        _ai_rule(db, threshold=70)
        db.commit()

        review, created = ensure_domestic_manual_review(db, opinion.id, ai.id)
        db.commit()
        same_review, reused = ensure_domestic_manual_review(db, opinion.id, ai.id)
        db.commit()

        assert created is True
        assert reused is False
        assert review.id == same_review.id
        assert opinion.risk_score == 20
        assert review.rule_risk_snapshot["risk_score"] == 20
        assert review.ai_risk_snapshot["risk_score"] == 90
        assert db.scalar(select(Event.id).where(Event.origin_review_id == review.id)) is None
        assert db.scalar(select(AlertRecord.id).where(AlertRecord.origin_review_id == review.id)) is None
    finally:
        _cleanup(db)
        db.close()


def test_force_supersedes_pending_review_and_failed_ai_cannot_review():
    db = SessionLocal()
    try:
        _cleanup(db)
        opinion = _opinion(db, _suffix())
        ai = _ai_result(db, opinion)
        db.commit()
        old, _ = ensure_domestic_manual_review(db, opinion.id, ai.id)
        db.commit()
        new, created = ensure_domestic_manual_review(db, opinion.id, ai.id, force=True)
        db.commit()
        db.refresh(old)
        assert created is True
        assert old.review_status == "superseded"
        assert new.id != old.id

        failed = _ai_result(db, opinion, status="failed")
        db.commit()
        try:
            ensure_domestic_manual_review(db, opinion.id, failed.id)
        except ValueError as exc:
            assert "completed" in str(exc)
        else:
            raise AssertionError("failed AI result must not create a review")
    finally:
        _cleanup(db)
        db.close()


def test_domestic_batch_selection_filters_low_value_and_applies_unanalyzed_before_recent_limit():
    db = SessionLocal()
    try:
        _cleanup(db)
        now = datetime.now(timezone.utc)
        low = _opinion(db, _suffix(), published_at=now, content_type="advertising")
        analyzed = _opinion(db, _suffix(), published_at=now - timedelta(minutes=1))
        pending = _opinion(db, _suffix(), published_at=now - timedelta(minutes=2))
        _ai_result(db, analyzed)
        db.commit()

        payload = DomesticAIBatchPayload(scope="recent", recent_n=1, only_unanalyzed=True, filters={})
        selected = _selection(db, payload)
        assert [row.id for row in selected] == [pending.id]
        assert low.id not in [row.id for row in selected]

        preview = _batch_preview(db, payload)
        assert preview["matched_count"] == 1
        assert preview["pending_analysis_count"] == 1
    finally:
        _cleanup(db)
        db.close()


def test_confirm_event_and_alert_are_scoped_and_idempotent():
    db = SessionLocal()
    try:
        _cleanup(db)
        opinion = _opinion(db, _suffix(), score=10)
        ai = _ai_result(db, opinion, score=90)
        _ai_rule(db, threshold=70)
        db.commit()
        review, _ = ensure_domestic_manual_review(db, opinion.id, ai.id)
        review.confirmation_version = "domestic-test-v1"
        db.commit()

        event_result = confirm_event_for_review(db, review, user_id=None, reason="test", request_id="event-1")
        assert event_result["created_count"] == 1
        event_again = confirm_event_for_review(db, review, user_id=None, reason="test", request_id="event-2")
        assert event_again["existing_count"] == 1

        alert_result = confirm_alert_for_review(db, review, user_id=None, reason="test", request_id="alert-1")
        assert alert_result["created_count"] == 1
        alert_again = confirm_alert_for_review(db, review, user_id=None, reason="test", request_id="alert-2")
        assert alert_again["created_count"] == 0
        assert db.scalar(select(AlertRecord.evaluation_source).where(AlertRecord.origin_review_id == review.id)) == "manual_review_ai"
        assert db.scalar(select(Event.confirmation_source).where(Event.origin_review_id == review.id)) == "manual_review_ai"
        assert db.scalar(select(text("COUNT(*)")).select_from(AlertRecord).where(AlertRecord.origin_review_id == review.id)) == 1
        assert db.scalar(select(text("COUNT(*)")).select_from(Event).where(Event.origin_review_id == review.id)) == 1
        assert db.scalar(select(text("COUNT(*)")).select_from(DomesticAIAlertCandidate).where(DomesticAIAlertCandidate.review_id == review.id)) == 1
    finally:
        _cleanup(db)
        db.close()


def test_confirm_event_reuses_aggregator_event_instead_of_duplicating():
    db = SessionLocal()
    try:
        _cleanup(db)
        opinion = _opinion(db, _suffix(), score=10)
        ai = _ai_result(db, opinion, score=90)
        db.commit()
        review, _ = ensure_domestic_manual_review(db, opinion.id, ai.id)
        review.confirmation_version = "domestic-test-v1"
        db.commit()

        # 模拟事件中心自动聚合链路已将该舆情并入一个 Event（confirmation_source=NULL, status=active）
        agg_event = Event(
            title="aggregated event",
            description="agg",
            opinion_count=1,
            first_time=opinion.publish_time,
            last_time=opinion.publish_time,
        )
        db.add(agg_event)
        db.flush()
        db.add(EventOpinion(event_id=agg_event.id, opinion_id=opinion.id))
        db.commit()

        # 人工确认：应认领复用聚合事件，而不是新建第二条
        event_result = confirm_event_for_review(db, review, user_id=None, reason="test", request_id="event-agg")
        assert event_result["created_count"] == 0
        assert event_result["existing_count"] == 1
        assert event_result["event_ids"] == [agg_event.id]
        assert db.scalar(select(text("COUNT(*)")).select_from(Event)) == 1
        assert db.scalar(select(Event.confirmation_source).where(Event.id == agg_event.id)) == "manual_review_ai"
        assert db.scalar(select(Event.origin_review_id).where(Event.id == agg_event.id)) == review.id

        # 再次确认不应重复创建
        again = confirm_event_for_review(db, review, user_id=None, reason="test", request_id="event-agg-2")
        assert again["existing_count"] == 1
        assert db.scalar(select(text("COUNT(*)")).select_from(Event)) == 1
    finally:
        _cleanup(db)
        db.close()


def test_normal_alert_evaluation_skips_ai_rules_and_uses_rule_score():
    db = SessionLocal()
    try:
        _cleanup(db)
        opinion = _opinion(db, _suffix(), score=20)
        _ai_result(db, opinion, score=95)
        _ai_rule(db, threshold=70)
        normal_rule = AlertRule(
            name=f"domestic rule {_suffix()}",
            rule_type="risk_score",
            risk_threshold=70,
            keywords="事故",
            risk_level="high",
            enabled=True,
        )
        db.add(normal_rule)
        db.commit()

        result = AlertService.evaluate(db)
        assert result["alerts_created"] == 0
        assert db.scalar(select(AlertRecord.id).where(AlertRecord.opinion_id == opinion.id)) is None

        opinion.risk_score = 80
        db.commit()
        result = AlertService.evaluate(db)
        assert result["alerts_created"] == 1
        alert = db.scalar(select(AlertRecord).where(AlertRecord.opinion_id == opinion.id))
        assert alert is not None
        assert alert.evaluation_source == "rule"
    finally:
        _cleanup(db)
        db.close()
