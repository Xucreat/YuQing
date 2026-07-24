"""中国新闻网采集器（Phase 2）。

数据源：中国新闻网 RSS 滚动新闻 https://www.chinanews.com.cn/rss/scroll-news.xml
（经实测可用，返回 30 条/次，含标题、摘要、链接）。

采用 RSS 而非 HTML 抓取：维护成本最低、结构稳定、不受前端改版影响。
复用 common.parse_rss（与既有 RSSCollector 同一套解析逻辑）。
"""
from __future__ import annotations

import logging
from typing import Any

from app.collectors.base import BaseCollector
from app.collectors.common import (
    DEFAULT_UA,
    http_get,
    make_session,
    matches_keywords,
    parse_publish_date_from_url,
    parse_rss,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

RSS_URL = "https://www.chinanews.com.cn/rss/scroll-news.xml"
TIMEOUT = 15


class ChinanewsCollector(BaseCollector):
    """中国新闻网采集器（RSS）。"""

    source_name = "中国新闻网"

    def __init__(self, keywords: str | None = None) -> None:
        self.session = make_session(DEFAULT_UA)
        kw = keywords if keywords is not None else settings.collector_keywords
        self.keywords: list[str] = [k.strip() for k in kw.split(",") if k.strip()]

    def fetch(self, keywords=None) -> list[dict[str, Any]]:
        xml = http_get(self.session, RSS_URL, TIMEOUT)
        if not xml:
            return []
        items = parse_rss(xml)
        results: list[dict[str, Any]] = []
        for it in items:
            text = (it["title"] or "") + " " + (it["content"] or "")
            effective_kw = keywords if keywords is not None else self.keywords
            if not matches_keywords(text, effective_kw):
                continue
            results.append(
                {
                    "title": it["title"],
                    "content": it["content"] or it["title"],
                    "source": self.source_name,
                    "url": it["url"],
                    # 优先用 RSS 提供的发布时间；RSS 缺失时回退到 URL 路径中的日期
                    # （中国新闻网文章 URL 形如 /gn/2026/07-24/...，含真实发布日期）。
                    "publish_time": it.get("publish_time")
                    or parse_publish_date_from_url(it["url"]),
                }
            )
        return results
