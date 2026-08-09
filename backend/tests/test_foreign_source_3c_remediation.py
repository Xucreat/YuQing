"""Phase 3C remediation tests for foreign alert action audit integrity."""
from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest

from app.db.session import SessionLocal
from app.models.alert import AlertRecord
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_action import ForeignAlertAction
from app.models.foreign_opinion import ForeignOpinion
from app.models.user import User
from app.services.foreign_alert_service import ForeignAlertService


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _make_alert(db, suffix: str, *, status: str = "triggered") -> tuple[ForeignAlert, int]:
    opinion = ForeignOpinion(
        source_key=f"fixture_3c_remediation_{suffix}",
        source_name_snapshot="Remediation fixture",
        title=f"Remediation alert {suffix}",
        summary="fixture",
        content="A sufficiently long remediation fixture article body.",
        url=f"https://fixture.test/remediation/{suffix}",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        matched_keywords=["China"],
        content_hash=(suffix * 8)[:64],
    )
    db.add(opinion)
    db.flush()
    alert = ForeignAlert(
        foreign_opinion_id=opinion.id,
        severity="high",
        status=status,
        title=f"Remediation alert {suffix}",
        message="fixture alert",
        deduplication_key=f"remediation:{suffix}",
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert, opinion.id


def _cleanup(db, alert_ids: list[int], opinion_ids: list[int]) -> None:
    if alert_ids:
        db.query(ForeignAlertAction).filter(ForeignAlertAction.foreign_alert_id.in_(alert_ids)).delete(
            synchronize_session=False
        )
        db.query(ForeignAlert).filter(ForeignAlert.id.in_(alert_ids)).delete(synchronize_session=False)
    if opinion_ids:
        db.query(ForeignOpinion).filter(ForeignOpinion.id.in_(opinion_ids)).delete(synchronize_session=False)
    db.commit()


def test_action_audit_fields_and_idempotent_transitions():
    db = SessionLocal()
    alert_ids: list[int] = []
    opinion_ids: list[int] = []
    suffix = _suffix()
    try:
        alert, opinion_id = _make_alert(db, suffix)
        alert_ids.append(alert.id)
        opinion_ids.append(opinion_id)
        actor_id = db.query(User).order_by(User.id.asc()).first().id

        acknowledged = ForeignAlertService.transition(
            db,
            alert.id,
            action_type="acknowledge",
            note="人工确认，继续观察",
            user_id=actor_id,
        )
        assert acknowledged.alert.status == "acknowledged"
        assert acknowledged.action.previous_status == "triggered"
        assert acknowledged.action.new_status == "acknowledged"
        assert acknowledged.action.note == "人工确认，继续观察"
        assert acknowledged.action.actor_id == actor_id
        assert acknowledged.action.created_at is not None

        repeated = ForeignAlertService.transition(
            db,
            alert.id,
            action_type="acknowledge",
            note="重复请求",
            user_id=actor_id,
        )
        assert repeated.idempotent is True
        assert repeated.action.id == acknowledged.action.id
        assert db.query(ForeignAlertAction).filter(ForeignAlertAction.foreign_alert_id == alert.id).count() == 1

        resolved = ForeignAlertService.transition(
            db,
            alert.id,
            action_type="resolve",
            note="确认事项已解决",
            user_id=actor_id,
        )
        assert resolved.action.previous_status == "acknowledged"
        assert resolved.action.new_status == "resolved"
        assert resolved.alert.status == "resolved"
        assert db.query(ForeignAlertAction).filter(ForeignAlertAction.foreign_alert_id == alert.id).count() == 2
    finally:
        _cleanup(db, alert_ids, opinion_ids)
        db.close()


def test_suppress_and_invalid_transition_do_not_create_bad_actions():
    db = SessionLocal()
    alert_ids: list[int] = []
    opinion_ids: list[int] = []
    suffix = _suffix()
    try:
        alert, opinion_id = _make_alert(db, suffix)
        alert_ids.append(alert.id)
        opinion_ids.append(opinion_id)
        actor_id = db.query(User).order_by(User.id.asc()).first().id

        suppressed = ForeignAlertService.transition(
            db,
            alert.id,
            action_type="suppress",
            note="抑制重复低价值告警",
            user_id=actor_id,
        )
        assert suppressed.alert.status == "suppressed"
        assert suppressed.action.previous_status == "triggered"
        assert suppressed.action.new_status == "suppressed"

        repeated = ForeignAlertService.transition(
            db,
            alert.id,
            action_type="suppress",
            note="重复抑制",
            user_id=actor_id,
        )
        assert repeated.idempotent is True
        assert repeated.action.id == suppressed.action.id
        with pytest.raises(ValueError):
            ForeignAlertService.transition(
                db,
                alert.id,
                action_type="resolve",
                note="非法解决",
                user_id=actor_id,
            )
        assert db.query(ForeignAlertAction).filter(ForeignAlertAction.foreign_alert_id == alert.id).count() == 1
        assert db.get(ForeignAlert, alert.id).status == "suppressed"
    finally:
        _cleanup(db, alert_ids, opinion_ids)
        db.close()


def test_action_api_requires_note_returns_history_and_keeps_domestic_alerts_unchanged(client, auth_headers):
    db = SessionLocal()
    alert_ids: list[int] = []
    opinion_ids: list[int] = []
    suffix = _suffix()
    try:
        alert, opinion_id = _make_alert(db, suffix)
        alert_ids.append(alert.id)
        opinion_ids.append(opinion_id)
        domestic_before = db.query(AlertRecord).count()
    finally:
        db.close()

    try:
        missing_note = client.post(
            f"/api/foreign/alerts/{alert.id}/acknowledge",
            headers=auth_headers,
            json={"note": "   "},
        )
        assert missing_note.status_code == 422

        response = client.post(
            f"/api/foreign/alerts/{alert.id}/acknowledge",
            headers=auth_headers,
            json={"note": "API 人工确认"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["alert_id"] == alert.id
        assert body["action_type"] == "acknowledge"
        assert body["previous_status"] == "triggered"
        assert body["new_status"] == "acknowledged"
        assert body["note"] == "API 人工确认"
        assert body["actor_id"] is not None
        assert body["created_at"]

        repeated = client.post(
            f"/api/foreign/alerts/{alert.id}/acknowledge",
            headers=auth_headers,
            json={"note": "重复 API 请求"},
        )
        assert repeated.status_code == 200
        assert repeated.json()["idempotent"] is True

        history = client.get(f"/api/foreign/alerts/{alert.id}/actions", headers=auth_headers)
        assert history.status_code == 200
        assert history.json()["total"] == 1
        assert history.json()["items"][0]["note"] == "API 人工确认"

        db = SessionLocal()
        assert db.query(AlertRecord).count() == domestic_before
        db.close()
        assert client.get(f"/api/foreign/alerts/{alert.id}/actions").status_code == 401
    finally:
        db = SessionLocal()
        _cleanup(db, alert_ids, opinion_ids)
        db.close()


def test_concurrent_actions_leave_one_valid_status_chain():
    db = SessionLocal()
    alert_ids: list[int] = []
    opinion_ids: list[int] = []
    suffix = _suffix()
    try:
        alert, opinion_id = _make_alert(db, suffix)
        alert_ids.append(alert.id)
        opinion_ids.append(opinion_id)
        actor_id = db.query(User).order_by(User.id.asc()).first().id

        def apply(action_type: str):
            worker_db = SessionLocal()
            try:
                result = ForeignAlertService.transition(
                    worker_db,
                    alert.id,
                    action_type=action_type,
                    note=f"并发{action_type}",
                    user_id=actor_id,
                )
                return "ok", result.action.id
            except Exception as exc:  # the loser must be a safe state conflict
                return type(exc).__name__, None
            finally:
                worker_db.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(apply, ("acknowledge", "suppress")))
        assert sum(result[0] == "ok" for result in results) == 1
        db.expire_all()
        fresh = db.get(ForeignAlert, alert.id)
        assert fresh.status in {"acknowledged", "suppressed"}
        assert db.query(ForeignAlertAction).filter(ForeignAlertAction.foreign_alert_id == alert.id).count() == 1
    finally:
        _cleanup(db, alert_ids, opinion_ids)
        db.close()


def test_transaction_failure_rolls_back_alert_and_action(monkeypatch):
    db = SessionLocal()
    alert_ids: list[int] = []
    opinion_ids: list[int] = []
    suffix = _suffix()
    try:
        alert, opinion_id = _make_alert(db, suffix)
        alert_ids.append(alert.id)
        opinion_ids.append(opinion_id)
        actor_id = db.query(User).order_by(User.id.asc()).first().id

        def fail_flush():
            raise RuntimeError("fixture flush failure")

        monkeypatch.setattr(db, "flush", fail_flush)
        with pytest.raises(RuntimeError, match="Foreign alert action failed"):
            ForeignAlertService.transition(
                db,
                alert.id,
                action_type="acknowledge",
                note="事务失败测试",
                user_id=actor_id,
            )
        db.rollback()
        fresh = db.get(ForeignAlert, alert.id)
        assert fresh.status == "triggered"
        assert db.query(ForeignAlertAction).filter(ForeignAlertAction.foreign_alert_id == alert.id).count() == 0
    finally:
        _cleanup(db, alert_ids, opinion_ids)
        db.close()
