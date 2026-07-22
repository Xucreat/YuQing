"""Weibo search collector - Playwright edition (P1).
Replaces the HTTP-based approach that returns 432 errors
with a Playwright-based browser automation crawler.
"""
from __future__ import annotations
import logging
from typing import Any
from app.collectors.base import BaseCollector
from app.collectors.weibo.crawler import WeiboCrawler
from app.core.config import settings

logger = logging.getLogger(__name__)
MAX_POSTS = 10


class WeiboCollector(BaseCollector):
    source_name = "微博"

    def __init__(self, keywords=None, headless=True):
        kw = keywords if keywords is not None else settings.collector_keywords
        self.keywords = [k.strip() for k in kw.split(",") if k.strip()]
        self._crawler = WeiboCrawler(headless=headless, cookie_str=settings.weibo_cookie)

    def fetch(self, keywords=None):
        if not self.keywords:
            return []
        results = []
        for kw in self.keywords[:3]:
            if len(results) >= MAX_POSTS:
                break
            try:
                posts = self._crawler.search(kw, max_count=MAX_POSTS)
                for p in posts:
                    p["source"] = self.source_name
                    p["publish_time"] = None
                results.extend(posts)
            except Exception as e:
                logger.warning("WeiboCollector kw=%s err=%s", kw, e)
        return results[:MAX_POSTS]

    def close(self):
        self._crawler.close()
