"""参数化「列表页 → 详情页」站点采集器（Phase 3：表驱动落地的关键）。

设计目标：新增一个政府网/新闻网只需在 data_sources 表插入一行配置
（class_path = GenericSiteCollector + config_json），**无需新建采集器类文件**。

config_json 约定（键均为可选，缺省走合理默认）：
  {
    "source_name": "石家庄市政府网",        # 来源显示名（覆盖类默认）
    "list_urls": ["http://www.sjz.gov.cn/..."],  # 列表/栏目页 URL（支持多页，含两级导航页）
    "link_rule": {                          # 列表页链接过滤
        "href_contains": ".html",           # 或 "href_regex": "(?i)\\.(html?|shtml|jhtml)$"
        "href_exclude": ["index.html"],     # 排除导航/栏目首页
        "title_blacklist": ["网站首页"],     # 排除链接文本命中这些词的噪声
        "max_links": 30                      # 单页最多取多少候选链接
    },
    "content_selectors": ["div.content", "div.TRS_Editor"],  # 正文容器（覆盖默认）
    "keywords": "河北,石家庄,..." ,          # 可选：覆盖全局关键词
    "max_articles": 10,
    "request_interval": 0.3,
    "timeout": 10
  }

scope_region_codes 不放在 config_json 中，而由 data_sources.scope_region_codes
列承载（registry 装配时注入到 collector.scope_region_codes）。

区域绑定：CollectorService 按 collector.scope_region_codes 写 Opinion.region_id。
"""
from __future__ import annotations

import logging
import re
from typing import Any, List, Optional

from bs4 import BeautifulSoup

from app.collectors.base_http import BaseHttpCollector
from app.collectors.common import extract_links, extract_publish_time

logger = logging.getLogger(__name__)


class GenericSiteCollector(BaseHttpCollector):
    """参数化「列表 → 详情」站点采集器。仅通过配置即可接入新站点。"""

    source_name = "generic_site"

    def __init__(self, config: Optional[dict] = None, **kwargs: Any) -> None:
        # 兼容 cls(**config_json) 与 cls(config=config_json) 两种调用方式
        cfg = dict(config or {})
        cfg.update(kwargs)
        super().__init__(cfg)

        list_urls = cfg.get("list_urls") or []
        if isinstance(list_urls, str):
            list_urls = [u.strip() for u in list_urls.split(",") if u.strip()]
        self.list_urls: List[str] = list(list_urls)

        self.link_rule: dict = cfg.get("link_rule") or {}
        self.content_selectors: List[str] = cfg.get("content_selectors") or self.CONTENT_SELECTORS
        self.min_title_len: int = int(self.link_rule.get("min_title_len", 6))

        if cfg.get("source_name"):
            self.source_name = cfg["source_name"]

        href_regex = self.link_rule.get("href_regex")
        self._href_regex = re.compile(href_regex) if href_regex else None
        self.max_links = self.link_rule.get("max_links")

    # ------------------------------------------------------------------
    # 采集流程
    # ------------------------------------------------------------------
    def _collect_links(self) -> List[dict]:
        """从所有列表页提取文章链接（title + 绝对 url），已按 url 去重。"""
        links: List[dict] = []
        seen: set = set()
        for base in self.list_urls:
            html = self._get(base)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            found = extract_links(
                soup,
                base,
                href_contains=self.link_rule.get("href_contains"),
                href_regex=self._href_regex,
                href_exclude=self.link_rule.get("href_exclude"),
                title_blacklist=self.link_rule.get("title_blacklist"),
                max_links=self.max_links,
            )
            for a in found:
                title = (a.get("title") or "").strip()
                if len(title) < self.min_title_len:
                    continue
                if a["url"] in seen:
                    continue
                seen.add(a["url"])
                links.append(a)
        return links

    def fetch(self, monitoring_keywords: Optional[List[str]] = None) -> List[dict[str, Any]]:
        """列表 → 详情正文 → 标准化 dict（关键词过滤 + 防御式跳过）。

        monitoring_keywords：来自 keywords 表的全局监测词；仅在未通过
        config_json 显式配置 keywords 时使用（逐源覆盖优先）。
        """
        results: List[dict[str, Any]] = []
        seen: set = set()
        # 逐源显式配置过 keywords（含空串=放行全部）→ 用 self.keywords；
        # 否则用全局监测词（来自 keywords 表）。
        effective_kw = (
            self.keywords
            if self.keywords_explicit
            else (monitoring_keywords or self.keywords)
        )
        for art in self._collect_links():
            if art["url"] in seen:
                continue
            seen.add(art["url"])
            if len(results) >= self.max_articles:
                break
            detail = self._get(art["url"])
            self.rate_limit()
            if not detail:
                continue  # 详情失败：跳过该条，保证入库正文非空
            dsoup = BeautifulSoup(detail, "html.parser")
            content = self.extract_content(dsoup, self.content_selectors)
            if not content:
                continue
            # 关键词过滤（national 源靠关键词命中本省舆情；空关键词放行全部）
            if not self.match(art["title"] + " " + content[:800], effective_kw):
                continue
            results.append(
                {
                    "title": art["title"],
                    "content": content,
                    "source": self.source_name,
                    "url": art["url"],
                    "publish_time": extract_publish_time(dsoup),
                }
            )
        return results
