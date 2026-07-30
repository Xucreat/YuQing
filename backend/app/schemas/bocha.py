from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.opinion import OpinionOut

BochaLeadStatus = Literal["new", "confirmed", "rejected", "promoted"]


class BochaSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    freshness: str | None = Field(default=None, max_length=64)
    summary: bool = True
    count: int | None = Field(default=None, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query is required")
        return value


class BochaLeadOut(BaseModel):
    id: int
    query: str
    title: str
    url: str
    snippet: str
    summary: str
    source_name: str
    publish_time: datetime | None = None
    raw_json: dict[str, Any] | None = None
    status: BochaLeadStatus
    opinion_id: int | None = None
    created_by: int | None = None
    search_session_id: int | None = None
    result_index: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BochaLeadListResponse(BaseModel):
    items: list[BochaLeadOut]
    total: int
    page: int
    size: int


class BochaRejectRequest(BaseModel):
    reason: str = Field(default="", max_length=1000)


class BochaPromoteRequest(BaseModel):
    region_id: int = Field(..., ge=1)


class BochaPromoteResponse(BaseModel):
    lead: BochaLeadOut
    opinion: OpinionOut
    already_promoted: bool = False


class BochaSearchResultOut(BaseModel):
    result_index: int
    title: str
    url: str
    snippet: str = ""
    summary: str = ""
    source_name: str = ""
    publish_time: datetime | None = None


class BochaSearchSessionOut(BaseModel):
    id: int
    query: str
    freshness: str | None = None
    summary: bool
    count: int
    result_count: int
    status: Literal["success", "failed"]
    error_message: str | None = None
    created_by: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None

    model_config = ConfigDict(from_attributes=True)


class BochaSearchSessionListResponse(BaseModel):
    items: list[BochaSearchSessionOut]
    total: int
    page: int
    size: int


class BochaSearchResponse(BaseModel):
    session: BochaSearchSessionOut
    items: list[BochaSearchResultOut]
    total: int
    query: str


class BochaSaveLeadRequest(BaseModel):
    session_id: int = Field(..., ge=1)
    result_index: int = Field(..., ge=0)
