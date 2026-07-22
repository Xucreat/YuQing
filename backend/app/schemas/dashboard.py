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
    """单个地区的舆情数量（地理分布的一项）。

    指挥大屏 Phase 1 后：regions 已按省级上卷，region_name 仅含省级（如「河北省」），
    不再出现市/县名称。
    """

    region_id: int
    region_name: str
    count: int


class RegionChildCity(BaseModel):
    """地图下钻：某省下属「市」的上卷结果（含所辖县计数），用于按市着色。

    - code：市级行政区划 code（与 GeoJSON 的 adcode 同口径，便于前端按名称匹配）。
    - name：市级全称（如「石家庄市」），与市级 GeoJSON feature name 一致。
    - count：该市（含所辖县）窗口内舆情总量。
    """

    code: str
    name: str
    count: int


class RegionChildRaw(BaseModel):
    """地图下钻：该市/县原始明细（侧栏或悬浮辅助展示）。"""

    region_name: str
    count: int
    level: str


class RegionChildrenResponse(BaseModel):
    """指挥大屏地图点击省级后的下钻响应。

    - province / province_code：被点击的省。
    - total：该省窗口内舆情总量（市+县合计）。
    - cities：按市上卷后的分布（地图着色用）。
    - raw：该市/县原始明细（剔除省级汇总）。
    """

    province: str
    province_code: str
    total: int
    cities: List[RegionChildCity]
    raw: List[RegionChildRaw]


class HotKeywordItem(BaseModel):
    """指挥大屏「热门关键词」的一项。

    - keyword: 监测关键词（来自 keywords 表）
    - count:   窗口内真实「提及」的舆情条数（每条舆情最多计 1 次，已去重）
    - trend:   相对前一个等长窗口的趋势：up / down / flat（真实对比，非伪造）
    """

    keyword: str
    count: int
    trend: str


class HotKeywordsResponse(BaseModel):
    """热门关键词响应。days 回显实际使用的窗口天数。"""

    items: List[HotKeywordItem]
    days: int


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
    """驾驶舱统计总览（指挥大屏 Phase 1 数据契约）。

    口径约定：
    - 累计指标（不受 days 影响）：total / event_count / high_risk
    - 当日指标：today（依据 created_at 的今日）
    - 时间窗口指标（days 控制）：trend / sentiments / sources / regions / region_detail / hot_keywords
    - regions：指挥大屏中国地图专用，已按省级上卷（仅含省级，如「河北省」）。
    - region_detail：驾驶舱「地区舆情 TOP」卡片专用，按市/县实际层级细分、剔除省级汇总，
      避免卡片仅显示「河北省」而过于空泛；前端地理分布卡片请消费本字段。
    - keywords：[兼容字段] 全量，来自 opinions.keywords（敏感词命中集合），旧 Dashboard 词云用；
      指挥大屏请改用 hot_keywords。
    - high_risk 业务语义为系统高危态势（全量），如需窗口化请在产品侧确认。
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
    region_detail: List[RegionItem] = []
    hot_keywords: List[HotKeywordItem] = []
