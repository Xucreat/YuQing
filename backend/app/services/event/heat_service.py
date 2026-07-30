"""Lightweight event heat and trend calculation for Phase 2-B."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion


TREND_RISING = "rising"
TREND_STABLE = "stable"
TREND_FALLING = "falling"
TREND_UNKNOWN = "unknown"


@dataclass(frozen=True)
class EventHeatMetrics:
    heat_score: int
    trend: str
    reason: dict[str, int]


def _as_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _effective_time(opinion: Opinion) -> Optional[datetime]:
    return _as_naive_utc(opinion.publish_time or opinion.created_at)


def _engagement_sum(opinion: Opinion) -> int:
    engagement = opinion.engagement or {}
    if not isinstance(engagement, dict):
        return 0
    total = 0
    for key in ("likes", "comments", "reposts", "shares"):
        value = engagement.get(key, 0)
        try:
            total += max(0, int(value or 0))
        except (TypeError, ValueError):
            continue
    return total


def _trend(recent_count: int, previous_7d_count: int, total_count: int) -> str:
    """Compare the latest day with the preceding seven-day daily average."""
    if total_count < 2:
        return TREND_UNKNOWN
    if previous_7d_count == 0:
        return TREND_RISING if recent_count >= 2 else TREND_UNKNOWN

    daily_average = previous_7d_count / 7
    ratio = recent_count / daily_average
    if ratio >= 1.5:
        return TREND_RISING
    if ratio <= 0.5:
        return TREND_FALLING
    return TREND_STABLE


def calculate_event_heat(
    opinions: Iterable[Opinion], now: Optional[datetime] = None
) -> EventHeatMetrics:
    """Calculate explainable, bounded event metrics from linked opinions."""
    rows = list(opinions)
    current = _as_naive_utc(now) or datetime.now(timezone.utc).replace(tzinfo=None)
    recent_start = current - timedelta(days=1)
    previous_start = current - timedelta(days=8)

    recent_24h_count = 0
    previous_7d_count = 0
    engagement_sum = 0
    for opinion in rows:
        point = _effective_time(opinion)
        if point is not None:
            if recent_start <= point <= current:
                recent_24h_count += 1
            elif previous_start <= point < recent_start:
                previous_7d_count += 1
        engagement_sum += _engagement_sum(opinion)

    quantity_contribution = min(40, len(rows) * 4)
    recent_contribution = min(35, recent_24h_count * 7)
    engagement_contribution = min(25, engagement_sum // 100)
    heat_score = min(
        100,
        quantity_contribution + recent_contribution + engagement_contribution,
    )
    return EventHeatMetrics(
        heat_score=heat_score,
        trend=_trend(recent_24h_count, previous_7d_count, len(rows)),
        reason={
            "opinion_count": len(rows),
            "recent_24h_count": recent_24h_count,
            "previous_7d_count": previous_7d_count,
            "engagement_sum": engagement_sum,
        },
    )


class EventHeatService:
    """Read linked opinions and persist the current event heat metrics."""

    @staticmethod
    def _load_opinions(db: Session, event_id: int) -> list[Opinion]:
        return (
            db.query(Opinion)
            .join(EventOpinion, EventOpinion.opinion_id == Opinion.id)
            .filter(EventOpinion.event_id == event_id)
            .all()
        )

    def refresh(
        self, db: Session, event: Event, now: Optional[datetime] = None
    ) -> EventHeatMetrics:
        opinions = self._load_opinions(db, event.id)
        metrics = calculate_event_heat(opinions, now=now)
        event.heat_score = metrics.heat_score
        event.trend = metrics.trend
        return metrics


__all__ = [
    "EventHeatMetrics",
    "EventHeatService",
    "TREND_RISING",
    "TREND_STABLE",
    "TREND_FALLING",
    "TREND_UNKNOWN",
    "calculate_event_heat",
]
