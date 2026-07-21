"""Collector 采集层。

导出各采集器，便于统一 import：
  - BaseCollector        采集器抽象基类
  - MockCollector        演示数据（离线 / 测试默认 / 兜底）
  - RSSCollector         RSS 可扩展接口（未配置则不联网）
  - GovernmentCollector  大厂县政府网站采集（Phase 3B）
  - BaiduNewsCollector  百度新闻（Phase 1 接通）
  - HebeiNewsCollector  河北新闻网（Phase 1 接通）
  - XinhuaCollector     新华网（Phase 2）
  - PeopleCollector     人民网（Phase 2）
  - ChinanewsCollector  中国新闻网 RSS（Phase 2）
  - HebeiDailyCollector 河北日报数字报（Phase 2）
  - ChangchengCollector 长城网（Phase 2）
  - HebeiGovCollector   河北省人民政府（Phase 2）

微博（WeiboCollector）已从运行流程移除，仅保留类以兼容，不再导出。
"""
from app.collectors.base import BaseCollector
from app.collectors.government_collector import GovernmentCollector
from app.collectors.mock_collector import MockCollector
from app.collectors.rss_collector import RSSCollector
from app.collectors.baidu_news_collector import BaiduNewsCollector
from app.collectors.hebei_news_collector import HebeiNewsCollector
from app.collectors.xinhua_collector import XinhuaCollector
from app.collectors.people_collector import PeopleCollector
from app.collectors.chinanews_collector import ChinanewsCollector
from app.collectors.hebei_daily_collector import HebeiDailyCollector
from app.collectors.changcheng_collector import ChangchengCollector
from app.collectors.hebei_gov_collector import HebeiGovCollector

__all__ = [
    "BaseCollector",
    "MockCollector",
    "RSSCollector",
    "GovernmentCollector",
    "BaiduNewsCollector",
    "HebeiNewsCollector",
    "XinhuaCollector",
    "PeopleCollector",
    "ChinanewsCollector",
    "HebeiDailyCollector",
    "ChangchengCollector",
    "HebeiGovCollector",
]
