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
    matches_region_topic,
    parse_publish_date_from_url,
    parse_rss,
)
from app.collectors.source_config import apply_keyword_scope
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

    def fetch(self, keywords=None, region_kw=None, topic_kw=None) -> list[dict[str, Any]]:
        # 采集参数改为「配置优先、代码默认兜底」（Phase DataSource-Config-1）；
        # max_items 默认 None = 不截断（与改造前一致，RSS 全量返回）；
        # filter_mode 默认 region_or_topic（国家级媒体 = 全国主题雷达）。
        cfg = self.source_config
        max_items = cfg.max_items(None)
        filter_mode = cfg.filter_mode("region_or_topic")
        region_kw, topic_kw = apply_keyword_scope(cfg.keyword_scope(), region_kw, topic_kw)

        xml = http_get(self.session, RSS_URL, TIMEOUT)
        if not xml:
            return []
        items = parse_rss(xml)
        results: list[dict[str, Any]] = []
        for it in items:
            if max_items is not None and len(results) >= max_items:
                break
            text = (it["title"] or "") + " " + (it["content"] or "")
            if region_kw is not None:
                # 国家级媒体（中国新闻网）= 全国主题雷达：地域命中 或 主题命中即通过。
                if not matches_region_topic(
                    text,
                    region_kw or [],
                    topic_kw or [],
                    match_mode=filter_mode,
                ):
                    continue
            else:
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
