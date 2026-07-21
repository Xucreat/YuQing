"""新华网采集器（Phase 2）。

数据源：新华网 https://www.xinhuanet.com/（国家级新闻门户）。
复用 common 中的 http_get / extract_links / extract_article_text / matches_keywords，
不重复实现请求与解析逻辑。关键词过滤保证只入库与监测范围相关的舆情。

设计约束（延续既有约定）：
- 防御式抓取：单篇失败跳过，不影响整体。
- 单次最多 MAX_ARTICLES 篇；详情页请求间隔 >=300ms。
- 关键词过滤为空时放行全部。
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

DEFAULT_URLS = ["https://www.xinhuanet.com/"]
# 新华网详情正文容器（经实测 div.main-left 命中真实正文）。
CONTENT_SELECTORS = ["div.main-left", "div.main", "div.content", "article"]
MAX_ARTICLES = 10
REQUEST_INTERVAL = 0.3
TIMEOUT = 10


class XinhuaCollector(BaseCollector):
    """新华网采集器。"""

    source_name = "新华网"

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
                href_exclude=["index.html", "download.html", "/board/", "javascript"],
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
