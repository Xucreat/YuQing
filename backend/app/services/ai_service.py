"""AI 服务：封装 DeepSeek，业务代码禁止直接调用 DeepSeek（Phase 2 细化）。

analyze(text) -> AIAnalyseResult：
  {
    "summary": "",
    "sentiment": "positive|negative|neutral",
    "risk_score": 0,
    "keywords": [],
    "suggestion": ""
  }

降级：DEEPSEEK_API_KEY 缺失或调用异常时，自动切换到 RuleBasedAnalyzer，
依据敏感词表计算 risk_score，保证离线演示可用。
"""
from abc import ABC, abstractmethod
from typing import Any


class AIService(ABC):
    @abstractmethod
    def analyze(self, text: str) -> dict[str, Any]:
        raise NotImplementedError


# TODO(Phase 2): DeepSeekService(AIService) + RuleBasedAnalyzer(AIService)
# TODO(Phase 2): 工厂函数 get_ai_service() 按环境变量选择实现
