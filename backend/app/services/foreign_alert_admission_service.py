"""Retired compatibility surface for the foreign AI-admission workflow."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.foreign_alert_admission import ForeignAlertAdmission
from app.models.foreign_alert_admission_action import ForeignAlertAdmissionAction


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlertAdmissionService:
    """Expose historical admissions without creating new formal AI alerts."""

    @staticmethod
    def set_status(
        db: Session,
        opinion_id: int,
        *,
        included: bool,
        actor_id: int | None,
        note: str,
    ) -> tuple[ForeignAlertAdmission, ForeignAlertAdmissionAction]:
        # Domestic and foreign formal alerts are rule-driven. Keep this
        # endpoint for API compatibility, but do not create new AI admissions
        # after the risk-contract alignment; existing rows remain historical.
        raise ValueError("Foreign AI results are history only; formal alert admission is disabled")

    @staticmethod
    def get_current(db: Session, opinion_id: int) -> ForeignAlertAdmission | None:
        # The migration removes these rows and the API no longer exposes them.
        # Keep the method for old service callers without reintroducing the
        # retired workflow into normal product reads.
        return None

    @staticmethod
    def list_actions(db: Session, admission_id: int) -> list[ForeignAlertAdmissionAction]:
        return []


def serialize_admission(admission: ForeignAlertAdmission | None) -> dict | None:
    if admission is None:
        return None
    return {
        "id": admission.id,
        "foreign_opinion_id": admission.foreign_opinion_id,
        "foreign_ai_result_id": admission.foreign_ai_result_id,
        "status": admission.status,
        "evaluation_source": "ai",
        "note": admission.note,
        "changed_by": admission.changed_by,
        "changed_at": admission.changed_at.isoformat() if admission.changed_at else None,
        "created_at": admission.created_at.isoformat() if admission.created_at else None,
        "updated_at": admission.updated_at.isoformat() if admission.updated_at else None,
    }


def serialize_admission_action(action: ForeignAlertAdmissionAction) -> dict:
    return {
        "id": action.id,
        "admission_id": action.admission_id,
        "foreign_opinion_id": action.foreign_opinion_id,
        "foreign_ai_result_id": action.foreign_ai_result_id,
        "evaluation_source": action.evaluation_source,
        "previous_status": action.previous_status,
        "new_status": action.new_status,
        "note": action.note,
        "actor_id": action.actor_id,
        "created_at": action.created_at.isoformat() if action.created_at else None,
    }
