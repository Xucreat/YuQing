"""Baidu News search collector (P0).

Searches Baidu News by keywords and extracts article titles, snippets, and URLs.
Uses HTTP + BeautifulSoup to parse search results from news.baidu.com.

Design constraints:
- Keyword-driven search (not site-scraping).
- Single request per keyword batch, with 0.5s interval between batches.
- Max 15 articles per run to stay low-profile.
- No pagination recursion, no anti-crawl bypass.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import quote, urljoin

import requests

from app.collectors.base import BaseCollector
from app.collectors.common import extract_publish_time, parse_publish_date_from_url
from app.collectors.source_config import apply_keyword_scope
from app.core.config import settings

logger = logging.getLogger(__name__)

BAIDU_NEWS_BASE = "https://www.baidu.com"
BAIDU_NEWS_SEARCH = "/s"
MAX_ARTICLES = 15
REQUEST_INTERVAL = 0.5
TIMEOUT = 10
# 默认过滤模式：百度新闻 = 地域雷达（改造前硬编码为「仅用地域词搜索」，即 region_only）。
# 可由 config_json.filter_mode 覆盖（Phase DataSource-Filter-Config-2）；
# 空配置时严格等同改造前行为，保证生产采集量零变化。
DEFAULT_FILTER_MODE = "region_only"
# 默认关键词范围：地域（与 region_only 语义一致）。
DEFAULT_KEYWORD_SCOPE = "region"

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_TITLE_CLEAN_RE = re.compile(r"[【】\[\]]")


class BaiduNewsCollector(BaseCollector):
    source_name = "百度新闻"

    def __init__(self, keywords: str | None = None) -> None:
        kw = keywords if keywords is not None else settings.collector_keywords
        self.keywords: list[str] = [k.strip() for k in kw.split(",") if k.strip()]

    def fetch(self, keywords=None, region_kw=None, topic_kw=None) -> list[dict[str, Any]]:
        # 采集参数改为「配置优先、代码默认兜底」（Phase DataSource-Config-1）；
        # max_items 默认 MAX_ARTICLES，config_json 未配置时与改造前完全一致。
        cfg = self.source_config
        max_items = cfg.max_items(MAX_ARTICLES)
        # 过滤策略完全配置化（Phase DataSource-Filter-Config-2）：
        # 读取 filter_mode / keyword_scope，缺省回退 DEFAULT_FILTER_MODE / DEFAULT_KEYWORD_SCOPE，
        # 与改造前「仅地域词搜索」行为完全一致。
        filter_mode = cfg.filter_mode(DEFAULT_FILTER_MODE)
        region_kw, topic_kw = apply_keyword_scope(cfg.keyword_scope(), region_kw, topic_kw)

        # 按 filter_mode 选择搜索关键词集（数据获取机制不变：仍是向百度新闻按关键词检索）。
        if filter_mode == "topic_only":
            selected = list(topic_kw or [])
        elif filter_mode == "region_or_topic":
            selected = list(region_kw or []) + list(topic_kw or [])
        else:  # region_only（默认）
            selected = list(region_kw or [])

        # 去重保序，剔除空串
        seen_kw: set[str] = set()
        search_kws: list[str] = []
        for k in selected:
            if k and k not in seen_kw:
                seen_kw.add(k)
                search_kws.append(k)

        if not search_kws:
            # 配置异常：所选关键词集为空 → fail-safe 跳过搜索，
            # 避免产出无地域 / 无主题数据（与改造前 region_kw 为空时的保护一致）。
            logger.error(
                "baidu_news: filter_mode=%s 下关键词集为空（配置异常），跳过搜索", filter_mode
            )
            return []

        results: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_UA})

        for kw in search_kws:
            if len(results) >= max_items:
                break
            params = {
                "wd": kw,
                "tn": "news",
                "ie": "utf-8",
                "rtt": "1",  # recent
            }
            try:
                resp = session.get(
                    urljoin(BAIDU_NEWS_BASE, BAIDU_NEWS_SEARCH),
                    params=params,
                    timeout=TIMEOUT,
                )
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding
            except Exception as exc:
                logger.warning("Baidu search failed for kw=%s err=%s", kw, exc)
                continue

            time.sleep(REQUEST_INTERVAL)

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            for item in soup.select("div.result, div.result-op"):
                if len(results) >= max_items:
                    break
                a_tag = item.select_one("h3 a")
                if not a_tag:
                    continue
                title = _TITLE_CLEAN_RE.sub("", a_tag.get_text(strip=True))
                href = a_tag.get("href", "").strip()
                if not title or not href:
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                snippet_el = item.select_one("div.c-summary, span.c-summary, div.c-abstract")
                content = snippet_el.get_text(strip=True) if snippet_el else title

                results.append({
                    "title": title,
                    "content": content,
                    "source": self.source_name,
                    "url": href,
                    # 搜索结果片段通常无可靠日期；extract_publish_time 先查片段文本，
                    # 再以 URL 兜底（百度落地页 URL 无日期时返回 None，属正常）。
                    "publish_time": extract_publish_time(item, href)
                    or parse_publish_date_from_url(href),
                })

        session.close()
        return results
