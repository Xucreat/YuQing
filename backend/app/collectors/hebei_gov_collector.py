"""河北省人民政府采集器（Phase 2）。

数据源：河北省人民政府门户网站「要闻」栏目
https://www.hebei.gov.cn/columns/580d0301-2e0b-4152-9dd1-7d7f4e0f4980/index.html
文章链接形如 /columns/580d0301-.../202607/21/{guid}.html（与国家级政府站同源 CMS，
正文容器经实测为 div.content）。
复用 common 公共函数。
"""
from __future__ import annotations

import logging
import re
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
)
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_URLS = [
    "https://www.hebei.gov.cn/columns/580d0301-2e0b-4152-9dd1-7d7f4e0f4980/index.html"
]
CONTENT_SELECTORS = ["div.content", "div.article", "div#Zoom", "div.article_con", "article"]
HREF_RE = re.compile(r"/columns/580d0301")
MAX_ARTICLES = 10
REQUEST_INTERVAL = 0.3
TIMEOUT = 10


class HebeiGovCollector(BaseCollector):
    """河北省人民政府采集器。"""

    source_name = "河北省人民政府"

    def __init__(self, urls: list[str] | None = None, keywords: str | None = None) -> None:
        self.urls: list[str] = list(urls) if urls else list(DEFAULT_URLS)
        self.session = make_session(DEFAULT_UA)
        kw = keywords if keywords is not None else settings.collector_keywords
        self.keywords: list[str] = [k.strip() for k in kw.split(",") if k.strip()]

    def fetch(self, keywords=None) -> list[dict[str, Any]]:
        effective_kw = keywords if keywords is not None else self.keywords
        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        for list_url in self.urls:
            html = http_get(self.session, list_url, TIMEOUT)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            links = extract_links(
                soup,
                list_url,
                href_contains=".html",
                href_regex=HREF_RE,
                href_exclude=["index.html"],
                max_links=40,
            )
            for art in links:
                if art["url"] in seen:
                    continue
                seen.add(art["url"])
                if len(results) >= MAX_ARTICLES:
                    break
                detail = http_get(self.session, art["url"], TIMEOUT)
                time.sleep(REQUEST_INTERVAL)
                if not detail:
                    continue
                dsoup = BeautifulSoup(detail, "html.parser")
                h1 = dsoup.select_one("h1")
                title = (h1.get_text(strip=True) if h1 else art["title"]) or art["title"]
                content = extract_article_text(dsoup, CONTENT_SELECTORS, use_paragraphs=False)
                if not content:
                    continue
                if not matches_keywords(title + " " + content[:800], effective_kw):
                    continue
                results.append(
                    {
                        "title": title,
                        "content": content,
                        "source": self.source_name,
                        "url": art["url"],
                        "publish_time": extract_publish_time(dsoup),
                    }
                )
        return results
