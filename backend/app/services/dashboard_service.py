"""Dashboard stats service layer (Phase 2B)."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import cast, Date, func, select
from sqlalchemy.orm import Session

from app.models.opinion import Opinion
from app.models.event import Event

HIGH_RISK_THRESHOLD = 70
TREND_DAYS = 7
TOP_KEYWORDS = 10


def get_dashboard_stats(db: Session, days: int = 7) -> dict:
    """Compute dashboard summary statistics."""
    total = db.scalar(select(func.count(Opinion.id))) or 0

    today = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                cast(Opinion.created_at, Date) == func.current_date()
            )
        )
        or 0
    )

    high_risk = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                Opinion.risk_score >= HIGH_RISK_THRESHOLD
            )
        )
        or 0
    )

    event_count = db.scalar(select(func.count(Event.id))) or 0

    today_date: date = db.scalar(select(func.current_date()))
    window_start = today_date - timedelta(days=days - 1)

    trend_rows = db.execute(
        select(
            cast(Opinion.created_at, Date).label("day"),
            func.count(Opinion.id).label("cnt"),
        )
        .where(cast(Opinion.created_at, Date) >= window_start)
        .group_by(cast(Opinion.created_at, Date))
        .order_by("day")
    ).all()
    counts = {row.day: row.cnt for row in trend_rows}
    trend = [
        {
            "date": (window_start + timedelta(days=i)).isoformat(),
            "count": counts.get(window_start + timedelta(days=i), 0),
        }
        for i in range(days)
    ]

    raw_keywords = db.execute(select(Opinion.keywords)).scalars().all()
    counter: Counter = Counter()
    for raw in raw_keywords:
        for kw in (raw or "").split(","):
            kw = kw.strip()
            if kw:
                counter[kw] += 1
    keywords = [
        {"word": word, "count": count}
        for word, count in counter.most_common(TOP_KEYWORDS)
    ]

    return {
        "total": total,
        "today": today,
        "high_risk": high_risk,
        "event_count": event_count,
        "trend": trend,
        "keywords": keywords,
    }
