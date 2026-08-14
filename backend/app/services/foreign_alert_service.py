"""Independent rule evaluation for the foreign alert pipeline.

This service deliberately imports only foreign opinion, risk, event, rule and
alert-run models. It never calls the domestic AlertService or writes domestic
alert/event/opinion tables. Evaluation is explicit; no scheduler imports this
module.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_action import ForeignAlertAction
from app.models.foreign_alert_rule import ForeignAlertRule
from app.models.foreign_alert_run import ForeignAlertRun
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_effective_risk import (
    alert_is_active,
)


MAX_EVALUATION_ITEMS = 200
MONITORING_TERMS = {"中国", "china", "chinese"}
ALERT_STATUSES = {"triggered", "acknowledged", "resolved", "suppressed", "failed"}


@dataclass(frozen=True)
class ForeignAlertTransition:
    alert: ForeignAlert
    action: ForeignAlertAction
    idempotent: bool = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize PostgreSQL timestamp-without-time-zone values for comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_error_summary(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split())
    lowered = text.casefold()
    if any(
        marker in lowered
        for marker in (
            "traceback",
            "sqlalchemy",
            "psycopg",
            "password",
            "token",
            "secret",
            "api key",
            "proxy",
            "connection string",
        )
    ):
        return "外网告警评估失败，详细错误已隐藏"
    return text[:240]


def _as_set(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip().casefold() for item in value if str(item).strip()}


def _current_risk_rows(db: Session) -> list[tuple[ForeignRiskResult, ForeignOpinion]]:
    return list(
        db.execute(
            select(ForeignRiskResult, ForeignOpinion)
            .join(ForeignOpinion, ForeignOpinion.id == ForeignRiskResult.foreign_opinion_id)
            .where(
                ForeignRiskResult.is_current.is_(True),
                ForeignRiskResult.analysis_status == "completed",
            )
            .order_by(ForeignRiskResult.id.asc())
        ).all()
    )


def _event_representative(db: Session, event_id: int) -> ForeignOpinion | None:
    return db.scalar(
        select(ForeignOpinion)
        .join(ForeignEventOpinion, ForeignEventOpinion.foreign_opinion_id == ForeignOpinion.id)
        .where(ForeignEventOpinion.foreign_event_id == event_id)
        .order_by(ForeignOpinion.id.asc())
        .limit(1)
    )


def _risk_terms(result: ForeignRiskResult) -> set[str]:
    terms = result.matched_terms or []
    return {
        str(item.get("word", "")).strip().casefold()
        for item in terms
        if isinstance(item, dict) and str(item.get("word", "")).strip()
    }


def _risk_matches(rule: ForeignAlertRule, result: ForeignRiskResult) -> bool:
    conditions = rule.conditions or {}
    if result.risk_score is None:
        return False
    if rule.rule_type == "risk_score":
        threshold = conditions.get("threshold", conditions.get("min_score"))
        if threshold is None:
            raise ValueError("risk_score rule requires conditions.threshold")
        return float(result.risk_score) >= float(threshold)
    if rule.rule_type == "risk_level":
        levels = _as_set(conditions.get("levels", conditions.get("risk_levels")))
        if not levels:
            raise ValueError("risk_level rule requires conditions.levels")
        return str(result.risk_level or "unknown").casefold() in levels
    if rule.rule_type == "risk_category":
        categories = _as_set(conditions.get("categories", conditions.get("risk_categories")))
        if not categories:
            raise ValueError("risk_category rule requires conditions.categories")
        return str(result.risk_category or "unknown").casefold() in categories
    return False


def _keyword_combo_matches(rule: ForeignAlertRule, opinion: ForeignOpinion, result: ForeignRiskResult) -> bool:
    conditions = rule.conditions or {}
    required_monitoring = _as_set(conditions.get("monitoring_keywords"))
    required_risk = _as_set(conditions.get("risk_terms"))
    # Monitoring keywords are not risk terms. A rule made only from the three
    # collection keywords is deliberately non-triggering.
    if not required_risk or required_risk.issubset(MONITORING_TERMS):
        return False
    actual_monitoring = _as_set(opinion.matched_keywords or [])
    actual_risk = _risk_terms(result)
    if not required_monitoring.issubset(actual_monitoring):
        return False
    if not required_risk.issubset(actual_risk):
        return False
    if "risk_level" in conditions:
        levels = _as_set(conditions.get("risk_level"))
        if result.risk_level.casefold() not in levels:
            return False
    return True


def _event_matches(rule: ForeignAlertRule, event: ForeignEvent) -> bool:
    # The 7-state ForeignEvent model has no "confirmed" status. "confirmed_event"
    # rules target live, active events (consistent with
    # foreign_visualization_service.confirmed_event_count, which counts
    # event_status == "active").
    if event.event_status != "active":
        return False
    conditions = rule.conditions or {}
    checks: list[bool] = []
    if "heat_score_min" in conditions:
        checks.append(event.heat_score >= int(conditions["heat_score_min"]))
    if "opinion_count_min" in conditions:
        checks.append(event.opinion_count >= int(conditions["opinion_count_min"]))
    if not checks:
        raise ValueError("confirmed_event rule requires heat_score_min or opinion_count_min")
    return all(checks) if conditions.get("match", "all") == "all" else any(checks)


def _render_dedup_key(rule: ForeignAlertRule, *, opinion_id: int | None, event_id: int | None, source_key: str, now: datetime) -> str:
    cooldown = max(int(rule.cooldown_seconds or 0), 1)
    values = {
        "rule_id": rule.id,
        "opinion_id": opinion_id or "none",
        "event_id": event_id or "none",
        "source_key": source_key or "unknown",
        "time_bucket": int(now.timestamp()) // cooldown,
        "rule_version": rule.rule_version,
    }
    key = rule.deduplication_key_template or "rule:{rule_id}:opinion:{opinion_id}:event:{event_id}"
    for name, value in values.items():
        key = key.replace("{" + name + "}", str(value))
    # Legacy templates did not include a time bucket. Append one so a new
    # rule alert can be emitted after cooldown without violating the unique
    # index.
    if "{time_bucket}" not in (rule.deduplication_key_template or ""):
        key = f"{key}:bucket:{values['time_bucket']}"
    return key[:512]


def _rule_snapshot(rule: ForeignAlertRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "conditions": rule.conditions or {},
        "severity": rule.severity,
        "rule_version": rule.rule_version,
    }


def _target_alert_data(
    rule: ForeignAlertRule,
    *,
    opinion: ForeignOpinion | None,
    result: ForeignRiskResult | None,
    event: ForeignEvent | None,
    matched: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    source = opinion.source_name_snapshot if opinion else ""
    opinion_title = opinion.title if opinion else ""
    event_title = event.title if event else ""
    if event:
        title = f"外网事件告警：{event.title or '无标题事件'}"
        message = f"已确认外网事件满足规则“{rule.name}”，文章数={event.opinion_count}，热度={event.heat_score}。"
    else:
        title = f"外网风险告警：{opinion_title or '无标题舆情'}"
        score = result.risk_score if result else None
        message = f"外网文章满足规则“{rule.name}”，风险分={score if score is not None else '-'}。"
    ttl_hours = max(int(settings.foreign_alert_active_ttl_hours or 0), 0)
    expires_at = now + timedelta(hours=ttl_hours) if ttl_hours else None
    return {
        "rule_id": rule.id,
        "foreign_opinion_id": opinion.id if opinion else None,
        "foreign_risk_result_id": result.id if result else None,
        "foreign_ai_result_id": None,
        "foreign_alert_admission_id": None,
        "foreign_event_id": event.id if event else None,
        "evaluation_source": "rule",
        "severity": rule.severity,
        "status": "triggered",
        "title": title[:512],
        "message": message,
        "matched_conditions": matched,
        "rule_snapshot": _rule_snapshot(rule),
        "source_name_snapshot": source[:128],
        "opinion_title_snapshot": opinion_title[:512],
        "event_title_snapshot": event_title[:512],
        "risk_score": result.risk_score if result else None,
        "risk_level": (
            result.risk_level
            if result
            else (
                event.risk_level
                if event
                else "unknown"
            )
        ),
        "expires_at": expires_at,
        "deduplication_key": _render_dedup_key(
            rule,
            opinion_id=opinion.id if opinion else None,
            event_id=event.id if event else None,
            source_key=opinion.source_key if opinion else "event",
            now=now,
        ),
        "triggered_at": now,
    }


class ForeignAlertService:
    """Explicit, bounded and foreign-only alert evaluation service."""

    @staticmethod
    def evaluate(
        db: Session,
        *,
        user_id: int | None = None,
        rule_ids: list[int] | None = None,
        max_items: int = MAX_EVALUATION_ITEMS,
        dry_run: bool = True,
        _run_type: str = "manual",
        opinion_ids: list[int] | None = None,
        commit: bool = True,
    ) -> ForeignAlertRun:
        if max_items < 1 or max_items > MAX_EVALUATION_ITEMS:
            raise ValueError(f"max_items must be between 1 and {MAX_EVALUATION_ITEMS}")
        if _run_type not in {"manual", "auto"}:
            raise ValueError("Invalid foreign alert run type")
        run = ForeignAlertRun(
            run_type="dry_run" if dry_run else _run_type,
            status="running",
            created_by=user_id,
            started_at=_utcnow(),
        )
        db.add(run)
        db.flush()
        rules_stmt = select(ForeignAlertRule).where(ForeignAlertRule.is_enabled.is_(True))
        if rule_ids:
            rules_stmt = rules_stmt.where(ForeignAlertRule.id.in_(rule_ids))
        rules = list(db.scalars(rules_stmt.order_by(ForeignAlertRule.id.asc())).all())
        errors: list[str] = []
        now = _utcnow()

        for rule in rules:
            try:
                with db.begin_nested():
                    # Serialize evaluations for the same rule.  The target
                    # query and the unique insert must observe one another;
                    # otherwise concurrent workers can both pass the
                    # cooldown check before either transaction commits.
                    db.execute(select(func.pg_advisory_xact_lock(int(rule.id))))
                    # Formal alerts are driven by current rule evaluations only.
                    # AI reviews remain available as history and are deliberately
                    # excluded from this target set.
                    targets: list[tuple[ForeignOpinion | None, ForeignRiskResult | None, ForeignEvent | None, dict[str, Any]]] = []
                    if rule.rule_type in {"risk_score", "risk_level", "risk_category"}:
                        for result, opinion in _current_risk_rows(db):
                            if opinion_ids is not None and opinion.id not in set(opinion_ids):
                                continue
                            if _risk_matches(rule, result):
                                targets.append((opinion, result, None, {"risk_score": result.risk_score, "risk_level": result.risk_level, "risk_category": result.risk_category, "evaluation_source": "rule"}))
                    elif rule.rule_type == "keyword_combo":
                        for result, opinion in _current_risk_rows(db):
                            if opinion_ids is not None and opinion.id not in set(opinion_ids):
                                continue
                            if _keyword_combo_matches(rule, opinion, result):
                                targets.append((opinion, result, None, {"monitoring_keywords": opinion.matched_keywords or [], "risk_terms": result.matched_terms or [], "evaluation_source": "rule"}))
                    elif rule.rule_type == "ai_risk_score":
                        # Formal foreign alerts are never produced from AI risk
                        # scores. AI alert *candidates* are generated only
                        # during the human review gate (see
                        # foreign_manual_review_service). Skip the formal
                        # evaluation path entirely so the AI branch can never
                        # auto-create a ForeignAlert here.
                        continue
                    elif rule.rule_type == "confirmed_event":
                        for event in db.scalars(select(ForeignEvent).where(ForeignEvent.event_status == "active").order_by(ForeignEvent.id.asc())).all():
                            if _event_matches(rule, event):
                                targets.append((None, None, event, {"event_status": event.event_status, "heat_score": event.heat_score, "opinion_count": event.opinion_count, "evaluation_source": "rule"}))
                    else:
                        raise ValueError(f"unsupported foreign alert rule type: {rule.rule_type}")

                    for opinion, result, event, matched in targets[:max_items]:
                        run.processed_count += 1
                        payload = _target_alert_data(
                            rule,
                            opinion=opinion,
                            result=result,
                            event=event,
                            matched=matched,
                            now=now,
                        )
                        existing = db.scalar(
                            select(ForeignAlert)
                            .where(
                                ForeignAlert.rule_id == rule.id,
                                ForeignAlert.foreign_opinion_id == payload["foreign_opinion_id"],
                                ForeignAlert.foreign_event_id == payload["foreign_event_id"],
                            )
                            .order_by(desc(ForeignAlert.triggered_at))
                            .limit(1)
                        )
                        if existing is not None:
                            cooldown = int(rule.cooldown_seconds or 0)
                            in_cooldown = cooldown <= 0 or _as_utc(existing.triggered_at) >= now - timedelta(seconds=cooldown)
                            if in_cooldown:
                                if existing.status == "suppressed":
                                    run.suppressed_count += 1
                                else:
                                    run.deduplicated_count += 1
                                continue
                        if dry_run:
                            run.triggered_count += 1
                            continue
                        inserted = db.execute(
                            pg_insert(ForeignAlert)
                            .values(**payload)
                            .on_conflict_do_nothing(
                                index_elements=[ForeignAlert.deduplication_key]
                            )
                        )
                        if inserted.rowcount:
                            run.triggered_count += 1
                        else:
                            run.deduplicated_count += 1
                    db.flush()
            except Exception as exc:
                run.failed_count += 1
                errors.append(_safe_error_summary(str(exc)) or "rule evaluation failed")

        run.status = "dry_run" if dry_run and not errors else ("failed" if errors else "success")
        run.finished_at = _utcnow()
        run.error_message = "; ".join(errors)[:1000] if errors else None
        if commit:
            db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def auto_evaluate(
        db: Session,
        *,
        user_id: int | None = None,
        rule_ids: list[int] | None = None,
        max_items: int = MAX_EVALUATION_ITEMS,
        dry_run: bool = True,
    ) -> ForeignAlertRun:
        """Evaluate foreign alerts only when the independent auto gate is on.

        This entry point is intentionally not registered with the domestic
        scheduler. It exists for a future explicitly managed foreign worker.
        """
        if not settings.foreign_alert_auto_evaluation_enabled:
            raise PermissionError("Foreign alert auto evaluation is disabled")
        return ForeignAlertService.evaluate(
            db,
            user_id=user_id,
            rule_ids=rule_ids,
            max_items=max_items,
            dry_run=dry_run,
            _run_type="auto",
        )

    @staticmethod
    def transition(
        db: Session,
        alert_id: int,
        *,
        action_type: str,
        note: str | None,
        user_id: int | None,
    ) -> ForeignAlertTransition:
        """Apply one foreign alert action and its audit row atomically."""
        action_type = action_type.strip().casefold()
        transitions = {
            "acknowledge": ("triggered", "acknowledged"),
            "resolve": ("acknowledged", "resolved"),
            "suppress": ("triggered", "suppressed"),
        }
        if action_type not in transitions:
            raise ValueError("Unsupported foreign alert action")
        # Existing direct service callers predate the API note requirement. Keep
        # them compatible while all public API requests must provide a note.
        normalized_note = (note or "Legacy service operation").strip()
        if not normalized_note:
            raise ValueError("Action note must not be empty")
        if len(normalized_note) > 4000:
            raise ValueError("Action note is too long")

        try:
            alert = db.scalar(
                select(ForeignAlert)
                .where(ForeignAlert.id == alert_id)
                .with_for_update()
            )
            if alert is None:
                raise LookupError("Foreign alert not found")
            if alert.evaluation_source not in {"rule", "manual_review_ai"}:
                raise LookupError("Foreign alert not found")
            previous_status = alert.status
            expected_previous, new_status = transitions[action_type]

            if previous_status == new_status:
                existing = db.scalar(
                    select(ForeignAlertAction)
                    .where(
                        ForeignAlertAction.foreign_alert_id == alert.id,
                        ForeignAlertAction.action_type == action_type,
                        ForeignAlertAction.new_status == new_status,
                    )
                    .order_by(ForeignAlertAction.created_at.desc(), ForeignAlertAction.id.desc())
                    .limit(1)
                )
                if existing is not None:
                    return ForeignAlertTransition(alert=alert, action=existing, idempotent=True)
                action = ForeignAlertAction(
                    foreign_alert_id=alert.id,
                    action_type=action_type,
                    previous_status=previous_status,
                    new_status=new_status,
                    note=normalized_note,
                    actor_id=user_id,
                    metadata_json={"idempotent": True},
                )
                db.add(action)
                db.flush()
                db.commit()
                db.refresh(alert)
                db.refresh(action)
                return ForeignAlertTransition(alert=alert, action=action, idempotent=True)

            if previous_status != expected_previous:
                raise ValueError(
                    f"Invalid foreign alert transition: {previous_status} -> {new_status}"
                )

            now = _utcnow()
            alert.status = new_status
            if action_type == "acknowledge":
                alert.acknowledged_at = now
                alert.acknowledged_by = user_id
            elif action_type == "resolve":
                alert.resolved_at = now
                alert.resolved_by = user_id
            else:
                alert.suppressed_at = now
                alert.suppressed_by = user_id

            action = ForeignAlertAction(
                foreign_alert_id=alert.id,
                action_type=action_type,
                previous_status=previous_status,
                new_status=new_status,
                note=normalized_note,
                actor_id=user_id,
                metadata_json={"idempotent": False},
                created_at=now,
            )
            db.add(action)
            db.flush()
            db.commit()
            db.refresh(alert)
            db.refresh(action)
            return ForeignAlertTransition(alert=alert, action=action)
        except (LookupError, ValueError):
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise RuntimeError("Foreign alert action failed") from exc

    @staticmethod
    def acknowledge(
        db: Session,
        alert_id: int,
        *,
        user_id: int | None,
        note: str | None = None,
    ) -> ForeignAlert:
        return ForeignAlertService.transition(
            db, alert_id, action_type="acknowledge", note=note, user_id=user_id
        ).alert

    @staticmethod
    def resolve(
        db: Session,
        alert_id: int,
        *,
        user_id: int | None,
        note: str | None = None,
    ) -> ForeignAlert:
        return ForeignAlertService.transition(
            db, alert_id, action_type="resolve", note=note, user_id=user_id
        ).alert

    @staticmethod
    def suppress(
        db: Session,
        alert_id: int,
        *,
        user_id: int | None,
        note: str | None = None,
    ) -> ForeignAlert:
        return ForeignAlertService.transition(
            db, alert_id, action_type="suppress", note=note, user_id=user_id
        ).alert

    @staticmethod
    def list_actions(db: Session, alert_id: int) -> list[ForeignAlertAction]:
        alert = db.get(ForeignAlert, alert_id)
        if (
            alert is None
            or alert.evaluation_source not in {"rule", "manual_review_ai"}
        ):
            return []
        return list(
            db.scalars(
                select(ForeignAlertAction)
                .where(ForeignAlertAction.foreign_alert_id == alert_id)
                .order_by(ForeignAlertAction.created_at.asc(), ForeignAlertAction.id.asc())
            ).all()
        )


def serialize_rule(rule: ForeignAlertRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "rule_type": rule.rule_type,
        "conditions": rule.conditions or {},
        "severity": rule.severity,
        "is_enabled": rule.is_enabled,
        "cooldown_seconds": rule.cooldown_seconds,
        "deduplication_key_template": rule.deduplication_key_template,
        "rule_version": rule.rule_version,
        "created_by": rule.created_by,
        "updated_by": rule.updated_by,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def serialize_alert(alert: ForeignAlert) -> dict[str, Any]:
    return {
        "id": alert.id,
        "rule_id": alert.rule_id,
        "foreign_opinion_id": alert.foreign_opinion_id,
        "foreign_risk_result_id": alert.foreign_risk_result_id,
        "foreign_ai_result_id": alert.foreign_ai_result_id,
        "foreign_alert_admission_id": alert.foreign_alert_admission_id,
        "foreign_event_id": alert.foreign_event_id,
        "evaluation_source": alert.evaluation_source,
        "severity": alert.severity,
        "status": alert.status,
        "title": alert.title,
        "message": alert.message,
        "matched_conditions": alert.matched_conditions or {},
        "rule_snapshot": alert.rule_snapshot or {},
        "source_name_snapshot": alert.source_name_snapshot,
        "opinion_title_snapshot": alert.opinion_title_snapshot,
        "event_title_snapshot": alert.event_title_snapshot,
        "risk_score": alert.risk_score,
        "risk_level": alert.risk_level,
        "formal_risk_score": alert.risk_score,
        "formal_risk_level": alert.risk_level,
        "deduplication_key": alert.deduplication_key,
        "expires_at": alert.expires_at.isoformat() if alert.expires_at else None,
        "is_active": alert_is_active(alert),
        "triggered_at": alert.triggered_at.isoformat() if alert.triggered_at else None,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
        "suppressed_at": alert.suppressed_at.isoformat() if alert.suppressed_at else None,
        "failure_reason": _safe_error_summary(alert.failure_reason),
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "updated_at": alert.updated_at.isoformat() if alert.updated_at else None,
        "linked_opinion_current_risk": None,
    }


def serialize_action(action: ForeignAlertAction) -> dict[str, Any]:
    return {
        "id": action.id,
        "alert_id": action.foreign_alert_id,
        "action_type": action.action_type,
        "previous_status": action.previous_status,
        "new_status": action.new_status,
        "note": action.note,
        "actor_id": action.actor_id,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "metadata": action.metadata_json or {},
    }


def serialize_run(run: ForeignAlertRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "run_type": run.run_type,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "processed_count": run.processed_count,
        "triggered_count": run.triggered_count,
        "deduplicated_count": run.deduplicated_count,
        "suppressed_count": run.suppressed_count,
        "failed_count": run.failed_count,
        "error_message": _safe_error_summary(run.error_message),
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
