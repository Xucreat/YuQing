from __future__ import annotations

from uuid import uuid4

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.bocha_lead import BochaLead
from app.models.bocha_search_session import BochaSearchSession
from app.models.opinion import Opinion
from app.models.user import User
from app.services.bocha_search_service import BochaSearchResult


def _url() -> str:
    return f"https://bocha-ai-search.example/{uuid4().hex}"


def _create_user_and_login(client, *, role: str = "analyst") -> tuple[int, dict]:
    username = f"{role}_{uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        user = User(
            username=username,
            password_hash=hash_password("pass123"),
            role=role,
            is_superuser=False,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    login = client.post("/api/login", json={"username": username, "password": "pass123"})
    assert login.status_code == 200, login.text
    return user_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _fake_search(self, db, **kwargs):
    results = [{
        "title": "AI search result",
        "url": _url(),
        "snippet": "snippet",
        "summary": "summary",
        "source_name": "Search source",
        "publish_time": None,
        "raw_json": {"source": "mock"},
    }]
    session = BochaSearchSession(
        query=kwargs["query"],
        freshness=kwargs.get("freshness"),
        summary=kwargs.get("summary", True),
        count=kwargs.get("count") or 1,
        result_count=len(results),
        status="success",
        created_by=kwargs.get("created_by"),
        raw_results=results,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return BochaSearchResult(session=session, results=results)


def test_user_search_does_not_create_leads_or_opinions(monkeypatch, client):
    class ForbiddenService:
        def __init__(self, *args, **kwargs):
            raise AssertionError("downstream analysis service was called")

    monkeypatch.setattr("app.services.risk_engine.RiskEngine", ForbiddenService)
    monkeypatch.setattr("app.services.event.aggregator.EventAggregator", ForbiddenService)
    monkeypatch.setattr("app.services.alert_service.AlertService", ForbiddenService)
    monkeypatch.setattr("app.services.ai_service.AIService", ForbiddenService)
    monkeypatch.setattr("app.services.ai.service.AIService", ForbiddenService)

    user_id, headers = _create_user_and_login(client)
    db = SessionLocal()
    try:
        before_leads = db.query(BochaLead).count()
        before_opinions = db.query(Opinion).count()
    finally:
        db.close()

    monkeypatch.setattr("app.api.bocha.BochaSearchService.search", _fake_search)
    response = client.post(
        "/api/bocha/search",
        json={"query": "廊坊 风险", "count": 1},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session"]["created_by"] == user_id
    assert body["total"] == 1
    assert body["items"][0]["result_index"] == 0

    db = SessionLocal()
    try:
        assert db.query(BochaLead).count() == before_leads
        assert db.query(Opinion).count() == before_opinions
    finally:
        db.close()


def test_save_lead_from_session_result(client):
    user_id, headers = _create_user_and_login(client)
    result_url = _url()
    db = SessionLocal()
    try:
        session = BochaSearchSession(
            query="保存测试",
            summary=True,
            count=1,
            result_count=1,
            status="success",
            created_by=user_id,
            raw_results=[{
                "title": "Saved title",
                "url": result_url,
                "snippet": "Saved snippet",
                "summary": "Saved summary",
                "source_name": "Saved source",
                "publish_time": None,
                "raw_json": {"url": result_url},
            }],
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    finally:
        db.close()

    response = client.post(
        "/api/bocha/leads",
        json={"session_id": session_id, "result_index": 0},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "new"
    assert body["created_by"] == user_id
    assert body["search_session_id"] == session_id
    assert body["result_index"] == 0
    assert body["url"] == result_url


def test_non_admin_cannot_promote(client, seeded_region_id):
    user_id, headers = _create_user_and_login(client)
    db = SessionLocal()
    try:
        lead = BochaLead(
            query="q",
            title="t",
            url=_url(),
            snippet="s",
            summary="sum",
            source_name="src",
            status="confirmed",
            created_by=user_id,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        lead_id = lead.id
    finally:
        db.close()

    response = client.post(
        f"/api/admin/bocha/leads/{lead_id}/promote",
        json={"region_id": seeded_region_id},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_promote_requires_confirmed_status(client, auth_headers, seeded_region_id):
    ids = {}
    db = SessionLocal()
    try:
        for lead_status in ("new", "rejected"):
            lead = BochaLead(
                query="q",
                title=f"{lead_status} lead",
                url=_url(),
                snippet="s",
                summary="sum",
                source_name="src",
                status=lead_status,
            )
            db.add(lead)
            db.commit()
            db.refresh(lead)
            ids[lead_status] = lead.id
    finally:
        db.close()

    for lead_status, lead_id in ids.items():
        response = client.post(
            f"/api/admin/bocha/leads/{lead_id}/promote",
            json={"region_id": seeded_region_id},
            headers=auth_headers,
        )
        assert response.status_code == 409, (lead_status, response.text)
