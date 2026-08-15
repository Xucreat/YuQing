"""Read-only foreign-event situation aggregation mirroring the domestic EventSituationService.

Foreign opinions use ``published_at`` (not ``publish_time``) and ``source_name_snapshot``
(not ``source``); we adapt them when feeding the generic ``EventRiskShadowService``.
The returned shape matches the domestic ``/events/{id}/situation`` response so the
shared frontend component can render both scopes identically.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_opinion import ForeignOpinion
from app.services.event.risk_shadow import EventRiskShadowService


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class ForeignEventSituationService:
    def __init__(self, *, stale_after_days: int = 7) -> None:
        self.stale_after_days = stale_after_days

    def build(self, db: Session, event_id: int) -> dict | None:
        event = db.get(ForeignEvent, event_id)
        if event is None:
            return None
        opinions = list(
            db.scalars(
                select(ForeignOpinion)
                .join(ForeignEventOpinion, ForeignEventOpinion.foreign_opinion_id == ForeignOpinion.id)
                .where(ForeignEventOpinion.foreign_event_id == event_id)
                .order_by(ForeignOpinion.published_at.asc().nullslast(), ForeignOpinion.id.asc())
            ).all()
        )
        now = datetime.now(timezone.utc)
        times = [_utc(o.published_at) for o in opinions if o.published_at]
        source_counts = Counter((o.source_name_snapshot or o.source_key or "未知") for o in opinions)
        daily = Counter(t.date().isoformat() for t in times)
        first_time = min(times) if times else None
        last_time = max(times) if times else None
        coverage_days = ((last_time - first_time).days + 1) if first_time and last_time else 0
        opinion_count = len(opinions)
        source_count = len(source_counts)

        if not opinions:
            sufficiency = {"level": "insufficient", "opinion_count": 0, "source_count": 0, "reason": "事件暂无关联舆情"}
        elif opinion_count < 3 or source_count < 2:
            sufficiency = {"level": "limited", "opinion_count": opinion_count, "source_count": source_count, "reason": "样本量或来源覆盖不足"}
        else:
            sufficiency = {"level": "sufficient", "opinion_count": opinion_count, "source_count": source_count, "reason": "样本量和来源覆盖满足基础研判"}

        # risk distribution by current_risk_score (thresholds mirror domestic semantics)
        risk_dist = {"high": 0, "medium": 0, "low": 0}
        for o in opinions:
            score = o.current_risk_score or 0
            if score >= 70:
                risk_dist["high"] += 1
            elif score >= 40:
                risk_dist["medium"] += 1
            else:
                risk_dist["low"] += 1

        statistics = {
            "opinion_count": opinion_count,
            "source_count": source_count,
            "risk_distribution": risk_dist,
        }

        # feed the generic risk shadow (adapt attribute names)
        adapted = [
            SimpleNamespace(
                current_risk_score=o.current_risk_score or 0,
                risk_score=o.current_risk_score or 0,
                publish_time=o.published_at,
                region_id=None,
                topic_category=None,
            )
            for o in opinions
        ]
        risk_shadow = EventRiskShadowService.calculate(event, adapted)

        negative_count = 0  # foreign opinions have no sentiment field
        heat = {
            "opinion_count": opinion_count,
            "source_count": source_count,
            "negative_count": negative_count,
            "negative_ratio": 0,
            "risk_shadow_score": risk_shadow["score"],
        }
        sources = [{"source": s, "count": c} for s, c in source_counts.most_common()]
        daily_items = [{"date": k, "count": daily[k]} for k in sorted(daily)]
        trend = self._trend(daily_items)
        stale_sources = [
            {"source": s, "last_valid_data_time": None, "reason": "超过数据新鲜度窗口"}
            for s in source_counts
            if not any(
                o.published_at and now - _utc(o.published_at) <= timedelta(days=self.stale_after_days)
                for o in opinions
                if (o.source_name_snapshot or o.source_key or "未知") == s
            )
        ]
        return {
            "statistics": statistics,
            "situation": {
                "event_id": event_id,
                "data_window": {
                    "first_time": first_time.isoformat() if first_time else None,
                    "last_time": last_time.isoformat() if last_time else None,
                    "start": first_time.isoformat() if first_time else None,
                    "end": last_time.isoformat() if last_time else None,
                    "coverage_days": coverage_days,
                },
                "data_sufficiency": sufficiency,
                "source_distribution": sources,
                "source_distribution_map": dict(source_counts),
                "daily_counts": daily_items,
                "keyword_distribution": [],
                "keyword_counts": [],
                "risk_factors": risk_shadow["factors"],
                "heat_summary": heat,
                "heat": heat,
                "trend_summary": trend,
                "trend": trend,
                "stale_sources": stale_sources,
                "risk_shadow": risk_shadow,
                "risk": risk_shadow,
            },
        }

    @staticmethod
    def _trend(daily_items: list[dict]) -> dict:
        if len(daily_items) < 2:
            return {"direction": "unknown", "description": "时间序列样本不足"}
        midpoint = max(1, len(daily_items) // 2)
        before = sum(item["count"] for item in daily_items[:midpoint])
        after = sum(item["count"] for item in daily_items[midpoint:])
        direction = "rising" if after > before else "falling" if after < before else "stable"
        return {
            "direction": direction,
            "before_count": before,
            "after_count": after,
            "description": {
                "rising": "后期内容量高于前期",
                "falling": "后期内容量低于前期",
                "stable": "前后期内容量接近",
            }[direction],
        }
