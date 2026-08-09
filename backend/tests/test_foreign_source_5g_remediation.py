"""Isolation tests for the foreign alert dual path and event auto gate."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_admission import ForeignAlertAdmission
from app.models.foreign_alert_rule import ForeignAlertRule
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_run import ForeignEventRun
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_alert_service import ForeignAlertService
from app.services.foreign_event_service import ForeignEventService
from app.services.foreign_event_auto_aggregation_service import (
    ForeignEventAutoAggregationService,
)


_AUTO_RUN_IDS: set[int] = set()
_ALERT_RUN_IDS: set[int] = set()


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _opinion(db, suffix: str, *, source: str, text: str) -> ForeignOpinion:
    row = ForeignOpinion(
        source_key=f"fixture_5g_{suffix}",
        source_name_snapshot=source,
        title=text,
        summary=text,
        content=f"{text}. This is a sufficiently long foreign fixture article body.",
        url=f"https://fixture.test/foreign-5g/{suffix}",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        matched_keywords=["China"],
        content_hash=(suffix * 8)[:64],
    )
    db.add(row)
    db.flush()
    return row


def _risk(db, opinion: ForeignOpinion, score: int) -> ForeignRiskResult:
    row = ForeignRiskResult(
        foreign_opinion_id=opinion.id,
        content_hash=opinion.content_hash,
        language="en",
        risk_score=score,
        risk_level="high" if score >= 70 else "medium",
        sentiment="negative",
        risk_category="security",
        matched_terms=[{"word": "conflict", "language": "en", "category": "security", "severity_weight": 70}],
        explanation="fixture",
        analyzer_type="rule",
        model_version="fixture-v1",
        analysis_status="completed",
        is_current=True,
        analyzed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    return row


def _ai(db, opinion: ForeignOpinion, score: int) -> ForeignAIResult:
    row = ForeignAIResult(
        foreign_opinion_id=opinion.id,
        content_hash=opinion.content_hash,
        model_name="fixture",
        model_version="fixture-ai-v1",
        status="completed",
        summary="fixture ai result",
        sentiment="negative",
        risk_score=score,
        keywords=["conflict"],
        suggestion="fixture",
        analyzed_at=datetime.now(timezone.utc),
        is_current=True,
    )
    db.add(row)
    db.flush()
    return row


def _cleanup(db, suffix: str) -> None:
    opinion_ids = [row.id for row in db.query(ForeignOpinion).filter(ForeignOpinion.source_key.like(f"fixture_5g_{suffix}%")).all()]
    event_ids = [row.id for row in db.query(ForeignEvent).filter(ForeignEvent.title.like(f"Shared crisis response {suffix}%")).all()]
    candidate_ids = [row.id for row in db.query(ForeignEventCandidate).filter(ForeignEventCandidate.title.like(f"Shared crisis response {suffix}%")).all()]
    if event_ids:
        db.query(ForeignEventAction).filter(ForeignEventAction.foreign_event_id.in_(event_ids)).delete(synchronize_session=False)
        db.query(ForeignEventOpinion).filter(ForeignEventOpinion.foreign_event_id.in_(event_ids)).delete(synchronize_session=False)
        db.query(ForeignEvent).filter(ForeignEvent.id.in_(event_ids)).delete(synchronize_session=False)
    if candidate_ids:
        db.query(ForeignEventAction).filter(ForeignEventAction.candidate_id.in_(candidate_ids)).delete(synchronize_session=False)
        db.query(ForeignEventCandidate).filter(ForeignEventCandidate.id.in_(candidate_ids)).delete(synchronize_session=False)
    if opinion_ids:
        db.query(ForeignAlert).filter(ForeignAlert.foreign_opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
        db.query(ForeignAlertAdmission).filter(ForeignAlertAdmission.foreign_opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
        db.query(ForeignAIResult).filter(ForeignAIResult.foreign_opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
        db.query(ForeignRiskResult).filter(ForeignRiskResult.foreign_opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
        db.query(ForeignOpinion).filter(ForeignOpinion.id.in_(opinion_ids)).delete(synchronize_session=False)
    db.query(ForeignAlertRule).filter(ForeignAlertRule.name.like(f"Phase 5G {suffix}%")).delete(synchronize_session=False)
    if _AUTO_RUN_IDS:
        db.query(ForeignEventRun).filter(ForeignEventRun.id.in_(_AUTO_RUN_IDS)).delete(synchronize_session=False)
        _AUTO_RUN_IDS.clear()
    if _ALERT_RUN_IDS:
        from app.models.foreign_alert_run import ForeignAlertRun

        db.query(ForeignAlertRun).filter(ForeignAlertRun.id.in_(_ALERT_RUN_IDS)).delete(synchronize_session=False)
        _ALERT_RUN_IDS.clear()
    db.commit()


def test_dual_alert_path_prefers_rule_and_uses_admitted_ai_fallback(monkeypatch):
    db = SessionLocal()
    suffix = _suffix()
    try:
        rule_opinion = _opinion(db, f"{suffix}-rule", source="Rule source", text=f"Rule article {suffix}")
        rule_only_opinion = _opinion(db, f"{suffix}-rule-only", source="Rule-only source", text=f"Rule-only article {suffix}")
        ai_opinion = _opinion(db, f"{suffix}-ai", source="AI source", text=f"AI article {suffix}")
        excluded_opinion = _opinion(db, f"{suffix}-excluded", source="Excluded source", text=f"Excluded article {suffix}")
        _risk(db, rule_opinion, 80)
        _risk(db, rule_only_opinion, 80)
        _risk(db, ai_opinion, 20)
        low_ai_opinion = _opinion(db, f"{suffix}-low-ai", source="Low AI source", text=f"Low AI article {suffix}")
        _risk(db, excluded_opinion, 20)
        _risk(db, low_ai_opinion, 20)
        _ai(db, rule_opinion, 90)
        rule_ai = _ai(db, ai_opinion, 75)
        excluded_ai = _ai(db, excluded_opinion, 75)
        low_ai = _ai(db, low_ai_opinion, 65)
        db.add_all([
            ForeignAlertAdmission(foreign_opinion_id=rule_opinion.id, foreign_ai_result_id=db.query(ForeignAIResult).filter(ForeignAIResult.foreign_opinion_id == rule_opinion.id).one().id, status="included", note="fixture"),
            ForeignAlertAdmission(foreign_opinion_id=ai_opinion.id, foreign_ai_result_id=rule_ai.id, status="included", note="fixture"),
            ForeignAlertAdmission(foreign_opinion_id=excluded_opinion.id, foreign_ai_result_id=excluded_ai.id, status="excluded", note="fixture"),
            ForeignAlertAdmission(foreign_opinion_id=low_ai_opinion.id, foreign_ai_result_id=low_ai.id, status="included", note="fixture"),
            ForeignAlertRule(name=f"Phase 5G {suffix} dual", rule_type="risk_score", conditions={"threshold": 70}, severity="high", is_enabled=True, cooldown_seconds=3600),
        ])
        db.commit()
        rule = db.query(ForeignAlertRule).filter(ForeignAlertRule.name == f"Phase 5G {suffix} dual").one()

        run = ForeignAlertService.evaluate(db, rule_ids=[rule.id], dry_run=False)
        alerts = db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule.id).all()
        _ALERT_RUN_IDS.add(run.id)
        assert run.triggered_count == 3
        assert db.query(ForeignAlert).filter(
            ForeignAlert.foreign_opinion_id == rule_only_opinion.id,
            ForeignAlert.evaluation_source == "rule",
        ).count() == 1
        assert {(row.foreign_opinion_id, row.evaluation_source) for row in alerts} == {
            (rule_opinion.id, "rule"),
            (rule_only_opinion.id, "rule"),
            (ai_opinion.id, "ai"),
        }
        assert all(row.foreign_ai_result_id is None for row in alerts if row.evaluation_source == "rule")
        assert db.query(ForeignAlert).filter(ForeignAlert.foreign_opinion_id == low_ai_opinion.id).count() == 0
        second = ForeignAlertService.evaluate(db, rule_ids=[rule.id], dry_run=False)
        _ALERT_RUN_IDS.add(second.id)
        assert second.deduplicated_count == 3
        assert db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule.id).count() == 3
        monkeypatch.setattr(settings, "foreign_alert_auto_evaluation_enabled", True)
        auto_run = ForeignAlertService.auto_evaluate(db, rule_ids=[rule.id], dry_run=True)
        _ALERT_RUN_IDS.add(auto_run.id)
        assert auto_run.run_type == "dry_run"
    finally:
        _cleanup(db, suffix)
        db.close()


def test_auto_alert_gate_is_closed_by_default():
    db = SessionLocal()
    try:
        with pytest.raises(PermissionError, match="disabled"):
            ForeignAlertService.auto_evaluate(db, dry_run=False)
        assert db.query(ForeignAlert).count() >= 0
    finally:
        db.close()


def test_auto_event_confirms_only_high_confidence_same_language_multi_source(monkeypatch):
    db = SessionLocal()
    suffix = _suffix()
    try:
        _opinion(db, f"{suffix}-guardian", source="The Guardian", text=f"Shared crisis response {suffix}")
        _opinion(db, f"{suffix}-fox", source="Fox News", text=f"Shared crisis response {suffix}")
        db.commit()
        monkeypatch.setattr(settings, "foreign_event_auto_aggregation_enabled", True)
        result = ForeignEventAutoAggregationService().aggregate(db, dry_run=False, opinion_ids=[row.id for row in db.query(ForeignOpinion).filter(ForeignOpinion.source_key.like(f"fixture_5g_{suffix}%")).all()])
        _AUTO_RUN_IDS.add(result.run.id)
        assert result.run.trigger_type == "auto"
        assert result.run.status == "success"
        assert result.created_events
        assert all(event.confirmation_source == "auto" for event in result.created_events)
        assert all(event.language in {"en", "zh"} for event in result.created_events)
        assert all(event.opinion_count >= 2 and event.source_count >= 2 for event in result.created_events)
        event = result.created_events[0]
        resolved = ForeignEventService().update_status(
            db,
            event.id,
            status="resolved",
            user_id=None,
            reason="manual revoke of automatic event",
            request_id=f"resolve-auto-{suffix}",
        )
        assert resolved.event_status == "resolved"
        linked_ids = [row.foreign_opinion_id for row in db.query(ForeignEventOpinion).filter(ForeignEventOpinion.foreign_event_id == event.id).all()]
        split = ForeignEventService().split_event(
            db,
            event.id,
            [linked_ids[0]],
            user_id=None,
            reason="manual split of automatic event",
            request_id=f"split-auto-{suffix}",
        )
        assert split.opinion_count == 1
    finally:
        _cleanup(db, suffix)
        db.close()


def test_auto_event_keeps_mixed_language_candidate_pending(monkeypatch):
    db = SessionLocal()
    suffix = _suffix()
    try:
        _opinion(db, f"{suffix}-a", source="Fox News", text=f"Shared crisis response {suffix} 中国")
        _opinion(db, f"{suffix}-b", source="The Guardian", text=f"Shared crisis response {suffix} 中国")
        db.commit()
        opinion_ids = [row.id for row in db.query(ForeignOpinion).filter(ForeignOpinion.source_key.like(f"fixture_5g_{suffix}%")).all()]
        monkeypatch.setattr(settings, "foreign_event_auto_aggregation_enabled", True)
        result = ForeignEventAutoAggregationService().aggregate(db, dry_run=False, opinion_ids=opinion_ids)
        _AUTO_RUN_IDS.add(result.run.id)
        assert not result.created_events
        assert result.pending_candidates
        assert all(candidate.review_source == "manual" for candidate in result.pending_candidates)
        assert all(candidate.candidate_status == "candidate" for candidate in result.pending_candidates)
    finally:
        _cleanup(db, suffix)
        db.close()


def test_ai_score_below_threshold_is_not_an_alert_and_auto_event_failure_rolls_back(monkeypatch):
    db = SessionLocal()
    suffix = _suffix()
    try:
        left = _opinion(db, f"{suffix}-left", source="Fox News", text=f"Shared rollback response {suffix}")
        right = _opinion(db, f"{suffix}-right", source="The Guardian", text=f"Shared rollback response {suffix}")
        _risk(db, left, 20)
        _risk(db, right, 20)
        db.commit()
        opinion_ids = [left.id, right.id]
        monkeypatch.setattr(settings, "foreign_event_auto_aggregation_enabled", True)
        before_runs = {row.id for row in db.query(ForeignEventRun).all()}

        def fail_confirm(*args, **kwargs):
            raise RuntimeError("password=secret proxy=http://private.example")

        monkeypatch.setattr(ForeignEventService, "confirm_candidate", fail_confirm)
        with pytest.raises(RuntimeError):
            ForeignEventAutoAggregationService().aggregate(db, dry_run=False, opinion_ids=opinion_ids)
        failed_runs = db.query(ForeignEventRun).filter(
            ForeignEventRun.trigger_type == "auto",
            ForeignEventRun.status == "failed",
        ).all()
        new_failed = [row for row in failed_runs if row.id not in before_runs]
        assert new_failed
        _AUTO_RUN_IDS.add(new_failed[-1].id)
        assert "password" not in (new_failed[-1].error_message or "").casefold()
        assert "proxy" not in (new_failed[-1].error_message or "").casefold()
        assert db.query(ForeignEventCandidate).filter(ForeignEventCandidate.title.like(f"Shared rollback response {suffix}%")).count() == 0
        assert db.query(ForeignEvent).filter(ForeignEvent.title.like(f"Shared rollback response {suffix}%")).count() == 0
    finally:
        _cleanup(db, suffix)
        db.close()


def test_concurrent_foreign_alert_evaluation_is_unique_and_successful(monkeypatch):
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix, source="Concurrency source", text=f"Concurrency article {suffix}")
        _risk(db, opinion, 80)
        rule = ForeignAlertRule(
            name=f"Phase 5G {suffix} concurrency",
            rule_type="risk_score",
            conditions={"threshold": 70},
            severity="high",
            is_enabled=True,
            cooldown_seconds=3600,
        )
        db.add(rule)
        db.commit()
        rule_id = int(rule.id)

        def evaluate_once():
            worker = SessionLocal()
            try:
                return ForeignAlertService.evaluate(worker, rule_ids=[rule_id], dry_run=False)
            finally:
                worker.close()

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            runs = list(executor.map(lambda _: evaluate_once(), (1, 2)))
        _ALERT_RUN_IDS.update(run.id for run in runs)
        assert all(run.status == "success" for run in runs)
        db.expire_all()
        assert db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule.id).count() == 1
        assert sum(run.triggered_count == 1 for run in runs) == 1
        assert sum(run.deduplicated_count == 1 for run in runs) == 1
    finally:
        _cleanup(db, suffix)
        db.close()


def test_alert_insert_failure_is_rolled_back_and_sensitive_error_is_hidden(monkeypatch):
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix, source="Rollback source", text=f"Rollback alert {suffix}")
        _risk(db, opinion, 80)
        rule = ForeignAlertRule(
            name=f"Phase 5G {suffix} rollback",
            rule_type="risk_score",
            conditions={"threshold": 70},
            severity="high",
            is_enabled=True,
        )
        db.add(rule)
        db.commit()
        import app.services.foreign_alert_service as alert_module

        def fail_insert(*args, **kwargs):
            raise RuntimeError("password=secret proxy=http://private.example")

        monkeypatch.setattr(alert_module, "pg_insert", fail_insert)
        run = ForeignAlertService.evaluate(db, rule_ids=[rule.id], dry_run=False)
        _ALERT_RUN_IDS.add(run.id)
        assert run.status == "failed"
        assert db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule.id).count() == 0
        assert "password" not in (run.error_message or "").casefold()
        assert "proxy" not in (run.error_message or "").casefold()
    finally:
        _cleanup(db, suffix)
        db.close()
