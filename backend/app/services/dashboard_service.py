"""Dashboard stats service layer (Phase 2B)."""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import cast, Date, func, select
from sqlalchemy.orm import Session

from app.models.opinion import Opinion
from app.models.event import Event
from app.models.region import Region

HIGH_RISK_THRESHOLD = 70
TREND_DAYS = 7
TOP_KEYWORDS = 10
TOP_REGIONS = 10


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

    # P0: source distribution
    from sqlalchemy import func as sfunc, select as sselect
    source_rows = db.execute(
        select(Opinion.source, sfunc.count(Opinion.id))
        .group_by(Opinion.source)
        .order_by(sfunc.count(Opinion.id).desc())
        .limit(10)
    ).all()
    sources = [{"source": s or "未知", "count": c} for s, c in source_rows]

    # P0: sentiment distribution
    sentiment_rows = db.execute(
        select(Opinion.sentiment, sfunc.count(Opinion.id))
        .group_by(Opinion.sentiment)
    ).all()
    sentiments = [{"label": s, "count": c} for s, c in sentiment_rows]

    # P2 指挥大屏：地理分布（按地区聚合舆情数量）
    region_rows = db.execute(
        select(Region.id, Region.name, sfunc.count(Opinion.id))
        .join(Opinion, Opinion.region_id == Region.id)
        .group_by(Region.id, Region.name)
        .order_by(sfunc.count(Opinion.id).desc())
        .limit(TOP_REGIONS)
    ).all()
    regions = [
        {"region_id": rid, "region_name": rname or "未知", "count": c}
        for rid, rname, c in region_rows
    ]

    return {
        "total": total,
        "today": today,
        "high_risk": high_risk,
        "event_count": event_count,
        "trend": trend,
        "keywords": keywords,
        "sources": sources,
        "sentiments": sentiments,
        "regions": regions,
    }
