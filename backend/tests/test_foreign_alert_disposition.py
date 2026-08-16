"""Phase 4 Foreign Alert unified disposition backend tests.

Pure unit/integration tests with mocked DB sessions. No connection to any real
database, no data writes. Covers:
  A. Service (set_disposition): lifecycle mapping, failed guard, invalid input,
     note behaviour, audit row, atomic failure.
  B. API (handle + list): new/legacy payload, conflict, permission, filters.
  C. Regression: transition() unchanged, domestic alerts untouched, AI preview
     readonly intact, no foreign forbidden matrix.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.models.foreign_alert import ForeignAlert, ForeignAlertDispositionAction
from app.services.foreign_alert_service import (
    DISPOSITION_LIFECYCLE,
    ForeignAlertDispositionError,
    ForeignAlertService,
    VALID_DISPOSITIONS,
)


def make_alert(
    *,
    alert_id=1,
    status="triggered",
    disposition_status="pending",
    evaluation_source="rule",
    note=None,
    severity="medium",
):
    a = ForeignAlert()
    a.id = alert_id
    a.status = status
    a.disposition_status = disposition_status
    a.evaluation_source = evaluation_source
    a.disposition_note = note
    a.severity = severity
    a.title = "t"
    a.message = "m"
    a.matched_conditions = {}
    a.rule_snapshot = {}
    a.risk_level = "unknown"
    a.deduplication_key = "k"
    a.triggered_at = datetime.now(timezone.utc)
    a.created_at = datetime.now(timezone.utc)
    a.updated_at = datetime.now(timezone.utc)
    a.failure_reason = None
    a.expires_at = None
    a.acknowledged_at = None
    a.resolved_at = None
    a.suppressed_at = None
    return a


def mock_db(scalar_value):
    db = MagicMock()
    db.scalar.return_value = scalar_value
    db.scalars.return_value.all.return_value = [scalar_value] if scalar_value is not None else []
    return db


@contextmanager
def _noop_audit(*_a, **_k):
    yield {}


def patch_api(monkeypatch, perms):
    import app.api.foreign_alerts as fa

    monkeypatch.setattr(fa, "get_user_permissions", lambda user, db: perms)
    monkeypatch.setattr(fa, "audit_write", _noop_audit)
    monkeypatch.setattr(fa, "attach_effective_risk", lambda *a, **k: None)
    return fa


# A. Service
@pytest.mark.parametrize(
    "disposition,expected_lifecycle",
    [
        ("pending", "triggered"),
        ("processing", "acknowledged"),
        ("resolved", "resolved"),
        ("ignored", "suppressed"),
        ("false_positive", "suppressed"),
    ],
)
def test_service_lifecycle_mapping(disposition, expected_lifecycle):
    src = list(DISPOSITION_LIFECYCLE.keys())
    assert set(src) == set(VALID_DISPOSITIONS)
    alert = make_alert(status="triggered", disposition_status="pending")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status=disposition, note="n", user_id=5)
    assert alert.status == expected_lifecycle
    assert alert.disposition_status == disposition


def test_service_free_correction_resolved_to_ignored():
    alert = make_alert(status="resolved", disposition_status="resolved")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="ignored", note=None, user_id=5)
    assert alert.status == "suppressed"
    assert alert.disposition_status == "ignored"


def test_service_free_correction_resolved_to_false_positive():
    alert = make_alert(status="resolved", disposition_status="resolved")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="false_positive", note="fp", user_id=5)
    assert alert.status == "suppressed"
    assert alert.disposition_status == "false_positive"


def test_service_free_correction_suppressed_to_resolved():
    alert = make_alert(status="suppressed", disposition_status="ignored")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="resolved", note=None, user_id=5)
    assert alert.status == "resolved"


def test_service_free_correction_false_positive_to_processing():
    alert = make_alert(status="suppressed", disposition_status="false_positive")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="processing", note=None, user_id=5)
    assert alert.status == "acknowledged"


def test_service_failed_rejected():
    alert = make_alert(status="failed", disposition_status="pending")
    db = mock_db(alert)
    with pytest.raises(ForeignAlertDispositionError) as exc:
        ForeignAlertService.set_disposition(db, 1, disposition_status="ignored", note=None, user_id=5)
    assert exc.value.status_code == 409
    assert str(exc.value)


def test_service_invalid_disposition_rejected():
    alert = make_alert()
    db = mock_db(alert)
    with pytest.raises(ForeignAlertDispositionError) as exc:
        ForeignAlertService.set_disposition(db, 1, disposition_status="bogus", note=None, user_id=5)
    assert exc.value.status_code == 422


def test_service_not_found():
    db = mock_db(None)
    with pytest.raises(LookupError):
        ForeignAlertService.set_disposition(db, 1, disposition_status="resolved", note=None, user_id=5)


def test_service_note_provided():
    alert = make_alert(disposition_status="processing", note="old")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="resolved", note="new note", user_id=5)
    assert alert.disposition_note == "new note"
    action = db.add.call_args.args[0]
    assert isinstance(action, ForeignAlertDispositionAction)
    assert action.note == "new note"


def test_service_note_empty_clears():
    alert = make_alert(note="old note")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="resolved", note="", user_id=5)
    assert alert.disposition_note == ""
    action = db.add.call_args.args[0]
    assert action.note == ""


def test_service_note_omitted_keeps_old():
    alert = make_alert(disposition_status="processing", note="keep me")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="resolved", note=None, user_id=5)
    assert alert.disposition_note == "keep me"
    action = db.add.call_args.args[0]
    assert action.note == "keep me"


def test_service_audit_row():
    alert = make_alert(status="acknowledged", disposition_status="processing")
    db = mock_db(alert)
    ForeignAlertService.set_disposition(db, 1, disposition_status="ignored", note="x", user_id=7)
    action = db.add.call_args.args[0]
    assert isinstance(action, ForeignAlertDispositionAction)
    assert action.foreign_alert_id == 1
    assert action.previous_disposition == "processing"
    assert action.new_disposition == "ignored"
    assert action.actor_id == 7
    assert action.metadata_json["previous_lifecycle_status"] == "acknowledged"
    assert action.metadata_json["new_lifecycle_status"] == "suppressed"


def test_service_atomic_failure_no_half_write():
    alert = make_alert(status="triggered", disposition_status="pending")
    db = mock_db(alert)
    db.commit.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        ForeignAlertService.set_disposition(db, 1, disposition_status="resolved", note="x", user_id=5)
    # Transaction was rolled back, discarding the staged disposition action.
    db.rollback.assert_called()
    assert db.add.called


# B. API
def _call_handle(monkeypatch, alert, perms, json_body):
    fa = patch_api(monkeypatch, perms)
    db = mock_db(alert)
    req = MagicMock()
    user = MagicMock()
    user.id = 99
    return fa.handle_foreign_alert(1, fa.ForeignAlertHandlePayload(**json_body), req, db, user), db


def test_api_new_disposition_status(monkeypatch):
    alert = make_alert(status="triggered", disposition_status="pending")
    resp, _ = _call_handle(monkeypatch, alert, ["*"], {"disposition_status": "resolved", "note": "done"})
    assert resp["disposition_status"] == "resolved"
    assert resp["status"] == "resolved"
    assert resp["disposition_note"] == "done"


def test_api_pending(monkeypatch):
    alert = make_alert()
    resp, _ = _call_handle(monkeypatch, alert, ["*"], {"disposition_status": "pending"})
    assert resp["disposition_status"] == "pending"
    assert resp["status"] == "triggered"


def test_api_false_positive_with_perm(monkeypatch):
    alert = make_alert()
    resp, _ = _call_handle(monkeypatch, alert, ["foreign:alerts:false_positive"], {"disposition_status": "false_positive", "note": "fp"})
    assert resp["disposition_status"] == "false_positive"
    assert resp["status"] == "suppressed"


def test_api_false_positive_no_perm(monkeypatch):
    alert = make_alert()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _call_handle(monkeypatch, alert, [], {"disposition_status": "false_positive"})
    assert exc.value.status_code == 403


def test_api_legacy_acknowledged(monkeypatch):
    alert = make_alert()
    resp, _ = _call_handle(monkeypatch, alert, ["*"], {"status": "acknowledged"})
    assert resp["disposition_status"] == "processing"
    assert resp["status"] == "acknowledged"


def test_api_legacy_resolved(monkeypatch):
    alert = make_alert()
    resp, _ = _call_handle(monkeypatch, alert, ["*"], {"status": "resolved"})
    assert resp["disposition_status"] == "resolved"


def test_api_legacy_suppressed(monkeypatch):
    alert = make_alert()
    resp, _ = _call_handle(monkeypatch, alert, ["*"], {"status": "suppressed"})
    assert resp["disposition_status"] == "ignored"


def test_api_both_consistent(monkeypatch):
    alert = make_alert()
    resp, _ = _call_handle(monkeypatch, alert, ["*"], {"disposition_status": "resolved", "status": "resolved"})
    assert resp["disposition_status"] == "resolved"


def test_api_both_conflict(monkeypatch):
    alert = make_alert()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _call_handle(monkeypatch, alert, ["*"], {"disposition_status": "resolved", "status": "suppressed"})
    assert exc.value.status_code == 409


def test_api_illegal_disposition_422(monkeypatch):
    alert = make_alert()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _call_handle(monkeypatch, alert, ["*"], {"disposition_status": "bogus"})
    assert exc.value.status_code == 422


def test_api_failed_chinese_409(monkeypatch):
    alert = make_alert(status="failed", disposition_status="pending")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _call_handle(monkeypatch, alert, ["*"], {"disposition_status": "resolved"})
    assert exc.value.status_code == 409
    assert isinstance(exc.value.detail, str) and len(exc.value.detail) > 0


def _call_list(monkeypatch, alerts, perms, **params):
    fa = patch_api(monkeypatch, perms)
    db = MagicMock()
    db.scalar.return_value = len(alerts)
    captured = {}

    def _scalars(stmt):
        captured["stmt"] = stmt
        res = MagicMock()
        res.all.return_value = list(alerts)
        return res

    db.scalars.side_effect = _scalars
    user = MagicMock()
    # Pass every Query-defaulted parameter explicitly: when a FastAPI route
    # function is invoked directly (not through the router) the `Query(...)`
    # wrappers are truthy and would wrongly trigger the status_filter 422.
    out = fa.list_foreign_alerts(
        page=1,
        size=20,
        status_filter=None,
        disposition_status_filter=params.get("disposition_status_filter"),
        disposition_filter=params.get("disposition_filter", "hide_fp"),
        severity=None,
        rule_id=None,
        source=None,
        foreign_event_id=None,
        foreign_opinion_id=None,
        triggered_from=None,
        triggered_to=None,
        db=db,
        _=user,
    )
    from sqlalchemy.dialects import postgresql

    sql = str(
        captured["stmt"].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    return out, sql


def test_api_list_returns_fields(monkeypatch):
    alert = make_alert(disposition_status="pending", note="hi")
    out, _ = _call_list(monkeypatch, [alert], ["*"])
    item = out["items"][0]
    assert "status" in item
    assert item["disposition_status"] == "pending"
    assert item["disposition_note"] == "hi"


def test_api_list_default_hide_fp(monkeypatch):
    fp = make_alert(alert_id=2, status="suppressed", disposition_status="false_positive")
    ignored = make_alert(alert_id=3, status="suppressed", disposition_status="ignored")
    _, sql = _call_list(monkeypatch, [fp, ignored], ["*"])
    # Default behaviour: false_positive excluded at the SQL layer, ignored kept.
    assert "disposition_status" in sql
    assert "false_positive" in sql
    assert ("!=" in sql) or ("<>" in sql)
    assert "disposition_status = 'false_positive'" not in sql


def test_api_list_all(monkeypatch):
    fp = make_alert(alert_id=2, status="suppressed", disposition_status="false_positive")
    ignored = make_alert(alert_id=3, status="suppressed", disposition_status="ignored")
    _, sql = _call_list(monkeypatch, [fp, ignored], ["*"], disposition_filter="all")
    assert "false_positive" not in sql


def test_api_list_only_fp(monkeypatch):
    fp = make_alert(alert_id=2, status="suppressed", disposition_status="false_positive")
    ignored = make_alert(alert_id=3, status="suppressed", disposition_status="ignored")
    _, sql = _call_list(monkeypatch, [fp, ignored], ["*"], disposition_filter="only_fp")
    assert "= 'false_positive'" in sql


def test_api_list_disposition_status_filter(monkeypatch):
    fp = make_alert(alert_id=2, status="suppressed", disposition_status="false_positive")
    ignored = make_alert(alert_id=3, status="suppressed", disposition_status="ignored")
    resolved = make_alert(alert_id=4, status="resolved", disposition_status="resolved")
    _, sql = _call_list(
        monkeypatch, [fp, ignored, resolved], ["*"], disposition_status_filter="ignored"
    )
    assert "= 'ignored'" in sql


def test_api_status_not_disposition_enum(monkeypatch):
    alert = make_alert(status="triggered", disposition_status="pending")
    resp, _ = _call_handle(monkeypatch, alert, ["*"], {"disposition_status": "false_positive"})
    # status becomes the lifecycle 'suppressed', NOT the disposition enum
    assert resp["status"] == "suppressed"
    assert resp["status"] != "false_positive"


# C. Regression
def test_regression_transition_matrix_unchanged():
    alert = make_alert(status="resolved", disposition_status="resolved")
    db = mock_db(alert)
    with pytest.raises(ValueError):
        ForeignAlertService.transition(db, 1, action_type="acknowledge", note="x", user_id=5)


def test_regression_domestic_untouched():
    import app.api.alerts as alerts_mod
    from app.api.alerts import handle_record

    assert callable(handle_record)
    # Phase 6：国内普通处置禁止流转矩阵已删除，不得再以该名称存在。
    assert not hasattr(alerts_mod, "_FORBIDDEN_DOMESTIC_TRANSITIONS")


def test_regression_domestic_allows_status_correction():
    """国内处置允许任意合法状态之间的纠正（含 resolved -> ignored 等此前被禁止的流转）。"""
    import app.api.alerts as alerts_mod
    from unittest.mock import patch

    class _Rec:
        status = "resolved"
        handled = False
        handle_note = ""
        id = 1
        rule_id = None
        rule_name = None
        risk_level = "high"
        formal_risk_score = None
        formal_risk_level = "high"
        opinion_id = None
        opinion_title = None
        event_id = None
        event_title = None
        trigger_reason = None
        handled_by = None
        handled_by_name = None
        handled_at = None
        confirmation_source = None
        evaluation_source = None
        confirmation_version = None
        rule_risk_snapshot = {}
        ai_risk_snapshot = {}
        review_reason = None
        confirmed_by = None
        confirmed_at = None
        origin_review_id = None
        origin_ai_result_id = None
        deduplication_key = None
        created_at = None
        opinion = None

    rec = _Rec()
    db = MagicMock()
    db.get.return_value = rec
    user = MagicMock()
    user.id = 42
    req = alerts_mod.AlertHandleRequest(status="ignored", note="纠正测试")
    with patch.object(alerts_mod, "audit_write") as aw:
        aw.return_value.__enter__.return_value = {}
        aw.return_value.__exit__.return_value = False
        resp = alerts_mod.handle_record(1, MagicMock(), req, user, db)
    assert resp["status"] == "ignored"
    assert resp["handle_note"] == "纠正测试"


def test_regression_no_foreign_forbidden_matrix():
    import app.api.foreign_alerts as fa
    import app.services.foreign_alert_service as fs
    import inspect

    assert "FORBIDDEN_DISPOSITION_MATRIX" not in inspect.getsource(fa)
    assert "FORBIDDEN_DISPOSITION_MATRIX" not in inspect.getsource(fs)


def test_regression_ai_preview_readonly_intact():
    import app.api.foreign as fm

    assert hasattr(fm, "_preview_foreign_event_candidate_count")
    assert hasattr(fm, "_foreign_ai_batch_preview")
