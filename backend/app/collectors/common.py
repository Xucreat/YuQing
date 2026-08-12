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

import datetime as _dt
import ipaddress
import json
import logging
import re
import shutil
import socket
import subprocess
import time as _time
import urllib.parse
from typing import List, Optional, Tuple

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
# 前半段为既有选择器（保障已有 9 源行为不变），后半段补充政务 CMS 常见正文容器
# （360/TRS/地方集约化平台：div.article / div.cont / div.neirong / div.nr / div.sj_nrbr 等）。
# 仅追加、不前置，避免误命中导航包装容器；命中即返回，未命中继续降级到 <p> 拼接。
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
    # —— 政务 CMS 补充（Phase 3 市级源接入）——
    "div.article",
    "div.cont",
    "div.neirong",
    "div.nr",
    "div.con_txt",
    "div.TRS_UEDITOR",
    "div.news_con",
    "div.detail",
    "div.content-box",
    "div.sj_nrbr",
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
    except requests.exceptions.SSLError as exc:
        # Some government sites reject Python OpenSSL but accept the system TLS stack.
        logger.warning("TLS 握手失败，尝试系统 curl 兼容抓取 url=%s err=%s", url, exc)
        return _curl_get(session, url, timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning("抓取失败 url=%s err=%s", url, exc)
        return None


def _curl_get(
    session: requests.Session, url: str, timeout: int, *, follow_redirects: bool = True
) -> Optional[str]:
    """Use the platform curl TLS stack as a narrow fallback for SSL failures.

    ``follow_redirects=False`` 时不传 ``--location``（curl 默认不跟随），用于
    SSRF 敏感场景（见 http_get_guarded）：避免重定向绕过地址白名单校验。
    既有调用方不传该参数，行为与改动前完全一致。
    """
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        logger.warning("系统 curl 不可用，无法执行 TLS 兼容抓取 url=%s", url)
        return None
    user_agent = str(session.headers.get("User-Agent") or DEFAULT_UA)
    timeout_value = str(max(1, int(timeout)))
    command = [
        curl,
        "--silent",
        "--show-error",
        "--fail",
    ]
    if follow_redirects:
        command.append("--location")
    command += [
        "--max-time",
        timeout_value,
        "--connect-timeout",
        timeout_value,
        "--user-agent",
        user_agent,
        url,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=max(1, int(timeout)) + 2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("系统 curl 抓取失败 url=%s err=%s", url, exc)
        return None
    if result.returncode != 0:
        detail = (result.stderr or b"").decode("utf-8", errors="replace").strip()
        logger.warning("系统 curl 返回失败 url=%s code=%s err=%s", url, result.returncode, detail)
        return None
    return (result.stdout or b"").decode("utf-8", errors="replace") or None


def http_get_guarded(
    session: requests.Session,
    url: str,
    timeout: int = 10,
    *,
    guard=None,
    max_redirects: int = 5,
) -> Optional[str]:
    """GET，**手动跟随重定向并对每一跳重新做 guard 校验**（SSRF 防护）。

    与 ``http_get`` 的区别：``allow_redirects=False``，逐跳解析 Location 并再次
    校验，防止「初始地址合法 → 302 跳转到 127.0.0.1 / 169.254.169.254」的绕过。
    TLS 失败回退 curl 时同样禁用 ``--location``。

    guard: ``Callable[[str], Tuple[bool, Optional[str]]]``，返回 (是否放行, 原因)。
    任何异常返回 None（防御式，不崩溃；与 http_get 的契约一致）。
    """
    if guard is None:
        def guard(_u):  # noqa: ANN001
            return True, None

    current = url
    for _hop in range(max_redirects + 1):
        try:
            ok, reason = guard(current)
        except Exception as exc:  # noqa: BLE001  guard 自身异常不得导致崩溃
            logger.warning("URL 安全校验异常 url=%s err=%s", current, exc)
            return None
        if not ok:
            logger.warning("URL 被安全校验拦截 url=%s reason=%s", current, reason)
            return None
        try:
            resp = session.get(current, timeout=timeout, allow_redirects=False)
        except requests.exceptions.SSLError as exc:
            logger.warning(
                "TLS 握手失败，尝试系统 curl 兼容抓取（禁止重定向） url=%s err=%s",
                current, exc,
            )
            return _curl_get(session, current, timeout, follow_redirects=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("抓取失败 url=%s err=%s", current, exc)
            return None
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                logger.warning("重定向缺少 Location url=%s", current)
                return None
            current = urllib.parse.urljoin(current, location)
            continue
        try:
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding
            return resp.text
        except Exception as exc:  # noqa: BLE001
            logger.warning("抓取失败 url=%s err=%s", current, exc)
            return None
    logger.warning("重定向次数超过上限（%s） url=%s", max_redirects, url)
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


def is_safe_rss_url(url: str, *, resolve_dns: bool = True) -> Tuple[bool, Optional[str]]:
    """SSRF 防护：校验 RSS/Atom 地址是否可安全抓取（供 RSSCollector 与后台 API 复用）。

    仅允许 http/https；解析后的 IP 不能是 loopback / 私网 / 链路本地 / 保留 /
    多播地址（阻止 localhost、127.0.0.1、10.x、192.168.x、169.254.x、fc00::/7 等）。
    返回 (safe, reason)，reason 仅在 safe=False 时有意义。

    ``resolve_dns``：为 False 时仅做「协议 + 字面量本地地址」的静态拦截（用于
    API 创建期快速校验，避免 DNS 抖动）；为 True 时（运行时默认）额外对域名做
    DNS 解析并逐 IP 检查，构成完整的 SSRF 防线。
    """
    if not isinstance(url, str) or not url.strip():
        return False, "地址为空"
    parsed = urllib.parse.urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, f"仅支持 http/https，当前为 {scheme or '无协议'}"
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False, "缺少主机名"
    # 1) 字面量本地/内网地址直接拦截（无需 DNS）
    if host in ("localhost", "0.0.0.0", "0", "::1", "::"):
        return False, f"禁止本地/无效地址：{host}"
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        addr = None
    if addr is not None:
        if addr.is_loopback or addr.is_private or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            return False, f"禁止内网地址：{host}"
        return True, None
    if not resolve_dns:
        # 无法静态判定（需 DNS），交由运行时兜底拦截
        return True, None
    # 2) 域名：解析后逐个检查是否为内网 IP
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception as exc:  # noqa: BLE001
        return False, f"域名解析失败：{exc}"
    if not infos:
        return False, "域名解析为空"
    for info in infos:
        ip = info[4][0] if isinstance(info, tuple) and len(info) > 4 else None
        if not ip:
            continue
        try:
            resolved = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (
            resolved.is_loopback
            or resolved.is_private
            or resolved.is_link_local
            or resolved.is_reserved
            or resolved.is_multicast
        ):
            return False, f"解析到内网地址：{ip}"
    return True, None


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


def matches_region_topic(
    text: str,
    region_kws: List[str],
    topic_kws: Optional[List[str]] = None,
    match_mode: str = "region_only",
) -> bool:
    """地域前置过滤（采集阶段）。

    match_mode 控制过滤策略：
      - "region_only"（默认）：严格地域前置。命中任一地域词 → True；否则 → False。
        适用于本地/区县/通用回退源——内容应明确关联廊坊地域。
      - "region_or_topic"：国家级源独立策略。命中任一地域词 → True；
        否则命中任一主题词（topic_kws）→ True；否则 → False。
        适用于 xinhua / people / chinanews 等全国性媒体：其本质是「全国主题雷达」，
        不应因严格地域前置而丢失全国范围内的廊坊相关主题召回。
      - "topic_only"（Phase DataSource-Config-1 新增，仅在 config_json 显式配置
        filter_mode 时启用）：纯主题过滤，不要求地域命中。命中任一主题词 → True；
        否则 → False。面向「区域监测 → 全国主题监测」的扩展场景。
        所有采集器的默认 filter_mode 均维持改造前取值，本模式默认无人使用。

    设计边界（明确，避免后续误用）：
      - region_kws 为空（配置异常，如地域词全部被禁用/未分类）：
        fail-safe 返回 False，**不降级**、不靠 topic 兜底，避免产出无地域数据。
        此行为在 region_only / region_or_topic 下一致；调用方应记录该异常
        （见 service.py 运行记录标注）。
      - topic_only 是**显式声明不做地域约束**的场景，因此不适用上述地域 fail-safe；
        改为对 topic_kws 施加同源的 fail-safe：主题词为空 → 返回 False，
        避免退化成「无条件放行」造成全量入库。
      - topic_kws 仅在 match_mode="region_or_topic" / "topic_only" 时参与判定；
        region_only 下忽略（保持不扩大范围）。
    """
    if match_mode == "topic_only":
        # 纯主题模式：不要求地域命中；主题词为空时 fail-safe 拦截（同样不放行全部）。
        if not topic_kws:
            logger.warning(
                "matches_region_topic: match_mode=topic_only 但 topic_kws 为空"
                "（配置异常），拦截全部以避免无条件放行"
            )
            return False
        return any(bool(t) and t in text for t in topic_kws)
    if not region_kws:
        # 配置异常：地域关键词为空。fail-safe —— 拦截一切，交由调用方记录，
        # 避免表现为「普通零数据」。与 match_mode 无关。
        logger.warning(
            "matches_region_topic: region_kws 为空（配置异常），拦截全部以避免无地域数据"
        )
        return False
    if any(bool(r) and r in text for r in region_kws):
        return True
    if match_mode == "region_or_topic" and topic_kws:
        return any(bool(t) and t in text for t in topic_kws)
    return False


class RSSParseError(ValueError):
    """Raised when a feed body is not well-formed RSS/Atom XML."""


def parse_rss(content: str) -> List[dict]:
    """解析 RSS/Atom XML 内容为标准化 dict 列表（复用 RSSCollector 既有逻辑）。

    惰性导入 feedparser：仅当确有内容时才加载，避免无谓依赖。
    返回 [{"title","content","source":"rss","url","publish_time":datetime|None}, ...]。
    """
    import feedparser  # noqa: WPS433  (lazy import by design)

    parsed = feedparser.parse(content)
    # ``bozo`` is feedparser's explicit malformed-input signal.  A malformed
    # document must not be reported as a successful empty feed, even when the
    # tolerant parser happened to recover a partial entry list.
    if bool(getattr(parsed, "bozo", False)):
        exc = getattr(parsed, "bozo_exception", None)
        raise RSSParseError(str(exc) if exc else "invalid RSS/Atom XML")
    items: List[dict] = []
    for entry in getattr(parsed, "entries", []) or []:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        content_value = entry.get("content") or ""
        if isinstance(content_value, list):
            content_value = next(
                (
                    part.get("value")
                    for part in content_value
                    if isinstance(part, dict) and part.get("value")
                ),
                "",
            )
        content_value = str(content_value or "").strip()
        guid = str(entry.get("guid") or entry.get("id") or "").strip()
        author = str(entry.get("author") or entry.get("creator") or "").strip()
        items.append(
            {
                "title": title,
                "summary": summary,
                "content": content_value or summary,
                "author": author,
                "external_id": guid or None,
                "guid": guid or None,
                "source": "rss",
                "url": (entry.get("link") or "").strip(),
                "publish_time": _feed_publish_time(entry),
            }
        )
    return items


# ---------------------------------------------------------------------------
# 发布时间抽取（需求：舆情列表需真实显示发布时间，采集器此前一律写 None）
# ---------------------------------------------------------------------------
# 常见承载发布时间的 <meta> 属性名（property 或 name，大小写不敏感）
_META_DATE_KEYS = (
    "article:published_time",
    "article:publication_time",
    "og:published_time",
    "og:pubdate",
    "og:publishdate",
    "datePublished",
    "date",
    "pubdate",
    "publishdate",
    "publishDate",
    "publish_time",
    "dc.date",
    "sdate",
    "article:published",
    "issued",
    "created",
)


def _normalize_date_text(s: str) -> str:
    """把中文/斜杠日期分隔符统一成 '-'，便于 strptime。"""
    return (
        s.strip()
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("/", "-")
    )


def _parse_absolute(s: str) -> Optional[_dt.datetime]:
    if not s:
        return None
    s = _normalize_date_text(s)
    # ISO 8601（含 T 与 Z / +08:00）
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    fmts = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    )
    for f in fmts:
        try:
            return _dt.datetime.strptime(s, f)
        except Exception:
            pass
    return None


def _parse_relative(s: str) -> Optional[_dt.datetime]:
    """解析「刚刚 / x分钟前 / x小时前 / 今天/昨天/前天 HH:MM」等相对时间。"""
    now = _dt.datetime.now()
    if "刚刚" in s or "刚才" in s:
        return now
    m = re.search(r"(\d+)\s*分钟前", s)
    if m:
        return now - _dt.timedelta(minutes=int(m.group(1)))
    m = re.search(r"(\d+)\s*小时前", s)
    if m:
        return now - _dt.timedelta(hours=int(m.group(1)))
    base = None
    if "前天" in s:
        base = now - _dt.timedelta(days=2)
    elif "昨天" in s:
        base = now - _dt.timedelta(days=1)
    elif "今天" in s or "今日" in s:
        base = now
    if base is not None:
        tm = re.search(r"(\d{1,2})[:：](\d{2})", s)
        if tm:
            return base.replace(
                hour=int(tm.group(1)), minute=int(tm.group(2)), second=0, microsecond=0
            )
        return base
    return None


def _parse_date_string(s: str) -> Optional[_dt.datetime]:
    dt = _parse_relative(s)
    if dt:
        return dt
    return _parse_absolute(s)


def parse_publish_date_from_url(url: Optional[str]) -> Optional[_dt.datetime]:
    """从文章 URL 路径中解析发布日期（如 /2026/07-24/ 或 /2026/07/24/）。

    作为采集器未能从页面 meta/JSON-LD/text 或 RSS 取得发布时间时的兜底来源
    （许多新闻/政务站点会把日期编码进 URL 路径）。解析失败返回 None。
    """
    if not url:
        return None
    m = re.search(r"(?:19|20)\d{2}[/\-]\d{1,2}[/\-]\d{1,2}", url)
    if not m:
        return None
    return _parse_absolute(m.group(0))


def extract_publish_time(soup, url: Optional[str] = None) -> Optional[_dt.datetime]:
    """从文章页（BeautifulSoup/Tag）抽取发布时间，失败返回 None。

    优先级：<meta> 时间属性 > JSON-LD datePublished > <time datetime> >
    正文文本中的日期片段（含相对时间）。仅返回 datetime，不做时区强转。
    """
    # 1) meta 标签
    for tag in soup.find_all("meta"):
        key = (tag.get("property") or tag.get("name") or "").lower()
        if key in _META_DATE_KEYS:
            val = (tag.get("content") or "").strip()
            dt = _parse_date_string(val)
            if dt:
                return dt

    # 2) JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text(strip=True) or "{}")
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            for fld in ("datePublished", "dateCreated", "uploadDate", "dateModified"):
                if node.get(fld):
                    dt = _parse_date_string(str(node[fld]))
                    if dt:
                        return dt

    # 3) <time datetime>
    for t in soup.find_all("time"):
        val = (t.get("datetime") or t.get_text(strip=True) or "").strip()
        if val:
            dt = _parse_date_string(val)
            if dt:
                return dt

    # 4) 文本片段：优先靠近标题的前 3000 字
    text = soup.get_text(" ", strip=True)[:3000]
    # 绝对日期（含中文/斜杠/横线，可选 时分）
    m = re.search(
        r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?(?:\s*[T\s]\d{1,2}[:：]\d{2}(?::\d{2})?)?",
        text,
    )
    if m:
        dt = _parse_date_string(m.group(0))
        if dt:
            return dt
    # 相对时间（前天/昨天/今天 + 可选 时分）
    m = re.search(r"(?:前天|昨天|今天|今日)[^\n]{0,12}", text)
    if m:
        dt = _parse_relative(m.group(0))
        if dt:
            return dt
    # 5) URL 兜底：页面/RSS 均无日期时，从 URL 路径解析（如 /2026/07-24/）
    if url:
        dt = parse_publish_date_from_url(url)
        if dt:
            return dt
    return None


def _feed_publish_time(entry) -> Optional[_dt.datetime]:
    """从 feedparser entry 抽取发布时间（优先 *_parsed 结构体）。"""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(key)
        if val:
            try:
                return _dt.datetime.fromtimestamp(_time.mktime(val))
            except Exception:
                pass
    for key in ("published", "updated", "created"):
        s = entry.get(key)
        if s:
            dt = _parse_date_string(s)
            if dt:
                return dt
    return None
