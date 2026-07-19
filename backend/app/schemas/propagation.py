"""Propagation schemas (Pydantic v2)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class PropagationNodeOut(BaseModel):
    id: int
    event_id: Optional[int] = None
    opinion_id: Optional[int] = None
    parent_id: Optional[int] = None
    source: str
    source_url: str
    title: str
    publish_time: Optional[datetime] = None
    risk_score: int
    sentiment: str
    keywords: str
    depth: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class PropagationLink(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source_id: int
    target_id: int
    source_name: str
    target_name: str


class SourceSummaryItem(BaseModel):
    source: str
    count: int

class PropagationGraphResponse(BaseModel):
    nodes: List[PropagationNodeOut]
    links: List[PropagationLink]
    event_id: Optional[int] = None
    event_title: str = ""
    total_opinions: int = 0
    source_summary: List[SourceSummaryItem] = []

class PropagationRebuildResponse(BaseModel):
    success: bool = True
    nodes_created: int = 0
