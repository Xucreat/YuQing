"""舆情报告服务：汇总统计 + reportlab 生成 PDF（P2 报告自动生成 + PDF 导出）。

无外部原生依赖（reportlab 纯 Python），可在 Windows 环境稳定生成中文 PDF。
"""
from __future__ import annotations

import io
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.opinion import Opinion
from app.models.region import Region
from app.services.dashboard_service import (
    HIGH_RISK_THRESHOLD,
    TOP_KEYWORDS,
    get_dashboard_stats,
)

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

    # 重点事件 TOP（按舆情数倒序）
    event_rows = (
        db.query(Event)
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
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

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
