"""Phase 4-Event-1 回归 / 新增测试：事件成员判定核心逻辑。

覆盖验收（相对 Phase 3C-0 旧并查集规则的反面约束）：
1. 两篇仅共享「事故」等通用词（文本不相似）→ 不应自动合并
2. A(事故,投诉) B(事故,投诉) C(投诉,维权) → 不得因链式传递全部并入同一 Event
3. 同 region 不同事件（不同通用词 + 文本不相似）→ 不应合并
4. 同一事件多篇高度相似舆情 → 应聚合为 1 个 Event
5. 不同时间段无关舆情（文本相似但时间超窗口）→ 不应合并
6. 空 keywords 的 Opinion → 不应被错误判定为同一事件；但高度相似的空关键词舆情应仍可经文本召回聚合
7. Event 重复运行 → 不产生重复 EventOpinion（幂等）
8. 现有 Event API contract 不发生破坏性变化

约束遵守：
- 不修改 Opinion/Event/EventOpinion Model、不改迁移、不改 API contract。
- 仅读取既有字段（region_id / created_at / publish_time / keywords / ai_keywords / title / content / risk_score）。
- 沿用 test_events.py 的 clean_events / seeded_region_id 隔离夹具（此处重定义以保证独立）。
"""
import uuid
from datetime import datetime, timedelta, timezone

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

SRC = "evt_v2"


@pytest.fixture
def clean_events():
    """清空 events / event_opinions / 本测试产生的 opinions，保证隔离。"""
    db = SessionLocal()
    try:
        # 先清理可能引用 events 的外键行（aggregate 会触发传播重建产生 propagation_nodes / alert_records）
        db.query(PropagationNode).delete()
        # AlertRecord 引用 opinion_id（FK），必须在删除 Opinion 之前整表清空。
        db.query(AlertRecord).delete()
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        # 清空「全部 opinions」而非仅本测试 source：aggregate() 会聚类
        # 所有 completed 且窗口内的 Opinion，若只清 SRC 会漏掉其它测试
        # 遗留（如 mig_src）导致聚类数量断言失真。测试库为独立
        # opinion_test，可安全截断（Region 种子不受影响）。
        db.query(Opinion).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        # 先清理可能引用 events 的外键行（aggregate 会触发传播重建产生 propagation_nodes / alert_records）
        db.query(PropagationNode).delete()
        # AlertRecord 引用 opinion_id（FK），必须在删除 Opinion 之前整表清空。
        db.query(AlertRecord).delete()
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        # 清空「全部 opinions」而非仅本测试 source：aggregate() 会聚类
        # 所有 completed 且窗口内的 Opinion，若只清 SRC 会漏掉其它测试
        # 遗留（如 mig_src）导致聚类数量断言失真。测试库为独立
        # opinion_test，可安全截断（Region 种子不受影响）。
        db.query(Opinion).delete()
        db.commit()
    finally:
        db.close()


def _mk(db, region_id, title, content, keywords="", risk=0, ai="",
        pub=None, created=None, source=SRC):
    op = Opinion(
        title=title,
        content=content,
        source=source,
        url=f"https://example.com/{uuid.uuid4().hex}",
        region_id=region_id,
        risk_score=risk,
        sentiment="neutral",
        summary="",
        keywords=keywords,
        ai_keywords=ai,
        analysis_status="completed",
        publish_time=pub,
        created_at=created or datetime.now(timezone.utc),
    )
    db.add(op)
    db.flush()
    return op


def _event_of(db, opinion_id) -> int | None:
    row = (
        db.query(EventOpinion.event_id)
        .filter(EventOpinion.opinion_id == opinion_id)
        .first()
    )
    return row.event_id if row else None


def _max_coverage_of(db, op_ids: list[int]) -> int:
    """返回这批 Opinion 中，被同一个 Event 链接的最大条数（用于反链式断言）。"""
    best = 0
    events = db.query(Event).all()
    for ev in events:
        linked = {
            r.opinion_id
            for r in db.query(EventOpinion)
            .filter(EventOpinion.event_id == ev.id)
            .all()
        }
        cov = len(set(op_ids) & linked)
        best = max(best, cov)
    return best


# ---------------------------------------------------------------------------
# 1) 两篇仅共享通用词（文本不相似）→ 不合并
# ---------------------------------------------------------------------------
def test_shared_generic_only_not_merged(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        a = _mk(db, r, "西区厂房火灾", "西区厂房深夜发生火灾，过火面积较大", "火灾", risk=50)
        b = _mk(db, r, "南区桥梁腐败", "南区桥梁工程被曝存在腐败问题", "腐败", risk=50)
        db.commit()
        res = EventAggregator().aggregate(db)
        # 各自因风险>=40 独立成事件，但不应合并为同一事件
        assert res["created"] == 2, res
        # 二者不得落入同一事件（无论是否各自成事件）
        assert _max_coverage_of(db, [a.id, b.id]) < 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2) 链式传递不应导致 A+B+C 全部并入同一 Event
# ---------------------------------------------------------------------------
def test_no_chain_merge(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "清河路28号储罐区"
        a = _mk(db, r, f"{anchor}爆炸", f"{anchor}发生爆炸事故，引发周边投诉", "事故,投诉", risk=50)
        b = _mk(db, r, f"{anchor}爆炸续报", f"{anchor}爆炸事故调查中，居民持续投诉", "事故,投诉", risk=50)
        c = _mk(db, r, "锦绣花园物业维权", "锦绣花园业主对物业进行维权投诉", "投诉,维权", risk=50)
        db.commit()
        EventAggregator().aggregate(db)
        # A、B 因文本高度相似合并；C 仅与 A/B 共享通用词「投诉」但文本不相似，
        # 不应借 B 之链搭车并入同一事件。
        assert _max_coverage_of(db, [a.id, b.id, c.id]) < 3
        eids = {_event_of(db, a.id), _event_of(db, b.id), _event_of(db, c.id)}
        assert not (len({x for x in eids if x is not None}) == 1)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3) 同 region 不同事件（不同通用词 + 文本不相似）→ 不合并
# ---------------------------------------------------------------------------
def test_same_region_diff_event_not_merged(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        a = _mk(db, r, "东区化工厂泄漏", "东区化工厂发生化学品泄漏，环保介入", "爆炸", risk=55)
        b = _mk(db, r, "西区食堂卫生问题", "西区食堂被曝卫生不达标遭投诉", "投诉", risk=55)
        db.commit()
        res = EventAggregator().aggregate(db)
        assert res["created"] == 2, res
        assert _max_coverage_of(db, [a.id, b.id]) < 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4) 同一事件多篇高度相似舆情 → 聚合为 1 个 Event
# ---------------------------------------------------------------------------
def test_high_similarity_merges(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "清河路28号储罐区"
        for _ in range(3):
            _mk(db, r, f"{anchor}交通事故", f"{anchor}发生交通事故车辆追尾", "事故", risk=10)
        db.commit()
        res = EventAggregator().aggregate(db)
        assert res["created"] == 1, res
        ev = db.query(Event).first()
        assert ev.opinion_count == 3, ev.opinion_count
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5) 不同时间段无关舆情（文本相同但发布时间超窗口）→ 不合并
# ---------------------------------------------------------------------------
def test_distant_time_not_merged(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "清河路28号储罐区"
        g = _mk(db, r, f"{anchor}交通事故", f"{anchor}发生交通事故车辆追尾", "事故",
                risk=10, pub=datetime(2026, 1, 1, tzinfo=timezone.utc))
        h = _mk(db, r, f"{anchor}交通事故", f"{anchor}发生交通事故车辆追尾", "事故",
                risk=10, pub=datetime(2026, 2, 10, tzinfo=timezone.utc))
        db.commit()
        EventAggregator().aggregate(db)
        # 发布时间相差 40 天（远超 event_window_days=7）→ 时间门槛阻断，不合并
        assert _max_coverage_of(db, [g.id, h.id]) < 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6) 空 keywords 的 Opinion → 不应被错误判定为同一事件；
#    但高度相似的空关键词舆情应仍可经文本召回聚合
# ---------------------------------------------------------------------------
def test_empty_keywords_disimilar_not_merged(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        p1 = _mk(db, r, "苹果发布新手机", "苹果公司今日发布新款智能手机产品", "", risk=0)
        p2 = _mk(db, r, "香蕉价格上涨", "多地香蕉批发价格出现明显上涨趋势", "", risk=0)
        db.commit()
        EventAggregator().aggregate(db)
        assert _max_coverage_of(db, [p1.id, p2.id]) < 2
    finally:
        db.close()


def test_empty_keywords_identical_text_merges(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "清河路28号储罐区"
        q1 = _mk(db, r, f"{anchor}停水通知", f"{anchor}今晚计划停水检修管道", "", risk=0)
        q2 = _mk(db, r, f"{anchor}停水通知", f"{anchor}今晚计划停水检修管道", "", risk=0)
        db.commit()
        res = EventAggregator().aggregate(db)
        assert res["created"] == 1, res
        assert _max_coverage_of(db, [q1.id, q2.id]) == 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 7) Event 重复运行 → 不产生重复 EventOpinion（幂等）
# ---------------------------------------------------------------------------
def test_idempotent_rerun(clean_events, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        _mk(db, r, "专项整改通报一", "关于专项整改工作的第一阶段通报", "专项整改", risk=10)
        _mk(db, r, "专项整改通报二", "关于专项整改工作的第二阶段通报", "专项整改", risk=10)
        db.commit()
        r1 = EventAggregator().aggregate(db)
        assert r1["created"] == 1, r1
        assert r1["linked"] == 2, r1
        before = db.query(EventOpinion).count()
        r2 = EventAggregator().aggregate(db)
        assert r2["created"] == 0, r2
        assert r2["updated"] == 0, r2
        assert r2["linked"] == 0, r2
        assert db.query(EventOpinion).count() == before
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 8) 现有 Event API contract 不发生破坏性变化
# ---------------------------------------------------------------------------
def test_api_contract_unchanged(
    clean_events, client: TestClient, auth_headers, seeded_region_id
) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        _mk(db, r, "专项整改通报一", "关于专项整改工作的第一阶段通报", "专项整改", risk=10)
        _mk(db, r, "专项整改通报二", "关于专项整改工作的第二阶段通报", "专项整改", risk=10)
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/events/aggregate", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    for k in ("created", "updated", "linked"):
        assert k in body and isinstance(body[k], int)
    assert body["created"] >= 1

    lst = client.get("/api/events?page=1&size=20", headers=auth_headers)
    assert lst.status_code == 200, lst.text
    lb = lst.json()
    assert "items" in lb and "total" in lb
    assert len(lb["items"]) >= 1
    for it in lb["items"]:
        for f in ("id", "title", "risk_level", "opinion_count", "status"):
            assert f in it, f
        assert it["status"] == "active"


# ---------------------------------------------------------------------------
# 13) 旧关键词「永久吸附」不再发生：超延续窗口的陈旧事件不吸附加新相似舆情
# ---------------------------------------------------------------------------
def test_no_permanent_absorption(clean_events, seeded_region_id) -> None:
    """验证：一个 last_time 远超 event_continuation_days(14) 的陈旧事件，
    不会把文本高度相似、但时间全新的舆情「永久吸附」进来。

    机制（来自 aggregator._match_existing_event 延续分支）：
      - 延续只考察 last_time >= now - event_continuation_days 的「活跃」事件；
      - 陈旧事件（last_time 太旧）直接跳过，新舆情只能独立成新事件。
    """
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "滨河西路28号储罐区"
        old_time = datetime.now(timezone.utc) - timedelta(days=30)
        # 陈旧舆情（30 天前，远超聚合窗口）
        old_op = _mk(
            db, r, f"{anchor}爆炸", f"{anchor}发生爆炸事故引发关注", "事故",
            risk=60, created=old_time, pub=old_time,
        )
        db.commit()
        # 直接构造一个「陈旧事件」（模拟 Phase 0 旧关键词伪聚合残留）：
        # last_time 远早于 event_continuation_days(14)，因此即便文本相似，
        # 增量聚合也不会把新舆情「永久吸附」进来。
        ev = Event(
            title=f"{anchor}旧事件",
            description="旧描述",
            keyword="事故",
            risk_level="high",
            opinion_count=1,
            first_time=old_time,
            last_time=old_time,
        )
        db.add(ev)
        db.flush()
        db.add(EventOpinion(event_id=ev.id, opinion_id=old_op.id))
        db.commit()
        old_ev = ev
        # 陈旧事件 last_time 远早于延续窗口
        # 注意：Event.last_time 为 naive TIMESTAMP（读取后无 tz），
        # 故用 naive datetime.now() 比较，避免 aware/naive 相减报错。
        assert old_ev.last_time is not None
        assert (datetime.now() - old_ev.last_time).days > 14

        # 全新的相似舆情（现在，落在聚合窗口内），文本与旧舆情高度相似
        new_op = _mk(
            db, r, f"{anchor}爆炸续报", f"{anchor}发生爆炸事故引发关注救援进行中", "事故",
            risk=60,
        )
        db.commit()
        # 增量聚合（非 rebuild）：新舆情不应被吸附进陈旧事件
        EventAggregator().aggregate(db)

        # 陈旧事件仍只有最初那一条成员（未被新舆情污染）
        assert (
            db.query(EventOpinion)
            .filter(EventOpinion.event_id == old_ev.id)
            .count()
            == 1
        )
        assert _event_of(db, old_op.id) == old_ev.id
        # 新舆情落在一个「不同」的新事件上（而非陈旧事件）
        new_ev_id = _event_of(db, new_op.id)
        assert new_ev_id is not None
        assert new_ev_id != old_ev.id
        # 二者不共享同一事件（反永久吸附）
        assert _max_coverage_of(db, [old_op.id, new_op.id]) < 2
    finally:
        db.close()
