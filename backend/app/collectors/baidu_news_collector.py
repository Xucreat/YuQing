"""Baidu News search collector (P0).

Searches Baidu News by keywords and extracts article titles, snippets, and URLs.
Uses HTTP + BeautifulSoup to parse search results from news.baidu.com.

Design constraints:
- Keyword-driven search (not site-scraping).
- Single request per keyword batch, with 0.5s interval between batches.
- Max 15 articles per run to stay low-profile.
- No pagination recursion, no anti-crawl bypass.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import quote, urljoin

import requests

from app.collectors.base import BaseCollector
from app.collectors.common import extract_publish_time
from app.core.config import settings

logger = logging.getLogger(__name__)

BAIDU_NEWS_BASE = "https://www.baidu.com"
BAIDU_NEWS_SEARCH = "/s"
MAX_ARTICLES = 15
REQUEST_INTERVAL = 0.5
TIMEOUT = 10

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_TITLE_CLEAN_RE = re.compile(r"[【】\[\]]")


class BaiduNewsCollector(BaseCollector):
    source_name = "百度新闻"

    def __init__(self, keywords: str | None = None) -> None:
        kw = keywords if keywords is not None else settings.collector_keywords
        self.keywords: list[str] = [k.strip() for k in kw.split(",") if k.strip()]

    def fetch(self) -> list[dict[str, Any]]:
        if not self.keywords:
            return []

        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_UA})

        for kw in self.keywords:
            if len(results) >= MAX_ARTICLES:
                break
            params = {
                "wd": kw,
                "tn": "news",
                "ie": "utf-8",
                "rtt": "1",  # recent
            }
            try:
                resp = session.get(
                    urljoin(BAIDU_NEWS_BASE, BAIDU_NEWS_SEARCH),
                    params=params,
                    timeout=TIMEOUT,
                )
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding
            except Exception as exc:
                logger.warning("Baidu search failed for kw=%s err=%s", kw, exc)
                continue

            time.sleep(REQUEST_INTERVAL)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("div.result, div.result-op"):
                if len(results) >= MAX_ARTICLES:
                    break
                a_tag = item.select_one("h3 a")
                if not a_tag:
                    continue
                title = _TITLE_CLEAN_RE.sub("", a_tag.get_text(strip=True))
                href = a_tag.get("href", "").strip()
                if not title or not href:
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                snippet_el = item.select_one("div.c-summary, span.c-summary, div.c-abstract")
                content = snippet_el.get_text(strip=True) if snippet_el else title

                results.append({
                    "title": title,
                    "content": content,
                    "source": self.source_name,
                    "url": href,
                    "publish_time": extract_publish_time(item),
                })

        session.close()
        return results
