"""Alert center API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user
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
def create_rule(payload: AlertRuleCreate, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rule = AlertRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@alerts_router.put("/rules/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, payload: AlertRuleUpdate, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    db.commit()
    db.refresh(rule)
    return rule


@alerts_router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rule = db.get(AlertRule, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"detail": "Rule deleted", "id": rule_id}


@alerts_router.post("/evaluate", response_model=AlertEvaluateResponse)
def evaluate_alerts(db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    result = AlertService.evaluate(db)
    AlertService.sync_alert_events(db)
    return AlertEvaluateResponse(success=True, **result)


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
def handle_record(record_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    rec = db.get(AlertRecord, record_id)
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    rec.handled = True
    db.commit()
    db.refresh(rec)
    return rec
