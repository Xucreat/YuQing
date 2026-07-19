from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class EventCreateResponse(BaseModel):
    success: bool = True
    created: int = 0
    updated: int = 0
    linked: int = 0


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
