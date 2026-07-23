"""Keyword management CRUD API（分层：监测关键词 + 敏感/风险词）。

- 监测关键词（type='monitoring'）：业务可配置，管理员可正常增删改查与启停。
- 敏感/风险词（type='sensitive'）：
    * source='system' 系统内置词 —— 受保护：可查看/搜索/筛选/启停，不可删除、不可篡改内容；
    * source='custom'  管理员自定词 —— 可新增/编辑/删除/启停。

安全边界以「数据层守卫」实现（系统敏感词禁删禁改），未引入新权限体系，
保留后续接入 RBAC 的扩展空间（当前沿用 keywords:write 操作级权限）。
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.keyword import Keyword
from app.models.user import User
from app.services.keyword_service import clear_keyword_cache
from pydantic import BaseModel, Field

keywords_router = APIRouter(
    tags=["keywords"],
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100

ALLOWED_TYPES = {"monitoring", "sensitive"}
ALLOWED_SOURCES = {"system", "custom"}


class KeywordCreate(BaseModel):
    word: str = Field(min_length=1, max_length=128)
    weight: int = 1
    category: str = "general"
    type: str = "monitoring"
    source: str = "custom"
    is_enabled: bool = True

    def model_post_init(self, __context) -> None:
        if self.type not in ALLOWED_TYPES:
            raise ValueError("type must be 'monitoring' or 'sensitive'")
        if self.source not in ALLOWED_SOURCES:
            raise ValueError("source must be 'system' or 'custom'")


class KeywordUpdate(BaseModel):
    word: Optional[str] = Field(default=None, min_length=1, max_length=128)
    weight: Optional[int] = None
    category: Optional[str] = None
    is_enabled: Optional[bool] = None


class KeywordOut(BaseModel):
    id: int
    word: str
    weight: int
    category: str
    type: str
    source: str
    is_enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class KeywordListResponse(BaseModel):
    items: list[KeywordOut]
    total: int
    page: int
    size: int


def _is_protected(kw: Keyword) -> bool:
    """系统内置敏感词：受保护，禁止删除与内容篡改。"""
    return kw.source == "system" and kw.type == "sensitive"


@keywords_router.get("", response_model=KeywordListResponse)
def list_keywords(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=MAX_SIZE),
    q: Optional[str] = None,
    kw_type: Optional[str] = Query(None, alias="type"),
    source: Optional[str] = None,
    is_enabled: Optional[bool] = None,
    category: Optional[str] = None,
    sort: str = "weight",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    stmt = select(Keyword)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Keyword.word.ilike(like))
    if kw_type:
        stmt = stmt.where(Keyword.type == kw_type)
    if source:
        stmt = stmt.where(Keyword.source == source)
    if is_enabled is not None:
        stmt = stmt.where(Keyword.is_enabled.is_(is_enabled))
    if category:
        stmt = stmt.where(Keyword.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    sort_col = getattr(Keyword, sort, Keyword.weight)
    if order == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())
    rows = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return KeywordListResponse(items=rows, total=total, page=page, size=size)


@keywords_router.post("", response_model=KeywordOut, status_code=status.HTTP_201_CREATED)
def create_keyword(
    payload: KeywordCreate,
    _: User = Depends(require_permission("keywords:write")),
    db: Session = Depends(get_db),
):
    # (word, type) 复合唯一：同名但不同类型（监测 vs 敏感）允许共存。
    existing = (
        db.query(Keyword)
        .filter(Keyword.word == payload.word, Keyword.type == payload.type)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"关键词已存在（type={payload.type}）：{payload.word}",
        )
    now = datetime.now(timezone.utc)
    kw = Keyword(
        word=payload.word,
        weight=payload.weight,
        category=payload.category,
        type=payload.type,
        source=payload.source,
        is_enabled=payload.is_enabled,
        created_at=now,
        updated_at=now,
    )
    db.add(kw)
    db.commit()
    db.refresh(kw)
    clear_keyword_cache()
    return kw


@keywords_router.put("/{keyword_id}", response_model=KeywordOut)
def update_keyword(
    keyword_id: int,
    payload: KeywordUpdate,
    _: User = Depends(require_permission("keywords:write")),
    db: Session = Depends(get_db),
):
    kw = db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    # 系统内置敏感词：仅允许运行时启停，禁止篡改内容（保护核心风险语义）。
    if _is_protected(kw):
        if (
            payload.word is not None
            or payload.weight is not None
            or payload.category is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="系统内置敏感词不可修改内容，仅可启停",
            )
        if payload.is_enabled is not None:
            kw.is_enabled = payload.is_enabled
        kw.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(kw)
        clear_keyword_cache()
        return kw

    if payload.word is not None:
        # 改词时需保证 (word, type) 不与他人冲突
        clash = (
            db.query(Keyword)
            .filter(
                Keyword.word == payload.word,
                Keyword.type == kw.type,
                Keyword.id != kw.id,
            )
            .first()
        )
        if clash:
            raise HTTPException(status_code=409, detail="关键词已存在（同类型）")
        kw.word = payload.word
    if payload.weight is not None:
        kw.weight = payload.weight
    if payload.category is not None:
        kw.category = payload.category
    if payload.is_enabled is not None:
        kw.is_enabled = payload.is_enabled
    kw.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(kw)
    clear_keyword_cache()
    return kw


@keywords_router.delete("/{keyword_id}", status_code=status.HTTP_200_OK)
def delete_keyword(
    keyword_id: int,
    _: User = Depends(require_permission("keywords:write")),
    db: Session = Depends(get_db),
):
    kw = db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    # 系统内置敏感词禁止删除（防止破坏基础风险识别能力）。
    if _is_protected(kw):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="系统内置敏感词不可删除",
        )
    db.delete(kw)
    db.commit()
    clear_keyword_cache()
    return {"detail": "Keyword deleted", "id": keyword_id}


@keywords_router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(Keyword.category).distinct()).all()
    return list(rows)
