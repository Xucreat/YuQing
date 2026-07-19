"""规则降级 Provider（Phase 2C-1：真正落地规则分析）。

当 DeepSeek 未配置或调用失败时，AIService 降级到本 Provider，
基于「敏感词权重」算 risk_score，保证离线 / 演示 / 测试始终可用。

设计约束（来自用户 Phase 2C-1 调整 2）：
- RuleFallbackProvider 只负责规则分析，不查询数据库。
- 敏感词列表经构造参数注入：__init__(keywords=None)。
  为空时使用内置 DEFAULT_KEYWORDS（MVP 阶段默认走内置表）。
  AIService 不直连数据库，仅把外部传入的 keywords 列表透传给本类。
- 输出统一为 AIAnalysisResult（类型化，不放回 dict）。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.schemas.ai import AIAnalysisResult
from app.services.ai.providers.base import BaseAIProvider

# 内置默认敏感词表：(词, 权重)
# 命中一个词：risk_score += 10 * weight。后续可由数据库 keywords 表扩展注入。
DEFAULT_KEYWORDS: List[Tuple[str, int]] = [
    ("火灾", 8),
    ("爆炸", 9),
    ("事故", 6),
    ("伤亡", 9),
    ("死亡", 8),
    ("冲突", 7),
    ("群体", 7),
    ("上访", 8),
    ("维权", 6),
    ("投诉", 4),
    ("谣言", 8),
    ("诈骗", 8),
    ("腐败", 7),
    ("贪污", 7),
    ("涉警", 8),
    ("舆情", 3),
]

# 评分常量
BASE_RISK = 20          # 无命中时的默认风险分
WEIGHT_FACTOR = 10       # 每个命中词增量 = WEIGHT_FACTOR * weight
MAX_RISK = 100          # 封顶
NEGATIVE_THRESHOLD = 70   # 风险 >= 此值判为 negative


class RuleFallbackProvider(BaseAIProvider):
    """基于规则/敏感词权重的降级分析。"""

    def __init__(
        self, keywords: Optional[List[Tuple[str, int]]] = None
    ) -> None:
        # 敏感词列表：外部注入（如未来从 keywords 表加载），
        # 为空则退回内置 DEFAULT_KEYWORDS。本类不查数据库。
        self.keywords: List[Tuple[str, int]] = list(keywords) if keywords else list(DEFAULT_KEYWORDS)

    def analyze(self, text: str) -> AIAnalysisResult:
        """对文本做规则分析，返回 AIAnalysisResult。"""
        hits: List[str] = []
        for word, _weight in self.keywords:
            if word and word in text:
                hits.append(word)

        risk_score = BASE_RISK + sum(
            WEIGHT_FACTOR * weight
            for word, weight in self.keywords
            if word in hits
        )
        risk_score = min(risk_score, MAX_RISK)

        sentiment = "negative" if risk_score >= NEGATIVE_THRESHOLD else "neutral"

        if hits:
            summary = (
                "系统规则分析：根据关键词命中情况生成摘要。"
                f"共命中敏感词 {len(hits)} 个：{', '.join(hits)}。"
            )
            suggestion = (
                "系统规则分析：\n"
                "发现敏感关键词，请关注事件传播情况，"
                "建议相关部门及时核查信息并做好舆情回应准备。"
            )
        else:
            summary = "系统规则分析：未命中已知敏感词，风险较低。"
            suggestion = (
                "系统规则分析：\n"
                "暂未发现明显敏感关键词，建议保持常规监测，"
                "关注后续传播动态。"
            )

        return AIAnalysisResult(
            summary=summary,
            sentiment=sentiment,
            risk_score=risk_score,
            keywords=hits,
            suggestion=suggestion,
        )
