from __future__ import annotations

import os
import socket
import time
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.collectors.common import (
    DEFAULT_UA,
    RSSParseError,
    RSS_PROBE_BLOCKED,
    RSS_PROBE_FATAL_CATEGORIES,
    RSS_PROBE_HTTP_FAILED,
    RSS_PROBE_INVALID_FEED,
    RSS_PROBE_NETWORK_FAILED,
    RSS_PROBE_OK,
    RSS_PROBE_REQUEST_FAILED,
    extract_article_text,
    is_safe_rss_url,
    parse_rss,
)
from app.services.foreign_content_sanitizer import sanitize_foreign_html


# ---------------------------------------------------------------------------
# 探测失败分类异常（语义与 common.RSS_PROBE_* 对应；供 probe 映射 Feed 状态）
# ---------------------------------------------------------------------------
class RSSProbeError(Exception):
    """探测失败基类，携带脱敏类别与可选 HTTP 状态码。"""

    category: str = RSS_PROBE_REQUEST_FAILED
    http_status: int | None = None

    def __init__(self, message: str = "", *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.http_status = http_status


class RSSNetworkError(RSSProbeError):
    category = RSS_PROBE_NETWORK_FAILED


class RSSHTTPError(RSSProbeError):
    category = RSS_PROBE_HTTP_FAILED


class RSSBlockedError(RSSProbeError):
    category = RSS_PROBE_BLOCKED


class RSSRequestError(RSSProbeError):
    category = RSS_PROBE_REQUEST_FAILED


def _mask_proxy_url(url: str | None) -> str | None:
    """把代理 URL 中的认证信息脱敏（user:pass@ -> ***@），避免日志/响应泄露凭据。"""
    if not url:
        return url
    try:
        parsed = urlsplit(url)
    except Exception:  # noqa: BLE001
        return None
    if parsed.username or parsed.password:
        netloc = "***:***@" + parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        return f"{parsed.scheme}://{netloc}"
    return url


def resolve_proxy_mode(
    *,
    proxy_override: str | None = None,
    proxy_env: str | None = None,
    use_direct: bool = False,
) -> str:
    """统一代理解析优先级，仅返回脱敏的 mode（绝不返回代理 URL / 凭据）。

    供 ForeignRSSCollector._resolve_proxy 与列表接口 ``_foreign_source_item`` 共用，
    保证「实际采集使用的代理」与「UI 展示的代理模式」完全一致，避免：

    - UI 显示「未配置代理」但采集实际走了系统代理；
    - 或反之。

    优先级（与 ``_resolve_proxy`` 完全一致）：
    1. proxy_override（显式代理 URL，API 不暴露，仅兜底兼容）
    2. use_direct（显式直连，即便存在代理环境变量也强制直连，禁止从代理失败静默回退）
    3. proxy_env 指向的环境变量（API 暴露的 ``proxy_env`` 字段）
    4. FOREIGN_HTTP_PROXY
    5. HTTPS_PROXY / https_proxy
    6. HTTP_PROXY / http_proxy
    7. 以上皆无 -> 直连（默认）

    mode 取值：``explicit`` / ``direct`` / ``env:<NAME>`` / ``direct_default``。
    """
    if proxy_override:
        return "explicit"
    if use_direct:
        return "direct"
    if proxy_env and os.getenv(proxy_env, "").strip():
        return f"env:{proxy_env}"
    if os.getenv("FOREIGN_HTTP_PROXY", "").strip():
        return "env:FOREIGN_HTTP_PROXY"
    if os.getenv("HTTPS_PROXY", "").strip() or os.getenv("https_proxy", "").strip():
        return "env:HTTPS_PROXY"
    if os.getenv("HTTP_PROXY", "").strip() or os.getenv("http_proxy", "").strip():
        return "env:HTTP_PROXY"
    return "direct_default"


class ForeignRSSCollector(BaseCollector):
    """RSS-only collector for the isolated foreign opinion pipeline."""

    source_name = "Foreign RSS"

    def __init__(
        self,
        feeds: list[str] | None = None,
        keywords: list[str] | str | None = None,
        is_foreign: bool = False,
        proxy_env: str | None = None,
        # 显式代理 URL：仅在确实需要通过配置引用代理时使用，且代理地址需经协议/格式校验。
        # 为避免凭据落库，推荐把代理地址放在环境变量中、用 proxy_env 引用其变量名，
        # 而不是把 URL 直接写进 config_json。proxy= 仅作为兜底兼容。
        proxy: str | None = None,
        # 显式直连模式（不经过任何代理）。必须是显式开关，禁止从代理失败静默回退到直连。
        use_direct: bool = False,
        timeout: int = 15,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        max_items: int = 100,
        max_content_length: int = 200_000,
        request_interval: float = 0.5,
        max_retries: int = 2,
        max_redirects: int = 5,
        fetch_full_text: bool = False,
        respect_robots: bool = True,
        source_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.feeds = [str(feed).strip() for feed in (feeds or []) if str(feed).strip()]
        if isinstance(keywords, str):
            keywords = keywords.split(",")
        self.keywords = [str(word).strip() for word in (keywords or []) if str(word).strip()]
        self.proxy_env = proxy_env or "FOREIGN_HTTP_PROXY"
        self.proxy_override = proxy
        self.use_direct = bool(use_direct)
        self.timeout = max(1, int(timeout))
        self.connect_timeout = max(
            0.1, float(connect_timeout if connect_timeout is not None else self.timeout)
        )
        self.read_timeout = max(
            0.1, float(read_timeout if read_timeout is not None else self.timeout)
        )
        self.max_items = max(1, int(max_items))
        self.max_content_length = max(1, int(max_content_length))
        self.request_interval = max(0.0, float(request_interval))
        self.max_retries = max(0, int(max_retries))
        self.max_redirects = max(0, min(int(max_redirects), 10))
        self.fetch_full_text = bool(fetch_full_text)
        self.respect_robots = bool(respect_robots)
        self.is_foreign = bool(is_foreign)
        if source_name:
            self.source_name = str(source_name)
        self.last_fetched_raw = 0
        self.last_error: str | None = None
        self.last_failed_feeds = 0
        self.last_feed_reports: list[dict[str, Any]] = []
        self.last_http_status: int | None = None
        # 代理解析结果与本次请求是否实际走代理（准确反映是否使用代理）。
        self.last_proxy_used: bool = False
        self.proxy_mode: str = "unresolved"
        self.last_proxy_url_masked: str | None = None

    def _resolve_proxy(self) -> dict[str, Any]:
        """统一代理解析（优先级见模块说明）。

        返回 {proxies, url, url_masked, mode}：
          - proxies: requests 可用的代理字典，或 None（直连）。
          - mode: 解析来源（env:FOREIGN_HTTP_PROXY / env:HTTPS_PROXY / explicit / direct ...）。
        代理地址必须校验协议与格式；缺省不自动从代理失败回退到直连。
        """
        candidate: str | None = None
        if self.proxy_override:
            candidate = self.proxy_override.strip()
        elif self.use_direct:
            # 显式直连：即便存在代理环境变量也强制直连（禁止从代理失败静默回退）。
            candidate = None
        elif self.proxy_env and os.getenv(self.proxy_env, "").strip():
            candidate = os.getenv(self.proxy_env, "").strip()
        elif os.getenv("FOREIGN_HTTP_PROXY", "").strip():
            candidate = os.getenv("FOREIGN_HTTP_PROXY", "").strip()
        elif os.getenv("HTTPS_PROXY", "").strip() or os.getenv("https_proxy", "").strip():
            candidate = (os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or "").strip()
        elif os.getenv("HTTP_PROXY", "").strip() or os.getenv("http_proxy", "").strip():
            candidate = (os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or "").strip()
        else:
            candidate = None
        # mode 由共享函数统一推导，保证与列表接口 _foreign_source_item 完全一致。
        mode = resolve_proxy_mode(
            proxy_override=self.proxy_override,
            proxy_env=self.proxy_env,
            use_direct=self.use_direct,
        )
        if candidate:
            _validate_proxy_url(candidate)  # 协议/格式非法 -> ValueError
            proxies: dict[str, str] | None = {"http": candidate, "https": candidate}
        else:
            proxies = None
        return {
            "proxies": proxies,
            "url": candidate,
            "url_masked": _mask_proxy_url(candidate),
            "mode": mode,
        }

    def _proxies(self) -> dict[str, str] | None:
        # 向后兼容：返回解析出的代理字典（无代理返回 None）。
        return self._resolve_proxy()["proxies"]

    @property
    def proxy_used(self) -> bool:
        # 准确反映「本次请求是否实际使用了代理」（由 _get_response 在请求前赋值）。
        return self.last_proxy_used

    def _get(self, url: str) -> str:
        return self._get_response(url).text

    def _get_response(self, url: str) -> requests.Response:
        resolution = self._resolve_proxy()
        proxies = resolution["proxies"]
        self.proxy_mode = resolution["mode"]
        self.last_proxy_url_masked = resolution["url_masked"]
        self.last_proxy_used = bool(proxies)
        for attempt in range(self.max_retries + 1):
            try:
                current = url
                for hop in range(self.max_redirects + 1):
                    safe, reason = is_safe_rss_url(current, resolve_dns=True)
                    if not safe:
                        raise RSSBlockedError(reason or "unsafe URL")
                    response = requests.get(
                        current,
                        headers={"User-Agent": DEFAULT_UA},
                        timeout=(self.connect_timeout, self.read_timeout),
                        proxies=proxies,
                        allow_redirects=False,
                    )
                    self.last_http_status = response.status_code
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise RSSRequestError("RSS redirect missing Location")
                        if hop >= self.max_redirects:
                            raise RSSRequestError("RSS redirect limit exceeded")
                        current = urljoin(current, location)
                        continue
                    response.raise_for_status()
                    response.encoding = response.encoding or response.apparent_encoding or "utf-8"
                    return response
                raise RSSRequestError("RSS redirect limit exceeded")
            except RSSProbeError:
                raise
            except requests.exceptions.HTTPError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                raise RSSHTTPError(str(exc), http_status=status)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                    requests.exceptions.SSLError, socket.gaierror, OSError) as exc:
                raise RSSNetworkError(f"{type(exc).__name__}: network request failed")
            except Exception as exc:  # noqa: BLE001
                raise RSSRequestError(f"{type(exc).__name__}: request failed")
        raise RSSRequestError("RSS request failed")

    @staticmethod
    def _feed_label(url: str) -> str:
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return "invalid-feed"
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}"

    def probe(self) -> list[dict[str, Any]]:
        """Probe each RSS feed without fetching article bodies or writing state."""
        self.last_feed_reports = []
        self.last_fetched_raw = 0
        self.last_error = None
        self.last_failed_feeds = 0
        for feed_url in self.feeds:
            self.last_http_status = None
            report: dict[str, Any] = {
                "feed": self._feed_label(feed_url),
                "http_status": None,
                "xml_parsed": False,
                "raw_count": 0,
                "valid_count": 0,
                "title_count": 0,
                "summary_count": 0,
                "published_time_count": 0,
                "url_duplicate_count": 0,
                "languages": {"en": 0, "zh": 0, "mixed": 0, "unknown": 0},
                "matched_count": 0,
                "failure_count": 0,
                "error": None,
            }
            try:
                raw = self._get(feed_url)
                report["http_status"] = self.last_http_status or 200
                parsed = parse_rss(raw)
                report["xml_parsed"] = True
                report["raw_count"] = len(parsed)
                self.last_fetched_raw += len(parsed)
                seen_urls: set[str] = set()
                for item in parsed[: self.max_items]:
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    summary = str(item.get("content") or "").strip()
                    if title:
                        report["title_count"] += 1
                    if summary:
                        report["summary_count"] += 1
                    if item.get("publish_time"):
                        report["published_time_count"] += 1
                    if title and url:
                        report["valid_count"] += 1
                        if url in seen_urls:
                            report["url_duplicate_count"] += 1
                        seen_urls.add(url)
                    sample = f"{title}\n{summary}"
                    has_zh = any("\u4e00" <= char <= "\u9fff" for char in sample)
                    has_en = any(char.isascii() and char.isalpha() for char in sample)
                    language = "mixed" if has_zh and has_en else "zh" if has_zh else "en" if has_en else "unknown"
                    report["languages"][language] += 1
                    text = "\n".join(
                        str(item.get(key) or "")
                        for key in ("title", "content")
                    ).casefold()
                    if any(word.casefold() in text for word in self.keywords):
                        report["matched_count"] += 1
            except RSSParseError:
                self.last_failed_feeds += 1
                self.last_error = "invalid RSS/Atom XML"
                report["failure_count"] = 1
                report["error"] = "invalid XML"
                report["error_category"] = RSS_PROBE_INVALID_FEED
                report["status"] = RSS_PROBE_INVALID_FEED
            except RSSProbeError as exc:
                self.last_failed_feeds += 1
                self.last_error = _safe_probe_message(exc)
                report["failure_count"] = 1
                report["http_status"] = exc.http_status
                report["error"] = _safe_probe_message(exc)
                report["error_category"] = exc.category
                report["status"] = exc.category
            except Exception:  # noqa: BLE001
                self.last_failed_feeds += 1
                self.last_error = "RSS request failed"
                report["failure_count"] = 1
                report["error"] = "request failed"
                report["error_category"] = RSS_PROBE_REQUEST_FAILED
                report["status"] = RSS_PROBE_REQUEST_FAILED
            if not report["failure_count"]:
                report["status"] = "success" if report["valid_count"] else "empty_feed"
                report["error_category"] = None
            self.last_feed_reports.append(report)
        return list(self.last_feed_reports)

    def _robots_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlsplit(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            parser = RobotFileParser()
            parser.parse(self._get(robots_url).splitlines())
            return parser.can_fetch(DEFAULT_UA, url)
        except Exception:
            # Optional full-text retrieval fails closed when robots cannot be read.
            return False

    def _fetch_full_text(self, url: str) -> str:
        if not self.fetch_full_text or not url:
            return ""
        if not self._robots_allowed(url):
            return ""
        try:
            html = self._get(url)
            return extract_article_text(
                BeautifulSoup(html, "html.parser"),
                fallback_chars=self.max_content_length,
            )[: self.max_content_length]
        except Exception:
            # RSS items remain usable when optional public-body retrieval fails.
            return ""

    def fetch(self, **kwargs: Any) -> list[dict[str, Any]]:
        # CollectorService's domestic keyword arguments are deliberately ignored.
        if not self.is_foreign or not self.keywords or not self.feeds:
            return []

        items: list[dict[str, Any]] = []
        self.last_fetched_raw = 0
        self.last_error = None
        self.last_failed_feeds = 0
        for feed_url in self.feeds:
            try:
                parsed = parse_rss(self._get(feed_url))
            except RSSParseError:
                self.last_error = "invalid RSS/Atom XML"
                self.last_failed_feeds += 1
                continue
            except Exception:  # noqa: BLE001
                self.last_error = "RSS request failed"
                self.last_failed_feeds += 1
                continue
            seen: set[tuple[str, str]] = set()
            for item in parsed:
                title = str(item.get("title") or "").strip()
                summary = str(item.get("summary") or item.get("content") or "").strip()
                raw_content = str(item.get("content") or summary).strip()
                url = str(item.get("url") or "").strip()
                summary = sanitize_foreign_html(summary)[: self.max_content_length]
                content = sanitize_foreign_html(self._fetch_full_text(url) or raw_content or summary)[: self.max_content_length]
                external_id = str(item.get("external_id") or item.get("guid") or "").strip()
                content_key = (title + "\n" + summary + "\n" + content).casefold()
                if external_id:
                    dedupe_key = ("external_id", external_id)
                elif url:
                    dedupe_key = ("url", url)
                else:
                    dedupe_key = ("content", content_key)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                merged = f"{title}\n{summary}\n{content}".lower()
                matched = [
                    word for word in self.keywords if word.lower() in merged
                ]
                if not matched:
                    continue
                items.append(
                    {
                        "title": title,
                        "summary": summary[: self.max_content_length],
                        "content": content,
                        "url": url,
                        "author": item.get("author") or "",
                        "external_id": external_id or None,
                        "guid": item.get("guid") or external_id or None,
                        "source": self.source_name,
                        "publish_time": item.get("publish_time"),
                        "matched_keywords": list(dict.fromkeys(matched)),
                    }
                )
                if len(items) >= self.max_items:
                    break
            self.last_fetched_raw += len(parsed)
            if len(items) >= self.max_items:
                break
            if self.request_interval:
                time.sleep(self.request_interval)
        return items[: self.max_items]


class FoxNewsForeignCollector(ForeignRSSCollector):
    source_name = "Fox News"


class GuardianForeignCollector(ForeignRSSCollector):
    source_name = "The Guardian"


class NYTimesChineseForeignCollector(ForeignRSSCollector):
    source_name = "纽约时报中文网"


# ---------------------------------------------------------------------------
# 代理地址校验 / 脱敏 / 代理健康探针
# ---------------------------------------------------------------------------
def _validate_proxy_url(url: str) -> None:
    """校验代理 URL 协议与格式；非法 -> ValueError。不校验可达性。"""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("代理地址不能为空")
    parsed = urlsplit(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https", "socks5", "socks5h", "socks4", "socks4a"):
        raise ValueError(f"不支持的代理协议：{scheme or '无协议'}")
    if not parsed.hostname:
        raise ValueError("代理地址缺少主机名")


def _safe_probe_message(exc: Exception) -> str:
    """把探测异常转成脱敏短描述（不泄露代理密码 / Token / 完整带认证 URL）。"""
    message = " ".join(str(exc).split())
    lowered = message.casefold()
    for marker in ("password", "token", "secret", "proxy", "://", "@",
                   "authorization", "cookie", "credential"):
        if marker in lowered:
            return "网络请求失败（已隐藏敏感细节）"
    return message[:240]


def probe_proxy_health(
    proxy_url: str,
    sample_feed: str | None = None,
    *,
    timeout: int = 5,
    resolve_dns: bool = True,
) -> dict[str, Any]:
    """可复用的代理探针：检查代理端口可达性，并可选经代理对样例 Feed 做短超时应用层探测。

    - ``tcp_reachable``：代理 host:port 是否可建立 TCP 连接（区分「代理端口不可达」）。
    - ``target_status``：经代理请求样例 Feed 的结果类别（无样例时为 None），
      用于区分「代理可达但目标站点失败」。
    - 不写入任何业务数据（opinions / collector_runs / 数据源）；遵守现有 SSRF 防护。
    - 返回的代理地址均脱敏。供测试接口调用。
    """
    result: dict[str, Any] = {
        "proxy_url_masked": _mask_proxy_url(proxy_url),
        "tcp_reachable": False,
        "tcp_error_category": None,
        "target_status": None,
        "target_http_status": None,
        "target_error_category": None,
        "mode": "health",
    }
    _validate_proxy_url(proxy_url)
    parsed = urlsplit(proxy_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=max(1, int(timeout))):
            result["tcp_reachable"] = True
    except (OSError, socket.gaierror, ValueError):
        result["tcp_error_category"] = RSS_PROBE_NETWORK_FAILED
        result["tcp_reachable"] = False
        return result  # 代理端口不可达，无需继续
    if not sample_feed:
        return result
    # 经代理对样例 Feed 做应用层探测（短超时），区分「代理可达但目标失败」。
    ok, reason = is_safe_rss_url(sample_feed, resolve_dns=resolve_dns)
    if not ok:
        result["target_status"] = RSS_PROBE_BLOCKED
        result["target_error_category"] = RSS_PROBE_BLOCKED
        return result
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        resp = requests.get(
            sample_feed,
            headers={"User-Agent": DEFAULT_UA},
            timeout=(timeout, timeout),
            proxies=proxies,
            allow_redirects=False,
        )
        result["target_http_status"] = resp.status_code
        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("Location")
            if not location:
                result["target_status"] = RSS_PROBE_REQUEST_FAILED
                result["target_error_category"] = RSS_PROBE_REQUEST_FAILED
                return result
            # 仅做一层探测，不展开重定向链（健康检查目的）。
            result["target_status"] = RSS_PROBE_OK
            return result
        resp.raise_for_status()
        result["target_status"] = RSS_PROBE_OK
    except requests.exceptions.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        result["target_http_status"] = status
        result["target_status"] = RSS_PROBE_HTTP_FAILED
        result["target_error_category"] = RSS_PROBE_HTTP_FAILED
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
            requests.exceptions.SSLError, socket.gaierror, OSError):
        result["target_status"] = RSS_PROBE_NETWORK_FAILED
        result["target_error_category"] = RSS_PROBE_NETWORK_FAILED
    except Exception:  # noqa: BLE001
        result["target_status"] = RSS_PROBE_REQUEST_FAILED
        result["target_error_category"] = RSS_PROBE_REQUEST_FAILED
    return result
