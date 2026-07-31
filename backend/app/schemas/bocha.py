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
    provider: str = "bocha"
    query: str
    title: str
    url: str
    snippet: str
    summary: str
    source_name: str
    publish_time: datetime | None = None
    provider_score: float | None = None
    raw_json: dict[str, Any] | None = None
    status: BochaLeadStatus
    opinion_id: int | None = None
    created_by: int | None = None
    creator_name: str | None = None
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
    provider: str = "bocha"
    provider_request_id: str | None = None
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
    provider_options: dict[str, Any] | None = None

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


AI_FRESHNESS = Literal["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"]


class BochaAISearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    freshness: AI_FRESHNESS = "noLimit"
    include: str | None = Field(default=None, max_length=2048)
    count: int = Field(default=10, ge=1, le=50)
    answer: bool = True
    stream: bool = False

    @field_validator("query")
    @classmethod
    def validate_ai_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query is required")
        return value

    @field_validator("stream")
    @classmethod
    def validate_ai_stream(cls, value: bool) -> bool:
        if value:
            raise ValueError("streaming AI Search is not supported")
        return value


class BochaAISearchSessionOut(BaseModel):
    id: int
    provider: str
    query: str
    freshness: str
    include: str | None = None
    count: int
    answer: str
    answer_enabled: bool = True
    follow_up_questions: list[str] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
    modal_cards: list[dict[str, Any]] = Field(default_factory=list)
    conversation_id: str | None = None
    result_count: int
    status: Literal["success", "failed"]
    error_message: str | None = None
    created_by: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None

    model_config = ConfigDict(from_attributes=True)


class BochaAISearchResultOut(BaseModel):
    result_index: int
    title: str = ""
    url: str
    snippet: str = ""
    source_domain: str = ""
    source_type: str = "web"
    publish_time: Any = None
    citation_url: str = ""
    raw_json: dict[str, Any] | None = None


class BochaAISearchResponse(BaseModel):
    session: BochaAISearchSessionOut
    answer: str = ""
    follow_up_questions: list[str] = Field(default_factory=list)
    web_pages: list[BochaAISearchResultOut] = Field(default_factory=list)
    images: list[dict[str, Any]] = Field(default_factory=list)
    modal_cards: list[dict[str, Any]] = Field(default_factory=list)
    conversation_id: str | None = None
    total: int = 0
    raw_response: dict[str, Any] = Field(default_factory=dict)


class BochaAISaveLeadRequest(BaseModel):
    session_id: int = Field(..., ge=1)
    result_index: int = Field(..., ge=0)


class BochaAILeadOut(BaseModel):
    id: int
    session_id: int
    result_index: int
    query: str
    title: str
    url: str
    snippet: str
    source_domain: str
    source_type: str
    publish_time: datetime | None = None
    raw_json: dict[str, Any] | None = None
    created_by: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
