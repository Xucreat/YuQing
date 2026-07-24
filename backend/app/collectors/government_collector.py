"""政府网站采集器（Phase 3B，Phase 2 复用 common 公共函数）。

数据源：河北廊坊大厂回族自治县人民政府网站（https://www.lfdc.gov.cn/）。
栏目 → HTML 解析（列表 + 详情正文）→ 标准化 dict → 交给 CollectorService 入库 + AI 分析。
Collector 本身不写库（沿用 BaseCollector 约束）。

Phase 2 改动：将原有的 _get / _parse_detail 逻辑下沉到 common.http_get /
common.extract_article_text，本文件仅保留「站点特有」的列表过滤（.jhtml + 数字 id 正则），
不再复制通用请求与解析实现。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

from app.collectors.base import BaseCollector
from app.collectors.common import (
    DEFAULT_UA,
    extract_article_text,
    extract_links,
    extract_publish_time,
    http_get,
    make_session,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# 站点根，用于相对路径 → 绝对路径。
BASE_URL = "https://www.lfdc.gov.cn"

# 单次采集保护上限（避免一次采集压力过大 / 递归全站）。
MAX_ARTICLES = 20
# 详情页请求间隔（>=300ms，避免连续请求政府网站）。
REQUEST_INTERVAL = 0.3
# 单次请求超时（秒）。
TIMEOUT = 10

# JEECMS 文章详情 URL 形如 /{栏目}/{数字id}.jhtml；用数字 id 过滤掉导航链接，
# 仅保留真实文章（仍基于 a[href*='.jhtml'] 选择器，只是剔除非文章噪声）。
_ARTICLE_PATH_RE = re.compile(r"/\d+\.jhtml$")


class GovernmentCollector(BaseCollector):
    """大厂县政府网站采集器（JEECMS / .jhtml 栏目结构）。"""

    source_name = "大厂县政府网站"

    def __init__(self, urls: list[str] | None = None) -> None:
        # 栏目地址来自 Pydantic Settings（settings.gov_news_urls），可注入覆盖（测试）。
        self.urls: list[str] = list(urls) if urls else list(settings.gov_news_urls)
        self.session = make_session(DEFAULT_UA)

    def _parse_list(self, html: str, base_url: str) -> list[dict[str, str]]:
        """从栏目页提取文章链接（title + 绝对 url），仅保留真实文章详情。"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        return extract_links(
            soup,
            base_url,
            href_contains=".jhtml",
            href_regex=_ARTICLE_PATH_RE,
        )

    def fetch(self, keywords=None) -> list[dict[str, Any]]:
        """采集栏目页文章 → 抓详情正文 → 返回标准化 dict 列表。

        - 单次最多 MAX_ARTICLES 篇；详情页请求间隔 REQUEST_INTERVAL。
        - 任何网络异常均隔离：整站不可用返回 []，单篇失败跳过。
        """
        if not self.urls:
            return []

        candidates: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for column_url in self.urls:
            html = http_get(self.session, column_url, TIMEOUT)
            if not html:
                continue
            for art in self._parse_list(html, BASE_URL):
                if art["url"] in seen_urls:
                    continue
                seen_urls.add(art["url"])
                candidates.append(art)

        results: list[dict[str, Any]] = []
        for art in candidates[:MAX_ARTICLES]:
            detail_html = http_get(self.session, art["url"], TIMEOUT)
            # 请求间隔：避免连续请求政府网站（放在每次详情请求之后）。
            time.sleep(REQUEST_INTERVAL)
            if not detail_html:
                continue  # 详情失败：跳过该条，保证入库正文非空
            from bs4 import BeautifulSoup

            dsoup = BeautifulSoup(detail_html, "html.parser")
            content = extract_article_text(dsoup, use_paragraphs=True)
            if not content:
                continue
            results.append(
                {
                    "title": art["title"],
                    "url": art["url"],
                    "content": content,
                    "source": self.source_name,
                    "publish_time": extract_publish_time(dsoup, art["url"]),
                }
            )
        return results
