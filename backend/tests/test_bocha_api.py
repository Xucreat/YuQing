from __future__ import annotations

from uuid import uuid4

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.bocha_lead import BochaLead
from app.models.bocha_search_session import BochaSearchSession
from app.models.opinion import Opinion
from app.models.user import User
import app.api.admin_bocha as admin_bocha
from app.services.bocha_search_service import BochaSearchResult
from app.services.bocha_search_service import BochaSearchError


def _url() -> str:
    return f"https://bocha-test.example/{uuid4().hex}"


def _create_lead(*, status: str = "new", url: str | None = None, created_by: int | None = None) -> int:
    db = SessionLocal()
    try:
        lead = BochaLead(
            query="test query",
            title="Bocha lead",
            url=url or _url(),
            snippet="snippet",
            summary="summary",
            source_name="Example",
            status=status,
            raw_json={"url": url or "raw"},
            created_by=created_by,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead.id
    finally:
        db.close()


def _get_lead(lead_id: int) -> BochaLead:
    db = SessionLocal()
    try:
        lead = db.get(BochaLead, lead_id)
        assert lead is not None
        db.expunge(lead)
        return lead
    finally:
        db.close()


def test_admin_bocha_search_success(monkeypatch, client, auth_headers):
    db = SessionLocal()
    try:
        before_leads = db.query(BochaLead).count()
        before_count = db.query(Opinion).count()
    finally:
        db.close()

    def fake_search(self, db, **kwargs):
        session = BochaSearchSession(
            query=kwargs["query"],
            freshness=kwargs.get("freshness"),
            summary=kwargs.get("summary", True),
            count=kwargs.get("count") or 1,
            result_count=1,
            status="success",
            created_by=kwargs.get("created_by"),
            raw_results=[],
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        results = [{
            "title": "Mock result",
            "url": _url(),
            "snippet": "mock snippet",
            "summary": "mock summary",
            "source_name": "Mock source",
            "publish_time": None,
            "raw_json": {"mock": True},
        }]
        session.raw_results = results
        db.commit()
        return BochaSearchResult(session=session, results=results)

    monkeypatch.setattr(
        "app.api.admin_bocha.BochaSearchService.search",
        fake_search,
    )
    response = client.post(
        "/api/admin/bocha/search",
        json={"query": "test query", "count": 1},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["session"]["status"] == "success"
    assert body["items"][0]["title"] == "Mock result"
    db = SessionLocal()
    try:
        assert db.query(Opinion).count() == before_count
        assert db.query(BochaLead).count() == before_leads
    finally:
        db.close()


def test_admin_bocha_search_missing_key_returns_controlled_error(
    monkeypatch,
    client,
    auth_headers,
):
    def fake_search(self, db, **kwargs):
        raise BochaSearchError("BOCHA_API_KEY is not configured")

    monkeypatch.setattr(
        "app.api.admin_bocha.BochaSearchService.search",
        fake_search,
    )

    response = client.post(
        "/api/admin/bocha/search",
        json={"query": "test query"},
        headers=auth_headers,
    )

    assert response.status_code == 503, response.text
    assert response.json()["detail"] == "Bocha search is not configured"
    assert "Authorization" not in response.text


def test_non_admin_bocha_access_is_rejected(client):
    username = f"analyst_{uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        db.add(
            User(
                username=username,
                password_hash=hash_password("analyst123"),
                role="analyst",
                is_superuser=False,
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/login",
        json={"username": username, "password": "analyst123"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/admin/bocha/leads", headers=headers)
    assert response.status_code == 403, response.text


def test_bocha_leads_list_supports_filters_and_pagination(client, auth_headers):
    _create_lead(status="new")
    _create_lead(status="confirmed")

    response = client.get(
        "/api/admin/bocha/leads",
        params={"status": "new", "query": "test", "page": 1, "size": 1},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page"] == 1
    assert body["size"] == 1
    assert body["total"] >= 1
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "new"


def test_bocha_confirm_and_reject_status_transitions(client, auth_headers):
    confirm_id = _create_lead()
    response = client.post(
        f"/api/admin/bocha/leads/{confirm_id}/confirm",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "confirmed"

    reject_id = _create_lead()
    response = client.post(
        f"/api/admin/bocha/leads/{reject_id}/reject",
        json={"reason": "not relevant"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"
    assert _get_lead(reject_id).status == "rejected"

    confirmed_reject_id = _create_lead(status="confirmed")
    response = client.post(
        f"/api/admin/bocha/leads/{confirmed_reject_id}/reject",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "rejected"

    response = client.post(
        f"/api/admin/bocha/leads/{confirm_id}/confirm",
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text


def test_bocha_promote_creates_opinion(client, auth_headers, seeded_region_id):
    lead_id = _create_lead(status="confirmed")
    response = client.post(
        f"/api/admin/bocha/leads/{lead_id}/promote",
        json={"region_id": seeded_region_id},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["already_promoted"] is False
    assert body["lead"]["status"] == "promoted"
    assert body["lead"]["opinion_id"] == body["opinion"]["id"]
    assert body["opinion"]["source"] == "Bocha辅助搜索"
    assert body["opinion"]["content"] == "summary"
    assert body["opinion"]["risk_score"] == 0
    assert body["opinion"]["severity_score"] == 0
    assert body["opinion"]["sentiment"] == "neutral"
    assert body["opinion"]["analysis_status"] == "pending"
    assert body["opinion"]["analysis_time"] is None
    assert body["opinion"]["analysis_suggestion"] is None


def test_bocha_promote_is_idempotent(client, auth_headers, seeded_region_id):
    assert not hasattr(admin_bocha, "_apply_system_rule_analysis")
    assert not hasattr(admin_bocha, "_run_promoted_opinion_pipeline")
    assert not hasattr(admin_bocha, "RuleFallbackProvider")
    assert not hasattr(admin_bocha, "RiskEngine")
    assert not hasattr(admin_bocha, "EventAggregator")
    assert not hasattr(admin_bocha, "AlertService")

    lead_id = _create_lead(status="confirmed")
    first = client.post(
        f"/api/admin/bocha/leads/{lead_id}/promote",
        json={"region_id": seeded_region_id},
        headers=auth_headers,
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/admin/bocha/leads/{lead_id}/promote",
        json={"region_id": seeded_region_id},
        headers=auth_headers,
    )
    assert second.status_code == 200, second.text
    assert second.json()["already_promoted"] is True
    assert second.json()["opinion"]["id"] == first.json()["opinion"]["id"]
    assert second.json()["opinion"]["analysis_status"] == "pending"
    assert second.json()["opinion"]["risk_score"] == 0
    assert second.json()["opinion"]["severity_score"] == 0


def test_bocha_promote_rejects_duplicate_url(client, auth_headers, seeded_region_id):
    url = _url()
    db = SessionLocal()
    try:
        db.add(
            Opinion(
                title="Existing opinion",
                content="existing",
                source="existing",
                url=url,
                region_id=seeded_region_id,
            )
        )
        db.commit()
    finally:
        db.close()

    lead_id = _create_lead(status="confirmed", url=url)
    response = client.post(
        f"/api/admin/bocha/leads/{lead_id}/promote",
        json={"region_id": seeded_region_id},
        headers=auth_headers,
    )
    assert response.status_code == 409, response.text
    assert _get_lead(lead_id).status == "confirmed"


def test_bocha_promote_does_not_run_downstream_pipeline(
    monkeypatch,
    client,
    auth_headers,
    seeded_region_id,
):
    class ForbiddenService:
        def __init__(self, *args, **kwargs):
            raise AssertionError("A downstream analysis service was called")

    monkeypatch.setattr("app.services.ai.fallback.RuleFallbackProvider", ForbiddenService)
    monkeypatch.setattr("app.services.risk_engine.RiskEngine", ForbiddenService)
    monkeypatch.setattr("app.services.event.aggregator.EventAggregator", ForbiddenService)
    monkeypatch.setattr("app.services.alert_service.AlertService", ForbiddenService)
    monkeypatch.setattr("app.services.ai_service.AIService", ForbiddenService)
    monkeypatch.setattr("app.services.ai.service.AIService", ForbiddenService)

    lead_id = _create_lead(status="confirmed")
    response = client.post(
        f"/api/admin/bocha/leads/{lead_id}/promote",
        json={"region_id": seeded_region_id},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["opinion"]["analysis_status"] == "pending"
    assert body["opinion"]["risk_score"] == 0
    assert body["opinion"]["severity_score"] == 0
