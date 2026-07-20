"""Event 规则聚合器（Phase 3C-0）。

激活既有 Event / event_opinions 基础设施（0001_initial 已建表），
**不做任何表结构改动、不新增 migration**。

聚合策略（规则、可解释、无 AI / 无聚类算法 / 无图数据库）：
  1. 读取最近 EVENT_WINDOW_DAYS 天内、analysis_status=completed、keywords 非空的 Opinion；
  2. 按 region_id 分组；
  3. 组内两两比较 keywords（逗号分隔），有任一交集则归为同一事件
     （连通分量聚类，O(n^2)，MVP 数据量 <10000 可接受）；
  4. 每组检查是否已有对应 Event（按 keyword 交集匹配）；
  5. 无对应 Event → 创建新 Event；
  6. 已有对应 Event → 显式追加 EventOpinion 关联（已有关联跳过），
     并重新计算派生字段；
  7. 返回 {"created": N, "updated": N, "linked": N}。

约束遵守：
  - 仅通过 EventOpinion(event_id=..., opinion_id=...) 显式建关联；
    不使用 relationship.append()，不修改关联表结构。
  - event_opinions 表保持现状（无 created_at / unique 约束）。
  - status 字段仅存在于 API Schema 层，本模块不写 Event.status（Model 无该列）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _keywords_set(keywords: str) -> set[str]:
    return {k.strip() for k in (keywords or "").split(",") if k.strip()}


def _map_risk_level(max_score: int) -> str:
    """Event.risk_level 映射：>=70 high / >=40 medium / else low。"""
    if max_score >= 70:
        return "high"
    if max_score >= 40:
        return "medium"
    return "low"


class EventAggregator:
    """将 Opinion 按规则聚合成 Event（只读既有 Model，不改表结构）。"""

    # ----- 对外接口 -----------------------------------------------------
    def aggregate(self, db: Session) -> dict:
        """执行一次聚合，返回统计字典 {"created","updated","linked"}。"""
        cutoff = _now_utc() - timedelta(days=settings.event_window_days)
        opinions = (
            db.query(Opinion)
            .filter(
                Opinion.analysis_status == "completed",
                Opinion.keywords.isnot(None),
                Opinion.keywords != "",
                Opinion.created_at >= cutoff,
            )
            .all()
        )

        created = 0
        created_ids: set[int] = set()
        updated_ids: set[int] = set()
        linked = 0

        # 按 region 分组后再聚类（仅同 region 内允许合并）
        by_region: dict[int, list[Opinion]] = {}
        for op in opinions:
            by_region.setdefault(op.region_id, []).append(op)

        for _region_id, ops in by_region.items():
            clusters = self._cluster_by_keywords(ops)
            for cluster in clusters:
                merged_kw = self._merge_keywords(cluster)
                existing = self._find_existing_event(db, merged_kw)
                if existing is None:
                    event = self._create_event(db, cluster)
                    db.flush()
                    created += 1
                    created_ids.add(event.id)
                    linked += self._link_all(db, event.id, cluster)
                else:
                    n = self._link_all(db, existing.id, cluster)
                    if n > 0:
                        updated_ids.add(existing.id)
                        linked += n
                        self._recompute_event(db, existing, cluster)

        db.commit()

        # P2: auto-trigger propagation rebuild for created & updated events
        try:
            from app.services.propagation_service import PropagationService
            for eid in created_ids:
                try:
                    PropagationService.rebuild_for_event(db, eid)
                except ValueError:
                    pass
            for eid in updated_ids:
                try:
                    PropagationService.rebuild_for_event(db, eid)
                except ValueError:
                    pass
        except Exception:
            pass

        return {
            "created": created,
            "updated": len(updated_ids),
            "linked": linked,
        }

    # ----- 聚类 ---------------------------------------------------------
    @staticmethod
    def _cluster_by_keywords(ops: list[Opinion]) -> list[list[Opinion]]:
        """同 region 内按 keywords 交集做连通分量聚类（O(n^2)）。"""
        n = len(ops)
        if n == 0:
            return []
        kw = {op.id: _keywords_set(op.keywords) for op in ops}
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i in range(n):
            for j in range(i + 1, n):
                if kw[ops[i].id] & kw[ops[j].id]:
                    union(i, j)

        groups: dict[int, list[Opinion]] = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(ops[i])
        return list(groups.values())

    @staticmethod
    def _merge_keywords(cluster: Iterable[Opinion]) -> set[str]:
        merged: set[str] = set()
        for op in cluster:
            merged |= _keywords_set(op.keywords)
        return merged

    # ----- 既有 Event 匹配 ----------------------------------------------
    def _find_existing_event(
        self, db: Session, merged_kw: set[str]
    ) -> Optional[Event]:
        """按 keyword 交集匹配既有 Event（取首个命中）。"""
        if not merged_kw:
            return None
        events = db.query(Event).all()
        for ev in events:
            if _keywords_set(ev.keyword) & merged_kw:
                return ev
        return None

    # ----- Event 创建 / 更新 --------------------------------------------
    @staticmethod
    def _pick_top_risk(cluster: list[Opinion]) -> Opinion:
        return max(cluster, key=lambda o: o.risk_score)

    def _create_event(self, db: Session, cluster: list[Opinion]) -> Event:
        top = self._pick_top_risk(cluster)
        merged_kw = sorted(self._merge_keywords(cluster))
        times = [op.created_at for op in cluster if op.created_at is not None]
        event = Event(
            title=top.title,
            description=(top.content or "")[:200],
            keyword=",".join(merged_kw),
            risk_level=_map_risk_level(max(op.risk_score for op in cluster)),
            opinion_count=len(cluster),
            first_time=min(times) if times else None,
            last_time=max(times) if times else None,
        )
        db.add(event)
        return event

    def _link_all(
        self, db: Session, event_id: int, cluster: list[Opinion]
    ) -> int:
        """显式创建 EventOpinion 关联；已存在则跳过。返回新建关联数。"""
        existing_ids = {
            row.opinion_id
            for row in db.query(EventOpinion)
            .filter(EventOpinion.event_id == event_id)
            .all()
        }
        added = 0
        for op in cluster:
            if op.id in existing_ids:
                continue
            db.add(EventOpinion(event_id=event_id, opinion_id=op.id))
            existing_ids.add(op.id)
            added += 1
        return added

    def _recompute_event(
        self, db: Session, event: Event, _new_cluster: list[Opinion]
    ) -> None:
        """重算 opinion_count / last_time / risk_level / keyword（并集）。"""
        linked = (
            db.query(EventOpinion)
            .filter(EventOpinion.event_id == event.id)
            .all()
        )
        opinion_ids = [row.opinion_id for row in linked]
        opinions = db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).all()
        if not opinions:
            return
        event.opinion_count = len(opinions)
        times = [o.created_at for o in opinions if o.created_at is not None]
        if times:
            event.last_time = max(times)
        event.risk_level = _map_risk_level(max(o.risk_score for o in opinions))
        merged = self._merge_keywords(opinions)
        if merged:
            event.keyword = ",".join(sorted(merged))
