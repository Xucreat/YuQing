"""Dashboard 统计响应模型（Pydantic v2）。

禁止直接返回 dict / ORM 对象；所有统计响应经本文件序列化。
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class TrendItem(BaseModel):
    """单日舆情数量（趋势图的一个点）。"""

    date: str  # ISO 日期，如 "2026-07-16"
    count: int


class KeywordItem(BaseModel):
    """单个关键词的统计（关键词排行的一项）。"""

    word: str
    count: int


class SourceItem(BaseModel):
    source: str
    count: int


class SentimentItem(BaseModel):
    label: str
    count: int


class RegionItem(BaseModel):
    """单个地区的舆情数量（地理分布的一项）。"""

    region_id: int
    region_name: str
    count: int


class RecentOpinionItem(BaseModel):
    """实时快讯中的一条最新舆情（精简字段）。"""

    id: int
    title: str
    source: str
    sentiment: str
    risk_score: int
    region_name: str
    created_at: str


class DashboardAlertItem(BaseModel):
    """预警滚动中的一条最新预警记录（精简字段）。"""

    id: int
    opinion_id: Optional[int] = None
    rule_name: str
    risk_level: str
    opinion_title: str
    trigger_reason: str
    handled: bool
    created_at: str


class DashboardStatsResponse(BaseModel):
    """驾驶舱统计总览。

    - total:      全部舆情数量（count(opinions.id)）
    - today:      今日新增（依据 created_at，非 publish_time）
    - high_risk:  高风险数量（risk_score >= 阈值，当前 70）
    - trend:      最近 7 日趋势（无数据日期 count=0，已补齐）
    - keywords:   TOP10 关键词（依据 opinions.keywords 逗号拆分统计）
    - regions:    地区舆情分布（依据 opinions.region_id 关联 regions.name）
    """

    total: int
    today: int
    high_risk: int
    event_count: int
    trend: List[TrendItem]
    keywords: List[KeywordItem]
    sources: List[SourceItem]
    sentiments: List[SentimentItem]
    regions: List[RegionItem] = []
