from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.bocha_lead import BochaLead
from app.models.bocha_search_session import BochaSearchSession
from app.models.user import User
from app.schemas.anspire import (AnspireOptionsResponse, AnspireSaveLeadRequest, AnspireSearchRequest,
    AnspireSearchResponse, AnspireResultOut, AnspireSessionListResponse, AnspireSessionOut)
from app.schemas.bocha import BochaLeadOut
from app.services.anspire_search_service import AnspireSearchError, AnspireSearchService

# RBAC 收口：Anspire 检索整体由「仅登录」收敛为需要 ai:search（路由级依赖，不改端点签名）。
anspire_router = APIRouter(
    prefix="/anspire",
    tags=["anspire"],
    dependencies=[Depends(get_current_user), Depends(require_permission("ai:search"))],
)

def _error(exc: AnspireSearchError) -> HTTPException:
    code = exc.status_code or (422 if "query" in str(exc) or "top_k" in str(exc) or "insite" in str(exc) or "time" in str(exc) else 503)
    return HTTPException(status_code=code, detail=str(exc))

@anspire_router.post("/search", response_model=AnspireSearchResponse)
def search_anspire(payload: AnspireSearchRequest, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        result = AnspireSearchService().search(db, query=payload.query, top_k=payload.top_k, insite=payload.insite,
            from_time=payload.from_time, to_time=payload.to_time, region_mode=payload.region_mode, created_by=current_user.id)
    except AnspireSearchError as exc: raise _error(exc) from exc
    return AnspireSearchResponse(session=result.session, items=[AnspireResultOut(result_index=i, **item) for i, item in enumerate(result.results)], total=len(result.results), query=result.session.query)

@anspire_router.get("/options", response_model=AnspireOptionsResponse)
def anspire_options():
    return AnspireOptionsResponse(top_k=[10,20,30,40,50], region_mode=[0,1,2], search_type="web", max_query_length=64, max_insite_sites=20)

@anspire_router.get("/sessions", response_model=AnspireSessionListResponse)
def list_anspire_sessions(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    base = select(BochaSearchSession).where(BochaSearchSession.provider == "anspire", BochaSearchSession.created_by == current_user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(BochaSearchSession.created_at.desc(), BochaSearchSession.id.desc()).offset((page-1)*size).limit(size)).all()
    return AnspireSessionListResponse(items=rows, total=total, page=page, size=size)

@anspire_router.post("/leads", response_model=BochaLeadOut, status_code=status.HTTP_201_CREATED)
def save_anspire_lead(payload: AnspireSaveLeadRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try: return AnspireSearchService().save_lead(db, session_id=payload.session_id, result_index=payload.result_index, created_by=current_user.id)
    except AnspireSearchError as exc: raise _error(exc) from exc

@anspire_router.get("/leads")
def list_anspire_leads(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    base = select(BochaLead).where(BochaLead.provider == "anspire", BochaLead.created_by == current_user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(BochaLead.created_at.desc(), BochaLead.id.desc()).offset((page-1)*size).limit(size)).all()
    return {"items": [BochaLeadOut.model_validate(row) for row in rows], "total": total, "page": page, "size": size}
