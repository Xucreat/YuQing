"""舆情相关 Pydantic 模型（Phase 2A：基础 CRUD；Phase 2C-0：补充 AI 字段）。

禁止直接返回 ORM 对象，统一经 Pydantic 序列化。
注意：opinions 表无 suggestion 列（研判建议由后续 AI 阶段补充），
故响应模型仅包含当前已存在的字段。
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class OpinionBase(BaseModel):
    """创建/更新共用的基础字段。"""

    title: str
    content: str
    source: str
    url: str
    region_id: int
    publish_time: datetime | None = None


class OpinionCreate(OpinionBase):
    """创建舆情请求体（供未来 Collector 写入）。

    创建后默认 risk_score=0、sentiment="neutral"、analysis_status="pending"，由服务端填充。
    """

    pass


class OpinionOut(OpinionBase):
    """完整舆情响应（列表项与详情共用）。"""

    id: int
    risk_score: int
    sentiment: str
    summary: str
    keywords: str
    created_at: datetime

    # ===== Phase 2C-0：AI 分析状态字段 =====
    analysis_status: str = "pending"
    analysis_time: Optional[datetime] = None
    # ===== Phase 2C-1：AI 研判建议 =====
    analysis_suggestion: Optional[str] = None

    # ===== AI 研判报告（DeepSeek，手动「触发 AI 分析」生成；与系统研判报告区分）=====
    ai_summary: str = ""
    ai_sentiment: str = "neutral"
    ai_risk_score: int = 0
    ai_keywords: str = ""
    ai_analysis_status: str = "pending"
    ai_analysis_time: Optional[datetime] = None
    ai_analysis_suggestion: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class OpinionListResponse(BaseModel):
    """分页列表响应。"""

    items: List[OpinionOut]
    total: int
    page: int
    size: int
