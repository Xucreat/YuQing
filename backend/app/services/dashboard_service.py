"""Dashboard 统计服务层（Phase 2B）。

职责：
  - 所有驾驶舱统计逻辑集中在此，router 不直接写 SQL 聚合。
  - 返回纯数据结构（dict），由 API 层序列化为 DashboardStatsResponse。

设计要点：
  - 日期口径统一使用数据库原生日期函数（current_date / cast(... as date)），
    避免 Python 侧时区与 naive TIMESTAMP 列之间的歧义。
  - 高风险口径：risk_score >= HIGH_RISK_THRESHOLD（当前 70），
    集中为常量，便于后续调整；不使用 sentiment 字段表达风险。
  - 关键词来自 opinions.keywords（TEXT 逗号分隔），在 Python 侧拆分后计数。
  - 全部为聚合/批量查询，无 N+1。
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import cast, Date, func, select
from sqlalchemy.orm import Session

from app.models.opinion import Opinion

# 高风险阈值：risk_score >= 此值记为高风险
HIGH_RISK_THRESHOLD = 70
# 趋势窗口天数
TREND_DAYS = 7
# 关键词 TOP 数量
TOP_KEYWORDS = 10


def get_dashboard_stats(db: Session) -> dict:
    """计算驾驶舱统计，返回 dict：

    {
      "total": int,
      "today": int,
      "high_risk": int,
      "trend": [{"date": "2026-07-16", "count": int}, ...],  # 长度 = TREND_DAYS
      "keywords": [{"word": str, "count": int}, ...],          # 长度 <= TOP_KEYWORDS
    }
    """
    # 1) 总数
    total = db.scalar(select(func.count(Opinion.id))) or 0

    # 2) 今日新增（依据 created_at，非 publish_time）
    today = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                cast(Opinion.created_at, Date) == func.current_date()
            )
        )
        or 0
    )

    # 3) 高风险（risk_score >= 阈值）
    high_risk = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                Opinion.risk_score >= HIGH_RISK_THRESHOLD
            )
        )
        or 0
    )

    # 4) 近 TREND_DAYS 日趋势（无数据日期补齐 count=0）
    today_date: date = db.scalar(select(func.current_date()))
    window_start = today_date - timedelta(days=TREND_DAYS - 1)

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
        for i in range(TREND_DAYS)
    ]

    # 5) TOP 关键词（opinions.keywords 逗号拆分后计数）
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
        "trend": trend,
        "keywords": keywords,
    }
