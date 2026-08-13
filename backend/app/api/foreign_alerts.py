from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.permissions import get_user_permissions, is_superuser_user, require_permission
from app.db.session import get_db
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_rule import ForeignAlertRule
from app.models.foreign_alert_run import ForeignAlertRun
from app.models.user import User
from app.services.audit_service import audit_write
from app.services.foreign_effective_risk import attach_effective_risk, resolve_one
from app.services.foreign_alert_service import (
    MAX_EVALUATION_ITEMS,
    ForeignAlertService,
    serialize_alert,
    serialize_action,
    serialize_rule,
    serialize_run,
)


foreign_alerts_router = APIRouter(
    prefix="/foreign/alerts",
    tags=["foreign-alerts"],
    dependencies=[Depends(get_current_user)],
)

foreign_alert_meta_router = APIRouter(
    prefix="/foreign",
    tags=["foreign-alerts"],
    dependencies=[Depends(get_current_user)],
)


@foreign_alert_meta_router.get("/alert-auto-evaluation/status")
def foreign_alert_auto_evaluation_status(
    _: User = Depends(require_permission("foreign:alerts:read")),
):
    return {
        "enabled": bool(settings.foreign_alert_auto_evaluation_enabled),
        "scheduler_registered": False,
        "external_notifications_enabled": False,
    }

MAX_SIZE = 100


def _visible_rule_alert_or_404(db: Session, alert_id: int) -> ForeignAlert:
    """Return a formal foreign alert (rule-sourced or human-confirmed AI).

    The cleanup migration removes legacy auto AI rows, but this guard keeps old
    databases from exposing or mutating them through an ID-based endpoint.
    """
    alert = db.get(ForeignAlert, alert_id)
    if (
        alert is None
        or alert.evaluation_source not in {"rule", "manual_review_ai"}
    ):
        raise HTTPException(status_code=404, detail="Foreign alert not found")
    return alert


class ForeignAlertRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=5000)
    rule_type: Literal["risk_score", "risk_level", "risk_category", "confirmed_event", "keyword_combo", "ai_risk_score"]
    conditions: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    is_enabled: bool = False
    cooldown_seconds: int = Field(default=0, ge=0, le=31_536_000)
    deduplication_key_template: str = Field(
        default="rule:{rule_id}:opinion:{opinion_id}:event:{event_id}", max_length=256
    )


class ForeignAlertRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=5000)
    rule_type: Literal["risk_score", "risk_level", "risk_category", "confirmed_event", "keyword_combo", "ai_risk_score"] | None = None
    conditions: dict[str, Any] | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    is_enabled: bool | None = None
    cooldown_seconds: int | None = Field(default=None, ge=0, le=31_536_000)
    deduplication_key_template: str | None = Field(default=None, max_length=256)


class EvaluatePayload(BaseModel):
    dry_run: bool = True
    rule_ids: list[int] | None = Field(default=None, max_length=100)
    max_items: int = Field(default=MAX_EVALUATION_ITEMS, ge=1, le=MAX_EVALUATION_ITEMS)


class ForeignAlertActionPayload(BaseModel):
    note: str = Field(min_length=1, max_length=4000)

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("note must not be empty")
        return normalized


def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} must be ISO8601") from exc
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _require_enable_permission(user: User, db: Session) -> None:
    if is_superuser_user(user):
        return
    if "foreign:alerts:enable" not in get_user_permissions(user, db):
        raise HTTPException(status_code=403, detail="Permission denied")


def _validate_rule_definition(rule_type: str, conditions: dict[str, Any]) -> None:
    conditions = conditions or {}
    if rule_type == "risk_score":
        threshold = conditions.get("threshold", conditions.get("min_score"))
        if threshold is None or isinstance(threshold, bool):
            raise HTTPException(status_code=422, detail="risk_score requires numeric conditions.threshold")
        try:
            float(threshold)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="risk_score threshold must be numeric") from exc
    elif rule_type == "risk_level":
        levels = conditions.get("levels", conditions.get("risk_levels"))
        if not isinstance(levels, list) or not levels or not all(str(item).strip() for item in levels):
            raise HTTPException(status_code=422, detail="risk_level requires a non-empty conditions.levels list")
    elif rule_type == "risk_category":
        categories = conditions.get("categories", conditions.get("risk_categories"))
        if not isinstance(categories, list) or not categories or not all(str(item).strip() for item in categories):
            raise HTTPException(status_code=422, detail="risk_category requires a non-empty conditions.categories list")
    elif rule_type == "confirmed_event":
        if not any(key in conditions for key in ("heat_score_min", "opinion_count_min")):
            raise HTTPException(status_code=422, detail="confirmed_event requires heat_score_min or opinion_count_min")
        for key in ("heat_score_min", "opinion_count_min"):
            if key in conditions:
                try:
                    if int(conditions[key]) < 0:
                        raise ValueError
                except (TypeError, ValueError) as exc:
                    raise HTTPException(status_code=422, detail=f"{key} must be a non-negative integer") from exc
    elif rule_type == "ai_risk_score":
        threshold = conditions.get("threshold", conditions.get("min_score"))
        if threshold is None or isinstance(threshold, bool):
            raise HTTPException(status_code=422, detail="ai_risk_score requires numeric conditions.threshold")
        try:
            float(threshold)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="ai_risk_score threshold must be numeric") from exc
    elif rule_type == "keyword_combo":
        risk_terms = conditions.get("risk_terms")
        if not isinstance(risk_terms, list) or not risk_terms or not all(str(item).strip() for item in risk_terms):
            raise HTTPException(status_code=422, detail="keyword_combo requires a non-empty conditions.risk_terms list")
        monitoring = conditions.get("monitoring_keywords", [])
        if not isinstance(monitoring, list) or not all(str(item).strip() for item in monitoring):
            raise HTTPException(status_code=422, detail="keyword_combo monitoring_keywords must be a list")


@foreign_alerts_router.get("")
def list_foreign_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    status_filter: str | None = Query(None, alias="status"),
    severity: str | None = None,
    rule_id: int | None = Query(None, ge=1),
    source: str | None = None,
    foreign_event_id: int | None = Query(None, ge=1),
    foreign_opinion_id: int | None = Query(None, ge=1),
    triggered_from: str | None = None,
    triggered_to: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:alerts:read")),
):
    # The alert center shows formal foreign alerts: rule-sourced alerts and
    # human-confirmed AI alerts (evaluation_source='manual_review_ai'). Legacy
    # auto AI admission alerts are retired and excluded.
    stmt = select(ForeignAlert).where(
        ForeignAlert.evaluation_source.in_(["rule", "manual_review_ai"])
    )
    if status_filter:
        if status_filter not in {"triggered", "acknowledged", "resolved", "suppressed", "failed"}:
            raise HTTPException(status_code=422, detail="invalid foreign alert status")
        stmt = stmt.where(ForeignAlert.status == status_filter)
    if severity:
        stmt = stmt.where(ForeignAlert.severity == severity)
    if rule_id is not None:
        stmt = stmt.where(ForeignAlert.rule_id == rule_id)
    if source:
        stmt = stmt.where(ForeignAlert.source_name_snapshot == source)
    if foreign_event_id is not None:
        stmt = stmt.where(ForeignAlert.foreign_event_id == foreign_event_id)
    if foreign_opinion_id is not None:
        stmt = stmt.where(ForeignAlert.foreign_opinion_id == foreign_opinion_id)
    start = _parse_datetime(triggered_from, "triggered_from")
    end = _parse_datetime(triggered_to, "triggered_to")
    if start:
        stmt = stmt.where(ForeignAlert.triggered_at >= start)
    if end:
        stmt = stmt.where(ForeignAlert.triggered_at <= end)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignAlert.triggered_at.desc(), ForeignAlert.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    items = [serialize_alert(row) for row in rows]
    # Keep formal alert risk separate from the linked opinion current risk.
    attach_effective_risk(db, items, id_key="foreign_opinion_id")
    for item in items:
        item["linked_opinion_current_risk"] = item.get("current_risk")
    return {"items": items, "total": total, "page": page, "size": size}


@foreign_alerts_router.get("/evaluate")
def evaluate_method_guard() -> None:
    # Keep the static path out of the integer detail route. POST is the only
    # supported evaluation method; this response is intentionally not used.
    raise HTTPException(status_code=405, detail="Method not allowed")


@foreign_alerts_router.post("/evaluate")
def evaluate_foreign_alerts(
    payload: EvaluatePayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:evaluate")),
    db: Session = Depends(get_db),
):
    with audit_write(
        db,
        action="EVALUATE_FOREIGN_ALERTS",
        operator=current_user,
        request=request,
        resource_type="foreign_alert_run",
        details={"dry_run": payload.dry_run, "rule_ids": payload.rule_ids, "max_items": payload.max_items},
    ) as ctx:
        run = ForeignAlertService.evaluate(
            db,
            user_id=current_user.id,
            rule_ids=payload.rule_ids,
            max_items=payload.max_items,
            dry_run=payload.dry_run,
        )
        ctx["resource_id"] = str(run.id)
    return serialize_run(run)


@foreign_alerts_router.get("/{alert_id}/actions")
def list_foreign_alert_actions(
    alert_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:alerts:read")),
):
    _visible_rule_alert_or_404(db, alert_id)
    actions = ForeignAlertService.list_actions(db, alert_id)
    return {"items": [serialize_action(action) for action in actions], "total": len(actions)}


@foreign_alerts_router.get("/{alert_id}")
def get_foreign_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:alerts:read")),
):
    alert = _visible_rule_alert_or_404(db, alert_id)
    payload = serialize_alert(alert)
    if alert.foreign_opinion_id:
        payload.update(resolve_one(db, alert.foreign_opinion_id))
    else:
        payload.update(
            {"effective_risk": None, "current_risk": None, "rule_risk": None, "latest_ai_risk": None, "alert": None}
        )
    payload["linked_opinion_current_risk"] = payload.get("current_risk")
    payload["rule"] = serialize_rule(db.get(ForeignAlertRule, alert.rule_id)) if alert.rule_id and db.get(ForeignAlertRule, alert.rule_id) else None
    payload["actions"] = [serialize_action(item) for item in ForeignAlertService.list_actions(db, alert_id)]
    if alert.foreign_opinion_id:
        from app.api.foreign import _foreign_opinion_detail
        from app.models.foreign_opinion import ForeignOpinion

        opinion = db.get(ForeignOpinion, alert.foreign_opinion_id)
        payload["opinion"] = _foreign_opinion_detail(db, opinion) if opinion else None
    else:
        payload["opinion"] = None
    if alert.foreign_event_id:
        from app.api.foreign_events import get_foreign_event

        payload["event"] = get_foreign_event(alert.foreign_event_id, db, _)
    else:
        payload["event"] = None
    return payload


@foreign_alerts_router.post("/{alert_id}/acknowledge")
def acknowledge_foreign_alert(
    alert_id: int,
    payload: ForeignAlertActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:acknowledge")),
    db: Session = Depends(get_db),
):
    audit_details = {"note": payload.note, "action_type": "acknowledge"}
    with audit_write(
        db,
        action="ACKNOWLEDGE_FOREIGN_ALERT",
        operator=current_user,
        request=request,
        resource_type="foreign_alert",
        resource_id=str(alert_id),
        details=audit_details,
    ):
        try:
            _visible_rule_alert_or_404(db, alert_id)
            transition = ForeignAlertService.transition(
                db,
                alert_id,
                action_type="acknowledge",
                note=payload.note,
                user_id=current_user.id,
            )
            audit_details.update(
                {
                    "previous_status": transition.action.previous_status,
                    "new_status": transition.action.new_status,
                    "idempotent": transition.idempotent,
                }
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {**serialize_action(transition.action), "alert": serialize_alert(transition.alert), "idempotent": transition.idempotent}


@foreign_alerts_router.post("/{alert_id}/resolve")
def resolve_foreign_alert(
    alert_id: int,
    payload: ForeignAlertActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:resolve")),
    db: Session = Depends(get_db),
):
    audit_details = {"note": payload.note, "action_type": "resolve"}
    with audit_write(
        db,
        action="RESOLVE_FOREIGN_ALERT",
        operator=current_user,
        request=request,
        resource_type="foreign_alert",
        resource_id=str(alert_id),
        details=audit_details,
    ):
        try:
            _visible_rule_alert_or_404(db, alert_id)
            transition = ForeignAlertService.transition(
                db,
                alert_id,
                action_type="resolve",
                note=payload.note,
                user_id=current_user.id,
            )
            audit_details.update(
                {
                    "previous_status": transition.action.previous_status,
                    "new_status": transition.action.new_status,
                    "idempotent": transition.idempotent,
                }
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {**serialize_action(transition.action), "alert": serialize_alert(transition.alert), "idempotent": transition.idempotent}


@foreign_alerts_router.post("/{alert_id}/suppress")
def suppress_foreign_alert(
    alert_id: int,
    payload: ForeignAlertActionPayload,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:suppress")),
    db: Session = Depends(get_db),
):
    audit_details = {"note": payload.note, "action_type": "suppress"}
    with audit_write(
        db,
        action="SUPPRESS_FOREIGN_ALERT",
        operator=current_user,
        request=request,
        resource_type="foreign_alert",
        resource_id=str(alert_id),
        details=audit_details,
    ):
        try:
            _visible_rule_alert_or_404(db, alert_id)
            transition = ForeignAlertService.transition(
                db,
                alert_id,
                action_type="suppress",
                note=payload.note,
                user_id=current_user.id,
            )
            audit_details.update(
                {
                    "previous_status": transition.action.previous_status,
                    "new_status": transition.action.new_status,
                    "idempotent": transition.idempotent,
                }
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {**serialize_action(transition.action), "alert": serialize_alert(transition.alert), "idempotent": transition.idempotent}


@foreign_alert_meta_router.get("/alert-rules")
def list_foreign_alert_rules(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    is_enabled: bool | None = None,
    rule_type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:alerts:rules:read")),
):
    stmt = select(ForeignAlertRule)
    if is_enabled is not None:
        stmt = stmt.where(ForeignAlertRule.is_enabled == is_enabled)
    if rule_type:
        stmt = stmt.where(ForeignAlertRule.rule_type == rule_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignAlertRule.id.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return {"items": [serialize_rule(row) for row in rows], "total": total, "page": page, "size": size}


@foreign_alert_meta_router.post("/alert-rules", status_code=status.HTTP_201_CREATED)
def create_foreign_alert_rule(
    payload: ForeignAlertRuleCreate,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:rules:write")),
    db: Session = Depends(get_db),
):
    if payload.is_enabled:
        raise HTTPException(status_code=422, detail="New foreign alert rules must start disabled")
    _validate_rule_definition(payload.rule_type, payload.conditions)
    with audit_write(
        db,
        action="CREATE_FOREIGN_ALERT_RULE",
        operator=current_user,
        request=request,
        resource_type="foreign_alert_rule",
        details=payload.model_dump(mode="json"),
    ) as ctx:
        rule = ForeignAlertRule(
            **payload.model_dump(exclude={"is_enabled"}),
            is_enabled=False,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        ctx["resource_id"] = str(rule.id)
    return serialize_rule(rule)


@foreign_alert_meta_router.patch("/alert-rules/{rule_id}")
def update_foreign_alert_rule(
    rule_id: int,
    payload: ForeignAlertRuleUpdate,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:rules:write")),
    db: Session = Depends(get_db),
):
    rule = db.get(ForeignAlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Foreign alert rule not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_enabled") is True:
        _require_enable_permission(current_user, db)
    next_type = values.get("rule_type", rule.rule_type)
    next_conditions = values.get("conditions", rule.conditions or {})
    _validate_rule_definition(next_type, next_conditions)
    with audit_write(
        db,
        action="UPDATE_FOREIGN_ALERT_RULE",
        operator=current_user,
        request=request,
        resource_type="foreign_alert_rule",
        resource_id=str(rule_id),
        details=values,
    ):
        for key, value in values.items():
            setattr(rule, key, value)
        rule.updated_by = current_user.id
        rule.rule_version = f"foreign-alert-{rule.id}-{int(datetime.now(timezone.utc).timestamp())}"
        db.commit()
        db.refresh(rule)
    return serialize_rule(rule)


@foreign_alert_meta_router.get("/alert-rules/{rule_id}")
def get_foreign_alert_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:alerts:rules:read")),
):
    rule = db.get(ForeignAlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Foreign alert rule not found")
    payload = serialize_rule(rule)
    payload["alert_count"] = db.scalar(
        select(func.count()).select_from(ForeignAlert).where(ForeignAlert.rule_id == rule.id)
    ) or 0
    return payload


@foreign_alert_meta_router.post("/alert-rules/{rule_id}/enable")
def enable_foreign_alert_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:rules:write")),
    db: Session = Depends(get_db),
):
    _require_enable_permission(current_user, db)
    rule = db.get(ForeignAlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Foreign alert rule not found")
    _validate_rule_definition(rule.rule_type, rule.conditions or {})
    with audit_write(db, action="ENABLE_FOREIGN_ALERT_RULE", operator=current_user, request=request,
                     resource_type="foreign_alert_rule", resource_id=str(rule_id), details={}):
        rule.is_enabled = True
        rule.updated_by = current_user.id
        rule.rule_version = f"foreign-alert-{rule.id}-{int(datetime.now(timezone.utc).timestamp())}"
        db.commit()
        db.refresh(rule)
    return serialize_rule(rule)


@foreign_alert_meta_router.post("/alert-rules/{rule_id}/disable")
def disable_foreign_alert_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:rules:write")),
    db: Session = Depends(get_db),
):
    rule = db.get(ForeignAlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Foreign alert rule not found")
    with audit_write(db, action="DISABLE_FOREIGN_ALERT_RULE", operator=current_user, request=request,
                     resource_type="foreign_alert_rule", resource_id=str(rule_id), details={}):
        rule.is_enabled = False
        rule.updated_by = current_user.id
        rule.rule_version = f"foreign-alert-{rule.id}-{int(datetime.now(timezone.utc).timestamp())}"
        db.commit()
        db.refresh(rule)
    return serialize_rule(rule)


@foreign_alert_meta_router.delete("/alert-rules/{rule_id}")
def delete_foreign_alert_rule(
    rule_id: int,
    request: Request,
    current_user: User = Depends(require_permission("foreign:alerts:rules:write")),
    db: Session = Depends(get_db),
):
    rule = db.get(ForeignAlertRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Foreign alert rule not found")
    if rule.is_enabled:
        raise HTTPException(status_code=409, detail="Disable the foreign alert rule before deleting it")
    with audit_write(db, action="DELETE_FOREIGN_ALERT_RULE", operator=current_user, request=request,
                     resource_type="foreign_alert_rule", resource_id=str(rule_id), details={}):
        db.delete(rule)
        db.commit()
    return {"deleted": True, "id": rule_id}


@foreign_alert_meta_router.get("/alert-runs")
def list_foreign_alert_runs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=MAX_SIZE),
    run_status: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("foreign:alerts:read")),
):
    stmt = select(ForeignAlertRun)
    if run_status:
        stmt = stmt.where(ForeignAlertRun.status == run_status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ForeignAlertRun.started_at.desc(), ForeignAlertRun.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return {"items": [serialize_run(row) for row in rows], "total": total, "page": page, "size": size}
