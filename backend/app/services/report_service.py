"""舆情报告服务：汇总统计 + reportlab 生成 PDF（P2 报告自动生成 + PDF 导出）。

无外部原生依赖（reportlab 纯 Python），可在 Windows 环境稳定生成中文 PDF。
"""
from __future__ import annotations

import io
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, cast, Date, func, select
from sqlalchemy.orm import Session

from app.models.alert import AlertRecord
from app.models.event import Event
from app.models.opinion import Opinion
from app.models.region import Region
from app.services.dashboard_service import (
    HIGH_RISK_THRESHOLD,
    TOP_KEYWORDS,
    _rollup_provinces,
    get_dashboard_stats,
)

# reportlab 渲染符号（模块级渲染函数 _r_* 与 render_* 共用；reportlab 为项目硬依赖）
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 中文字体注册（优先系统字体，回退到 reportlab 内置 CID 字体）
# ---------------------------------------------------------------------------
_FONT_NAME = "Helvetica"


def _register_font() -> str:
    global _FONT_NAME
    if _FONT_NAME != "Helvetica" and _FONT_NAME != "STSong-Light":
        return _FONT_NAME
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        (r"C:\Windows\Fonts\msyh.ttc", 0),
        (r"C:\Windows\Fonts\simhei.ttf", 0),
        (r"C:\Windows\Fonts\simsun.ttc", 0),
    ]
    for path, idx in candidates:
        try:
            pdfmetrics.registerFont(TTFont("CJK", path, subfontIndex=idx))
            _FONT_NAME = "CJK"
            return _FONT_NAME
        except Exception:
            continue
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _FONT_NAME = "STSong-Light"
    except Exception:
        _FONT_NAME = "Helvetica"
    return _FONT_NAME


# ---------------------------------------------------------------------------
# 数据汇总
# ---------------------------------------------------------------------------
def build_overview(db: Session, days: int = 7) -> dict:
    """汇总报告所需的全部数据。"""
    stats = get_dashboard_stats(db, days=days)
    total = stats["total"] or 0
    high_risk = stats["high_risk"] or 0
    risk_rate = round(high_risk / total * 100, 1) if total else 0.0
    neg = next((s["count"] for s in stats["sentiments"] if s["label"] == "negative"), 0)
    negative_rate = round(neg / total * 100, 1) if total else 0.0

    # 高风险舆情 TOP10
    top_rows = (
        db.execute(
            select(
                Opinion.id,
                Opinion.title,
                Opinion.source,
                Opinion.risk_score,
                Opinion.sentiment,
                Opinion.summary,
                Opinion.created_at,
                Region.name.label("region_name"),
            )
            .join(Region, Region.id == Opinion.region_id)
            .where(Opinion.risk_score >= HIGH_RISK_THRESHOLD)
            .where(Opinion.geo_filtered.isnot(True))
            .order_by(Opinion.risk_score.desc(), Opinion.id.desc())
            .limit(10)
        )
        .mappings()
        .all()
    )
    top_risky = [
        {
            "id": r["id"],
            "title": (r["title"] or "(无标题)"),
            "source": r["source"] or "未知",
            "region_name": r["region_name"] or "未知",
            "risk_score": r["risk_score"] or 0,
            "sentiment": r["sentiment"] or "neutral",
            "created_at": r["created_at"].isoformat() if r["created_at"] else "",
            "summary": (r["summary"] or "")[:120],
        }
        for r in top_rows
    ]

    # 重点事件 TOP（按舆情数倒序；Phase X-History-1B 排除软废弃事件）
    event_rows = (
        db.query(Event)
        .filter(Event.status != "deprecated")
        .order_by(func.coalesce(Event.opinion_count, 0).desc(), Event.id.desc())
        .limit(10)
        .all()
    )
    events = [
        {
            "id": ev.id,
            "title": ev.title or "(未命名事件)",
            "risk_level": ev.risk_level or "low",
            "opinion_count": ev.opinion_count or 0,
        }
        for ev in event_rows
    ]

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "period_days": days,
        "total": total,
        "today": stats["today"] or 0,
        "high_risk": high_risk,
        "event_count": stats["event_count"] or 0,
        "risk_rate": risk_rate,
        "negative_rate": negative_rate,
        "trend": stats["trend"],
        "top_keywords": stats["keywords"][:TOP_KEYWORDS],
        "top_sources": stats["sources"][:10],
        "top_regions": stats["regions"][:10],
        "top_risky": top_risky,
        "events": events,
        "sentiments": stats["sentiments"],
    }


# ---------------------------------------------------------------------------
# PDF 渲染
# ---------------------------------------------------------------------------
def render_pdf(data: dict) -> bytes:
    """使用 reportlab 将报告数据渲染为 A4 PDF 字节流。"""
    font = _register_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RptTitle", parent=styles["Title"], fontName=font, fontSize=22, leading=26
    )
    sub_style = ParagraphStyle(
        "RptSub", parent=styles["Normal"], fontName=font, fontSize=11,
        textColor=colors.HexColor("#6e6e73"), alignment=TA_CENTER,
    )
    h_style = ParagraphStyle(
        "RptH", parent=styles["Heading2"], fontName=font, fontSize=14,
        textColor=colors.HexColor("#0071e3"), spaceBefore=14, spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "RptCell", parent=styles["Normal"], fontName=font, fontSize=9, leading=12
    )
    cell_style_r = ParagraphStyle(
        "RptCellR", parent=cell_style, alignment=TA_LEFT
    )

    def P(text: str, style=cell_style) -> Paragraph:
        safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, style)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="互联网舆情监测报告",
    )
    flow: list = []

    flow.append(Paragraph("互联网舆情监测报告", title_style))
    flow.append(Spacer(1, 4))
    flow.append(Paragraph(
        f"统计周期：近 {data['period_days']} 天　|　生成时间：{data['generated_at']}",
        sub_style,
    ))
    flow.append(Spacer(1, 12))

    # 总体态势 KPI
    flow.append(Paragraph("一、总体态势", h_style))
    kpi = [
        ["总舆情数", "今日新增", "高风险数", "事件数", "风险率", "负面率"],
        [
            str(data["total"]), str(data["today"]), str(data["high_risk"]),
            str(data["event_count"]), f"{data['risk_rate']}%", f"{data['negative_rate']}%",
        ],
    ]
    kpi_tbl = Table(kpi, colWidths=[28 * mm] * 6)
    kpi_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0071e3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#e8f1fd")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c0ccda")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow.append(kpi_tbl)

    # 趋势（近 7 日）
    flow.append(Paragraph("二、舆情趋势（近 7 日）", h_style))
    trend_rows = [["日期", "数量"]] + [
        [t["date"], str(t["count"])] for t in data["trend"][-7:]
    ]
    trend_tbl = Table(trend_rows, colWidths=[40 * mm, 30 * mm])
    trend_tbl.setStyle(_grid_style(font, colors.HexColor("#34c759")))
    flow.append(trend_tbl)

    # 高风险舆情 TOP10
    flow.append(Paragraph("三、高风险舆情 TOP", h_style))
    if data["top_risky"]:
        rows = [["标题", "来源", "地区", "风险", "情感"]]
        for o in data["top_risky"]:
            rows.append([
                P(o["title"]), P(o["source"]), P(o["region_name"]),
                str(o["risk_score"]), o["sentiment"],
            ])
        t = Table(rows, colWidths=[64 * mm, 26 * mm, 24 * mm, 14 * mm, 22 * mm], repeatRows=1)
        t.setStyle(_grid_style(font, colors.HexColor("#ff3b30")))
        flow.append(t)
    else:
        flow.append(Paragraph("本期无高风险舆情。", cell_style))

    # 重点事件
    flow.append(Paragraph("四、重点事件", h_style))
    if data["events"]:
        rows = [["事件", "风险等级", "舆情数"]]
        for ev in data["events"]:
            rows.append([P(ev["title"]), ev["risk_level"], str(ev["opinion_count"])])
        t = Table(rows, colWidths=[100 * mm, 28 * mm, 22 * mm], repeatRows=1)
        t.setStyle(_grid_style(font, colors.HexColor("#c77700")))
        flow.append(t)
    else:
        flow.append(Paragraph("本期无聚合事件。", cell_style))

    # 来源 / 地区 / 关键词分布
    flow.append(Paragraph("五、分布特征", h_style))
    dist_rows = [["来源 TOP", "数量", "地区 TOP", "数量", "关键词 TOP", "数量"]]
    src = data["top_sources"][:5]
    reg = data["top_regions"][:5]
    kw = data["top_keywords"][:5]
    for i in range(5):
        s = src[i] if i < len(src) else None
        r = reg[i] if i < len(reg) else None
        k = kw[i] if i < len(kw) else None
        dist_rows.append([
            P(s["source"]) if s else "", str(s["count"]) if s else "",
            P(r["region_name"]) if r else "", str(r["count"]) if r else "",
            P(k["word"]) if k else "", str(k["count"]) if k else "",
        ])
    dist_tbl = Table(
        dist_rows,
        colWidths=[30 * mm, 14 * mm, 30 * mm, 14 * mm, 30 * mm, 14 * mm],
        repeatRows=1,
    )
    dist_tbl.setStyle(_grid_style(font, colors.HexColor("#0071e3")))
    flow.append(dist_tbl)

    # 情感分布
    flow.append(Paragraph("六、情感分布", h_style))
    sent_rows = [["情感", "数量"]] + [
        [s["label"], str(s["count"])] for s in data["sentiments"]
    ]
    sent_tbl = Table(sent_rows, colWidths=[40 * mm, 30 * mm])
    sent_tbl.setStyle(_grid_style(font, colors.HexColor("#86868b")))
    flow.append(sent_tbl)

    flow.append(Spacer(1, 16))
    flow.append(Paragraph(
        "本报告由舆情监测平台自动生成，数据来源于系统监测库，仅供参考。",
        ParagraphStyle("foot", parent=cell_style, fontSize=8,
                       textColor=colors.HexColor("#a0a0a5"), alignment=TA_CENTER),
    ))

    doc.build(flow)
    return buf.getvalue()


def _grid_style(font: str, header_color):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), header_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e0e0e5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ])


# ===========================================================================
# Phase Report-1：可配置报告生成器（模块注册模式）
# ---------------------------------------------------------------------------
# 设计约束：
#   1. legacy build_overview / render_pdf 原样保留，旧接口 /reports/overview
#      /reports/overview/pdf 完全兼容，不改动任何已有行为。
#   2. 新增 ReportConfig（报告配置）+ MODULE_REGISTRY（模块注册表），
#      每个模块自带 data_fn（取数）与 render_fn（渲染），支持按序插拔。
#   3. 时间口径：time_field 支持 created_at（采集时间）/ publish_time（发布时间）。
#      publish_time 为可空字段，缺失发布时间的记录在「发布时间」口径下自然被排除。
#   4. 时间范围：优先使用 start_date/end_date 自定义区间；否则回退到 days 预设窗口。
# ===========================================================================
@dataclass
class ReportConfig:
    """报告生成配置（由 API 层 Pydantic 模型映射而来）。"""

    report_name: str = "舆情监测报告"
    time_field: str = "created_at"  # "created_at"（采集时间） | "publish_time"（发布时间）
    start_date: Optional[str] = None  # "YYYY-MM-DD"
    end_date: Optional[str] = None
    days: int = 7
    module_keys: List[str] = field(default_factory=list)
    # Phase Report-2-P1：按模块 key 传入的可配置参数，如 {"top_risky": {"limit": 20}}
    module_params: Dict[str, Dict[str, Any]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase Report-2-P1 统一时间口径（方案 A：本地时间语义，不做任何时区转换）
# ---------------------------------------------------------------------------
# Phase 0 审计结论：opinions.created_at / publish_time 为 timestamp without time
# zone，实际存储语义 = Asia/Shanghai 本地时间；dashboard_service 全部按本地日期
# 计算。因此报告侧同样按本地日期比较，禁止「本地日期 -> UTC」转换。
#
# publish_time 口径：Phase 0 实测 904 条中 207 条为空（22.90% >= 5%），
# 统一使用 COALESCE(publish_time, created_at)，禁止过滤/丢弃无发布时间数据。
TIME_FIELD_LABELS = {
    "created_at": "采集时间",
    "publish_time": "发布时间（缺失回退采集时间）",
}


def _time_column(time_field: str):
    """返回时间口径列表达式（过滤 / 排序 / 分组 / 展示统一使用本函数）。"""
    if time_field == "publish_time":
        return func.coalesce(Opinion.publish_time, Opinion.created_at)
    return Opinion.created_at


def _time_filter(col, ws: date, we: date):
    """本地日期闭区间过滤，与 dashboard_service 现有 cast(col, Date) 口径一致。"""
    return and_(cast(col, Date) >= ws, cast(col, Date) <= we)


def _window_clause(col, ws: date, we: date):
    """兼容别名（Phase Report-1 内部命名），等价于 _time_filter。"""
    return _time_filter(col, ws, we)


def _resolve_window(db: Session, cfg: ReportConfig):
    """返回 (window_start, window_end) 两个 date。"""
    today: date = db.scalar(select(func.current_date()))
    if cfg.start_date and cfg.end_date:
        try:
            ws = date.fromisoformat(cfg.start_date)
            we = date.fromisoformat(cfg.end_date)
        except ValueError:
            ws = today - timedelta(days=max(1, int(cfg.days or 7)) - 1)
            we = today
    else:
        d = max(1, int(cfg.days or 7))
        ws = today - timedelta(days=d - 1)
        we = today
    if ws > we:
        ws, we = we, ws
    return ws, we


def _p_int(params: dict, key: str, default: int, lo: int, hi: int) -> int:
    """安全读取整型模块参数（越界钳制，非法值回退默认）。"""
    try:
        v = int((params or {}).get(key, default))
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


# ---- 模块取数函数（db, ws, we, col, params）-> dict --------------------------
def _m_overview_kpi(db, ws, we, col, params=None) -> dict:
    # Phase X-History-1B：排除地域语义污染标记 geo_filtered IS NOT TRUE
    base = _window_clause(col, ws, we)
    total = (
        db.scalar(
            select(func.count(Opinion.id)).where(base, Opinion.geo_filtered.isnot(True))
        )
        or 0
    )
    high_risk = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                base,
                Opinion.risk_score >= HIGH_RISK_THRESHOLD,
                Opinion.geo_filtered.isnot(True),
            )
        )
        or 0
    )
    event_count = (
        db.scalar(
            select(func.count(Event.id)).where(
                _window_clause(Event.first_time, ws, we),
                Event.status != "deprecated",
            )
        )
        or 0
    )
    neg = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                base, Opinion.sentiment == "negative", Opinion.geo_filtered.isnot(True)
            )
        )
        or 0
    )
    risk_rate = round(high_risk / total * 100, 1) if total else 0.0
    negative_rate = round(neg / total * 100, 1) if total else 0.0
    return {
        "total": total,
        "high_risk": high_risk,
        "event_count": event_count,
        "risk_rate": risk_rate,
        "negative_rate": negative_rate,
    }


def _m_trend(db, ws, we, col, params=None) -> dict:
    rows = (
        db.execute(
            select(cast(col, Date).label("day"), func.count(Opinion.id).label("cnt"))
            .where(_window_clause(col, ws, we))
            .where(Opinion.geo_filtered.isnot(True))
            .group_by(cast(col, Date))
            .order_by("day")
        )
        .all()
    )
    counts = {r.day: r.cnt for r in rows}
    span = (we - ws).days + 1
    trend = [
        {"date": (ws + timedelta(days=i)).isoformat(), "count": counts.get(ws + timedelta(days=i), 0)}
        for i in range(span)
    ]
    return {"trend": trend}


def _m_top_risky(db, ws, we, col, params=None) -> dict:
    limit = _p_int(params, "limit", 10, 1, 50)
    rows = (
        db.execute(
            select(
                Opinion.id,
                Opinion.title,
                Opinion.source,
                Opinion.risk_score,
                Opinion.sentiment,
                Opinion.summary,
                col.label("ts"),
                Region.name.label("region_name"),
            )
            .join(Region, Region.id == Opinion.region_id)
            .where(_time_filter(col, ws, we), Opinion.risk_score >= HIGH_RISK_THRESHOLD, Opinion.geo_filtered.isnot(True))
            .order_by(Opinion.risk_score.desc(), Opinion.id.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    top_risky = [
        {
            "id": r["id"],
            "title": (r["title"] or "(无标题)"),
            "source": r["source"] or "未知",
            "region_name": r["region_name"] or "未知",
            "risk_score": r["risk_score"] or 0,
            "sentiment": r["sentiment"] or "neutral",
            "created_at": r["ts"].isoformat() if r["ts"] else "",
            "summary": (r["summary"] or "")[:120],
        }
        for r in rows
    ]
    return {"top_risky": top_risky}


def _m_events(db, ws, we, col, params=None) -> dict:
    limit = _p_int(params, "limit", 10, 1, 50)
    # Phase X-History-1B：排除软废弃事件
    event_rows = (
        db.query(Event).filter(Event.status != "deprecated")
        .order_by(func.coalesce(Event.opinion_count, 0).desc(), Event.id.desc()).limit(limit).all()
    )
    events = [
        {
            "id": ev.id,
            "title": ev.title or "(未命名事件)",
            "risk_level": ev.risk_level or "low",
            "opinion_count": ev.opinion_count or 0,
        }
        for ev in event_rows
    ]
    return {"events": events}


def _m_source_dist(db, ws, we, col, params=None) -> dict:
    """来源分布（原 distribution 拆分项之一）。"""
    limit = _p_int(params, "limit", 10, 1, 30)
    rows = (
        db.execute(
            select(Opinion.source, func.count(Opinion.id))
            .where(_time_filter(col, ws, we))
            .where(Opinion.geo_filtered.isnot(True))
            .group_by(Opinion.source)
            .order_by(func.count(Opinion.id).desc())
            .limit(limit)
        )
        .all()
    )
    total = sum(c for _s, c in rows) or 0
    return {
        "top_sources": [
            {
                "source": s or "未知",
                "count": c,
                "ratio": round(c / total * 100, 1) if total else 0.0,
            }
            for s, c in rows
        ]
    }


def _m_region_dist(db, ws, we, col, params=None) -> dict:
    """地区分布（省级上卷，与指挥大屏同源逻辑）。"""
    limit = _p_int(params, "limit", 10, 1, 30)
    region_rows = (
        db.execute(
            select(Opinion.region_id, func.count(Opinion.id))
            .where(_time_filter(col, ws, we))
            .where(Opinion.geo_filtered.isnot(True))
            .group_by(Opinion.region_id)
        )
        .all()
    )
    return {"top_regions": _rollup_provinces(db, region_rows)[:limit]}


def _m_keyword_dist(db, ws, we, col, params=None) -> dict:
    """热点关键词分布（来源 opinions.keywords，逗号分隔）。"""
    limit = _p_int(params, "limit", TOP_KEYWORDS, 1, 50)
    kw_rows = db.execute(select(Opinion.keywords).where(_time_filter(col, ws, we)).where(Opinion.geo_filtered.isnot(True))).scalars().all()
    counter: Counter = Counter()
    for raw in kw_rows:
        for kw in (raw or "").split(","):
            kw = kw.strip()
            if kw:
                counter[kw] += 1
    return {"top_keywords": [{"word": w, "count": c} for w, c in counter.most_common(limit)]}


# 风险分类中文标签（risk_category 由 RiskEngine 派生，历史数据可能为 NULL）
RISK_CATEGORY_LABELS = {
    "safety_accident": "安全事故",
    "social_security": "社会治安",
    "political": "政治敏感",
    "other": "其他",
}


def _m_risk_category(db, ws, we, col, params=None) -> dict:
    """风险分类分布（纯解释性标签，NULL 归入「未分类」）。"""
    rows = (
        db.execute(
            select(Opinion.risk_category, func.count(Opinion.id))
            .where(_time_filter(col, ws, we))
            .where(Opinion.geo_filtered.isnot(True))
            .group_by(Opinion.risk_category)
            .order_by(func.count(Opinion.id).desc())
        )
        .all()
    )
    total = sum(c for _k, c in rows) or 0
    return {
        "categories": [
            {
                "key": k or "unclassified",
                "label": RISK_CATEGORY_LABELS.get(k or "", "未分类"),
                "count": c,
                "ratio": round(c / total * 100, 1) if total else 0.0,
            }
            for k, c in rows
        ],
        "total": total,
    }


# 预警处置状态中文标签（与 alert_records.status 值域一致）
ALERT_STATUS_LABELS = {
    "pending": "待处置",
    "processing": "处置中",
    "resolved": "已解决",
    "ignored": "已忽略",
    "false_positive": "误报",
}
_ALERT_CLOSED = ("resolved", "ignored", "false_positive")


def _m_alert_summary(db, ws, we, col, params=None) -> dict:
    """预警处置概览（按 alert_records.created_at 本地日期窗口统计）。"""
    acol = AlertRecord.created_at
    status_rows = (
        db.execute(
            select(AlertRecord.status, func.count(AlertRecord.id))
            .where(_time_filter(acol, ws, we))
            .group_by(AlertRecord.status)
        )
        .all()
    )
    level_rows = (
        db.execute(
            select(AlertRecord.risk_level, func.count(AlertRecord.id))
            .where(_time_filter(acol, ws, we))
            .group_by(AlertRecord.risk_level)
        )
        .all()
    )
    by_status = {s or "pending": c for s, c in status_rows}
    total = sum(by_status.values())
    closed = sum(v for k, v in by_status.items() if k in _ALERT_CLOSED)
    return {
        "total": total,
        "closed": closed,
        "pending": total - closed,
        "closed_rate": round(closed / total * 100, 1) if total else 0.0,
        "by_status": [
            {"key": k, "label": ALERT_STATUS_LABELS.get(k, k), "count": v}
            for k, v in sorted(by_status.items(), key=lambda x: -x[1])
        ],
        "by_level": [
            {"level": lv or "low", "count": c}
            for lv, c in sorted(level_rows, key=lambda x: -x[1])
        ],
    }


def _m_opinion_list(db, ws, we, col, params=None) -> dict:
    """舆情明细清单（按所选时间口径倒序，默认 50 条，上限 200）。"""
    limit = _p_int(params, "limit", 50, 1, 200)
    min_risk = _p_int(params, "min_risk", 0, 0, 100)
    rows = (
        db.execute(
            select(
                Opinion.id,
                Opinion.title,
                Opinion.source,
                Opinion.risk_score,
                Opinion.sentiment,
                col.label("ts"),
                Region.name.label("region_name"),
            )
            .outerjoin(Region, Region.id == Opinion.region_id)
            .where(_time_filter(col, ws, we), Opinion.risk_score >= min_risk, Opinion.geo_filtered.isnot(True))
            .order_by(col.desc(), Opinion.id.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    return {
        "items": [
            {
                "id": r["id"],
                "title": r["title"] or "(无标题)",
                "source": r["source"] or "未知",
                "region_name": r["region_name"] or "未知",
                "risk_score": r["risk_score"] or 0,
                "sentiment": r["sentiment"] or "neutral",
                "time": r["ts"].strftime("%m-%d %H:%M") if r["ts"] else "",
            }
            for r in rows
        ],
        "limit": limit,
    }


def _m_conclusion(db, ws, we, col, params=None) -> dict:
    """结论建议（基于窗口内统计自动生成，不引入任何外部模型）。"""
    base = _time_filter(col, ws, we)
    total = (
        db.scalar(
            select(func.count(Opinion.id)).where(base, Opinion.geo_filtered.isnot(True))
        )
        or 0
    )
    high_risk = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                base, Opinion.risk_score >= HIGH_RISK_THRESHOLD, Opinion.geo_filtered.isnot(True)
            )
        )
        or 0
    )
    neg = (
        db.scalar(
            select(func.count(Opinion.id)).where(
                base, Opinion.sentiment == "negative", Opinion.geo_filtered.isnot(True)
            )
        )
        or 0
    )
    top_source = db.execute(
        select(Opinion.source, func.count(Opinion.id))
        .where(base, Opinion.geo_filtered.isnot(True))
        .group_by(Opinion.source)
        .order_by(func.count(Opinion.id).desc())
        .limit(1)
    ).first()

    # 走势判断：窗口前半段 vs 后半段
    span = (we - ws).days + 1
    mid = ws + timedelta(days=span // 2)
    first_half = db.scalar(
        select(func.count(Opinion.id)).where(base, cast(col, Date) < mid, Opinion.geo_filtered.isnot(True))
    ) or 0
    second_half = total - first_half
    if first_half == 0:
        trend_word = "持平" if second_half == 0 else "上升"
    elif second_half > first_half * 1.2:
        trend_word = "上升"
    elif second_half < first_half * 0.8:
        trend_word = "下降"
    else:
        trend_word = "基本持平"

    risk_rate = round(high_risk / total * 100, 1) if total else 0.0
    neg_rate = round(neg / total * 100, 1) if total else 0.0
    points: List[str] = [
        f"统计区间内共采集舆情 {total} 条，整体走势{trend_word}"
        f"（前半段 {first_half} 条 / 后半段 {second_half} 条）。",
        f"高风险舆情 {high_risk} 条，占比 {risk_rate}%；负面舆情 {neg} 条，占比 {neg_rate}%。",
    ]
    if top_source and top_source[0]:
        points.append(f"主要信息来源为「{top_source[0]}」，共 {top_source[1]} 条，建议重点跟踪该渠道。")
    if high_risk > 0:
        points.append("建议对高风险舆情逐条核实并落实处置责任，必要时启动线下核查与回应。")
    else:
        points.append("本期未发现高风险舆情，建议保持常态化监测频次。")
    if neg_rate >= 30:
        points.append("负面情感占比偏高，建议加强正面信息投放与舆论引导。")
    return {
        "points": points,
        "total": total,
        "high_risk": high_risk,
        "risk_rate": risk_rate,
        "negative_rate": neg_rate,
        "trend_word": trend_word,
    }


def _m_sentiment(db, ws, we, col, params=None) -> dict:
    rows = (
        db.execute(
            select(Opinion.sentiment, func.count(Opinion.id))
            .where(_window_clause(col, ws, we))
            .where(Opinion.geo_filtered.isnot(True))
            .group_by(Opinion.sentiment)
        )
        .all()
    )
    sentiments = [{"label": s or "neutral", "count": c} for s, c in rows]
    return {"sentiments": sentiments}


# ---- 模块渲染函数（flow, data, ctx）-> 向 flow 追加 platypus 元素 ----------
def _r_overview_kpi(flow, d, ctx):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    P, grid, font = ctx["P"], ctx["grid"], ctx["font"]
    kpi = [
        ["总舆情数", "高风险数", "事件数", "风险率", "负面率"],
        [
            str(d.get("total", 0)), str(d.get("high_risk", 0)),
            str(d.get("event_count", 0)), f"{d.get('risk_rate', 0)}%", f"{d.get('negative_rate', 0)}%",
        ],
    ]
    t = Table(kpi, colWidths=[34 * mm] * 5)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0071e3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#e8f1fd")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c0ccda")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    flow.append(t)


def _r_trend(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    trend = d.get("trend", [])
    rows = [["日期", "数量"]] + [[t["date"], str(t["count"])] for t in trend]
    t = Table(rows, colWidths=[50 * mm, 30 * mm])
    t.setStyle(grid(colors.HexColor("#34c759")))
    flow.append(t)


def _r_top_risky(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    items = d.get("top_risky", [])
    if not items:
        flow.append(Paragraph("本期无高风险舆情。", ctx["cell_style"]))
        return
    rows = [["标题", "来源", "地区", "风险", "情感"]]
    for o in items:
        rows.append([
            P(o["title"]), P(o["source"]), P(o["region_name"]),
            str(o["risk_score"]), o["sentiment"],
        ])
    t = Table(rows, colWidths=[64 * mm, 26 * mm, 24 * mm, 14 * mm, 22 * mm], repeatRows=1)
    t.setStyle(grid(colors.HexColor("#ff3b30")))
    flow.append(t)


def _r_events(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    evs = d.get("events", [])
    if not evs:
        flow.append(Paragraph("本期无聚合事件。", ctx["cell_style"]))
        return
    rows = [["事件", "风险等级", "舆情数"]]
    for ev in evs:
        rows.append([P(ev["title"]), ev["risk_level"], str(ev["opinion_count"])])
    t = Table(rows, colWidths=[100 * mm, 28 * mm, 22 * mm], repeatRows=1)
    t.setStyle(grid(colors.HexColor("#c77700")))
    flow.append(t)


def _r_source_dist(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    items = d.get("top_sources", [])
    if not items:
        flow.append(Paragraph("本期无来源数据。", ctx["cell_style"]))
        return
    rows = [["来源", "数量", "占比"]] + [
        [P(i["source"]), str(i["count"]), f"{i.get('ratio', 0)}%"] for i in items
    ]
    t = Table(rows, colWidths=[80 * mm, 25 * mm, 25 * mm], repeatRows=1)
    t.setStyle(grid(colors.HexColor("#0071e3")))
    flow.append(t)


def _r_region_dist(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    items = d.get("top_regions", [])
    if not items:
        flow.append(Paragraph("本期无地区数据。", ctx["cell_style"]))
        return
    rows = [["地区", "数量"]] + [[P(i["region_name"]), str(i["count"])] for i in items]
    t = Table(rows, colWidths=[80 * mm, 30 * mm], repeatRows=1)
    t.setStyle(grid(colors.HexColor("#5856d6")))
    flow.append(t)


def _r_keyword_dist(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    items = d.get("top_keywords", [])
    if not items:
        flow.append(Paragraph("本期无关键词命中。", ctx["cell_style"]))
        return
    rows = [["关键词", "命中数"]] + [[P(i["word"]), str(i["count"])] for i in items]
    t = Table(rows, colWidths=[80 * mm, 30 * mm], repeatRows=1)
    t.setStyle(grid(colors.HexColor("#00a2a6")))
    flow.append(t)


def _r_risk_category(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    items = d.get("categories", [])
    if not items:
        flow.append(Paragraph("本期无风险分类数据。", ctx["cell_style"]))
        return
    rows = [["风险分类", "数量", "占比"]] + [
        [P(i["label"]), str(i["count"]), f"{i.get('ratio', 0)}%"] for i in items
    ]
    t = Table(rows, colWidths=[70 * mm, 25 * mm, 25 * mm], repeatRows=1)
    t.setStyle(grid(colors.HexColor("#ff9500")))
    flow.append(t)


def _r_alert_summary(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    total = d.get("total", 0)
    flow.append(Paragraph(
        f"本期预警共 {total} 条，已闭环 {d.get('closed', 0)} 条，"
        f"待处置 {d.get('pending', 0)} 条，闭环率 {d.get('closed_rate', 0)}%。",
        ctx["cell_style"],
    ))
    flow.append(Spacer(1, 4))
    if not total:
        return
    rows = [["处置状态", "数量"]] + [[P(i["label"]), str(i["count"])] for i in d.get("by_status", [])]
    t = Table(rows, colWidths=[60 * mm, 30 * mm], repeatRows=1)
    t.setStyle(grid(colors.HexColor("#ff3b30")))
    flow.append(t)
    lv = d.get("by_level", [])
    if lv:
        flow.append(Spacer(1, 4))
        rows2 = [["风险等级", "数量"]] + [[i["level"], str(i["count"])] for i in lv]
        t2 = Table(rows2, colWidths=[60 * mm, 30 * mm], repeatRows=1)
        t2.setStyle(grid(colors.HexColor("#c77700")))
        flow.append(t2)


def _r_opinion_list(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    items = d.get("items", [])
    if not items:
        flow.append(Paragraph("本期无舆情明细。", ctx["cell_style"]))
        return
    rows = [["时间", "标题", "来源", "地区", "风险", "情感"]]
    for o in items:
        rows.append([
            P(o["time"]), P(o["title"]), P(o["source"]),
            P(o["region_name"]), str(o["risk_score"]), o["sentiment"],
        ])
    t = Table(
        rows,
        colWidths=[20 * mm, 62 * mm, 24 * mm, 22 * mm, 12 * mm, 20 * mm],
        repeatRows=1,
    )
    t.setStyle(grid(colors.HexColor("#0071e3")))
    flow.append(t)


def _r_conclusion(flow, d, ctx):
    style = ctx["cell_style"]
    pts = d.get("points", [])
    if not pts:
        flow.append(Paragraph("暂无可输出的结论建议。", style))
        return
    for i, p in enumerate(pts, start=1):
        safe = (p or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        flow.append(Paragraph(f"{i}. {safe}", style))
        flow.append(Spacer(1, 3))


def _r_sentiment(flow, d, ctx):
    P, grid = ctx["P"], ctx["grid"]
    rows = [["情感", "数量"]] + [[s["label"], str(s["count"])] for s in d.get("sentiments", [])]
    t = Table(rows, colWidths=[50 * mm, 30 * mm])
    t.setStyle(grid(colors.HexColor("#86868b")))
    flow.append(t)


# ---- 模块注册表 ------------------------------------------------------------
# 结构：key / name / title / description / data_fn / render_fn /
#       default_enabled / params（前端可配置参数元数据）
def _limit_param(default: int, lo: int, hi: int, label: str = "展示条数") -> list:
    return [{"key": "limit", "label": label, "type": "int",
             "default": default, "min": lo, "max": hi}]


REPORT_MODULES = [
    {
        "key": "overview_kpi",
        "name": "总体态势 KPI",
        "title": "总体态势",
        "description": "统计区间内总量、高风险数、事件数、风险率与负面率等核心指标",
        "data_fn": _m_overview_kpi,
        "render_fn": _r_overview_kpi,
        "default_enabled": True,
        "params": [],
    },
    {
        "key": "trend",
        "name": "舆情趋势",
        "title": "舆情趋势",
        "description": "按日统计的舆情数量走势（按所选时间口径）",
        "data_fn": _m_trend,
        "render_fn": _r_trend,
        "default_enabled": True,
        "params": [],
    },
    {
        "key": "sentiment",
        "name": "情感分布",
        "title": "情感分布",
        "description": "正面 / 负面 / 中性情感占比",
        "data_fn": _m_sentiment,
        "render_fn": _r_sentiment,
        "default_enabled": True,
        "params": [],
    },
    {
        "key": "top_risky",
        "name": "高风险舆情 TOP",
        "title": "高风险舆情 TOP",
        "description": "统计区间内风险评分最高的舆情清单",
        "data_fn": _m_top_risky,
        "render_fn": _r_top_risky,
        "default_enabled": True,
        "params": _limit_param(10, 1, 50),
    },
    {
        "key": "events",
        "name": "重点事件",
        "title": "重点事件",
        "description": "聚合事件及其舆情规模",
        "data_fn": _m_events,
        "render_fn": _r_events,
        "default_enabled": True,
        "params": _limit_param(10, 1, 50),
    },
    {
        "key": "source_dist",
        "name": "来源分布",
        "title": "来源分布",
        "description": "统计区间内各信息来源的舆情数量与占比",
        "data_fn": _m_source_dist,
        "render_fn": _r_source_dist,
        "default_enabled": True,
        "params": _limit_param(10, 1, 30),
    },
    {
        "key": "region_dist",
        "name": "地区分布",
        "title": "地区分布",
        "description": "统计区间内按省级上卷的舆情地域分布",
        "data_fn": _m_region_dist,
        "render_fn": _r_region_dist,
        "default_enabled": True,
        "params": _limit_param(10, 1, 30),
    },
    {
        "key": "keyword_dist",
        "name": "热点关键词",
        "title": "热点关键词",
        "description": "统计区间内命中关键词的频次 TOP",
        "data_fn": _m_keyword_dist,
        "render_fn": _r_keyword_dist,
        "default_enabled": True,
        "params": _limit_param(TOP_KEYWORDS, 1, 50),
    },
    {
        "key": "risk_category",
        "name": "风险分类分布",
        "title": "风险分类分布",
        "description": "按风险分类标签（安全事故 / 社会治安 / 政治敏感 / 其他）统计占比",
        "data_fn": _m_risk_category,
        "render_fn": _r_risk_category,
        "default_enabled": False,
        "params": [],
    },
    {
        "key": "alert_summary",
        "name": "预警处置概览",
        "title": "预警处置概览",
        "description": "统计区间内预警数量、处置状态分布与闭环率",
        "data_fn": _m_alert_summary,
        "render_fn": _r_alert_summary,
        "default_enabled": False,
        "params": [],
    },
    {
        "key": "opinion_list",
        "name": "舆情明细清单",
        "title": "舆情明细清单",
        "description": "按所选时间口径倒序输出舆情明细（可设置条数与最低风险分）",
        "data_fn": _m_opinion_list,
        "render_fn": _r_opinion_list,
        "default_enabled": False,
        "params": _limit_param(50, 1, 200) + [
            {"key": "min_risk", "label": "最低风险分", "type": "int",
             "default": 0, "min": 0, "max": 100}
        ],
    },
    {
        "key": "conclusion",
        "name": "结论建议",
        "title": "结论建议",
        "description": "基于统计结果自动生成的态势结论与处置建议",
        "data_fn": _m_conclusion,
        "render_fn": _r_conclusion,
        "default_enabled": True,
        "params": [],
    },
]
MODULE_MAP = {m["key"]: m for m in REPORT_MODULES}
DEFAULT_MODULE_KEYS = [m["key"] for m in REPORT_MODULES if m.get("default_enabled")]
ALL_MODULE_KEYS = [m["key"] for m in REPORT_MODULES]

# 历史配置兼容：Phase Report-1 的 distribution 已拆分为三个独立模块。
# distribution 不再出现在 /reports/modules 清单中，但请求中出现时自动展开，
# 保证 Phase Report-1.1 已落库的 report_records.config_json 仍可复现。
MODULE_ALIASES: Dict[str, List[str]] = {
    "distribution": ["source_dist", "region_dist", "keyword_dist"],
}


def expand_module_keys(keys: Optional[List[str]]) -> List[str]:
    """展开历史别名并按原顺序去重（不校验合法性，交由 API 层报 400）。"""
    out: List[str] = []
    for k in keys or []:
        for real in MODULE_ALIASES.get(k, [k]):
            if real not in out:
                out.append(real)
    return out


_CN_NUM = "〇一二三四五六七八九十"


def _cn_index(i: int) -> str:
    """章节序号中文化：1->一, 10->十, 12->十二, >20 回退阿拉伯数字。"""
    if i <= 0 or i > 20:
        return str(i)
    if i <= 10:
        return _CN_NUM[i]
    return "十" + (_CN_NUM[i - 10] if i > 10 else "")


def build_report(db: Session, cfg: ReportConfig) -> dict:
    """按配置构建可配置报告的完整数据（含 meta + 有序 modules）。

    单模块取数失败不会中断整份报告：记录日志、回滚事务、在该模块上标记
    error，其余模块继续构建（Phase Report-2-P1 失败隔离要求）。
    """
    ws, we = _resolve_window(db, cfg)
    col = _time_column(cfg.time_field)
    modules: List[dict] = []
    failed: List[str] = []
    for key in expand_module_keys(cfg.module_keys):
        m = MODULE_MAP.get(key)
        if not m:
            logger.warning("报告生成：忽略未知模块 key=%s", key)
            continue
        params = {p["key"]: p.get("default") for p in m.get("params") or []}
        params.update((cfg.module_params or {}).get(key) or {})
        error: Optional[str] = None
        try:
            data = m["data_fn"](db, ws, we, col, params)
        except Exception as exc:  # noqa: BLE001 - 单模块隔离，禁止整份报告 500
            logger.exception("报告模块取数失败：key=%s", key)
            # PG 事务在语句失败后进入 aborted 状态，必须回滚否则后续模块全部失败
            try:
                db.rollback()
            except Exception:  # noqa: BLE001
                logger.exception("报告模块取数失败后回滚异常：key=%s", key)
            data = {}
            error = str(exc)[:200]
            failed.append(key)
        modules.append({
            "key": key,
            "name": m["name"],
            "title": m["title"],
            "data": data,
            "error": error,
        })
    return {
        "meta": {
            "report_name": cfg.report_name or "舆情监测报告",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "time_field": cfg.time_field,
            "time_field_label": TIME_FIELD_LABELS.get(cfg.time_field, "采集时间"),
            "window_label": f"{ws.isoformat()} ~ {we.isoformat()}",
            "window_start": ws.isoformat(),
            "window_end": we.isoformat(),
            "days": (we - ws).days + 1,
            "failed_modules": failed,
        },
        "modules": modules,
    }


def render_report_pdf(report: dict) -> bytes:
    """将可配置报告数据渲染为 A4 PDF 字节流（按 modules 顺序插拔章节）。"""
    font = _register_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "RptTitle", parent=styles["Title"], fontName=font, fontSize=22, leading=26
    )
    sub_style = ParagraphStyle(
        "RptSub", parent=styles["Normal"], fontName=font, fontSize=11,
        textColor=colors.HexColor("#6e6e73"), alignment=TA_CENTER,
    )
    h_style = ParagraphStyle(
        "RptH", parent=styles["Heading2"], fontName=font, fontSize=14,
        textColor=colors.HexColor("#0071e3"), spaceBefore=14, spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "RptCell", parent=styles["Normal"], fontName=font, fontSize=9, leading=12
    )

    def P(text: str, style=cell_style) -> Paragraph:
        safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return Paragraph(safe, style)

    def grid(color):
        return _grid_style(font, color)

    ctx = {"font": font, "P": P, "grid": grid, "h_style": h_style, "cell_style": cell_style}
    meta = report.get("meta", {})

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=meta.get("report_name", "舆情监测报告"),
    )
    flow: list = []
    flow.append(Paragraph(meta.get("report_name", "互联网舆情监测报告"), title_style))
    flow.append(Spacer(1, 4))
    flow.append(Paragraph(
        f"统计口径：{meta.get('time_field_label', '采集时间')}　|　"
        f"统计区间：{meta.get('window_label', '')}　|　生成时间：{meta.get('generated_at', '')}",
        sub_style,
    ))
    flow.append(Spacer(1, 12))

    err_style = ParagraphStyle(
        "RptErr", parent=cell_style, textColor=colors.HexColor("#ff3b30")
    )
    for i, mod in enumerate(report.get("modules", []), start=1):
        flow.append(Paragraph(f"{_cn_index(i)}、{mod.get('title', mod.get('key', ''))}", h_style))
        # 失败隔离：渲染先写入独立子流，成功后再并入主流，
        # 避免半成品元素污染 doc.build 导致整份 PDF 失败。
        sub: list = []
        try:
            if mod.get("error"):
                raise RuntimeError(mod["error"])
            fn = MODULE_MAP[mod["key"]]["render_fn"]
            fn(sub, mod["data"], ctx)
        except Exception as exc:  # noqa: BLE001 - 单模块隔离
            logger.exception("报告模块渲染失败：key=%s", mod.get("key"))
            sub = [Paragraph("该模块生成失败", err_style)]
        flow.extend(sub)
        flow.append(Spacer(1, 6))

    flow.append(Spacer(1, 16))
    flow.append(Paragraph(
        "本报告由舆情监测平台自动生成，数据来源于系统监测库，仅供参考。",
        ParagraphStyle("foot", parent=cell_style, fontSize=8,
                       textColor=colors.HexColor("#a0a0a5"), alignment=TA_CENTER),
    ))
    doc.build(flow)
    return buf.getvalue()
