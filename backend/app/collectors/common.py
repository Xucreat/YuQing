"""采集器公共函数（Phase 2：提炼局部公共函数，不改动 Collector 继承结构）。

仅提供可复用的「请求 / 解析 / 清洗 / 关键词过滤 / RSS 解析」原子函数，
供各具体 Collector 调用，避免每个网站复制一套相同的实现。

设计约束（延续既有约定）：
  - 防御式抓取：网络失败 / 超时 / HTTP 错误码 → 返回 None，不崩溃。
  - 正文按优先级降级提取，避免整页噪声入库。
  - 关键词过滤为空时放行全部（便于测试与全量采集）。
  - RSS 解析惰性依赖 feedparser（未配置源时不强制加载）。
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 桌面浏览器 UA（避免被简单 UA 过滤拦截；不做任何反爬绕过）。
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 通用正文候选容器（按优先级降级），覆盖政务站与多数新闻门户结构。
DEFAULT_CONTENT_SELECTORS = [
    "div.content",
    "div.article-content",
    "div.text",
    "div.TRS_Editor",
    "div#Zoom",
    "div.article_con",
    "article",
    "div.rm_txt_con",
    "div.detailMessage",
    "div.main-left",
    "div.main",
]

_BODY_FALLBACK_CHARS = 500


def make_session(ua: str = DEFAULT_UA) -> requests.Session:
    """创建带桌面 UA 的 requests.Session。"""
    s = requests.Session()
    s.headers.update({"User-Agent": ua})
    return s


def http_get(
    session: requests.Session, url: str, timeout: int = 10
) -> Optional[str]:
    """GET 单个 URL，返回解码后的 HTML 文本；任何异常返回 None（防御式，不崩溃）。

    统一 resp.encoding = resp.apparent_encoding 防中文乱码（与既有采集器一致）。
    """
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return resp.text
    except Exception as exc:  # noqa: BLE001  防御：单个 URL 失败不影响整体流程
        logger.warning("抓取失败 url=%s err=%s", url, exc)
        return None


def _join(base: str, href: str) -> str:
    """相对/协议相对/绝对 href → 绝对 URL。

    - //host/path（协议相对）→ https://host/path
    - /path（站点相对）→ 基于 base 拼接
    - 绝对 http(s) → 原样
    """
    from urllib.parse import urljoin

    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(base, href)


def extract_links(
    soup: BeautifulSoup,
    base_url: str,
    *,
    href_contains: Optional[str] = None,
    href_regex: Optional[re.Pattern] = None,
    href_exclude: Optional[List[str]] = None,
    title_blacklist: Optional[List[str]] = None,
    max_links: Optional[int] = None,
) -> List[dict]:
    """从列表页提取文章链接（title + 绝对 url），可基于 href 子串 / 正则 / 排除项过滤。

    返回 [{"title": str, "url": str}, ...]，已按 url 去重。
    """
    seen: set = set()
    out: List[dict] = []
    black = title_blacklist or []
    exclude = href_exclude or []

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href == "#" or href.startswith("javascript"):
            continue
        if href_contains and href_contains not in href:
            continue
        if href_regex and not href_regex.search(href):
            continue
        if any(ex in href for ex in exclude):
            continue
        abs_url = _join(base_url, href)
        if abs_url in seen:
            continue
        title = (a.get("title") or a.get_text(strip=True) or "").strip()
        if not title:
            continue
        if any(b in title for b in black):
            continue
        seen.add(abs_url)
        out.append({"title": title, "url": abs_url})
        if max_links and len(out) >= max_links:
            break
    return out


def extract_article_text(
    soup: BeautifulSoup,
    selectors: Optional[List[str]] = None,
    fallback_chars: int = _BODY_FALLBACK_CHARS,
    use_paragraphs: bool = True,
) -> str:
    """按优先级降级提取正文，避免整页噪声入库。

    - 先尝试各正文容器选择器（命中且非空即返回）。
    - use_paragraphs=True：退而求其次拼接 body 内 <p>。
    - 最终兜底：body 纯文本截断 fallback_chars。
    """
    selectors = selectors or DEFAULT_CONTENT_SELECTORS
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            text = node.get_text(separator="\n", strip=True)
            if text:
                return text

    body = soup.body or soup
    if use_paragraphs:
        paragraphs = [
            p.get_text(strip=True)
            for p in body.find_all("p")
            if p.get_text(strip=True)
        ]
        if paragraphs:
            return "\n".join(paragraphs)
    return body.get_text(separator="\n", strip=True)[:fallback_chars]


def matches_keywords(text: str, keywords: List[str]) -> bool:
    """任一关键词命中即返回 True；关键词为空 → 全部放行。"""
    if not keywords:
        return True
    return any(bool(kw) and kw in text for kw in keywords)


def parse_rss(content: str) -> List[dict]:
    """解析 RSS/Atom XML 内容为标准化 dict 列表（复用 RSSCollector 既有逻辑）。

    惰性导入 feedparser：仅当确有内容时才加载，避免无谓依赖。
    返回 [{"title","content","source":"rss","url","publish_time":None}, ...]。
    """
    import feedparser  # noqa: WPS433  (lazy import by design)

    parsed = feedparser.parse(content)
    items: List[dict] = []
    for entry in getattr(parsed, "entries", []) or []:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        items.append(
            {
                "title": title,
                "content": (
                    entry.get("summary") or entry.get("description") or ""
                ).strip(),
                "source": "rss",
                "url": (entry.get("link") or "").strip(),
                "publish_time": None,
            }
        )
    return items
