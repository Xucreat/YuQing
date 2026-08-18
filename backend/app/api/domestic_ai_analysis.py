from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import get_user_permissions, is_superuser_user, require_permission
from app.core.task_manager import DuplicateTaskError, Task, cancel_task, get_task, start_task
from app.db.session import SessionLocal, get_db
from app.models.alert import AlertRule
from app.models.domestic_ai_alert_candidate import DomesticAIAlertCandidate
from app.models.domestic_ai_batch_run import DomesticAIBatchRun
from app.models.domestic_ai_result import DomesticAIResult
from app.models.domestic_manual_review import DomesticManualReview
from app.models.opinion import Opinion
from app.models.user import User
from app.services.audit_service import log_operation
from app.services.domestic_ai_service import DomesticAIService, serialize_domestic_ai_result
from app.services.domestic_manual_review_service import (
    confirm_alert_for_review,
    confirm_event_for_review,
    ensure_domestic_manual_review,
)
from app.services.current_risk import apply_review_decision

LOW_VALUE_CONTENT_TYPES = frozenset({"irrelevant", "advertising"})


def _current_risk_score_expression():
    return case(
        (Opinion.current_risk_updated_at.is_not(None), Opinion.current_risk_score),
        else_=Opinion.risk_score,
    )


domestic_ai_router = APIRouter(
    prefix="/domestic/ai-analysis",
    tags=["domestic-ai-analysis"],
    dependencies=[Depends(get_current_user)],
)


class DomesticAIBatchPayload(BaseModel):
    scope: Literal["recent", "filters", "time", "selected"] = "recent"
    opinion_ids: list[int] | None = Field(default=None, max_length=5000)
    recent_n: int = Field(default=100, ge=1, le=100000)
    filters: dict[str, Any] = Field(default_factory=dict)
    date_from: str | None = None
    date_to: str | None = None
    only_unanalyzed: bool = True
    force: bool = False
    full_confirmation: bool = False
    token_budget: int = Field(default=100_000, ge=1_000, le=2_000_000)


class DomesticAIReviewDecisionPayload(BaseModel):
    decision: Literal["keep_rule", "use_ai_display", "confirm_event_change", "confirm_alert_change", "reject_change", "complete_review"]
    reason: str = Field(default="", max_length=4000)
    request_id: str | None = Field(default=None, max_length=128)


class DomesticAIReviewBatchPayload(BaseModel):
    review_ids: list[int] | None = Field(default=None, max_length=5000)
    decision: Literal["keep_rule", "use_ai_display", "confirm_event_change", "confirm_alert_change", "reject_change"]
    reason: str = Field(default="", max_length=4000)
    request_id: str | None = Field(default=None, max_length=128)
    confirm_all: bool = False


def require_domestic_review_read(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    if is_superuser_user(current_user):
        return current_user
    perms = set(get_user_permissions(current_user, db))
    if perms.intersection(
        {
            "ai:review:read",
            "domestic:events:review:read",
            "domestic:alerts:review:read",
        }
    ):
        return current_user
    raise HTTPException(status_code=403, detail="Domestic review read permission required")


def _safe_error(value: object) -> str:
    message = " ".join(str(value or "").split())
    lowered = message.casefold()
    if any(
        marker in lowered
        for marker in ("traceback", "password", "token", "secret", "api key", "connection string", "://", "@")
    ):
        return "国内 AI 操作失败，详细错误已隐藏"
    return message[:1000] or "国内 AI 操作失败"


def _parse_day(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be YYYY-MM-DD") from exc


def _apply_domestic_filters(stmt, filters: dict[str, Any]):
    q = filters.get("q") or filters.get("keyword")
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Opinion.title.ilike(like), Opinion.content.ilike(like), Opinion.keywords.ilike(like)))
    source = filters.get("source")
    if source:
        stmt = stmt.where(Opinion.source == str(source))
    keyword = filters.get("keyword")
    if keyword and keyword != q:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Opinion.keywords.ilike(like), Opinion.title.ilike(like), Opinion.content.ilike(like)))
    risk_level = filters.get("risk_level")
    if risk_level:
        # Matches the existing /opinions contract: risk_level is the sentiment filter.
        stmt = stmt.where(Opinion.sentiment == str(risk_level))
    level = filters.get("level")
    current_score = _current_risk_score_expression()
    if level == "high":
        stmt = stmt.where(current_score >= 70)
    elif level in {"mid", "medium"}:
        stmt = stmt.where(current_score >= 40, current_score <= 69)
    elif level == "low":
        stmt = stmt.where(current_score <= 39)
    risk_min = filters.get("risk_min")
    risk_max = filters.get("risk_max")
    if risk_min is not None:
        stmt = stmt.where(current_score >= int(risk_min))
    if risk_max is not None:
        stmt = stmt.where(current_score <= int(risk_max))
    content_type = filters.get("content_type")
    if content_type:
        stmt = stmt.where(Opinion.content_type == str(content_type))
    if not filters.get("include_low_value") and not content_type:
        stmt = stmt.where(
            or_(
                Opinion.content_type.is_(None),
                Opinion.content_type.notin_(LOW_VALUE_CONTENT_TYPES),
            )
        )
    relevance_min = filters.get("relevance_min")
    relevance_max = filters.get("relevance_max")
    relevance = filters.get("relevance")
    if relevance == "high":
        relevance_min = 60
    elif relevance == "low":
        relevance_min, relevance_max = 40, 59
    if relevance_min is not None:
        stmt = stmt.where(Opinion.relevance_score >= int(relevance_min))
    if relevance_max is not None:
        stmt = stmt.where(Opinion.relevance_score <= int(relevance_max))
    sentiment = filters.get("sentiment")
    if sentiment:
        stmt = stmt.where(Opinion.sentiment == str(sentiment))
    region_id = filters.get("region_id")
    if region_id:
        stmt = stmt.where(Opinion.region_id == int(region_id))
    date_from = _parse_day(filters.get("date_from"), "date_from")
    date_to = _parse_day(filters.get("date_to"), "date_to")
    if date_from:
        stmt = stmt.where(func.date(Opinion.publish_time) >= date_from.date())
    if date_to:
        stmt = stmt.where(func.date(Opinion.publish_time) <= date_to.date())
    return stmt


def _selection(db: Session, payload: DomesticAIBatchPayload) -> list[Opinion]:
    stmt = select(Opinion)
    filters_snapshot = payload.filters or {}
    if payload.scope == "selected":
        ids = sorted(set(payload.opinion_ids or []))
        if not ids:
            raise HTTPException(status_code=422, detail="Selected scope requires opinion_ids")
        stmt = stmt.where(Opinion.id.in_(ids))
    else:
        stmt = _apply_domestic_filters(stmt, filters_snapshot)
    if payload.scope == "time":
        date_from = _parse_day(payload.date_from or filters_snapshot.get("date_from"), "date_from")
        date_to = _parse_day(payload.date_to or filters_snapshot.get("date_to"), "date_to")
        if date_from is None or date_to is None:
            raise HTTPException(status_code=422, detail="Time scope requires date_from and date_to")
        stmt = stmt.where(func.date(Opinion.publish_time) >= date_from.date(), func.date(Opinion.publish_time) <= date_to.date())
    order = (Opinion.publish_time.desc().nullslast(), Opinion.created_at.desc(), Opinion.id.desc())
    rows = list(db.scalars(stmt.order_by(*order)).all())
    if payload.only_unanalyzed and not payload.force and rows:
        completed = set(
            db.scalars(
                select(DomesticAIResult.opinion_id).where(
                    DomesticAIResult.opinion_id.in_([row.id for row in rows]),
                    DomesticAIResult.status == "completed",
                )
            ).all()
        )
        rows = [row for row in rows if row.id not in completed]
    if payload.scope == "recent":
        rows = rows[: payload.recent_n]
    return rows


def _estimate_tokens(rows: list[Opinion]) -> int:
    return sum(max(1, len("\n".join(part for part in (row.title, row.summary, row.content) if part)) // 4) for row in rows)


def _preview_domestic_alert_count(db: Session, opinion_ids: list[int]) -> int:
    """预览「可能影响的预警」数量（Phase 2 预览真实化）。

    仅基于**已存在**的 completed DomesticAIResult 与**已启用**的 ai_risk_score
    规则做真实计数：不触发任何评估、不写库，也不改变「AI 只生成候选、不直接
    触发告警」的边界。统计口径为「命中至少一条启用规则阈值」的去重舆情数，
    属于预估值（无法预测本次新研判将产生的分数）。
    """
    if not opinion_ids:
        return 0
    thresholds = [
        int(rule.risk_threshold or 0)
        for rule in db.scalars(
            select(AlertRule).where(
                AlertRule.enabled.is_(True),
                AlertRule.rule_type == "ai_risk_score",
            )
        ).all()
    ]
    if not thresholds:
        return 0
    return int(
        db.scalar(
            select(func.count(func.distinct(DomesticAIResult.opinion_id))).where(
                DomesticAIResult.opinion_id.in_(list(opinion_ids)),
                DomesticAIResult.status == "completed",
                DomesticAIResult.risk_score.is_not(None),
                DomesticAIResult.risk_score >= min(thresholds),
            )
        )
        or 0
    )


def _batch_preview(db: Session, payload: DomesticAIBatchPayload) -> dict[str, Any]:
    rows = _selection(db, payload)
    all_rows = rows
    if payload.only_unanalyzed:
        all_rows = _selection(db, payload.model_copy(update={"only_unanalyzed": False}))
    all_ids = [row.id for row in all_rows]
    completed_count = 0
    if all_ids:
        completed_count = int(
            db.scalar(
                select(func.count())
                .select_from(DomesticAIResult)
                .where(DomesticAIResult.opinion_id.in_(all_ids), DomesticAIResult.status == "completed")
            ) or 0
        )
    token_estimate = _estimate_tokens(rows)
    risk_counts = {"high": 0, "medium": 0, "low": 0, "unknown": 0}
    for row in rows:
        score = row.current_risk_score if row.current_risk_updated_at is not None else row.risk_score
        if score >= 70:
            key = "high"
        elif score >= 40:
            key = "medium"
        else:
            key = "low"
        risk_counts[key] += 1
    filters_snapshot = payload.model_dump(mode="json")
    # Phase 2 预览真实化：预览失败不得让接口 500，异常时回退为 0。
    try:
        possible_alert_count = _preview_domestic_alert_count(db, all_ids)
    except Exception:
        db.rollback()
        possible_alert_count = 0
    return {
        "matched_count": len(all_rows),
        "existing_ai_result_count": completed_count,
        "pending_analysis_count": len(rows),
        "estimated_token_usage": token_estimate,
        "estimated_duration_seconds": max(1, len(rows) * 2),
        "estimated_cost": None,
        "risk_level_counts": risk_counts,
        "possible_event_count": sum(
            1
            for row in rows
            if (row.current_risk_score if row.current_risk_updated_at is not None else row.risk_score) >= 70
        ),
        "possible_alert_count": possible_alert_count,
        "filters": filters_snapshot,
        "opinion_ids": [row.id for row in rows],
        "token_budget": payload.token_budget,
        "token_budget_exceeded": token_estimate > payload.token_budget,
    }


def _run_batch(task: Task, opinion_ids: list[int], force: bool, run_id: str) -> dict[str, Any]:
    db = SessionLocal()
    processed = success = failed = skipped = 0
    failures: list[dict[str, Any]] = []
    event_total = 0
    alert_total = 0
    try:
        total = len(opinion_ids)
        run = db.scalar(select(DomesticAIBatchRun).where(DomesticAIBatchRun.run_id == run_id))
        if run:
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            run.current_step = "国内 AI 批量研判启动"
            db.commit()
        for opinion_id in opinion_ids:
            if task.cancel_requested:
                skipped += total - processed
                break
            processed += 1
            task.progress = int((processed - 1) / total * 100) if total else 100
            task.step = f"国内 AI 研判 {processed}/{total}"
            if run:
                run.processed_count = processed
                run.success_count = success
                run.failed_count = failed
                run.skipped_count = skipped
                run.current_step = task.step
                db.commit()
            try:
                result, _ = DomesticAIService().analyze_opinion_manual(
                    db,
                    opinion_id,
                    force=force,
                    batch_run_id=run_id,
                )
                if result.status != "completed":
                    failed += 1
                    failures.append({"opinion_id": opinion_id, "error": result.error_message or "AI analysis failed"})
                    continue
                review, _ = ensure_domestic_manual_review(db, opinion_id, result.id, batch_run_id=run_id, force=force)
                event_total += int((review.event_preview or {}).get("candidate_count") or 0)
                alert_total += int((review.alert_preview or {}).get("candidate_count") or 0)
                db.commit()
                success += 1
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed += 1
                failures.append({"opinion_id": opinion_id, "error": _safe_error(exc)})
        status_value = "cancelled" if task.cancel_requested else ("partial_failed" if failed else "succeeded")
        event_preview = {"candidate_count": event_total, "requires_manual_confirmation": True}
        alert_preview = {"candidate_count": alert_total, "requires_manual_confirmation": True}
        result_payload = {
            "run_id": run_id,
            "processed_count": processed,
            "success_count": success,
            "failed_count": failed,
            "skipped_count": skipped,
            "failures": failures,
            "status": status_value,
            "event_preview": event_preview,
            "alert_preview": alert_preview,
        }
        if run:
            run.processed_count = processed
            run.success_count = success
            run.failed_count = failed
            run.skipped_count = skipped
            run.failures = failures
            run.event_preview = event_preview
            run.alert_preview = alert_preview
            run.status = status_value
            run.current_step = "国内 AI 批量研判已完成"
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        return result_payload
    finally:
        db.close()


@domestic_ai_router.post("/batch/preview")
def preview_batch(
    payload: DomesticAIBatchPayload,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("domestic:ai:analyze")),
):
    return _batch_preview(db, payload)


@domestic_ai_router.post("/batch")
def start_batch(
    payload: DomesticAIBatchPayload,
    request: Request,
    current_user: User = Depends(require_permission("domestic:ai:analyze")),
    db: Session = Depends(get_db),
):
    if payload.scope == "filters" and not payload.full_confirmation:
        raise HTTPException(status_code=422, detail="当前筛选全量 AI 研判需要二次确认")
    preview = _batch_preview(db, payload)
    if not preview["opinion_ids"]:
        raise HTTPException(status_code=422, detail="没有匹配的国内舆情需要 AI 研判")
    if preview["token_budget_exceeded"]:
        raise HTTPException(status_code=422, detail="预计 Token 消耗超过批量任务预算")
    run_id = uuid.uuid4().hex
    run = DomesticAIBatchRun(
        run_id=run_id,
        scope=payload.scope,
        filters_snapshot=preview["filters"],
        opinion_ids=preview["opinion_ids"],
        total_count=len(preview["opinion_ids"]),
        estimated_token_usage=preview["estimated_token_usage"],
        created_by=current_user.id,
        status="queued",
        current_step="任务已提交",
    )
    db.add(run)
    db.commit()
    dedupe_key = hashlib.sha256(json.dumps({"ids": preview["opinion_ids"], "force": payload.force}, sort_keys=True).encode()).hexdigest()
    try:
        task_id = start_task("domestic-ai-analysis", _run_batch, preview["opinion_ids"], payload.force, run_id, dedupe_key=dedupe_key)
    except DuplicateTaskError as exc:
        raise HTTPException(status_code=409, detail="等价的国内 AI 批量任务正在运行") from exc
    run.task_id = task_id
    log_operation(
        db,
        action="DOMESTIC_AI_BATCH_START",
        operator=current_user,
        request=request,
        resource_type="domestic_ai_batch",
        resource_id=run_id,
        details={"task_id": task_id, **preview},
    )
    db.commit()
    return {
        "run_id": run_id,
        "task_id": task_id,
        "status": "queued",
        "matched_count": preview["matched_count"],
        "pending_analysis_count": preview["pending_analysis_count"],
        "total_count": len(preview["opinion_ids"]),
        "processed_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "estimated_token_usage": preview["estimated_token_usage"],
        "message": f"任务已提交，匹配 {preview['matched_count']} 条，待研判 {preview['pending_analysis_count']} 条",
    }


def _batch_item(row: DomesticAIBatchRun) -> dict[str, Any]:
    return {
        "run_id": row.run_id,
        "task_id": row.task_id,
        "scope": row.scope,
        "filters": row.filters_snapshot or {},
        "opinion_ids": row.opinion_ids or [],
        "total_count": row.total_count,
        "processed_count": row.processed_count,
        "success_count": row.success_count,
        "failed_count": row.failed_count,
        "skipped_count": row.skipped_count,
        "status": row.status,
        "current_step": row.current_step,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "estimated_token_usage": row.estimated_token_usage,
        "actual_token_usage": row.actual_token_usage,
        "failures": row.failures or [],
        "event_preview": row.event_preview or {},
        "alert_preview": row.alert_preview or {},
        "created_by": row.created_by,
    }


@domestic_ai_router.get("/batches")
def list_batches(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("domestic:ai:batch:read")),
):
    stmt = select(DomesticAIBatchRun).order_by(DomesticAIBatchRun.created_at.desc()).offset((page - 1) * size).limit(size)
    rows = list(db.scalars(stmt).all())
    total = db.scalar(select(func.count()).select_from(DomesticAIBatchRun)) or 0
    return {"items": [_batch_item(row) for row in rows], "total": total, "page": page, "size": size}


@domestic_ai_router.get("/batch/{run_id}")
def get_batch(
    run_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("domestic:ai:batch:read")),
):
    row = db.scalar(select(DomesticAIBatchRun).where(DomesticAIBatchRun.run_id == run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Domestic AI batch not found")
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
        row.status = result.get("status", row.status)
        row.current_step = task.step or row.current_step
        row.finished_at = task.finished_at or row.finished_at
        db.commit()
    if task is None and row.status in {"queued", "running"}:
        row.status = "failed"
        row.finished_at = datetime.now(timezone.utc)
        failures = list(row.failures or [])
        if not any(isinstance(item, dict) and item.get("code") == "worker_restarted" for item in failures):
            failures.append({"code": "worker_restarted", "error": "批量任务所在服务已重启，原内存任务不可恢复"})
        row.failures = failures
        row.current_step = "批量任务所在服务已重启"
        db.commit()
    return _batch_item(row) | ({"progress": task.progress, "step": task.step, "message": task.message} if task else {})


@domestic_ai_router.post("/batch/{run_id}/cancel")
def cancel_batch(
    run_id: str,
    request: Request,
    current_user: User = Depends(require_permission("domestic:ai:batch:cancel")),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(DomesticAIBatchRun).where(DomesticAIBatchRun.run_id == run_id))
    task = cancel_task(row.task_id if row else run_id)
    if row is None or task is None:
        raise HTTPException(status_code=404, detail="Domestic AI batch not found")
    row.status = "cancelled" if task.status == "cancelled" else row.status
    row.current_step = "取消请求已提交"
    log_operation(db, action="DOMESTIC_AI_BATCH_CANCEL", operator=current_user, request=request, resource_type="domestic_ai_batch", resource_id=run_id, details={"status": task.status})
    db.commit()
    return _batch_item(row) | {"progress": task.progress, "step": task.step}


@domestic_ai_router.post("/batch/{run_id}/retry-failed")
def retry_failed(
    run_id: str,
    request: Request,
    current_user: User = Depends(require_permission("domestic:ai:analyze")),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(DomesticAIBatchRun).where(DomesticAIBatchRun.run_id == run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Domestic AI batch not found")
    ids = [int(item["opinion_id"]) for item in (row.failures or []) if isinstance(item, dict) and item.get("opinion_id")]
    if not ids:
        raise HTTPException(status_code=422, detail="没有可重试的失败记录")
    payload = DomesticAIBatchPayload(scope="selected", opinion_ids=ids, only_unanalyzed=False, force=True)
    return start_batch(payload, request, current_user, db)


def _review_item(row: DomesticManualReview, opinion: Opinion | None, operator: User | None, db: Session) -> dict[str, Any]:
    alert_count = int(
        db.scalar(
            select(func.count())
            .select_from(DomesticAIAlertCandidate)
            .where(DomesticAIAlertCandidate.review_id == row.id)
        ) or 0
    )
    display_source = {
        "use_ai_display": "ai",
        "keep_rule": "rule",
        "confirm_event_change": "rule",
        "confirm_alert_change": "ai",
        "reject_change": "rule",
    }.get(row.review_decision or "", "rule")
    return {
        "id": row.id,
        "review_id": row.id,
        "opinion_id": row.opinion_id,
        "opinion_title": opinion.title if opinion else "",
        "source": opinion.source if opinion else "",
        "publish_time": opinion.publish_time.isoformat() if opinion and opinion.publish_time else None,
        "rule_risk_snapshot": row.rule_risk_snapshot or {},
        "ai_risk_snapshot": row.ai_risk_snapshot or {},
        "display_source": display_source,
        "event_candidate_count": (row.event_preview or {}).get("candidate_count", 0),
        "alert_candidate_count": alert_count,
        "review_status": row.review_status,
        "review_decision": row.review_decision,
        "review_reason": row.review_reason,
        "reviewed_by": row.reviewed_by,
        "reviewed_by_name": operator.username if operator else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "batch_run_id": row.batch_run_id,
        "confirmation_version": row.confirmation_version,
        "display_decision": row.display_decision,
        "event_review_status": row.event_review_status,
        "alert_review_status": row.alert_review_status,
        "review_closed_at": row.review_closed_at.isoformat() if row.review_closed_at else None,
        "completed_by": row.completed_by,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "completion_reason": row.completion_reason,
        "event_preview": row.event_preview or {},
        "alert_preview": row.alert_preview or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@domestic_ai_router.get("/reviews")
def list_reviews(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_domestic_review_read),
):
    stmt = select(DomesticManualReview)
    if status:
        stmt = stmt.where(DomesticManualReview.review_status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(DomesticManualReview.created_at.desc(), DomesticManualReview.id.desc()).offset((page - 1) * size).limit(size)).all())
    opinion_ids = {row.opinion_id for row in rows}
    opinions = {row.id: row for row in db.scalars(select(Opinion).where(Opinion.id.in_(opinion_ids))).all()} if opinion_ids else {}
    user_ids = {row.reviewed_by for row in rows if row.reviewed_by}
    users = {row.id: row for row in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    return {"items": [_review_item(row, opinions.get(row.opinion_id), users.get(row.reviewed_by), db) for row in rows], "total": total, "page": page, "size": size}


@domestic_ai_router.get("/reviews/{review_id}")
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_domestic_review_read),
):
    row = db.get(DomesticManualReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Domestic manual review not found")
    return _review_item(row, db.get(Opinion, row.opinion_id), db.get(User, row.reviewed_by) if row.reviewed_by else None, db)


@domestic_ai_router.post("/reviews/{review_id}/decision")
def decide_review(
    review_id: int,
    payload: DomesticAIReviewDecisionPayload,
    request: Request,
    current_user: User = Depends(require_domestic_review_read),
    db: Session = Depends(get_db),
):
    row = db.get(DomesticManualReview, review_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Domestic manual review not found")
    now = datetime.now(timezone.utc)
    # 已关闭的复核（confirmed/rejected/superseded）不可再操作：直接幂等返回，不重复建记录。
    if row.review_status != "pending_review":
        return {
            "review": _review_item(row, db.get(Opinion, row.opinion_id), db.get(User, row.reviewed_by) if row.reviewed_by else None, db),
            "decision": row.review_decision,
            "review_status": row.review_status,
            "event_result": {},
            "alert_result": {},
            "idempotent": True,
            "message": "该复核记录已处理，本次调用未产生新的正式事件或预警。",
        }
    action = payload.decision
    # 按动作判定所需权限：四个蓝色操作只更新子状态（沿用既有细粒度权限），
    # 「完成复核」需要独立的 review:complete 写权限，「驳回全部 AI 变更」沿用 reject。
    if action == "reject_change":
        required = "domestic:ai:review:reject"
    elif action == "confirm_event_change":
        required = "domestic:events:review:confirm"
    elif action == "confirm_alert_change":
        required = "domestic:alerts:review:confirm"
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
        opinion = db.get(Opinion, row.opinion_id)
        if opinion is None:
            raise HTTPException(status_code=404, detail="Opinion not found")
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
        row.confirmation_version = f"domestic-manual-review-{row.id}-{int(now.timestamp())}"
        event_result = confirm_event_for_review(db, row, user_id=current_user.id, reason=payload.reason, request_id=payload.request_id, commit=False)
        message = "已确认事件候选并生成正式事件（仍留在待复核）" if event_result.get("created_count") else event_result.get("reason") or "已确认，未重复创建正式事件"
    elif action == "confirm_alert_change":
        row.alert_review_status = "confirmed"
        row.review_decision = action
        row.confirmation_version = f"domestic-manual-review-{row.id}-{int(now.timestamp())}"
        alert_result = confirm_alert_for_review(db, row, user_id=current_user.id, reason=payload.reason, request_id=payload.request_id, commit=False)
        message = "已确认，已生成正式预警（仍留在待复核）" if alert_result.get("created_count") else (
            "已确认，但已有相同预警，未重复创建（仍留在待复核）" if alert_result.get("deduplicated_count") else alert_result.get("reason") or "已确认，但未命中规则，未生成正式预警"
        )
    elif action == "reject_change":
        # 驳回全部 AI 变更：行离开待复核进入已驳回，不建正式记录。
        row.review_status = "rejected"
        row.review_decision = action
        opinion = db.get(Opinion, row.opinion_id)
        if opinion is not None:
            apply_review_decision(
                db,
                opinion=opinion,
                decision=action,
                rule_snapshot=row.rule_risk_snapshot,
                ai_snapshot=row.ai_risk_snapshot,
            )
        message = "已驳回该条 AI 复核（驳回全部 AI 变更），未生成正式事件或预警"
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
    row.review_reason = payload.reason.strip() or None
    row.reviewed_by = current_user.id
    log_operation(db, action="DOMESTIC_AI_MANUAL_REVIEW", operator=current_user, request=request, resource_type="domestic_manual_review", resource_id=str(row.id), details={"decision": payload.decision, "reason": payload.reason})
    if not getattr(request.state, "batch_mode", False):
        db.commit()
        db.refresh(row)
    return {
        "review": _review_item(row, db.get(Opinion, row.opinion_id), db.get(User, row.reviewed_by) if row.reviewed_by else None, db),
        "decision": payload.decision,
        "review_status": row.review_status,
        "event_result": event_result,
        "alert_result": alert_result,
        "idempotent": False,
        "message": message,
    }


@domestic_ai_router.post("/reviews/batch")
def decide_reviews_batch(
    payload: DomesticAIReviewBatchPayload,
    request: Request,
    current_user: User = Depends(require_domestic_review_read),
    db: Session = Depends(get_db),
):
    if payload.decision == "reject_change":
        required = "domestic:ai:review:reject"
    elif payload.decision == "confirm_event_change":
        required = "domestic:events:review:confirm"
    elif payload.decision == "confirm_alert_change":
        required = "domestic:alerts:review:confirm"
    else:
        required = "ai:review:read"
    if not is_superuser_user(current_user) and required not in get_user_permissions(current_user, db):
        raise HTTPException(status_code=403, detail="Permission denied")
    if payload.confirm_all:
        if not is_superuser_user(current_user) and "domestic:ai:full-confirm" not in get_user_permissions(current_user, db):
            raise HTTPException(status_code=403, detail="Full confirmation permission required")
        review_ids = list(db.scalars(select(DomesticManualReview.id).where(DomesticManualReview.review_status == "pending_review")).all())
    else:
        review_ids = list(dict.fromkeys(payload.review_ids or []))
    if not review_ids:
        raise HTTPException(status_code=422, detail="No pending reviews selected")
    results = []
    failed = []
    request.state.batch_mode = True
    display_only = {"use_ai_display", "keep_rule"}
    try:
        # 展示类决策（采用 AI 展示 / 保留规则风险）只翻转舆情展示口径，不生成任何
        # 正式事件或预警，因此可以逐条隔离执行：单条无法应用（例如缺少已完成的 AI
        # 结果）时仅记录该条失败并继续，其余条目仍正常提交。正式决策（确认事件/预警、
        # 驳回、完成复核）保持原有「全有或全无」语义，绝不改成部分成功，以避免出现
        # 半确认的正式记录。
        for index, review_id in enumerate(review_ids):
            sp = db.begin_nested()
            try:
                results.append(
                    decide_review(
                        review_id,
                        DomesticAIReviewDecisionPayload(
                            decision=payload.decision,
                            reason=payload.reason,
                            request_id=f"{payload.request_id or 'batch'}:{review_id}:{index}",
                        ),
                        request,
                        current_user,
                        db,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                db.rollback()  # 回滚到当前 savepoint，而非整笔事务
                if payload.decision in display_only:
                    failed.append({
                        "review_id": review_id,
                        "reason": _safe_error(exc),
                        "message": (
                            "该舆情暂无可采用的 AI 研判结果"
                            if payload.decision == "use_ai_display"
                            else "该舆情缺少可保留的规则风险数据"
                            if payload.decision == "keep_rule"
                            else "该条复核处理失败，请稍后重试"
                        ),
                    })
                    continue
                raise
            else:
                sp.commit()
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=409, detail=f"批量人工复核已整体回滚：{_safe_error(exc)}") from exc
    finally:
        request.state.batch_mode = False
    return {"items": results, "total": len(results), "failed": failed, "transaction": "committed"}


@domestic_ai_router.get("/results/{opinion_id}")
def list_results(
    opinion_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("ai:review:read")),
):
    rows = db.scalars(
        select(DomesticAIResult)
        .where(DomesticAIResult.opinion_id == opinion_id)
        .order_by(DomesticAIResult.created_at.desc(), DomesticAIResult.id.desc())
    ).all()
    return {"items": [serialize_domestic_ai_result(row) for row in rows], "total": len(rows)}
