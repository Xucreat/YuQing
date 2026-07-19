"""AI Provider 抽象基类（Phase 2C-0：仅定义接口，不实现调用）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAIProvider(ABC):
    """所有 AI Provider（DeepSeek / Fallback）的统一接口。"""

    @abstractmethod
    def analyze(self, text: str) -> Dict[str, Any]:
        """对文本做舆情分析，返回统一结构。

        统一输出字段：
            summary: str
            sentiment: "positive" | "negative" | "neutral"
            risk_score: int (0-100)
            keywords: list[str]
        """
        raise NotImplementedError
