"""采集器抽象基类（Phase 2 细化）。

设计约束：
  - Collector 禁止直接操作数据库。
  - 流程：Collector.fetch() -> Service -> Database。
  - fetch() 返回标准化原始舆情列表（dict / Pydantic 模型）。
"""
from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """所有采集器的基类。"""

    source_name: str = "base"

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """拉取原始舆情数据，返回 dict 列表。子类必须实现。"""
        raise NotImplementedError
