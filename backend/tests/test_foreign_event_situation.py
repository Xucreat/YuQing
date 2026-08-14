"""Phase 3: foreign event situation endpoint regression tests.

Covers:
1. endpoint exists / valid event returns 200
2. response contains statistics
3. response contains situation
4. situation contains source_distribution, data_window, risk_shadow,
   data_sufficiency, risk_factors
5. 404 for missing event
6. unauthorized (no auth) rejected
7. forbidden (authenticated, no permission) rejected with 403
8. response structure equals ForeignEventSituationService.build output

Targets isolated test db opinion_test only.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.api.foreign_events import get_foreign_event_situation
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_opinion import ForeignOpinion
from app.models.user import User
from app.services.foreign_event_situation import ForeignEventSituationService


def _make_event_with_opinions(db, n=3):
    event = ForeignEvent(
        title="situation-test-event",
        summary="",
        language="en",
        event_status="active",
        risk_level="medium",
        heat_score=20,
        opinion_count=n,
        source_count=2,
        confidence=0.6,
    )
    db.add(event)
    db.flush()
    sources = ["CNN", "Reuters"]
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    op_ids = []
    for i in range(n):
        op = ForeignOpinion(
            title=f"op {i}",
            url=f"https://example.com/{i}",
            source_name_snapshot=sources[i % 2],
            published_at=base + timedelta(days=i),
            current_risk_score=70 if i == 0 else (50 if i == 1 else 30),
        )
        db.add(op)
        db.flush()
        op_ids.append(op.id)
        link = ForeignEventOpinion(
            foreign_event_id=event.id,
            foreign_opinion_id=op.id,
            relation_type="primary",
        )
        db.add(link)
    db.commit()
    return event, op_ids


def _cleanup(db, event_id, op_ids):
    db.execute(
        delete(ForeignEventOpinion).where(
            ForeignEventOpinion.foreign_event_id == event_id
        )
    )
    if op_ids:
        db.execute(delete(ForeignOpinion).where(ForeignOpinion.id.in_(op_ids)))
    db.execute(delete(ForeignEvent).where(ForeignEvent.id == event_id))
    db.commit()


def test_situation_endpoint_200_and_shape(client, auth_headers):
    db = SessionLocal()
    ev = None
    op_ids = []
    try:
        ev, op_ids = _make_event_with_opinions(db, 3)
        r = client.get(f"/api/foreign/events/{ev.id}/situation", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "statistics" in body
        assert "situation" in body
        sit = body["situation"]
        for key in (
            "source_distribution",
            "data_window",
            "risk_shadow",
            "data_sufficiency",
            "risk_factors",
        ):
            assert key in sit, f"missing {key}"
        assert isinstance(sit["source_distribution"], list)
        assert isinstance(sit["risk_factors"], list)
        assert sit["data_sufficiency"]["level"] in (
            "insufficient",
            "limited",
            "sufficient",
        )
    finally:
        if ev is not None:
            _cleanup(db, ev.id, op_ids)
        db.close()


def test_situation_matches_service_build(client, auth_headers):
    db = SessionLocal()
    ev = None
    op_ids = []
    try:
        ev, op_ids = _make_event_with_opinions(db, 3)
        expected = ForeignEventSituationService().build(db, ev.id)
        r = client.get(f"/api/foreign/events/{ev.id}/situation", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json() == expected
    finally:
        if ev is not None:
            _cleanup(db, ev.id, op_ids)
        db.close()


def test_situation_404_for_missing(client, auth_headers):
    r = client.get("/api/foreign/events/99999999/situation", headers=auth_headers)
    assert r.status_code == 404, r.text


def test_situation_unauthorized_no_auth(client):
    r = client.get("/api/foreign/events/1/situation")
    assert r.status_code in (401, 403), r.text


def test_situation_forbidden_without_permission(client):
    db = SessionLocal()
    user = None
    try:
        uname = f"noeventperm_{int(time.time() * 1000)}"
        user = User(
            username=uname,
            password_hash=hash_password("test1234"),
            role="nonexistent_role_xyz",
            is_superuser=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        login = client.post(
            "/api/login", json={"username": uname, "password": "test1234"}
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = client.get("/api/foreign/events/1/situation", headers=headers)
        assert r.status_code == 403, r.text
    finally:
        if user is not None:
            try:
                db.delete(user)
                db.commit()
            except Exception:
                db.rollback()
        db.close()
