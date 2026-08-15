from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.domestic_ai_result import DomesticAIResult
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.models.opinion import Opinion


def risk_level_from_score(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def current_risk_payload(
    row: Opinion | ForeignOpinion | None,
) -> dict[str, Any] | None:
    if row is None:
        return None

    source = row.current_risk_source or "rule"
    score = row.current_risk_score
    level = row.current_risk_level

    if (
        source == "rule"
        and row.current_risk_updated_at is None
        and isinstance(row, Opinion)
    ):
        score = row.risk_score
        level = risk_level_from_score(row.risk_score)

    return {
        "source": source,
        "risk_score": score,
        "risk_level": level or risk_level_from_score(score),
        "ai_result_id": row.current_ai_result_id,
        "updated_at": (
            row.current_risk_updated_at.isoformat()
            if row.current_risk_updated_at
            else None
        ),
    }


def adopt_domestic_rule(row: Opinion, *, score: int | None = None) -> None:
    score = int(row.risk_score if score is None else score)
    row.current_risk_source = "rule"
    row.current_risk_score = score
    row.current_risk_level = risk_level_from_score(score)
    row.current_ai_result_id = None
    row.current_risk_updated_at = utcnow()


def adopt_domestic_ai(row: Opinion, result: DomesticAIResult) -> None:
    if result.status != "completed" or result.risk_score is None:
        raise ValueError("A completed AI result with a risk score is required")
    row.current_risk_source = "ai"
    row.current_risk_score = int(result.risk_score)
    row.current_risk_level = risk_level_from_score(result.risk_score)
    row.current_ai_result_id = result.id
    row.current_risk_updated_at = utcnow()


def sync_domestic_rule_if_not_ai_adopted(row: Opinion) -> None:
    if (row.current_risk_source or "rule") != "ai":
        adopt_domestic_rule(row)


def adopt_foreign_rule(row: ForeignOpinion, *, score: int | None = None) -> None:
    score = int(row.current_risk_score if score is None else score)
    row.current_risk_source = "rule"
    row.current_risk_score = score
    row.current_risk_level = risk_level_from_score(score)
    row.current_ai_result_id = None
    row.current_risk_updated_at = utcnow()


def adopt_foreign_ai(row: ForeignOpinion, result_id: int, score: int | None) -> None:
    if score is None:
        raise ValueError("A completed AI result with a risk score is required")
    row.current_risk_source = "ai"
    row.current_risk_score = int(score)
    row.current_risk_level = risk_level_from_score(score)
    row.current_ai_result_id = result_id
    row.current_risk_updated_at = utcnow()


def sync_foreign_rule_if_not_ai_adopted(
    row: ForeignOpinion,
    result: ForeignRiskResult | None,
) -> None:
    if (row.current_risk_source or "rule") != "ai" and result is not None:
        adopt_foreign_rule(row, score=result.risk_score)


def apply_review_decision(
    db: Session,
    opinion: Opinion | ForeignOpinion,
    decision: str,
    rule_snapshot: dict[str, Any] | None = None,
    ai_snapshot: dict[str, Any] | None = None,
) -> None:
    rule_snapshot = rule_snapshot or {}
    ai_snapshot = ai_snapshot or {}

    if decision == "use_ai_display":
        ai_id = ai_snapshot.get("id") or ai_snapshot.get("ai_result_id")
        score = ai_snapshot.get("risk_score")
        if ai_id is None or score is None:
            raise ValueError("AI review snapshot is incomplete")

        if isinstance(opinion, Opinion):
            result = db.get(DomesticAIResult, int(ai_id))
            if result is None:
                raise ValueError("AI result not found")
            adopt_domestic_ai(opinion, result)
        else:
            result = db.get(ForeignAIResult, int(ai_id))
            if result is None or result.risk_score is None:
                raise ValueError("AI result not found")
            adopt_foreign_ai(opinion, int(ai_id), int(result.risk_score))
        return

    if decision in {
        "complete_review",
        "reject_change",
        "keep_rule",
        "confirm_event_change",
        "confirm_alert_change",
    }:
        score = rule_snapshot.get("risk_score")
        if score is None:
            score = opinion.risk_score if isinstance(opinion, Opinion) else opinion.current_risk_score

        if isinstance(opinion, Opinion):
            adopt_domestic_rule(opinion, score=int(score))
        else:
            adopt_foreign_rule(opinion, score=int(score))
