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
1. The current effective risk is always the current rule result.
2. A manually triggered AI result is returned as ``latest_ai_risk`` history
   and never replaces or escalates the rule result.
3. Alerts describe their own lifecycle. Their status, expiry, and evaluation
   source never change ``effective_risk``.
4. History is never max()-ed into the current risk: an old high AI score cannot
   inflate a foreign opinion after the rule evaluation changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Sequence

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_risk_service import (
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
)


# Kept for alert lifecycle presentation and compatibility with existing callers.
ACTIVE_ALERT_STATUSES = ("triggered", "acknowledged")
# Statuses that end an alert. Kept explicit so callers can label history.
CLOSED_ALERT_STATUSES = ("resolved", "suppressed", "failed")

RULE_SOURCE = "rule"
AI_SOURCE = "ai"
RiskSource = Literal["rule", "ai"]


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
    rule: dict[str, Any] | None,
    ai: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return the user-selected display risk without changing the effective risk."""
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
        "effective_risk": _effective_payload(
            rule=None, alert=None
        ),
        "display_risk": _display_payload(source=RULE_SOURCE, rule=None, ai=None),
        "rule_risk": None,
        "latest_ai_risk": None,
        "alert": None,
    }


def resolve_effective_risk(
    db: Session,
    opinion_ids: Sequence[int] | Iterable[int],
    *,
    risk_source: RiskSource = RULE_SOURCE,
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
    if inspector.has_table("foreign_ai_results"):
        for ai_result in db.scalars(
            select(ForeignAIResult)
            .where(
                ForeignAIResult.foreign_opinion_id.in_(ids),
                ForeignAIResult.status == "completed",
            )
            .order_by(ForeignAIResult.id.asc())
        ).all():
            # Later rows win, so the newest completed AI evaluation is kept as
            # the latest history entry even when is_current was reset.
            # The newest completed result is the latest AI view, regardless of
            # whether a later retry has reset ``is_current`` on older rows.
            ai_by_opinion[ai_result.foreign_opinion_id] = ai_result

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
        views[opinion_id] = {
            "effective_risk": _effective_payload(
                rule=rule_payload,
                alert=rule_alert,
            ),
            "display_risk": _display_payload(
                source=risk_source,
                rule=rule_payload,
                ai=ai_payload,
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
    risk_source: RiskSource = RULE_SOURCE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve a single opinion; always returns a complete view."""
    return resolve_effective_risk(
        db, [opinion_id], risk_source=risk_source, now=now
    ).get(
        opinion_id,
        {
            **_empty_view(),
            "display_risk": _display_payload(source=risk_source, rule=None, ai=None),
        },
    )


def attach_effective_risk(
    db: Session,
    items: list[dict[str, Any]],
    *,
    id_key: str = "id",
    risk_source: RiskSource = RULE_SOURCE,
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
    *, risk_source: RiskSource = RULE_SOURCE, now: datetime | None = None
):
    """SQL expression for the selected foreign display risk level.

    Used for list filtering so the filter and the rendered column always agree.
    """
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
        from sqlalchemy import case

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
