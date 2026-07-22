"""Phase 4-Event-2A：受控 Event 全量重建迁移（preflight + 正式，默认 dry-run）。

设计定位
========
本模块只负责「把当前聚合结果安全落地为 events / event_opinions 表」，
即【迁移编排】。聚合规则本身完全复用 aggregator 的纯函数
（cluster_opinions / _merge_condition / _representative / _signals /
_map_risk_level / _merge_keywords），与 Phase 4-Event-1 已验证版本一致，
不改动聚合判定逻辑。

为什么需要它（来自 Phase 4-Event-1.5 只读 dry-run 结论）
==============================================================
现有 aggregate(rebuild=True) 存在迁移风险：
  - 仅清空「活跃」Event 的 EventOpinion 关联（last_time 在窗口内），
    但重建后若某些旧 Event 在新规则下不再有成员，其 Event 行残留为空孤儿；
  - 旧 Event 行不会被删除 -> 总量膨胀（实测 70 -> ~90）；
  - 无快照、无审计归档、无可靠回滚。
本模块用「快照(磁盘) + 单事务全量删除重建 + 一致性校验 + 提交后再校验」
取代之，彻底消除空孤儿、孤儿关联与数量膨胀。

严格约束（本阶段）
================
  - 默认 dry_run=True：只计算并返回预测，绝对不写库。
  - 正式执行需 force=True；对生产库额外要求 allow_production=True（防误触）。
  - 正式执行前必先跑 preflight，且 preflight 与正式执行使用【同一纯函数】，
    保证输入一致。
  - 正式执行在单一事务内：快照落盘 -> 解除外键引用 -> 全量 DELETE ->
    按 compute_new_events 重建 -> 一致性校验 -> commit；任一校验失败则 rollback。
  - 不产生空 Event / 孤儿 EventOpinion / 重复 EventOpinion；
    opinion_count 由真实关联数重算。
  - 本阶段（Phase 4-Event-2A）不调用正式执行；正式迁移留待后续阶段确认。
"""
from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import AlertRecord
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.propagation import PropagationNode
from app.services.event.aggregator import (
    EventAggregator,
    _effective_time,
    _map_risk_level,
    _representative,
    _signals,
    cluster_opinions,
)

# 已知生产库名（用于防误触守卫）。
PRODUCTION_DB_NAMES = frozenset({"opinion_db"})


def _db_name(db: Session) -> str:
    """从 SQLAlchemy 引擎 URL 提取数据库名（用于生产守卫）。"""
    try:
        url = db.get_bind().url
        return url.database or ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# 物化判定：与 aggregator.aggregate 完全一致
# ---------------------------------------------------------------------------
def _materialize(cluster: list[Opinion], cfg=settings) -> bool:
    """是否物化为独立 Event：多成员 / 含高区分度信号 / 风险够高 / 有 ai_keywords。"""
    rep = _representative(cluster)
    high_rep, _ = _signals(rep)
    ai_rep = {k.strip() for k in (rep.ai_keywords or "").split(",") if k.strip()}
    return (
        len(cluster) >= 2
        or bool(high_rep)
        or rep.risk_score >= cfg.event_singleton_min_risk
        or bool(ai_rep)
    )


def _merge_kw_local(cluster: Iterable) -> set:
    """本地关键词并集（避免与 aggregator._merge_keywords 名耦合）。"""
    merged: set = set()
    for op in cluster:
        for k in (op.keywords or "").split(","):
            k = k.strip()
            if k:
                merged.add(k)
    return merged


def _load_window_opinions(db: Session, cfg=settings) -> List[Opinion]:
    """候选 Opinion：最近 event_window_days 天内、analysis_status=completed。

    与 aggregator.aggregate 的取数完全一致（含「不再要求 keywords 非空」）。
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cfg.event_window_days)
    return (
        db.query(Opinion)
        .filter(Opinion.analysis_status == "completed", Opinion.created_at >= cutoff)
        .all()
    )


# ---------------------------------------------------------------------------
# 共享纯计算：preflight 与正式迁移都调用它 -> 输入必然一致
# ---------------------------------------------------------------------------
def compute_new_events(db: Session, cfg=settings) -> List[dict]:
    """纯计算：返回「正式迁移将创建的 Event 计划」（不含 id，仅成员描述）。

    依赖仅 opinion 表（与 events 无关），故 preflight 时与正式执行时
    （即便中间删除了旧 events）结果完全一致。
    """
    opinions = _load_window_opinions(db, cfg)
    clusters = cluster_opinions(opinions, cfg)
    plans: List[dict] = []
    for idx, cluster in enumerate(clusters):
        if not _materialize(cluster, cfg):
            continue
        rep = _representative(cluster)
        merged_kw = sorted(_merge_kw_local(cluster))
        times = [t for t in (_effective_time(o) for o in cluster) if t is not None]
        plans.append(
            {
                "index": idx,
                "member_ids": [o.id for o in cluster],
                "representative_id": rep.id,
                "title": rep.title,
                "description": (rep.content or "")[:200],
                "keyword": ",".join(merged_kw),
                "risk_level": _map_risk_level(max(o.risk_score for o in cluster)),
                "opinion_count": len(cluster),
                "first_time": min(times) if times else None,
                "last_time": max(times) if times else None,
            }
        )
    return plans


# ---------------------------------------------------------------------------
# 只读预检（Preflight）
# ---------------------------------------------------------------------------
def preflight(db: Session, cfg=settings) -> dict:
    """只读预检：不执行任何 INSERT / UPDATE / DELETE（仅 SELECT）。

    返回完整预测结果，含 old_to_new_mapping（每个旧 Event 的成员去向）。
    """
    # ---- 旧数据（只读）----
    old_events = db.query(Event).all()
    old_event_count = len(old_events)
    old_members: dict[int, List[int]] = {}
    for ev in old_events:
        rows = (
            db.query(EventOpinion.opinion_id)
            .filter(EventOpinion.event_id == ev.id)
            .all()
        )
        old_members[ev.id] = [r.opinion_id for r in rows]
    old_total_links = sum(len(v) for v in old_members.values())
    old_singleton = sum(1 for v in old_members.values() if len(v) == 1)
    old_multi = old_event_count - old_singleton
    old_max = max((len(v) for v in old_members.values()), default=0)

    # ---- 候选 Opinion（与 compute 一致）----
    candidate = _load_window_opinions(db, cfg)
    candidate_ids = {o.id for o in candidate}

    # ---- 新计划 ----
    plans = compute_new_events(db, cfg)
    predicted_event_count = len(plans)
    new_member_ids = {oid for p in plans for oid in p["member_ids"]}
    predicted_coverage = len(new_member_ids)
    predicted_singleton = sum(1 for p in plans if p["opinion_count"] == 1)
    predicted_multi = predicted_event_count - predicted_singleton
    predicted_max = max((p["opinion_count"] for p in plans), default=0)
    predicted_avg = (
        sum(p["opinion_count"] for p in plans) / predicted_event_count
        if predicted_event_count
        else 0.0
    )
    # 下述三项在设计上恒为 0（重建时全量删除后由计划重建，无空/孤儿/重复）。
    predicted_empty = sum(1 for p in plans if p["opinion_count"] == 0)
    predicted_orphan = 0
    predicted_duplicate = 0

    # ---- 旧 -> 新 映射 ----
    old_to_new: List[dict] = []
    for ev in old_events:
        oids = set(old_members[ev.id])
        targets = [p["index"] for p in plans if (set(p["member_ids"]) & oids)]
        retained = len(oids & new_member_ids)
        old_to_new.append(
            {
                "old_event_id": ev.id,
                "old_member_count": len(oids),
                "retained_member_count": retained,
                "split_into_new_event_indices": targets,
                "split_count": len(targets),
                "fully_disappeared": retained == 0 and len(oids) > 0,
                "became_empty": len(oids) > 0 and retained == 0,
            }
        )

    return {
        "old_event_count": old_event_count,
        "old_opinion_coverage": old_total_links,
        "old_singleton_count": old_singleton,
        "old_multi_member_count": old_multi,
        "old_max_members": old_max,
        "candidate_opinion_count": len(candidate_ids),
        "predicted_event_count": predicted_event_count,
        "predicted_opinion_coverage": predicted_coverage,
        "predicted_singleton_count": predicted_singleton,
        "predicted_multi_member_count": predicted_multi,
        "predicted_max_members": predicted_max,
        "predicted_avg_members": round(predicted_avg, 3),
        "predicted_empty_event_count": predicted_empty,
        "predicted_orphan_link_count": predicted_orphan,
        "predicted_duplicate_link_count": predicted_duplicate,
        "old_to_new_mapping": old_to_new,
    }


# ---------------------------------------------------------------------------
# 磁盘快照（等效审计记录，纯 SELECT，不写数据库）
# ---------------------------------------------------------------------------
def _snapshot_to_disk(db: Session, path: str) -> str:
    """把当前 events / event_opinions / propagation_nodes / alert_records 全量读出，
    写成 JSON 文件（扩展版，覆盖迁移会触及的全部关联表）。

    仅 SELECT，落盘到磁盘；供事后审计与回滚还原，不触碰数据库。

    说明（对应 Phase 4-Event-2A.6 §三.3）：
    快照保存的是「旧状态」，其意义是：
      - 迁移事务失败 / 提交后异常时提供额外恢复依据；
      - 不假设可以通过旧 Event id 直接映射到新 Event id
        （旧->新不存在确定性映射，只能按成员/舆情重推导）。
    """
    events = db.query(Event).all()
    ev_rows = [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "keyword": e.keyword,
            "risk_level": e.risk_level,
            "opinion_count": e.opinion_count,
            "first_time": e.first_time.isoformat() if e.first_time else None,
            "last_time": e.last_time.isoformat() if e.last_time else None,
        }
        for e in events
    ]
    links = db.query(EventOpinion).all()
    link_rows = [
        {"event_id": l.event_id, "opinion_id": l.opinion_id} for l in links
    ]
    # ---- propagation_nodes：恢复传播树所需的完整字段 ----
    pnodes = db.query(PropagationNode).all()
    pnode_rows = [
        {
            "id": n.id,
            "event_id": n.event_id,
            "opinion_id": n.opinion_id,
            "parent_id": n.parent_id,
            "source": n.source,
            "source_url": n.source_url,
            "title": n.title,
            "publish_time": n.publish_time.isoformat() if n.publish_time else None,
            "risk_score": n.risk_score,
            "sentiment": n.sentiment,
            "keywords": n.keywords,
            "depth": n.depth,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in pnodes
    ]
    # ---- alert_records：恢复预警关联所需的完整字段 ----
    arecords = db.query(AlertRecord).all()
    arecord_rows = [
        {
            "id": a.id,
            "rule_id": a.rule_id,
            "rule_name": a.rule_name,
            "risk_level": a.risk_level,
            "opinion_id": a.opinion_id,
            "opinion_title": a.opinion_title,
            "event_id": a.event_id,
            "event_title": a.event_title,
            "trigger_reason": a.trigger_reason,
            "handled": a.handled,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in arecords
    ]
    payload = {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "events": ev_rows,
        "event_opinions": link_rows,
        "propagation_nodes": pnode_rows,
        "alert_records": arecord_rows,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


# ---------------------------------------------------------------------------
# Alert 重链（复用 alert_service 的按 opinion_id 重链逻辑）
# ---------------------------------------------------------------------------
def _relink_alerts(db: Session) -> dict:
    """迁移后把 AlertRecord 按 opinion_id 重链到新 Event。

    优先复用 AlertService.sync_alert_events（幂等：只处理 event_id is None 的记录，
    不产生重复 AlertRecord）。随后统计重链 / orphan 数量，保证可观测。

    重链依据必须是 opinion_id（确定性外键），绝不使用标题模糊匹配。
    若 opinion_id 对应的 Opinion 在当前新规则下未物化为任何 Event
    （如 risk_score<40 的单条舆情），则该 AlertRecord 保持 event_id=None，
    显式记为 orphan，不允许静默丢失。
    """
    from app.services.alert_service import AlertService

    before_total = db.query(AlertRecord).count()
    before_null = (
        db.query(AlertRecord)
        .filter(AlertRecord.event_id.is_(None))
        .count()
    )
    # 复用既有逻辑（内部自行 commit）
    AlertService.sync_alert_events(db)
    # 重新统计（sync 后会话可能已提交，重新 query）
    after_relinked = (
        db.query(AlertRecord)
        .filter(AlertRecord.event_id.isnot(None))
        .count()
    )
    after_orphan = (
        db.query(AlertRecord)
        .filter(AlertRecord.event_id.is_(None))
        .count()
    )
    orphan_rows = [
        {
            "id": a.id,
            "opinion_id": a.opinion_id,
            "rule_id": a.rule_id,
            "reason": (
                "opinion_not_in_any_event"
                if a.opinion_id is not None
                else "opinion_id_null"
            ),
        }
        for a in db.query(AlertRecord)
        .filter(AlertRecord.event_id.is_(None))
        .all()
    ]
    return {
        "total": before_total,
        "before_event_id_null": before_null,
        "relinked": after_relinked,
        "orphan": after_orphan,
        "orphan_records": orphan_rows[:200],
    }


def _rebuild_propagation(db: Session, created_ids: List[int]) -> dict:
    """逐 Event 触发传播树重建，显式捕获并上报失败（不再静默吞掉）。

    设计（对应 Phase 4-Event-2A.6 §三.2）：
      - 主迁移事务已成功提交，传播重建属 best-effort；
      - 单个 Event 重建失败不应升级为全局事务失败（否则会让已提交的数据完整性修复白做）；
      - 但失败必须「可观测」：记录 event_id / 异常类型 / 异常信息 / traceback / 失败数；
      - 每个失败后立即 db.rollback()，重置会话待定状态，避免污染下一个 Event 的重建；
      - 最终明确区分：全部完成 / 部分成功 / 全部失败。
    """
    import traceback

    from app.services.propagation_service import PropagationService

    result = {
        "total": len(created_ids),
        "succeeded": [],
        "failed": [],
        "failed_count": 0,
    }
    for eid in created_ids:
        try:
            PropagationService.rebuild_for_event(db, eid)
            result["succeeded"].append(eid)
        except Exception as exc:  # noqa: BLE001 - 需要捕获一切以记录并继续
            # 重置会话，防止本事件未提交的残留状态影响后续
            try:
                db.rollback()
            except Exception:
                pass
            result["failed"].append(
                {
                    "event_id": eid,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                    "traceback": traceback.format_exc(limit=6),
                }
            )
            result["failed_count"] += 1
    # 汇总分类
    if result["failed_count"] == 0:
        result["status"] = "all_succeeded"
    elif result["failed_count"] == result["total"]:
        result["status"] = "all_failed"
    else:
        result["status"] = "partial"
    return result


# ---------------------------------------------------------------------------
# 一致性校验（只读 SELECT）
# ---------------------------------------------------------------------------
def consistency_check(db: Session) -> dict:
    """迁移后一致性校验（只读）：

    - 空 Event：opinion_count==0 或实际无 links
    - 孤儿 EventOpinion：指向不存在的 opinion / event
    - 重复 EventOpinion：同 (event_id, opinion_id) 多行
    - opinion_count 与真实 links 数不一致
    - 被关联 opinion_id 真实存在
    """
    events = db.query(Event).all()
    links = db.query(EventOpinion).all()
    opinion_ids = {o.id for o in db.query(Opinion.id).all()} if links else set()
    event_ids = {e.id for e in events}

    empty_events = [
        e.id
        for e in events
        if e.opinion_count == 0 or not any(l.event_id == e.id for l in links)
    ]
    orphan = [
        {"event_id": l.event_id, "opinion_id": l.opinion_id}
        for l in links
        if l.opinion_id not in opinion_ids or l.event_id not in event_ids
    ]
    seen: set = set()
    dup = 0
    for l in links:
        key = (l.event_id, l.opinion_id)
        if key in seen:
            dup += 1
        else:
            seen.add(key)
    cnt = Counter(l.event_id for l in links)
    count_mismatch = [
        {
            "event_id": e.id,
            "opinion_count_field": e.opinion_count,
            "actual_links": cnt.get(e.id, 0),
        }
        for e in events
        if cnt.get(e.id, 0) != e.opinion_count
    ]
    return {
        "empty_event_count": len(empty_events),
        "empty_event_ids": empty_events,
        "orphan_link_count": len(orphan),
        "orphan_links": orphan[:50],
        "duplicate_link_count": dup,
        "opinion_count_mismatch": count_mismatch,
    }


def _recompute_counts(db: Session) -> None:
    """用真实 EventOpinion 关联重算每个 Event 的 opinion_count。"""
    events = db.query(Event).all()
    if not events:
        return
    links = db.query(EventOpinion).all()
    cnt = Counter(l.event_id for l in links)
    for e in events:
        e.opinion_count = cnt.get(e.id, 0)


# ---------------------------------------------------------------------------
# 主入口：受控迁移
# ---------------------------------------------------------------------------
def migrate_events(
    db: Session,
    dry_run: bool = True,
    force: bool = False,
    allow_production: bool = False,
    cfg=settings,
    snapshot_dir: Optional[str] = None,
) -> dict:
    """受控 Event 全量重建迁移。

    dry_run=True（默认）：只运行 preflight，返回预测，绝对不写库。
    dry_run=False：需 force=True；生产库另需 allow_production=True。

    正式执行流程（单一事务）：
      1) preflight（只读，且与正式执行同源计算）
      2) 磁盘快照（审计记录，纯 SELECT 落盘；已扩展覆盖
         propagation_nodes / alert_records 完整字段）
      3) 解除引用 events 的外键（propagation_nodes / alert_records 置空）
      4) 全量 DELETE events / event_opinions
      5) 按 compute_new_events 重建 Event + EventOpinion（get-or-create）
      6) 一致性校验（失败则 rollback）
      7) commit；提交后再跑一次只读一致性校验
      8) 传播树重建（best-effort，逐 Event 显式捕获并上报失败，
         不再静默吞掉；失败不升级为全局事务回滚）
      9) AlertRecord 按 opinion_id 重链到新 Event（复用
         alert_service.sync_alert_events，幂等、可观测、orphan 显式记录）
    """
    # 1) preflight（只读）
    pf = preflight(db, cfg)

    if dry_run:
        pf["executed"] = False
        pf["dry_run"] = True
        return pf

    # 2) 守卫
    if not force:
        raise RuntimeError("正式迁移必须显式传入 force=True")
    db_name = _db_name(db)
    if db_name in PRODUCTION_DB_NAMES and not allow_production:
        raise RuntimeError(
            f"检测到连接生产库({db_name})；正式迁移需显式 allow_production=True 以确认。"
        )

    # 3) 磁盘快照（审计记录）
    snap_dir = snapshot_dir or os.path.join(
        tempfile.gettempdir(), "event_migration_snapshots"
    )
    snap_path = os.path.join(
        snap_dir,
        f"event_snapshot_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.json",
    )
    _snapshot_to_disk(db, snap_path)

    # 4) 单一事务
    try:
        # 4a) 解除外键引用（先置空，再删），避免 FK 约束失败
        db.query(PropagationNode).filter(
            PropagationNode.event_id.isnot(None)
        ).update(
            {"event_id": None, "parent_id": None}, synchronize_session=False
        )
        db.query(AlertRecord).filter(AlertRecord.event_id.isnot(None)).update(
            {"event_id": None, "event_title": ""}, synchronize_session=False
        )
        # 注意：DELETE 使用默认 synchronize_session="fetch"，
        # SQLAlchemy 会自动把被删实例从本会话身份映射中移除，
        # 避免后续 query 误返回这些 stale 对象（表现为空/孤儿 Event），
        # 也避免 ObjectDeletedError。
        db.query(EventOpinion).delete()
        db.query(Event).delete()

        # 4b) 重建
        plans = compute_new_events(db, cfg)
        # 一致性保证：preflight 与正式执行输入完全相同
        if len(plans) != pf["predicted_event_count"]:
            raise RuntimeError(
                "preflight 与正式执行计划不一致"
                f"（{pf['predicted_event_count']} != {len(plans)}）"
            )
        created_ids: List[int] = []
        for p in plans:
            ev = Event(
                title=p["title"],
                description=p["description"],
                keyword=p["keyword"],
                risk_level=p["risk_level"],
                opinion_count=len(p["member_ids"]),
                first_time=p["first_time"],
                last_time=p["last_time"],
            )
            db.add(ev)
            db.flush()
            created_ids.append(ev.id)
            existing = {
                r.opinion_id
                for r in db.query(EventOpinion)
                .filter(EventOpinion.event_id == ev.id)
                .all()
            }
            for oid in p["member_ids"]:
                if oid in existing:
                    continue
                db.add(EventOpinion(event_id=ev.id, opinion_id=oid))
                existing.add(oid)
            # 显式 flush：本项目 Session 可能关闭 autoflush，
            # 必须在一致性校验前把 links 落库，否则校验看不到新建关联。
            db.flush()

        # 4c) 用真实 links 重算 opinion_count，确保与字段一致
        _recompute_counts(db)
        check = consistency_check(db)
        if (
            check["empty_event_count"] > 0
            or check["orphan_link_count"] > 0
            or check["duplicate_link_count"] > 0
            or check["opinion_count_mismatch"]
        ):
            raise RuntimeError(f"迁移后一致性校验失败：{check}")

        # 4d) 提交
        db.commit()
    except Exception:
        db.rollback()
        raise

    # 5) 提交后再跑一次只读一致性校验
    post = consistency_check(db)
    # 6) 传播树重建（best-effort，显式可观测，见 _rebuild_propagation）
    propagation_rebuild = _rebuild_propagation(db, created_ids)
    # 7) AlertRecord 按 opinion_id 重链（复用 alert_service，可观测）
    alert_relink = _relink_alerts(db)

    result = dict(pf)
    result["executed"] = True
    result["dry_run"] = False
    result["snapshot_path"] = snap_path
    result["post_migration_consistency"] = post
    result["created_event_count"] = len(created_ids)
    result["propagation_rebuild"] = propagation_rebuild
    result["alert_relink"] = alert_relink
    return result


# 便于外部直接引用（保持与 aggregator 命名一致）。
__all__ = ["preflight", "migrate_events", "compute_new_events", "consistency_check"]
