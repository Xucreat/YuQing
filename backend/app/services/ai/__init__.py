"""AI 分析服务（Phase 2C-0：基础架构，未接入真实模型）。

业务代码统一经 AIService.analyze()，禁止直连 DeepSeek / Provider。
"""
from app.services.ai.fallback import RuleFallbackProvider
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.deepseek import DeepSeekProvider
from app.services.ai.service import AIService

__all__ = [
    "AIService",
    "BaseAIProvider",
    "DeepSeekProvider",
    "RuleFallbackProvider",
]
