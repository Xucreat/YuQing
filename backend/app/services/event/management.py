"""国内事件 合并 / 拆分 处置服务（Phase 事件处置增强）。

与外网 ForeignEventService.merge_events / split_event 对齐，但作用于国内
events / event_opinions 表，并复用既有风险/热度服务重算指标。

操作语义：
- 合并(merge)：把 source 事件的全部关联舆情迁移到 target 事件；source 置为
  archived（已归档）；双方指标（opinion_count / first_time / last_time / 风险 /
  热度）重算；写入 merge 动作记录。
- 拆分(split)：把指定舆情从原事件迁出，新建一个 active 事件承载；原事件至少
  保留一条舆情；双方指标重算；写入 split 动作记录。
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_action import EventAction
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.event.heat_service import EventHeatService
from app.services.event.risk_service import EventRiskService


class EventManagementService:
    # ------------------------------------------------------------------ #
    # 指标重算（复用聚合器的口径：风险取舆情集合分、热度走 EventHeatService）
    # ------------------------------------------------------------------ #
    def _recompute(self, db: Session, event: Optional[Event]) -> None:
        if event is None:
            return
        linked = (
            db.query(EventOpinion)
            .filter(EventOpinion.event_id == event.id)
            .all()
        )
        opinion_ids = [row.opinion_id for row in linked]
        opinions: list[Opinion] = (
            db.query(Opinion).filter(Opinion.id.in_(opinion_ids)).all()
            if opinion_ids
            else []
        )
        event.opinion_count = len(opinions)
        times = [o.publish_time for o in opinions if o.publish_time is not None]
        if times:
            event.first_time = min(times)
            event.last_time = max(times)
        if opinions:
            score = EventRiskService.score_from_opinions(opinions)
            event.risk_score = EventRiskService.clamp_score(score)
            event.risk_level = EventRiskService.level_from_score(event.risk_score)
        # 热度（含趋势）走既有服务
        try:
            EventHeatService().refresh(db, event)
        except Exception:
            # 热度重算失败不应阻断合并/拆分主流程
            pass

    # ------------------------------------------------------------------ #
    # 合并
    # ------------------------------------------------------------------ #
    def merge_events(
        self,
        db: Session,
        source_id: int,
        target_id: int,
        *,
        user_id: Optional[int] = None,
        reason: str = "",
    ) -> Event:
        if source_id == target_id:
            raise ValueError("source and target event must differ")
        source = db.get(Event, source_id)
        target = db.get(Event, target_id)
        if source is None or target is None:
            raise LookupError("Event not found")

        links = (
            db.query(EventOpinion)
            .filter(EventOpinion.event_id == source.id)
            .all()
        )
        existing_ids = set(
            rid
            for (rid,) in db.query(EventOpinion.opinion_id)
            .filter(EventOpinion.event_id == target.id)
            .all()
        )
        for link in links:
            if link.opinion_id in existing_ids:
                # 目标已关联该舆情，避免违反唯一约束 → 直接删除源侧冗余关联
                db.delete(link)
                continue
            link.event_id = target.id

        old_status = source.status
        source.status = "archived"
        db.add(
            EventAction(
                event_id=source.id,
                user_id=user_id,
                action_type="merge",
                content=f"合并至事件 #{target.id}。{reason}".strip(),
                old_status=old_status,
                new_status="archived",
            )
        )
        db.commit()
        self._recompute(db, target)
        self._recompute(db, source)
        db.commit()
        db.refresh(target)
        db.refresh(source)
        return target

    # ------------------------------------------------------------------ #
    # 拆分
    # ------------------------------------------------------------------ #
    def split_event(
        self,
        db: Session,
        event_id: int,
        opinion_ids: list[int],
        *,
        user_id: Optional[int] = None,
        reason: str = "",
    ) -> Event:
        event = db.get(Event, event_id)
        if event is None:
            raise LookupError("Event not found")
        if not opinion_ids:
            raise ValueError("opinion_ids must not be empty")

        links = (
            db.query(EventOpinion)
            .filter(
                EventOpinion.event_id == event.id,
                EventOpinion.opinion_id.in_(opinion_ids),
            )
            .all()
        )
        if not links:
            raise ValueError("所选舆情均不属于该事件")
        current_count = (
            db.query(func.count(EventOpinion.id))
            .filter(EventOpinion.event_id == event.id)
            .scalar()
            or 0
        )
        if len(links) >= int(current_count):
            raise ValueError("拆分至少需在原事件中保留一条舆情")

        opinions = (
            db.query(Opinion)
            .filter(Opinion.id.in_([link.opinion_id for link in links]))
            .all()
        )
        representative = opinions[0] if opinions else event
        new_event = Event(
            title=getattr(representative, "title", None) or event.title,
            description=event.description,
            keyword=getattr(representative, "keyword", "") or "",
            risk_level=event.risk_level,
            region_id=getattr(representative, "region_id", None),
            topic_category=getattr(representative, "topic_category", None)
            or event.topic_category,
            heat_score=event.heat_score,
            trend=event.trend,
            status="active",
            opinion_count=0,
            first_time=getattr(representative, "publish_time", None),
            last_time=getattr(representative, "publish_time", None),
            confirmation_source=event.confirmation_source,
            confirmation_version=event.confirmation_version,
        )
        db.add(new_event)
        db.flush()
        for link in links:
            link.event_id = new_event.id
        db.add(
            EventAction(
                event_id=event.id,
                user_id=user_id,
                action_type="split",
                content=(
                    f"拆分 {len(links)} 条舆情至新事件 #{new_event.id}。{reason}"
                ).strip(),
            )
        )
        db.commit()
        self._recompute(db, event)
        self._recompute(db, new_event)
        db.commit()
        db.refresh(new_event)
        return new_event
