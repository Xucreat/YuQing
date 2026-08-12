"""Unified "current effective risk" for foreign opinions.

These tests pin the six business rules that the two evaluation engines must
obey together:

* collection only ever produces a rule evaluation,
* the AI evaluation is manual, single-shot and idempotent,
* rule and AI results never overwrite each other,
* AI results remain history and never drive the current risk,
* the opinion list and the alert center read the very same resolver,
* the legacy orphaned alert shape (opinion #8) no longer shows 75 vs 20.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_admission import ForeignAlertAdmission
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services import foreign_ai_service as ai_module
from app.services.foreign_ai_service import ForeignAIService
from app.services.foreign_effective_risk import (
    effective_risk_level_expression,
    resolve_one,
)
from app.services.foreign_risk_service import ForeignRiskService


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _opinion(db, suffix: str, *, text_body: str = "Foreign effective risk fixture") -> ForeignOpinion:
    row = ForeignOpinion(
        source_key=f"fixture_eff_{suffix}",
        source_name_snapshot="Effective risk source",
        title=f"{text_body} {suffix}",
        summary=text_body,
        content=f"{text_body}. A sufficiently long foreign fixture article body about China.",
        url=f"https://fixture.test/foreign-eff/{suffix}",
        published_at=_utcnow(),
        collected_at=_utcnow(),
        matched_keywords=["China"],
        content_hash=(suffix * 8)[:64],
    )
    db.add(row)
    db.flush()
    return row


def _rule_result(db, opinion: ForeignOpinion, score: int, *, level: str | None = None) -> ForeignRiskResult:
    row = ForeignRiskResult(
        foreign_opinion_id=opinion.id,
        content_hash=opinion.content_hash,
        language="en",
        risk_score=score,
        risk_level=level or ("high" if score >= 70 else "medium" if score >= 40 else "low"),
        sentiment="neutral",
        risk_category="unknown",
        matched_terms=[],
        explanation="fixture rule evaluation",
        analyzer_type="rule",
        model_name="rule-engine",
        model_version="fixture-rule-v1",
        analysis_status="completed",
        is_current=True,
        analyzed_at=_utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def _ai_result(
    db, opinion: ForeignOpinion, score: int, *, content_hash: str | None = None
) -> ForeignAIResult:
    row = ForeignAIResult(
        foreign_opinion_id=opinion.id,
        content_hash=content_hash or opinion.content_hash,
        model_name="deepseek",
        model_version="foreign-ai-v1",
        status="completed",
        summary="fixture ai evaluation",
        sentiment="negative",
        risk_score=score,
        keywords=["china"],
        suggestion="fixture",
        analyzed_at=_utcnow(),
        is_current=True,
    )
    db.add(row)
    db.flush()
    return row


def _alert(
    db,
    opinion: ForeignOpinion,
    *,
    ai_result: ForeignAIResult | None = None,
    rule_result: ForeignRiskResult | None = None,
    status: str = "triggered",
    score: int | None = None,
    level: str = "high",
    expires_at: datetime | None = None,
    source: str = "ai",
) -> ForeignAlert:
    row = ForeignAlert(
        rule_id=None,
        foreign_opinion_id=opinion.id,
        foreign_risk_result_id=rule_result.id if rule_result else None,
        foreign_ai_result_id=ai_result.id if ai_result else None,
        evaluation_source=source,
        severity="high",
        status=status,
        title="fixture alert",
        message="fixture alert",
        matched_conditions={},
        rule_snapshot={},
        source_name_snapshot=opinion.source_name_snapshot,
        opinion_title_snapshot=opinion.title,
        event_title_snapshot="",
        risk_score=score if score is not None else (ai_result.risk_score if ai_result else None),
        risk_level=level,
        deduplication_key=f"fixture:{opinion.id}:{uuid.uuid4().hex}",
        triggered_at=_utcnow(),
        expires_at=expires_at,
        resolved_at=_utcnow() if status == "resolved" else None,
        suppressed_at=_utcnow() if status == "suppressed" else None,
    )
    db.add(row)
    db.flush()
    return row


def _cleanup(db, suffix: str) -> None:
    opinion_ids = [
        row.id
        for row in db.query(ForeignOpinion)
        .filter(ForeignOpinion.source_key.like(f"fixture_eff_{suffix}%"))
        .all()
    ]
    if opinion_ids:
        db.query(ForeignAlert).filter(ForeignAlert.foreign_opinion_id.in_(opinion_ids)).delete(
            synchronize_session=False
        )
        db.query(ForeignAlertAdmission).filter(
            ForeignAlertAdmission.foreign_opinion_id.in_(opinion_ids)
        ).delete(synchronize_session=False)
        db.query(ForeignAIResult).filter(
            ForeignAIResult.foreign_opinion_id.in_(opinion_ids)
        ).delete(synchronize_session=False)
        db.query(ForeignRiskResult).filter(
            ForeignRiskResult.foreign_opinion_id.in_(opinion_ids)
        ).delete(synchronize_session=False)
        db.query(ForeignOpinion).filter(ForeignOpinion.id.in_(opinion_ids)).delete(
            synchronize_session=False
        )
    db.commit()


class _StubAI:
    """Minimal stand-in for the DeepSeek analysis payload."""

    summary = "stub summary"
    sentiment = "negative"
    risk_score = 75
    keywords = ["china"]
    suggestion = "stub suggestion"


class _StubProvider:
    calls = 0
    is_configured = True

    def __init__(self) -> None:
        pass

    def analyze(self, _text: str) -> _StubAI:
        type(self).calls += 1
        return _StubAI()


# --- 1. collection never calls AI -----------------------------------------


def test_collection_and_rule_engine_never_call_ai(monkeypatch):
    """Rule 1: the collection pipeline must not reach the AI provider."""
    for name in ("foreign_collection_service.py", "foreign_risk_service.py"):
        source = (BACKEND_DIR / "app" / "services" / name).read_text(encoding="utf-8")
        assert "ForeignAIService" not in source, f"{name} must not import the AI service"
        assert "DeepSeekProvider" not in source, f"{name} must not call the AI provider"

    def _explode(*_args, **_kwargs):  # pragma: no cover - must never run
        raise AssertionError("Collection path called the AI provider")

    monkeypatch.setattr(ai_module, "DeepSeekProvider", _explode)

    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        db.commit()
        ForeignRiskService().analyze_opinion(db, opinion.id)
        db.commit()
        assert (
            db.query(ForeignAIResult)
            .filter(ForeignAIResult.foreign_opinion_id == opinion.id)
            .count()
            == 0
        )
        view = resolve_one(db, opinion.id)
        assert view["latest_ai_risk"] is None
        assert view["effective_risk"]["source"] == "rule"
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 2 & 7. manual AI runs once and is idempotent --------------------------


def test_manual_ai_runs_once_and_repeat_click_is_idempotent(monkeypatch):
    """Rule 2: one manual trigger equals exactly one provider call."""
    monkeypatch.setenv("FOREIGN_AI_REVIEW_ENABLED", "true")
    monkeypatch.setattr(ai_module, "DeepSeekProvider", _StubProvider)
    _StubProvider.calls = 0

    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        _rule_result(db, opinion, 20)
        db.commit()

        service = ForeignAIService()
        first, reused_first = service.analyze_opinion_manual(db, opinion.id)
        assert reused_first is False
        assert first.status == "completed"
        assert first.risk_score == 75
        assert _StubProvider.calls == 1

        second, reused_second = service.analyze_opinion_manual(db, opinion.id)
        assert reused_second is True
        assert second.id == first.id
        assert _StubProvider.calls == 1, "a repeated click must not call the model again"

        assert (
            db.query(ForeignAIResult)
            .filter(ForeignAIResult.foreign_opinion_id == opinion.id)
            .count()
            == 1
        )
        # Rule 3: the rule result is untouched by the AI run.
        rule_row = db.scalar(
            select(ForeignRiskResult).where(
                ForeignRiskResult.foreign_opinion_id == opinion.id
            )
        )
        assert rule_row.risk_score == 20
        assert rule_row.risk_level == "low"
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 3 & 4. an active AI alert does not drive the effective risk -----------


def test_active_ai_alert_is_hidden_and_does_not_drive_effective_risk_on_both_pages(client, auth_headers):
    """A legacy AI alert is hidden while the rule result stays canonical."""
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        rule_row = _rule_result(db, opinion, 20)
        ai_row = _ai_result(db, opinion, 75)
        alert = _alert(db, opinion, ai_result=ai_row, rule_result=rule_row, status="triggered")
        db.commit()
        opinion_id, alert_id = opinion.id, alert.id

        view = resolve_one(db, opinion_id)
        assert view["effective_risk"]["source"] == "rule"
        assert view["effective_risk"]["risk_score"] == 20
        assert view["effective_risk"]["risk_level"] == "low"
        assert view["effective_risk"]["reason"] == "rule_baseline"
        assert view["latest_ai_risk"]["in_effect"] is False
        # Rule 3: the rule evaluation is preserved side by side.
        assert view["rule_risk"]["risk_score"] == 20
        assert view["rule_risk"]["risk_level"] == "low"

        detail = client.get(f"/api/foreign/opinions/{opinion_id}/detail", headers=auth_headers)
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()

        alerts = client.get(
            "/api/foreign/alerts", params={"foreign_opinion_id": opinion_id}, headers=auth_headers
        )
        assert alerts.status_code == 200, alerts.text
        assert alerts.json()["items"] == []
        assert detail_body["alert"] is None
        assert view["alert"] is None, "AI alerts are not part of the normal alert view"

        # Legacy AI rows are also inaccessible through ID-based alert routes.
        assert client.get(f"/api/foreign/alerts/{alert_id}", headers=auth_headers).status_code == 404
        assert client.get(f"/api/foreign/alerts/{alert_id}/actions", headers=auth_headers).status_code == 404
        transition = client.post(
            f"/api/foreign/alerts/{alert_id}/acknowledge",
            json={"note": "legacy row"},
            headers=auth_headers,
        )
        assert transition.status_code == 404
        admission = client.post(
            f"/api/foreign/opinions/{opinion_id}/ai-alert-admission",
            json={"included": True, "note": "legacy row"},
            headers=auth_headers,
        )
        assert admission.status_code == 410
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 4, 5. resolving an alert does not change the rule result --------------


@pytest.mark.parametrize("closed_status", ["resolved", "suppressed"])
def test_closed_alert_falls_back_to_rule_and_keeps_ai_history(closed_status):
    """Closing an alert keeps the rule risk and preserves AI history."""
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        rule_row = _rule_result(db, opinion, 20)
        ai_row = _ai_result(db, opinion, 75)
        _alert(db, opinion, ai_result=ai_row, rule_result=rule_row, status=closed_status)
        db.commit()

        view = resolve_one(db, opinion.id)
        assert view["effective_risk"]["source"] == "rule"
        assert view["effective_risk"]["risk_score"] == 20
        assert view["effective_risk"]["risk_level"] == "low"
        assert view["effective_risk"]["reason"] == "rule_baseline"
        # History stays readable and is explicitly marked as not in effect.
        assert view["latest_ai_risk"]["risk_score"] == 75
        assert view["latest_ai_risk"]["risk_level"] == "high"
        assert view["latest_ai_risk"]["in_effect"] is False
        assert view["latest_ai_risk"]["alert_status"] is None
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 6. expiry changes alert state only ------------------------------------


def test_expired_alert_behaves_like_a_resolved_alert():
    """An expired alert never changes the effective rule risk."""
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        rule_row = _rule_result(db, opinion, 20)
        ai_row = _ai_result(db, opinion, 75)
        _alert(
            db,
            opinion,
            ai_result=ai_row,
            rule_result=rule_row,
            status="triggered",
            expires_at=_utcnow() - timedelta(hours=1),
        )
        db.commit()

        view = resolve_one(db, opinion.id)
        assert view["effective_risk"]["source"] == "rule"
        assert view["effective_risk"]["risk_score"] == 20
        assert view["latest_ai_risk"]["risk_score"] == 75
        assert view["latest_ai_risk"]["in_effect"] is False
        assert view["alert"] is None

        # A future deadline keeps the alert active, but not effective.
        db.query(ForeignAlert).filter(ForeignAlert.foreign_opinion_id == opinion.id).update(
            {"expires_at": _utcnow() + timedelta(hours=1)}, synchronize_session=False
        )
        db.commit()
        db.expire_all()
        active_view = resolve_one(db, opinion.id)
        assert active_view["effective_risk"]["source"] == "rule"
        assert active_view["effective_risk"]["risk_score"] == 20
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 7. AI history without a rule never becomes current risk --------------


def test_ai_only_opinion_has_unknown_effective_risk():
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        ai_row = _ai_result(db, opinion, 90)
        _alert(db, opinion, ai_result=ai_row, rule_result=None, status="triggered")
        db.commit()

        view = resolve_one(db, opinion.id)
        assert view["effective_risk"]["source"] == "rule"
        assert view["effective_risk"]["risk_score"] is None
        assert view["effective_risk"]["risk_level"] == "unknown"
        assert view["latest_ai_risk"]["risk_score"] == 90
        assert view["latest_ai_risk"]["in_effect"] is False
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 8. no AI evaluation means the rule result is the only truth -----------


def test_opinion_without_ai_shows_only_the_rule_result(client, auth_headers):
    """Rule 1: before any manual review the rule result is the current risk."""
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        _rule_result(db, opinion, 55)
        db.commit()
        opinion_id = opinion.id

        view = resolve_one(db, opinion_id)
        assert view["effective_risk"] == {
            **view["effective_risk"],
            "source": "rule",
            "risk_score": 55,
            "risk_level": "medium",
            "reason": "rule_baseline",
        }
        assert view["latest_ai_risk"] is None
        assert view["alert"] is None

        detail = client.get(f"/api/foreign/opinions/{opinion_id}/detail", headers=auth_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["effective_risk"]["risk_score"] == 55
        assert detail.json()["latest_ai_risk"] is None
    finally:
        _cleanup(db, suffix)
        db.close()


def test_display_risk_source_switches_without_changing_effective_risk():
    """AI view is opt-in, completed-only, and never replaces the rule result."""
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        _rule_result(db, opinion, 20)
        db.commit()

        rule_view = resolve_one(db, opinion.id, risk_source="rule")
        ai_fallback = resolve_one(db, opinion.id, risk_source="ai")
        assert rule_view["effective_risk"]["risk_score"] == 20
        assert rule_view["display_risk"]["source"] == "rule"
        assert ai_fallback["display_risk"] == {
            **ai_fallback["display_risk"],
            "source": "rule",
            "fallback": True,
            "fallback_reason": "ai_result_unavailable",
        }

        _ai_result(db, opinion, 75)
        db.commit()
        ai_view = resolve_one(db, opinion.id, risk_source="ai")
        assert ai_view["effective_risk"]["risk_score"] == 20
        assert ai_view["display_risk"]["source"] == "ai"
        assert ai_view["display_risk"]["risk_score"] == 75
        assert ai_view["display_risk"]["fallback"] is False
    finally:
        _cleanup(db, suffix)
        db.close()


def test_incomplete_ai_result_falls_back_for_display_and_list_filter(client, auth_headers):
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        _rule_result(db, opinion, 20)
        ai_row = _ai_result(db, opinion, 75)
        ai_row.status = "processing"
        db.commit()
        view = resolve_one(db, opinion.id, risk_source="ai")
        assert view["latest_ai_risk"] is None
        assert view["display_risk"]["source"] == "rule"
        assert view["display_risk"]["fallback"] is True

        response = client.get(
            "/api/foreign/opinions",
            params={"risk_source": "ai", "risk_level": "low", "q": suffix},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert any(item["id"] == opinion.id for item in items)
        row = next(item for item in items if item["id"] == opinion.id)
        assert row["display_risk"]["source"] == "rule"
        assert row["display_risk"]["fallback"] is True
    finally:
        _cleanup(db, suffix)
        db.close()


def test_detail_returns_latest_completed_ai_result_even_when_not_current(client, auth_headers):
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        _rule_result(db, opinion, 20)
        first = _ai_result(db, opinion, 45)
        second = _ai_result(db, opinion, 85, content_hash=(suffix + "retry")[:64])
        first.is_current = True
        second.is_current = False
        db.commit()

        response = client.get(
            f"/api/foreign/opinions/{opinion.id}/detail",
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["latest_ai_risk"]["ai_result_id"] == second.id
        assert payload["ai_result"]["id"] == second.id
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 5. the list filter uses the same definition as the column -------------


def test_effective_risk_filter_matches_the_rendered_level():
    """Filtering by risk_level uses the current rule level."""
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        rule_row = _rule_result(db, opinion, 20)
        ai_row = _ai_result(db, opinion, 75)
        alert = _alert(db, opinion, ai_result=ai_row, rule_result=rule_row, status="triggered")
        db.commit()

        expression = effective_risk_level_expression()
        high_ids = set(
            db.scalars(select(ForeignOpinion.id).where(expression == "high")).all()
        )
        assert opinion.id not in high_ids

        alert.status = "resolved"
        alert.resolved_at = _utcnow()
        db.commit()
        low_ids = set(
            db.scalars(
                select(ForeignOpinion.id).where(effective_risk_level_expression() == "low")
            ).all()
        )
        assert opinion.id in low_ids
    finally:
        _cleanup(db, suffix)
        db.close()


# --- 9. the legacy orphaned alert shape (opinion #8) -----------------------


def test_legacy_orphan_alert_is_consistent_and_repair_is_idempotent(client, auth_headers):
    """Rule 6: the 75 vs 20 mismatch cannot reappear and the repair is safe."""
    db = SessionLocal()
    suffix = _suffix()
    try:
        opinion = _opinion(db, suffix)
        rule_row = _rule_result(db, opinion, 20)
        ai_row = _ai_result(db, opinion, 75)
        # Exactly the shape found in production for opinion #8.
        legacy = _alert(
            db,
            opinion,
            ai_result=ai_row,
            rule_result=None,
            status="resolved",
            score=75,
            level="unknown",
        )
        db.commit()
        legacy_id = legacy.id

        # Even before any repair, both pages already agree on 20/low because
        # the alert is closed. The AI score stays visible as history.
        view = resolve_one(db, opinion.id)
        assert view["effective_risk"]["risk_score"] == 20
        assert view["latest_ai_risk"]["risk_score"] == 75
        assert view["latest_ai_risk"]["in_effect"] is False

        repair_link = text(
            """
            UPDATE foreign_alerts AS a
            SET foreign_risk_result_id = r.id
            FROM foreign_risk_results AS r
            WHERE a.foreign_risk_result_id IS NULL
              AND a.foreign_opinion_id IS NOT NULL
              AND r.foreign_opinion_id = a.foreign_opinion_id
              AND r.is_current IS TRUE
            """
        )
        repair_level = text(
            """
            UPDATE foreign_alerts
            SET risk_level = CASE
                WHEN risk_score >= 70 THEN 'high'
                WHEN risk_score >= 40 THEN 'medium'
                ELSE 'low'
            END
            WHERE risk_level = 'unknown' AND risk_score IS NOT NULL
            """
        )
        for _ in range(2):  # repeatable / idempotent
            db.execute(repair_link)
            db.execute(repair_level)
            db.commit()

        db.expire_all()
        repaired = db.get(ForeignAlert, legacy_id)
        assert repaired.foreign_risk_result_id == rule_row.id, "orphan link must be repaired"
        assert repaired.risk_level == "high", "the alert keeps its own AI level"

        # Rule 6: the rule result itself is never rewritten to 75/high.
        db.refresh(rule_row)
        assert rule_row.risk_score == 20
        assert rule_row.risk_level == "low"

        alerts = client.get(
            "/api/foreign/alerts",
            params={"foreign_opinion_id": opinion.id},
            headers=auth_headers,
        )
        assert alerts.status_code == 200, alerts.text
        assert alerts.json()["items"] == []
        detail = client.get(
            f"/api/foreign/opinions/{opinion.id}/detail", headers=auth_headers
        ).json()
        assert detail["alert"] is None
    finally:
        _cleanup(db, suffix)
        db.close()
