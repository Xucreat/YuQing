"""隔离的外网舆情 API。

本模块只读写 ``foreign_*`` 表和带 ``is_foreign=true`` 的 data_sources，
不复用国内 opinions 查询、关键词服务或 CollectorService。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import cast, func, or_, select, String
from sqlalchemy.orm import Session

from app.api.admin_data_sources import (
    _is_foreign,
    _parse_config_json,
    _serialize,
    _validate_foreign_config,
)
from app.core.dependencies import get_current_user
from app.core.permissions import require_admin, require_permission
from app.core.task_manager import start_task
from app.db.session import SessionLocal, get_db
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.models.user import User
from app.services.audit_service import audit_write
from app.services.foreign_collection_service import collect_foreign
from app.services.foreign_keyword_service import get_foreign_keywords


foreign_router = APIRouter(
    prefix="/foreign",
    tags=["foreign"],
    dependencies=[Depends(get_current_user)],
)


class ForeignKeywordPayload(BaseModel):
    word: str = Field(min_length=1, max_length=128)
    category: str = Field(default="general", max_length=64)
    is_enabled: bool = True


class ForeignSourcePayload(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    key: str = Field(min_length=1, max_length=64)
    feeds: list[str] = Field(min_length=1)
    proxy_env: str | None = "FOREIGN_HTTP_PROXY"
    enabled: bool = False
    schedule_enabled: bool = False
    schedule_interval_minutes: int = Field(default=60, ge=5, le=10080)
    priority: int = Field(default=500, ge=0, le=9999)
    fetch_full_text: bool = False
    max_items: int = Field(default=100, ge=1, le=500)


def _source_config(source: DataSource) -> dict:
    cfg, err = _parse_config_json(source.config_json or "{}")
    return cfg if not err and isinstance(cfg, dict) else {}


def _foreign_source_or_404(db: Session, source_id: int) -> DataSource:
    source = db.get(DataSource, source_id)
    if source is None or not _is_foreign(source.class_path):
        raise HTTPException(status_code=404, detail="Foreign data source not found")
    return source


def _foreign_source_item(source: DataSource) -> dict[str, Any]:
    cfg = _source_config(source)
    return {
        "id": source.id,
        "key": source.key,
        "name": source.name,
        "type": source.type,
        "class_path": source.class_path,
        "enabled": source.enabled,
        "schedule_enabled": source.schedule_enabled,
        "schedule_interval_minutes": source.schedule_interval_minutes,
        "priority": source.priority,
        "feeds": cfg.get("feeds") or [],
        "keywords": cfg.get("keywords") or [],
        "proxy_env": cfg.get("proxy_env"),
        "proxy_configured": bool(
            cfg.get("proxy_env") and __import__("os").getenv(str(cfg["proxy_env"]))
        ),
        "fetch_full_text": bool(cfg.get("fetch_full_text", False)),
        "max_items": cfg.get("max_items", 100),
        "config_json": source.config_json,
    }


@foreign_router.get("/keywords")
def list_foreign_keywords(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    q: str | None = None,
    is_enabled: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("keywords:read")),
):
    stmt = select(ForeignKeyword)
    if q:
        stmt = stmt.where(ForeignKeyword.word.ilike(f"%{q}%"))
    if is_enabled is not None:
        stmt = stmt.where(ForeignKeyword.is_enabled.is_(is_enabled))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignKeyword.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {"items": rows, "total": total, "page": page, "size": size}


@foreign_router.post("/keywords", status_code=201)
def create_foreign_keyword(
    payload: ForeignKeywordPayload,
    request: Request,
    current_user: User = Depends(require_permission("keywords:write")),
    db: Session = Depends(get_db),
):
    word = payload.word.strip()
    if db.scalar(select(ForeignKeyword).where(ForeignKeyword.word == word)):
        raise HTTPException(status_code=409, detail=f"Foreign keyword already exists: {word}")
    with audit_write(
        db,
        action="CREATE",
        operator=current_user,
        request=request,
        resource_type="foreign_keyword",
        details={"word": word},
    ) as ctx:
        row = ForeignKeyword(
            word=word,
            category=payload.category.strip() or "general",
            is_enabled=payload.is_enabled,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        ctx["resource_id"] = str(row.id)
    return row


@foreign_router.patch("/keywords/{keyword_id}")
def update_foreign_keyword(
    keyword_id: int,
    payload: ForeignKeywordPayload,
    request: Request,
    current_user: User = Depends(require_permission("keywords:write")),
    db: Session = Depends(get_db),
):
    row = db.get(ForeignKeyword, keyword_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign keyword not found")
    word = payload.word.strip()
    clash = db.scalar(
        select(ForeignKeyword).where(
            ForeignKeyword.word == word,
            ForeignKeyword.id != keyword_id,
        )
    )
    if clash:
        raise HTTPException(status_code=409, detail=f"Foreign keyword already exists: {word}")
    with audit_write(
        db,
        action="UPDATE",
        operator=current_user,
        request=request,
        resource_type="foreign_keyword",
        resource_id=str(keyword_id),
        details={"word": word},
    ):
        row.word = word
        row.category = payload.category.strip() or "general"
        row.is_enabled = payload.is_enabled
        db.commit()
    db.refresh(row)
    return row


@foreign_router.delete("/keywords/{keyword_id}")
def delete_foreign_keyword(
    keyword_id: int,
    request: Request,
    current_user: User = Depends(require_permission("keywords:write")),
    db: Session = Depends(get_db),
):
    row = db.get(ForeignKeyword, keyword_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign keyword not found")
    with audit_write(
        db,
        action="DELETE",
        operator=current_user,
        request=request,
        resource_type="foreign_keyword",
        resource_id=str(keyword_id),
        details={"word": row.word},
    ):
        db.delete(row)
        db.commit()
    return {"detail": "Foreign keyword deleted", "id": keyword_id}


@foreign_router.get("/sources")
def list_foreign_sources(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    rows = db.scalars(
        select(DataSource)
        .where(DataSource.class_path.ilike("%foreign_rss%"))
        .order_by(DataSource.priority.asc(), DataSource.id.asc())
    ).all()
    return {"items": [_foreign_source_item(row) for row in rows], "total": len(rows)}


@foreign_router.post("/sources", status_code=201)
def create_foreign_source(
    payload: ForeignSourcePayload,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if " " in payload.key or not payload.key.replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="key 只能包含字母、数字、下划线")
    if db.scalar(select(DataSource).where(DataSource.key == payload.key)):
        raise HTTPException(status_code=409, detail=f"key 已存在：{payload.key}")
    cfg = {
        "is_foreign": True,
        "collector": "foreign_rss",
        "source_name": payload.name.strip(),
        "feeds": [feed.strip() for feed in payload.feeds if feed.strip()],
        "proxy_env": payload.proxy_env,
        "keywords": get_foreign_keywords(db),
        "collection_mode": "foreign",
        "fetch_full_text": payload.fetch_full_text,
        "max_items": payload.max_items,
    }
    error = _validate_foreign_config(cfg)
    if error:
        raise HTTPException(status_code=422, detail=error)
    with audit_write(
        db,
        action="CREATE",
        operator=current_user,
        request=request,
        resource_type="foreign_data_source",
        details={"key": payload.key, "name": payload.name},
    ) as ctx:
        source = DataSource(
            key=payload.key,
            name=payload.name.strip(),
            type="foreign_rss",
            class_path="app.collectors.foreign_rss.ForeignRSSCollector",
            enabled=payload.enabled,
            schedule_enabled=False,
            schedule_interval_minutes=payload.schedule_interval_minutes,
            priority=payload.priority,
            scope_region_codes=None,
            config_json=json.dumps(cfg, ensure_ascii=False),
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        ctx["resource_id"] = str(source.id)
    return _foreign_source_item(source)


@foreign_router.patch("/sources/{source_id}")
def update_foreign_source(
    source_id: int,
    payload: dict,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    source = _foreign_source_or_404(db, source_id)
    cfg = _source_config(source)
    if "feeds" in payload:
        cfg["feeds"] = payload["feeds"]
    if "proxy_env" in payload:
        cfg["proxy_env"] = payload["proxy_env"]
    if "fetch_full_text" in payload:
        cfg["fetch_full_text"] = bool(payload["fetch_full_text"])
    if "max_items" in payload:
        cfg["max_items"] = int(payload["max_items"])
    if "name" in payload:
        source.name = str(payload["name"]).strip() or source.name
        cfg["source_name"] = source.name
    error = _validate_foreign_config(cfg)
    if error:
        raise HTTPException(status_code=422, detail=error)
    if payload.get("enabled") is True or payload.get("schedule_enabled") is True:
        source_enabled = payload.get("enabled", source.enabled)
        if source_enabled is not True:
            raise HTTPException(
                status_code=422,
                detail="foreign source must be enabled before enabling schedule",
            )
    with audit_write(
        db,
        action="UPDATE",
        operator=current_user,
        request=request,
        resource_type="foreign_data_source",
        resource_id=str(source_id),
        details={"changes": list(payload.keys())},
    ):
        if "enabled" in payload:
            source.enabled = bool(payload["enabled"])
        # Phase 1 keeps foreign scheduling manual-only.
        if "schedule_enabled" in payload:
            source.schedule_enabled = False
        if "schedule_interval_minutes" in payload:
            source.schedule_interval_minutes = max(
                5, int(payload["schedule_interval_minutes"])
            )
        if "priority" in payload:
            source.priority = int(payload["priority"])
        source.config_json = json.dumps(cfg, ensure_ascii=False)
        db.commit()
    db.refresh(source)
    return _foreign_source_item(source)


def _foreign_opinion_item(row: ForeignOpinion) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_id": row.source_id,
        "source_key": row.source_key,
        "source_name_snapshot": row.source_name_snapshot,
        "title": row.title,
        "summary": row.summary,
        "content": row.content,
        "url": row.url,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "collected_at": row.collected_at.isoformat() if row.collected_at else None,
        "matched_keywords": row.matched_keywords or [],
        "content_hash": row.content_hash,
        "duplicate_of_id": row.duplicate_of_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@foreign_router.get("/opinions")
def list_foreign_opinions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    keyword: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    stmt = select(ForeignOpinion)
    if source:
        stmt = stmt.where(ForeignOpinion.source_name_snapshot == source)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                ForeignOpinion.title.ilike(like),
                ForeignOpinion.summary.ilike(like),
                ForeignOpinion.content.ilike(like),
            )
        )
    if keyword:
        stmt = stmt.where(
            cast(ForeignOpinion.matched_keywords, String).ilike(f"%{keyword}%")
        )
    if date_from:
        try:
            stmt = stmt.where(
                func.date(ForeignOpinion.published_at)
                >= datetime.strptime(date_from, "%Y-%m-%d").date()
            )
        except ValueError:
            raise HTTPException(status_code=422, detail="date_from must be YYYY-MM-DD")
    if date_to:
        try:
            stmt = stmt.where(
                func.date(ForeignOpinion.published_at)
                <= datetime.strptime(date_to, "%Y-%m-%d").date()
            )
        except ValueError:
            raise HTTPException(status_code=422, detail="date_to must be YYYY-MM-DD")
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignOpinion.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "items": [_foreign_opinion_item(row) for row in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_router.get("/opinions/sources")
def list_foreign_opinion_sources(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    rows = db.execute(
        select(ForeignOpinion.source_name_snapshot)
        .where(ForeignOpinion.source_name_snapshot != "")
        .group_by(ForeignOpinion.source_name_snapshot)
        .order_by(func.count(ForeignOpinion.id).desc())
    ).all()
    return [row[0] for row in rows]


@foreign_router.get("/opinions/{opinion_id}")
def get_foreign_opinion(
    opinion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    row = db.get(ForeignOpinion, opinion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign opinion not found")
    return _foreign_opinion_item(row)


def _foreign_run_item(row: CollectorRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "scope": row.scope,
        "collector_name": row.collector_name,
        "batch_id": row.batch_id,
        "trigger_type": row.trigger_type,
        "start_time": row.start_time.isoformat() if row.start_time else None,
        "end_time": row.end_time.isoformat() if row.end_time else None,
        "status": row.status,
        "fetched_raw": row.fetched_raw,
        "matched": row.upstream_returned,
        "created": row.created,
        "duplicate": row.duplicate,
        "failed": row.failed,
        "proxy_used": bool(row.proxy_used),
        "error_msg": row.error_msg,
    }


@foreign_router.get("/collection-runs")
def list_foreign_collection_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    stmt = select(CollectorRun).where(CollectorRun.scope == "foreign")
    if status:
        stmt = stmt.where(CollectorRun.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(CollectorRun.start_time.desc(), CollectorRun.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "items": [_foreign_run_item(row) for row in rows],
        "total": total,
        "page": page,
        "size": size,
    }


def _run_foreign_collect_task(task, source_ids: list[int] | None) -> dict:
    db = SessionLocal()
    try:
        task.step = "外网 RSS 采集中"

        def progress(done: int, total: int, name: str) -> None:
            task.progress = int(done / total * 100) if total else 100
            task.step = f"已处理 {done}/{total} 个外网数据源（{name}）"

        result = collect_foreign(
            db,
            source_ids=source_ids,
            on_progress=progress,
        )
        task.step = "外网采集完成"
        return result
    finally:
        db.close()


@foreign_router.post("/collect")
def collect_foreign_now(
    source_ids: list[int] | None = Body(None, embed=True),
    current_user: User = Depends(require_admin),
):
    task_id = start_task(
        "foreign-collector",
        _run_foreign_collect_task,
        source_ids,
    )
    return {
        "success": True,
        "task_id": task_id,
        "batch_id": uuid.uuid4().hex,
        "scope": "foreign",
        "message": "外网采集任务已接受",
    }
