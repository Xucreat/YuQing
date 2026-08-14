"""Phase 4B-Backend: foreign event hard-delete endpoint tests.

Verified behaviour (clean probe, not a code bug):
Deleting a foreign event only removes the event row and its
foreign_event_opinions link rows (unlink). Opinions themselves are
PRESERVED (the foreign_opinion_id FK CASCADE only fires when an opinion is
deleted, not when a link is deleted). foreign_event_action and foreign_alert
keep their rows with foreign_event_id set to NULL, so ck_foreign_alerts_has_target
is never violated (the alert still has a valid foreign_opinion_id).

This matches the required product semantics: "remove the event from the list,
unlink its opinions, keep the opinions, affect nothing else."

Covers:
1. requires auth (no auth -> 401/403)
2. no write permission -> 403
3. missing event -> 404
4. with permission -> 200 + detail + id
5. after delete GET -> 404
6. foreign_event_opinion links removed (unlink)
7. foreign_event_action preserved with foreign_event_id NULL
8. foreign_opinion preserved (not cascade-deleted)
9. foreign_alert preserved with foreign_event_id NULL and foreign_opinion_id intact
"""
from __future__ import annotations

import time

import pytest
from sqlalchemy import delete, func, select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_opinion import ForeignOpinion
from app.models.user import User


def _make_event(db, n=2, with_alert=False):
    event = ForeignEvent(
        title="delete-test-event",
        summary="",
        language="en",
        event_status="active",
        risk_level="low",
        heat_score=10,
        opinion_count=n,
        source_count=1,
        confidence=0.6,
    )
    db.add(event)
    db.flush()
    op_ids = []
    for i in range(n):
        op = ForeignOpinion(
            title=f"del-op-{i}",
            url=f"https://example.com/del/{int(time.time() * 1000000)}-{i}",
            source_name_snapshot="CNN",
            current_risk_score=30,
        )
        db.add(op)
        db.flush()
        op_ids.append(op.id)
        db.add(
            ForeignEventOpinion(
                foreign_event_id=event.id,
                foreign_opinion_id=op.id,
                relation_type="primary",
            )
        )
    action = ForeignEventAction(action_type="status_change", foreign_event_id=event.id)
    db.add(action)
    db.flush()
    action_id = action.id
    alert_id = None
    if with_alert:
        # Production practice (foreign_event_service.py): an alert carries both
        # foreign_event_id and foreign_opinion_id.
        alert = None
        alert = ForeignAlert(
            severity="high",
            deduplication_key=f"del-alert-{int(time.time() * 1000000)}-{event.id}",
            foreign_event_id=event.id,
            foreign_opinion_id=op_ids[0],
            evaluation_source="rule",
        )
        db.add(alert)
        db.flush()
        alert_id = alert.id
    db.commit()
    return event, op_ids, action_id, alert_id


def _cleanup(db, event_id, op_ids, action_id, alert_id):
    # Order matters: drop the alert/action rows first so that deleting the
    # opinions afterwards does not trip ck_foreign_alerts_has_target
    # (the alert would otherwise lose its last non-null target). The event
    # itself is already gone after the delete-under-test.
    if alert_id is not None:
        db.execute(delete(ForeignAlert).where(ForeignAlert.id == alert_id))
    if action_id is not None:
        db.execute(delete(ForeignEventAction).where(ForeignEventAction.id == action_id))
    if op_ids:
        db.execute(delete(ForeignOpinion).where(ForeignOpinion.id.in_(op_ids)))
    db.execute(delete(ForeignEvent).where(ForeignEvent.id == event_id))
    db.commit()


def test_delete_endpoint_requires_auth(client):
    r = client.delete("/api/foreign/events/1")
    assert r.status_code in (401, 403), r.text


def test_delete_forbidden_without_write_permission(client):
    db = SessionLocal()
    user = None
    try:
        uname = f"noforeignwrite_{int(time.time() * 1000000)}"
        user = User(
            username=uname,
            password_hash=hash_password("test1234"),
            role="nonexistent_role_xyz",
            is_superuser=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        login = client.post("/api/login", json={"username": uname, "password": "test1234"})
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        r = client.delete("/api/foreign/events/1", headers=headers)
        assert r.status_code == 403, r.text
    finally:
        if user is not None:
            try:
                db.delete(user)
                db.commit()
            except Exception:
                db.rollback()
        db.close()


def test_delete_missing_event_404(client, auth_headers):
    r = client.delete("/api/foreign/events/99999999", headers=auth_headers)
    assert r.status_code == 404, r.text


def test_delete_success_no_alert(client, auth_headers):
    db = SessionLocal()
    ev = None
    op_ids = []
    action_id = None
    alert_id = None
    try:
        ev, op_ids, action_id, alert_id = _make_event(db, 2, with_alert=False)
        event_id = ev.id
        link_count_before = db.scalar(
            select(func.count(ForeignEventOpinion.id)).where(
                ForeignEventOpinion.foreign_event_id == event_id
            )
        )
        assert link_count_before == 2

        r = client.delete(f"/api/foreign/events/{event_id}", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("detail") == "Foreign event deleted"
        assert body.get("id") == event_id

        # GET event -> 404 after delete (no fake delete)
        g = client.get(f"/api/foreign/events/{event_id}", headers=auth_headers)
        assert g.status_code == 404, g.text

        # opinion links removed (unlink)
        link_count_after = db.scalar(
            select(func.count(ForeignEventOpinion.id)).where(
                ForeignEventOpinion.foreign_event_id == event_id
            )
        )
        assert link_count_after == 0, "foreign_event_opinions links should be removed"

        # opinions themselves preserved
        op_count = db.scalar(
            select(func.count(ForeignOpinion.id)).where(ForeignOpinion.id.in_(op_ids))
        )
        assert op_count == 2, "foreign_opinions should be preserved"

        # action preserved, foreign_event_id nulled (SET NULL semantics)
        action = db.get(ForeignEventAction, action_id)
        assert action is not None, "foreign_event_action should be preserved"
        assert action.foreign_event_id is None, "foreign_event_action.foreign_event_id should be NULL"
    finally:
        if ev is not None:
            _cleanup(db, ev.id, op_ids, action_id, alert_id)
        db.close()


def test_delete_with_alert_preserves_opinions(client, auth_headers):
    db = SessionLocal()
    ev = None
    op_ids = []
    action_id = None
    alert_id = None
    try:
        ev, op_ids, action_id, alert_id = _make_event(db, 2, with_alert=True)
        event_id = ev.id

        r = client.delete(f"/api/foreign/events/{event_id}", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("detail") == "Foreign event deleted"
        assert body.get("id") == event_id

        # GET event -> 404 after delete (no fake delete)
        g = client.get(f"/api/foreign/events/{event_id}", headers=auth_headers)
        assert g.status_code == 404, g.text

        # opinions preserved (not cascade-deleted)
        op_count = db.scalar(
            select(func.count(ForeignOpinion.id)).where(ForeignOpinion.id.in_(op_ids))
        )
        assert op_count == 2, "foreign_opinions must be preserved on event delete"

        # links removed (unlink)
        link_count = db.scalar(
            select(func.count(ForeignEventOpinion.id)).where(
                ForeignEventOpinion.foreign_event_id == event_id
            )
        )
        assert link_count == 0, "foreign_event_opinions links should be removed"

        # action preserved, foreign_event_id nulled
        action = db.get(ForeignEventAction, action_id)
        assert action is not None, "foreign_event_action should be preserved"
        assert action.foreign_event_id is None

        # alert preserved: event_id NULL but opinion_id still valid -> check passes
        alert = db.get(ForeignAlert, alert_id)
        assert alert is not None, "foreign_alert should be preserved"
        assert alert.foreign_event_id is None, "foreign_alert.foreign_event_id should be NULL"
        assert alert.foreign_opinion_id == op_ids[0], "foreign_alert.foreign_opinion_id should survive"
    finally:
        if ev is not None:
            _cleanup(db, ev.id, op_ids, action_id, alert_id)
        db.close()
