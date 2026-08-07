from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.collectors.common import DEFAULT_UA, extract_article_text, parse_rss


class ForeignRSSCollector(BaseCollector):
    """RSS-only collector for the isolated foreign opinion pipeline."""

    source_name = "Foreign RSS"

    def __init__(
        self,
        feeds: list[str] | None = None,
        keywords: list[str] | str | None = None,
        is_foreign: bool = False,
        proxy_env: str | None = None,
        timeout: int = 15,
        max_items: int = 100,
        max_content_length: int = 200_000,
        request_interval: float = 0.5,
        max_retries: int = 2,
        fetch_full_text: bool = False,
        source_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.feeds = [str(feed).strip() for feed in (feeds or []) if str(feed).strip()]
        if isinstance(keywords, str):
            keywords = keywords.split(",")
        self.keywords = [str(word).strip() for word in (keywords or []) if str(word).strip()]
        self.proxy_env = proxy_env or "FOREIGN_HTTP_PROXY"
        self.timeout = max(1, int(timeout))
        self.max_items = max(1, int(max_items))
        self.max_content_length = max(1, int(max_content_length))
        self.request_interval = max(0.0, float(request_interval))
        self.max_retries = max(0, int(max_retries))
        self.fetch_full_text = bool(fetch_full_text)
        self.is_foreign = bool(is_foreign)
        if source_name:
            self.source_name = str(source_name)
        self.last_fetched_raw = 0
        self.last_error: str | None = None

    def _proxies(self) -> dict[str, str] | None:
        value = os.getenv(self.proxy_env, "").strip()
        return {"http": value, "https": value} if value else None

    def _get(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(
                    url,
                    headers={"User-Agent": DEFAULT_UA},
                    timeout=(self.timeout, self.timeout),
                    proxies=self._proxies(),
                )
                response.raise_for_status()
                response.encoding = response.encoding or response.apparent_encoding or "utf-8"
                return response.text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 5))
        raise RuntimeError(str(last_error) if last_error else "request failed")

    def _fetch_full_text(self, url: str) -> str:
        if not self.fetch_full_text or not url:
            return ""
        try:
            html = self._get(url)
            return extract_article_text(
                BeautifulSoup(html, "html.parser"),
                fallback_chars=self.max_content_length,
            )[: self.max_content_length]
        except Exception:
            # RSS items remain usable when optional public-body retrieval fails.
            return ""

    def fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        # CollectorService's domestic keyword arguments are deliberately ignored.
        if not self.is_foreign or not self.keywords or not self.feeds:
            return []

        items: list[dict[str, Any]] = []
        self.last_fetched_raw = 0
        self.last_error = None
        for feed_url in self.feeds:
            try:
                parsed = parse_rss(self._get(feed_url))
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                continue
            for item in parsed:
                title = str(item.get("title") or "").strip()
                summary = str(item.get("content") or "").strip()
                url = str(item.get("url") or "").strip()
                content = (
                    self._fetch_full_text(url) or summary
                )[: self.max_content_length]
                merged = f"{title}\n{summary}\n{content}".lower()
                matched = [
                    word for word in self.keywords if word.lower() in merged
                ]
                if not matched:
                    continue
                items.append(
                    {
                        "title": title,
                        "summary": summary[: self.max_content_length],
                        "content": content,
                        "url": url,
                        "source": self.source_name,
                        "publish_time": item.get("publish_time"),
                        "matched_keywords": list(dict.fromkeys(matched)),
                    }
                )
                if len(items) >= self.max_items:
                    break
            self.last_fetched_raw += len(parsed)
            if len(items) >= self.max_items:
                break
            if self.request_interval:
                time.sleep(self.request_interval)
        return items[: self.max_items]


class FoxNewsForeignCollector(ForeignRSSCollector):
    source_name = "Fox News"


class GuardianForeignCollector(ForeignRSSCollector):
    source_name = "The Guardian"


class NYTimesChineseForeignCollector(ForeignRSSCollector):
    source_name = "纽约时报中文网"
