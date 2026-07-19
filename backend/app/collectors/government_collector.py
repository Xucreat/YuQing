"""政府网站采集器（Phase 3B）。

数据源：河北廊坊大厂回族自治县人民政府网站（https://www.lfdc.gov.cn/）。
栏目：
  - 今日大厂  /jrdc.jhtml   每日政务动态
  - 公告公示  /gggs.jhtml   政府正式公告、通知

数据流：栏目页采集 → HTML 解析（列表 + 详情正文）→ 标准化 dict → 交给
CollectorService 入库 + AI 分析。Collector 本身不写库（沿用 BaseCollector 约束）。

设计约束（来自用户确认）：
- 继承既有 BaseCollector（source_name = "大厂县政府网站"）。
- 使用 requests（timeout=10）+ 桌面 User-Agent；统一
  response.encoding = response.apparent_encoding 防中文乱码。
- 防御式抓取：网络失败 / HTTP 错误码 / 超时 → 不崩溃，记录日志并返回 []
  （详情页失败则跳过该条），保证整体流程不中断。
- 单次最多抓取 MAX_ARTICLES = 20 篇；详情页请求间隔 time.sleep(0.3) (>=300ms)；
  不递归全站、不抓附件、不实现反爬绕过。
- 正文解析按优先级降级，避免整个 <body> 原文入库（减少噪声）。

禁止（本阶段）：Scrapy / Playwright / Selenium / 多线程爬虫 / 定时任务。
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from app.collectors.base import BaseCollector
from app.core.config import settings

logger = logging.getLogger(__name__)

# 站点根，用于相对路径 → 绝对路径。
BASE_URL = "https://www.lfdc.gov.cn"

# 桌面浏览器 User-Agent（避免被简单 UA 过滤拦截；不做任何反爬绕过）。
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 单次采集保护上限（避免一次采集压力过大 / 递归全站）。
MAX_ARTICLES = 20
# 详情页请求间隔（>=300ms，避免连续请求政府网站）。
REQUEST_INTERVAL = 0.3
# 单次请求超时（秒）。
TIMEOUT = 10

# 详情页正文候选容器（按优先级降级）。
_CONTENT_SELECTORS = [
    "div.content",
    "div.article-content",
    "div.text",
    "div.TRS_Editor",
    "div#Zoom",
    "div.article_con",
    "article",
]

# body 纯文本兜底截断长度。
_BODY_FALLBACK_CHARS = 500

# JEECMS 文章详情 URL 形如 /{栏目}/{数字id}.jhtml（如 /xnyw/34542.jhtml）；
# 而导航/栏目页为单段（如 /jrdc.jhtml、/ywwh.jhtml）。用数字 id 过滤掉导航链接，
# 仅保留真实文章（仍基于 a[href*='.jhtml'] 选择器，只是剔除非文章噪声）。
_ARTICLE_PATH_RE = re.compile(r"/\d+\.jhtml$")


class GovernmentCollector(BaseCollector):
    """大厂县政府网站采集器（JEECMS / .jhtml 栏目结构）。"""

    source_name = "大厂县政府网站"

    def __init__(self, urls: list[str] | None = None) -> None:
        # 栏目地址来自 Pydantic Settings（settings.gov_news_urls），可注入覆盖（测试）。
        self.urls: list[str] = list(urls) if urls else list(settings.gov_news_urls)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": DEFAULT_UA})

    # ------------------------------------------------------------------
    # HTTP：防御式抓取
    # ------------------------------------------------------------------
    def _get(self, url: str) -> str | None:
        """GET 单个 URL，返回解码后的 HTML 文本；任何异常返回 None（不崩溃）。"""
        try:
            resp = self.session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            # 统一按 apparent_encoding 解码，确保中文不乱码。
            resp.encoding = resp.apparent_encoding
            return resp.text
        except requests.RequestException as exc:  # 网络失败 / 超时 / HTTP 错误码
            logger.warning("政府网站抓取失败 url=%s err=%s", url, exc)
            return None
        except Exception as exc:  # noqa: BLE001  防御：不因单个 URL 崩掉整体
            logger.warning("政府网站抓取异常 url=%s err=%s", url, exc)
            return None

    # ------------------------------------------------------------------
    # 解析：栏目页 → 文章链接
    # ------------------------------------------------------------------
    def _parse_list(self, html: str) -> list[dict[str, str]]:
        """从栏目页提取文章链接（title + 绝对 url）。"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        seen: set[str] = set()
        articles: list[dict[str, str]] = []
        for a in soup.select("a[href*='.jhtml']"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            abs_url = urljoin(BASE_URL, href)
            # 仅保留文章详情（/{栏目}/{数字id}.jhtml），剔除导航/栏目页噪声。
            if not _ARTICLE_PATH_RE.search(urlparse(abs_url).path):
                continue
            if abs_url in seen:
                continue
            # 标题：优先 title 属性，否则取标签文本。
            title = (a.get("title") or "").strip() or a.get_text(strip=True)
            if not title:
                continue
            seen.add(abs_url)
            articles.append({"title": title, "url": abs_url})
        return articles

    # ------------------------------------------------------------------
    # 解析：详情页 → 正文
    # ------------------------------------------------------------------
    def _parse_detail(self, html: str) -> str:
        """按优先级降级提取正文，避免整个 <body> 原文入库。"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # 1) 常见正文容器（含政务网站常见 #Zoom / article_con）。
        for selector in _CONTENT_SELECTORS:
            node = soup.select_one(selector)
            if node:
                text = node.get_text(separator="\n", strip=True)
                if text:
                    return text

        # 2) body 内所有 <p> 拼接。
        body = soup.body or soup
        paragraphs = [
            p.get_text(strip=True)
            for p in body.find_all("p")
            if p.get_text(strip=True)
        ]
        if paragraphs:
            return "\n".join(paragraphs)

        # 3) 最终兜底：body 纯文本前 N 字符。
        body_text = body.get_text(separator="\n", strip=True)
        return body_text[:_BODY_FALLBACK_CHARS]

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def fetch(self) -> list[dict[str, Any]]:
        """采集栏目页文章 → 抓详情正文 → 返回标准化 dict 列表。

        - 单次最多 MAX_ARTICLES 篇；详情页请求间隔 REQUEST_INTERVAL。
        - 任何网络异常均隔离：整站不可用返回 []，单篇失败跳过。
        """
        if not self.urls:
            return []

        # 1) 收集各栏目页文章链接（跨栏目按 url 去重）。
        candidates: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        for column_url in self.urls:
            html = self._get(column_url)
            if not html:
                continue
            for art in self._parse_list(html):
                if art["url"] in seen_urls:
                    continue
                seen_urls.add(art["url"])
                candidates.append(art)

        # 2) 抓取详情正文（限流 + 上限）。
        results: list[dict[str, Any]] = []
        for art in candidates[:MAX_ARTICLES]:
            detail_html = self._get(art["url"])
            # 请求间隔：避免连续请求政府网站（放在每次详情请求之后）。
            time.sleep(REQUEST_INTERVAL)
            if not detail_html:
                continue  # 详情失败：跳过该条，保证入库正文非空
            content = self._parse_detail(detail_html)
            if not content:
                continue
            results.append(
                {
                    "title": art["title"],
                    "url": art["url"],
                    "content": content,
                    "source": self.source_name,
                    # 政府站发布时间解析脆弱，MVP 统一 None；去重以 url 为准。
                    "publish_time": None,
                }
            )
        return results
