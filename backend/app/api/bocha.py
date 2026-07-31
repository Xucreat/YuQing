from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
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
    BochaAILeadOut,
    BochaAISaveLeadRequest,
    BochaAISearchRequest,
    BochaAISearchResponse,
    BochaAISearchResultOut,
)
from app.services.audit_service import audit_write
from app.services.bocha_search_service import BochaSearchError, BochaSearchService
from app.services.bocha_ai_search_service import BochaAISearchError, BochaAISearchService

bocha_router = APIRouter(
    prefix="/bocha",
    tags=["bocha"],
    # RBAC 收口：AI 检索（Web Search / AI Search）整体由「仅登录」收敛为需要 ai:search。
    # 路由级依赖对本 router 下全部端点生效，端点内部逻辑与签名保持不变。
    dependencies=[Depends(get_current_user), Depends(require_permission("ai:search"))],
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


def _ai_response(result) -> BochaAISearchResponse:
    return BochaAISearchResponse(
        session=result.session,
        answer=result.answer,
        follow_up_questions=result.follow_up_questions,
        web_pages=[BochaAISearchResultOut(result_index=index, **item) for index, item in enumerate(result.web_pages)],
        images=result.images,
        modal_cards=result.modal_cards,
        conversation_id=result.conversation_id,
        total=result.total,
        raw_response=result.raw_response,
    )


@bocha_router.post(
    "/ai-search",
    response_model=BochaAISearchResponse,
    status_code=status.HTTP_200_OK,
)
def search_bocha_ai(
    payload: BochaAISearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BochaAISearchResponse:
    try:
        with audit_write(
            db,
            action="bocha_ai_user_search",
            operator=current_user,
            request=request,
            resource_type="bocha_ai_search_session",
            details={
                "query": payload.query,
                "freshness": payload.freshness,
                "include": payload.include,
                "requested_count": payload.count,
                "answer": payload.answer,
                "stream": payload.stream,
            },
        ) as ctx:
            result = BochaAISearchService().search(
                db,
                query=payload.query,
                freshness=payload.freshness,
                include=payload.include,
                count=payload.count,
                answer=payload.answer,
                stream=payload.stream,
                created_by=current_user.id,
            )
            ctx["resource_id"] = str(result.session.id)
    except BochaAISearchError as exc:
        message = str(exc)
        if "BOCHA_API_KEY" in message:
            detail, code = "Bocha AI search is not configured", status.HTTP_503_SERVICE_UNAVAILABLE
        elif "quota exhausted" in message.lower():
            detail, code = "Bocha AI search quota exhausted; configure a valid BOCHA_AI_API_KEY", status.HTTP_503_SERVICE_UNAVAILABLE
        elif "authentication failed" in message.lower() or "permission denied" in message.lower():
            detail, code = "Bocha AI search credentials are invalid or lack permission", status.HTTP_503_SERVICE_UNAVAILABLE
        elif "invalid" in message.lower() or "between" in message.lower() or "freshness" in message.lower() or "query" in message.lower():
            detail, code = message, status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            detail, code = "Bocha AI search is unavailable", status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=code, detail=detail) from exc
    return _ai_response(result)


@bocha_router.get("/ai-search/options")
def bocha_ai_search_options() -> dict[str, object]:
    from app.core.config import settings

    return {
        "platform_includes": {
            "weibo": settings.bocha_ai_weibo_domains,
            "xiaohongshu": settings.bocha_ai_xiaohongshu_domains,
        },
        "freshness": ["oneDay", "oneWeek", "oneMonth", "oneYear", "noLimit"],
        "max_count": 50,
    }


@bocha_router.post(
    "/ai-leads",
    response_model=BochaAILeadOut,
    status_code=status.HTTP_201_CREATED,
)
def save_bocha_ai_lead(
    payload: BochaAISaveLeadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> object:
    try:
        return BochaAISearchService().save_lead(
            db,
            session_id=payload.session_id,
            result_index=payload.result_index,
            created_by=current_user.id,
        )
    except BochaAISearchError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


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
