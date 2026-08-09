from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.collectors.common import DEFAULT_UA, extract_article_text, parse_rss
from app.services.foreign_content_sanitizer import sanitize_foreign_html


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
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        max_items: int = 100,
        max_content_length: int = 200_000,
        request_interval: float = 0.5,
        max_retries: int = 2,
        fetch_full_text: bool = False,
        respect_robots: bool = True,
        source_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.feeds = [str(feed).strip() for feed in (feeds or []) if str(feed).strip()]
        if isinstance(keywords, str):
            keywords = keywords.split(",")
        self.keywords = [str(word).strip() for word in (keywords or []) if str(word).strip()]
        self.proxy_env = proxy_env or "FOREIGN_HTTP_PROXY"
        self.timeout = max(1, int(timeout))
        self.connect_timeout = max(
            0.1, float(connect_timeout if connect_timeout is not None else self.timeout)
        )
        self.read_timeout = max(
            0.1, float(read_timeout if read_timeout is not None else self.timeout)
        )
        self.max_items = max(1, int(max_items))
        self.max_content_length = max(1, int(max_content_length))
        self.request_interval = max(0.0, float(request_interval))
        self.max_retries = max(0, int(max_retries))
        self.fetch_full_text = bool(fetch_full_text)
        self.respect_robots = bool(respect_robots)
        self.is_foreign = bool(is_foreign)
        if source_name:
            self.source_name = str(source_name)
        self.last_fetched_raw = 0
        self.last_error: str | None = None
        self.last_failed_feeds = 0
        self.last_feed_reports: list[dict[str, Any]] = []
        self.last_http_status: int | None = None

    def _proxies(self) -> dict[str, str] | None:
        value = os.getenv(self.proxy_env, "").strip()
        return {"http": value, "https": value} if value else None

    def _get(self, url: str) -> str:
        return self._get_response(url).text

    def _get_response(self, url: str) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.get(
                    url,
                    headers={"User-Agent": DEFAULT_UA},
                    timeout=(self.connect_timeout, self.read_timeout),
                    proxies=self._proxies(),
                )
                self.last_http_status = response.status_code
                response.raise_for_status()
                response.encoding = response.encoding or response.apparent_encoding or "utf-8"
                return response
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 5))
        raise RuntimeError(str(last_error) if last_error else "request failed")

    @staticmethod
    def _feed_label(url: str) -> str:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return "invalid-feed"
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"

    def probe(self) -> list[dict[str, Any]]:
        """Probe each RSS feed without fetching article bodies or writing state."""
        self.last_feed_reports = []
        self.last_fetched_raw = 0
        self.last_error = None
        self.last_failed_feeds = 0
        for feed_url in self.feeds:
            self.last_http_status = None
            report: dict[str, Any] = {
                "feed": self._feed_label(feed_url),
                "http_status": None,
                "xml_parsed": False,
                "raw_count": 0,
                "valid_count": 0,
                "title_count": 0,
                "summary_count": 0,
                "published_time_count": 0,
                "url_duplicate_count": 0,
                "languages": {"en": 0, "zh": 0, "mixed": 0, "unknown": 0},
                "matched_count": 0,
                "failure_count": 0,
                "error": None,
            }
            try:
                raw = self._get(feed_url)
                report["http_status"] = self.last_http_status or 200
                parsed = parse_rss(raw)
                report["xml_parsed"] = True
                report["raw_count"] = len(parsed)
                self.last_fetched_raw += len(parsed)
                seen_urls: set[str] = set()
                for item in parsed[: self.max_items]:
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    summary = str(item.get("content") or "").strip()
                    if title:
                        report["title_count"] += 1
                    if summary:
                        report["summary_count"] += 1
                    if item.get("publish_time"):
                        report["published_time_count"] += 1
                    if title and url:
                        report["valid_count"] += 1
                        if url in seen_urls:
                            report["url_duplicate_count"] += 1
                        seen_urls.add(url)
                    sample = f"{title}\n{summary}"
                    has_zh = any("\u4e00" <= char <= "\u9fff" for char in sample)
                    has_en = any(char.isascii() and char.isalpha() for char in sample)
                    language = "mixed" if has_zh and has_en else "zh" if has_zh else "en" if has_en else "unknown"
                    report["languages"][language] += 1
                    text = "\n".join(
                        str(item.get(key) or "")
                        for key in ("title", "content")
                    ).casefold()
                    if any(word.casefold() in text for word in self.keywords):
                        report["matched_count"] += 1
            except Exception as exc:  # noqa: BLE001
                self.last_failed_feeds += 1
                self.last_error = str(exc)
                report["failure_count"] = 1
                report["error"] = "RSS feed request or XML parsing failed"
            self.last_feed_reports.append(report)
        return list(self.last_feed_reports)

    def _robots_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            parser = RobotFileParser()
            parser.parse(self._get(robots_url).splitlines())
            return parser.can_fetch(DEFAULT_UA, url)
        except Exception:
            # Optional full-text retrieval fails closed when robots cannot be read.
            return False

    def _fetch_full_text(self, url: str) -> str:
        if not self.fetch_full_text or not url:
            return ""
        if not self._robots_allowed(url):
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
        self.last_failed_feeds = 0
        for feed_url in self.feeds:
            try:
                parsed = parse_rss(self._get(feed_url))
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc)
                self.last_failed_feeds += 1
                continue
            for item in parsed:
                title = str(item.get("title") or "").strip()
                summary = str(item.get("content") or "").strip()
                url = str(item.get("url") or "").strip()
                summary = sanitize_foreign_html(summary)[: self.max_content_length]
                content = sanitize_foreign_html(self._fetch_full_text(url) or summary)[: self.max_content_length]
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
