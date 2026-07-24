"""Alert center API routes."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.alert import AlertRule, AlertRecord
from app.models.user import User
from app.schemas.alert import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleOut, AlertRuleListResponse,
    AlertRecordOut, AlertRecordListResponse, AlertEvaluateResponse,
    AlertHandleRequest,
)
from app.services.alert_service import AlertService
from app.services.audit_service import audit_write

alerts_router = APIRouter(tags=["alerts"], dependencies=[Depends(get_current_user)])
MAX_SIZE = 100

# 处置状态白名单（与 AlertRecord.status CheckConstraint 一致）
_ALLOWED_ALERT_STATUSES = {"pending", "processing", "resolved", "ignored", "false_positive"}


def _parse_since(since: str | None) -> datetime | None:
    """解析 ISO8601 时间戳（兼容结尾 Z），返回 UTC aware datetime；无效则 None。"""
    if not since:
        return None
    s = since.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@alerts_router.get("/rules", response_model=AlertRuleListResponse)
def list_rules(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
):
    total = db.query(AlertRule).count()
    rows = db.query(AlertRule).order_by(AlertRule.id.desc()).offset((page - 1) * size).limit(size).all()
    return AlertRuleListResponse(items=rows, total=total, page=page, size=size)


@alerts_router.post("/rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(payload: AlertRuleCreate, request: Request, current_user: User = Depends(require_permission("alerts:write")), db: Session = Depends(get_db)):
    with audit_write(db, action="CREATE", operator=current_user, request=request, resource_type="alert_rule", details=payload.model_dump(mode="json")) as ctx:
        rule = AlertRule(**payload.model_dump())
        db.add(rule)
        db.commit()
        ctx["resource_id"] = str(rule.id)
    db.refresh(rule)
    return rule


@alerts_router.put("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, payload: AlertRuleUpdate, request: Request, current_user: User = Depends(require_permission("alerts:write")), db: Session = Depends(get_db)):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    with audit_write(db, action="UPDATE", operator=current_user, request=request, resource_type="alert_rule", resource_id=str(rule_id), details=payload.model_dump(exclude_unset=True, mode="json")):
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(rule, k, v)
        db.commit()
    db.refresh(rule)
    return rule


@alerts_router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, request: Request, current_user: User = Depends(require_permission("alerts:write")), db: Session = Depends(get_db)):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    with audit_write(db, action="DELETE", operator=current_user, request=request, resource_type="alert_rule", resource_id=str(rule_id), details={"name": rule.name if hasattr(rule, "name") else None}):
        db.delete(rule)
        db.commit()
    return {"detail": "Rule deleted", "id": rule_id}


@alerts_router.post("/evaluate", response_model=AlertEvaluateResponse)
def evaluate_alerts(db: Session = Depends(get_db), _u: User = Depends(require_permission("alerts:write"))):
    result = AlertService.evaluate(db)
    AlertService.sync_alert_events(db)
    return AlertEvaluateResponse(success=True, **result)


@alerts_router.get("/unread", response_model=AlertRecordListResponse)
def unread_alerts(
    since: str | None = Query(None, description="ISO8601 时间戳，仅返回该时间之后创建的预警记录"),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
):
    """前端轮询用：返回 since 之后产生的新预警（最多 10 条，含 total 总数）。"""
    q = db.query(AlertRecord)
    since_dt = _parse_since(since)
    if since_dt is not None:
        q = q.where(AlertRecord.created_at > since_dt)
    total = q.count()
    rows = q.order_by(AlertRecord.id.desc()).limit(10).all()
    return AlertRecordListResponse(items=rows, total=total, page=1, size=10)


@alerts_router.get("/records", response_model=AlertRecordListResponse)
def list_records(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    risk_level: str | None = None,
    handled: bool | None = None,
    status: str | None = None,
    exclude_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
):
    # status 合法性校验：非法值返回 422
    if status is not None and status not in _ALLOWED_ALERT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status 必须为以下之一：{sorted(_ALLOWED_ALERT_STATUSES)}",
        )
    if exclude_status is not None and exclude_status not in _ALLOWED_ALERT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"exclude_status 必须为以下之一：{sorted(_ALLOWED_ALERT_STATUSES)}",
        )
    q = db.query(AlertRecord)
    if risk_level:
        q = q.where(AlertRecord.risk_level == risk_level)
    if handled is not None:
        q = q.where(AlertRecord.handled == handled)
    if status:
        q = q.where(AlertRecord.status == status)
    if exclude_status:
        q = q.where(AlertRecord.status != exclude_status)
    # 时间范围过滤（沿用 opinions 的 YYYY-MM-DD 约定，按 created_at 日期部分）
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d").date()
            q = q.where(func.date(AlertRecord.created_at) >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d").date()
            q = q.where(func.date(AlertRecord.created_at) <= d)
        except ValueError:
            pass
    total = q.count()
    rows = q.order_by(AlertRecord.id.desc()).offset((page - 1) * size).limit(size).all()
    return AlertRecordListResponse(items=rows, total=total, page=page, size=size)


# 处置状态 → handled 布尔双写映射（保护旧 ?handled= 过滤与前端标签）。
_RESOLVED_STATES = {"resolved", "ignored", "false_positive"}


@alerts_router.put("/records/{record_id}/handle", response_model=AlertRecordOut)
def handle_record(
    record_id: int,
    request: Request,
    payload: Optional[AlertHandleRequest] = Body(default=None),
    current_user: User = Depends(require_permission("alerts:write")),
    db: Session = Depends(get_db),
):
    """处置一条预警记录。

    兼容旧调用（无 body）：等价 {status: "resolved", note: ""}。
    新调用可指定 status ∈ {pending, processing, resolved, ignored, false_positive} 与备注。
    写入 handled_by / handled_at / handle_note，status 与 handled 双写，并记录 HANDLE_ALERT 审计。
    """
    rec = db.get(AlertRecord, record_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")

    # 无 body → 旧兼容语义：一键标记为已解决。
    req = payload or AlertHandleRequest()
    old_status = rec.status
    new_status = req.status

    with audit_write(
        db,
        action="HANDLE_ALERT",
        operator=current_user,
        request=request,
        resource_type="alert_record",
        resource_id=str(record_id),
        details={"old_status": old_status, "new_status": new_status, "note": req.note},
    ):
        rec.status = new_status
        rec.handled = new_status in _RESOLVED_STATES
        rec.handled_by = current_user.id
        rec.handled_at = datetime.now(timezone.utc)
        rec.handle_note = req.note or ""
        db.commit()
    db.refresh(rec)
    return rec
