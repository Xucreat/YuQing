from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TopK = Literal[10, 20, 30, 40, 50]
RegionMode = Literal[0, 1, 2]

class AnspireSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=64)
    top_k: TopK = 10
    insite: str = Field(default="", max_length=2048)
    from_time: datetime | None = None
    to_time: datetime | None = None
    region_mode: RegionMode = 0

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query is required")
        return value

    @field_validator("insite")
    @classmethod
    def clean_insite(cls, value: str) -> str:
        sites = [part.strip() for part in value.split(",") if part.strip()]
        if len(sites) > 20:
            raise ValueError("insite supports at most 20 sites")
        return ",".join(sites)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.from_time and self.to_time and self.from_time > self.to_time:
            raise ValueError("from_time must not be later than to_time")
        return self

class AnspireResultOut(BaseModel):
    result_index: int
    title: str = ""
    url: str = ""
    snippet: str = ""
    summary: str = ""
    source_name: str = ""
    publish_time: datetime | None = None
    provider: str = "anspire"
    provider_score: float | None = None
    raw_json: dict[str, Any] | None = None

class AnspireSessionOut(BaseModel):
    id: int
    provider: str
    provider_request_id: str | None = None
    provider_options: dict[str, Any] | None = None
    query: str
    result_count: int
    status: Literal["success", "failed"]
    error_message: str | None = None
    created_by: int | None = None
    created_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    model_config = ConfigDict(from_attributes=True)

class AnspireSearchResponse(BaseModel):
    session: AnspireSessionOut
    items: list[AnspireResultOut]
    total: int
    query: str

class AnspireSaveLeadRequest(BaseModel):
    session_id: int = Field(..., ge=1)
    result_index: int = Field(..., ge=0)

class AnspireOptionsResponse(BaseModel):
    top_k: list[int]
    region_mode: list[int]
    search_type: str
    max_query_length: int
    max_insite_sites: int

class AnspireSessionListResponse(BaseModel):
    items: list[AnspireSessionOut]
    total: int
    page: int
    size: int
