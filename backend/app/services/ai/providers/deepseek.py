"""DeepSeek Provider（Phase 2C-1：真实调用）。

使用 OpenAI SDK 兼容方式调用 DeepSeek：
    from openai import OpenAI
    client = OpenAI(api_key=..., base_url=settings.deepseek_base_url)
    client.chat.completions.create(model=..., messages=[...])

设计要点：
- 配置全部来自 settings（禁止硬编码）：api_key / base_url / model。
- analyze(text) 返回 AIAnalysisResult（类型化，不放 dict）。
- 解析兼容 ```json ... ``` 代码块：strip fence -> json.loads -> AIAnalysisResult.model_validate。
- 任何异常（未配置 / 网络 / JSON 解析 / 校验失败）一律向上抛，
  由 AIService 捕获并降级到 RuleFallbackProvider。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from openai import OpenAI

from app.core.config import settings
from app.schemas.ai import AIAnalysisResult
from app.services.ai.providers.base import BaseAIProvider

SYSTEM_PROMPT = (
    "你是一名公安互联网舆情分析专家。"
    "请根据提供的信息进行风险研判，并严格只返回 JSON。"
)

USER_PROMPT_TEMPLATE = (
    "请对以下互联网舆情进行风险研判，并严格按 JSON 格式返回结果。\n\n"
    "【舆情内容】\n{text}\n\n"
    "返回 JSON 结构（不要输出 JSON 以外的任何说明文字）：\n"
    "{{\n"
    '  "summary": "舆情摘要（中文，1-2 句）",\n'
    '  "sentiment": "positive | negative | neutral",\n'
    '  "risk_score": 0,\n'
    '  "keywords": ["关键词1", "关键词2"],\n'
    '  "suggestion": "研判建议（中文，1-2 句）"\n'
    "}}"
)

# 匹配 ```json ... ``` 或 ``` ... ```
_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _strip_code_fence(raw: str) -> str:
    """去除 LLM 可能包裹的 markdown 代码块。"""
    if raw is None:
        return ""
    text = raw.strip()
    # 可能带 BOM / 零宽字符
    text = text.lstrip("﻿")
    m = _FENCE_RE.match(text)
    if m:
        return m.group(1).strip()
    return text


def _parse_ai_json(raw: str) -> AIAnalysisResult:
    """解析 DeepSeek 返回文本为 AIAnalysisResult（失败抛异常）。"""
    cleaned = _strip_code_fence(raw)
    data: Dict[str, Any] = json.loads(cleaned)  # JSONDecodeError -> 上浮
    return AIAnalysisResult.model_validate(data)  # ValidationError -> 上浮


class DeepSeekProvider(BaseAIProvider):
    """DeepSeek 模型 Provider（OpenAI 兼容）。"""

    def __init__(self) -> None:
        self.api_key: str = settings.deepseek_api_key
        self.base_url: str = settings.deepseek_base_url
        self.model: str = settings.deepseek_model
        self._client: OpenAI | None = None

    @property
    def is_configured(self) -> bool:
        """是否已配置可用（API Key 非空）。"""
        return bool(self.api_key)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def analyze(self, text: str) -> AIAnalysisResult:
        """调用 DeepSeek 返回结构化结果；任何失败一律上抛以便降级。"""
        if not self.is_configured:
            raise RuntimeError("DeepSeek API key 未配置，无法调用")

        client = self._get_client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(text=text),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = resp.choices[0].message.content or ""
        return _parse_ai_json(raw)
