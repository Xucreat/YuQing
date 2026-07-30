from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.core.security import create_access_token
from app.models.audit import OperationLog
from app.models.event import Event
from app.models.event_action import EventAction
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


def _create_event(region_id: int, *, status: str = "active") -> int:
    db = SessionLocal()
    try:
        event = Event(
            title=f"Phase2E operations {uuid.uuid4().hex}",
            description="event operations test",
            keyword="test",
            region_id=region_id,
            status=status,
            risk_score=73,
            risk_level="high",
            topic_category="livelihood",
            heat_score=61,
            trend="rising",
            opinion_count=0,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event.id
    finally:
        db.close()


def _cleanup_event(event_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(OperationLog).filter(
            OperationLog.resource_type == "event",
            OperationLog.resource_id == str(event_id),
        ).delete(synchronize_session=False)
        db.query(EventAction).filter(EventAction.event_id == event_id).delete(
            synchronize_session=False
        )
        db.query(Event).filter(Event.id == event_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_event_status_update_creates_action_and_preserves_metrics(
    client, auth_headers, seeded_region_id
):
    event_id = _create_event(seeded_region_id)
    try:
        response = client.patch(
            f"/api/events/{event_id}/status",
            json={"status": "verifying"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "verifying"
        assert data["risk_score"] == 73
        assert data["risk_level"] == "high"
        assert data["heat_score"] == 61
        assert data["trend"] == "rising"

        db = SessionLocal()
        try:
            action = db.query(EventAction).filter_by(event_id=event_id).one()
            assert action.action_type == "status_change"
            assert action.old_status == "active"
            assert action.new_status == "verifying"
            assert action.user_id is not None
            assert "关注中" in action.content
            assert "核查中" in action.content
            audit = db.query(OperationLog).filter_by(
                resource_type="event", resource_id=str(event_id)
            ).one()
            assert audit.action == "EVENT_STATUS_CHANGE"
            assert audit.result == "success"
        finally:
            db.close()

        detail = client.get(f"/api/events/{event_id}", headers=auth_headers)
        assert detail.status_code == 200, detail.text
        timeline = detail.json()["actions"]
        assert len(timeline) == 1
        assert timeline[0]["action_type"] == "status_change"
        assert timeline[0]["username"]
    finally:
        _cleanup_event(event_id)


def test_invalid_event_status_returns_422(client, auth_headers, seeded_region_id):
    event_id = _create_event(seeded_region_id)
    try:
        response = client.patch(
            f"/api/events/{event_id}/status",
            json={"status": "invalid"},
            headers=auth_headers,
        )
        assert response.status_code == 422, response.text
        db = SessionLocal()
        try:
            assert db.get(Event, event_id).status == "active"
            assert db.query(EventAction).filter_by(event_id=event_id).count() == 0
        finally:
            db.close()
    finally:
        _cleanup_event(event_id)


def test_disallowed_event_status_jump_returns_409(
    client, auth_headers, seeded_region_id
):
    event_id = _create_event(seeded_region_id)
    try:
        response = client.patch(
            f"/api/events/{event_id}/status",
            json={"status": "resolved"},
            headers=auth_headers,
        )
        assert response.status_code == 409, response.text
        db = SessionLocal()
        try:
            assert db.get(Event, event_id).status == "active"
            assert db.query(EventAction).filter_by(event_id=event_id).count() == 0
        finally:
            db.close()
    finally:
        _cleanup_event(event_id)


def test_event_note_creates_action_without_changing_status_or_metrics(
    client, auth_headers, seeded_region_id
):
    event_id = _create_event(seeded_region_id, status="processing")
    try:
        response = client.post(
            f"/api/events/{event_id}/actions",
            json={"action_type": "note", "content": "  已通知街道核查  "},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["action_type"] == "note"
        assert data["content"] == "已通知街道核查"
        assert data["old_status"] is None
        assert data["new_status"] is None

        db = SessionLocal()
        try:
            event = db.get(Event, event_id)
            assert event.status == "processing"
            assert event.risk_score == 73
            assert event.heat_score == 61
            assert event.trend == "rising"
            action = db.query(EventAction).filter_by(event_id=event_id).one()
            assert action.content == "已通知街道核查"
            audit = db.query(OperationLog).filter_by(
                resource_type="event", resource_id=str(event_id)
            ).one()
            assert audit.action == "EVENT_NOTE_CREATE"
        finally:
            db.close()
    finally:
        _cleanup_event(event_id)


@pytest.mark.parametrize(
    ("old_status", "new_status"),
    [
        ("active", "verifying"),
        ("verifying", "processing"),
        ("processing", "resolved"),
        ("resolved", "closed"),
    ],
)
def test_all_forward_event_status_transitions_are_allowed(
    client, auth_headers, seeded_region_id, old_status, new_status
):
    event_id = _create_event(seeded_region_id, status=old_status)
    try:
        response = client.patch(
            f"/api/events/{event_id}/status",
            json={"status": new_status},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == new_status
    finally:
        _cleanup_event(event_id)


@pytest.mark.parametrize("old_status", ["verifying", "processing", "resolved", "closed"])
def test_event_status_can_return_to_active(
    client, auth_headers, seeded_region_id, old_status
):
    event_id = _create_event(seeded_region_id, status=old_status)
    try:
        response = client.patch(
            f"/api/events/{event_id}/status",
            json={"status": "active"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "active"
    finally:
        _cleanup_event(event_id)


def test_event_operations_require_events_write_permission(client, seeded_region_id):
    suffix = uuid.uuid4().hex[:8]
    viewer_role_name = f"p2e_v_{suffix}"
    writer_role_name = f"p2e_w_{suffix}"
    db = SessionLocal()
    try:
        permission = db.query(Permission).filter_by(code="events:write").first()
        if permission is None:
            permission = Permission(
                code="events:write",
                name="管理事件",
                resource="events",
                action="write",
                group="事件管理",
            )
            db.add(permission)
            db.flush()
        viewer_role = Role(
            name=viewer_role_name,
            code=viewer_role_name,
            display_name="Phase2E viewer",
        )
        writer_role = Role(
            name=writer_role_name,
            code=writer_role_name,
            display_name="Phase2E writer",
        )
        writer_role.permissions = [permission]
        viewer = User(
            username=f"p2e_viewer_{suffix}",
            password_hash="unused",
            role=viewer_role_name,
            is_active=True,
        )
        writer = User(
            username=f"p2e_writer_{suffix}",
            password_hash="unused",
            role=writer_role_name,
            is_active=True,
        )
        db.add_all([viewer_role, writer_role, viewer, writer])
        db.commit()
        db.refresh(viewer)
        db.refresh(writer)
        viewer_id, writer_id = viewer.id, writer.id
        viewer_headers = {
            "Authorization": f"Bearer {create_access_token(viewer_id)}"
        }
        writer_headers = {
            "Authorization": f"Bearer {create_access_token(writer_id)}"
        }
    finally:
        db.close()

    event_id = _create_event(seeded_region_id)
    try:
        denied = client.patch(
            f"/api/events/{event_id}/status",
            json={"status": "verifying"},
            headers=viewer_headers,
        )
        assert denied.status_code == 403, denied.text
        denied_note = client.post(
            f"/api/events/{event_id}/actions",
            json={"action_type": "note", "content": "not allowed"},
            headers=viewer_headers,
        )
        assert denied_note.status_code == 403, denied_note.text

        allowed = client.patch(
            f"/api/events/{event_id}/status",
            json={"status": "verifying"},
            headers=writer_headers,
        )
        assert allowed.status_code == 200, allowed.text
    finally:
        _cleanup_event(event_id)
        db = SessionLocal()
        try:
            db.query(User).filter(User.id.in_([viewer_id, writer_id])).delete(
                synchronize_session=False
            )
            db.query(Role).filter(
                Role.name.in_([viewer_role_name, writer_role_name])
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
