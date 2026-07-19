"""Event 聚合接口（Phase 3C-0 / MVP）。

路由：
  POST  /events/aggregate  手动触发聚合
  GET   /events            列表分页
  GET   /events/{id}       详情 + 关联舆情
  GET   /events/{id}/opinions  关联舆情分页
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.user import User
from app.schemas.event import (
    EventCreateResponse,
    EventDetailResponse,
    EventListResponse,
    EventOut,
)
from app.schemas.opinion import OpinionListResponse, OpinionOut
from app.services.event.aggregator import EventAggregator

events_router = APIRouter(
    tags=["events"],
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100


@events_router.post(
    "/aggregate",
    response_model=EventCreateResponse,
    status_code=status.HTTP_200_OK,
)
def aggregate_events(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> EventCreateResponse:
    """手动触发一次 Event 聚合。"""
    result = EventAggregator().aggregate(db)
    return EventCreateResponse(success=True, **result)


@events_router.get(
    "/{event_id}/opinions",
    response_model=OpinionListResponse,
    status_code=status.HTTP_200_OK,
)
def get_event_opinions(
    event_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> OpinionListResponse:
    """Event 关联舆情列表（分页）。"""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    base_q = (
        db.query(Opinion)
        .join(EventOpinion, EventOpinion.opinion_id == Opinion.id)
        .where(EventOpinion.event_id == event_id)
    )
    total = base_q.count()
    rows = base_q.order_by(Opinion.id.desc()).offset((page - 1) * size).limit(size).all()
    return OpinionListResponse(items=rows, total=total, page=page, size=size)


@events_router.get(
    "/{event_id}",
    response_model=EventDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> EventDetailResponse:
    """Event 详情 + 关联舆情列表。"""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    opinions = (
        db.query(Opinion)
        .join(EventOpinion, EventOpinion.opinion_id == Opinion.id)
        .where(EventOpinion.event_id == event_id)
        .order_by(Opinion.id.desc())
        .all()
    )
    opinion_outs = [OpinionOut.model_validate(o) for o in opinions]
    return EventDetailResponse(
        id=event.id,
        title=event.title,
        risk_level=event.risk_level,
        opinion_count=event.opinion_count,
        first_time=event.first_time,
        last_time=event.last_time,
        description=event.description,
        keyword=event.keyword,
        opinions=opinion_outs,
        total_opinions=len(opinion_outs),
    )


@events_router.get(
    "",
    response_model=EventListResponse,
    status_code=status.HTTP_200_OK,
)
def list_events(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> EventListResponse:
    """Event 列表（分页，按 id DESC）。"""
    total = db.query(Event).count()
    rows = (
        db.query(Event)
        .order_by(Event.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    items = [
        EventOut(
            id=e.id,
            title=e.title,
            risk_level=e.risk_level,
            opinion_count=e.opinion_count,
            status="active",
            first_time=e.first_time,
            last_time=e.last_time,
        )
        for e in rows
    ]
    return EventListResponse(items=items, total=total, page=page, size=size)
