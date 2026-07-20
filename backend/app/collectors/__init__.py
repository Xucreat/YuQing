"""Collector 采集层。

导出各采集器，便于统一 import：
  - BaseCollector        采集器抽象基类
  - MockCollector        演示数据（离线 / 测试默认 / 兜底）
  - RSSCollector         RSS 可扩展接口（未配置则不联网）
  - GovernmentCollector  大厂县政府网站采集（Phase 3B）

三者均可独立使用。
"""
from app.collectors.base import BaseCollector
from app.collectors.government_collector import GovernmentCollector
from app.collectors.mock_collector import MockCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.baidu_news_collector import BaiduNewsCollector
from app.collectors.weibo_collector import WeiboCollector
from app.collectors.hebei_news_collector import HebeiNewsCollector

__all__ = [
    "BaseCollector",
    "MockCollector",
    "RSSCollector",
    "GovernmentCollector",
    "BaiduNewsCollector",
    "WeiboCollector",
    "HebeiNewsCollector",
]
