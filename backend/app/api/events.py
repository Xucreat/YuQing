"""Event 聚合接口（Phase 3C-0 / MVP）。

路由：
  POST  /events/aggregate  手动触发聚合
  GET   /events            列表分页
  GET   /events/{id}       详情 + 关联舆情
  GET   /events/{id}/opinions  关联舆情分页
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.core.task_manager import start_task
from app.db.session import SessionLocal, get_db
from app.models.event import Event
from app.models.event_action import EventAction
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.region import Region
from app.models.user import User
from app.models.propagation import PropagationNode
from app.models.alert import AlertRecord
from app.schemas.event import (
    EventActionCreate,
    EventActionOut,
    EventCreateResponse,
    EventDetailResponse,
    EventListResponse,
    EventOut,
    EventStatusUpdate,
    EventTaskResponse,
)
from app.schemas.opinion import OpinionListResponse, OpinionOut
from app.services.event.aggregator import EventAggregator
from app.services.event.risk_service import EventRiskService
from app.services.event.situation import EventSituationService
from app.services.audit_service import audit_write

events_router = APIRouter(
    tags=["events"],
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100

EVENT_STATUS_LABELS = {
    "active": "关注中",
    "verifying": "核查中",
    "processing": "处理中",
    "resolved": "已解决",
    "closed": "已关闭",
}
NEXT_EVENT_STATUS = {
    "active": "verifying",
    "verifying": "processing",
    "processing": "resolved",
    "resolved": "closed",
}


def _event_out(db: Session, event: Event) -> EventOut:
    region = db.get(Region, event.region_id) if event.region_id else None
    risk_score = EventRiskService.get_score(db, event.id)
    return EventOut(
        id=event.id,
        title=event.title,
        region_id=event.region_id,
        region_name=region.name if region else None,
        risk_level=EventRiskService.level_from_score(risk_score),
        risk_score=risk_score,
        topic_category=event.topic_category,
        heat_score=event.heat_score,
        trend=event.trend,
        opinion_count=event.opinion_count,
        status=event.status,
        first_time=event.first_time,
        last_time=event.last_time,
    )


def _event_action_out(action: EventAction, username: Optional[str]) -> EventActionOut:
    return EventActionOut(
        id=action.id,
        event_id=action.event_id,
        user_id=action.user_id,
        username=username,
        action_type=action.action_type,
        content=action.content,
        old_status=action.old_status,
        new_status=action.new_status,
        created_at=action.created_at,
    )


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
    "/{event_id}/situation",
    status_code=status.HTTP_200_OK,
)
def get_event_situation(
    event_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> dict:
    """Return a read-only event situation snapshot and risk explanation."""
    situation = EventSituationService().build(db, event_id)
    if situation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return situation


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
    region = db.get(Region, event.region_id) if event.region_id else None
    opinions = (
        db.query(Opinion)
        .join(EventOpinion, EventOpinion.opinion_id == Opinion.id)
        .where(EventOpinion.event_id == event_id)
        .order_by(Opinion.id.desc())
        .all()
    )
    opinion_outs = [OpinionOut.model_validate(o) for o in opinions]
    action_rows = (
        db.query(EventAction, User.username)
        .outerjoin(User, User.id == EventAction.user_id)
        .filter(EventAction.event_id == event_id)
        .order_by(EventAction.created_at.desc(), EventAction.id.desc())
        .all()
    )
    risk_score = EventRiskService.get_score(db, event.id)
    return EventDetailResponse(
        id=event.id,
        title=event.title,
        region_id=event.region_id,
        region_name=region.name if region else None,
        risk_level=EventRiskService.level_from_score(risk_score),
        risk_score=risk_score,
        topic_category=event.topic_category,
        heat_score=event.heat_score,
        trend=event.trend,
        opinion_count=event.opinion_count,
        status=event.status,
        first_time=event.first_time,
        last_time=event.last_time,
        description=event.description,
        keyword=event.keyword,
        opinions=opinion_outs,
        total_opinions=len(opinion_outs),
        actions=[_event_action_out(action, username) for action, username in action_rows],
    )


@events_router.patch(
    "/{event_id}/status",
    response_model=EventOut,
    status_code=status.HTTP_200_OK,
)
def update_event_status(
    event_id: int,
    body: EventStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:write")),
) -> EventOut:
    """Advance an event's manual handling state or return it to active."""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    old_status = event.status
    new_status = body.status
    if new_status == old_status:
        return _event_out(db, event)
    if new_status != "active" and NEXT_EVENT_STATUS.get(old_status) != new_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid event status transition: {old_status} -> {new_status}",
        )

    content = (
        f"事件状态由{EVENT_STATUS_LABELS[old_status]}"
        f"变更为{EVENT_STATUS_LABELS[new_status]}"
    )
    with audit_write(
        db,
        action="EVENT_STATUS_CHANGE",
        operator=current_user,
        request=request,
        resource_type="event",
        resource_id=str(event_id),
        details={"old_status": old_status, "new_status": new_status},
    ):
        event.status = new_status
        db.add(
            EventAction(
                event_id=event.id,
                user_id=current_user.id,
                action_type="status_change",
                content=content,
                old_status=old_status,
                new_status=new_status,
            )
        )
        db.commit()
        db.refresh(event)
    return _event_out(db, event)


@events_router.post(
    "/{event_id}/actions",
    response_model=EventActionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_event_action(
    event_id: int,
    body: EventActionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("events:write")),
) -> EventActionOut:
    """Add a manual note without changing event risk or handling state."""
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    action = EventAction(
        event_id=event.id,
        user_id=current_user.id,
        action_type="note",
        content=body.content,
    )
    with audit_write(
        db,
        action="EVENT_NOTE_CREATE",
        operator=current_user,
        request=request,
        resource_type="event",
        resource_id=str(event_id),
        details={"action_type": "note"},
    ):
        db.add(action)
        db.commit()
        db.refresh(action)
    return _event_action_out(action, current_user.username)


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
    region_id: Optional[int] = Query(None, ge=1, description="按影响地区 ID 筛选"),
    risk_level: Optional[Literal["low", "medium", "high"]] = Query(
        None, description="风险等级筛选：low=低 / medium=中 / high=高"
    ),
    topic_category: Optional[
        Literal[
            "livelihood", "traffic", "education", "healthcare", "environment",
            "safety", "market", "gov_service", "social_security",
            "public_emergency", "other",
        ]
    ] = Query(None, description="按事件主题筛选"),
    event_status: Optional[
        Literal["active", "verifying", "processing", "resolved", "closed"]
    ] = Query(None, alias="status", description="按事件处置状态筛选"),
    trend: Optional[Literal["rising", "stable", "falling", "unknown"]] = Query(
        None, description="趋势筛选：rising=升温 / stable=稳定 / falling=降温 / unknown=数据不足"
    ),
    heat_min: Optional[int] = Query(None, ge=0, le=100),
    heat_max: Optional[int] = Query(None, ge=0, le=100),
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> EventListResponse:
    """Event 列表，支持事件属性筛选并按风险、热度、更新时间降序排列。"""
    q = db.query(Event)
    if title:
        # ilike 使用绑定参数，模式字符串经占位符传递，无注入风险
        q = q.filter(Event.title.ilike(f"%{title.strip()}%"))
    if region_id is not None:
        q = q.filter(Event.region_id == region_id)
    risk_score_expr = EventRiskService.score_expression()
    if risk_level:
        q = q.filter(
            EventRiskService.level_expression(risk_score_expr) == risk_level
        )
    if topic_category:
        q = q.filter(Event.topic_category == topic_category)
    if event_status:
        q = q.filter(Event.status == event_status)
    if trend:
        q = q.filter(Event.trend == trend)
    if heat_min is not None:
        q = q.filter(Event.heat_score >= heat_min)
    if heat_max is not None:
        q = q.filter(Event.heat_score <= heat_max)
    total = q.count()
    rows = (
        q.add_columns(risk_score_expr.label("computed_risk_score"))
        .order_by(
            risk_score_expr.desc(),
            Event.heat_score.desc(),
            Event.last_time.desc().nullslast(),
        )
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    region_ids = {
        event.region_id
        for event, _computed_score in rows
        if event.region_id is not None
    }
    region_names = {
        region.id: region.name
        for region in db.query(Region).filter(Region.id.in_(region_ids)).all()
    } if region_ids else {}
    items = [
        EventOut(
            id=e.id,
            title=e.title,
            region_id=e.region_id,
            region_name=region_names.get(e.region_id),
            risk_level=EventRiskService.level_from_score(computed_score),
            risk_score=EventRiskService.clamp_score(computed_score),
            topic_category=e.topic_category,
            heat_score=e.heat_score,
            trend=e.trend,
            opinion_count=e.opinion_count,
            status=e.status,
            first_time=e.first_time,
            last_time=e.last_time,
        )
        for e, computed_score in rows
    ]
    return EventListResponse(items=items, total=total, page=page, size=size)
