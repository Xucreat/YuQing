"""Alert center API routes."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.alert import AlertRule, AlertRecord
from app.models.user import User
from app.schemas.alert import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleOut, AlertRuleListResponse,
    AlertRecordOut, AlertRecordListResponse, AlertEvaluateResponse,
)
from app.services.alert_service import AlertService

alerts_router = APIRouter(tags=["alerts"], dependencies=[Depends(get_current_user)])
MAX_SIZE = 100


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
def create_rule(payload: AlertRuleCreate, db: Session = Depends(get_db), _u: User = Depends(require_permission("alerts:write"))):
    rule = AlertRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@alerts_router.put("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, payload: AlertRuleUpdate, db: Session = Depends(get_db), _u: User = Depends(require_permission("alerts:write"))):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule


@alerts_router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), _u: User = Depends(require_permission("alerts:write"))):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
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
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
):
    q = db.query(AlertRecord)
    if risk_level:
        q = q.where(AlertRecord.risk_level == risk_level)
    if handled is not None:
        q = q.where(AlertRecord.handled == handled)
    total = q.count()
    rows = q.order_by(AlertRecord.id.desc()).offset((page - 1) * size).limit(size).all()
    return AlertRecordListResponse(items=rows, total=total, page=page, size=size)


@alerts_router.put("/records/{record_id}/handle", response_model=AlertRecordOut)
def handle_record(record_id: int, db: Session = Depends(get_db), _u: User = Depends(require_permission("alerts:write"))):
    rec = db.get(AlertRecord, record_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    rec.handled = True
    db.commit()
    db.refresh(rec)
    return rec
