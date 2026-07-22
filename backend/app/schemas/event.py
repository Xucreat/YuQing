from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class EventCreateResponse(BaseModel):
    success: bool = True
    created: int = 0
    updated: int = 0
    linked: int = 0
    incremental: bool = False


class EventTaskResponse(BaseModel):
    """聚合任务已启动（后台异步执行）。

    success 表示「任务已成功入队」，不代表聚合已完成；进度/结果通过
    GET /api/tasks/{task_id} 轮询获取。
    """

    success: bool = True
    task_id: str
    message: str = "聚合中"


class EventOut(BaseModel):
    id: int
    title: str
    risk_level: str
    opinion_count: int
    status: str = "active"
    first_time: Optional[datetime] = None
    last_time: Optional[datetime] = None


class EventListResponse(BaseModel):
    items: List[EventOut] = []
    total: int = 0
    page: int = 1
    size: int = 20


class EventDetailResponse(EventOut):
    description: str = ""
    keyword: str = ""
    opinions: List = []
    total_opinions: int = 0
