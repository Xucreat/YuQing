"""Keyword management CRUD API (P1)."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.keyword import Keyword
from pydantic import BaseModel

keywords_router = APIRouter(
    tags=["keywords"],
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100


class KeywordCreate(BaseModel):
    word: str
    weight: int = 1
    category: str = "general"


class KeywordUpdate(BaseModel):
    word: str | None = None
    weight: int | None = None
    category: str | None = None


class KeywordOut(BaseModel):
    id: int
    word: str
    weight: int
    category: str

    class Config:
        from_attributes = True


class KeywordListResponse(BaseModel):
    items: list[KeywordOut]
    total: int
    page: int
    size: int


@keywords_router.get("", response_model=KeywordListResponse)
def list_keywords(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=MAX_SIZE),
    q: str | None = None,
    category: str | None = None,
    sort: str = "weight",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    stmt = select(Keyword)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Keyword.word.ilike(like))
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
def create_keyword(payload: KeywordCreate, db: Session = Depends(get_db)):
    existing = db.query(Keyword).filter(Keyword.word == payload.word).first()
    if existing:
        raise HTTPException(status_code=409, detail="Keyword already exists")
    kw = Keyword(word=payload.word, weight=payload.weight, category=payload.category)
    db.add(kw)
    db.commit()
    db.refresh(kw)
    return kw


@keywords_router.put("/{keyword_id}", response_model=KeywordOut)
def update_keyword(keyword_id: int, payload: KeywordUpdate, db: Session = Depends(get_db)):
    kw = db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    if payload.word is not None:
        kw.word = payload.word
    if payload.weight is not None:
        kw.weight = payload.weight
    if payload.category is not None:
        kw.category = payload.category
    db.commit()
    db.refresh(kw)
    return kw


@keywords_router.delete("/{keyword_id}", status_code=status.HTTP_200_OK)
def delete_keyword(keyword_id: int, db: Session = Depends(get_db)):
    kw = db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    db.delete(kw)
    db.commit()
    return {"detail": "Keyword deleted", "id": keyword_id}


@keywords_router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(Keyword.category).distinct()).all()
    return list(rows)
