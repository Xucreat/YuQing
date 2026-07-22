"""Event 聚合接口（Phase 3C-0 / MVP）。

路由：
  POST  /events/aggregate  手动触发聚合
  GET   /events            列表分页
  GET   /events/{id}       详情 + 关联舆情
  GET   /events/{id}/opinions  关联舆情分页
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.core.task_manager import start_task
from app.db.session import SessionLocal, get_db
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.user import User
from app.models.propagation import PropagationNode
from app.models.alert import AlertRecord
from app.schemas.event import (
    EventCreateResponse,
    EventDetailResponse,
    EventListResponse,
    EventOut,
    EventTaskResponse,
)
from app.schemas.opinion import OpinionListResponse, OpinionOut
from app.services.event.aggregator import EventAggregator

events_router = APIRouter(
    tags=["events"],
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100


def _run_aggregate_task(task, session_factory, rebuild: bool) -> dict:
    """后台任务体：执行聚合（增量或全量 rebuild）。"""
    task.step = "聚合计算中…"
    db = session_factory()
    try:
        if rebuild:
            result = EventAggregator().aggregate(db, rebuild=True)
        else:
            result = EventAggregator().aggregate(db, incremental=True)
        task.step = "重建传播树…"
        return result
    finally:
        db.close()


@events_router.post(
    "/aggregate",
    response_model=EventTaskResponse,
    status_code=status.HTTP_200_OK,
)
def aggregate_events(
    rebuild: bool = Query(False, description="true=全量重建活跃事件关联；默认增量聚合"),
    _: User = Depends(require_permission("events:write")),
) -> EventTaskResponse:
    """手动触发一次 Event 聚合（后台异步执行，默认增量）。

    接口立即返回 task_id，前端通过 ``GET /api/tasks/{task_id}`` 轮询进度与结果。
    默认走增量路径（仅处理未关联舆情，存量不变时秒回）；传 ``?rebuild=true``
    执行全量重聚类（重建活跃事件关联）。
    """
    task_id = start_task("aggregate", _run_aggregate_task, SessionLocal, rebuild)
    return EventTaskResponse(success=True, task_id=task_id, message="聚合中")


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


@events_router.delete(
    "/{event_id}",
    status_code=status.HTTP_200_OK,
)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("events:write")),
) -> dict:
    """Delete an event and all its related records."""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    # Nullify parent refs among propagation nodes for this event
    db.query(PropagationNode).where(
        PropagationNode.event_id == event_id
    ).update({"parent_id": None}, synchronize_session=False)
    db.query(PropagationNode).where(PropagationNode.event_id == event_id).delete()

    # Delete event-opinion links
    db.query(EventOpinion).where(EventOpinion.event_id == event_id).delete()

    # Nullify alert record references to this event
    db.query(AlertRecord).where(AlertRecord.event_id == event_id).update(
        {"event_id": None, "event_title": ""}, synchronize_session=False
    )

    db.delete(event)
    db.commit()
    return {"detail": "Event deleted", "id": event_id}

@events_router.get(
    "",
    response_model=EventListResponse,
    status_code=status.HTTP_200_OK,
)
def list_events(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    title: Optional[str] = Query(None, description="按事件标题模糊搜索（不区分大小写）"),
    risk_level: Optional[Literal["low", "medium", "high"]] = Query(
        None, description="风险等级筛选：low=低 / medium=中 / high=高"
    ),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> EventListResponse:
    """Event 列表（分页，按 id DESC，支持标题模糊搜索 + 风险等级筛选）。"""
    q = db.query(Event)
    if title:
        # ilike 使用绑定参数，模式字符串经占位符传递，无注入风险
        q = q.filter(Event.title.ilike(f"%{title.strip()}%"))
    if risk_level:
        q = q.filter(Event.risk_level == risk_level)
    total = q.count()
    rows = (
        q.order_by(Event.id.desc())
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
