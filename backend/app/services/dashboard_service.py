"""Dashboard stats service layer (指挥大屏 Phase 1 数据契约修正)。

数据契约（GET /api/dashboard/stats?days=N）：
  - total        累计指标：系统全部舆情数量（count(opinions.id)），不受 days 影响。
  - event_count  累计指标：当前事件总量（count(events.id)），不受 days 影响。
  - today        当日指标：今日（依据 created_at，非 publish_time）新增舆情数。
  - high_risk    累计指标（业务语义：系统高危态势）：risk_score >= 阈值的舆情总数，
                  统计全量而非 days 窗口。理由：KPI「高危舆情」表达的是系统整体风险水位，
                  与「今日/近 N 日」窗口无关。如需窗口化请在产品侧确认后调整。
  - trend        时间窗口指标：最近 days 日每日增量（无数据日期 count=0，已补齐）。
  - sentiments   时间窗口指标：窗口内情感分布（created_at >= window_start）。
  - sources      时间窗口指标：窗口内来源分布（Top，created_at >= window_start）。
  - regions      时间窗口指标 + 省级上卷：窗口内按省级聚合的舆情分布（见 _rollup_provinces）。
  - keywords     [兼容字段，保留] 来自 opinions.keywords（规则命中的敏感词集合），
                  全量统计，供旧 Dashboard 词云使用；指挥大屏请勿使用本字段。
  - hot_keywords 时间窗口指标：基于监测关键词表对窗口内 title+content 的真实提及频次，
                  指挥大屏「热门关键词」请使用本字段。

注意：未把所有字段统一成 days 窗口——累计/当日/窗口三类指标口径互斥，强行统一会丢失语义。
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta

from sqlalchemy import (
    and_,
    cast,
    case,
    Date,
    func,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.models.alert import AlertRecord
from app.models.event import Event
from app.models.opinion import Opinion
from app.models.region import Region
from app.services.keyword_service import get_monitoring_keywords

logger = logging.getLogger(__name__)

HIGH_RISK_THRESHOLD = 70
TOP_KEYWORDS = 10
TOP_SOURCES = 10
TOP_REGIONS = 10  # 仅作兜底上限；省级上卷后通常远小于此
TOP_REGIONS_DETAIL = 10  # 驾驶舱「地区舆情 TOP」细分卡片：市/县 TOP 上限


# ---------------------------------------------------------------------------
# 省级上卷（指挥大屏地图专用）
# ---------------------------------------------------------------------------
def _province_code(code: str, level: str) -> str:
    """由行政区划 code 推导省级 code（GB/T 2260 前缀），不依赖 parent_code。

    - 省：130000 / 13 -> 130000
    - 市：130100      -> 130000
    - 县：131028      -> 130000

    纯靠 code 前缀推导，因此对 parent_code 缺失/不完整（如大厂回族自治县
    parent_code=None）也能正确上卷；未来新增其它省份（如 440000 广东）同样适用。
    不写死任何具体省名。
    """
    code = code or ""
    if len(code) >= 2:
        return code[:2] + "0000"
    return code  # 兜底（极少出现）：无法推导时原样返回，后续会被判定为未知地区


def _rollup_provinces(db: Session, counts_by_region) -> list[dict]:
    """将 (region_id, count) 序列按省级归并，输出仅含省级地域的分布。

    - 输出只含省级（地图 choropleth 仅接受省名）。
    - 无法识别省级归属的 region，记录 warning 日志并归入「未知地区」(region_id=0)，
      绝不静默丢弃（计数保留）。
    """
    prov_rows = db.execute(
        select(Region.code, Region.id, Region.name).where(Region.level == "province")
    ).all()
    # 以规范化后的省级 code 为 key，兼容省 code 写成 2 位或 6 位的情况
    prov_map: dict[str, tuple[int, str]] = {}
    for code, rid, name in prov_rows:
        prov_map[_province_code(code, "province")] = (rid, name)

    region_rows = db.execute(select(Region.id, Region.code, Region.level)).all()
    prov_of_region: dict[int, int] = {}  # region_id -> 省级 region id（0=未知）
    for rid, code, level in region_rows:
        pkey = _province_code(code, level)
        prov = prov_map.get(pkey)
        if prov is None:
            logger.warning(
                "指挥大屏: 无法将 region(id=%s, code=%s, level=%s) 归并到省级，"
                "归入「未知地区」(region_id=0)",
                rid, code, level,
            )
            prov_of_region[rid] = 0
        else:
            prov_of_region[rid] = prov[0]

    name_by_prov: dict[int, str] = {rid: name for _c, rid, name in prov_rows}
    name_by_prov[0] = "未知地区"

    agg: Counter = Counter()
    for rid, cnt in counts_by_region:
        agg[prov_of_region.get(rid, 0)] += cnt

    return [
        {
            "region_id": pid,
            "region_name": name_by_prov.get(pid, "未知地区"),
            "count": c,
        }
        for pid, c in agg.most_common()
    ]


def _detail_regions(db: Session, window_start) -> list[dict]:
    """地区细分（驾驶舱「地区舆情 TOP」卡片专用）。

    与 _rollup_provinces（指挥大屏地图用，强制省级上卷）不同，本函数：
    - 直接按数据中最细的已标注层级（市 / 县）聚合，呈现真实细分分布；
    - 剔除省级（河北省）汇总行，避免卡片仅显示「河北省」而过于空泛；
    - 按 count 降序取 TOP_REGIONS_DETAIL。

    不破坏现有 regions 省级上卷契约（指挥大屏中国地图仍消费 regions）。
    """
    rows = (
        db.execute(
            select(
                Region.id,
                Region.name,
                Region.level,
                func.count(Opinion.id).label("cnt"),
            )
            .join(Opinion, Opinion.region_id == Region.id)
            .where(
                and_(
                    cast(Opinion.created_at, Date) >= window_start,
                    Region.level != "province",
                )
            )
            .group_by(Region.id, Region.name, Region.level)
            .order_by(func.count(Opinion.id).desc())
            .limit(TOP_REGIONS_DETAIL)
        )
        .all()
    )
    return [
        {"region_id": rid, "region_name": name, "count": cnt}
        for rid, name, _level, cnt in rows
    ]


# ---------------------------------------------------------------------------
# 地区下钻（指挥大屏地图点击省级 → 市级着色）
# ---------------------------------------------------------------------------
def _city_code(code: str) -> str:
    """由行政区划 code 推导市级 code（GB/T 2260 前 4 位）。

    - 市：130100 -> 130100
    - 县：131028 -> 131000
    纯靠 code 前缀推导，不依赖 parent_code（大厂回族自治县 parent_code 缺失也能正确归属）。
    """
    code = code or ""
    if len(code) >= 4:
        return code[:4] + "00"
    if len(code) == 2:
        return code + "0000"
    return code


def get_region_children(db: Session, province_name: str, days: int = 7) -> dict | None:
    """地区下钻：给定省级名称，返回其下属市/县舆情分布。

    用于指挥大屏中国地图点击某省后的下钻：
    - 不依赖 parent_code，纯靠行政区划 code 前缀（_province_code / _city_code）推导归属，
      因此对 parent_code 缺失/不完整的县级（如大厂回族自治县）也能正确上卷到所属市；
    - 市级按 code 前缀归并（含所辖县计数），与市级 GeoJSON（feature name 如「石家庄市」）
      按名称匹配着色；
    - 同时返回 raw 市/县明细，供侧栏或悬浮辅助展示。
    无匹配省份时返回 None（由路由转 404）。
    """
    window_start = date.today() - timedelta(days=days - 1)

    prov = (
        db.execute(
            select(Region).where(Region.name == province_name, Region.level == "province")
        )
        .scalars()
        .first()
    )
    if prov is None:
        return None
    prov_prefix = _province_code(prov.code, "province")

    # 取全部市/县，再按 code 前缀筛出属于该省的（不依赖 parent_code）
    all_subs = (
        db.execute(select(Region).where(Region.level != "province"))
        .scalars()
        .all()
    )
    subs = [r for r in all_subs if _province_code(r.code, r.level) == prov_prefix]
    if not subs:
        return {
            "province": province_name,
            "province_code": prov.code,
            "total": 0,
            "cities": [],
            "raw": [],
        }

    sub_ids = [r.id for r in subs]
    counts_rows = (
        db.execute(
            select(Opinion.region_id, func.count(Opinion.id).label("cnt"))
            .where(Opinion.region_id.in_(sub_ids))
            .where(cast(Opinion.created_at, Date) >= window_start)
            .group_by(Opinion.region_id)
        )
        .all()
    )
    counts = {rid: cnt for rid, cnt in counts_rows}

    # 市级信息表（按 city_code 归并）
    city_info: dict[str, dict] = {}
    for r in subs:
        if r.level == "city":
            city_info[_city_code(r.code)] = {"name": r.name, "count": 0}

    raw = []
    total = 0
    for r in subs:
        c = counts.get(r.id, 0)
        total += c
        raw.append({"region_name": r.name, "count": c, "level": r.level})
        cc = _city_code(r.code)
        if cc in city_info:
            city_info[cc]["count"] += c

    cities = [
        {"code": code, "name": v["name"], "count": v["count"]}
        for code, v in city_info.items()
    ]
    cities.sort(key=lambda x: -x["count"])
    raw.sort(key=lambda x: -x["count"])

    return {
        "province": province_name,
        "province_code": prov.code,
        "total": total,
        "cities": cities,
        "raw": raw,
    }


# ---------------------------------------------------------------------------
# 基础聚合（带进程内 TTL 缓存）
# ---------------------------------------------------------------------------
def get_dashboard_stats(db: Session, days: int = 7) -> dict:
    """计算驾驶舱总览统计（见模块 docstring 的数据契约）。"""
    key = f"dash:stats:{days}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    total = db.scalar(select(func.count(Opinion.id))) or 0

    today = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                cast(Opinion.created_at, Date) == func.current_date()
            )
        )
        or 0
    )

    # 累计指标：系统高危态势（全量，不随 days 变化）
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

    # ---- 时间窗口指标：trend / sentiments / sources / regions ----
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

    # sentiments：窗口内情感分布
    sentiment_rows = db.execute(
        select(Opinion.sentiment, func.count(Opinion.id))
        .where(cast(Opinion.created_at, Date) >= window_start)
        .group_by(Opinion.sentiment)
    ).all()
    sentiments = [{"label": s, "count": c} for s, c in sentiment_rows]

    # sources：窗口内来源分布 Top
    source_rows = db.execute(
        select(Opinion.source, func.count(Opinion.id))
        .where(cast(Opinion.created_at, Date) >= window_start)
        .group_by(Opinion.source)
        .order_by(func.count(Opinion.id).desc())
        .limit(TOP_SOURCES)
    ).all()
    sources = [{"source": s or "未知", "count": c} for s, c in source_rows]

    # regions：窗口内，按省级上卷（指挥大屏中国地图专用，保持省级契约）
    region_rows = db.execute(
        select(Opinion.region_id, func.count(Opinion.id))
        .where(cast(Opinion.created_at, Date) >= window_start)
        .group_by(Opinion.region_id)
    ).all()
    regions = _rollup_provinces(db, region_rows)

    # region_detail：窗口内，市/县细分（驾驶舱「地区舆情 TOP」卡片用，剔除省级汇总）
    region_detail = _detail_regions(db, window_start)

    # keywords：[兼容字段] 全量，来自 opinions.keywords（敏感词命中集合）
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

    # hot_keywords：指挥大屏「热门关键词」（窗口内真实提及频次）
    hot_keywords = get_hot_keywords(db, days=days, limit=TOP_KEYWORDS)

    data = {
        "total": total,
        "today": today,
        "high_risk": high_risk,
        "event_count": event_count,
        "trend": trend,
        "sentiments": sentiments,
        "sources": sources,
        "regions": regions,
        "region_detail": region_detail,
        "keywords": keywords,
        "hot_keywords": hot_keywords["items"],
    }
    cache_set(key, data)
    return data


def get_recent_opinions(db: Session, limit: int = 8) -> list[dict]:
    """实时快讯：最近产生的舆情（按创建时间倒序）。带 TTL 缓存。"""
    key = f"dash:recent:{limit}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    rows = (
        db.execute(
            select(
                Opinion.id,
                Opinion.title,
                Opinion.source,
                Opinion.sentiment,
                Opinion.risk_score,
                Region.name.label("region_name"),
                Opinion.created_at,
            )
            .join(Region, Region.id == Opinion.region_id)
            .order_by(Opinion.created_at.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    items = [
        {
            "id": r["id"],
            "title": r["title"] or "(无标题)",
            "source": r["source"] or "未知",
            "sentiment": r["sentiment"] or "neutral",
            "risk_score": r["risk_score"] or 0,
            "region_name": r["region_name"] or "未知",
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        }
        for r in rows
    ]
    cache_set(key, items)
    return items


def get_dashboard_alerts(db: Session, limit: int = 8) -> list[dict]:
    """预警滚动：最近触发的预警记录（按时间倒序）。带 TTL 缓存。"""
    key = f"dash:alerts:{limit}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    rows = (
        db.query(AlertRecord)
        .order_by(AlertRecord.id.desc())
        .limit(limit)
        .all()
    )
    items = [
        {
            "id": r.id,
            "opinion_id": r.opinion_id,
            "rule_name": r.rule_name or "预警规则",
            "risk_level": r.risk_level or "low",
            "opinion_title": r.opinion_title or "",
            "trigger_reason": r.trigger_reason or "",
            "handled": bool(r.handled),
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]
    cache_set(key, items)
    return items


# ---------------------------------------------------------------------------
# KPI 趋势数据（指挥大屏 KPI 卡片 sparkline 用）
# ---------------------------------------------------------------------------
def get_kpi_trends(db: Session, days: int = 14) -> dict:
    """返回最近 days 天各核心指标的日值序列，供前端绘制 sparkline。

    - opinions：每日新增舆情数（与 stats.trend 同源）
    - high_risk：每日新增高危舆情（risk_score >= HIGH_RISK_THRESHOLD 的当日增量）
    - events：每日新增事件数
    无数据日期补 0，保证序列长度 = days。
    """
    key = f"dash:kpi_trends:{days}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    today_date: date = db.scalar(select(func.current_date()))
    window_start = today_date - timedelta(days=days - 1)

    # ---- 每日新增舆情 ----
    opinion_rows = db.execute(
        select(
            cast(Opinion.created_at, Date).label("day"),
            func.count(Opinion.id).label("cnt"),
        )
        .where(cast(Opinion.created_at, Date) >= window_start)
        .group_by(cast(Opinion.created_at, Date))
        .order_by("day")
    ).all()
    opinion_counts = {row.day: row.cnt for row in opinion_rows}

    # ---- 每日新增高危舆情 ----
    hr_rows = db.execute(
        select(
            cast(Opinion.created_at, Date).label("day"),
            func.count(Opinion.id).label("cnt"),
        )
        .where(and_(
            cast(Opinion.created_at, Date) >= window_start,
            Opinion.risk_score >= HIGH_RISK_THRESHOLD,
        ))
        .group_by(cast(Opinion.created_at, Date))
        .order_by("day")
    ).all()
    hr_counts = {row.day: row.cnt for row in hr_rows}

    # ---- 每日新增事件（用 first_time 代替 created_at） ----
    event_rows = db.execute(
        select(
            cast(Event.first_time, Date).label("day"),
            func.count(Event.id).label("cnt"),
        )
        .where(cast(Event.first_time, Date) >= window_start)
        .group_by(cast(Event.first_time, Date))
        .order_by("day")
    ).all()
    event_counts = {row.day: row.cnt for row in event_rows}

    def _series(counts_map):
        return [
            {"date": (window_start + timedelta(days=i)).isoformat(), "value": counts_map.get(window_start + timedelta(days=i), 0)}
            for i in range(days)
        ]

    data = {
        "days": days,
        "opinions": _series(opinion_counts),
        "high_risk": _series(hr_counts),
        "events": _series(event_counts),
    }
    cache_set(key, data)
    return data


# ---------------------------------------------------------------------------
# 热门关键词（指挥大屏专用，真实数据源）
# ---------------------------------------------------------------------------
def _like_escape(col):
    """去除空格并转义 LIKE 通配符 % _，避免监测词中的特殊字符破坏匹配。"""
    s = func.replace(func.replace(col, " ", ""), "%", "\\%")
    s = func.replace(s, "_", "\\_")
    return s


def get_hot_keywords(db: Session, days: int = 7, limit: int = 10) -> dict:
    """指挥大屏「热门关键词」。

    数据源：监测关键词表（keywords 表，经 keyword_service.get_monitoring_keywords 获取）。
    口径：统计窗口内（created_at >= window_start）title+content 真实「提及」的舆情条数。
          - 去重到「每条舆情最多计 1 次」（避免同一文档内多次出现导致严重重复计数）。
          - 不读取 Opinion.keywords（那只是规则命中的敏感词集合，语义不符）。
          - 关键词大小写不敏感（ILIKE 处理英文；中文无大小写）。
    趋势 trend：当前窗口计数 vs 紧邻的前一个等长窗口计数（cur>prev→up，<→down，=→flat）。
          为真实对比，非伪造；若无可比数据则按 cur 给出 up/flat 的稳妥判定。
    空数据：keywords 表为空或窗口内无提及 -> 返回稳定空结构 {"items":[], "days":N}，不 500。
    """
    key = f"dash:hot:{days}:{limit}"
    cached = cache_get(key)
    if cached is not None:
        return cached

    keywords = get_monitoring_keywords(db)
    if not keywords:
        data = {"items": [], "days": days}
        cache_set(key, data)
        return data

    today_date: date = db.scalar(select(func.current_date()))
    window_start = today_date - timedelta(days=days - 1)
    prev_start = window_start - timedelta(days=days)

    sub = select(func.unnest(pg_array(list(keywords))).label("kw")).subquery()
    pattern = func.concat("%", _like_escape(sub.c.kw), "%")
    stmt = (
        select(
            sub.c.kw.label("kw"),
            func.count(
                case((cast(Opinion.created_at, Date) >= window_start, Opinion.id))
            ).label("cur"),
            func.count(
                case(
                    (
                        and_(
                            cast(Opinion.created_at, Date) >= prev_start,
                            cast(Opinion.created_at, Date) < window_start,
                        ),
                        Opinion.id,
                    )
                )
            ).label("prev"),
        )
        .select_from(sub)
        .join(
            Opinion,
            or_(
                Opinion.title.ilike(pattern, escape="\\"),
                Opinion.content.ilike(pattern, escape="\\"),
            ),
        )
        .where(cast(Opinion.created_at, Date) >= prev_start)
        .group_by(sub.c.kw)
    )
    rows = db.execute(stmt).all()

    items = []
    for kw, cur, prev in rows:
        if cur is None or cur <= 0:
            continue
        prev = prev or 0
        trend = "up" if cur > prev else ("down" if cur < prev else "flat")
        items.append({"keyword": kw, "count": cur, "trend": trend})

    items.sort(key=lambda x: x["count"], reverse=True)
    items = items[:limit]

    data = {"items": items, "days": days}
    cache_set(key, data)
    return data
