"""Grok 实时搜索辅助采集源（Phase Grok-2）。

定位：仅作为「辅助线索采集源」，绝不是 AI 分析模型。
   职责：关键词 → Grok API（Live Search）→ 解析 citations → 输出标准原始舆情 dict。
   不进入 AI 分析链路：不调用 DeepSeek / AIService / RuleFallbackProvider / RiskEngine。

设计约束（与现有采集器一致）：
  - 继承 BaseCollector；fetch(keywords=None) 契约对齐 BaiduNewsCollector。
  - Collector 禁止直接操作数据库（不写库、不评分、不建 Event）。
  - 只采集 Grok 返回的 citations（真实 url + title + snippet）：
      * title 仅来自 citation.title
      * content 仅允许来自 citation.snippet（即真实页面的摘要文本）
      * 严禁把 Grok「生成回答正文」写入 opinion.content
      * 无 url 的 citation 直接丢弃（避免空 url 进入去重/上报口径）
  - 配置全部来自 settings（GROK_* 环境变量），API Key 绝不进入 data_sources.config_json。
  - 代理：设置 GROK_PROXY 时显式注入 httpx 代理；否则复用 openai 默认 httpx 客户端
    （trust_env=True，自动继承 HTTPS_PROXY），与「命令行可达 ≠ 服务可达」的生产约束一致。
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Tuple

from openai import OpenAI

from app.collectors.base import BaseCollector
from app.core.config import settings

logger = logging.getLogger(__name__)


class GrokCollector(BaseCollector):
    """Grok 实时搜索辅助采集器（仅采集真实 citations）。"""

    source_name = "Grok实时搜索"
    data_source_key = "grok_search"

    def __init__(self, **kwargs: Any) -> None:
        # 配置全部来自 settings（GROK_* 环境变量），不接收 config_json 中的敏感/冗余键。
        # 允许 cls(**cfg) 以空 config_json={} 装配；忽略未来可能传入的非敏感键。
        super().__init__()

    # ------------------------------------------------------------------
    # 客户端构建（API Key 缺失即硬失败，交由 CollectorService 记录为失败）
    # ------------------------------------------------------------------
    def _build_client(self) -> OpenAI:
        api_key = settings.grok_api_key
        if not api_key:
            raise RuntimeError(
                "GROK_API_KEY 未配置：GrokCollector 无法运行"
                "（请在生产 .env 设置 GROK_API_KEY，禁止写入 data_sources.config_json）"
            )
        base_url = settings.grok_base_url or "https://api.x.ai/v1"
        kwargs: dict = {
            "api_key": api_key,
            "base_url": base_url,
            "timeout": 30.0,
            "max_retries": 2,
        }
        # 显式代理优先；未设置时复用 openai 默认 httpx 客户端（trust_env 继承 HTTPS_PROXY）
        proxy = settings.grok_proxy
        if proxy:
            import httpx

            kwargs["http_client"] = httpx.Client(proxy=proxy, trust_env=True)
        return OpenAI(**kwargs)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def fetch(self, keywords: Optional[List[str]] = None) -> List[dict]:
        keywords = keywords or []
        if not keywords:
            logger.info("GrokCollector: 未提供关键词，跳过采集")
            return []

        # API Key 缺失：整体硬失败（在逐关键词容错之外），让 CollectorService 记录失败，
        # 而非静默返回空结果伪装成「采集成功 0 条」。
        if not settings.grok_api_key:
            raise RuntimeError(
                "GROK_API_KEY 未配置：GrokCollector 无法运行"
                "（请在生产 .env 设置 GROK_API_KEY，禁止写入 data_sources.config_json）"
            )

        client = self._build_client()
        max_per_kw = max(1, settings.grok_search_count)
        results: List[dict] = []

        for kw in keywords:
            try:
                citations = self._search_one(client, kw)
            except Exception as exc:  # noqa: BLE001 — 单关键词失败隔离，不拖垮整体
                logger.warning("GrokCollector: 关键词[%s] 查询失败，已跳过: %s", kw, exc)
                continue

            for url, title, snippet in citations[:max_per_kw]:
                if not url:
                    # 无 url citation 直接丢弃（双保险；_extract_citations 已过滤）
                    continue
                results.append(
                    {
                        "title": title or kw,
                        "content": snippet or "",  # 仅 citation snippet，绝不用生成文本
                        "source": self.source_name,
                        "url": url,
                        "publish_time": None,  # Grok citations 无可靠发布时间；交由既有去重/过滤处理
                    }
                )

        logger.info(
            "GrokCollector: 关键词 %d 个，解析得到有效 citation %d 条",
            len(keywords),
            len(results),
        )
        return results

    # ------------------------------------------------------------------
    # 单次关键词检索
    # ------------------------------------------------------------------
    def _search_one(self, client: OpenAI, keyword: str) -> List[Tuple[str, Optional[str], str]]:
        """调用 Grok Live Search，返回 [(url, title, snippet), ...]。

        仅解析 citations，绝不读取模型「生成回答正文」。
        """
        response = client.chat.completions.create(
            model=settings.grok_model or "grok-4.20",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个检索助手。仅基于网络搜索返回的引用(citations)提供信息，"
                        "不得自行编造或补充任何内容。"
                    ),
                },
                {
                    "role": "user",
                    "content": f'请检索与「{keyword}」相关的最新公开信息，并使用网络搜索。',
                },
            ],
            # xAI Live Search：开启网页搜索并要求返回 citations。
            # 若运营方所用 xAI 版本参数名不同，可在此调整，不影响其他采集链路。
            search_parameters={"mode": "on", "return_citations": True},
            max_tokens=2000,
            temperature=0,
        )
        return self._extract_citations(response)

    # ------------------------------------------------------------------
    # citations 解析（只取真实 url/title/snippet；无 url 丢弃）
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_citations(response: Any) -> List[Tuple[str, Optional[str], str]]:
        """从 Grok 响应中提取 citations。

        兼容两种形态：
          - xAI 顶层 response.citations（list[Citation]，含 url/title/content）
          - OpenAI 风格 message.annotations（dict 或对象）
        无论哪种，只要没有 url 就丢弃。
        """
        raw = getattr(response, "citations", None)
        if not raw:
            try:
                msg = response.choices[0].message
                raw = getattr(msg, "annotations", None) or []
            except Exception:  # noqa: BLE001
                raw = []

        out: List[Tuple[str, Optional[str], str]] = []
        for c in (raw or []):
            if isinstance(c, dict):
                url = c.get("url")
                title = c.get("title")
                snippet = c.get("content") or c.get("text") or c.get("snippet") or ""
            else:
                url = getattr(c, "url", None)
                title = getattr(c, "title", None)
                snippet = (
                    getattr(c, "content", None)
                    or getattr(c, "text", None)
                    or getattr(c, "snippet", None)
                    or ""
                )
            if not url:
                # 规则：无 url citation 直接丢弃
                continue
            out.append((url, title, snippet or ""))
        return out
