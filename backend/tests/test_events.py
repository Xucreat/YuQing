"""Phase 3C-0 自测：EventAggregator + Events API。

使用真实 PostgreSQL 测试库（opinion_test@127.0.0.1:5433）。
覆盖验收：
1. Event ORM 可正常创建并保存已有字段
2. 两个同 keyword Opinion → aggregate 产生 1 个 Event
3. 不同 keyword Opinion → aggregate 产生 2 个 Event
4. 多个 Opinion 正确关联到同一 Event（经 event_opinions 表验证）
5. risk_level 取最高值映射正确（>=70→high, >=40→medium, else→low）
6. 重复执行 aggregate 幂等（不重复创建 Event / 不重复添加关联）
7. POST /api/events/aggregate 返回正确格式
8. GET /api/events 分页正常

约束遵守：
- 不修改 Opinion/Collector/AIService/Dashboard/已有 migration
- EventOpinion 关联经显式 EventOpinion(event_id, opinion_id) 创建
- Event.status 不存在（仅 API Schema 层固定 active）
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.event.aggregator import EventAggregator

EVT_SOURCE = "evt_test"


@pytest.fixture
def clean_events():
    """清空 events / event_opinions / 本测试产生的 opinions，保证隔离。"""
    db = SessionLocal()
    try:
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).filter(Opinion.source == EVT_SOURCE).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).filter(Opinion.source == EVT_SOURCE).delete()
        db.commit()
    finally:
        db.close()


def _make_opinion(db, region_id, title, keywords, risk_score, content="content"):
    """插入一条已完成、带关键词的 Opinion（位于聚合窗口内）。"""
    op = Opinion(
        title=title,
        content=content,
        source=EVT_SOURCE,
        url=f"https://example.com/{uuid.uuid4().hex}",
        region_id=region_id,
        risk_score=risk_score,
        sentiment="neutral",
        summary="",
        keywords=keywords,
        analysis_status="completed",
        created_at=datetime.now(timezone.utc),
    )
    db.add(op)
    db.flush()
    return op


# ---------------------------------------------------------------------------
# 1) Event ORM 可以正常创建并保存已有字段
# ---------------------------------------------------------------------------
def test_event_orm_persist(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        ev = Event(
            title="测试事件",
            description="描述文本",
            keyword="a,b",
            risk_level="high",
            opinion_count=3,
            first_time=datetime.now(timezone.utc),
            last_time=datetime.now(timezone.utc),
        )
        db.add(ev)
        db.commit()
        got = db.get(Event, ev.id)
        assert got is not None
        assert got.title == "测试事件"
        assert got.keyword == "a,b"
        assert got.risk_level == "high"
        assert got.opinion_count == 3
        # Event Model 无 status 列（status 仅 API 层）
        assert not hasattr(got, "status")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2) 两个同 keyword Opinion → aggregate 产生 1 个 Event
# ---------------------------------------------------------------------------
def test_same_keyword_one_event(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        # "a,b" 与 "b,c" 在关键词 b 上相交 -> 同一事件
        _make_opinion(db, seeded_region_id, "T1", "a,b", 10)
        _make_opinion(db, seeded_region_id, "T2", "b,c", 20)
        db.commit()

        res = EventAggregator().aggregate(db)
        assert res["created"] == 1, res
        assert res["linked"] == 2, res
        assert db.query(Event).count() == 1
        assert db.query(EventOpinion).count() == 2

        ev = db.query(Event).first()
        assert ev.opinion_count == 2
        # 最高 risk=20 -> low
        assert ev.risk_level == "low", ev.risk_level
        # 标题取最高 risk Opinion（T2, risk=20）
        assert ev.title == "T2"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3) 不同 keyword Opinion → aggregate 产生 2 个 Event
# ---------------------------------------------------------------------------
def test_diff_keyword_two_events(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        _make_opinion(db, seeded_region_id, "T1", "a,b", 10)
        _make_opinion(db, seeded_region_id, "T2", "x,y", 20)
        db.commit()

        res = EventAggregator().aggregate(db)
        assert res["created"] == 2, res
        assert res["linked"] == 2, res
        assert db.query(Event).count() == 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4) 多个 Opinion 正确关联到同一 Event（经 event_opinions 表验证）
# ---------------------------------------------------------------------------
def test_multiple_linked_same_event(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        for i in range(3):
            _make_opinion(db, seeded_region_id, f"T{i}", "k1,k2", 30 + i)
        db.commit()

        res = EventAggregator().aggregate(db)
        assert res["created"] == 1, res
        assert res["linked"] == 3, res

        ev = db.query(Event).first()
        assert ev is not None
        # 经关联表验证：3 条 Opinion 均挂到同一 Event
        n = (
            db.query(EventOpinion)
            .filter(EventOpinion.event_id == ev.id)
            .count()
        )
        assert n == 3, n
        assert ev.opinion_count == 3
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5) risk_level 取最高值映射正确
# ---------------------------------------------------------------------------
def test_risk_level_mapping(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        _make_opinion(db, seeded_region_id, "high", "kh", 75)
        _make_opinion(db, seeded_region_id, "med", "km", 50)
        _make_opinion(db, seeded_region_id, "low", "kl", 10)
        db.commit()

        res = EventAggregator().aggregate(db)
        assert res["created"] == 3, res

        levels = {e.keyword: e.risk_level for e in db.query(Event).all()}
        assert levels["kh"] == "high", levels
        assert levels["km"] == "medium", levels
        assert levels["kl"] == "low", levels
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6) 重复执行 aggregate 幂等
# ---------------------------------------------------------------------------
def test_idempotent_rerun(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        _make_opinion(db, seeded_region_id, "T1", "a,b", 10)
        _make_opinion(db, seeded_region_id, "T2", "b,c", 20)
        db.commit()

        r1 = EventAggregator().aggregate(db)
        assert r1["created"] == 1, r1
        assert r1["linked"] == 2, r1

        # 重复执行：不重复创建 Event、不重复添加关联
        r2 = EventAggregator().aggregate(db)
        assert r2["created"] == 0, r2
        assert r2["updated"] == 0, r2
        assert r2["linked"] == 0, r2

        assert db.query(Event).count() == 1
        assert db.query(EventOpinion).count() == 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 7) POST /api/events/aggregate 返回正确格式
# ---------------------------------------------------------------------------
def test_api_aggregate(
    clean_events, client: TestClient, auth_headers, seeded_region_id
) -> None:
    db: Session = SessionLocal()
    try:
        _make_opinion(db, seeded_region_id, "T1", "a,b", 10)
        _make_opinion(db, seeded_region_id, "T2", "b,c", 20)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/events/aggregate", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert "created" in body and "updated" in body and "linked" in body
    assert isinstance(body["created"], int)
    # 至少聚合出本测试注入的 2 条（忽略其它库内已完成数据）
    assert body["created"] >= 1, body
    assert body["linked"] >= 2, body

    db = SessionLocal()
    try:
        assert db.query(Event).count() >= 1
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 8) GET /api/events 分页正常
# ---------------------------------------------------------------------------
def test_api_list_pagination(
    clean_events, client: TestClient, auth_headers, seeded_region_id
) -> None:
    db: Session = SessionLocal()
    try:
        # 4 条互不相交的关键词 -> 4 个独立 Event
        for i in range(4):
            _make_opinion(db, seeded_region_id, f"T{i}", f"kw{i}", 30 + i)
        db.commit()
    finally:
        db.close()

    # 先聚合，确保 Event 已生成
    agg = client.post("/api/events/aggregate", headers=auth_headers)
    assert agg.status_code == 200, agg.text

    resp = client.get("/api/events?page=1&size=2", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body and "total" in body
    assert body["page"] == 1
    assert body["size"] == 2
    assert body["total"] >= 4, body
    assert len(body["items"]) <= 2

    # 每个 Event 必须含固定 status=active（仅 API 层）
    for it in body["items"]:
        assert it["status"] == "active"
        assert "id" in it and "title" in it and "risk_level" in it
        assert "opinion_count" in it

    # id DESC 排序
    if len(body["items"]) >= 2:
        assert body["items"][0]["id"] >= body["items"][1]["id"]
