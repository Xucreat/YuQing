"""DeepSeek Provider（Phase 2C-1：真实调用）。

使用 OpenAI SDK 兼容方式调用 DeepSeek：
    from openai import OpenAI
    client = OpenAI(api_key=..., base_url=settings.deepseek_base_url)
    client.chat.completions.create(model=..., messages=[...])

设计要点：
- 配置全部来自 settings（禁止硬编码）：api_key / base_url / model / timeout / max_retries。
- 统一底层调用入口 `_chat_json(messages, schema)`：OpenAI 调用 + 去代码围栏 + pydantic 校验。
  所有上层方法（analyze / generate_event_narrative）共用此唯一调用路径，
  不引入第二套 LLM 调用封装（Phase C-Event-2 约束）。
- analyze(text) 返回 AIAnalysisResult（类型化，不放 dict）。
- generate_event_narrative(context) 返回 EventNarrative（事件级叙事，类型化）。
- 任何异常（未配置 / 网络超时 / JSON 解析 / 校验失败）一律向上抛，
  由调用方（AIService 或 Event-2 编排器）捕获并降级。
- 超时由 settings.deepseek_timeout 控制；限流/5xx 由 SDK 内置退避重试处理。
- 增加 logging：记录调用耗时、是否降级、错误类型，提升可观测性。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Type

from openai import OpenAI

from app.core.config import settings
from app.schemas.ai import AIAnalysisResult
from app.services.ai.providers.base import BaseAIProvider

logger = logging.getLogger(__name__)

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

# 事件级叙事系统提示（Phase C-Event-2）。
EVENT_NARRATIVE_SYSTEM = (
    "你是一名资深舆情分析师。"
    "你的任务是为「已经聚类完成的一个事件」撰写标题与描述。"
    "注意：输入的多条舆情已被系统判定属于同一事件，"
    "你只需基于这些事实撰写叙事，不得假设或引入事件之外的任何信息。"
)

EVENT_NARRATIVE_USER_TEMPLATE = (
    "以下是某个事件（已聚类）的成员舆情事实。请仅基于这些事实撰写事件标题和描述。\n\n"
    "【事件级别事实】\n"
    "- 风险等级：{risk_level}\n"
    "- 关联舆情条数：{opinion_count}\n"
    "- 时间跨度：{first_time} 至 {last_time}\n"
    "- 合并关键词：{keywords}\n\n"
    "【成员舆情（已按时间先后排列，已脱敏，不含原文链接与作者身份）】\n"
    "{members}\n\n"
    "【撰写要求】\n"
    "1. title：一句话事件标题（不超过 80 字），准确概括该事件；"
    "禁止包含未在上述事实中出现的地点、人物、机构、数字或时间。\n"
    "2. description：一段连贯描述（不超过 400 字），按时间顺序说明事件发展；"
    "如成员来源平台不同可说明涉及来源；如风险等级不同可说明；"
    "禁止重复罗列，禁止虚构任何事实。\n"
    "3. 仅输出 JSON，不要输出其他文字：\n"
    "{{\n"
    '  "title": "事件标题",\n'
    '  "description": "事件描述"\n'
    "}}"
)

# 匹配 ```json ... ``` 或 ``` ... ```
_FENCE_RE = __import__("re").compile(r"^```(?:json)?\s*(.*?)\s*```$", __import__("re").DOTALL)


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


def _parse_json_to_model(raw: str, schema: Type[Any]) -> Any:
    """解析 LLM 返回文本为指定 pydantic 模型（失败抛异常）。"""
    cleaned = _strip_code_fence(raw)
    data: Dict[str, Any] = json.loads(cleaned)  # JSONDecodeError -> 上浮
    return schema.model_validate(data)  # ValidationError -> 上浮


def _parse_ai_json(raw: str) -> AIAnalysisResult:
    """解析 DeepSeek 返回文本为 AIAnalysisResult（失败抛异常）。"""
    return _parse_json_to_model(raw, AIAnalysisResult)


class DeepSeekProvider(BaseAIProvider):
    """DeepSeek 模型 Provider（OpenAI 兼容）。"""

    def __init__(self) -> None:
        self.api_key: str = settings.deepseek_api_key
        self.base_url: str = settings.deepseek_base_url
        self.model: str = settings.deepseek_model
        self.timeout: float = settings.deepseek_timeout
        self.max_retries: int = settings.deepseek_max_retries
        self._client: OpenAI | None = None

    @property
    def is_configured(self) -> bool:
        """是否已配置可用（API Key 非空）。"""
        return bool(self.api_key)

    def _get_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=self.max_retries,
            )
        return self._client

    def _chat_json(self, messages: list[dict], schema: Type[Any]) -> Any:
        """唯一底层调用入口：OpenAI 调用 + 去围栏 + pydantic 校验。

        任何失败（未配置 / 网络超时 / JSON 解析 / 校验失败）一律向上抛，
        由调用方决定降级策略。
        """
        if not self.is_configured:
            raise RuntimeError("DeepSeek API key 未配置，无法调用")
        client = self._get_client()
        t0 = time.perf_counter()
        try:
            resp = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001 — 统一上抛，由上层降级
            logger.warning("DeepSeek 调用失败（%.1fms）: %s", (time.perf_counter() - t0) * 1000, exc)
            raise
        raw = resp.choices[0].message.content or ""
        logger.info(
            "DeepSeek 调用成功（%.1fms, %d 字符）",
            (time.perf_counter() - t0) * 1000,
            len(raw),
        )
        return _parse_json_to_model(raw, schema)

    def analyze(self, text: str) -> AIAnalysisResult:
        """调用 DeepSeek 返回结构化结果；任何失败一律上抛以便降级。"""
        return self._chat_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": USER_PROMPT_TEMPLATE.format(text=text),
                },
            ],
            AIAnalysisResult,
        )

    def generate_event_narrative(self, context: dict) -> "Any":
        """调用 DeepSeek 为单个事件生成标题/描述；失败一律上抛由编排器降级。"""
        from app.schemas.event_narrative import EventNarrative

        members_block = context.get("members_block") or ""
        user = EVENT_NARRATIVE_USER_TEMPLATE.format(
            risk_level=context.get("risk_level", ""),
            opinion_count=context.get("opinion_count", 0),
            first_time=context.get("first_time") or "未知",
            last_time=context.get("last_time") or "未知",
            keywords=context.get("keywords") or "",
            members=members_block,
        )
        return self._chat_json(
            [
                {"role": "system", "content": EVENT_NARRATIVE_SYSTEM},
                {"role": "user", "content": user},
            ],
            EventNarrative,
        )
