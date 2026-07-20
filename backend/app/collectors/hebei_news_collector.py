"""Hebei local news collector (P1): web scraping from hebnews.cn.

RSS feeds at hebnews.cn / lfnews.cn are no longer available (301/HTML, 502).
Now scrapes the actual news listing pages and article detail pages,
following the same defensive-scraping pattern as GovernmentCollector.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.core.config import settings

logger = logging.getLogger(__name__)

# News listing pages: these are live and scrapeable.
DEFAULT_URLS = [
    "https://lf.hebnews.cn/",      # Langfang channel (nearest to Dachang)
    "https://hebei.hebnews.cn/",   # Hebei province channel
]

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_CONTENT_SELECTORS = [
    "div.content",
    "div.article-content",
    "div.text",
    "div.TRS_Editor",
    "div#Zoom",
    "div.article_con",
    "article",
]

_BODY_FALLBACK_CHARS = 500
REQUEST_INTERVAL = 0.3


class HebeiNewsCollector(BaseCollector):
    """Scrape hebnews.cn listing pages for keyword-filtered articles."""

    source_name = "河北新闻网"

    def __init__(self, urls: list[str] | None = None):
        feed_val = getattr(settings, "hebei_news_feeds", "")
        if feed_val and isinstance(feed_val, str) and feed_val.strip():
            self.urls = [u.strip() for u in feed_val.split(",") if u.strip()]
        elif urls:
            self.urls = list(urls)
        else:
            self.urls = list(DEFAULT_URLS)

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA})
        kw = settings.collector_keywords
        self.keywords = [k.strip() for k in kw.split(",") if k.strip()]

    def _get(self, url: str) -> str | None:
        """Fetch a single URL, return decoded HTML or None."""
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except Exception as exc:
            logger.warning("hebei fetch failed url=%s err=%s", url, exc)
            return None

    def _parse_content(self, html: str) -> str:
        """Extract article body by priority."""
        soup = BeautifulSoup(html, "html.parser")
        for selector in _CONTENT_SELECTORS:
            node = soup.select_one(selector)
            if node:
                text = node.get_text(separator="\n", strip=True)
                if text:
                    return text
        body = soup.body or soup
        return body.get_text(separator="\n", strip=True)[:_BODY_FALLBACK_CHARS]

    def fetch(self) -> list[dict[str, Any]]:
        if not self.urls or not self.keywords:
            return []

        # 1) collect article links from listing pages
        candidates: list[dict[str, str]] = []
        seen: set[str] = set()

        for list_url in self.urls:
            html = self._get(list_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href*='content_']"):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                abs_url = urljoin(list_url, href)
                if abs_url in seen:
                    continue
                title = (a.get("title") or "").strip() or a.get_text(strip=True)
                if not title:
                    continue
                seen.add(abs_url)
                candidates.append({"title": title, "url": abs_url})
            if len(candidates) >= 20:
                break

        # 2) fetch detail pages and filter by keywords
        results: list[dict[str, Any]] = []
        for art in candidates[:20]:
            if len(results) >= 10:
                break
            detail_html = self._get(art["url"])
            time.sleep(REQUEST_INTERVAL)
            if not detail_html:
                continue

            soup = BeautifulSoup(detail_html, "html.parser")
            h1 = soup.select_one("h1")
            title = (h1.get_text(strip=True) if h1 else art["title"]).strip()
            if not title:
                continue

            content = self._parse_content(detail_html)
            if not content:
                continue

            # Keyword filter
            text = title + " " + content[:800]
            if not any(kw in text for kw in self.keywords):
                continue

            results.append({
                "title": title,
                "content": content,
                "source": self.source_name,
                "url": art["url"],
                "publish_time": None,
            })

        return results
