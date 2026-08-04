"""采集器抽象基类（Phase 2 细化）。

设计约束：
  - Collector 禁止直接操作数据库。
  - 流程：Collector.fetch() -> Service -> Database。
  - fetch() 返回标准化原始舆情列表（dict / Pydantic 模型）。
"""
from abc import ABC, abstractmethod
from typing import Any

from app.collectors.source_config import EMPTY_CONFIG, DataSourceConfig


class BaseCollector(ABC):
    """所有采集器的基类。"""

    source_name: str = "base"

    # 数据源采集参数（来自 data_sources.config_json，由 registry 装配时注入）。
    # 类级默认为空配置：未经 registry 直接实例化（测试 / 脚本）时，所有
    # 配置读取都会落到调用方 default，行为与配置化改造前完全一致。
    source_config: DataSourceConfig = EMPTY_CONFIG

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """拉取原始舆情数据，返回 dict 列表。子类必须实现。"""
        raise NotImplementedError
