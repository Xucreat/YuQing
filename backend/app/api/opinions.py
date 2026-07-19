"""舆情基础 CRUD API（Phase 2A）。

路由（均挂载在 /api 下，由 main.py 统一加前缀）：
  GET    /opinions          列表（分页 + source/risk_level/keyword 过滤）
  GET    /opinions/{id}     详情（404: "Opinion not found"）
  POST   /opinions          创建（供未来 Collector 写入；默认 risk_score=0 / sentiment=neutral）
  DELETE /opinions/{id}     删除（MVP 保留）

所有路由受 Depends(get_current_user) 保护（Bearer JWT）。
禁止提前实现：AI Service / DeepSeek / Collector / Event 聚合 / Dashboard。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, delete as sa_delete
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.opinion import Opinion
from app.models.region import Region
from app.models.event_opinion import EventOpinion
from app.models.alert import AlertRecord
from app.schemas.opinion import OpinionCreate, OpinionListResponse, OpinionOut

opinions_router = APIRouter(
    tags=["opinions"],
    # 全部舆情接口均需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)

MAX_SIZE = 100


@opinions_router.get("", response_model=OpinionListResponse)
def list_opinions(
    page: int = 1,
    size: int = 20,
    source: str | None = None,
    risk_level: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
) -> OpinionListResponse:
    """分页列表，支持来源 / 风险等级 / 关键词过滤。

    risk_level 映射到 opinions.sentiment（positive|negative|neutral，
    因 opinions 表无 risk_level 列，按用户约束不改动数据库结构）。
    keyword 对 keywords / title / content 做模糊匹配。
    """
    page = max(page, 1)
    size = max(min(size, MAX_SIZE), 1)

    stmt = select(Opinion)
    if source:
        stmt = stmt.where(Opinion.source == source)
    if risk_level:
        stmt = stmt.where(Opinion.sentiment == risk_level)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            or_(
                Opinion.keywords.ilike(like),
                Opinion.title.ilike(like),
                Opinion.content.ilike(like),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Opinion.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()

    return OpinionListResponse(items=rows, total=total, page=page, size=size)


@opinions_router.get("/{opinion_id}", response_model=OpinionOut)
def get_opinion(opinion_id: int, db: Session = Depends(get_db)) -> Opinion:
    """舆情详情；不存在返回 404 {"detail":"Opinion not found"}。"""
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )
    return opinion


@opinions_router.post("", response_model=OpinionOut, status_code=status.HTTP_201_CREATED)
def create_opinion(payload: OpinionCreate, db: Session = Depends(get_db)) -> Opinion:
    """创建舆情（供未来 Collector 写入）。

    创建后默认 risk_score=0、sentiment="neutral"（AI 阶段再更新）。
    region_id 必须存在，否则 404 "Region not found"。
    """
    region = db.get(Region, payload.region_id)
    if region is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Region not found",
        )

    opinion = Opinion(
        title=payload.title,
        content=payload.content,
        source=payload.source,
        url=payload.url,
        publish_time=payload.publish_time,
        region_id=payload.region_id,
        risk_score=0,
        sentiment="neutral",
    )
    db.add(opinion)
    db.commit()
    db.refresh(opinion)
    return opinion


@opinions_router.delete("/{opinion_id}", status_code=status.HTTP_200_OK)
def delete_opinion(opinion_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete opinion with cascade cleanup of related records."""
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )

    # Cascade-clean related records before deleting opinion
    from app.models.propagation import PropagationNode
    for eo in db.query(EventOpinion).where(EventOpinion.opinion_id == opinion_id).all():
        db.delete(eo)
    db.query(AlertRecord).where(AlertRecord.opinion_id == opinion_id).update(
        {"opinion_id": None}, synchronize_session=False
    )
    for pn in db.query(PropagationNode).where(PropagationNode.opinion_id == opinion_id).all():
        db.delete(pn)
    db.flush()
    db.delete(opinion)
    db.commit()
    return {"detail": "Opinion deleted", "id": opinion_id}