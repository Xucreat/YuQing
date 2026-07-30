from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


EventStatus = Literal["active", "verifying", "processing", "resolved", "closed"]


class EventStatusUpdate(BaseModel):
    status: EventStatus


class EventActionCreate(BaseModel):
    action_type: Literal["note"]
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        content = value.strip()
        if not content:
            raise ValueError("content must not be blank")
        return content


class EventActionOut(BaseModel):
    id: int
    event_id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action_type: str
    content: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    region_id: Optional[int] = None
    region_name: Optional[str] = None
    risk_level: str
    risk_score: int = 0
    topic_category: Optional[str] = None
    heat_score: int = 0
    trend: str = "unknown"
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
    actions: List[EventActionOut] = Field(default_factory=list)
