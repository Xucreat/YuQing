"""Read-only event situation aggregation based on existing opinion links."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.event.risk_shadow import EventRiskShadowService


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class EventSituationService:
    def __init__(self, *, stale_after_days: int = 7) -> None:
        self.stale_after_days = stale_after_days

    def build(self, db: Session, event_id: int) -> dict | None:
        event = db.get(Event, event_id)
        if event is None:
            return None
        opinions = list(
            db.scalars(
                select(Opinion)
                .join(EventOpinion, EventOpinion.opinion_id == Opinion.id)
                .where(EventOpinion.event_id == event_id)
                .order_by(Opinion.publish_time.asc().nullslast(), Opinion.id.asc())
            ).all()
        )
        now = datetime.now(timezone.utc)
        times = [_utc(row.publish_time) for row in opinions if row.publish_time]
        source_counts = Counter((row.source or "未知") for row in opinions)
        daily = Counter(value.date().isoformat() for value in times)
        keywords = Counter()
        for row in opinions:
            for keyword in (row.keywords or "").replace("，", ",").split(","):
                keyword = keyword.strip()
                if keyword:
                    keywords[keyword] += 1
        first_time = min(times) if times else None
        last_time = max(times) if times else None
        coverage_days = ((last_time - first_time).days + 1) if first_time and last_time else 0
        if not opinions:
            sufficiency = {"level": "insufficient", "opinion_count": 0, "source_count": 0, "reason": "事件暂无关联舆情"}
        elif len(opinions) < 3 or len(source_counts) < 2:
            sufficiency = {"level": "limited", "opinion_count": len(opinions), "source_count": len(source_counts), "reason": "样本量或来源覆盖不足"}
        else:
            sufficiency = {"level": "sufficient", "opinion_count": len(opinions), "source_count": len(source_counts), "reason": "样本量和来源覆盖满足基础研判"}

        risk_shadow = EventRiskShadowService.calculate(event, opinions)
        negative_count = sum(1 for row in opinions if (row.sentiment or "").lower() in {"negative", "负面"})
        daily_items = [{"date": key, "count": daily[key]} for key in sorted(daily)]
        trend = self._trend(daily_items)
        heat = {"opinion_count": len(opinions), "source_count": len(source_counts), "negative_count": negative_count, "negative_ratio": round(negative_count / len(opinions), 4) if opinions else 0, "risk_shadow_score": risk_shadow["score"]}
        sources = [{"source": source, "count": count} for source, count in source_counts.most_common()]
        keyword_items = [{"keyword": keyword, "count": count} for keyword, count in keywords.most_common()]
        stale_sources = [
            {"source": source, "last_valid_data_time": max((_utc(row.publish_time) for row in opinions if (row.source or "未知") == source and row.publish_time), default=None).isoformat() if any((row.source or "未知") == source and row.publish_time for row in opinions) else None, "reason": "超过数据新鲜度窗口"}
            for source in source_counts
            if not any((row.source or "未知") == source and row.publish_time and now - _utc(row.publish_time) <= timedelta(days=self.stale_after_days) for row in opinions)
        ]
        return {
            "event_id": event_id,
            "data_window": {"first_time": first_time.isoformat() if first_time else None, "last_time": last_time.isoformat() if last_time else None, "start": first_time.isoformat() if first_time else None, "end": last_time.isoformat() if last_time else None, "coverage_days": coverage_days},
            "data_sufficiency": sufficiency,
            "source_distribution": sources,
            "source_distribution_map": dict(source_counts),
            "daily_counts": daily_items,
            "keyword_distribution": keyword_items,
            "keyword_counts": keyword_items,
            "risk_factors": risk_shadow["factors"],
            "heat_summary": heat,
            "heat": heat,
            "trend_summary": trend,
            "trend": trend,
            "stale_sources": stale_sources,
            "risk_shadow": risk_shadow,
            "risk": risk_shadow,
        }

    @staticmethod
    def _trend(daily_items: list[dict]) -> dict:
        if len(daily_items) < 2:
            return {"direction": "unknown", "description": "时间序列样本不足"}
        midpoint = max(1, len(daily_items) // 2)
        before = sum(item["count"] for item in daily_items[:midpoint])
        after = sum(item["count"] for item in daily_items[midpoint:])
        direction = "rising" if after > before else "falling" if after < before else "stable"
        return {"direction": direction, "before_count": before, "after_count": after, "description": {"rising": "后期内容量高于前期", "falling": "后期内容量低于前期", "stable": "前后期内容量接近"}[direction]}

    calculate = build
    get_situation = build
