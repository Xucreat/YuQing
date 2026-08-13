from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


EventStatus = Literal["active", "verifying", "processing", "resolved", "closed", "deprecated"]


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


# --------------------------------------------------------------------------- #
# Phase 2-E-2：事件运营闭环增强（statistics / alerts，均为只读派生，不落库）   #
# --------------------------------------------------------------------------- #
class EventStatistics(BaseModel):
    """事件运营统计快照（详情接口内即时计算，不持久化）。

    - opinion_count：关联舆情数（取实际加载的关联舆情条数）
    - source_count：COUNT(DISTINCT Opinion.source)
    - latest_time：MAX(Opinion.created_at)
    - risk_distribution：按 Opinion.risk_score 分桶（复用 EventRiskService.level_from_score
      的同一阈值：>=70 high / >=40 medium / 其余 low），与线上风险模型一致。
    """

    opinion_count: int = 0
    source_count: int = 0
    latest_time: Optional[datetime] = None
    risk_distribution: dict = Field(
        default_factory=lambda: {"high": 0, "medium": 0, "low": 0}
    )


class EventAlertOut(BaseModel):
    """事件关联告警（反查 alert_records.event_id）。title 映射 opinion_title
    （AlertRecord 无 title 列，仅有 opinion_title / event_title）。"""

    id: int
    title: str
    risk_level: str
    formal_risk_score: Optional[int] = None
    formal_risk_level: Optional[str] = None
    linked_opinion_current_risk: Optional[dict] = None
    status: str
    created_at: datetime


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
    formal_risk_score: Optional[int] = None
    formal_risk_level: Optional[str] = None
    linked_opinion_current_risk: Optional[dict] = None
    # Read-only event-level reference score; the existing risk_score remains
    # unchanged for compatibility with current filters and alert behavior.
    risk_shadow_score: Optional[int] = None
    risk_shadow_level: Optional[str] = None
    risk_shadow_version: Optional[str] = None
    topic_category: Optional[str] = None
    heat_score: int = 0
    trend: str = "unknown"
    opinion_count: int
    # Phase 2-E-2：来源数量（列表批量计算，详情来自 statistics）；可空保证兼容。
    source_count: Optional[int] = None
    status: str = "active"
    first_time: Optional[datetime] = None
    last_time: Optional[datetime] = None
    confirmation_source: Optional[str] = None
    confirmation_version: Optional[str] = None
    rule_risk_snapshot: Optional[dict] = None
    ai_risk_snapshot: Optional[dict] = None
    review_reason: Optional[str] = None
    confirmed_by: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    origin_review_id: Optional[int] = None
    origin_ai_result_id: Optional[int] = None


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
    # Phase 2-E-2：运营统计 + 关联告警（只读派生，additive，向后兼容）
    statistics: Optional[EventStatistics] = None
    alerts: List[EventAlertOut] = Field(default_factory=list)
