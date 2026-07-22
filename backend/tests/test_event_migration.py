"""Phase 4-Event-2A：受控 Event 全量重建迁移测试。

覆盖范围（相对需求第七节 11 项）：
1. 旧 Event 被完全拆散（多成员旧 Event -> 多个新 Event）
2. 一个旧 Event 拆成多个新 Event（映射 split_count>=2）
3. 多个旧 Event 合并为一个新 Event
4. 新 Event 不允许无成员（一致性校验拦截空 Event）
5. 不产生孤儿 EventOpinion
6. 不产生重复 EventOpinion
7. opinion_count 与真实关联数一致
8. preflight 与正式迁移输入一致（predicted_event_count == 实际 created）
9. dry-run 不产生数据库写入
10. 事务失败可以回滚
11. 迁移前后可验证数据完整性

说明：
- 本测试在隔离测试库（opinion_test）运行，仅验证「迁移机制」，不触碰生产库。
- 「旧 Event」通过直接写入 Event + EventOpinion 模拟 Phase 4-Event-0 之前的
  旧规则伪聚合结果（在同一 region/窗口下把本不该合并的 Opinion 聚到一起），
  以验证新规则迁移会正确拆解 / 合并。
- 聚合判定规则本身沿用 Phase 4-Event-1 的 cluster_opinions，不在本文件修改。
约束遵守：
- 不修改 Event / EventOpinion / Opinion Model、不改迁移、不改 API contract。
- 仅使用既有字段与 aggregator 暴露的纯函数。
"""
import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.alert import AlertRecord, AlertRule
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.propagation import PropagationNode
from app.services.event.migration import (
    compute_new_events,
    consistency_check,
    migrate_events,
    preflight,
    _snapshot_to_disk,
)

SRC = "mig_src"


@pytest.fixture
def mig_clean():
    """清空 propagation/alert/events/event_opinions/全部 opinions，保证隔离。

    注意：必须清空「全部 opinions」而不仅是本测试 source 的，
    否则其它测试遗留、且落在聚合窗口内的 opinions 会被 compute_new_events
    误纳入，导致事件数量断言失真。测试库为独立 opinion_test，可安全截断。
    """
    db = SessionLocal()
    try:
        db.query(PropagationNode).delete()
        # AlertRecord 引用 opinion_id（FK），必须在删除 Opinion 之前整表清空，
        # 否则 delete opinions 会触发外键约束失败（本测试会创建 AlertRecord）。
        db.query(AlertRecord).delete()
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(PropagationNode).delete()
        # AlertRecord 引用 opinion_id（FK），必须在删除 Opinion 之前整表清空，
        # 否则 delete opinions 会触发外键约束失败（本测试会创建 AlertRecord）。
        db.query(AlertRecord).delete()
        db.query(EventOpinion).delete()
        db.query(Event).delete()
        db.query(Opinion).delete()
        db.commit()
    finally:
        db.close()


def _mk(db, region_id, title, content, keywords="", risk=0, ai="",
         pub=None, created=None):
    op = Opinion(
        title=title,
        content=content,
        source=SRC,
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


def _make_old_event(db, member_ids, title="旧事件"):
    """直接写入一个「旧规则」Event + EventOpinion（绕过新聚合，模拟历史伪聚合）。"""
    ev = Event(
        title=title,
        description="旧描述",
        keyword="事故,投诉",
        risk_level="high",
        opinion_count=len(member_ids),
        first_time=datetime.now(timezone.utc),
        last_time=datetime.now(timezone.utc),
    )
    db.add(ev)
    db.flush()
    for oid in member_ids:
        db.add(EventOpinion(event_id=ev.id, opinion_id=oid))
    db.flush()
    return ev


def _event_of(db, opinion_id):
    row = (
        db.query(EventOpinion.event_id)
        .filter(EventOpinion.opinion_id == opinion_id)
        .first()
    )
    return row.event_id if row else None


def _link_count(db, event_id):
    return (
        db.query(EventOpinion)
        .filter(EventOpinion.event_id == event_id)
        .count()
    )


# ---------------------------------------------------------------------------
# 1) + 2) 旧多成员 Event 被完全拆散为一个个新 Event（且含一个低分成员变空）
# ---------------------------------------------------------------------------
def test_old_event_fully_dispersed(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        # 三篇互不相似、各带不同通用词的高风险舆情（各 risk>=40 -> 各自物化为单条 Event）
        a = _mk(db, r, "西区厂房火灾", "西区厂房深夜发生火灾过火面积较大", "火灾", risk=50)
        b = _mk(db, r, "南区桥梁腐败", "南区桥梁工程被曝存在腐败问题", "腐败", risk=50)
        c = _mk(db, r, "北区管道泄漏", "北区供水管道发生泄漏影响居民", "事故", risk=50)
        # 一篇低风险、独特关键词、文本不相似的舆情（新规则下不应物化为 Event）
        d = _mk(db, r, "某社区便民通知", "某社区发布便民服务临时通知", "谣言", risk=5)
        db.commit()

        # 模拟旧规则：把 a,b,c 误聚为一个旧 Event；d 单独成另一个旧 Event
        old1 = _make_old_event(db, [a.id, b.id, c.id], title="旧伪聚合1")
        old2 = _make_old_event(db, [d.id], title="旧伪聚合2")
        db.commit()

        pf = preflight(db)
        old1_map = next(
            x for x in pf["old_to_new_mapping"] if x["old_event_id"] == old1.id
        )
        old2_map = next(
            x for x in pf["old_to_new_mapping"] if x["old_event_id"] == old2.id
        )
        # 旧1（3 成员）被拆成 >=2 个新 Event，且成员全部保留
        assert old1_map["split_count"] >= 2, old1_map
        assert old1_map["retained_member_count"] == 3, old1_map
        # 旧2 的成员 d 在新规则下不物化 -> 旧2 完全消失/变空
        assert old2_map["fully_disappeared"] is True, old2_map
        assert old2_map["became_empty"] is True, old2_map

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        assert res["executed"] is True
        # 新规则下 a,b,c 各自独立成 Event（3 个）；d 不物化 -> 共 3 个
        assert db.query(Event).count() == 3, db.query(Event).count()
        # 旧 old1/old2 已不存在
        assert db.get(Event, old1.id) is None
        assert db.get(Event, old2.id) is None
        # d 不再挂到任何 Event
        assert _event_of(db, d.id) is None
        # a,b,c 各自独立（不共享 Event）
        assert len({_event_of(db, x.id) for x in (a, b, c)}) == 3
        # 一致性：无空/孤儿/重复
        chk = consistency_check(db)
        assert chk["empty_event_count"] == 0, chk
        assert chk["orphan_link_count"] == 0, chk
        assert chk["duplicate_link_count"] == 0, chk
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3) 多个旧 Event 合并为一个新 Event
# ---------------------------------------------------------------------------
def test_multiple_old_merge_into_one(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "清河路28号储罐区"
        # 三篇高度相似（同文本+同通用词）-> 新规则应合并为 1 个 Event
        x = _mk(db, r, f"{anchor}交通事故", f"{anchor}发生交通事故车辆追尾", "事故", risk=10)
        y = _mk(db, r, f"{anchor}交通事故", f"{anchor}发生交通事故车辆追尾", "事故", risk=10)
        z = _mk(db, r, f"{anchor}交通事故", f"{anchor}发生交通事故车辆追尾", "事故", risk=10)
        db.commit()

        # 模拟旧规则：把同一真实事件拆成 3 个独立旧 Event
        old1 = _make_old_event(db, [x.id], title="旧拆1")
        old2 = _make_old_event(db, [y.id], title="旧拆2")
        old3 = _make_old_event(db, [z.id], title="旧拆3")
        db.commit()

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # 新规则：x,y,z 合并为 1 个 Event
        assert res["created_event_count"] == 1, res
        assert db.query(Event).count() == 1
        ev = db.query(Event).first()
        assert _link_count(db, ev.id) == 3
        # 旧 3 个 Event 已不存在
        for oid in (old1.id, old2.id, old3.id):
            assert db.get(Event, oid) is None
        chk = consistency_check(db)
        assert chk["empty_event_count"] == 0, chk
        assert chk["duplicate_link_count"] == 0, chk
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 8) preflight 与正式迁移输入一致
# ---------------------------------------------------------------------------
def test_preflight_matches_formal(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "滨江路下穿隧道"
        for _ in range(3):
            _mk(db, r, f"{anchor}积水", f"{anchor}暴雨导致积水交通中断", "事故", risk=10)
        db.commit()

        pf = preflight(db)
        assert pf["predicted_event_count"] == 1, pf

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # 正式执行创建的 Event 数 == preflight 预测数
        assert res["created_event_count"] == pf["predicted_event_count"], (res, pf)
        assert res["predicted_event_count"] == pf["predicted_event_count"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 9) dry-run 不产生数据库写入
# ---------------------------------------------------------------------------
def test_dry_run_no_writes(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "云栖大道"
        for _ in range(2):
            _mk(db, r, f"{anchor}演练", f"{anchor}今天组织消防演练活动", "事故", risk=10)
        db.commit()
        before = db.query(Event).count()

        res = migrate_events(db, dry_run=True)  # 默认 dry_run
        assert res["dry_run"] is True
        assert res["executed"] is False
        after = db.query(Event).count()
        assert after == before, (before, after)
        # preflight 预测值仍正确产出
        assert res["predicted_event_count"] == 1, res
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 10) 事务失败可以回滚
# ---------------------------------------------------------------------------
def test_transaction_rollback_on_failure(mig_clean, seeded_region_id, monkeypatch) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        a = _mk(db, r, "事件甲", "事件甲正文内容独一无二", "事故", risk=50)
        b = _mk(db, r, "事件乙", "事件乙正文内容完全不同", "投诉", risk=50)
        db.commit()
        old = _make_old_event(db, [a.id, b.id], title="待迁移旧事件")
        db.commit()
        before = db.query(Event).count()

        # 注入一致性校验失败，触发 rollback
        def _boom(db):
            raise RuntimeError("injected consistency failure")

        monkeypatch.setattr(
            "app.services.event.migration.consistency_check", _boom
        )
        with pytest.raises(RuntimeError):
            migrate_events(db, dry_run=False, force=True, allow_production=True)

        # 回滚后：旧数据完好，无变化
        after = db.query(Event).count()
        assert after == before, (before, after)
        assert db.get(Event, old.id) is not None
        assert _link_count(db, old.id) == 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 11) 迁移前后可验证数据完整性
# ---------------------------------------------------------------------------
def test_integrity_before_and_after(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "示范新区"
        p = _mk(db, r, f"{anchor}噪声投诉", f"{anchor}夜间施工噪声引发居民投诉", "投诉", risk=45)
        q = _mk(db, r, f"{anchor}噪声投诉", f"{anchor}夜间施工噪声引发居民投诉", "投诉", risk=45)
        db.commit()

        # 迁移前：干净库一致性 0 问题
        pre = consistency_check(db)
        assert pre["empty_event_count"] == 0, pre
        assert pre["orphan_link_count"] == 0, pre
        assert pre["duplicate_link_count"] == 0, pre

        # 建立一个会被拆散的旧伪聚合
        old = _make_old_event(db, [p.id, q.id], title="旧噪声伪聚合")
        db.commit()

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # 迁移后：p,q 高相似应合并为 1 个 Event，且各校验项全 0
        assert res["post_migration_consistency"]["empty_event_count"] == 0
        assert res["post_migration_consistency"]["orphan_link_count"] == 0
        assert res["post_migration_consistency"]["duplicate_link_count"] == 0
        assert res["post_migration_consistency"]["opinion_count_mismatch"] == []
        ev = db.query(Event).first()
        assert ev is not None
        assert ev.opinion_count == 2
        assert _link_count(db, ev.id) == 2
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4)+5)+6)+7) 综合：迁移后无空/孤儿/重复，opinion_count 与关联一致
# ---------------------------------------------------------------------------
def test_migration_integrity_contract(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        # 两个真实同事件（高相似）+ 两个无关单条
        anchor = "光华大街"
        s1 = _mk(db, r, f"{anchor}塌方", f"{anchor}边坡塌方道路中断", "事故", risk=60)
        s2 = _mk(db, r, f"{anchor}塌方", f"{anchor}边坡塌方道路中断", "事故", risk=60)
        t1 = _mk(db, r, "东湖景区公告", "东湖景区发布闭园维护公告", "谣言", risk=42)
        t2 = _mk(db, r, "西园路灯维修", "西园片区路灯集中维修通知", "投诉", risk=42)
        db.commit()

        # 旧规则把它们全误聚为一个大 Event
        old = _make_old_event(
            db, [s1.id, s2.id, t1.id, t2.id], title="旧大杂烩"
        )
        db.commit()

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # 新规则：s1,s2 合并(1)；t1,t2 各成单条(2) -> 共 3 个 Event
        assert res["created_event_count"] == 3, res
        chk = res["post_migration_consistency"]
        # 4) 无空 Event
        assert chk["empty_event_count"] == 0, chk
        # 5) 无孤儿 EventOpinion
        assert chk["orphan_link_count"] == 0, chk
        # 6) 无重复 EventOpinion
        assert chk["duplicate_link_count"] == 0, chk
        # 7) 每个 Event 的 opinion_count 与真实关联数一致
        assert chk["opinion_count_mismatch"] == [], chk
        for ev in db.query(Event).all():
            assert ev.opinion_count == _link_count(db, ev.id), ev.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.1) AlertRecord 按 opinion_id 重链（迁移前带旧 event_id，迁移后指向新 Event）
# ---------------------------------------------------------------------------
def test_alert_relink_by_opinion_id(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        # 一条高风险舆情 -> 新规则会独立物化为 Event
        o = _mk(db, r, "高新区化工泄漏", "高新区化工厂发生泄漏环保部门介入", "事故", risk=55)
        db.commit()
        # 旧规则把它误聚到一个旧 Event
        old = _make_old_event(db, [o.id], title="旧化工事件")
        db.commit()
        # 关联一条 AlertRecord：先指向旧 Event（模拟历史状态）
        rule = AlertRule(name="r1", risk_threshold=40, risk_level="high", enabled=True)
        db.add(rule)
        db.flush()
        rec = AlertRecord(
            rule_id=rule.id,
            rule_name="r1",
            risk_level="high",
            opinion_id=o.id,
            opinion_title=o.title,
            event_id=old.id,  # 初始指向旧 Event
            event_title=old.title,
            trigger_reason="risk>=40",
        )
        db.add(rec)
        db.commit()

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # 主数据完整性
        assert res["post_migration_consistency"]["empty_event_count"] == 0
        # 重链结果：该 AlertRecord 被重链到「包含 o 的新 Event」，不再是旧 id
        assert res["alert_relink"]["relinked"] >= 1, res["alert_relink"]
        rec2 = db.query(AlertRecord).filter(AlertRecord.opinion_id == o.id).first()
        assert rec2 is not None
        assert rec2.event_id is not None
        assert rec2.event_id != old.id, "重链不应回到已删除的旧 Event id"
        # 该新 event 确实包含 o
        assert _event_of(db, o.id) == rec2.event_id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.2) opinion 未物化为 Event 时，AlertRecord 显式记为 orphan（不静默丢失）
# ---------------------------------------------------------------------------
def test_alert_orphan_when_opinion_not_materialized(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        # 低风险单条舆情 -> 不满足 event_singleton_min_risk=40 -> 不物化
        low = _mk(db, r, "社区便民通知", "某社区发布便民服务临时通知", "谣言", risk=5)
        db.commit()
        rule = AlertRule(name="r2", risk_threshold=1, risk_level="low", enabled=True)
        db.add(rule)
        db.flush()
        rec = AlertRecord(
            rule_id=rule.id,
            rule_name="r2",
            risk_level="low",
            opinion_id=low.id,
            opinion_title=low.title,
            event_id=None,
            event_title="",
            trigger_reason="low-risk",
        )
        db.add(rec)
        db.commit()

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # low 未物化 -> 不应挂到任何 Event
        assert _event_of(db, low.id) is None
        # 重链后该 AlertRecord 仍为 orphan（event_id 为 None）
        assert res["alert_relink"]["orphan"] >= 1, res["alert_relink"]
        rec2 = db.query(AlertRecord).filter(AlertRecord.opinion_id == low.id).first()
        assert rec2.event_id is None
        assert any(
            o["opinion_id"] == low.id and o["reason"] == "opinion_not_in_any_event"
            for o in res["alert_relink"]["orphan_records"]
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.3) 单个 Event 传播树重建失败时的可观测性（不静默吞掉）
# ---------------------------------------------------------------------------
def test_propagation_single_event_failure_observable(
    mig_clean, seeded_region_id, monkeypatch
) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        o = _mk(db, r, "老旧小区改造", "老旧小区改造施工引发居民关注", "投诉", risk=50)
        db.commit()
        old = _make_old_event(db, [o.id], title="旧改造事件")
        db.commit()

        captured = {}

        def _boom(db, event_id):
            captured["event_id"] = event_id
            raise RuntimeError("injected propagation failure")

        monkeypatch.setattr(
            "app.services.propagation_service.PropagationService.rebuild_for_event",
            _boom,
        )
        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # 主迁移事务成功，不因传播失败而回滚
        assert res["executed"] is True
        assert res["post_migration_consistency"]["empty_event_count"] == 0
        # 失败被显式记录
        pr = res["propagation_rebuild"]
        assert pr["failed_count"] >= 1, pr
        failed = pr["failed"][0]
        assert "event_id" in failed and failed["event_id"] is not None
        assert failed["error_type"] == "RuntimeError"
        assert "injected propagation failure" in failed["error"]
        assert failed["traceback"]  # 非空 traceback
        assert pr["status"] in ("partial", "all_failed")
        assert captured["event_id"] is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.4) 部分传播重建失败时的迁移报告分类（succeeded + failed = total）
# ---------------------------------------------------------------------------
def test_propagation_partial_failure_report(
    mig_clean, seeded_region_id, monkeypatch
) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        # 两篇「完全不相似」的舆情 -> 必须形成 2 个独立 Event
        a = _mk(db, r, "路段A山体滑坡", "路段A发生山体滑坡道路中断", "滑坡", risk=50)
        b = _mk(db, r, "路段B水管爆裂", "路段B自来水管爆裂影响供水", "爆管", risk=50)
        db.commit()
        old1 = _make_old_event(db, [a.id], title="旧A")
        old2 = _make_old_event(db, [b.id], title="旧B")
        db.commit()

        # 确定性失败：第 2 个 Event 重建失败 -> 恰好 1 个失败（避免依赖 id 奇偶）
        calls = {"n": 0}

        def _boom_on(db, event_id):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("boom #2")
            return {"nodes_created": 0}

        monkeypatch.setattr(
            "app.services.propagation_service.PropagationService.rebuild_for_event",
            _boom_on,
        )
        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        pr = res["propagation_rebuild"]
        assert pr["total"] == 2, pr
        assert pr["status"] == "partial", pr
        assert pr["failed_count"] == 1, pr
        assert len(pr["succeeded"]) + pr["failed_count"] == pr["total"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.5)+6) 快照包含 propagation_nodes 与 alert_records 完整字段
# ---------------------------------------------------------------------------
def test_snapshot_includes_propagation_and_alerts(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        o = _mk(db, r, " snapshot 事件", "snapshot 测试正文内容", "事故", risk=50)
        db.commit()
        old = _make_old_event(db, [o.id], title="旧快照事件")
        db.commit()
        # 放置一个传播节点与一个预警记录，验证快照能捕获
        db.add(
            PropagationNode(
                event_id=old.id,
                opinion_id=o.id,
                parent_id=None,
                source="mig_src",
                source_url="https://example.com/x",
                title="snapshot 事件",
                publish_time=datetime.now(timezone.utc),
                risk_score=50,
                sentiment="negative",
                keywords="事故",
                depth=0,
            )
        )
        rule = AlertRule(name="r3", risk_threshold=40, risk_level="high", enabled=True)
        db.add(rule)
        db.flush()
        db.add(
            AlertRecord(
                rule_id=rule.id,
                rule_name="r3",
                risk_level="high",
                opinion_id=o.id,
                opinion_title=o.title,
                event_id=old.id,
                event_title=old.title,
                trigger_reason="risk>=40",
            )
        )
        db.commit()

        snap_path = _snapshot_to_disk(
            db, os.path.join(tempfile.gettempdir(), "event_snap_test.json")
        )
        with open(snap_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
        assert "propagation_nodes" in snap, snap.keys()
        assert "alert_records" in snap, snap.keys()
        # 字段完整性
        pn = snap["propagation_nodes"][0]
        for k in ("id", "event_id", "opinion_id", "parent_id", "source", "title"):
            assert k in pn, pn
        ar = snap["alert_records"][0]
        for k in ("id", "opinion_id", "event_id", "event_title", "rule_id"):
            assert k in ar, ar
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.8) 旧 Event -> 新 Event 无 id 确定性映射：恢复依赖成员，而非 id 对应
# ---------------------------------------------------------------------------
def test_no_id_mapping_recovery_via_members(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        a = _mk(db, r, "江畔路塌方", "江畔路边坡塌方道路中断", "事故", risk=60)
        b = _mk(db, r, "江畔路塌方续", "江畔路边坡塌方道路中断救援中", "事故", risk=60)
        db.commit()
        # 旧规则把它们误聚成一个旧 Event
        old = _make_old_event(db, [a.id, b.id], title="旧江畔伪聚合")
        old_id = old.id
        db.commit()

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        # 旧 Event 已删除，新 Event 的 id 与旧 id 无对应关系
        assert db.get(Event, old_id) is None
        new_ids = {e.id for e in db.query(Event).all()}
        assert old_id not in new_ids
        # 通过成员（而非 id）恢复：a,b 现在都属于同一个新 Event
        ea = _event_of(db, a.id)
        eb = _event_of(db, b.id)
        assert ea is not None and eb is not None
        assert ea == eb, (ea, eb)
        # 一致性校验：无重复关联
        chk = consistency_check(db)
        assert chk["duplicate_link_count"] == 0, chk
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.9)+10) 物化阈值：risk<40 单条不物化；risk>=40 单条物化
# ---------------------------------------------------------------------------
def test_materialize_singleton_risk_threshold(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        low = _mk(db, r, "便民通知甲", "某社区发布便民服务临时通知甲", "谣言", risk=30)
        high = _mk(db, r, "火灾通报乙", "某厂房发生火灾过火面积较大乙", "火灾", risk=50)
        db.commit()

        # compute_new_events 与正式迁移同源：low 不应出现在任何新 Event
        planned = {oid for p in compute_new_events(db) for oid in p["member_ids"]}
        assert low.id not in planned, "risk<40 单条不应物化"
        assert high.id in planned, "risk>=40 单条应物化"

        res = migrate_events(db, dry_run=False, force=True, allow_production=True)
        assert _event_of(db, low.id) is None, "risk<40 单条不应挂到任何 Event"
        assert _event_of(db, high.id) is not None, "risk>=40 单条应独立成 Event"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# §八.14) 重复执行迁移不产生重复关联（幂等于关联层）
# ---------------------------------------------------------------------------
def test_migration_idempotent_rerun_no_duplicate(mig_clean, seeded_region_id) -> None:
    db: Session = SessionLocal()
    try:
        r = seeded_region_id
        anchor = "示范二路"
        for _ in range(2):
            _mk(db, r, f"{anchor}噪声投诉", f"{anchor}夜间施工噪声引发居民投诉", "投诉", risk=45)
        db.commit()

        res1 = migrate_events(db, dry_run=False, force=True, allow_production=True)
        links_after_1 = db.query(EventOpinion).count()
        dup_after_1 = consistency_check(db)["duplicate_link_count"]
        assert dup_after_1 == 0

        # 再次执行（同一份数据）
        res2 = migrate_events(db, dry_run=False, force=True, allow_production=True)
        links_after_2 = db.query(EventOpinion).count()
        dup_after_2 = consistency_check(db)["duplicate_link_count"]
        # 关联总数不增、重复数为 0（全量删除重建，结果确定）
        assert links_after_2 == links_after_1, (links_after_1, links_after_2)
        assert dup_after_2 == 0
        assert res2["created_event_count"] == res1["created_event_count"], (res1, res2)
    finally:
        db.close()
