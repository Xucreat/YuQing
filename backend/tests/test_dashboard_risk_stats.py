"""Phase 2-B.2 Dashboard 风险统计接口测试。

覆盖：
1. /api/dashboard/risk-distribution 返回 risk_levels/event_states/risk_categories
2. /api/dashboard/alert-stats 返回 total_alerts/by_status/handling_rate/mttr_hours
3. 历史 NULL risk_category 归入 other
"""
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.alert import AlertRule, AlertRecord
from app.models.opinion import Opinion


def _mk_opinion(db, region_id, risk_score=50, event_state="occurred", risk_category=None):
    op = Opinion(
        title=f"test-{uuid.uuid4().hex[:6]}", content="test", source="test",
        url=f"https://example.com/t/{uuid.uuid4()}",
        region_id=region_id, risk_score=risk_score, sentiment="neutral",
        summary="", keywords="", event_state=event_state, risk_category=risk_category,
    )
    db.add(op)
    db.flush()
    return op


def test_1_risk_distribution_structure(client: TestClient, auth_headers: dict, seeded_region_id):
    db = SessionLocal()
    opinion_ids = []
    try:
        op = _mk_opinion(db, seeded_region_id, risk_score=85, event_state="occurred", risk_category="safety_accident")
        db.commit()
        opinion_ids.append(op.id)

        resp = client.get("/api/dashboard/risk-distribution?days=7", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "risk_levels" in body
        assert "event_states" in body
        assert "risk_categories" in body
        assert isinstance(body["risk_levels"], list)
        assert isinstance(body["event_states"], list)
        assert isinstance(body["risk_categories"], list)
        # 至少有我们插入的数据
        cats = {item["label"] for item in body["risk_categories"]}
        assert "safety_accident" in cats
    finally:
        if opinion_ids:
            db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_2_alert_stats_structure(client: TestClient, auth_headers: dict):
    resp = client.get("/api/dashboard/alert-stats?days=7", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "total_alerts" in body
    assert "by_status" in body
    assert "handling_rate" in body
    assert isinstance(body["total_alerts"], int)
    assert isinstance(body["by_status"], list)
    assert isinstance(body["handling_rate"], (int, float))


def test_3_null_risk_category_grouped_as_other(client: TestClient, auth_headers: dict, seeded_region_id):
    db = SessionLocal()
    opinion_ids = []
    try:
        # 插入一条 risk_category=NULL 的历史数据
        op = _mk_opinion(db, seeded_region_id, risk_score=30, event_state="occurred", risk_category=None)
        db.commit()
        opinion_ids.append(op.id)

        resp = client.get("/api/dashboard/risk-distribution?days=7", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        cats = {item["label"]: item["count"] for item in body["risk_categories"]}
        assert "other" in cats  # NULL 归入 other
    finally:
        if opinion_ids:
            db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()
