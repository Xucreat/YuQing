from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.bocha_lead import BochaLead
from app.models.bocha_search_session import BochaSearchSession
from app.models.user import User
from app.schemas.bocha import (
    BochaLeadListResponse,
    BochaLeadOut,
    BochaLeadStatus,
    BochaSaveLeadRequest,
    BochaSearchRequest,
    BochaSearchResponse,
    BochaSearchResultOut,
    BochaSearchSessionListResponse,
)
from app.services.audit_service import audit_write
from app.services.bocha_search_service import BochaSearchError, BochaSearchService

bocha_router = APIRouter(
    prefix="/bocha",
    tags=["bocha"],
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100


def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be a valid ISO-8601 datetime",
        ) from exc
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _result_out(item: dict, index: int) -> BochaSearchResultOut:
    return BochaSearchResultOut(
        result_index=index,
        title=str(item.get("title") or ""),
        url=str(item.get("url") or ""),
        snippet=str(item.get("snippet") or ""),
        summary=str(item.get("summary") or ""),
        source_name=str(item.get("source_name") or ""),
        publish_time=item.get("publish_time"),
    )


@bocha_router.post(
    "/search",
    response_model=BochaSearchResponse,
    status_code=status.HTTP_200_OK,
)
def search_bocha(
    payload: BochaSearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BochaSearchResponse:
    try:
        with audit_write(
            db,
            action="bocha_user_search",
            operator=current_user,
            request=request,
            resource_type="bocha_search_session",
            details={
                "query": payload.query,
                "freshness": payload.freshness,
                "summary": payload.summary,
                "requested_count": payload.count,
            },
        ) as ctx:
            result = BochaSearchService().search(
                db,
                query=payload.query,
                freshness=payload.freshness,
                summary=payload.summary,
                count=payload.count,
                created_by=current_user.id,
            )
            ctx["resource_id"] = str(result.session.id)
    except BochaSearchError as exc:
        detail = (
            "Bocha search is not configured"
            if "BOCHA_API_KEY" in str(exc)
            else "Bocha search is unavailable"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        ) from exc

    return BochaSearchResponse(
        session=result.session,
        items=[_result_out(item, idx) for idx, item in enumerate(result.results)],
        total=len(result.results),
        query=result.session.query,
    )


@bocha_router.get(
    "/sessions",
    response_model=BochaSearchSessionListResponse,
)
def list_bocha_sessions(
    status_filter: str | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, max_length=512),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BochaSearchSessionListResponse:
    start = _parse_datetime(created_from, "created_from")
    end = _parse_datetime(created_to, "created_to")

    stmt = select(BochaSearchSession).where(BochaSearchSession.created_by == current_user.id)
    count_stmt = select(BochaSearchSession.id).where(BochaSearchSession.created_by == current_user.id)
    if status_filter:
        if status_filter not in {"success", "failed"}:
            raise HTTPException(status_code=422, detail="status must be success or failed")
        stmt = stmt.where(BochaSearchSession.status == status_filter)
        count_stmt = count_stmt.where(BochaSearchSession.status == status_filter)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(BochaSearchSession.query.ilike(like))
        count_stmt = count_stmt.where(BochaSearchSession.query.ilike(like))
    if start is not None:
        stmt = stmt.where(BochaSearchSession.created_at >= start)
        count_stmt = count_stmt.where(BochaSearchSession.created_at >= start)
    if end is not None:
        stmt = stmt.where(BochaSearchSession.created_at <= end)
        count_stmt = count_stmt.where(BochaSearchSession.created_at <= end)

    total = db.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(BochaSearchSession.created_at.desc(), BochaSearchSession.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return BochaSearchSessionListResponse(items=rows, total=total, page=page, size=size)


@bocha_router.post(
    "/leads",
    response_model=BochaLeadOut,
    status_code=status.HTTP_201_CREATED,
)
def save_bocha_lead(
    payload: BochaSaveLeadRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BochaLead:
    session = db.get(BochaSearchSession, payload.session_id)
    if session is None or session.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bocha search session not found")
    try:
        with audit_write(
            db,
            action="bocha_save_lead",
            operator=current_user,
            request=request,
            resource_type="bocha_lead",
            details={"session_id": payload.session_id, "result_index": payload.result_index},
        ) as ctx:
            lead = BochaSearchService().save_lead(
                db,
                session_id=payload.session_id,
                result_index=payload.result_index,
                created_by=current_user.id,
            )
            ctx["resource_id"] = str(lead.id)
    except BochaSearchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return lead


@bocha_router.get(
    "/leads",
    response_model=BochaLeadListResponse,
)
def list_my_bocha_leads(
    status_filter: BochaLeadStatus | None = Query(default=None, alias="status"),
    query: str | None = Query(default=None, max_length=512),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BochaLeadListResponse:
    start = _parse_datetime(created_from, "created_from")
    end = _parse_datetime(created_to, "created_to")

    stmt = select(BochaLead).where(BochaLead.created_by == current_user.id)
    count_stmt = select(BochaLead.id).where(BochaLead.created_by == current_user.id)
    if status_filter:
        stmt = stmt.where(BochaLead.status == status_filter)
        count_stmt = count_stmt.where(BochaLead.status == status_filter)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(BochaLead.query.ilike(like))
        count_stmt = count_stmt.where(BochaLead.query.ilike(like))
    if start is not None:
        stmt = stmt.where(BochaLead.created_at >= start)
        count_stmt = count_stmt.where(BochaLead.created_at >= start)
    if end is not None:
        stmt = stmt.where(BochaLead.created_at <= end)
        count_stmt = count_stmt.where(BochaLead.created_at <= end)

    total = db.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(BochaLead.created_at.desc(), BochaLead.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return BochaLeadListResponse(items=rows, total=total, page=page, size=size)
