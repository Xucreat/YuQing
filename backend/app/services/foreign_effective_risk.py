"""Single source of truth for the foreign "current effective risk".

Two independent evaluations exist for one foreign opinion:

* the **rule** evaluation in ``foreign_risk_results`` produced by the automatic
  collection pipeline (``ForeignRiskService``), and
* the **AI** evaluation in ``foreign_ai_results`` produced only by an explicit
  manual review (``ForeignAIService``).

Neither one overwrites the other. This module decides which of the two is the
*current* risk and exposes the other one as history, so the foreign opinion
list, the foreign workspace alert tab and the unified alert center never
interpret the raw tables on their own.

Resolution contract
-------------------
1. The persisted ``current_risk_*`` fields are the ordinary cross-page risk.
2. An explicit AI review decision can adopt the latest completed AI result as
   current risk; otherwise current risk remains the rule baseline.
3. Rule and AI evaluations remain available as comparison/history fields.
4. Formal alerts/events keep their own snapshots and never rewrite current risk.
5. History is never max()-ed into the current risk.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Sequence

from sqlalchemy import case, inspect, select
from sqlalchemy.orm import Session

from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_risk_service import (
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
)
from app.services.current_risk import current_risk_payload


# Kept for alert lifecycle presentation and compatibility with existing callers.
ACTIVE_ALERT_STATUSES = ("triggered", "acknowledged")
# Statuses that end an alert. Kept explicit so callers can label history.
CLOSED_ALERT_STATUSES = ("resolved", "suppressed", "failed")

RULE_SOURCE = "rule"
AI_SOURCE = "ai"
RiskSource = Literal["current", "rule", "ai"]
CURRENT_SOURCE = "current"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def risk_level_from_score(score: int | None) -> str:
    """Map a score to a level with the same thresholds as the rule engine."""
    if score is None:
        return "unknown"
    if score >= HIGH_RISK_THRESHOLD:
        return "high"
    if score >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def alert_is_active(alert: ForeignAlert | None, *, now: datetime | None = None) -> bool:
    """An alert is active while it is open and not past its validity deadline.

    ``expires_at`` is a *naive* timestamp persisted in the server TimeZone
    (Asia/Shanghai on this deployment): the DB converts the UTC-aware instants
    the app writes via ``utcnow()`` into local wall-clock time. Comparing it
    against a UTC-aware ``now`` would be off by the zone offset, so both sides
    are normalised into the same local frame before the deadline check. This
    keeps the Python decision identical to the SQL filter in
    ``effective_risk_level_expression`` (where Postgres applies the session
    TimeZone to the bound literal).
    """
    if alert is None:
        return False
    if alert.status not in ACTIVE_ALERT_STATUSES:
        return False
    expires_at = getattr(alert, "expires_at", None)
    if expires_at is None:
        return True
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone().replace(tzinfo=None)
    if now is None:
        ref = datetime.now()
    elif now.tzinfo is not None:
        ref = now.astimezone().replace(tzinfo=None)
    else:
        ref = now
    # Past the deadline -> no longer active.
    return expires_at > ref


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _rule_payload(result: ForeignRiskResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "source": RULE_SOURCE,
        "risk_result_id": result.id,
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "sentiment": result.sentiment,
        "risk_category": result.risk_category,
        "analysis_status": result.analysis_status,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "evaluated_at": _iso(result.analyzed_at),
    }


def _ai_payload(
    ai_result: ForeignAIResult | None,
    alert: ForeignAlert | None,
    *,
    is_active: bool,
) -> dict[str, Any] | None:
    if ai_result is None:
        return None
    return {
        "source": AI_SOURCE,
        "ai_result_id": ai_result.id,
        "risk_score": ai_result.risk_score,
        "risk_level": risk_level_from_score(ai_result.risk_score),
        "sentiment": ai_result.sentiment,
        "status": ai_result.status,
        "model_name": ai_result.model_name,
        "model_version": ai_result.model_version,
        "evaluated_at": _iso(ai_result.analyzed_at),
        "is_current_evaluation": bool(ai_result.is_current),
        # AI is history only; an associated alert does not put it in effect.
        "alert_id": alert.id if alert else None,
        "alert_status": alert.status if alert else None,
        "alert_active": bool(is_active),
        "in_effect": False,
    }


def _alert_payload(alert: ForeignAlert | None, *, is_active: bool) -> dict[str, Any] | None:
    if alert is None:
        return None
    return {
        "id": alert.id,
        "status": alert.status,
        "severity": alert.severity,
        "evaluation_source": alert.evaluation_source,
        "risk_score": alert.risk_score,
        "risk_level": alert.risk_level,
        "triggered_at": _iso(alert.triggered_at),
        "resolved_at": _iso(alert.resolved_at),
        "suppressed_at": _iso(alert.suppressed_at),
        "expires_at": _iso(getattr(alert, "expires_at", None)),
        "is_active": bool(is_active),
    }


def _effective_payload(
    *,
    rule: dict[str, Any] | None,
    alert: ForeignAlert | None,
) -> dict[str, Any]:
    if rule is not None:
        return {
            "source": RULE_SOURCE,
            "risk_score": rule["risk_score"],
            "risk_level": rule["risk_level"],
            "sentiment": rule["sentiment"],
            "model_name": rule["model_name"],
            "model_version": rule["model_version"],
            "evaluated_at": rule["evaluated_at"],
            "alert_id": None,
            "alert_status": alert.status if alert else None,
            "reason": "rule_baseline",
        }
    return {
        "source": RULE_SOURCE,
        "risk_score": None,
        "risk_level": "unknown",
        "sentiment": "unknown",
        "model_name": None,
        "model_version": None,
        "evaluated_at": None,
        "alert_id": None,
        "alert_status": alert.status if alert else None,
        "reason": "not_analyzed",
    }


def _display_payload(
    *,
    source: RiskSource,
    current: dict[str, Any] | None,
    rule: dict[str, Any] | None,
    ai: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return current risk by default, or an explicit comparison source."""
    if source == CURRENT_SOURCE and current is not None:
        # The persisted current risk only carries score/level/source. Enrich the
        # display view with sentiment/model_version/evaluated_at from the
        # underlying rule or AI result so the "当前风险" caliber shows the same
        # three columns as the rule/AI caliber instead of empty cells.
        src = current.get("source")
        base = rule if src == RULE_SOURCE else (ai if src == AI_SOURCE else None)
        base = base or {}
        return {
            **current,
            "sentiment": base.get("sentiment"),
            "model_version": base.get("model_version"),
            "evaluated_at": base.get("evaluated_at"),
            "fallback": False,
        }
    if source == AI_SOURCE and ai is not None:
        return {
            **ai,
            "source": AI_SOURCE,
            "fallback": False,
        }
    if rule is not None:
        return {
            **rule,
            "source": RULE_SOURCE,
            "fallback": source == AI_SOURCE,
            **({"fallback_reason": "ai_result_unavailable"} if source == AI_SOURCE else {}),
        }
    return {
        "source": RULE_SOURCE,
        "risk_score": None,
        "risk_level": "unknown",
        "sentiment": "unknown",
        "model_name": None,
        "model_version": None,
        "evaluated_at": None,
        "fallback": source == AI_SOURCE,
        **({"fallback_reason": "ai_result_unavailable"} if source == AI_SOURCE else {}),
    }


def _empty_view() -> dict[str, Any]:
    return {
        "current_risk": None,
        "effective_risk": _effective_payload(rule=None, alert=None),
        "display_risk": _display_payload(source=CURRENT_SOURCE, current=None, rule=None, ai=None),
        "rule_risk": None,
        "latest_ai_risk": None,
        "alert": None,
    }


def resolve_effective_risk(
    db: Session,
    opinion_ids: Sequence[int] | Iterable[int],
    *,
    risk_source: RiskSource = CURRENT_SOURCE,
    now: datetime | None = None,
) -> dict[int, dict[str, Any]]:
    """Resolve the effective-risk view for a batch of foreign opinions."""
    ids = [int(value) for value in dict.fromkeys(opinion_ids)]
    if not ids:
        return {}
    moment = now or _utcnow()
    bind = db.get_bind()
    inspector = inspect(bind)

    rule_by_opinion: dict[int, ForeignRiskResult] = {}
    for result in db.scalars(
        select(ForeignRiskResult)
        .where(
            ForeignRiskResult.foreign_opinion_id.in_(ids),
            ForeignRiskResult.is_current.is_(True),
        )
        .order_by(ForeignRiskResult.id.asc())
    ).all():
        rule_by_opinion[result.foreign_opinion_id] = result

    ai_by_opinion: dict[int, ForeignAIResult] = {}
    ai_by_id: dict[int, ForeignAIResult] = {}
    if inspector.has_table("foreign_ai_results"):
        for ai_result in db.scalars(
            select(ForeignAIResult)
            .where(
                ForeignAIResult.foreign_opinion_id.in_(ids),
                ForeignAIResult.status == "completed",
            )
            .order_by(ForeignAIResult.id.asc())
        ).all():
            ai_by_id[ai_result.id] = ai_result
            # Later rows win, so the newest completed AI evaluation is kept as
            # the latest history entry even when is_current was reset.
            # The newest completed result is the latest AI view, regardless of
            # whether a later retry has reset ``is_current`` on older rows.
            ai_by_opinion[ai_result.foreign_opinion_id] = ai_result

    opinion_by_id = {
        row.id: row
        for row in db.scalars(select(ForeignOpinion).where(ForeignOpinion.id.in_(ids))).all()
    }

    rule_alert_by_opinion: dict[int, ForeignAlert] = {}
    for alert in db.scalars(
        select(ForeignAlert)
        .where(
            ForeignAlert.foreign_opinion_id.in_(ids),
            ForeignAlert.evaluation_source == RULE_SOURCE,
            ForeignAlert.foreign_ai_result_id.is_(None),
        )
        .order_by(ForeignAlert.triggered_at.asc(), ForeignAlert.id.asc())
    ).all():
        opinion_id = alert.foreign_opinion_id
        if opinion_id is None:
            continue
        current = rule_alert_by_opinion.get(opinion_id)
        # Prefer an active alert; otherwise keep the most recent one.
        if current is None or alert_is_active(alert, now=moment) or not alert_is_active(current, now=moment):
            rule_alert_by_opinion[opinion_id] = alert
    views: dict[int, dict[str, Any]] = {}
    for opinion_id in ids:
        rule_result = rule_by_opinion.get(opinion_id)
        ai_result = ai_by_opinion.get(opinion_id)
        rule_alert = rule_alert_by_opinion.get(opinion_id)
        rule_payload = _rule_payload(rule_result)
        ai_payload = _ai_payload(ai_result, None, is_active=False)
        current_payload = current_risk_payload(opinion_by_id.get(opinion_id))
        display_ai_payload = ai_payload
        if current_payload is not None and current_payload.get("source") == AI_SOURCE:
            display_ai_payload = _ai_payload(
                ai_by_id.get(current_payload.get("ai_result_id")),
                None,
                is_active=False,
            )
        opinion_row = opinion_by_id.get(opinion_id)
        if (
            current_payload is not None
            and current_payload["source"] == RULE_SOURCE
            and opinion_row is not None
            and opinion_row.current_risk_updated_at is None
            and rule_payload is None
        ):
            current_payload = None
        if (
            current_payload is not None
            and current_payload["source"] == RULE_SOURCE
            and opinion_row is not None
            and opinion_row.current_risk_updated_at is None
            and rule_payload is not None
        ):
            current_payload = {
                **rule_payload,
                "source": RULE_SOURCE,
                "ai_result_id": None,
                "updated_at": None,
                "reason": "rule_baseline",
            }
        if current_payload is not None:
            current_payload = {
                **current_payload,
                "reason": "human_adopted" if current_payload["source"] == AI_SOURCE else "rule_baseline",
            }
        views[opinion_id] = {
            "current_risk": current_payload,
            "effective_risk": current_payload or _effective_payload(rule=rule_payload, alert=rule_alert),
            "display_risk": _display_payload(
                source=risk_source,
                current=current_payload,
                rule=rule_payload,
                ai=display_ai_payload,
            ),
            "rule_risk": rule_payload,
            "latest_ai_risk": ai_payload,
            "alert": _alert_payload(
                rule_alert,
                is_active=alert_is_active(rule_alert, now=moment),
            ),
        }
    return views


def resolve_one(
    db: Session,
    opinion_id: int,
    *,
    risk_source: RiskSource = CURRENT_SOURCE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve a single opinion; always returns a complete view."""
    return resolve_effective_risk(
        db, [opinion_id], risk_source=risk_source, now=now
    ).get(
        opinion_id,
        {
            **_empty_view(),
            "display_risk": _display_payload(source=risk_source, current=None, rule=None, ai=None),
        },
    )


def attach_effective_risk(
    db: Session,
    items: list[dict[str, Any]],
    *,
    id_key: str = "id",
    risk_source: RiskSource = CURRENT_SOURCE,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Merge the resolver output into already serialized dictionaries.

    Rows without an opinion id (for example event-level alerts) still receive
    the keys, but with null values, so the frontend never has to guess whether
    a missing key means "no risk" or "not resolved".
    """
    ids = [item[id_key] for item in items if item.get(id_key) is not None]
    views = resolve_effective_risk(db, ids, risk_source=risk_source, now=now)
    for item in items:
        key = item.get(id_key)
        if key is None:
            item.update(
                {
                    "effective_risk": None,
                    "current_risk": None,
                    "display_risk": None,
                    "rule_risk": None,
                    "latest_ai_risk": None,
                    "alert": None,
                }
            )
            continue
        item.update(views.get(key) or _empty_view())
    return items


def effective_risk_level_expression(
    *, risk_source: RiskSource = CURRENT_SOURCE, now: datetime | None = None
):
    """SQL expression for the selected foreign display risk level.

    Used for list filtering so the filter and the rendered column always agree.
    """
    if risk_source == CURRENT_SOURCE:
        rule_level = (
            select(ForeignRiskResult.risk_level)
            .where(
                ForeignRiskResult.foreign_opinion_id == ForeignOpinion.id,
                ForeignRiskResult.is_current.is_(True),
            )
            .order_by(ForeignRiskResult.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        return case(
            (ForeignOpinion.current_risk_updated_at.is_not(None), ForeignOpinion.current_risk_level),
            else_=rule_level,
        )

    rule_level = (
        select(ForeignRiskResult.risk_level)
        .where(
            ForeignRiskResult.foreign_opinion_id == ForeignOpinion.id,
            ForeignRiskResult.is_current.is_(True),
        )
        .order_by(ForeignRiskResult.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    if risk_source == AI_SOURCE:
        ai_level = (
            select(ForeignAIResult.risk_score)
            .where(
                ForeignAIResult.foreign_opinion_id == ForeignOpinion.id,
                ForeignAIResult.status == "completed",
            )
            .order_by(ForeignAIResult.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        ai_result_id = (
            select(ForeignAIResult.id)
            .where(
                ForeignAIResult.foreign_opinion_id == ForeignOpinion.id,
                ForeignAIResult.status == "completed",
            )
            .order_by(ForeignAIResult.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        return case(
            (
                ai_result_id.is_not(None),
                case(
                    (ai_level.is_(None), "unknown"),
                    (ai_level >= HIGH_RISK_THRESHOLD, "high"),
                    (ai_level >= MEDIUM_RISK_THRESHOLD, "medium"),
                    else_="low",
                ),
            ),
            else_=rule_level,
        )
    return rule_level
