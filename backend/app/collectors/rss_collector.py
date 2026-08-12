"""RSS 采集器（国内通用 RSS 数据源，Phase RSS-Support）。

设计约束（来自用户）：
- feeds 优先来自当前数据源的 config_json（{"feeds":[{"url":...}]}）；
  RSS_URLS 环境变量仅作为旧配置兼容 fallback（新建/编辑一律走 config_json）。
- 复用 common.http_get_guarded + feedparser：先 http_get_guarded（带超时 +
  SSRF 防护，且手动跟随重定向并对每一跳重新做地址校验，防 302 跳内网绕过），
  再 feedparser 解析（惰性导入，无源不加载）。
- 单 Feed 失败隔离；单源失败不影响其他国内数据源（registry/service 顶层捕获）。
- 去重优先级：guid(external_id) > link(url) > 内容哈希（两者皆无时）。
- 不做任何 AI 调用。
"""
import hashlib
import logging
import os
from typing import Any, Optional

from app.collectors.base import BaseCollector
from app.collectors.common import (
    DEFAULT_UA,
    _feed_publish_time,
    http_get_guarded,
    is_safe_rss_url,
    make_session,
)

logger = logging.getLogger(__name__)


def _parse_rss_urls_env() -> list[str]:
    """从环境变量 RSS_URLS（逗号分隔）读取 RSS 源；为空返回 []。"""
    raw = os.getenv("RSS_URLS", "") or ""
    return [u.strip() for u in raw.split(",") if u.strip()]


def http_get(session, url: str, timeout: int = 10):
    """Compatibility seam for RSS tests and callers, retaining guarded fetches."""
    return http_get_guarded(session, url, timeout, guard=is_safe_rss_url)


class RSSCollector(BaseCollector):
    """通用国内 RSS 采集器：从数据源 config_json.feeds 读取地址并抓取。"""

    source_name = "rss"

    DEFAULT_TIMEOUT = 15
    DEFAULT_MAX_ITEMS = 100

    def __init__(
        self,
        feeds: Optional[list] = None,
        max_items: Optional[int] = None,
        timeout: Optional[int] = None,
        keywords: Optional[str] = None,
        source_name: Optional[str] = None,
    ) -> None:
        # feeds 为空（None 或 []）-> 回退 RSS_URLS 环境变量；仍空则不加载 feedparser、不联网。
        self.session = make_session(DEFAULT_UA)
        self.feeds: list[dict] = self._normalize_feeds(feeds)
        self._max_items = max_items
        self._timeout = timeout
        # 与 GenericSiteCollector 同一约定：config_json.source_name 覆盖类默认名。
        # collector_runs.collector_name 与 opinions.source 均取 self.source_name，
        # 缺省会让所有 RSS 源共用 "rss" 一个名字（列表显示「未运行」且互相串台）。
        if source_name and str(source_name).strip():
            self.source_name = str(source_name).strip()

    # -- feeds 归一化 -------------------------------------------------------
    @staticmethod
    def _normalize_feeds(feeds) -> list[dict]:
        """接受 list[str] 或 list[{"url":...}]（或 None）。

        返回 [{"url": 合法 http/https 地址}, ...]。非法地址直接抛错，
        交由 registry 记为装配失败（可见、可追溯），不静默吞掉。
        """
        if feeds is None:
            feeds = [{"url": u} for u in _parse_rss_urls_env()]
        out: list[dict] = []
        for f in feeds or []:
            if isinstance(f, str):
                url = f
            elif isinstance(f, dict):
                url = f.get("url")
            else:
                raise ValueError(f"非法的 RSS feed 配置：{f!r}")
            if not isinstance(url, str) or not url.strip():
                raise ValueError(f"RSS feed 地址不能为空：{f!r}")
            url = url.strip()
            ok, reason = is_safe_rss_url(url, resolve_dns=False)
            if not ok:
                raise ValueError(f"RSS feed 地址不合法（{reason}）：{url}")
            out.append({"url": url})
        return out

    # -- 运行期参数 ---------------------------------------------------------
    def _effective_timeout(self) -> int:
        if self._timeout:
            return int(self._timeout)
        return int(
            self.source_config.get_int("timeout", self.DEFAULT_TIMEOUT, minimum=1)
            or self.DEFAULT_TIMEOUT
        )

    def _effective_max_items(self):
        if self._max_items is not None:
            return self._max_items
        return self.source_config.max_items(self.DEFAULT_MAX_ITEMS) or self.DEFAULT_MAX_ITEMS

    def _src(self) -> str:
        # 与 GenericSiteCollector 一致：item.source 取显示名 source_name。
        return getattr(self, "source_name", None) or "rss"

    # -- 解析单条 entry -----------------------------------------------------
    @staticmethod
    def _entry_to_item(entry, source: str) -> Optional[dict]:
        title = (entry.get("title") or "").strip()
        if not title:
            return None
        link = (entry.get("link") or "").strip()
        guid = (entry.get("guid") or entry.get("id") or "").strip()
        content = (entry.get("summary") or entry.get("description") or "").strip()
        author = (entry.get("author") or entry.get("creator") or "").strip()
        pub = _feed_publish_time(entry)
        external_id = guid or None
        # 两者皆无（既无 guid 也无 link）-> 稳定的内容哈希，避免重复入库
        if not external_id and not link:
            external_id = "sha1:" + hashlib.sha1(
                f"{title}|{content}".encode("utf-8")
            ).hexdigest()
        return {
            "title": title,
            "content": content,
            "url": link,
            "publish_time": pub,
            "author": author,
            "source": source,
            "external_id": external_id,
        }

    @staticmethod
    def _dedup_key(it: dict):
        eid = it.get("external_id")
        if eid:
            return ("external_id", eid)
        if it.get("url"):
            return ("url", it["url"])
        return ("hash", it.get("external_id"))

    # -- 抓取 ---------------------------------------------------------------
    def fetch(self, keywords=None, region_kw=None, topic_kw=None) -> list[dict[str, Any]]:
        # region_kw / topic_kw：统一 CollectorService 接口参数（service.py 调用
        # collector.fetch(keywords=..., region_kw=..., topic_kw=...)）。RSS 与
        # government_collector 同约定——不在采集器内部做地域前置过滤，地域准入
        # 由 service 层 OpinionAdmissionService 统一裁定。这样 fetched_raw 能真实
        # 反映 Feed 抓取量（便于诊断），admission_filtered 反映地域准入结果。
        # 不接受这两个参数会导致真实采集路径 TypeError（test_connection/单测因不传
        # 该参数而无法暴露此缺陷）。
        del region_kw, topic_kw
        if not self.feeds:
            return []
        max_items = self._effective_max_items()
        timeout = self._effective_timeout()
        source = self._src()
        seen: set = set()
        items: list[dict] = []

        import feedparser  # 惰性导入：仅当确有源时才加载

        for feed in self.feeds:
            if max_items is not None and len(items) >= max_items:
                break
            url = feed["url"]
            try:
                # 运行时完整 SSRF 防护（含 DNS 解析后的内网地址拦截）
                ok, reason = is_safe_rss_url(url)
                if not ok:
                    logger.warning(
                        "RSS 源被 SSRF 防护拦截 name=%s url=%s reason=%s",
                        source, url, reason,
                    )
                    continue
                xml = http_get(self.session, url, timeout)
                if not xml:
                    logger.warning("RSS 源抓取为空 name=%s url=%s", source, url)
                    continue
                parsed = feedparser.parse(xml)
                for entry in getattr(parsed, "entries", []) or []:
                    if max_items is not None and len(items) >= max_items:
                        break
                    it = self._entry_to_item(entry, source)
                    if not it:
                        continue
                    key = self._dedup_key(it)
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append(it)
            except Exception as exc:  # noqa: BLE001
                # 单个 Feed 失败隔离：记录数据源名 + Feed 地址 + 原因，继续下一个
                logger.error(
                    "RSS 源采集失败 name=%s url=%s err=%s",
                    source, url, f"{type(exc).__name__}: {exc}",
                )
                continue
        return items
