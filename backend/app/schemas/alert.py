"""Alert schemas (Pydantic v2)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator

class AlertRuleCreate(BaseModel):
    name: str
    description: str = ""
    risk_threshold: int = 70
    keywords: str = ""
    sources: str = ""
    risk_level: str = "high"
    enabled: bool = True

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    risk_threshold: Optional[int] = None
    keywords: Optional[str] = None
    sources: Optional[str] = None
    risk_level: Optional[str] = None
    enabled: Optional[bool] = None

class AlertRuleOut(BaseModel):
    id: int
    name: str
    description: str
    risk_threshold: int
    keywords: str
    sources: str
    risk_level: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AlertRuleListResponse(BaseModel):
    items: List[AlertRuleOut]
    total: int
    page: int
    size: int

class AlertRecordOut(BaseModel):
    id: int
    rule_id: int
    rule_name: str
    risk_level: str
    opinion_id: Optional[int] = None
    opinion_title: str
    event_id: Optional[int] = None
    event_title: str
    trigger_reason: str
    handled: bool
    # Phase 2-B.1 告警处置闭环字段（旧数据 status 由迁移回填，其余可空）
    status: str = "pending"
    handled_by: Optional[int] = None
    handled_at: Optional[datetime] = None
    handle_note: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Phase 2-B.1：处置请求体。无 body 调用（旧兼容）等价 status='resolved', note=''。
_ALLOWED_HANDLE_STATUS = {"pending", "processing", "resolved", "ignored", "false_positive"}


class AlertHandleRequest(BaseModel):
    status: str = "resolved"
    note: str = ""

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in _ALLOWED_HANDLE_STATUS:
            raise ValueError(
                f"status must be one of {sorted(_ALLOWED_HANDLE_STATUS)}"
            )
        return v

class AlertRecordListResponse(BaseModel):
    items: List[AlertRecordOut]
    total: int
    page: int
    size: int

class AlertEvaluateResponse(BaseModel):
    success: bool = True
    total_checked: int = 0
    alerts_created: int = 0
