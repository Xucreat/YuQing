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
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.propagation import PropagationNode
from app.models.alert import AlertRecord
from app.services.event.aggregator import EventAggregator
from app.core import task_manager

EVT_SOURCE = "evt_test"


@pytest.fixture
def clean_events():
    """清空 events / event_opinions / 本测试产生的 opinions，保证隔离。"""
    def wait_for_background_tasks() -> None:
        # The aggregate endpoint is asynchronous.  Do not start FK cleanup
        # while its worker can still be inserting propagation nodes.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with task_manager._tasks_lock:
                running = any(
                    task.status in (task_manager.STATUS_PENDING, task_manager.STATUS_RUNNING)
                    for task in task_manager._tasks.values()
                )
            if not running:
                return
            time.sleep(0.05)

    db = SessionLocal()
    try:
        wait_for_background_tasks()
        # 先清理可能引用 events 的外键行（aggregate 会触发传播重建产生 propagation_nodes / alert_records）
        db.query(PropagationNode).delete()
        db.query(AlertRecord).filter(AlertRecord.event_id.isnot(None)).update(
            {"event_id": None, "event_title": ""}, synchronize_session=False
        )
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).filter(Opinion.source == EVT_SOURCE).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        wait_for_background_tasks()
        # 先清理可能引用 events 的外键行（aggregate 会触发传播重建产生 propagation_nodes / alert_records）
        db.query(PropagationNode).delete()
        db.query(AlertRecord).filter(AlertRecord.event_id.isnot(None)).update(
            {"event_id": None, "event_title": ""}, synchronize_session=False
        )
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).filter(Opinion.source == EVT_SOURCE).delete()
        db.commit()
    finally:
        db.close()


def _make_opinion(db, region_id, title, keywords, risk_score, content=None):
    """插入一条已完成、带关键词的 Opinion（位于聚合窗口内）。

    注意：content 默认按 title 派生为互异文本，避免「不同事件但正文完全相同」
    在引入文本相似度信号后被误合并（语义已变为「正文相同≈同一事件」）。
    需要验证「共享关键词即合并」的用例仍依赖关键词，不受正文影响。
    """
    op = Opinion(
        title=title,
        content=content if content is not None else f"内容-{uuid.uuid4().hex}：{title}",
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


# =========================================================================== #
# Phase 2-E-2：事件运营闭环后端增强测试                                         #
# 覆盖：source_count / statistics / alerts / 风险分布 / 状态机 / hot-topic / 权限 #
# =========================================================================== #
from app.core.security import hash_password  # noqa: E402
from app.models.alert import AlertRule, AlertRecord  # noqa: E402
from app.models.user import User  # noqa: E402

READONLY_USER = "evt_viewer_2e2"
TEST_SRC_PREFIX = "2e2_"


@pytest.fixture
def clean_2e2():
    """清空 2-E-2 测试产生的 events / event_opinions / opinions / alert_records。"""
    db = SessionLocal()
    try:
        db.query(PropagationNode).delete()
        db.query(AlertRecord).filter(
            AlertRecord.opinion_title.like(f"{TEST_SRC_PREFIX}%")
        ).delete(synchronize_session=False)
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).filter(Opinion.source.like(f"{TEST_SRC_PREFIX}%")).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.username == READONLY_USER).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(PropagationNode).delete()
        db.query(AlertRecord).filter(
            AlertRecord.opinion_title.like(f"{TEST_SRC_PREFIX}%")
        ).delete(synchronize_session=False)
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).filter(Opinion.source.like(f"{TEST_SRC_PREFIX}%")).delete(
            synchronize_session=False
        )
        db.query(User).filter(User.username == READONLY_USER).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def _make_event_with_opinions(
    db, region_id, *, title="2E2事件", topic_category="other", heat=50,
    status="active", opinions_spec=(),
):
    """opinions_spec: list of dict(title, source, risk_score, content)."""
    ev = Event(
        title=title,
        description="",
        keyword="2e2",
        risk_level="low",
        status=status,
        topic_category=topic_category,
        heat_score=heat,
        opinion_count=len(opinions_spec),
        first_time=datetime.now(timezone.utc),
        last_time=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.flush()
    for spec in opinions_spec:
        op = Opinion(
            title=spec.get("title", "t"),
            content=spec.get("content", f"c-{uuid.uuid4().hex}"),
            source=spec["source"],
            url=f"https://example.com/{uuid.uuid4().hex}",
            region_id=region_id,
            risk_score=spec.get("risk_score", 0),
            sentiment="neutral",
            summary="",
            keywords="",
            analysis_status="completed",
            created_at=datetime.now(timezone.utc),
        )
        db.add(op)
        db.flush()
        db.add(EventOpinion(event_id=ev.id, opinion_id=op.id))
    db.commit()
    return ev


def _make_alert(db, event, *, risk_level="high", opinion_title=None):
    rule = db.query(AlertRule).first()
    if rule is None:
        rule = AlertRule(name="2e2-rule", risk_threshold=70, risk_level="high", enabled=True)
        db.add(rule)
        db.flush()
    ar = AlertRecord(
        rule_id=rule.id,
        rule_name=rule.name,
        risk_level=risk_level,
        opinion_title=opinion_title or f"{TEST_SRC_PREFIX}alert-{uuid.uuid4().hex}",
        event_id=event.id,
        event_title=event.title,
        status="pending",
    )
    db.add(ar)
    db.commit()
    return ar


def _readonly_headers(client: TestClient) -> dict:
    """创建无任何权限的普通用户并登录（role=viewer 角色不存在 → 空权限集）。"""
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == READONLY_USER).delete(
            synchronize_session=False
        )
        db.add(
            User(
                username=READONLY_USER,
                password_hash=hash_password("viewer123"),
                role="viewer",
                is_active=True,
                is_superuser=False,
            )
        )
        db.commit()
    finally:
        db.close()
    resp = client.post(
        "/api/login", json={"username": READONLY_USER, "password": "viewer123"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# 1) 列表 source_count 字段存在且与 SQL 一致
# ---------------------------------------------------------------------------
def test_list_source_count(clean_2e2, client: TestClient, auth_headers, seeded_region_id):
    db = SessionLocal()
    try:
        _make_event_with_opinions(
            db, seeded_region_id,
            topic_category="education",
            opinions_spec=[
                {"source": f"{TEST_SRC_PREFIX}A", "risk_score": 10, "title": "s1"},
                {"source": f"{TEST_SRC_PREFIX}A", "risk_score": 20, "title": "s2"},
                {"source": f"{TEST_SRC_PREFIX}B", "risk_score": 30, "title": "s3"},
            ],
        )
    finally:
        db.close()

    resp = client.get("/api/events?size=100", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    mine = [it for it in items if it["title"] == "2E2事件"]
    assert mine, "测试事件未出现在列表"
    it = mine[0]
    assert "source_count" in it, it
    # 3 条舆情、2 个不同来源
    assert it["source_count"] == 2, it

    # 与直接 SQL 核对
    db = SessionLocal()
    try:
        from sqlalchemy import func as _f
        row = (
            db.query(_f.count(Opinion.source.distinct()))
            .join(EventOpinion, EventOpinion.opinion_id == Opinion.id)
            .filter(EventOpinion.event_id == it["id"])
            .one()
        )
        assert row[0] == 2, row
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2) 详情返回 statistics + alerts；无告警时 alerts=[]
# ---------------------------------------------------------------------------
def test_detail_statistics_and_alerts(clean_2e2, client: TestClient, auth_headers, seeded_region_id):
    db = SessionLocal()
    try:
        ev = _make_event_with_opinions(
            db, seeded_region_id,
            opinions_spec=[
                {"source": f"{TEST_SRC_PREFIX}A", "risk_score": 75, "title": "h"},
                {"source": f"{TEST_SRC_PREFIX}B", "risk_score": 50, "title": "m"},
                {"source": f"{TEST_SRC_PREFIX}C", "risk_score": 10, "title": "l"},
            ],
        )
        _make_alert(db, ev, risk_level="high", opinion_title=f"{TEST_SRC_PREFIX}alert-X")
        ev_id = ev.id
    finally:
        db.close()

    resp = client.get(f"/api/events/{ev_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "statistics" in body and body["statistics"] is not None, body
    st = body["statistics"]
    assert st["opinion_count"] == 3, st
    assert st["source_count"] == 3, st
    assert st["latest_time"] is not None, st
    assert st["risk_distribution"] == {"high": 1, "medium": 1, "low": 1}, st
    assert len(body["alerts"]) == 1, body["alerts"]
    al = body["alerts"][0]
    assert al["title"] == f"{TEST_SRC_PREFIX}alert-X", al
    assert al["risk_level"] == "high", al
    assert al["status"] == "pending", al


def test_detail_no_alert_returns_empty(clean_2e2, client: TestClient, auth_headers, seeded_region_id):
    db = SessionLocal()
    try:
        ev = _make_event_with_opinions(
            db, seeded_region_id,
            opinions_spec=[{"source": f"{TEST_SRC_PREFIX}A", "risk_score": 10}],
        )
        ev_id = ev.id
    finally:
        db.close()

    resp = client.get(f"/api/events/{ev_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["alerts"] == [], resp.json()


# ---------------------------------------------------------------------------
# 3) 风险分布 high/medium/low 正确（阈值 >=70 / >=40 / 其余）
# ---------------------------------------------------------------------------
def test_risk_distribution_buckets(clean_2e2, client: TestClient, auth_headers, seeded_region_id):
    db = SessionLocal()
    try:
        ev = _make_event_with_opinions(
            db, seeded_region_id,
            opinions_spec=[
                {"source": f"{TEST_SRC_PREFIX}A", "risk_score": 70, "title": "h1"},
                {"source": f"{TEST_SRC_PREFIX}B", "risk_score": 99, "title": "h2"},
                {"source": f"{TEST_SRC_PREFIX}C", "risk_score": 40, "title": "m1"},
                {"source": f"{TEST_SRC_PREFIX}D", "risk_score": 69, "title": "m2"},
                {"source": f"{TEST_SRC_PREFIX}E", "risk_score": 0, "title": "l1"},
                {"source": f"{TEST_SRC_PREFIX}F", "risk_score": 39, "title": "l2"},
            ],
        )
        ev_id = ev.id
    finally:
        db.close()

    resp = client.get(f"/api/events/{ev_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    rd = resp.json()["statistics"]["risk_distribution"]
    assert rd == {"high": 2, "medium": 2, "low": 2}, rd


# ---------------------------------------------------------------------------
# 4) 状态机：active→deprecated 成功；deprecated→active 保持；active→resolved 仍 409
# ---------------------------------------------------------------------------
def test_status_transitions(clean_2e2, client: TestClient, auth_headers, seeded_region_id):
    db = SessionLocal()
    try:
        ev = _make_event_with_opinions(
            db, seeded_region_id,
            status="active",
            opinions_spec=[{"source": f"{TEST_SRC_PREFIX}A", "risk_score": 10}],
        )
        ev_id = ev.id
    finally:
        db.close()

    # active -> deprecated（2-E-2 新增放行）
    r = client.patch(f"/api/events/{ev_id}/status", json={"status": "deprecated"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "deprecated", r.json()

    # deprecated -> active（恢复，既有逻辑）
    r = client.patch(f"/api/events/{ev_id}/status", json={"status": "active"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active", r.json()

    # active -> resolved（非法跳转，仍 409）
    r = client.patch(f"/api/events/{ev_id}/status", json={"status": "resolved"}, headers=auth_headers)
    assert r.status_code == 409, r.text


def test_status_verifying_processing_to_deprecated(
    clean_2e2, client: TestClient, auth_headers, seeded_region_id
):
    """verifying / processing 也可直接忽略。"""
    for src in ("verifying", "processing"):
        db = SessionLocal()
        try:
            ev = _make_event_with_opinions(
                db, seeded_region_id,
                status=src,
                opinions_spec=[{"source": f"{TEST_SRC_PREFIX}{src}", "risk_score": 10}],
            )
            ev_id = ev.id
        finally:
            db.close()
        r = client.patch(
            f"/api/events/{ev_id}/status", json={"status": "deprecated"}, headers=auth_headers
        )
        assert r.status_code == 200, (src, r.text)
        assert r.json()["status"] == "deprecated", (src, r.json())


# ---------------------------------------------------------------------------
# 5) hot-topic：education 精确 / 中文 ILIKE / 不存在返回 []
# ---------------------------------------------------------------------------
def test_hot_topic(clean_2e2, client: TestClient, auth_headers, seeded_region_id):
    db = SessionLocal()
    try:
        # 事件 A：topic_category=education（第一优先命中）
        _make_event_with_opinions(
            db, seeded_region_id,
            title="教育事件A",
            topic_category="education",
            heat=80,
            opinions_spec=[
                {"source": f"{TEST_SRC_PREFIX}A", "risk_score": 10, "title": "学校新闻",
                 "content": "某地教育政策"},
            ],
        )
        # 事件 B：topic_category=other，但舆情正文含「教育」（第二优先 ILIKE 命中）
        _make_event_with_opinions(
            db, seeded_region_id,
            title="普通事件B",
            topic_category="other",
            heat=30,
            opinions_spec=[
                {"source": f"{TEST_SRC_PREFIX}B", "risk_score": 10, "title": "x",
                 "content": "教育补课乱象"},
            ],
        )
    finally:
        db.close()

    # 第一优先：枚举值 education
    r = client.get("/api/events/hot-topic/education", headers=auth_headers)
    assert r.status_code == 200, r.text
    titles = [it["title"] for it in r.json()["items"]]
    assert "教育事件A" in titles, titles
    assert "普通事件B" not in titles, titles  # 仅 topic_category 精确命中

    # 第二优先：中文 教育（ILIKE，应同时命中 A、B）
    r = client.get("/api/events/hot-topic/%E6%95%99%E8%82%B2", headers=auth_headers)
    assert r.status_code == 200, r.text
    titles = [it["title"] for it in r.json()["items"]]
    assert "教育事件A" in titles, titles
    assert "普通事件B" in titles, titles

    # 不存在
    r = client.get("/api/events/hot-topic/zZzNotExist", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["items"] == [], r.json()
    assert r.json()["total"] == 0, r.json()


# ---------------------------------------------------------------------------
# 6) 权限：无 events:write 的用户修改状态 → 403
# ---------------------------------------------------------------------------
def test_status_change_requires_write(
    clean_2e2, client: TestClient, auth_headers, seeded_region_id
):
    db = SessionLocal()
    try:
        ev = _make_event_with_opinions(
            db, seeded_region_id,
            status="active",
            opinions_spec=[{"source": f"{TEST_SRC_PREFIX}A", "risk_score": 10}],
        )
        ev_id = ev.id
    finally:
        db.close()

    ro = _readonly_headers(client)
    r = client.patch(
        f"/api/events/{ev_id}/status", json={"status": "deprecated"}, headers=ro
    )
    assert r.status_code == 403, r.text

    # admin 仍可操作（回归）
    r = client.patch(
        f"/api/events/{ev_id}/status", json={"status": "deprecated"}, headers=auth_headers
    )
    assert r.status_code == 200, r.text
