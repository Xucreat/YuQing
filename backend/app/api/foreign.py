"""隔离的外网舆情 API。

本模块只读写 ``foreign_*`` 表和带 ``is_foreign=true`` 的 data_sources，
不复用国内 opinions 查询、关键词服务或 CollectorService。
"""
from __future__ import annotations

import json
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import cast, func, inspect, or_, select, String
from sqlalchemy.orm import Session

from app.api.admin_data_sources import (
    _parse_config_json,
    _validate_foreign_config,
)
from app.core.dependencies import get_current_user
from app.core.permissions import get_user_permissions, is_superuser_user, require_permission
from app.core.task_manager import DuplicateTaskError, Task, cancel_task, get_task, start_task
from app.db.session import SessionLocal, get_db
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.foreign_keyword import ForeignKeyword
from app.collectors.foreign_rss import resolve_proxy_mode
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_analysis_run import ForeignAnalysisRun
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_manual_review import ForeignManualReview
from app.models.foreign_ai_batch_run import ForeignAIBatchRun
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_risk_result import ForeignRiskResult
from app.models.foreign_risk_term import ForeignRiskTerm
from app.models.user import User
from app.services.audit_service import audit_write, log_operation
from app.services.foreign_collection_service import collect_foreign
from app.services.foreign_ai_service import (
    AI_MODEL_VERSION,
    ForeignAIService,
    serialize_ai_result,
)
from app.services.foreign_keyword_service import (
    create_foreign_keyword_row,
    delete_foreign_keyword_row,
    get_foreign_keyword_row,
    get_foreign_keywords,
    get_foreign_monitoring_keywords,
    list_foreign_keyword_categories,
    list_foreign_keyword_rows,
    update_foreign_keyword_row,
)
from app.services.foreign_collection_service import (
    _assert_foreign_source_constructable,
    test_foreign_source,
)
from app.services.foreign_content_sanitizer import sanitize_foreign_html
from app.services.foreign_effective_risk import (
    CURRENT_SOURCE,
    RULE_SOURCE,
    RiskSource,
    attach_effective_risk,
    effective_risk_level_expression,
    resolve_one,
)
from app.services.foreign_risk_service import (
    RULE_MODEL_VERSION,
    ForeignRiskService,
)
from app.services.foreign_event_service import ForeignEventService
from app.services.foreign_alert_service import ForeignAlertService
from app.services.foreign_manual_review_service import (
    confirm_alert_for_review,
    confirm_event_for_review,
    ensure_foreign_manual_review,
)
from app.services.current_risk import apply_review_decision
from app.models.foreign_ai_alert_candidate import ForeignAIAlertCandidate
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event_opinion import ForeignEventOpinion


foreign_router = APIRouter(
    prefix="/foreign",
    tags=["foreign"],
    dependencies=[Depends(get_current_user)],
)

_FOREIGN_AI_BATCH_TASKS: dict[str, str] = {}
_FOREIGN_AI_BATCH_META: dict[str, dict[str, Any]] = {}


def require_foreign_review_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    """Allow reviewers to read the shared queue through any review domain permission."""
    if is_superuser_user(current_user):
        return current_user
    perms = set(get_user_permissions(current_user, db))
    if perms.intersection({
        "ai:review:read",
        "foreign:events:review:read",
        "foreign:alerts:review:read",
    }):
        return current_user
    raise HTTPException(status_code=403, detail="Foreign review read permission required")


class ForeignKeywordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1, max_length=128)
    category: str = Field(default="主题", max_length=64)
    type: Literal["monitoring", "sensitive"] = "monitoring"
    source: Literal["system", "custom"] = "custom"
    weight: int = Field(default=10, ge=0, le=100)
    severity_weight: int = Field(default=0, ge=0, le=100)
    rule_config: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True


class ForeignAIAlertAdmissionPayload(BaseModel):
    included: bool
    note: str = Field(min_length=1, max_length=4000)


class ForeignAIBatchPayload(BaseModel):
    """Selection contract for asynchronous foreign AI review."""

    scope: Literal["count", "time", "full"] = "count"
    opinion_ids: list[int] | None = Field(default=None, max_length=5000)
    recent_n: int = Field(default=100, ge=1, le=100000)
    limit: int = Field(default=100, ge=1, le=100000)
    date_from: str | None = None
    date_to: str | None = None
    use_current_filters: bool = False
    current_filters: dict[str, Any] = Field(default_factory=dict)
    only_unanalyzed: bool = True
    force: bool = False
    full_confirmation: bool = False
    token_budget: int = Field(default=100_000, ge=1_000, le=2_000_000)


class ForeignAIReviewDecisionPayload(BaseModel):
    decision: Literal[
        "keep_rule", "use_ai_display", "confirm_event_change",
        "confirm_alert_change", "reject_change", "complete_review"
    ]
    reason: str = Field(default="", max_length=4000)
    request_id: str | None = Field(default=None, max_length=128)


class ForeignAIReviewBatchPayload(BaseModel):
    review_ids: list[int] | None = Field(default=None, max_length=5000)
    decision: Literal["keep_rule", "use_ai_display", "confirm_event_change", "confirm_alert_change", "reject_change"]
    reason: str = Field(default="", max_length=4000)
    request_id: str | None = Field(default=None, max_length=128)
    confirm_all: bool = False


class ForeignKeywordUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str | None = Field(default=None, min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    type: Literal["monitoring", "sensitive"] | None = None
    source: Literal["system", "custom"] | None = None
    weight: int | None = Field(default=None, ge=0, le=100)
    severity_weight: int | None = Field(default=None, ge=0, le=100)
    rule_config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class ForeignKeywordBulkPayload(BaseModel):
    keyword_ids: list[int] = Field(min_length=1, max_length=500)
    is_enabled: bool


class ForeignCollectionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_ids: list[int] | None = Field(default=None, max_length=50)
    all_sources: bool = False


class ForeignSourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    key: str = Field(min_length=1, max_length=64)
    feeds: list[str] = Field(min_length=1)
    language: Literal["en", "zh", "mixed", "unknown"] = "unknown"
    proxy_env: str | None = "FOREIGN_HTTP_PROXY"
    enabled: bool = False
    schedule_enabled: bool = False
    schedule_interval_minutes: int = Field(default=60, ge=5, le=10080)
    priority: int = Field(default=500, ge=0, le=9999)
    fetch_full_text: bool = False
    max_items: int = Field(default=100, ge=1, le=500)
    timeout: int = Field(default=15, ge=1, le=120)
    connect_timeout: float = Field(default=15, ge=0.1, le=120)
    read_timeout: float = Field(default=15, ge=0.1, le=120)
    request_interval: float = Field(default=0.5, ge=0, le=60)
    max_retries: int = Field(default=2, ge=0, le=5)
    max_content_length: int = Field(default=200_000, ge=100, le=1_000_000)
    respect_robots: bool = True

    @staticmethod
    def _check_full_text(value: bool) -> bool:
        if value:
            raise ValueError("fetch_full_text must remain false in the foreign manual phase")
        return value


class ForeignSourceUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    feeds: list[str] | None = Field(default=None, min_length=1)
    language: Literal["en", "zh", "mixed", "unknown"] | None = None
    proxy_env: str | None = "FOREIGN_HTTP_PROXY"
    enabled: bool | None = None
    schedule_enabled: bool | None = None
    schedule_interval_minutes: int | None = Field(default=None, ge=5, le=10080)
    priority: int | None = Field(default=None, ge=0, le=9999)
    fetch_full_text: bool | None = None
    max_items: int | None = Field(default=None, ge=1, le=500)
    timeout: int | None = Field(default=None, ge=1, le=120)
    connect_timeout: float | None = Field(default=None, ge=0.1, le=120)
    read_timeout: float | None = Field(default=None, ge=0.1, le=120)
    request_interval: float | None = Field(default=None, ge=0, le=60)
    max_retries: int | None = Field(default=None, ge=0, le=5)
    max_content_length: int | None = Field(default=None, ge=100, le=1_000_000)
    respect_robots: bool | None = None

    @staticmethod
    def _check_full_text(value: bool | None) -> bool | None:
        if value:
            raise ValueError("fetch_full_text must remain false in the foreign manual phase")
        return value


class ForeignSourceTestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: int | None = Field(default=None, ge=1)
    name: str = Field(default="Foreign source test", min_length=1, max_length=128)
    feeds: list[str] | None = None
    keywords: list[str] | None = None
    proxy_env: str | None = "FOREIGN_HTTP_PROXY"
    timeout: int = Field(default=15, ge=1, le=120)
    connect_timeout: float = Field(default=15, ge=0.1, le=120)
    read_timeout: float = Field(default=15, ge=0.1, le=120)
    max_items: int = Field(default=100, ge=1, le=500)
    max_retries: int = Field(default=2, ge=0, le=5)
    respect_robots: bool = False
    fetch_full_text: bool = False


class ForeignRiskAnalyzePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model_version: str = Field(default=RULE_MODEL_VERSION, min_length=1, max_length=64)


class ForeignRiskBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    foreign_opinion_ids: list[int] = Field(min_length=1, max_length=50)
    model_version: str = Field(default=RULE_MODEL_VERSION, min_length=1, max_length=64)


def _source_config(source: DataSource) -> dict:
    cfg, err = _parse_config_json(source.config_json or "{}")
    return cfg if not err and isinstance(cfg, dict) else {}


def _is_foreign_config(source: DataSource) -> bool:
    return _source_config(source).get("is_foreign") is True


def _safe_foreign_error(value: object) -> str | None:
    if not value:
        return None
    message = " ".join(str(value).split())
    lowered = message.casefold()
    if any(
        marker in lowered
        for marker in (
            "traceback", "sqlalchemy", "psycopg", "password", "token",
            "secret", "api key", "proxy", "connection string", "://", "@",
        )
    ):
        return "外网运行失败，详细错误已隐藏"
    return message[:240]


def _foreign_source_or_404(db: Session, source_id: int) -> DataSource:
    source = db.get(DataSource, source_id)
    if source is None or not _is_foreign_config(source):
        raise HTTPException(status_code=404, detail="Foreign data source not found")
    return source


def _foreign_source_item(source: DataSource) -> dict[str, Any]:
    cfg = _source_config(source)
    safe_config_keys = {
        "is_foreign", "collector", "source_name", "feeds", "language", "proxy_env", "keywords",
        "collection_mode", "max_items", "timeout", "max_content_length",
        "request_interval", "max_retries", "fetch_full_text", "connect_timeout",
        "read_timeout", "respect_robots",
    }
    safe_config = {key: cfg[key] for key in safe_config_keys if key in cfg}
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
        "language": cfg.get("language", "unknown"),
        "keywords": cfg.get("keywords") or [],
        "proxy_env": cfg.get("proxy_env"),
        # proxy_mode 由统一解析函数推导（含 FOREIGN_HTTP_PROXY/HTTPS_PROXY/HTTP_PROXY 回退），
        # 保证「实际采集使用的代理」与「UI 展示」完全一致；绝不包含代理 URL / 凭据。
        "proxy_mode": resolve_proxy_mode(
            proxy_env=cfg.get("proxy_env"),
            proxy_override=cfg.get("proxy"),
            use_direct=bool(cfg.get("use_direct")),
        ),
        # 向后兼容的布尔字段：是否实际走了非直连代理（direct_default 之外即为有代理）。
        "proxy_configured": resolve_proxy_mode(
            proxy_env=cfg.get("proxy_env"),
            proxy_override=cfg.get("proxy"),
            use_direct=bool(cfg.get("use_direct")),
        ) != "direct_default",
        "fetch_full_text": bool(cfg.get("fetch_full_text", False)),
        "max_items": cfg.get("max_items", 100),
        "timeout": cfg.get("timeout", 15),
        "connect_timeout": cfg.get("connect_timeout", cfg.get("timeout", 15)),
        "read_timeout": cfg.get("read_timeout", cfg.get("timeout", 15)),
        "request_interval": cfg.get("request_interval", 0.5),
        "max_retries": cfg.get("max_retries", 2),
        "max_content_length": cfg.get("max_content_length", 200_000),
        "respect_robots": bool(cfg.get("respect_robots", True)),
        # 验证状态（存储于 config_json，无新增表/列）：前端据此展示「未验证 / 已验证 / 失败」。
        "verified": bool(cfg.get("verified", False)),
        "last_probe_at": cfg.get("last_probe_at"),
        "last_probe_status": cfg.get("last_probe_status"),
        "last_probe_error_category": cfg.get("last_probe_error_category"),
        # Keep the legacy field for existing clients, but never echo arbitrary
        # source configuration that could contain a proxy URL or credential.
        "config_json": json.dumps(safe_config, ensure_ascii=False),
    }


def _foreign_source_runtime(db: Session, sources: list[DataSource]) -> dict[int, dict[str, Any]]:
    """Attach authoritative run, quality, and schedule fields to foreign sources.

    Foreign collection writes ``collector_name`` using ``DataSource.name`` and
    marks each row with ``scope='foreign'``. Keeping this join in the listing
    endpoint makes the management table independent of visualization grouping.
    """
    names = [source.name for source in sources]
    runs_by_name: dict[str, list[CollectorRun]] = {name: [] for name in names}
    if names:
        runs = db.scalars(
            select(CollectorRun)
            .where(
                CollectorRun.scope == "foreign",
                CollectorRun.collector_name.in_(names),
            )
            .order_by(CollectorRun.start_time.desc(), CollectorRun.id.desc())
        ).all()
        for run in runs:
            runs_by_name.setdefault(run.collector_name, []).append(run)

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    result: dict[int, dict[str, Any]] = {}
    for source in sources:
        all_runs = runs_by_name.get(source.name, [])
        recent_runs = [run for run in all_runs if run.start_time and run.start_time >= cutoff]
        latest = all_runs[0] if all_runs else None
        failed_streak = 0
        empty_streak = 0
        for run in all_runs:
            if run.status in {"failed", "error", "partial"} or (run.failed or 0) > 0:
                failed_streak += 1
            else:
                break
        for run in all_runs:
            if (run.fetched_raw or 0) == 0:
                empty_streak += 1
            else:
                break
        if latest is None:
            empty_fetch_risk = "unknown"
        elif empty_streak >= 3:
            empty_fetch_risk = "high"
        elif (latest.fetched_raw or 0) == 0:
            empty_fetch_risk = "warning"
        else:
            empty_fetch_risk = "normal"
        next_collect_time = source.next_collect_time
        # Older foreign sources may have been enabled before the scheduling
        # timestamp was introduced. Keep the read-only list useful without
        # mutating existing rows; the next update persists the canonical value.
        if source.enabled and source.schedule_enabled and next_collect_time is None:
            next_collect_time = datetime.now() + timedelta(minutes=source.schedule_interval_minutes)
        result[source.id] = {
            "latest_run_status": latest.status if latest else None,
            "latest_run_at": (
                (latest.end_time or latest.start_time).isoformat()
                if latest and (latest.end_time or latest.start_time)
                else None
            ),
            "next_collect_time": next_collect_time.isoformat() if next_collect_time else None,
            "collection_quality": {
                "empty_fetch_risk": empty_fetch_risk,
                "latest_fetched_raw": latest.fetched_raw if latest else None,
                "latest_created": latest.created if latest else None,
                "run_count": len(recent_runs),
                "success_rate": round(
                    sum(run.status == "success" for run in recent_runs) / len(recent_runs), 4
                ) if recent_runs else None,
                "consecutive_failed_count": failed_streak,
                "consecutive_empty_fetch_count": empty_streak,
            },
        }
    return result


def _rescore_foreign_worker(task: Task) -> dict:
    """后台任务：对全部国外舆情用最新敏感词库重新评分。"""
    from app.db.session import SessionLocal
    from app.services.foreign_risk_service import ForeignRiskService

    db = SessionLocal()
    try:
        return ForeignRiskService().rescore_all(db, task=task)
    finally:
        db.close()


def _trigger_rescore_if_sensitive(db: Session, ids: list[int], *, force: bool = False) -> None:
    """若涉及 sensitive 类型关键词变更，触发一次可控的后台重新评分。

    重新评分使用项目既有 task_manager，去重键避免并发重复执行；
    失败不影响关键词本身的写操作（best-effort）。

    force=True 用于「删除」场景：被删词已从表中移除，无法再用
    id 命中 sensitive 行，但调用方已知 was_sensitive，需强制触发重评分。
    """
    if not ids and not force:
        return
    if not force:
        has_sensitive = db.scalar(
            select(func.count())
            .select_from(ForeignKeyword)
            .where(ForeignKeyword.id.in_(ids), ForeignKeyword.type == "sensitive")
        )
        if not has_sensitive:
            return
    try:
        start_task("foreign_rescore", _rescore_foreign_worker, dedupe_key="foreign_rescore")
    except DuplicateTaskError:
        # 已有重新评分任务在执行，忽略重复触发。
        pass


@foreign_router.post("/opinions/rescore")
def rescore_foreign_opinions(
    request: Request,
    _: User = Depends(require_permission("foreign:keywords:write")),
    db: Session = Depends(get_db),
):
    """手动触发全部国外舆情重新评分（用最新启用的敏感词库）。

    后台任务执行，立即返回 task_id；前端轮询 GET /api/tasks/{task_id} 查看进度。
    """
    try:
        task_id = start_task("foreign_rescore", _rescore_foreign_worker, dedupe_key="foreign_rescore")
    except DuplicateTaskError:
        raise HTTPException(status_code=409, detail="已有国外舆情重新评分任务在执行")
    return {"task_id": task_id}


@foreign_router.get("/keywords")
def list_foreign_keywords(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    q: str | None = None,
    category: str | None = None,
    type_: str | None = Query(None, alias="type"),
    source: str | None = None,
    is_enabled: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:keywords:read")),
):
    items, total, _ = list_foreign_keyword_rows(
        db, page=page, size=size, q=q, category=category, type_=type_,
        source=source, is_enabled=is_enabled,
    )
    return {"items": items, "total": total, "page": page, "size": size}


@foreign_router.get("/keywords/categories")
def list_foreign_keyword_category_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:keywords:read")),
):
    return {"items": list_foreign_keyword_categories(db)}


@foreign_router.post("/keywords", status_code=201)
def create_foreign_keyword(
    payload: ForeignKeywordPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:keywords:write")),
    db: Session = Depends(get_db),
):
    word = payload.word.strip()
    if db.scalar(select(ForeignKeyword.id).where(ForeignKeyword.word == word)):
        raise HTTPException(status_code=409, detail=f"Foreign keyword already exists: {word}")
    with audit_write(
        db,
        action="CREATE",
        operator=current_user,
        request=request,
        resource_type="foreign_keyword",
        details={"word": word},
    ) as ctx:
        try:
            row = create_foreign_keyword_row(
                db, word=word, category=payload.category.strip() or "general",
                is_enabled=payload.is_enabled, type_=payload.type, source=payload.source,
                weight=payload.weight, severity_weight=payload.severity_weight,
                rule_config=payload.rule_config,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            if "uq_foreign_keywords_word" in str(exc) or "duplicate key" in str(exc).lower():
                raise HTTPException(status_code=409, detail=f"Foreign keyword already exists: {word}") from exc
            raise
        ctx["resource_id"] = str(row["id"])
    _trigger_rescore_if_sensitive(db, [row["id"]])
    return row


@foreign_router.patch("/keywords/{keyword_id}")
def update_foreign_keyword(
    keyword_id: int,
    payload: ForeignKeywordUpdatePayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:keywords:write")),
    db: Session = Depends(get_db),
):
    existing, _ = get_foreign_keyword_row(db, keyword_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Foreign keyword not found")
    values = payload.model_dump(exclude_unset=True)
    if "word" in values:
        values["word"] = values["word"].strip()
    if "category" in values:
        values["category"] = values["category"].strip() or "general"
    if "type" in values:
        values["type"] = values.pop("type")
    with audit_write(
        db,
        action="UPDATE",
        operator=current_user,
        request=request,
        resource_type="foreign_keyword",
        resource_id=str(keyword_id),
        details={"changes": list(values.keys())},
    ):
        try:
            result = update_foreign_keyword_row(db, keyword_id, values)
            db.commit()
        except Exception as exc:
            db.rollback()
            if "uq_foreign_keywords_word" in str(exc) or "duplicate key" in str(exc).lower():
                raise HTTPException(status_code=409, detail="Foreign keyword already exists") from exc
            raise
    _trigger_rescore_if_sensitive(db, [keyword_id])
    return result


@foreign_router.post("/keywords/bulk-status")
def bulk_update_foreign_keywords(
    payload: ForeignKeywordBulkPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:keywords:write")),
    db: Session = Depends(get_db),
):
    changed = 0
    with audit_write(
        db, action="BULK_UPDATE", operator=current_user, request=request,
        resource_type="foreign_keyword", details=payload.model_dump(),
    ):
        for keyword_id in payload.keyword_ids:
            changed += int(bool(update_foreign_keyword_row(
                db, keyword_id, {"is_enabled": payload.is_enabled}
            )))
        db.commit()
    _trigger_rescore_if_sensitive(db, payload.keyword_ids)
    return {"changed": changed, "is_enabled": payload.is_enabled}


@foreign_router.delete("/keywords/{keyword_id}")
def delete_foreign_keyword(
    keyword_id: int,
    request: Request,
    current_user: User = Depends(require_permission("foreign:keywords:write")),
    db: Session = Depends(get_db),
):
    row, _ = get_foreign_keyword_row(db, keyword_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign keyword not found")
    # 删除前记住类型，便于敏感词删除后触发重新评分。
    was_sensitive = row.get("type") == "sensitive"
    with audit_write(
        db,
        action="DELETE",
        operator=current_user,
        request=request,
        resource_type="foreign_keyword",
        resource_id=str(keyword_id),
        details={"word": row["word"]},
    ):
        delete_foreign_keyword_row(db, keyword_id)
        db.commit()
    if was_sensitive:
        _trigger_rescore_if_sensitive(db, [keyword_id], force=True)
    return {"detail": "Foreign keyword deleted", "id": keyword_id}


@foreign_router.get("/sources")
def list_foreign_sources(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:sources:read")),
):
    candidates = db.scalars(
        select(DataSource).order_by(DataSource.priority.asc(), DataSource.id.asc())
    ).all()
    rows = [row for row in candidates if _is_foreign_config(row)]
    if q:
        needle = q.casefold()
        rows = [row for row in rows if needle in row.name.casefold() or needle in row.key.casefold()]
    total = len(rows)
    offset = (page - 1) * size
    runtime = _foreign_source_runtime(db, rows[offset:offset + size])
    items = []
    for row in rows[offset:offset + size]:
        item = _foreign_source_item(row)
        item.update(runtime.get(row.id, {}))
        items.append(item)
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_router.get("/sources/approved")
def list_approved_foreign_sources(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:sources:read")),
):
    """Return the backend-owned manual collection scope.

    Enabled foreign sources are the approved scope for a selected collection.
    Domestic and disabled sources never leave this endpoint.
    """
    rows = db.scalars(select(DataSource).order_by(DataSource.priority.asc(), DataSource.id.asc())).all()
    approved_rows = [row for row in rows if row.enabled and _is_foreign_config(row)]
    runtime = _foreign_source_runtime(db, approved_rows)
    approved = []
    for row in approved_rows:
        item = _foreign_source_item(row)
        item.update(runtime.get(row.id, {}))
        approved.append(item)
    return {"items": approved, "ids": [item["id"] for item in approved], "total": len(approved)}


@foreign_router.post("/sources", status_code=201)
def create_foreign_source(
    payload: ForeignSourcePayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:sources:write")),
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
        "language": payload.language,
        "proxy_env": payload.proxy_env,
        "keywords": get_foreign_monitoring_keywords(db),
        "collection_mode": "foreign",
        "fetch_full_text": False,
        "max_items": payload.max_items,
        "timeout": payload.timeout,
        "connect_timeout": payload.connect_timeout,
        "read_timeout": payload.read_timeout,
        "request_interval": payload.request_interval,
        "max_retries": payload.max_retries,
        "max_content_length": payload.max_content_length,
        "respect_robots": payload.respect_robots,
        # 创建期不做真实网络探测：保存为「未验证」状态，由独立「测试连接」接口验证。
        "verified": False,
    }
    error = _validate_foreign_config(cfg)
    if error:
        raise HTTPException(status_code=422, detail=error)
    if payload.fetch_full_text:
        raise HTTPException(status_code=422, detail="fetch_full_text must remain false in the foreign manual phase")
    try:
        # 创建期仅做结构 + SSRF 静态校验 + 采集器装配，不发起网络请求。
        # 目标站点宕机 / 代理抖动 / 暂时无条目都不会阻塞保存。
        _assert_foreign_source_constructable(
            feeds=cfg["feeds"], keywords=cfg["keywords"], name=payload.name,
            proxy_env=payload.proxy_env, timeout=payload.timeout,
            connect_timeout=payload.connect_timeout, read_timeout=payload.read_timeout,
            max_items=payload.max_items, max_retries=payload.max_retries,
            respect_robots=payload.respect_robots,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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
            schedule_enabled=payload.schedule_enabled,
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
    payload: ForeignSourceUpdatePayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:sources:write")),
    db: Session = Depends(get_db),
):
    source = _foreign_source_or_404(db, source_id)
    changes = payload.model_dump(exclude_unset=True)
    cfg = _source_config(source)
    next_name = str(changes.get("name", source.name)).strip() or source.name
    cfg["keywords"] = get_foreign_monitoring_keywords(db)
    if "feeds" in changes:
        cfg["feeds"] = changes["feeds"]
    if "language" in changes:
        cfg["language"] = changes["language"]
    if "proxy_env" in changes:
        cfg["proxy_env"] = changes["proxy_env"]
    if "fetch_full_text" in changes and changes["fetch_full_text"]:
        raise HTTPException(status_code=422, detail="fetch_full_text must remain false in the foreign manual phase")
    cfg["fetch_full_text"] = False
    if "max_items" in changes:
        cfg["max_items"] = int(changes["max_items"])
    for key in (
        "timeout", "connect_timeout", "read_timeout", "request_interval",
        "max_retries", "max_content_length", "respect_robots",
    ):
        if key in changes:
            cfg[key] = changes[key]
    if "name" in changes:
        cfg["source_name"] = next_name
    error = _validate_foreign_config(cfg)
    if error:
        raise HTTPException(status_code=422, detail=error)
    # 连接相关配置发生变化时，旧探测结果失效 -> 重置为「未验证」，由「测试连接」重新验证。
    connection_keys = (
        "feeds", "proxy_env", "timeout", "connect_timeout", "read_timeout",
        "max_retries", "max_items", "respect_robots", "language", "fetch_full_text",
    )
    if any(key in changes for key in connection_keys):
        cfg["verified"] = False
        cfg.pop("last_probe_at", None)
        cfg.pop("last_probe_status", None)
        cfg.pop("last_probe_error_category", None)
    try:
        # 编辑期同样不发起网络请求，仅做结构 + SSRF 静态校验 + 采集器装配。
        _assert_foreign_source_constructable(
            feeds=cfg.get("feeds") or [], keywords=cfg.get("keywords"),
            name=next_name, proxy_env=cfg.get("proxy_env"),
            timeout=int(cfg.get("timeout", 15)),
            connect_timeout=float(cfg.get("connect_timeout", cfg.get("timeout", 15))),
            read_timeout=float(cfg.get("read_timeout", cfg.get("timeout", 15))),
            max_items=int(cfg.get("max_items", 100)), max_retries=int(cfg.get("max_retries", 2)),
            respect_robots=bool(cfg.get("respect_robots", True)),
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if changes.get("enabled") is True or changes.get("schedule_enabled") is True:
        source_enabled = changes.get("enabled", source.enabled)
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
        details={"changes": list(changes.keys())},
    ):
        if "enabled" in changes:
            source.enabled = bool(changes["enabled"])
        if "name" in changes:
            source.name = next_name
        if "schedule_enabled" in changes:
            source.schedule_enabled = bool(changes["schedule_enabled"])
        if "schedule_interval_minutes" in changes:
            source.schedule_interval_minutes = max(
                5, int(changes["schedule_interval_minutes"])
            )
        if "priority" in changes:
            source.priority = int(changes["priority"])
        # Keep the management view's next-run column authoritative. A foreign
        # source is scheduled independently, so its next run is recalculated
        # whenever scheduling is toggled or its interval changes.
        if source.schedule_enabled:
            source.next_collect_time = (
                datetime.now() + timedelta(minutes=source.schedule_interval_minutes)
            )
        elif "schedule_enabled" in changes or "enabled" in changes:
            source.next_collect_time = None
        source.config_json = json.dumps(cfg, ensure_ascii=False)
        db.commit()
    db.refresh(source)
    return _foreign_source_item(source)


@foreign_router.post("/sources/test")
def test_foreign_source_connection(
    payload: ForeignSourceTestPayload,
    _: User = Depends(require_permission("foreign:sources:test")),
    db: Session = Depends(get_db),
):
    if payload.fetch_full_text:
        raise HTTPException(status_code=422, detail="fetch_full_text must remain false in the foreign manual phase")
    try:
        result = test_foreign_source(
            db, source_id=payload.source_id, name=payload.name,
            feeds=payload.feeds, keywords=payload.keywords,
            proxy_env=payload.proxy_env, timeout=payload.timeout,
            connect_timeout=payload.connect_timeout, read_timeout=payload.read_timeout,
            max_items=payload.max_items, max_retries=payload.max_retries,
            respect_robots=payload.respect_robots,
            persist=True,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result


@foreign_router.get("/sources/{source_id}/runs")
def list_foreign_source_runs(
    source_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:sources:read")),
):
    source = _foreign_source_or_404(db, source_id)
    stmt = select(CollectorRun).where(
        CollectorRun.scope == "foreign",
        CollectorRun.collector_name == source.name,
    )
    if status:
        stmt = stmt.where(CollectorRun.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(CollectorRun.start_time.desc(), CollectorRun.id.desc())
        .offset((page - 1) * size).limit(size)
    ).all()
    return {"items": [_foreign_run_item(row) for row in rows], "total": total, "page": page, "size": size}


def _foreign_opinion_item(row: ForeignOpinion) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_id": row.source_id,
        "source_key": row.source_key,
        "source_name_snapshot": row.source_name_snapshot,
        "title": row.title,
        "summary": sanitize_foreign_html(row.summary),
        "content": sanitize_foreign_html(row.content),
        "url": row.url,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "collected_at": row.collected_at.isoformat() if row.collected_at else None,
        "matched_keywords": row.matched_keywords or [],
        "content_hash": row.content_hash,
        "duplicate_of_id": row.duplicate_of_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "current_risk_source": row.current_risk_source or "rule",
        "current_risk_score": row.current_risk_score,
        "current_risk_level": row.current_risk_level or "low",
        "current_ai_result_id": row.current_ai_result_id,
        "current_risk_updated_at": row.current_risk_updated_at.isoformat() if row.current_risk_updated_at else None,
    }


def _foreign_opinion_detail(
    db: Session, row: ForeignOpinion, *, risk_source: RiskSource = CURRENT_SOURCE
) -> dict[str, Any]:
    payload = _foreign_opinion_item(row)
    payload.update(resolve_one(db, row.id, risk_source=risk_source))
    current_rule = db.scalar(
        select(ForeignRiskResult)
        .where(
            ForeignRiskResult.foreign_opinion_id == row.id,
            ForeignRiskResult.is_current.is_(True),
        )
        .order_by(ForeignRiskResult.id.desc())
    )
    payload["rule_result"] = _foreign_risk_item(current_rule, row) if current_rule else None
    payload["ai_result"] = None
    payload["ai_alert_admission"] = None
    payload["ai_alert_admission_actions"] = []
    if inspect(db.get_bind()).has_table("foreign_ai_results"):
        ai_result = db.scalar(
            select(ForeignAIResult)
            .where(
                ForeignAIResult.foreign_opinion_id == row.id,
                ForeignAIResult.status == "completed",
            )
            .order_by(ForeignAIResult.id.desc())
        )
        payload["ai_result"] = serialize_ai_result(ai_result)
    runs = db.scalars(
        select(ForeignAnalysisRun)
        .where(ForeignAnalysisRun.foreign_opinion_id == row.id)
        .order_by(ForeignAnalysisRun.started_at.desc(), ForeignAnalysisRun.id.desc())
        .limit(50)
    ).all()
    payload["analysis_runs"] = [_foreign_analysis_run_item(run) for run in runs]
    # Link the most recent batch run that produced / updated this opinion's AI
    # result so the "AI 研判运行记录" dialog can surface the batch record and
    # so a single AI result is correctly associated with its batch_run_id.
    latest_batch = db.scalar(
        select(ForeignAnalysisRun.batch_run_id)
        .where(
            ForeignAnalysisRun.foreign_opinion_id == row.id,
            ForeignAnalysisRun.batch_run_id.is_not(None),
        )
        .order_by(ForeignAnalysisRun.id.desc())
        .limit(1)
    )
    if latest_batch is None:
        latest_batch = db.scalar(
            select(ForeignManualReview.batch_run_id)
            .where(
                ForeignManualReview.foreign_opinion_id == row.id,
                ForeignManualReview.batch_run_id.is_not(None),
            )
            .order_by(ForeignManualReview.id.desc())
            .limit(1)
        )
    payload["current_batch_run_id"] = latest_batch
    return payload


@foreign_router.get("/opinions")
def list_foreign_opinions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    keyword: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    language: str | None = None,
    risk_level: str | None = None,
    analysis_status: str | None = None,
    risk_source: RiskSource = Query(CURRENT_SOURCE),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:opinions:read")),
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
    if language or analysis_status:
        sub = select(ForeignRiskResult.foreign_opinion_id).where(
            ForeignRiskResult.is_current.is_(True)
        )
        if language:
            sub = sub.where(ForeignRiskResult.language == language)
        if analysis_status:
            sub = sub.where(ForeignRiskResult.analysis_status == analysis_status)
        stmt = stmt.where(ForeignOpinion.id.in_(sub))
    if risk_level:
        # The filter must use the same selected source as the serialized
        # display_risk column. Formal alert/event snapshots remain separate.
        query_source = risk_source
        if risk_source == "ai" and not inspect(db.get_bind()).has_table("foreign_ai_results"):
            # During a rolling deployment the AI table may not exist yet; the
            # resolver will mark the serialized view as a rule fallback.
            query_source = RULE_SOURCE
        stmt = stmt.where(
            effective_risk_level_expression(risk_source=query_source) == risk_level
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
    items = [_foreign_opinion_item(row) for row in rows]
    # One resolver call for the whole page: the list and the alert center then
    # render exactly the same effective risk.
    attach_effective_risk(db, items, risk_source=risk_source)
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_router.get("/opinions/sources")
def list_foreign_opinion_sources(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:opinions:read")),
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
    risk_source: RiskSource = Query(CURRENT_SOURCE),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:opinions:read")),
):
    row = db.get(ForeignOpinion, opinion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign opinion not found")
    return _foreign_opinion_detail(db, row, risk_source=risk_source)


@foreign_router.get("/opinions/{opinion_id}/original")
def get_foreign_opinion_original(
    opinion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:opinions:read")),
):
    row = db.get(ForeignOpinion, opinion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign opinion not found")
    return {
        "id": row.id,
        "title": row.title,
        # This legacy route remains available for old clients but never
        # exposes the stored publisher HTML.
        "content": sanitize_foreign_html(row.content),
        "url": row.url,
        "source_name_snapshot": row.source_name_snapshot,
    }


@foreign_router.get("/opinions/{opinion_id}/detail")
def get_foreign_opinion_detail(
    opinion_id: int,
    risk_source: RiskSource = Query(CURRENT_SOURCE),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:opinions:read")),
):
    row = db.get(ForeignOpinion, opinion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign opinion not found")
    return _foreign_opinion_detail(db, row, risk_source=risk_source)


@foreign_router.post("/opinions/{opinion_id}/ai-analyze")
def analyze_foreign_opinion_ai(
    opinion_id: int,
    force: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:ai:analyze")),
):
    """The one and only manual AI review entry point.

    Collection, scheduling and list queries never reach this handler; a human
    request with ``foreign:ai:analyze`` is always required. Repeated calls on
    unchanged content reuse the stored evaluation instead of calling the
    provider again.
    """
    if not inspect(db.get_bind()).has_table("foreign_ai_results"):
        raise HTTPException(status_code=503, detail="Foreign AI storage migration is not applied")
    try:
        result, reused = ForeignAIService().analyze_opinion_manual(
            db, opinion_id, force=force
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Single AI analysis enters the shared manual-review lifecycle, identical to
    # the batch path. AI never creates a formal event/alert here.
    review, review_created = ensure_foreign_manual_review(
        db, opinion_id, result.id, batch_run_id=None, force=force
    )
    db.commit()
    db.refresh(review)
    payload = serialize_ai_result(result) or {}
    payload["reused"] = reused
    # Return the canonical rule view alongside the historical AI result.
    payload.update(resolve_one(db, opinion_id))
    payload.update(
        {
            "analysis_id": str(result.id),
            "review_id": review.id,
            "review_status": review.review_status,
            "review_created": review_created,
            "event_preview": review.event_preview or {},
            "alert_preview": review.alert_preview or {},
            "message": "AI 研判完成，已进入人工复核",
        }
    )
    return payload


@foreign_router.post("/opinions/{opinion_id}/ai-alert-admission")
def set_foreign_ai_alert_admission(
    opinion_id: int,
    payload: ForeignAIAlertAdmissionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:ai-admit")),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=410,
        detail="Foreign AI results are historical only; AI alert admission is retired",
    )


def _foreign_ai_batch_selection(db: Session, payload: ForeignAIBatchPayload) -> list[ForeignOpinion]:
    if payload.scope == "time" and not (payload.date_from or payload.current_filters.get("date_from")):
        raise HTTPException(status_code=422, detail="Time scope requires date_from")
    if payload.scope == "time" and not (payload.date_to or payload.current_filters.get("date_to")):
        raise HTTPException(status_code=422, detail="Time scope requires date_to")
    filters = payload.current_filters if payload.use_current_filters else {}
    stmt = select(ForeignOpinion)
    if payload.opinion_ids:
        stmt = stmt.where(ForeignOpinion.id.in_(sorted(set(payload.opinion_ids))))
    source = filters.get("source")
    keyword = filters.get("keyword")
    q = filters.get("q")
    language = filters.get("language")
    risk_level = filters.get("risk_level")
    analysis_status = filters.get("analysis_status")
    risk_source = filters.get("risk_source") or RULE_SOURCE
    date_from = payload.date_from or filters.get("date_from")
    date_to = payload.date_to or filters.get("date_to")
    if source:
        stmt = stmt.where(ForeignOpinion.source_name_snapshot == str(source))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(ForeignOpinion.title.ilike(like), ForeignOpinion.summary.ilike(like), ForeignOpinion.content.ilike(like)))
    if keyword:
        stmt = stmt.where(cast(ForeignOpinion.matched_keywords, String).ilike(f"%{keyword}%"))
    if language or analysis_status:
        sub = select(ForeignRiskResult.foreign_opinion_id).where(ForeignRiskResult.is_current.is_(True))
        if language:
            sub = sub.where(ForeignRiskResult.language == str(language))
        if analysis_status:
            sub = sub.where(ForeignRiskResult.analysis_status == str(analysis_status))
        stmt = stmt.where(ForeignOpinion.id.in_(sub))
    if risk_level:
        stmt = stmt.where(
            effective_risk_level_expression(
                risk_source=risk_source if risk_source in {CURRENT_SOURCE, RULE_SOURCE, "ai"} else CURRENT_SOURCE
            ) == str(risk_level)
        )
    if date_from:
        try:
            stmt = stmt.where(ForeignOpinion.published_at >= datetime.strptime(str(date_from), "%Y-%m-%d"))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="date_from must be YYYY-MM-DD") from exc
    if date_to:
        try:
            end = datetime.strptime(str(date_to), "%Y-%m-%d") + timedelta(days=1)
            stmt = stmt.where(ForeignOpinion.published_at < end)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="date_to must be YYYY-MM-DD") from exc
    rows = list(db.scalars(stmt.order_by(ForeignOpinion.published_at.desc(), ForeignOpinion.id.desc())).all())
    if payload.only_unanalyzed and not payload.force and rows and inspect(db.get_bind()).has_table("foreign_ai_results"):
        completed = set(db.scalars(select(ForeignAIResult.foreign_opinion_id).where(
            ForeignAIResult.foreign_opinion_id.in_([row.id for row in rows]), ForeignAIResult.status == "completed",
        )).all())
        rows = [row for row in rows if row.id not in completed]
    if payload.scope == "count":
        rows = rows[: payload.recent_n]
    elif payload.scope == "time":
        rows = rows
    return rows


def _preview_foreign_candidate_count(db: Session, opinion_ids: list[int]) -> int:
    """统计外网「可能影响的预警」候选数：规则风险命中 + AI 分命中（按舆情去重）。

    与 ForeignAlertService.evaluate(dry_run=True) 并列存在：不改动 evaluate 的
    内部逻辑，也绝不创建 ForeignAlert。AI 分只计入「候选」口径，其正式化仍必须
    经过人工复核闸门，因此本函数不改变既有边界。统计基于**已存在**的规则风险
    结果与已完成 AI 结论，属于预估值。
    """
    if not opinion_ids:
        return 0
    from app.models.foreign_alert_rule import ForeignAlertRule
    from app.services.foreign_alert_service import _current_risk_rows, _risk_matches

    ids = {int(value) for value in opinion_ids}
    matched: set[int] = set()
    rules = list(
        db.scalars(select(ForeignAlertRule).where(ForeignAlertRule.is_enabled.is_(True))).all()
    )
    risk_rules = [
        rule
        for rule in rules
        if rule.rule_type in {"risk_score", "risk_level", "risk_category"}
    ]
    if risk_rules:
        for result, opinion in _current_risk_rows(db):
            if opinion.id not in ids or opinion.id in matched:
                continue
            for rule in risk_rules:
                try:
                    hit = _risk_matches(rule, result)
                except ValueError:
                    continue
                if hit:
                    matched.add(int(opinion.id))
                    break
    thresholds: list[float] = []
    for rule in rules:
        if rule.rule_type != "ai_risk_score":
            continue
        conditions = rule.conditions or {}
        threshold = conditions.get("threshold", conditions.get("min_score"))
        if threshold is None:
            continue
        try:
            thresholds.append(float(threshold))
        except (TypeError, ValueError):
            continue
    if thresholds and inspect(db.get_bind()).has_table("foreign_ai_results"):
        floor = min(thresholds)
        ai_rows = db.execute(
            select(ForeignAIResult.foreign_opinion_id, ForeignAIResult.risk_score).where(
                ForeignAIResult.foreign_opinion_id.in_(list(ids)),
                ForeignAIResult.status == "completed",
                ForeignAIResult.risk_score.is_not(None),
            )
        ).all()
        for opinion_id, score in ai_rows:
            if opinion_id is None or score is None or int(opinion_id) in matched:
                continue
            try:
                if float(score) >= floor:
                    matched.add(int(opinion_id))
            except (TypeError, ValueError):
                continue
    return len(matched)


def _preview_foreign_event_candidate_count(db: Session, opinion_ids: list[int]) -> int:
    """纯只读预估「可能成为新事件的候选」条数。

    只统计所选舆情中尚未通过 foreign_event_opinions 关联到任何事件的条数，
    不调用 ForeignEventService.rebuild_candidates（该函数会写入 foreign_event_runs
    运行记录），不创建 ForeignEventCandidate。属预估值，仅用于预览展示。
    """
    if not opinion_ids:
        return 0
    ids = {int(v) for v in opinion_ids}
    linked = set(
        db.scalars(
            select(ForeignEventOpinion.foreign_opinion_id).where(
                ForeignEventOpinion.foreign_opinion_id.in_(list(ids))
            )
        ).all()
    )
    return len(ids - linked)


def _foreign_ai_batch_preview(db: Session, payload: ForeignAIBatchPayload) -> dict[str, Any]:
    rows = _foreign_ai_batch_selection(db, payload)
    all_rows = rows
    if payload.only_unanalyzed:
        all_rows = _foreign_ai_batch_selection(db, payload.model_copy(update={"only_unanalyzed": False}))
    all_ids = [row.id for row in all_rows]
    completed_count = 0
    if all_ids and inspect(db.get_bind()).has_table("foreign_ai_results"):
        completed_count = int(db.scalar(select(func.count()).select_from(ForeignAIResult).where(
            ForeignAIResult.foreign_opinion_id.in_(all_ids), ForeignAIResult.status == "completed"
        )) or 0)
    token_estimate = sum(max(1, len("\n".join(part.strip() for part in (row.title, row.summary, row.content) if part and part.strip())) // 4) for row in rows)
    risk_counts = {level: 0 for level in ("high", "medium", "low", "unknown")}
    for row in rows:
        try:
            risk = resolve_one(db, row.id).get("rule_risk") or {}
        except Exception:
            risk = {}
        risk_counts[risk.get("risk_level") or "unknown"] = risk_counts.get(risk.get("risk_level") or "unknown", 0) + 1
    possible_event_count = 0
    possible_alert_count = 0
    if rows:
        # Phase 2 预览只读化：移除原先的 rebuild_candidates(commit=True) 与
        # evaluate(dry_run=True) 调用。两者都会在预览阶段向 foreign_event_runs /
        # foreign_alert_runs 写入运行（审计）记录，违反「预览不写库」约束。
        # 改为纯 SELECT 统计，不调用 AI、不创建 ForeignAlert / ForeignAIResult /
        # ForeignRiskResult / 候选记录 / 运行记录；异常时回退为 0，保证接口不 500。
        try:
            possible_event_count = _preview_foreign_event_candidate_count(
                db, [row.id for row in rows]
            )
        except Exception:
            possible_event_count = 0
        try:
            possible_alert_count = _preview_foreign_candidate_count(
                db, [row.id for row in rows]
            )
        except Exception:
            possible_alert_count = 0
    return {
        "matched_count": len(all_rows),
        "existing_ai_result_count": completed_count,
        "pending_analysis_count": len(rows),
        "estimated_token_usage": token_estimate,
        "estimated_duration_seconds": max(1, len(rows) * 2),
        "estimated_cost": None,
        "risk_level_counts": risk_counts,
        "possible_event_count": possible_event_count,
        "possible_alert_count": possible_alert_count,
        "filters": payload.model_dump(mode="json"),
        "opinion_ids": [row.id for row in rows],
        "token_budget": payload.token_budget,
        "token_budget_exceeded": token_estimate > payload.token_budget,
    }


def _run_foreign_ai_batch(task: Task, opinion_ids: list[int], force: bool, batch_run_id: str) -> dict[str, Any]:
    db = SessionLocal()
    processed = success = failed = skipped = 0
    failures: list[dict[str, Any]] = []
    try:
        total = len(opinion_ids)
        run = db.scalar(select(ForeignAIBatchRun).where(ForeignAIBatchRun.run_id == batch_run_id))
        if run:
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            db.commit()
        for opinion_id in opinion_ids:
            if task.cancel_requested:
                skipped += total - processed
                break
            processed += 1
            task.progress = int((processed - 1) / total * 100) if total else 100
            task.step = f"Foreign AI review {processed}/{total}"
            if run:
                run.processed_count = processed
                run.success_count = success
                run.failed_count = failed
                run.skipped_count = skipped
                db.commit()
            try:
                result, reused = ForeignAIService().analyze_opinion_manual(
                    db, opinion_id, force=force, batch_run_id=batch_run_id
                )
                if result.status == "completed":
                    success += 1
                    # Single and batch share the same review lifecycle.
                    review, _ = ensure_foreign_manual_review(
                        db, opinion_id, result.id, batch_run_id=batch_run_id, force=force
                    )
                    db.commit()
                else:
                    failed += 1
                    failures.append({"opinion_id": opinion_id, "error": result.error_message or "AI analysis failed"})
            except Exception as exc:  # noqa: BLE001
                failed += 1
                failures.append({"opinion_id": opinion_id, "error": _safe_foreign_error(exc)})
        event_preview: dict[str, Any] = {"candidate_count": 0, "items": [], "requires_manual_confirmation": True}
        alert_preview: dict[str, Any] = {"triggered_count": 0, "deduplicated_count": 0, "requires_manual_confirmation": True}
        try:
            event_run, _, event_items = ForeignEventService().rebuild_candidates(
                db, user_id=None, dry_run=True, opinion_ids=opinion_ids, commit=True
            )
            event_preview = {"run_id": event_run.id, "candidate_count": len(event_items), "items": event_items, "requires_manual_confirmation": True}
        except Exception as exc:  # noqa: BLE001
            event_preview["error"] = _safe_foreign_error(exc)
        try:
            alert_run = ForeignAlertService.evaluate(db, user_id=None, dry_run=True, max_items=200, opinion_ids=opinion_ids)
            alert_preview = {"run_id": alert_run.id, "triggered_count": alert_run.triggered_count, "deduplicated_count": alert_run.deduplicated_count, "requires_manual_confirmation": True}
        except Exception as exc:  # noqa: BLE001
            alert_preview["error"] = _safe_foreign_error(exc)
        for review in db.scalars(select(ForeignManualReview).where(ForeignManualReview.batch_run_id == batch_run_id)).all():
            scoped_event = dict(event_preview)
            scoped_event["items"] = [item for item in (event_preview.get("items") or []) if review.foreign_opinion_id in (item.get("opinion_ids") or [])]
            review.event_preview = scoped_event
            ai_candidate_count = int(
                db.scalar(
                    select(func.count()).select_from(ForeignAIAlertCandidate).where(
                        ForeignAIAlertCandidate.review_id == review.id
                    )
                ) or 0
            )
            review.alert_preview = {
                "candidate_count": ai_candidate_count,
                "requires_manual_confirmation": True,
            }
        db.commit()
        result = {"run_id": batch_run_id, "processed_count": processed, "success_count": success,
                "failed_count": failed, "skipped_count": skipped, "failures": failures,
                "status": "cancelled" if task.cancel_requested else ("partial" if failed else "success"),
                "event_preview": event_preview, "alert_preview": alert_preview}
        if run:
            run.processed_count = processed; run.success_count = success; run.failed_count = failed
            run.skipped_count = skipped; run.failures = failures; run.event_preview = event_preview
            run.alert_preview = alert_preview; run.status = result["status"]
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        return result
    finally:
        db.close()


@foreign_router.post("/ai-analysis/batch/preview")
def preview_foreign_ai_batch(payload: ForeignAIBatchPayload, db: Session = Depends(get_db), _: User = Depends(require_permission("foreign:ai:analyze"))):
    if not inspect(db.get_bind()).has_table("foreign_ai_results"):
        raise HTTPException(status_code=503, detail="Foreign AI storage migration is not applied")
    try:
        return _foreign_ai_batch_preview(db, payload)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        # Preview is advisory and must never expose a raw database/provider
        # traceback to the browser. Keep the request usable even when an
        # optional impact calculator is unavailable during a rolling deploy.
        return {
            "matched_count": 0,
            "existing_ai_result_count": 0,
            "pending_analysis_count": 0,
            "estimated_token_usage": 0,
            "estimated_duration_seconds": 0,
            "estimated_cost": None,
            "risk_level_counts": {"high": 0, "medium": 0, "low": 0, "unknown": 0},
            "possible_event_count": 0,
            "possible_alert_count": 0,
            "filters": payload.model_dump(mode="json"),
            "opinion_ids": [],
            "token_budget": payload.token_budget,
            "token_budget_exceeded": False,
            "preview_warning": f"Foreign AI preview temporarily unavailable: {_safe_foreign_error(exc)}",
        }


@foreign_router.post("/ai-analysis/batch")
def start_foreign_ai_batch(payload: ForeignAIBatchPayload, request: Request, current_user: User = Depends(require_permission("foreign:ai:analyze")), db: Session = Depends(get_db)):
    if payload.scope == "full" and not payload.full_confirmation:
        raise HTTPException(status_code=422, detail="Full foreign AI analysis requires explicit confirmation")
    preview = _foreign_ai_batch_preview(db, payload)
    if not preview["opinion_ids"]:
        raise HTTPException(status_code=422, detail="No foreign opinions match the batch selection")
    if preview["token_budget_exceeded"]:
        raise HTTPException(status_code=422, detail="Estimated token usage exceeds the configured batch budget")
    batch_run_id = uuid.uuid4().hex
    run = ForeignAIBatchRun(
        run_id=batch_run_id, scope=payload.scope,
        filters_snapshot=preview.get("filters") or {}, opinion_ids=preview["opinion_ids"],
        total_count=len(preview["opinion_ids"]), estimated_token_usage=preview["estimated_token_usage"],
        created_by=current_user.id, status="pending",
    )
    db.add(run)
    db.flush()
    # Commit the durable run before starting the worker. The task manager can
    # execute immediately on another thread; without this commit the worker's
    # independent SessionLocal transaction cannot see the run row.
    db.commit()
    dedupe_key = hashlib.sha256(json.dumps({"ids": preview["opinion_ids"], "force": payload.force}, sort_keys=True).encode()).hexdigest()
    try:
        task_id = start_task("foreign-ai-analysis", _run_foreign_ai_batch, preview["opinion_ids"], payload.force, batch_run_id, dedupe_key=dedupe_key)
    except DuplicateTaskError as exc:
        raise HTTPException(status_code=409, detail="Equivalent foreign AI batch is already running") from exc
    _FOREIGN_AI_BATCH_TASKS[batch_run_id] = task_id
    _FOREIGN_AI_BATCH_META[batch_run_id] = {"run_id": batch_run_id, "task_id": task_id, "total_count": len(preview["opinion_ids"]), "estimated_token_usage": preview["estimated_token_usage"], "started_at": datetime.now(timezone.utc).isoformat()}
    run.task_id = task_id
    log_operation(db, action="FOREIGN_AI_BATCH_START", operator=current_user, request=request, resource_type="foreign_ai_batch", resource_id=batch_run_id, details={"task_id": task_id, **preview})
    db.commit()
    return {
        **_FOREIGN_AI_BATCH_META[batch_run_id],
        "status": "pending",
        "matched_count": preview["matched_count"],
        "pending_analysis_count": preview["pending_analysis_count"],
        "processed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
    }


def _batch_item(row: ForeignAIBatchRun) -> dict[str, Any]:
    return {"run_id": row.run_id, "task_id": row.task_id, "scope": row.scope,
            "filters": row.filters_snapshot or {}, "opinion_ids": row.opinion_ids or [],
            "total_count": row.total_count, "processed_count": row.processed_count,
            "success_count": row.success_count, "failed_count": row.failed_count,
            "skipped_count": row.skipped_count, "status": row.status,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
            "estimated_token_usage": row.estimated_token_usage, "actual_token_usage": row.actual_token_usage,
            "failures": row.failures or [], "event_preview": row.event_preview or {},
            "alert_preview": row.alert_preview or {}, "created_by": row.created_by}

@foreign_router.get("/ai-analysis/batches")
def list_foreign_ai_batches(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), _: User = Depends(require_permission("foreign:ai:batch:read"))):
    stmt = select(ForeignAIBatchRun).order_by(ForeignAIBatchRun.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = list(db.scalars(stmt).all())
    total = db.scalar(select(func.count()).select_from(ForeignAIBatchRun)) or 0
    return {"items": [_batch_item(row) for row in rows], "total": total, "page": page, "size": size}

@foreign_router.get("/ai-analysis/batch/{run_id}")
def get_foreign_ai_batch(run_id: str, db: Session = Depends(get_db), _: User = Depends(require_permission("foreign:ai:batch:read"))):
    row = db.scalar(select(ForeignAIBatchRun).where(ForeignAIBatchRun.run_id == run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign AI batch not found")
    task = get_task(row.task_id) if row.task_id else None
    if task is not None and task.result:
        result = task.result
        row.processed_count = result.get("processed_count", row.processed_count)
        row.success_count = result.get("success_count", row.success_count)
        row.failed_count = result.get("failed_count", row.failed_count)
        row.skipped_count = result.get("skipped_count", row.skipped_count)
        row.failures = result.get("failures", row.failures)
        row.event_preview = result.get("event_preview", row.event_preview)
        row.alert_preview = result.get("alert_preview", row.alert_preview)
        if task.status in ("success", "failed", "cancelled") and row.status not in ("success", "partial", "failed", "cancelled"):
            row.status = result.get("status", task.status); row.finished_at = task.finished_at
        db.commit()
    if task is None and row.status in ("pending", "running"):
        # The in-process task manager is intentionally lightweight. After a
        # process restart its task object is gone; persist an explicit terminal
        # state so the UI does not report an infinite running task.
        row.status = "failed"
        row.finished_at = datetime.now(timezone.utc)
        failures = list(row.failures or [])
        if not any(item.get("code") == "worker_restarted" for item in failures if isinstance(item, dict)):
            failures.append({"code": "worker_restarted", "error": "批量任务所在服务已重启，原内存任务不可恢复"})
        row.failures = failures
        db.commit()
    return _batch_item(row) | ({"progress": task.progress, "step": task.step, "message": task.message} if task else {})


@foreign_router.post("/ai-analysis/batch/{run_id}/cancel")
def cancel_foreign_ai_batch(run_id: str, request: Request, current_user: User = Depends(require_permission("foreign:ai:batch:cancel")), db: Session = Depends(get_db)):
    row = db.scalar(select(ForeignAIBatchRun).where(ForeignAIBatchRun.run_id == run_id))
    task = cancel_task(row.task_id if row else run_id)
    if row is None or task is None:
        raise HTTPException(status_code=404, detail="Foreign AI batch not found")
    log_operation(db, action="FOREIGN_AI_BATCH_CANCEL", operator=current_user, request=request, resource_type="foreign_ai_batch", resource_id=run_id, details={"status": task.status})
    if not getattr(request.state, "batch_mode", False):
        db.commit()
    row.status = "cancelled" if task.status == "cancelled" else row.status
    db.commit()
    return _batch_item(row) | {"progress": task.progress, "step": task.step}


@foreign_router.get("/ai-analysis/reviews")
def list_foreign_manual_reviews(page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200), status: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_foreign_review_read)):
    stmt = select(ForeignManualReview)
    if status:
        stmt = stmt.where(ForeignManualReview.review_status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(ForeignManualReview.created_at.desc(), ForeignManualReview.id.desc()).offset((page - 1) * size).limit(size)).all()
    opinion_ids = {row.foreign_opinion_id for row in rows}
    opinions = {
        opinion.id: opinion
        for opinion in db.scalars(select(ForeignOpinion).where(ForeignOpinion.id.in_(opinion_ids))).all()
    } if opinion_ids else {}
    user_ids = {row.reviewed_by for row in rows if row.reviewed_by}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    return {"items": [_foreign_manual_review_item(row, opinions.get(row.foreign_opinion_id), users.get(row.reviewed_by), db=db) for row in rows], "total": total, "page": page, "size": size}


def _foreign_manual_review_item(row: ForeignManualReview, opinion: ForeignOpinion | None = None, operator: User | None = None, db: Session | None = None) -> dict[str, Any]:
    alert_candidate_count = 0
    event_candidate_count = 0
    if db is not None:
        alert_candidate_count = int(
            db.scalar(
                select(func.count()).select_from(ForeignAIAlertCandidate).where(
                    ForeignAIAlertCandidate.review_id == row.id
                )
            ) or 0
        )
        event_candidate_count = int(
            db.scalar(
                select(func.count()).select_from(ForeignEventCandidate).where(
                    ForeignEventCandidate.review_id == row.id,
                    ForeignEventCandidate.candidate_status == "candidate",
                )
            ) or 0
        )
    display_source = {
        "use_ai_display": "ai",
        "keep_rule": "rule",
        "confirm_event_change": "rule",
        "confirm_alert_change": "ai",
        "reject_change": "rule",
        "complete_review": "rule",
    }.get(row.review_decision or "", "rule" if row.display_decision is None else ("ai" if row.display_decision == "use_ai_display" else "rule"))
    return {"id": row.id, "foreign_opinion_id": row.foreign_opinion_id,
            "opinion_title": opinion.title if opinion else "",
            "opinion_source": opinion.source_name_snapshot if opinion else "",
            "opinion_published_at": opinion.published_at.isoformat() if opinion and opinion.published_at else None,
            "source_type": row.source_type,
            "rule_risk_snapshot": row.rule_risk_snapshot or {}, "ai_risk_snapshot": row.ai_risk_snapshot or {},
            "display_source": display_source,
            "review_status": row.review_status, "review_decision": row.review_decision, "review_reason": row.review_reason,
            "reviewed_by": row.reviewed_by, "reviewed_by_name": operator.username if operator else None,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "batch_run_id": row.batch_run_id, "event_preview_id": row.event_preview_id, "alert_preview_id": row.alert_preview_id,
            "confirmation_version": row.confirmation_version,
            "display_decision": row.display_decision,
            "event_review_status": row.event_review_status,
            "alert_review_status": row.alert_review_status,
            "review_closed_at": row.review_closed_at.isoformat() if row.review_closed_at else None,
            "completed_by": row.completed_by,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "completion_reason": row.completion_reason,
            "event_candidate_count": event_candidate_count or (row.event_preview or {}).get("candidate_count", 0),
            "alert_candidate_count": alert_candidate_count,
            "event_preview": row.event_preview or {}, "alert_preview": row.alert_preview or {}, "created_at": row.created_at.isoformat() if row.created_at else None}


def _stamp_confirmed_alerts(
    db: Session,
    *,
    opinion_id: int,
    user_id: int | None,
    reason: str,
    confirmation_version: str | None,
    rule_risk_snapshot: dict | None,
    ai_risk_snapshot: dict | None,
) -> None:
    """Attach human-confirmation provenance to the rule-sourced foreign alerts
    that belong to the reviewed opinion.

    This is idempotent: alerts that were already confirmed in a prior review are
    left untouched. The formal alert remains a rule-driven record; only the
    confirmation metadata is recorded so the human decision is traceable.
    """
    from sqlalchemy import update as _update

    db.execute(
        _update(ForeignAlert)
        .where(
            ForeignAlert.foreign_opinion_id == opinion_id,
            ForeignAlert.evaluation_source == "rule",
            ForeignAlert.status == "triggered",
            ForeignAlert.confirmed_at.is_(None),
        )
        .values(
            confirmed_by=user_id,
            confirmed_at=datetime.now(timezone.utc),
            review_reason=reason or None,
            confirmation_version=confirmation_version,
            rule_risk_snapshot=rule_risk_snapshot or {},
            ai_risk_snapshot=ai_risk_snapshot or {},
        )
    )


@foreign_router.post("/ai-analysis/reviews/{review_id}/decision")
def decide_foreign_manual_review(review_id: int, payload: ForeignAIReviewDecisionPayload, request: Request, current_user: User = Depends(require_foreign_review_read), db: Session = Depends(get_db)):
    row = db.get(ForeignManualReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Foreign manual review not found")
    now = datetime.now(timezone.utc)
    # 已关闭的复核（confirmed/rejected/superseded）不可再操作：直接幂等返回，不重复建记录。
    if row.review_status != "pending_review":
        return {
            "review": _foreign_manual_review_item(row, db.get(ForeignOpinion, row.foreign_opinion_id), db.get(User, row.reviewed_by) if row.reviewed_by else None, db=db),
            "decision": row.review_decision,
            "review_status": row.review_status,
            "event_result": {},
            "alert_result": {},
            "idempotent": True,
            "message": "该复核记录已处理，本次调用未产生新的正式事件或预警。",
        }

    action = payload.decision
    if action == "confirm_event_change" and row.event_review_status == "confirmed":
        return {
            "review": _foreign_manual_review_item(
                row,
                db.get(ForeignOpinion, row.foreign_opinion_id),
                db.get(User, row.reviewed_by) if row.reviewed_by else None,
                db=db,
            ),
            "decision": row.review_decision,
            "review_status": row.review_status,
            "event_result": {"candidate_count": 0, "created_count": 0, "existing_count": 1},
            "alert_result": {},
            "idempotent": True,
            "message": "事件复核已确认，本次未重复生成正式事件。",
        }
    if action == "confirm_alert_change" and row.alert_review_status == "confirmed":
        return {
            "review": _foreign_manual_review_item(
                row,
                db.get(ForeignOpinion, row.foreign_opinion_id),
                db.get(User, row.reviewed_by) if row.reviewed_by else None,
                db=db,
            ),
            "decision": row.review_decision,
            "review_status": row.review_status,
            "event_result": {},
            "alert_result": {"matched": False, "created_count": 0, "deduplicated_count": 1},
            "idempotent": True,
            "message": "预警复核已确认，本次未重复生成正式预警。",
        }
    # 按动作判定所需权限：四个蓝色操作只更新子状态（沿用既有细粒度权限），
    # 「完成复核」需要独立的 review:complete 写权限，「驳回全部 AI 变更」沿用 reject。
    if action == "reject_change":
        required = "foreign:ai:review:reject"
    elif action == "confirm_event_change":
        required = "foreign:events:review:confirm"
    elif action == "confirm_alert_change":
        required = "foreign:alerts:review:confirm"
    elif action == "complete_review":
        required = "ai:review:complete"
    else:  # keep_rule / use_ai_display
        required = "ai:review:read"
    if not is_superuser_user(current_user) and required not in get_user_permissions(current_user, db):
        raise HTTPException(status_code=403, detail="Permission denied")

    row.reviewed_at = now
    event_result: dict[str, Any] = {}
    alert_result: dict[str, Any] = {}
    if action in ("keep_rule", "use_ai_display"):
        opinion = db.get(ForeignOpinion, row.foreign_opinion_id)
        if opinion is None:
            raise HTTPException(status_code=404, detail="Foreign opinion not found")
        apply_review_decision(
            db,
            opinion=opinion,
            decision=action,
            rule_snapshot=row.rule_risk_snapshot,
            ai_snapshot=row.ai_risk_snapshot,
        )
        row.display_decision = action
        row.review_decision = action
        message = ("已采用 AI 作为当前风险，普通列表、驾驶舱及关联展示将读取 AI 风险。"
                   if action == "use_ai_display"
                   else "已保留系统规则作为当前风险，普通列表、驾驶舱及关联展示将读取规则风险。")
    elif action == "confirm_event_change":
        row.event_review_status = "confirmed"
        row.review_decision = action
        row.confirmation_version = f"manual-review-{row.id}-{int(now.timestamp())}"
        event_result = confirm_event_for_review(
            db, row, user_id=current_user.id, reason=payload.reason,
            request_id=payload.request_id, commit=False,
        )
        alert_result = {}
        message = ("已确认复核关联的事件候选为正式外网事件（仍留在待复核）。" if event_result.get("candidate_count") else (event_result.get("reason") or "未找到可确认的事件候选。"))
    elif action == "confirm_alert_change":
        row.alert_review_status = "confirmed"
        row.review_decision = action
        row.confirmation_version = f"manual-review-{row.id}-{int(now.timestamp())}"
        alert_result = confirm_alert_for_review(
            db, row, user_id=current_user.id, reason=payload.reason,
            request_id=payload.request_id, commit=False,
        )
        event_result = {}
        message = ("已依据 AI 预警候选生成正式外网预警（仍留在待复核）。" if alert_result.get("matched") else (alert_result.get("reason") or "未命中 AI 预警规则候选。"))
    elif action == "reject_change":
        # 驳回全部 AI 变更：行离开待复核进入已驳回，不建正式记录。
        row.review_status = "rejected"
        row.review_decision = action
        opinion = db.get(ForeignOpinion, row.foreign_opinion_id)
        if opinion is not None:
            apply_review_decision(
                db,
                opinion=opinion,
                decision=action,
                rule_snapshot=row.rule_risk_snapshot,
                ai_snapshot=row.ai_risk_snapshot,
            )
        message = "已驳回该条外网人工复核（驳回全部 AI 变更），未生成正式事件或预警。"
    elif action == "complete_review":
        # 唯一进入「已确认」的入口：仅关闭复核，不创建任何正式事件/预警，天然幂等。
        row.review_status = "confirmed"
        row.review_decision = action
        row.review_closed_at = now
        row.completed_by = current_user.id
        row.completed_at = now
        row.completion_reason = payload.reason.strip() or None
        message = "已完成复核，进入「已确认」。"
    else:
        raise HTTPException(status_code=422, detail="未知的复核决策")

    # Common audit fields (display/reject branches do not mint a
    # confirmation_version, since no formal record is produced).
    row.review_reason = payload.reason.strip() or None
    row.reviewed_by = current_user.id

    log_operation(db, action="FOREIGN_AI_MANUAL_REVIEW", operator=current_user, request=request, resource_type="foreign_manual_review", resource_id=str(row.id), details={"decision": payload.decision, "reason": payload.reason})
    if not getattr(request.state, "batch_mode", False):
        db.commit()
        db.refresh(row)
    return {
        "review": _foreign_manual_review_item(row, db.get(ForeignOpinion, row.foreign_opinion_id), db.get(User, row.reviewed_by) if row.reviewed_by else None, db=db),
        "decision": payload.decision,
        "review_status": row.review_status,
        "event_result": event_result,
        "alert_result": alert_result,
        "idempotent": False,
        "message": message,
    }


@foreign_router.post("/ai-analysis/reviews/batch")
def decide_foreign_manual_reviews_batch(payload: ForeignAIReviewBatchPayload, request: Request, current_user: User = Depends(require_foreign_review_read), db: Session = Depends(get_db)):
    if payload.decision == "reject_change":
        required = "foreign:ai:review:reject"
    elif payload.decision == "confirm_event_change":
        required = "foreign:events:review:confirm"
    elif payload.decision == "confirm_alert_change":
        required = "foreign:alerts:review:confirm"
    else:
        required = "ai:review:read"
    if not is_superuser_user(current_user) and required not in get_user_permissions(current_user, db):
        raise HTTPException(status_code=403, detail="Permission denied")
    if payload.confirm_all:
        if not is_superuser_user(current_user) and "foreign:ai:full-confirm" not in get_user_permissions(current_user, db):
            raise HTTPException(status_code=403, detail="Full confirmation permission required")
        stmt = select(ForeignManualReview.id).where(ForeignManualReview.review_status == "pending_review")
        review_ids = list(db.scalars(stmt).all())
    else:
        review_ids = list(dict.fromkeys(payload.review_ids or []))
    if not review_ids:
        raise HTTPException(status_code=422, detail="No pending reviews selected")
    results = []
    failed = []
    request.state.batch_mode = True
    display_only = {"use_ai_display", "keep_rule"}
    try:
        # Display-only decisions (adopt AI / keep rule) only flip the opinion
        # display source and mint no formal event or alert. They are therefore
        # safe to apply per-review: a single review that cannot be applied
        # (e.g. it has no completed AI result) is skipped and recorded, while
        # the rest of the batch still commits. Formal decisions (confirm
        # event/alert, reject, complete) keep the original all-or-nothing
        # guarantee so there is never a half-confirmed formal record.
        for index, review_id in enumerate(review_ids):
            sp = db.begin_nested()
            try:
                results.append(decide_foreign_manual_review(
                    review_id,
                    ForeignAIReviewDecisionPayload(
                        decision=payload.decision,
                        reason=payload.reason,
                        request_id=f"{payload.request_id or 'batch'}:{review_id}:{index}",
                    ), request, current_user, db,
                ))
            except Exception as exc:
                db.rollback()  # rolls back to the savepoint, not the whole tx
                if payload.decision in display_only:
                    failed.append({"review_id": review_id, "detail": _safe_foreign_error(exc)})
                    continue
                raise
            else:
                sp.commit()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"批量人工复核已整体回滚：{_safe_foreign_error(exc)}") from exc
    finally:
        request.state.batch_mode = False
    return {"items": results, "total": len(results), "failed": failed, "transaction": "committed"}


def _foreign_risk_item(result: ForeignRiskResult, opinion: ForeignOpinion) -> dict[str, Any]:
    return {
        "id": result.id,
        "foreign_opinion_id": result.foreign_opinion_id,
        "analysis_run_id": result.analysis_run_id,
        "content_hash": result.content_hash,
        "language": result.language,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "sentiment": result.sentiment,
        "sentiment_confidence": result.sentiment_confidence,
        "risk_category": result.risk_category,
        "matched_terms": result.matched_terms or [],
        "explanation": result.explanation,
        "analyzer_type": result.analyzer_type,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "analysis_status": result.analysis_status,
        "error_message": _safe_foreign_error(result.error_message),
        "analyzed_at": result.analyzed_at.isoformat() if result.analyzed_at else None,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "updated_at": result.updated_at.isoformat() if result.updated_at else None,
        "is_current": bool(result.is_current),
        "opinion": _foreign_opinion_item(opinion),
    }


def _parse_risk_date(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be YYYY-MM-DD",
        ) from exc


@foreign_router.get("/risk")
def list_foreign_risk(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    source: str | None = None,
    language: str | None = None,
    sentiment: str | None = None,
    risk_level: str | None = None,
    analysis_status: str | None = None,
    model_version: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:risk:read")),
):
    stmt = (
        select(ForeignRiskResult, ForeignOpinion)
        .join(
            ForeignOpinion,
            ForeignOpinion.id == ForeignRiskResult.foreign_opinion_id,
        )
    )
    if source:
        stmt = stmt.where(ForeignOpinion.source_name_snapshot == source)
    if language:
        stmt = stmt.where(ForeignRiskResult.language == language)
    if sentiment:
        stmt = stmt.where(ForeignRiskResult.sentiment == sentiment)
    if risk_level:
        stmt = stmt.where(ForeignRiskResult.risk_level == risk_level)
    if analysis_status:
        stmt = stmt.where(ForeignRiskResult.analysis_status == analysis_status)
    if model_version:
        stmt = stmt.where(ForeignRiskResult.model_version == model_version)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                ForeignOpinion.title.ilike(like),
                ForeignOpinion.summary.ilike(like),
                ForeignOpinion.content.ilike(like),
            )
        )
    start = _parse_risk_date(date_from, "date_from")
    end = _parse_risk_date(date_to, "date_to")
    if start:
        stmt = stmt.where(ForeignOpinion.published_at >= start)
    if end:
        stmt = stmt.where(
            ForeignOpinion.published_at < end.replace(hour=23, minute=59, second=59)
        )
    total = db.scalar(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ) or 0
    rows = db.execute(
        stmt.order_by(ForeignRiskResult.analyzed_at.desc(), ForeignRiskResult.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    items = [_foreign_risk_item(result, opinion) for result, opinion in rows]
    # Rule rows keep their own values; the resolver only adds the shared
    # effective-risk view so this endpoint cannot drift from the list page.
    attach_effective_risk(db, items, id_key="foreign_opinion_id")
    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_router.get("/risk/summary")
def summarize_foreign_risk(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:risk:read")),
):
    rows = db.execute(
        select(
            ForeignRiskResult.analysis_status,
            ForeignRiskResult.risk_level,
            ForeignRiskResult.sentiment,
            func.count(ForeignRiskResult.id),
        ).group_by(
            ForeignRiskResult.analysis_status,
            ForeignRiskResult.risk_level,
            ForeignRiskResult.sentiment,
        )
    ).all()
    return {
        "total": sum(int(row[3]) for row in rows),
        "by_status": {
            row[0]: sum(int(item[3]) for item in rows if item[0] == row[0])
            for row in rows
        },
        "by_risk_level": {
            row[0]: sum(int(item[3]) for item in rows if item[1] == row[0])
            for row in rows
        },
        "by_sentiment": {
            row[0]: sum(int(item[3]) for item in rows if item[2] == row[0])
            for row in rows
        },
    }


@foreign_router.get("/risk/{foreign_opinion_id}")
def get_foreign_risk(
    foreign_opinion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:risk:read")),
):
    opinion = db.get(ForeignOpinion, foreign_opinion_id)
    if opinion is None:
        raise HTTPException(status_code=404, detail="Foreign opinion not found")
    results = db.scalars(
        select(ForeignRiskResult)
        .where(ForeignRiskResult.foreign_opinion_id == foreign_opinion_id)
        .order_by(ForeignRiskResult.created_at.desc(), ForeignRiskResult.id.desc())
    ).all()
    return {
        "foreign_opinion_id": foreign_opinion_id,
        "opinion": _foreign_opinion_item(opinion),
        "items": [_foreign_risk_item(result, opinion) for result in results],
    }


@foreign_router.post("/risk/{foreign_opinion_id}/analyze")
def analyze_foreign_risk(
    foreign_opinion_id: int,
    payload: ForeignRiskAnalyzePayload | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:risk:analyze")),
):
    service = ForeignRiskService()
    try:
        result = service.analyze_opinion(
            db,
            foreign_opinion_id,
            model_version=payload.model_version if payload else RULE_MODEL_VERSION,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _foreign_risk_item(result, db.get(ForeignOpinion, foreign_opinion_id))


@foreign_router.post("/risk/batch")
def analyze_foreign_risk_batch(
    payload: ForeignRiskBatchPayload,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:risk:batch")),
):
    service = ForeignRiskService()
    try:
        run, results = service.analyze_many(
            db,
            payload.foreign_opinion_ids,
            model_version=payload.model_version,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    opinion_map = {
        opinion.id: opinion
        for opinion in db.scalars(
            select(ForeignOpinion).where(
                ForeignOpinion.id.in_(payload.foreign_opinion_ids)
            )
        ).all()
    }
    return {
        "run": _foreign_analysis_run_item(run),
        "items": [
            _foreign_risk_item(result, opinion_map[result.foreign_opinion_id])
            for result in results
        ],
    }


@foreign_router.post("/risk/{foreign_opinion_id}/ai-review")
def manual_foreign_ai_review(
    foreign_opinion_id: int,
    current_user: User = Depends(require_permission("foreign:risk:ai")),
    db: Session = Depends(get_db),
):
    if db.get(ForeignOpinion, foreign_opinion_id) is None:
        raise HTTPException(status_code=404, detail="Foreign opinion not found")
    try:
        ForeignRiskService().manual_ai_review(db, foreign_opinion_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "FOREIGN_AI_DISABLED",
                "message": str(exc),
            },
        ) from exc
    return {"status": "disabled", "foreign_opinion_id": foreign_opinion_id}


def _foreign_analysis_run_item(row: ForeignAnalysisRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "foreign_opinion_id": row.foreign_opinion_id,
        "analysis_run_id": row.id,
        "batch_run_id": row.batch_run_id,
        "analyzer_type": row.analyzer_type,
        "model_name": row.model_name,
        "model_version": row.model_version,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "processed_count": row.processed_count,
        "success_count": row.success_count,
        "failed_count": row.failed_count,
        "error_message": _safe_foreign_error(row.error_message),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@foreign_router.get("/analysis-runs")
def list_foreign_analysis_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:risk:read")),
):
    stmt = select(ForeignAnalysisRun)
    if status:
        stmt = stmt.where(ForeignAnalysisRun.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignAnalysisRun.started_at.desc(), ForeignAnalysisRun.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "items": [_foreign_analysis_run_item(row) for row in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@foreign_router.get("/risk-terms")
def list_foreign_risk_terms(
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=100),
    language: str | None = None,
    is_enabled: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:risk:terms:read")),
):
    stmt = select(ForeignRiskTerm)
    if language:
        stmt = stmt.where(ForeignRiskTerm.language == language)
    if is_enabled is not None:
        stmt = stmt.where(ForeignRiskTerm.is_enabled.is_(is_enabled))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignRiskTerm.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {
        "items": rows,
        "total": total,
        "page": page,
        "size": size,
    }


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
        "error_msg": _safe_foreign_error(row.error_msg),
    }


@foreign_router.get("/collection-runs")
def list_foreign_collection_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:sources:read")),
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


@foreign_router.get("/collection-schedule/status")
def foreign_collection_schedule_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:sources:read")),
):
    """Expose opt-in scheduler state and the current eligible source count."""
    from app.core.scheduler import foreign_scheduler_status

    status_payload = foreign_scheduler_status()
    eligible = db.scalars(
        select(DataSource).where(
            DataSource.enabled.is_(True), DataSource.schedule_enabled.is_(True)
        )
    ).all()
    status_payload["eligible_source_count"] = sum(
        1 for source in eligible if _is_foreign_config(source)
    )
    return status_payload


def _run_foreign_collect_task(
    task,
    source_ids: list[int] | None,
    all_sources: bool,
    batch_id: str,
) -> dict:
    db = SessionLocal()
    try:
        task.batch_id = batch_id
        task.step = "外网 RSS 采集中"

        def progress(done: int, total: int, name: str) -> None:
            task.progress = int(done / total * 100) if total else 100
            task.step = f"已处理 {done}/{total} 个外网数据源（{name}）"

        result = collect_foreign(
            db,
            source_ids=source_ids,
            all_sources=all_sources,
            batch_id=batch_id,
            on_progress=progress,
        )
        task.step = "外网采集完成"
        created_ids = result.get("created_ids") or []
        if created_ids:
            from app.services.foreign_risk_service import ForeignRiskService

            svc = ForeignRiskService()
            total = len(created_ids)
            done = 0
            for i in range(0, total, 50):
                chunk = created_ids[i : i + 50]
                try:
                    svc.analyze_many(db, chunk)
                    done += len(chunk)
                    task.step = f"外网规则研判 {done}/{total}"
                except Exception as exc:  # noqa: BLE001
                    task.step = f"外网规则研判部分失败：{exc}"
            result["analyzed"] = done
        return result
    finally:
        db.close()


@foreign_router.post("/collect")
def collect_foreign_now(
    payload: ForeignCollectionPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    permission = "foreign:sources:collect_all" if payload.all_sources else "foreign:sources:collect"
    if not is_superuser_user(current_user) and permission not in get_user_permissions(current_user, db):
        log_operation(
            db,
            action="FOREIGN_COLLECTION",
            operator=current_user,
            request=request,
            resource_type="foreign_collection",
            result="failed",
            error_message="Permission denied",
            details={"permission": permission},
        )
        db.commit()
        raise HTTPException(status_code=403, detail="Permission denied")
    source_ids = payload.source_ids
    if payload.all_sources and source_ids is not None:
        raise HTTPException(status_code=422, detail="source_ids cannot be combined with all_sources=true")
    if not payload.all_sources and not source_ids:
        raise HTTPException(
            status_code=422,
            detail="Select at least one foreign source; use all_sources=true for full collection",
        )
    if source_ids is not None and len(set(source_ids)) != len(source_ids):
        raise HTTPException(status_code=422, detail="source_ids must not contain duplicates")
    if not payload.all_sources:
        selected = db.scalars(select(DataSource).where(DataSource.id.in_(source_ids or []))).all()
        selected_by_id = {source.id: source for source in selected}
        missing = [source_id for source_id in source_ids or [] if source_id not in selected_by_id]
        if missing:
            raise HTTPException(status_code=422, detail="One or more selected foreign sources were not found")
        if any(not _is_foreign_config(source) for source in selected):
            raise HTTPException(status_code=422, detail="All selected sources must be foreign sources")
        if any(not source.enabled for source in selected):
            raise HTTPException(status_code=422, detail="All selected foreign sources must be enabled")
    dedupe_key = "all" if payload.all_sources else ",".join(str(item) for item in sorted(source_ids or []))
    batch_id = uuid.uuid4().hex
    try:
        try:
            task_id = start_task(
                "foreign-collector",
                _run_foreign_collect_task,
                source_ids,
                payload.all_sources,
                batch_id,
                dedupe_key=dedupe_key,
            )
        except TypeError as exc:
            # Keep lightweight test doubles and older embedders compatible;
            # the production task manager accepts dedupe_key.
            if "dedupe_key" not in str(exc):
                raise
            task_id = start_task(
                "foreign-collector", _run_foreign_collect_task,
                source_ids, payload.all_sources, batch_id,
            )
    except DuplicateTaskError as exc:
        log_operation(
            db,
            action="FOREIGN_COLLECTION",
            operator=current_user,
            request=request,
            resource_type="foreign_collection",
            result="failed",
            error_message="Duplicate collection task",
            details={"all_sources": payload.all_sources, "source_ids": sorted(source_ids or [])},
        )
        db.commit()
        raise HTTPException(status_code=409, detail="An equivalent foreign collection task is already running") from exc
    log_operation(
        db,
        action="FOREIGN_COLLECTION",
        operator=current_user,
        request=request,
        resource_type="foreign_collection",
        resource_id=task_id,
        details={
            "all_sources": payload.all_sources,
            "source_ids": sorted(source_ids or []),
            "permission": permission,
        },
    )
    db.commit()
    return {
        "success": True,
        "task_id": task_id,
        "batch_id": batch_id,
        "scope": "foreign",
        "message": "外网采集任务已接受",
    }
