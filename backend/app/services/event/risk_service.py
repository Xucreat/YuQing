"""Event 风险分统一计算服务。

事件风险分以当前 EventOpinion 关联的 Opinion 风险分为准；没有关联舆情的
历史事件保留 events.risk_score，避免破坏旧数据的既有 API 行为。
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion


class EventRiskService:
    """提供事件风险分的 Python 计算和 SQL 查询表达式。"""

    @staticmethod
    def clamp_score(score: int | None) -> int:
        return max(0, min(100, int(score or 0)))

    @classmethod
    def score_from_opinions(cls, opinions: Iterable[Opinion]) -> int:
        return max((cls.clamp_score(op.risk_score) for op in opinions), default=0)

    @staticmethod
    def level_from_score(score: int | None) -> str:
        normalized = EventRiskService.clamp_score(score)
        if normalized >= 70:
            return "high"
        if normalized >= 40:
            return "medium"
        return "low"

    @staticmethod
    def level_expression(score_expression):
        return case(
            (score_expression >= 70, "high"),
            (score_expression >= 40, "medium"),
            else_="low",
        )

    @staticmethod
    def score_expression():
        """返回可用于 Event 列表筛选、排序和返回值的关联风险分表达式。

        关联舆情存在时取其最高分；没有关联舆情时回退到 events.risk_score，
        兼容历史手工事件和旧数据。
        """
        clamped = case(
            (Opinion.risk_score < 0, 0),
            (Opinion.risk_score > 100, 100),
            else_=Opinion.risk_score,
        )
        linked_max = (
            select(func.max(clamped))
            .select_from(EventOpinion)
            .join(Opinion, Opinion.id == EventOpinion.opinion_id)
            .where(EventOpinion.event_id == Event.id)
            .correlate(Event)
            .scalar_subquery()
        )
        return func.coalesce(linked_max, Event.risk_score, 0)

    @classmethod
    def get_score(cls, db: Session, event_id: int) -> int:
        score = db.execute(
            select(cls.score_expression()).where(Event.id == event_id)
        ).scalar_one()
        return cls.clamp_score(score)
