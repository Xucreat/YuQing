"""舆情报告响应模型（P2 报告自动生成 + PDF 导出）。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from app.schemas.dashboard import (
    KeywordItem,
    RegionItem,
    SentimentItem,
    SourceItem,
    TrendItem,
)


class ReportOpinionItem(BaseModel):
    """高风险舆情 TOP 条目。"""

    id: int
    title: str
    source: str
    region_name: str
    risk_score: int
    sentiment: str
    created_at: str
    summary: str


class ReportEventItem(BaseModel):
    """重点事件条目。"""

    id: int
    title: str
    risk_level: str
    opinion_count: int


class ReportOverviewResponse(BaseModel):
    """舆情报告总览（JSON，供前端预览 / PDF 渲染共用）。"""

    generated_at: str
    period_days: int
    total: int
    today: int
    high_risk: int
    event_count: int
    risk_rate: float
    negative_rate: float
    trend: List[TrendItem]
    top_keywords: List[KeywordItem]
    top_sources: List[SourceItem]
    top_regions: List[RegionItem]
    top_risky: List[ReportOpinionItem]
    events: List[ReportEventItem]
    sentiments: List[SentimentItem]
