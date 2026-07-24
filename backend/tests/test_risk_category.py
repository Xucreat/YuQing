"""Phase 2-B.2 风险分类测试。

覆盖：
1-4. 分类正确性（safety_accident / social_security / political / other）
5.   多分类命中取 severity 总分最高者
6-7. 评分不变量（severity_score/final_risk_score/event_state 与 Phase 2-A.1 一致）
8.   RiskEngine 输出 → Opinion 保存 → API 返回 risk_category 一致性
"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.alert import AlertRule, AlertRecord
from app.models.opinion import Opinion
from app.services.alert_service import AlertService
from app.services.risk_engine import (
    RiskEngine, RISK_MODEL_VERSION, CATEGORY_OTHER,
)


def _ref(title, content, sentiment="negative"):
    return RiskEngine().refine(title, content, sentiment)


# ---------------------------------------------------------------------------
# 1. safety_accident
# ---------------------------------------------------------------------------
def test_1_safety_accident():
    r = _ref("燃气爆炸事故", "发生爆炸，造成人员伤亡", "negative")
    assert r.risk_category == "safety_accident"
    assert r.severity_score == 100  # 爆炸90+伤亡90=180→cap100


# ---------------------------------------------------------------------------
# 2. social_security
# ---------------------------------------------------------------------------
def test_2_social_security():
    r = _ref("社区冲突事件", "发生冲突，涉嫌诈骗", "negative")
    assert r.risk_category == "social_security"
    assert r.severity_score == 100  # 冲突50+诈骗50=100


# ---------------------------------------------------------------------------
# 3. political
# ---------------------------------------------------------------------------
def test_3_political():
    r = _ref("群众上访反映腐败", "上访群众反映贪污腐败问题", "negative")
    assert r.risk_category == "political"
    assert r.severity_score == 100  # 上访50+腐败50+贪污50=150→cap100


# ---------------------------------------------------------------------------
# 4. other（仅语境词，无危害词）
# ---------------------------------------------------------------------------
def test_4_other_no_harm_words():
    r = _ref("群众投诉维权", "业主投诉物业服务差", "negative")
    assert r.risk_category == "other"
    assert r.severity_score == 0


# ---------------------------------------------------------------------------
# 5. 多分类命中：取 severity 总分最高者
# ---------------------------------------------------------------------------
def test_5_multi_category_highest_severity_wins():
    # 爆炸(safety_accident, 90) + 上访(political, 50) → safety_accident
    r = _ref("爆炸事故引发群众上访", "发生爆炸，群众上访", "negative")
    assert r.risk_category == "safety_accident"
    # 爆炸(90) + 上访(50) = 140 → cap 100
    assert r.severity_score == 100


# ---------------------------------------------------------------------------
# 6. 评分不变量：severity_score / final_risk_score / event_state 与 Phase 2-A.1 一致
# ---------------------------------------------------------------------------
def test_6_scoring_invariant_severity_and_final():
    # 与 test_risk_engine.py::test_severity_caps_at_100 同输入
    r = _ref("化工厂爆炸致多人伤亡", "化工厂发生爆炸，造成多人伤亡", "negative")
    assert r.severity_score == 100
    assert r.final_risk_score == 100
    assert r.event_state == "occurred"
    assert r.risk_category == "safety_accident"  # 新增字段，不影响评分


def test_7_scoring_invariant_floor_and_positive():
    # 与 test_risk_engine.py::test_severity_floor_keeps_major_event_high_when_resolved_and_positive 同输入
    r = _ref(
        "化工厂爆炸致多人伤亡，救援已妥善解决",
        "事故处置圆满，整改完成",
        "positive",
    )
    assert r.severity_score == 100
    assert r.final_risk_score == 70  # Floor 保底
    assert r.risk_category == "safety_accident"


# ---------------------------------------------------------------------------
# 8. 一致性：RiskEngine 输出 → Opinion 保存 → API 返回 risk_category
# ---------------------------------------------------------------------------
def test_8_risk_category_consistency_engine_to_api(client: TestClient, auth_headers: dict, seeded_region_id):
    db = SessionLocal()
    rule_ids, opinion_ids = [], []
    try:
        rule = AlertRule(
            name=f"p2b2-cat-{uuid.uuid4().hex[:8]}",
            risk_threshold=70, keywords="爆炸", risk_level="high", enabled=True,
        )
        db.add(rule)
        db.flush()
        rule_ids.append(rule.id)

        # 用 RiskEngine 生成风险字段（模拟 collector 路径）
        engine = RiskEngine()
        refine = engine.refine("燃气爆炸事故", "发生爆炸，造成人员伤亡", "negative")
        op = Opinion(
            title="燃气爆炸事故", content="发生爆炸，造成人员伤亡",
            source="p2b2测试", url=f"https://example.com/t/{uuid.uuid4()}",
            region_id=seeded_region_id, risk_score=refine.final_risk_score,
            sentiment="negative", summary="", keywords="爆炸",
            severity_score=refine.severity_score, event_state=refine.event_state,
            resolution_flag=refine.resolution_flag,
            risk_factors=refine.risk_factors,
            risk_model_version=RISK_MODEL_VERSION,
            risk_category=refine.risk_category,
        )
        db.add(op)
        db.commit()
        opinion_ids.append(op.id)

        # API 返回应包含 risk_category
        resp = client.get(f"/api/opinions/{op.id}", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["risk_category"] == "safety_accident"
        assert body["severity_score"] == 100
        assert body["risk_model_version"] == "risk-v2.0"
    finally:
        if opinion_ids:
            db.query(AlertRecord).filter(AlertRecord.opinion_id.in_(opinion_ids)).delete(synchronize_session=False)
        if rule_ids:
            db.query(AlertRecord).filter(AlertRecord.rule_id.in_(rule_ids)).delete(synchronize_session=False)
            db.query(AlertRule).filter(AlertRule.id.in_(rule_ids)).delete(synchronize_session=False)
        if opinion_ids:
            db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()
