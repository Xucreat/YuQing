from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.permissions import require_admin
from app.db.session import get_db
from app.models.bocha_lead import BochaLead
from app.models.opinion import Opinion
from app.models.region import Region
from app.models.user import User
from app.schemas.bocha import (
    BochaLeadListResponse,
    BochaLeadOut,
    BochaLeadStatus,
    BochaPromoteRequest,
    BochaPromoteResponse,
    BochaRejectRequest,
    BochaSearchRequest,
    BochaSearchResponse,
    BochaSearchResultOut,
)
from app.schemas.opinion import OpinionOut
from app.services.audit_service import audit_write
from app.services.bocha_search_service import BochaSearchError, BochaSearchService

admin_bocha_router = APIRouter(prefix="/admin/bocha", tags=["admin-bocha"])

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


def _get_lead_or_404(db: Session, lead_id: int) -> BochaLead:
    lead = db.scalars(
        select(BochaLead)
        .where(BochaLead.id == lead_id)
        .options(joinedload(BochaLead.creator))
    ).first()
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bocha lead not found",
        )
    return lead


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


@admin_bocha_router.post(
    "/search",
    response_model=BochaSearchResponse,
    status_code=status.HTTP_200_OK,
)
def search_bocha(
    payload: BochaSearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> BochaSearchResponse:
    try:
        with audit_write(
            db,
            action="bocha_search",
            operator=current_user,
            request=request,
            resource_type="bocha_search",
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


@admin_bocha_router.get(
    "/leads",
    response_model=BochaLeadListResponse,
)
def list_bocha_leads(
    status_filter: BochaLeadStatus | None = Query(default=None, alias="status"),
    provider: str | None = Query(default=None, pattern="^(bocha|anspire)$"),
    query: str | None = Query(default=None, max_length=512),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> BochaLeadListResponse:
    start = _parse_datetime(created_from, "created_from")
    end = _parse_datetime(created_to, "created_to")

    stmt = select(BochaLead).options(joinedload(BochaLead.creator))
    if provider:
        stmt = stmt.where(BochaLead.provider == provider)
    if status_filter:
        stmt = stmt.where(BochaLead.status == status_filter)
    if query:
        stmt = stmt.where(BochaLead.query.ilike(f"%{query.strip()}%"))
    if start is not None:
        stmt = stmt.where(BochaLead.created_at >= start)
    if end is not None:
        stmt = stmt.where(BochaLead.created_at <= end)

    count_stmt = select(BochaLead.id)
    if provider:
        count_stmt = count_stmt.where(BochaLead.provider == provider)
    if status_filter:
        count_stmt = count_stmt.where(BochaLead.status == status_filter)
    if query:
        count_stmt = count_stmt.where(BochaLead.query.ilike(f"%{query.strip()}%"))
    if start is not None:
        count_stmt = count_stmt.where(BochaLead.created_at >= start)
    if end is not None:
        count_stmt = count_stmt.where(BochaLead.created_at <= end)

    total = db.scalar(select(func.count()).select_from(count_stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(BochaLead.created_at.desc(), BochaLead.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return BochaLeadListResponse(
        items=rows,
        total=total,
        page=page,
        size=size,
    )


@admin_bocha_router.post(
    "/leads/{lead_id}/confirm",
    response_model=BochaLeadOut,
)
def confirm_bocha_lead(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> BochaLead:
    lead = _get_lead_or_404(db, lead_id)
    if lead.status != "new":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a new Bocha lead can be confirmed",
        )

    with audit_write(
        db,
        action="bocha_confirm",
        operator=current_user,
        request=request,
        resource_type="bocha_lead",
        resource_id=str(lead_id),
        details={"old_status": "new", "new_status": "confirmed"},
    ):
        lead.status = "confirmed"
        db.commit()
    db.refresh(lead)
    return lead


@admin_bocha_router.post(
    "/leads/{lead_id}/reject",
    response_model=BochaLeadOut,
)
def reject_bocha_lead(
    lead_id: int,
    request: Request,
    payload: BochaRejectRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> BochaLead:
    lead = _get_lead_or_404(db, lead_id)
    if lead.status not in {"new", "confirmed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a new or confirmed Bocha lead can be rejected",
        )

    old_status = lead.status
    with audit_write(
        db,
        action="bocha_reject",
        operator=current_user,
        request=request,
        resource_type="bocha_lead",
        resource_id=str(lead_id),
        details={
            "old_status": old_status,
            "new_status": "rejected",
            "reason": payload.reason if payload else "",
        },
    ):
        lead.status = "rejected"
        db.commit()
    db.refresh(lead)
    return lead


@admin_bocha_router.post(
    "/leads/{lead_id}/promote",
    response_model=BochaPromoteResponse,
)
def promote_bocha_lead(
    lead_id: int,
    payload: BochaPromoteRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> BochaPromoteResponse:
    lead = db.scalar(
        select(BochaLead)
        .where(BochaLead.id == lead_id)
        .with_for_update()
        # ``created_by`` is nullable; a joined eager load turns the lock into
        # a LEFT JOIN, which PostgreSQL rejects for FOR UPDATE.  Load the
        # optional creator in a separate query after locking the lead row.
        .options(selectinload(BochaLead.creator))
    )
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bocha lead not found",
        )

    try:
        with audit_write(
            db,
            action="bocha_promote",
            operator=current_user,
            request=request,
            resource_type="bocha_lead",
            resource_id=str(lead_id),
            details={"region_id": payload.region_id},
        ) as ctx:
            if lead.status == "promoted":
                if lead.opinion_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Promoted Bocha lead has no linked Opinion",
                    )
                opinion = db.get(Opinion, lead.opinion_id)
                if opinion is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Promoted Bocha lead points to a missing Opinion",
                    )
                db.refresh(lead)
                db.refresh(opinion)
                ctx["resource_id"] = str(opinion.id)
                return BochaPromoteResponse(
                    lead=lead,
                    opinion=OpinionOut.model_validate(opinion),
                    already_promoted=True,
                )
            if lead.status != "confirmed":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Only a confirmed Bocha lead can be promoted",
                )

            url = (lead.url or "").strip()
            if not url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Bocha lead URL is required for promotion",
                )

            region = db.get(Region, payload.region_id)
            if region is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Region not found",
                )

            existing = db.scalar(select(Opinion).where(Opinion.url == url))
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An Opinion with this URL already exists",
                )

            opinion = Opinion(
                title=lead.title or "",
                content=lead.summary or lead.snippet or "",
                source="Anspire网页搜索" if lead.provider == "anspire" else "Bocha辅助搜索",
                url=url,
                publish_time=lead.publish_time,
                region_id=region.id,
                risk_score=0,
                severity_score=0,
                sentiment="neutral",
                analysis_status="pending",
                analysis_time=None,
                analysis_suggestion=None,
            )
            db.add(opinion)
            db.flush()

            lead.opinion_id = opinion.id
            lead.status = "promoted"
            db.commit()
            db.refresh(lead)
            db.refresh(opinion)
            ctx["resource_id"] = str(opinion.id)
            return BochaPromoteResponse(
                lead=lead,
                opinion=OpinionOut.model_validate(opinion),
                already_promoted=False,
            )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An Opinion with this URL already exists",
        ) from exc
