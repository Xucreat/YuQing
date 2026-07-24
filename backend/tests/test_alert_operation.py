"""Phase 2-B.1 告警处置闭环测试。

覆盖：
1. 新告警默认 status=pending
2. 旧 API（无 body）handle → status=resolved, handled=True
3. 带 body（processing）→ handled_by/handled_at/handle_note 正确
4. viewer 无 alerts:write 权限 → 403
5. audit: HANDLE_ALERT 记录存在
6. 风险不变量：evaluate 的 risk_level/trigger_reason/critical 判断与实施前一致

所有用例在测试库（opinion_test）上自清理，不污染其它数据。
"""
import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.alert import AlertRule, AlertRecord
from app.models.audit import OperationLog
from app.models.opinion import Opinion
from app.services.alert_service import AlertService


# ---------------------------------------------------------------------------
# helpers（与 test_phase1_risk_model 同模式，自清理）
# ---------------------------------------------------------------------------
def _mk_opinion(db, region_id, title, content, sentiment, risk_score, keywords="", severity_score=0):
    op = Opinion(
        title=title, content=content, source="phase2b1测试",
        url=f"https://example.com/t/{uuid.uuid4()}",
        region_id=region_id, risk_score=risk_score, sentiment=sentiment,
        summary="", keywords=keywords, severity_score=severity_score,
    )
    db.add(op)
    db.flush()
    return op


def _mk_rule(db, name, threshold, keywords, risk_level="high"):
    rule = AlertRule(
        name=name, risk_threshold=threshold, keywords=keywords,
        risk_level=risk_level, enabled=True,
    )
    db.add(rule)
    db.flush()
    return rule


def _cleanup(db, rule_ids, opinion_ids):
    if opinion_ids:
        db.query(AlertRecord).filter(AlertRecord.opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
    if rule_ids:
        db.query(AlertRecord).filter(AlertRecord.rule_id.in_(rule_ids)).delete(synchronize_session=False)
        db.query(AlertRule).filter(AlertRule.id.in_(rule_ids)).delete(synchronize_session=False)
    if opinion_ids:
        db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).delete(synchronize_session=False)
    db.commit()


def _seed_alert(db, region_id):
    """创建 opinion + rule，跑 evaluate 生成 AlertRecord，返回 (rule_id, opinion_id, record_id)。"""
    rule = _mk_rule(db, f"p2b1-{uuid.uuid4().hex[:8]}", 70, "爆炸")
    op = _mk_opinion(db, region_id,
                     "燃气爆炸事故",
                     "发生燃气爆炸，造成人员伤亡",
                     "negative", 90, keywords="爆炸", severity_score=90)
    db.commit()
    AlertService.evaluate(db)
    rec = db.query(AlertRecord).filter(
        AlertRecord.rule_id == rule.id, AlertRecord.opinion_id == op.id
    ).first()
    assert rec is not None, "evaluate 未生成告警"
    return rule.id, op.id, rec.id


# ---------------------------------------------------------------------------
# 1. 新告警默认 status=pending
# ---------------------------------------------------------------------------
def test_1_new_alert_status_pending(seeded_region_id):
    db = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        rule = _mk_rule(db, f"p2b1-pending-{uuid.uuid4().hex[:8]}", 70, "爆炸")
        op = _mk_opinion(db, seeded_region_id,
                         "燃气爆炸事故",
                         "发生燃气爆炸，造成人员伤亡",
                         "negative", 90, keywords="爆炸", severity_score=90)
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        rec = db.query(AlertRecord).filter(
            AlertRecord.rule_id == rule.id, AlertRecord.opinion_id == op.id
        ).first()
        assert rec is not None
        assert rec.status == "pending", f"expected pending, got {rec.status}"
        assert rec.handled is False
        assert rec.handled_by is None
        assert rec.handled_at is None
        assert rec.handle_note is None
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 2. 旧 API（无 body）handle → status=resolved, handled=True
# ---------------------------------------------------------------------------
def test_2_legacy_handle_no_body(client: TestClient, auth_headers: dict, seeded_region_id):
    db = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        rule_id, op_id, rec_id = _seed_alert(db, seeded_region_id)
        rule_ids.append(rule_id)
        opinion_ids.append(op_id)

        resp = client.put(f"/api/alerts/records/{rec_id}/handle", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["handled"] is True
        assert body["handled_by"] is not None
        assert body["handled_at"] is not None
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 3. 带 body（processing）→ handled_by/handled_at/handle_note 正确
# ---------------------------------------------------------------------------
def test_3_handle_with_body_processing(client: TestClient, auth_headers: dict, seeded_region_id):
    db = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        rule_id, op_id, rec_id = _seed_alert(db, seeded_region_id)
        rule_ids.append(rule_id)
        opinion_ids.append(op_id)

        resp = client.put(
            f"/api/alerts/records/{rec_id}/handle",
            json={"status": "processing", "note": "已派专人跟进"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "processing"
        # processing 不在 {resolved,ignored,false_positive} → handled=False
        assert body["handled"] is False
        assert body["handled_by"] is not None
        assert body["handled_at"] is not None
        assert body["handle_note"] == "已派专人跟进"
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 4. viewer 无 alerts:write 权限 → 403
# ---------------------------------------------------------------------------
def test_4_viewer_forbidden(client: TestClient, auth_headers: dict, seeded_region_id):
    db = SessionLocal()
    rule_ids, opinion_ids = [], []
    viewer_uid = None
    vu_username = f"p2b1_viewer_{uuid.uuid4().hex[:6]}"
    try:
        rule_id, op_id, rec_id = _seed_alert(db, seeded_region_id)
        rule_ids.append(rule_id)
        opinion_ids.append(op_id)

        vu = client.post("/api/users", json={
            "username": vu_username, "password": "Passw0rd1", "role": "viewer",
        }, headers=auth_headers)
        assert vu.status_code == 201, vu.text
        viewer_uid = vu.json()["id"]

        lr = client.post("/api/login", json={
            "username": vu_username, "password": "Passw0rd1",
        })
        assert lr.status_code == 200, lr.text
        viewer_headers = {"Authorization": f"Bearer {lr.json()['access_token']}"}

        resp = client.put(f"/api/alerts/records/{rec_id}/handle", headers=viewer_headers)
        assert resp.status_code == 403, f"expected 403, got {resp.status_code}: {resp.text}"
    finally:
        if viewer_uid:
            client.delete(f"/api/users/{viewer_uid}", headers=auth_headers)
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 5. audit: HANDLE_ALERT 记录存在
# ---------------------------------------------------------------------------
def test_5_audit_handle_alert_exists(client: TestClient, auth_headers: dict, seeded_region_id):
    db = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        rule_id, op_id, rec_id = _seed_alert(db, seeded_region_id)
        rule_ids.append(rule_id)
        opinion_ids.append(op_id)

        resp = client.put(
            f"/api/alerts/records/{rec_id}/handle",
            json={"status": "resolved", "note": "审计验证"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text

        logs = db.query(OperationLog).filter(
            OperationLog.action == "HANDLE_ALERT",
            OperationLog.resource_type == "alert_record",
            OperationLog.resource_id == str(rec_id),
        ).all()
        assert len(logs) >= 1, "未找到 HANDLE_ALERT 审计记录"
        log = logs[-1]
        assert log.result == "success"
        details = json.loads(log.details_json) if log.details_json else {}
        assert details.get("new_status") == "resolved"
        assert details.get("note") == "审计验证"
        assert details.get("old_status") == "pending"
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()


# ---------------------------------------------------------------------------
# 6. 风险不变量：evaluate 的 risk_level/trigger_reason/critical 判断不变
# ---------------------------------------------------------------------------
def test_6_risk_invariant_unchanged(seeded_region_id):
    """验证 evaluate 产出的 risk_level/trigger_reason/critical 判断与 Phase 2-A.1 一致。

    场景：severity_score=90(>=70) → critical；trigger_reason 含 severity_score=90 + factors。
    Phase 2-B.1 仅加 status='pending'，不改任何风险判定逻辑。
    """
    db = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        rule = _mk_rule(db, f"p2b1-invariant-{uuid.uuid4().hex[:8]}", 70, "爆炸")
        op = _mk_opinion(db, seeded_region_id,
                         "燃气爆炸事故",
                         "发生燃气爆炸，造成人员伤亡",
                         "negative", 90, keywords="爆炸", severity_score=90)
        # 模拟 collector 写回的 risk_factors（Phase 2-A.1）
        op.risk_factors = {
            "severity": [{"keyword": "爆炸", "score": 90}, {"keyword": "伤亡", "score": 90}],
            "event_state": "occurred",
            "resolution_flag": False,
        }
        op.risk_model_version = "risk-v2.0"
        db.commit()
        rule_ids.append(rule.id)
        opinion_ids.append(op.id)

        AlertService.evaluate(db)
        rec = db.query(AlertRecord).filter(
            AlertRecord.rule_id == rule.id, AlertRecord.opinion_id == op.id
        ).first()
        assert rec is not None

        # 风险等级 = critical（severity_score=90 >= 70）
        assert rec.risk_level == "critical", f"expected critical, got {rec.risk_level}"
        # trigger_reason 含 severity_score=90 + factors=[爆炸,伤亡] + event_state=occurred
        assert "severity_score=90" in rec.trigger_reason
        assert "factors=[爆炸,伤亡]" in rec.trigger_reason
        assert "event_state=occurred" in rec.trigger_reason
        # Phase 2-B.1 新增：status=pending，但不影响风险判定
        assert rec.status == "pending"
    finally:
        _cleanup(db, rule_ids, opinion_ids)
        db.close()
