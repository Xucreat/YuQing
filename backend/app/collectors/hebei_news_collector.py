"""Hebei local news collector (P1, Phase 2 复用 common 公共函数).

RSS feeds at hebnews.cn / lfnews.cn are no longer available (301/HTML, 502).
Now scrapes the actual news listing pages and article detail pages,
following the same defensive-scraping pattern, but reusing common.http_get /
common.extract_links / common.extract_article_text instead of a private copy.

The list link filter (a[href*='content_']) and keyword filter are site-specific
and kept here; the generic request/parse is delegated to common.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.collectors.common import (
    DEFAULT_UA,
    extract_article_text,
    extract_links,
    extract_publish_time,
    http_get,
    make_session,
    matches_keywords,
    matches_region_topic,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# News listing pages: these are live and scrapeable.
DEFAULT_URLS = [
    "https://lf.hebnews.cn/",      # Langfang channel (nearest to Dachang)
    "https://hebei.hebnews.cn/",   # Hebei province channel
]

REQUEST_INTERVAL = 0.3
TIMEOUT = 10


class HebeiNewsCollector(BaseCollector):
    """Scrape hebnews.cn listing pages for keyword-filtered articles."""

    source_name = "河北新闻网"

    def __init__(self, urls: list[str] | None = None) -> None:
        feed_val = getattr(settings, "hebei_news_feeds", "")
        if feed_val and isinstance(feed_val, str) and feed_val.strip():
            self.urls = [u.strip() for u in feed_val.split(",") if u.strip()]
        elif urls:
            self.urls = list(urls)
        else:
            self.urls = list(DEFAULT_URLS)

        self.session = make_session(DEFAULT_UA)
        kw = settings.collector_keywords
        self.keywords = [k.strip() for k in kw.split(",") if k.strip()]

    def fetch(self, keywords=None, region_kw=None, topic_kw=None) -> list[dict[str, Any]]:
        # region_kw 非空 → 走地域前置过滤；否则退回旧 OR（向后兼容）。
        use_region = region_kw is not None
        effective_kw = keywords if keywords is not None else self.keywords
        # 单次抓取上限：可经 config_json.max_items 覆盖（默认 10，与原行为一致）
        max_items = self.source_config.max_items(10)
        candidate_cap = max(20, max_items * 2)
        if not self.urls:
            return []
        if not use_region and not effective_kw:
            return []

        # 1) collect article links from listing pages
        candidates: list[dict[str, str]] = []
        seen: set[str] = set()

        for list_url in self.urls:
            html = http_get(self.session, list_url, TIMEOUT)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for art in extract_links(soup, list_url, href_contains="content_"):
                if art["url"] in seen:
                    continue
                seen.add(art["url"])
                candidates.append(art)
            if len(candidates) >= candidate_cap:
                break

        # 2) fetch detail pages and filter by keywords
        results: list[dict[str, Any]] = []
        for art in candidates[:candidate_cap]:
            if len(results) >= max_items:
                break
            detail_html = http_get(self.session, art["url"], TIMEOUT)
            time.sleep(REQUEST_INTERVAL)
            if not detail_html:
                continue

            dsoup = BeautifulSoup(detail_html, "html.parser")
            h1 = dsoup.select_one("h1")
            title = (h1.get_text(strip=True) if h1 else art["title"]).strip()
            if not title:
                continue

            content = extract_article_text(dsoup, use_paragraphs=False)
            if not content:
                continue

            # Keyword filter
            text = title + " " + content[:800]
            if use_region:
                if not matches_region_topic(text, region_kw or [], topic_kw or []):
                    continue
            else:
                if not matches_keywords(text, effective_kw):
                    continue

            results.append(
                {
                    "title": title,
                    "content": content,
                    "source": self.source_name,
                    "url": art["url"],
                    "publish_time": extract_publish_time(dsoup, art["url"]),
                }
            )

        return results
