"""河北日报采集器（Phase 2）。

数据源：河北日报数字报（方正电子报）https://hbrb.hebnews.cn/
结构为两级：版面索引(layout → node_XX.html) → 文章(pc/paper/c/.../content_XXX.html)。

经实测：
- 索引页列出各版面（第01版 头版 / 第02版 要闻 ...），链接形如 202607/21/node_01.html
- 版面页列出文章，链接形如 ../../c/202607/21/content_304725.html
- 文章详情页正文容器为 div.content（实测命中 1000+ 字真实正文）

复用 common 的 http_get / extract_links / extract_article_text / matches_keywords，
仅此处特有的「两级导航」为采集器自有逻辑（无法与单级列表站点共用，故不强行抽象）。
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
    http_get,
    make_session,
    matches_keywords,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

LAYOUT_URL = "https://hbrb.hebnews.cn/pc/paper/layout/index.html"
CONTENT_SELECTORS = ["div.content", "div.article", "article"]
MAX_SECTIONS = 4          # 仅取前 4 个版面（头版/要闻为主）
MAX_PER_SECTION = 5       # 每版面最多 5 篇
TOTAL_CAP = 12            # 全源上限，控制抓取量
REQUEST_INTERVAL = 0.3
TIMEOUT = 15


class HebeiDailyCollector(BaseCollector):
    """河北日报（数字报）采集器。"""

    source_name = "河北日报"

    def __init__(self, keywords: str | None = None) -> None:
        self.session = make_session(DEFAULT_UA)
        kw = keywords if keywords is not None else settings.collector_keywords
        self.keywords: list[str] = [k.strip() for k in kw.split(",") if k.strip()]

    def fetch(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        layout = http_get(self.session, LAYOUT_URL, TIMEOUT)
        if not layout:
            return results
        lsoup = BeautifulSoup(layout, "html.parser")
        sections = extract_links(
            lsoup,
            LAYOUT_URL,
            href_contains="node_",
            href_exclude=["index.html"],
            max_links=MAX_SECTIONS,
        )

        for sec in sections:
            if len(results) >= TOTAL_CAP:
                break
            shtml = http_get(self.session, sec["url"], TIMEOUT)
            time.sleep(REQUEST_INTERVAL)
            if not shtml:
                continue
            ssoup = BeautifulSoup(shtml, "html.parser")
            arts = extract_links(
                ssoup, sec["url"], href_contains="content_", max_links=MAX_PER_SECTION
            )
            for art in arts:
                if len(results) >= TOTAL_CAP:
                    break
                dhtml = http_get(self.session, art["url"], TIMEOUT)
                time.sleep(REQUEST_INTERVAL)
                if not dhtml:
                    continue
                dsoup = BeautifulSoup(dhtml, "html.parser")
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
                        "publish_time": None,
                    }
                )
        return results
