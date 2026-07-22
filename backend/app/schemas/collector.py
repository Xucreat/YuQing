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
    fetched_raw: int = 0   # 采集器实际抓取到的原始舆情条数（去重前）
    created: int = 0       # 本次新增 Opinion 数
    analyzed: int = 0       # AI 分析成功（completed）数
    failed: int = 0         # 失败数 = created - analyzed（记录保留，状态 failed）
    message: str = ""


class CollectorStatusResponse(BaseModel):
    """采集状态（模块级内存，重启丢失；Phase 3A 临时实现）。"""

    last_run: Optional[datetime] = None
    total_collected: int = 0
    collector_type: Optional[str] = None  # 最近一次采集方式（government / mock）


class CollectorTaskResponse(BaseModel):
    """采集任务已启动（后台异步执行）。

    success 表示「任务已成功入队」，不代表采集已完成；进度/结果通过
    GET /api/tasks/{task_id} 轮询获取。
    """

    success: bool = True
    task_id: str
    message: str = "采集中"
