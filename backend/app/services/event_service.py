"""[DEPRECATED] 事件聚合服务（Phase 2 占位实现）。

WARNING: 已废弃（Phase 3C-0）。保留此文件仅为兼容，请勿在新代码中调用。
新的 Event 聚合逻辑统一位于 app/services/event/aggregator.py
（EventAggregator：规则聚合，激活既有 events/event_opinions 表）。

原设计：
  - events 表：事件标题/描述/关键词/风险等级/舆情数/首末时间
  - event_opinions 表：事件 <-> 多条舆情 的关联
"""
from typing import Any


class EventService:
    def aggregate(self, opinions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # DEPRECATED: 使用 app.services.event.aggregator.EventAggregator 代替。
        return []
