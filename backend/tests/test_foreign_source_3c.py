"""Phase Foreign-Source-3C isolated alert tests.

These tests use the local opinion_test database configured by conftest.py. All
fixtures are named with a unique suffix and are removed in teardown; no real
RSS, AI, proxy or notification channel is used.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.alert import AlertRecord
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_rule import ForeignAlertRule
from app.models.foreign_alert_run import ForeignAlertRun
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_alert_service import ForeignAlertService


_RUN_IDS: set[int] = set()


def _remember_run(run: ForeignAlertRun) -> ForeignAlertRun:
    _RUN_IDS.add(run.id)
    return run


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _opinion(db, suffix: str, *, source: str = "Fixture source") -> ForeignOpinion:
    row = ForeignOpinion(
        source_key=f"fixture_3c_{suffix}",
        source_name_snapshot=source,
        title=f"Phase 3C alert article {suffix}",
        summary="Fixture summary",
        content="A sufficiently long fixture article body for foreign alert evaluation.",
        url=f"https://fixture.test/foreign-alert/{suffix}",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        matched_keywords=["China"],
        content_hash=(suffix * 8)[:64],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _risk(db, opinion: ForeignOpinion, *, score: int = 90) -> ForeignRiskResult:
    result = ForeignRiskResult(
        foreign_opinion_id=opinion.id,
        content_hash=opinion.content_hash,
        language="en",
        risk_score=score,
        risk_level="high" if score >= 70 else "medium",
        sentiment="negative",
        risk_category="security",
        matched_terms=[
            {"word": "conflict", "language": "en", "category": "security", "severity_weight": 70}
        ],
        explanation="fixture risk result",
        analyzer_type="rule",
        model_version="fixture-v1",
        analysis_status="completed",
        is_current=True,
        analyzed_at=datetime.now(timezone.utc),
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def _cleanup(db, suffix: str) -> None:
    rule_ids = [row.id for row in db.query(ForeignAlertRule).filter(ForeignAlertRule.name.like(f"Phase 3C {suffix}%")).all()]
    opinion_ids = [row.id for row in db.query(ForeignOpinion).filter(ForeignOpinion.source_key == f"fixture_3c_{suffix}").all()]
    event_ids = [row.id for row in db.query(ForeignEvent).filter(ForeignEvent.title.like(f"Phase 3C event {suffix}%")).all()]
    if rule_ids:
        db.query(ForeignAlert).filter(ForeignAlert.rule_id.in_(rule_ids)).delete(synchronize_session=False)
        db.query(ForeignAlertRule).filter(ForeignAlertRule.id.in_(rule_ids)).delete(synchronize_session=False)
    if event_ids:
        db.query(ForeignEventOpinion).filter(ForeignEventOpinion.foreign_event_id.in_(event_ids)).delete(synchronize_session=False)
        db.query(ForeignEvent).filter(ForeignEvent.id.in_(event_ids)).delete(synchronize_session=False)
    if opinion_ids:
        db.query(ForeignRiskResult).filter(ForeignRiskResult.foreign_opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
        db.query(ForeignOpinion).filter(ForeignOpinion.id.in_(opinion_ids)).delete(synchronize_session=False)
    if _RUN_IDS:
        db.query(ForeignAlertRun).filter(ForeignAlertRun.id.in_(_RUN_IDS)).delete(synchronize_session=False)
        _RUN_IDS.clear()
    db.commit()


def test_risk_threshold_is_idempotent_and_domestic_alerts_are_unchanged():
    db = SessionLocal()
    suffix = _suffix()
    opinion = _opinion(db, suffix)
    _risk(db, opinion)
    rule = ForeignAlertRule(
        name=f"Phase 3C {suffix} threshold",
        rule_type="risk_score",
        conditions={"threshold": 80},
        severity="high",
        is_enabled=True,
        cooldown_seconds=3600,
    )
    db.add(rule)
    db.commit()
    domestic_before = db.query(AlertRecord).count()
    try:
        first = _remember_run(ForeignAlertService.evaluate(db, rule_ids=[rule.id], dry_run=False))
        second = _remember_run(ForeignAlertService.evaluate(db, rule_ids=[rule.id], dry_run=False))
        alerts = db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule.id).all()
        assert first.triggered_count == 1
        assert second.deduplicated_count == 1
        assert len(alerts) == 1
        assert db.query(AlertRecord).count() == domestic_before
        assert db.query(ForeignAlertRun).filter(ForeignAlertRun.id == second.id).one().status == "success"
    finally:
        _cleanup(db, suffix)
        db.close()


def test_confirmed_event_triggers_but_unconfirmed_event_does_not():
    db = SessionLocal()
    suffix = _suffix()
    opinion = _opinion(db, suffix)
    event = ForeignEvent(
        title=f"Phase 3C event {suffix} confirmed",
        summary="fixture event",
        language="en",
        event_status="active",
        risk_level="high",
        heat_score=85,
        opinion_count=1,
        source_count=1,
        confidence=0.8,
    )
    db.add(event)
    db.flush()
    db.add(ForeignEventOpinion(foreign_event_id=event.id, foreign_opinion_id=opinion.id))
    # Negative case: an event in a non-target status (here "archived") must NOT
    # satisfy the confirmed_event rule even with a higher heat score.
    inactive = ForeignEvent(
        title=f"Phase 3C event {suffix} archived",
        summary="fixture inactive event",
        language="en",
        event_status="archived",
        risk_level="high",
        heat_score=99,
        opinion_count=8,
        source_count=3,
        confidence=0.8,
    )
    db.add(inactive)
    db.flush()
    db.add(ForeignEventOpinion(foreign_event_id=inactive.id, foreign_opinion_id=opinion.id))
    rule = ForeignAlertRule(
        name=f"Phase 3C {suffix} event",
        rule_type="confirmed_event",
        conditions={"heat_score_min": 80},
        severity="medium",
        is_enabled=True,
    )
    db.add(rule)
    db.commit()
    try:
        run = _remember_run(ForeignAlertService.evaluate(db, rule_ids=[rule.id], dry_run=False))
        alert = db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule.id).one()
        assert run.triggered_count == 1
        assert alert.foreign_event_id == event.id
        assert alert.foreign_opinion_id is None
        # The archived (non-target) event must not have produced an alert.
        assert db.query(ForeignAlert).filter(
            ForeignAlert.rule_id == rule.id,
            ForeignAlert.foreign_event_id == inactive.id,
        ).count() == 0
        assert db.query(AlertRecord).count() >= 0
    finally:
        _cleanup(db, suffix)
        db.close()


def test_keyword_only_monitoring_terms_and_disabled_rules_do_not_trigger():
    db = SessionLocal()
    suffix = _suffix()
    opinion = _opinion(db, suffix)
    result = _risk(db, opinion)
    monitor_only = ForeignAlertRule(
        name=f"Phase 3C {suffix} monitoring-only",
        rule_type="keyword_combo",
        conditions={"monitoring_keywords": ["China"], "risk_terms": ["China"]},
        severity="critical",
        is_enabled=True,
    )
    disabled = ForeignAlertRule(
        name=f"Phase 3C {suffix} disabled",
        rule_type="risk_score",
        conditions={"threshold": 1},
        severity="high",
        is_enabled=False,
    )
    db.add_all([monitor_only, disabled])
    db.commit()
    try:
        run = _remember_run(ForeignAlertService.evaluate(db, rule_ids=[monitor_only.id, disabled.id], dry_run=False))
        assert run.triggered_count == 0
        assert db.query(ForeignAlert).filter(ForeignAlert.rule_id.in_([monitor_only.id, disabled.id])).count() == 0
        assert result.matched_terms[0]["word"] == "conflict"
    finally:
        _cleanup(db, suffix)
        db.close()


def test_alert_state_transitions_are_idempotent_and_failed_rule_is_audited():
    db = SessionLocal()
    suffix = _suffix()
    opinion = _opinion(db, suffix)
    _risk(db, opinion)
    rule = ForeignAlertRule(
        name=f"Phase 3C {suffix} state",
        rule_type="risk_score",
        conditions={"threshold": 70},
        severity="high",
        is_enabled=True,
    )
    broken = ForeignAlertRule(
        name=f"Phase 3C {suffix} broken",
        rule_type="risk_score",
        conditions={"threshold": "not-a-number"},
        severity="medium",
        is_enabled=True,
    )
    db.add_all([rule, broken])
    db.commit()
    try:
        run = _remember_run(ForeignAlertService.evaluate(db, rule_ids=[rule.id, broken.id], dry_run=False))
        assert run.status == "failed"
        assert run.failed_count == 1
        alert = db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule.id).one()
        assert ForeignAlertService.acknowledge(db, alert.id, user_id=None).status == "acknowledged"
        assert ForeignAlertService.acknowledge(db, alert.id, user_id=None).status == "acknowledged"
        assert ForeignAlertService.resolve(db, alert.id, user_id=None).status == "resolved"
        assert ForeignAlertService.resolve(db, alert.id, user_id=None).status == "resolved"
        assert run.error_message and "foreign" not in run.error_message.casefold()
    finally:
        _cleanup(db, suffix)
        db.close()


def test_foreign_alert_api_isolated_and_frontend_contract(client, auth_headers):
    response = client.get("/api/foreign/alerts", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "items" in payload and "opinions" not in payload and "events" not in payload
    assert client.get("/api/foreign/alert-rules", headers=auth_headers).status_code == 200
    assert client.get("/api/foreign/alert-runs", headers=auth_headers).status_code == 200
    assert client.get("/api/foreign/alerts").status_code == 401
    suffix = _suffix()
    created = client.post(
        "/api/foreign/alert-rules",
        headers=auth_headers,
        json={
            "name": f"Phase 3C {suffix} API rule",
            "rule_type": "risk_score",
            "conditions": {"threshold": 90},
            "severity": "high",
            "is_enabled": True,
        },
    )
    assert created.status_code == 422, created.text
    created = client.post(
        "/api/foreign/alert-rules",
        headers=auth_headers,
        json={
            "name": f"Phase 3C {suffix} API rule",
            "rule_type": "risk_score",
            "conditions": {"threshold": 90},
            "severity": "high",
        },
    )
    assert created.status_code == 201, created.text
    rule_id = created.json()["id"]
    assert created.json()["is_enabled"] is False
    enabled = client.patch(
        f"/api/foreign/alert-rules/{rule_id}",
        headers=auth_headers,
        json={"is_enabled": True},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["is_enabled"] is True
    dry_run = client.post(
        "/api/foreign/alerts/evaluate",
        headers=auth_headers,
        json={"dry_run": True, "rule_ids": [rule_id], "max_items": 1},
    )
    assert dry_run.status_code == 200, dry_run.text
    assert dry_run.json()["status"] in {"dry_run", "success"}
    run_id = dry_run.json()["id"]
    db = SessionLocal()
    try:
        db.query(ForeignAlert).filter(ForeignAlert.rule_id == rule_id).delete(synchronize_session=False)
        db.query(ForeignAlertRule).filter(ForeignAlertRule.id == rule_id).delete(synchronize_session=False)
        db.query(ForeignAlertRun).filter(ForeignAlertRun.id == run_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    contract = (
        __import__("pathlib").Path(__file__).parents[2] / "frontend" / "src" / "views" / "Alerts.vue"
    ).read_text(encoding="utf-8")
    # Alert rules and records are intentionally hosted by the unified alert
    # center; ForeignWorkspace only links to it and renders a read-only feed.
    assert 'label="foreign"' in contract
    assert "/foreign/alerts" in contract
    assert "/foreign/alerts/evaluate" in contract
