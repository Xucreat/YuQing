"""AI 分析结果 Schema（Phase 2C-1）。

AIAnalysisResult 是 AI 分析的业务领域对象（domain object），
由 DeepSeekProvider / RuleFallbackProvider 统一返回，
AIService 透传，API 层经其字段写库 / model_dump() 序列化。

后续可在本模型扩展：模型信息(model)、置信度(confidence)、token 用量等，
保持类型约束，不回退到裸 dict。
"""
from typing import List, Literal

from pydantic import BaseModel, Field


class AIAnalysisResult(BaseModel):
    """单条舆情 AI 分析结果（统一结构）。"""

    summary: str = Field(..., description="AI 摘要")
    # 情感：positive / negative / neutral
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        ..., description="情感判定"
    )
    # 风险评分 0-100
    risk_score: int = Field(..., ge=0, le=100, description="风险评分 0-100")
    keywords: List[str] = Field(default_factory=list, description="抽取的关键词")
    suggestion: str = Field(..., description="研判建议")

    model_config = {"extra": "forbid"}
