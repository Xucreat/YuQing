from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_run import ForeignEventRun
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.models.user import User
from app.services.audit_service import audit_write
from app.services.foreign_event_service import (
    ForeignEventService,
    serialize_action,
    serialize_candidate,
    serialize_event,
    serialize_run,
)
from app.services.foreign_content_sanitizer import sanitize_foreign_html
from app.services.current_risk import current_risk_payload
from app.services.foreign_event_auto_aggregation_service import (
    ForeignEventAutoAggregationService,
    serialize_auto_result,
)


foreign_events_router = APIRouter(
    prefix="/foreign/events",
    tags=["foreign-events"],
    dependencies=[Depends(get_current_user)],
)

foreign_event_meta_router = APIRouter(
    prefix="/foreign",
    tags=["foreign-events"],
    dependencies=[Depends(get_current_user)],
)


@foreign_events_router.get("/auto-aggregate/status")
def foreign_event_auto_aggregation_status(
    _: User = Depends(require_permission("foreign:events:read")),
):
    return {
        "enabled": bool(settings.foreign_event_auto_aggregation_enabled),
        "confidence_threshold": settings.foreign_event_auto_confidence_threshold,
        "time_window_hours": settings.foreign_event_auto_time_window_hours,
        "scheduler_registered": False,
        "cross_language_enabled": bool(settings.foreign_event_cross_language_enabled),
        "cross_language_auto_confirm_enabled": False,
        "cross_language_auto_confirm_supported": False,
    }

MAX_SIZE = 100


def _foreign_current_risk_summary(
    db: Session,
    opinions: list[ForeignOpinion],
) -> dict[str, Any] | None:
    if not opinions:
        return None
    opinion_ids = [item.id for item in opinions]
    rule_rows = db.scalars(
        select(ForeignRiskResult)
        .where(
            ForeignRiskResult.foreign_opinion_id.in_(opinion_ids),
            ForeignRiskResult.is_current.is_(True),
        )
        .order_by(ForeignRiskResult.id.desc())
    ).all()
    rule_by_opinion = {
        row.foreign_opinion_id: row
        for row in rule_rows
    }

    def score(item: ForeignOpinion) -> int:
        if (
            (item.current_risk_source or "rule") == "rule"
            and item.current_risk_updated_at is None
        ):
            return int((rule_by_opinion.get(item.id).risk_score or 0) if rule_by_opinion.get(item.id) else 0)
        return int(item.current_risk_score or 0)

    row = max(opinions, key=score)
    if (
        (row.current_risk_source or "rule") == "rule"
        and row.current_risk_updated_at is None
        and row.id in rule_by_opinion
    ):
        rule = rule_by_opinion[row.id]
        current = {
            "source": "rule",
            "risk_score": rule.risk_score,
            "risk_level": rule.risk_level,
        }
    else:
        current = current_risk_payload(row) or {}
    return {
        "source": current.get("source", "rule"),
        "risk_score": current.get("risk_score"),
        "risk_level": current.get("risk_level") or "unknown",
        "opinion_id": row.id,
        "opinion_count": len(opinions),
    }


def _attach_foreign_event_current_risk(
    db: Session,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    event_ids = [item["id"] for item in items if item.get("id") is not None]
    if not event_ids:
        return items
    rows = db.execute(
        select(ForeignEventOpinion.foreign_event_id, ForeignOpinion)
        .join(ForeignOpinion, ForeignOpinion.id == ForeignEventOpinion.foreign_opinion_id)
        .where(ForeignEventOpinion.foreign_event_id.in_(event_ids))
    ).all()
    grouped: dict[int, list[ForeignOpinion]] = {event_id: [] for event_id in event_ids}
    for event_id, opinion in rows:
        grouped.setdefault(event_id, []).append(opinion)
    for item in items:
        item["linked_opinion_current_risk"] = _foreign_current_risk_summary(
            db,
            grouped.get(item["id"], [])
        )
    return items


class CandidateActionPayload(BaseModel):
    reason: str = Field(default="", max_length=2000)
    request_id: str | None = Field(default=None, max_length=128)


class MergePayload(BaseModel):
    target_event_id: int = Field(ge=1)
    reason: str = Field(default="", max_length=2000)
    request_id: str | None = Field(default=None, max_length=128)


class SplitPayload(BaseModel):
    opinion_ids: list[int] = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=2000)
    request_id: str | None = Field(default=None, max_length=128)


class StatusPayload(BaseModel):
    status: str = Field(pattern="^(confirmed|monitoring|resolved|archived)$")
    reason: str = Field(default="", max_length=2000)
    request_id: str | None = Field(default=None, max_length=128)


class RebuildPayload(BaseModel):
    dry_run: bool = True
    opinion_ids: list[int] | None = Field(default=None, max_length=500)
    cross_language: bool = False


def _parse_date(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be YYYY-MM-DD") from exc


def _foreign_event_or_404(db: Session, event_id: int) -> ForeignEvent:
    event = db.get(ForeignEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Foreign event not found")
    return event


def _foreign_candidate_or_404(db: Session, candidate_id: int) -> ForeignEventCandidate:
    candidate = db.get(ForeignEventCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Foreign event candidate not found")
    return candidate


def _event_with_counts(db: Session, event: ForeignEvent) -> dict[str, Any]:
    payload = serialize_event(event)
    payload["opinions"] = []
    return payload


@foreign_events_router.get("")
def list_foreign_events(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    status: str | None = None,
    language: str | None = None,
    source: str | None = None,
    risk_level: str | None = None,
    q: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    min_opinion_count: int | None = Query(None, ge=0),
    first_seen_from: str | None = None,
    first_seen_to: str | None = None,
    last_seen_from: str | None = None,
    last_seen_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:events:read")),
):
    stmt = select(ForeignEvent)
    if status:
        stmt = stmt.where(ForeignEvent.event_status == status)
    if language:
        stmt = stmt.where(ForeignEvent.language == language)
    if risk_level:
        stmt = stmt.where(ForeignEvent.risk_level == risk_level)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                ForeignEvent.title.ilike(like),
                ForeignEvent.summary.ilike(like),
            )
        )
    if source:
        stmt = stmt.join(
            ForeignEventOpinion,
            ForeignEventOpinion.foreign_event_id == ForeignEvent.id,
        ).join(
            ForeignOpinion,
            ForeignOpinion.id == ForeignEventOpinion.foreign_opinion_id,
        ).where(ForeignOpinion.source_name_snapshot == source).distinct()
    if min_confidence is not None:
        stmt = stmt.where(ForeignEvent.confidence >= min_confidence)
    if min_opinion_count is not None:
        stmt = stmt.where(ForeignEvent.opinion_count >= min_opinion_count)
    first_from = _parse_date(first_seen_from, "first_seen_from")
    first_to = _parse_date(first_seen_to, "first_seen_to")
    last_from = _parse_date(last_seen_from, "last_seen_from")
    last_to = _parse_date(last_seen_to, "last_seen_to")
    if first_from:
        stmt = stmt.where(ForeignEvent.first_seen_at >= first_from)
    if first_to:
        stmt = stmt.where(ForeignEvent.first_seen_at < first_to.replace(hour=23, minute=59, second=59))
    if last_from:
        stmt = stmt.where(ForeignEvent.last_seen_at >= last_from)
    if last_to:
        stmt = stmt.where(ForeignEvent.last_seen_at < last_to.replace(hour=23, minute=59, second=59))
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignEvent.last_seen_at.desc().nullslast(), ForeignEvent.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    items = [serialize_event(row) for row in rows]
    return {
        "items": _attach_foreign_event_current_risk(db, items),
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_events_router.get("/candidates")
def list_foreign_event_candidates(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    status: str | None = None,
    language: str | None = None,
    min_confidence: float | None = Query(None, ge=0, le=1),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:events:candidates:read")),
):
    stmt = select(ForeignEventCandidate)
    if status:
        stmt = stmt.where(ForeignEventCandidate.candidate_status == status)
    if language:
        stmt = stmt.where(ForeignEventCandidate.language == language)
    if min_confidence is not None:
        stmt = stmt.where(ForeignEventCandidate.confidence >= min_confidence)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                ForeignEventCandidate.title.ilike(like),
                ForeignEventCandidate.summary.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(
            ForeignEventCandidate.candidate_status.asc(),
            ForeignEventCandidate.confidence.desc(),
            ForeignEventCandidate.id.desc(),
        )
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "items": [serialize_candidate(row) for row in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_events_router.get("/candidates/{candidate_id}")
def get_foreign_event_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:events:candidates:read")),
):
    candidate = _foreign_candidate_or_404(db, candidate_id)
    payload = serialize_candidate(candidate)
    opinion_ids = list((candidate.evidence_json or {}).get("opinion_ids", []))
    opinions = db.scalars(
        select(ForeignOpinion).where(ForeignOpinion.id.in_(opinion_ids))
    ).all() if opinion_ids else []
    payload["opinions"] = [
        {
            "id": opinion.id,
            "title": opinion.title,
            "source_name_snapshot": opinion.source_name_snapshot,
            "published_at": opinion.published_at.isoformat() if opinion.published_at else None,
            "url": opinion.url,
        }
        for opinion in opinions
    ]
    return payload


@foreign_events_router.get("/{event_id}/opinions")
def list_foreign_event_opinions(
    event_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:events:read")),
):
    _foreign_event_or_404(db, event_id)
    stmt = (
        select(ForeignEventOpinion, ForeignOpinion)
        .join(ForeignOpinion, ForeignOpinion.id == ForeignEventOpinion.foreign_opinion_id)
        .where(ForeignEventOpinion.foreign_event_id == event_id)
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(ForeignOpinion.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    current_by_opinion = {}
    for _, opinion in rows:
        current_by_opinion[opinion.id] = _foreign_current_risk_summary(db, [opinion])
    return {
        "items": [
            {
                "relation": {
                    "id": relation.id,
                    "relation_type": relation.relation_type,
                    "similarity_score": relation.similarity_score,
                    "matched_terms": relation.matched_terms or [],
                    "evidence_json": relation.evidence_json or {},
                },
                "opinion": {
                    "id": opinion.id,
                    "source_name_snapshot": opinion.source_name_snapshot,
                    "title": opinion.title,
                    "summary": sanitize_foreign_html(opinion.summary),
                    "content": sanitize_foreign_html(opinion.content),
                    "url": opinion.url,
                    "published_at": opinion.published_at.isoformat() if opinion.published_at else None,
                    "collected_at": opinion.collected_at.isoformat() if opinion.collected_at else None,
                    "current_risk": current_by_opinion.get(opinion.id),
                },
            }
            for relation, opinion in rows
        ],
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_events_router.get("/{event_id}")
def get_foreign_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:events:read")),
):
    event = _foreign_event_or_404(db, event_id)
    payload = serialize_event(event)
    links = db.execute(
        select(ForeignEventOpinion, ForeignOpinion)
        .join(ForeignOpinion, ForeignOpinion.id == ForeignEventOpinion.foreign_opinion_id)
        .where(ForeignEventOpinion.foreign_event_id == event.id)
        .order_by(ForeignOpinion.id.desc())
    ).all()
    payload["opinions"] = [
        {
            "id": opinion.id,
            "source_name_snapshot": opinion.source_name_snapshot,
            "title": opinion.title,
            "summary": sanitize_foreign_html(opinion.summary),
            "content": sanitize_foreign_html(opinion.content),
            "url": opinion.url,
            "published_at": opinion.published_at.isoformat() if opinion.published_at else None,
            "collected_at": opinion.collected_at.isoformat() if opinion.collected_at else None,
            "current_risk": current_risk_payload(opinion),
            "relation_type": relation.relation_type,
            "similarity_score": relation.similarity_score,
        }
        for relation, opinion in links
    ]
    payload["linked_opinion_current_risk"] = _foreign_current_risk_summary(
        db,
        [opinion for _, opinion in links]
    )
    opinion_ids = [item["id"] for item in payload["opinions"]]
    risk_rows = db.scalars(
        select(ForeignRiskResult).where(
            ForeignRiskResult.foreign_opinion_id.in_(opinion_ids),
            ForeignRiskResult.is_current.is_(True),
        )
    ).all() if opinion_ids else []
    payload["risk_results"] = [
        {
            "foreign_opinion_id": row.foreign_opinion_id,
            "risk_score": row.risk_score,
            "risk_level": row.risk_level,
            "risk_category": row.risk_category,
            "matched_terms": row.matched_terms or [],
            "analysis_status": row.analysis_status,
        }
        for row in risk_rows
    ]
    candidate = db.get(ForeignEventCandidate, event.origin_candidate_id) if event.origin_candidate_id else None
    payload["auto_aggregation"] = {
        "confirmation_source": event.confirmation_source,
        "candidate_id": candidate.id if candidate else None,
        "review_source": candidate.review_source if candidate else None,
        "confidence": candidate.confidence if candidate else event.confidence,
        "evidence": candidate.evidence_json if candidate else {},
    }
    action_rows = db.scalars(
        select(ForeignEventAction)
        .where(or_(ForeignEventAction.foreign_event_id == event.id, ForeignEventAction.target_event_id == event.id))
        .order_by(ForeignEventAction.created_at.asc(), ForeignEventAction.id.asc())
    ).all()
    payload["actions"] = [serialize_action(row) for row in action_rows]
    return payload


def _confirm_candidate(
    candidate_id: int,
    body: CandidateActionPayload,
    request: Request,
    current_user: User,
    db: Session,
):
    _foreign_candidate_or_404(db, candidate_id)
    try:
        with audit_write(
            db,
            action="FOREIGN_EVENT_CANDIDATE_CONFIRM",
            operator=current_user,
            request=request,
            resource_type="foreign_event_candidate",
            resource_id=str(candidate_id),
            details={"reason": body.reason},
        ):
            event = ForeignEventService().confirm_candidate(
                db,
                candidate_id,
                user_id=current_user.id,
                reason=body.reason,
                request_id=body.request_id,
            )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_event(event)


@foreign_events_router.post("/candidates/{candidate_id}/confirm")
def confirm_foreign_candidate(
    candidate_id: int,
    body: CandidateActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:confirm")),
    db: Session = Depends(get_db),
):
    return _confirm_candidate(candidate_id, body, request, current_user, db)


@foreign_events_router.post("/{event_id}/confirm")
def confirm_foreign_candidate_legacy_path(
    event_id: int,
    body: CandidateActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:confirm")),
    db: Session = Depends(get_db),
):
    return _confirm_candidate(event_id, body, request, current_user, db)


def _reject_candidate(
    candidate_id: int,
    body: CandidateActionPayload,
    request: Request,
    current_user: User,
    db: Session,
):
    _foreign_candidate_or_404(db, candidate_id)
    try:
        with audit_write(
            db,
            action="FOREIGN_EVENT_CANDIDATE_REJECT",
            operator=current_user,
            request=request,
            resource_type="foreign_event_candidate",
            resource_id=str(candidate_id),
            details={"reason": body.reason},
        ):
            candidate = ForeignEventService().reject_candidate(
                db,
                candidate_id,
                user_id=current_user.id,
                reason=body.reason,
                request_id=body.request_id,
            )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_candidate(candidate)


@foreign_events_router.post("/candidates/{candidate_id}/reject")
def reject_foreign_candidate(
    candidate_id: int,
    body: CandidateActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:confirm")),
    db: Session = Depends(get_db),
):
    return _reject_candidate(candidate_id, body, request, current_user, db)


@foreign_events_router.post("/{event_id}/reject")
def reject_foreign_candidate_legacy_path(
    event_id: int,
    body: CandidateActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:confirm")),
    db: Session = Depends(get_db),
):
    return _reject_candidate(event_id, body, request, current_user, db)


@foreign_events_router.post("/{event_id}/merge")
def merge_foreign_events(
    event_id: int,
    body: MergePayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:merge")),
    db: Session = Depends(get_db),
):
    try:
        with audit_write(
            db,
            action="FOREIGN_EVENT_MERGE",
            operator=current_user,
            request=request,
            resource_type="foreign_event",
            resource_id=str(event_id),
            details={"target_event_id": body.target_event_id, "reason": body.reason},
        ):
            event = ForeignEventService().merge_events(
                db,
                event_id,
                body.target_event_id,
                user_id=current_user.id,
                reason=body.reason,
                request_id=body.request_id,
            )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_event(event)


@foreign_events_router.post("/{event_id}/split")
def split_foreign_event(
    event_id: int,
    body: SplitPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:split")),
    db: Session = Depends(get_db),
):
    try:
        with audit_write(
            db,
            action="FOREIGN_EVENT_SPLIT",
            operator=current_user,
            request=request,
            resource_type="foreign_event",
            resource_id=str(event_id),
            details={"opinion_ids": body.opinion_ids, "reason": body.reason},
        ):
            event = ForeignEventService().split_event(
                db,
                event_id,
                body.opinion_ids,
                user_id=current_user.id,
                reason=body.reason,
                request_id=body.request_id,
            )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_event(event)


@foreign_events_router.post("/{event_id}/status")
def update_foreign_event_status(
    event_id: int,
    body: StatusPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:status")),
    db: Session = Depends(get_db),
):
    try:
        with audit_write(
            db,
            action="FOREIGN_EVENT_STATUS_CHANGE",
            operator=current_user,
            request=request,
            resource_type="foreign_event",
            resource_id=str(event_id),
            details={"status": body.status, "reason": body.reason},
        ):
            event = ForeignEventService().update_status(
                db,
                event_id,
                status=body.status,
                user_id=current_user.id,
                reason=body.reason,
                request_id=body.request_id,
            )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_event(event)


@foreign_events_router.post("/{event_id}/close")
def close_foreign_event(
    event_id: int,
    body: CandidateActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:status")),
    db: Session = Depends(get_db),
):
    return update_foreign_event_status(
        event_id,
        StatusPayload(status="resolved", reason=body.reason, request_id=body.request_id),
        request,
        current_user,
        db,
    )


@foreign_events_router.post("/rebuild")
def rebuild_foreign_candidates(
    body: RebuildPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:rebuild")),
    db: Session = Depends(get_db),
):
    try:
        with audit_write(
            db,
            action="FOREIGN_EVENT_REBUILD",
            operator=current_user,
            request=request,
            resource_type="foreign_event_run",
            details={"dry_run": body.dry_run, "opinion_count": len(body.opinion_ids or [])},
        ) as audit:
            run, candidates, previews = ForeignEventService().rebuild_candidates(
                db,
                user_id=current_user.id,
                dry_run=body.dry_run,
                opinion_ids=body.opinion_ids,
                cross_language=body.cross_language,
            )
            audit["resource_id"] = str(run.id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "run": serialize_run(run),
        "items": [serialize_candidate(row) for row in candidates],
        "previews": previews,
    }


@foreign_events_router.post("/auto-aggregate")
def auto_aggregate_foreign_events(
    body: RebuildPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:events:auto-aggregate")),
    db: Session = Depends(get_db),
):
    if body.cross_language:
        raise HTTPException(
            status_code=409,
            detail="Cross-language automatic confirmation is not supported; use candidate rebuild for manual review",
        )
    try:
        with audit_write(
            db,
            action="FOREIGN_EVENT_AUTO_AGGREGATE",
            operator=current_user,
            request=request,
            resource_type="foreign_event_run",
            details={"dry_run": body.dry_run, "opinion_count": len(body.opinion_ids or [])},
        ) as audit:
            result = ForeignEventAutoAggregationService().aggregate(
                db,
                user_id=current_user.id,
                dry_run=body.dry_run,
                opinion_ids=body.opinion_ids,
            )
            audit["resource_id"] = str(result.run.id)
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return serialize_auto_result(result)


@foreign_event_meta_router.get("/event-runs")
def list_foreign_event_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:events:read")),
):
    stmt = select(ForeignEventRun).where(ForeignEventRun.scope == "foreign")
    if status:
        stmt = stmt.where(ForeignEventRun.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignEventRun.started_at.desc(), ForeignEventRun.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "items": [serialize_run(row) for row in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_event_meta_router.get("/event-actions")
def list_foreign_event_actions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    action_type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:events:read")),
):
    stmt = select(ForeignEventAction)
    if action_type:
        stmt = stmt.where(ForeignEventAction.action_type == action_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignEventAction.created_at.desc(), ForeignEventAction.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "items": [serialize_action(row) for row in rows],
        "total": total,
        "page": page,
        "size": size,
    }
