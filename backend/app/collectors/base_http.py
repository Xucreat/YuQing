"""HTTP 采集基类（Phase 3：抽象共享能力，不破坏 BaseCollector 契约）。

承载「列表→详情」类站点的公共能力：
  - 防御式 HTTP 抓取（带可配置重试 + 指数退避）；
  - 限流（请求间隔，避免连续请求政府/新闻网站）；
  - 正文按优先级降级提取（复用 common.extract_article_text）；
  - 关键词过滤（复用 common.matches_keywords）。

供 GenericSiteCollector 及未来标准采集器继承；现有 9 个 bespoke 采集器
（Government/Xinhua/...）**不改动**，继续独立使用，保证迁移零回归。

所有采集器禁止直接操作数据库：fetch() -> 标准化 dict 列表 -> CollectorService 入库。
"""
from __future__ import annotations

import logging
import time
from typing import Any, List, Optional

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.collectors.common import (
    DEFAULT_CONTENT_SELECTORS,
    DEFAULT_UA,
    extract_article_text,
    http_get,
    make_session,
    matches_keywords,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class BaseHttpCollector(BaseCollector):
    """共享 HTTP 采集能力的抽象基类（自身不直接实例化）。"""

    source_name: str = "base_http"

    # 子类/配置可覆盖的默认值
    DEFAULT_TIMEOUT: int = 10
    REQUEST_INTERVAL: float = 0.3
    MAX_RETRIES: int = 1
    RETRY_BACKOFF: float = 1.0
    MAX_ARTICLES: int = 10
    CONTENT_SELECTORS: List[str] = DEFAULT_CONTENT_SELECTORS

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config: dict = dict(config or {})
        self.session = make_session(DEFAULT_UA)
        self.timeout: int = int(self.config.get("timeout", self.DEFAULT_TIMEOUT))
        self.request_interval: float = float(
            self.config.get("request_interval", self.REQUEST_INTERVAL)
        )
        self.max_retries: int = int(self.config.get("max_retries", self.MAX_RETRIES))
        self.retry_backoff: float = float(
            self.config.get("retry_backoff", self.RETRY_BACKOFF)
        )
        self.max_articles: int = int(self.config.get("max_articles", self.MAX_ARTICLES))
        kw = self.config.get("keywords")
        if kw is None:
            kw = settings.collector_keywords
        self.keywords: List[str] = (
            [k.strip() for k in kw.split(",") if k.strip()]
            if isinstance(kw, str)
            else list(kw or [])
        )
        # 是否通过 config_json 显式配置过 keywords（含空串=放行全部）。
        # 显式配置时逐源覆盖全局监测词；未配置时由 fetch 注入全局监测词。
        self.keywords_explicit: bool = "keywords" in self.config

    # ------------------------------------------------------------------
    # 共享能力
    # ------------------------------------------------------------------
    def _get(self, url: str) -> Optional[str]:
        """防御式 GET（带重试 + 指数退避）。任何失败返回 None，不崩溃。"""
        for attempt in range(self.max_retries + 1):
            html = http_get(self.session, url, self.timeout)
            if html:
                return html
            if attempt < self.max_retries:
                time.sleep(self.retry_backoff * (attempt + 1))
        logger.warning("抓取失败(重试耗尽) url=%s", url)
        return None

    def rate_limit(self) -> None:
        """请求间隔限流（>=0 时生效）。"""
        if self.request_interval > 0:
            time.sleep(self.request_interval)

    def extract_content(self, soup: BeautifulSoup, selectors: Optional[List[str]] = None) -> str:
        """按优先级降级提取正文（复用 common）。"""
        return extract_article_text(soup, selectors or self.CONTENT_SELECTORS, use_paragraphs=True)

    def match(self, text: str, keywords: Optional[List[str]] = None) -> bool:
        """关键词过滤：空关键词放行全部。

        keywords 优先级：显式传入（来自 keywords 表，经 fetch 注入）>
        self.keywords（来自 config_json.keywords 或 settings 兜底）。
        """
        kws = keywords if keywords is not None else self.keywords
        return matches_keywords(text, kws)
