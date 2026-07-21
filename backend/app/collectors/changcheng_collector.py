"""长城网采集器（Phase 2）。

数据源：长城网（河北新闻网站）https://www.hebei.com.cn/
文章链接为 .shtml（站点/协议相对，如 //news.hebccw.cn/system/2026/07/21/...shtml），
详情正文容器经实测为 div.detailMessage。
复用 common 公共函数；_join 已处理协议相对 URL（// → https:）。
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
)
from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_URLS = ["https://www.hebei.com.cn/"]
CONTENT_SELECTORS = ["div.detailMessage", "div.content", "div.text", "article"]
MAX_ARTICLES = 10
REQUEST_INTERVAL = 0.3
TIMEOUT = 10


class ChangchengCollector(BaseCollector):
    """长城网采集器。"""

    source_name = "长城网"

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
                soup, list_url, href_contains=".shtml", max_links=40
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
