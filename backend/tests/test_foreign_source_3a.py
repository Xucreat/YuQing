"""Phase Foreign-Source-3A: isolated foreign risk/sentiment tests."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from app.db.session import SessionLocal
from app.models.foreign_analysis_run import ForeignAnalysisRun
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.models.foreign_risk_term import ForeignRiskTerm
from app.services.foreign_risk_service import ForeignRiskService


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _opinion(db, *, title: str, summary: str = "", content: str = "") -> ForeignOpinion:
    suffix = _suffix()
    row = ForeignOpinion(
        source_key=f"fixture_{suffix}",
        source_name_snapshot=f"Foreign Risk Fixture {suffix}",
        title=title,
        summary=summary,
        content=content,
        url=f"https://fixture.test/foreign-risk/{suffix}",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        matched_keywords=["China"],
        content_hash="",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _cleanup(db, opinion_id: int) -> None:
    db.query(ForeignRiskResult).filter(
        ForeignRiskResult.foreign_opinion_id == opinion_id
    ).delete(synchronize_session=False)
    db.query(ForeignAnalysisRun).filter(
        ForeignAnalysisRun.foreign_opinion_id == opinion_id
    ).delete(synchronize_session=False)
    db.query(ForeignOpinion).filter(ForeignOpinion.id == opinion_id).delete(
        synchronize_session=False
    )
    db.commit()


def test_rule_analysis_uses_only_foreign_tables_and_conservative_empty_terms():
    db = SessionLocal()
    row = _opinion(
        db,
        title="China policy update",
        summary="Chinese officials discussed a routine meeting.",
    )
    domestic_before = db.execute(
        __import__("sqlalchemy").text("select count(*) from opinions")
    ).scalar()
    try:
        result = ForeignRiskService().analyze_opinion(db, row.id)
        assert result.analysis_status == "completed"
        assert result.risk_score == 20
        assert result.risk_level == "low"
        assert result.sentiment == "neutral"
        assert result.matched_terms == []
        assert db.execute(
            __import__("sqlalchemy").text("select count(*) from opinions")
        ).scalar() == domestic_before
        assert db.query(ForeignAnalysisRun).filter(
            ForeignAnalysisRun.foreign_opinion_id == row.id
        ).count() == 1
    finally:
        _cleanup(db, row.id)
        db.close()


def test_language_specific_terms_mixed_text_and_versioned_idempotency():
    db = SessionLocal()
    suffix = _suffix()
    row = _opinion(
        db,
        title="China conflict update",
        summary="关于中国冲突的 mixed-language report。",
        content="The report describes violence and diplomatic progress.",
    )
    terms = [
        ForeignRiskTerm(
            word="冲突",
            language="zh",
            category="conflict",
            severity_weight=50,
            sentiment="negative",
            term_set_version=f"test-{suffix}",
        ),
        ForeignRiskTerm(
            word="violence",
            language="en",
            category="violence",
            severity_weight=40,
            sentiment="negative",
            term_set_version=f"test-{suffix}",
        ),
        ForeignRiskTerm(
            word="progress",
            language="en",
            category="policy",
            severity_weight=0,
            sentiment="positive",
            term_set_version=f"test-{suffix}",
        ),
    ]
    db.add_all(terms)
    db.commit()
    try:
        service = ForeignRiskService()
        first = service.analyze_opinion(db, row.id, model_version="test-v1")
        again = service.analyze_opinion(db, row.id, model_version="test-v1")
        upgraded = service.analyze_opinion(db, row.id, model_version="test-v2")
        assert first.id == again.id
        assert upgraded.id != first.id
        assert first.language == "mixed"
        assert first.risk_score == 110 or first.risk_score == 100
        assert first.risk_level == "high"
        assert {item["word"] for item in first.matched_terms} == {"冲突", "violence", "progress"}
        assert first.sentiment == "negative"
        assert db.query(ForeignRiskResult).filter(
            ForeignRiskResult.foreign_opinion_id == row.id
        ).count() == 2
    finally:
        db.query(ForeignRiskTerm).filter(
            ForeignRiskTerm.term_set_version == f"test-{suffix}"
        ).delete(synchronize_session=False)
        _cleanup(db, row.id)
        db.close()


def test_empty_or_short_content_is_skipped_without_exception():
    db = SessionLocal()
    row = _opinion(db, title="China", summary="", content="")
    try:
        result = ForeignRiskService().analyze_opinion(db, row.id)
        assert result.analysis_status == "skipped"
        assert result.sentiment == "unknown"
        assert result.risk_score is None
        assert result.risk_level == "unknown"
    finally:
        _cleanup(db, row.id)
        db.close()


def test_analysis_failure_is_recorded_and_article_remains(monkeypatch):
    db = SessionLocal()
    row = _opinion(db, title="China failure fixture", content="A sufficiently long fixture body.")

    def fail(*_args, **_kwargs):
        raise RuntimeError("fixture failure")

    monkeypatch.setattr("app.services.foreign_risk_service._build_decision", fail)
    try:
        result = ForeignRiskService().analyze_opinion(db, row.id)
        assert result.analysis_status == "failed"
        assert "fixture failure" in (result.error_message or "")
        assert db.get(ForeignOpinion, row.id) is not None
    finally:
        _cleanup(db, row.id)
        db.close()


def test_foreign_risk_api_is_bidirectionally_isolated_and_ai_disabled(
    client, auth_headers
):
    db = SessionLocal()
    row = _opinion(db, title="China API fixture", content="Routine foreign policy coverage.")
    opinion_id = row.id
    opinion_url = row.url
    db.close()
    try:
        analyzed = client.post(
            f"/api/foreign/risk/{opinion_id}/analyze",
            headers=auth_headers,
            json={},
        )
        assert analyzed.status_code == 200, analyzed.text
        payload = analyzed.json()
        assert payload["foreign_opinion_id"] == opinion_id
        assert payload["opinion"]["id"] == opinion_id

        foreign_list = client.get(
            "/api/foreign/risk",
            headers=auth_headers,
            params={"q": "API fixture"},
        )
        assert foreign_list.status_code == 200, foreign_list.text
        assert {item["foreign_opinion_id"] for item in foreign_list.json()["items"]} == {
            opinion_id
        }

        domestic_list = client.get(
            "/api/opinions",
            headers=auth_headers,
            params={"q": "API fixture"},
        )
        assert domestic_list.status_code == 200, domestic_list.text
        assert all(item["url"] != opinion_url for item in domestic_list.json()["items"])

        ai = client.post(
            f"/api/foreign/risk/{opinion_id}/ai-review",
            headers=auth_headers,
        )
        assert ai.status_code == 503, ai.text
        assert ai.json()["detail"]["code"] == "FOREIGN_AI_DISABLED"
    finally:
        db = SessionLocal()
        _cleanup(db, opinion_id)
        db.close()


def test_analysis_runs_and_terms_api_are_foreign_only(client, auth_headers):
    terms = client.get(
        "/api/foreign/risk-terms",
        headers=auth_headers,
    )
    assert terms.status_code == 200, terms.text
    assert terms.json()["total"] == 0

    runs = client.get(
        "/api/foreign/analysis-runs",
        headers=auth_headers,
    )
    assert runs.status_code == 200, runs.text
    # Rule and explicitly enabled AI reviews are both foreign analysis runs;
    # the endpoint must never leak a domestic analyzer type into this view.
    assert all(item["analyzer_type"] in {"rule", "ai"} for item in runs.json()["items"])
