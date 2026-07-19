"""RSS 采集器：从外部 RSS 源拉取舆情（Phase 3A：可扩展接口）。

设计约束（来自用户）：
- RSS_URLS 未配置或为空时：**不加载 feedparser，不执行网络请求**，直接返回 []。
- feedparser 采用**惰性导入**：仅当 feeds 非空时才 import，避免无谓依赖与网络副作用。
- 本阶段只完成「可扩展接口」，不实现真实爬虫逻辑（Scrapy/Playwright 等一律禁止）。
- 同样地仅返回标准化 dict，不写库（写库由 CollectorService 负责）。
"""
import os

from app.collectors.base import BaseCollector


def _parse_rss_urls_env() -> list[str]:
    """从环境变量 RSS_URLS（逗号分隔）读取 RSS 源；为空返回 []。"""
    raw = os.getenv("RSS_URLS", "") or ""
    return [u.strip() for u in raw.split(",") if u.strip()]


class RSSCollector(BaseCollector):
    source_name = "rss"

    def __init__(self, feeds: list[str] | None = None) -> None:
        # feeds 为空（None 或 []）-> 不加载 feedparser、不联网。
        self.feeds: list[str] = list(feeds) if feeds else _parse_rss_urls_env()

    def fetch(self) -> list[dict]:
        # 未配置 / 空源：直接返回空，避免任何 import 与网络动作。
        if not self.feeds:
            return []

        # 惰性导入：仅当确有源时才加载 feedparser。
        import feedparser  # noqa: WPS433  (lazy import by design)

        items: list[dict] = []
        for url in self.feeds:
            parsed = feedparser.parse(url)
            for entry in getattr(parsed, "entries", []) or []:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue
                items.append(
                    {
                        "title": title,
                        "content": (entry.get("summary") or entry.get("description") or "").strip(),
                        "source": "rss",
                        "url": (entry.get("link") or "").strip(),
                        # RSS 通常无精确发布时间，留给 CollectorService 兜底去重。
                        "publish_time": None,
                    }
                )
        return items
