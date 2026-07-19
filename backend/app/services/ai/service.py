"""AI 统一入口（Phase 2C-1：真实调用 + 降级）。

架构：
    Business Layer
        |
      AIService
        |
      Provider
        |-- DeepSeekProvider   （配置且调用成功时优先）
        |-- RuleFallbackProvider（降级：DeepSeek 未配置 / 异常时）

设计约束（来自用户 Phase 2C-1 调整 1 / 2）：
- Provider 层与 AIService 均返回类型化 AIAnalysisResult（不放 dict）。
- AIService 负责调度：有 Key 先 DeepSeek，未配置或异常则降级 RuleFallbackProvider。
- AIService 不直接查询数据库；敏感词列表经构造参数注入 RuleFallbackProvider
  （MVP 默认 None -> 使用内置 DEFAULT_KEYWORDS；未来可由外部从 keywords 表加载后注入）。
- analyze(title, content) 对外签名；内部拼为 text 委托给 provider.analyze(text)，
  保持 provider 兼容 Phase 2C-0 的 analyze(text) 接口。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.schemas.ai import AIAnalysisResult
from app.services.ai.fallback import RuleFallbackProvider
from app.services.ai.providers.deepseek import DeepSeekProvider


class AIService:
    """AI 分析服务统一入口。"""

    def __init__(
        self, keywords: Optional[List[Tuple[str, int]]] = None
    ) -> None:
        # 统一管理 provider；敏感词经构造参数注入 fallback（不直连数据库）。
        self._deepseek: DeepSeekProvider = DeepSeekProvider()
        self._fallback: RuleFallbackProvider = RuleFallbackProvider(keywords)

    @property
    def deepseek(self) -> DeepSeekProvider:
        return self._deepseek

    @property
    def fallback(self) -> RuleFallbackProvider:
        return self._fallback

    def analyze(self, title: str, content: str) -> AIAnalysisResult:
        """分析单条舆情，返回类型化 AIAnalysisResult。

        优先 DeepSeek（已配置时），未配置或任何异常降级 RuleFallbackProvider。
        """
        text = f"标题：{title}\n正文：{content}"
        if self._deepseek.is_configured:
            try:
                return self._deepseek.analyze(text)
            except Exception:
                # DeepSeek 调用 / 解析失败 -> 降级规则分析
                return self._fallback.analyze(text)
        return self._fallback.analyze(text)
