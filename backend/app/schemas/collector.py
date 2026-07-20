"""Collector 接口响应模型（Phase 3A / 3B）。

仅做序列化，不直接返回 ORM / dict。
- CollectorRunResponse：单次采集运行结果（created / analyzed / failed）。
- CollectorStatusResponse：采集状态（内存，重启丢失）。

Phase 3B：新增 collector_type 表示**采集方式**（government / mock），
与数据库 Opinion.source（新闻来源，如「大厂县政府网站」）区分，勿混淆。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CollectorRunResponse(BaseModel):
    """采集运行结果。"""

    success: bool = True
    collector_type: str = ""  # 采集方式：government | mock（非数据来源）
    created: int = 0       # 本次新增 Opinion 数
    analyzed: int = 0       # AI 分析成功（completed）数
    failed: int = 0         # 失败数 = created - analyzed（记录保留，状态 failed）
    message: str = ""


class CollectorStatusResponse(BaseModel):
    """采集状态（模块级内存，重启丢失；Phase 3A 临时实现）。"""

    last_run: Optional[datetime] = None
    total_collected: int = 0
    collector_type: Optional[str] = None  # 最近一次采集方式（government / mock）
