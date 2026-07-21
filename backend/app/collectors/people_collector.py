"""人民网采集器（Phase 2）。

数据源：人民网 https://www.people.com.cn/（国家级新闻门户）。
复用 common 公共函数；文章链接以 /c数字-数字.html 结尾为强特征过滤噪声。
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

DEFAULT_URLS = ["https://www.people.com.cn/"]
# 人民网详情正文容器（经实测 div.rm_txt_con 命中真实正文）。
CONTENT_SELECTORS = ["div.rm_txt_con", "div.rm_txt", "div.content", "article"]
# 人民网文章 URL 形如 /n1/2026/0721/c1004-40764523.html
HREF_RE = re.compile(r"c\d+-\d+\.html$")
MAX_ARTICLES = 10
REQUEST_INTERVAL = 0.3
TIMEOUT = 10


class PeopleCollector(BaseCollector):
    """人民网采集器。"""

    source_name = "人民网"

    def __init__(self, urls: list[str] | None = None, keywords: str | None = None) -> None:
        self.urls: list[str] = list(urls) if urls else list(DEFAULT_URLS)
        self.session = make_session(DEFAULT_UA)
        kw = keywords if keywords is not None else settings.collector_keywords
        self.keywords: list[str] = [k.strip() for k in kw.split(",") if k.strip()]

    def fetch(self) -> list[dict[str, Any]]:
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
                href_exclude=["index.html", "download.html"],
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
                if not matches_keywords(title + " " + content[:800], self.keywords):
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
