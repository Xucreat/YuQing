"""Manual admission of completed foreign AI results into alert evaluation."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_alert_admission import ForeignAlertAdmission
from app.models.foreign_alert_admission_action import ForeignAlertAdmissionAction
from app.models.foreign_opinion import ForeignOpinion


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlertAdmissionService:
    """Keep AI admission explicit, reversible, and foreign-only."""

    @staticmethod
    def set_status(
        db: Session,
        opinion_id: int,
        *,
        included: bool,
        actor_id: int | None,
        note: str,
    ) -> tuple[ForeignAlertAdmission, ForeignAlertAdmissionAction]:
        opinion = db.get(ForeignOpinion, opinion_id)
        if opinion is None:
            raise LookupError("Foreign opinion not found")
        ai_result = db.scalar(
            select(ForeignAIResult)
            .where(
                ForeignAIResult.foreign_opinion_id == opinion_id,
                ForeignAIResult.is_current.is_(True),
                ForeignAIResult.status == "completed",
            )
            .order_by(ForeignAIResult.id.desc())
        )
        if ai_result is None:
            raise ValueError("A completed current foreign AI result is required")

        admission = db.scalar(
            select(ForeignAlertAdmission)
            .where(
                ForeignAlertAdmission.foreign_opinion_id == opinion_id,
                ForeignAlertAdmission.foreign_ai_result_id == ai_result.id,
            )
            .with_for_update()
        )
        new_status = "included" if included else "excluded"
        if admission is None:
            admission = ForeignAlertAdmission(
                foreign_opinion_id=opinion_id,
                foreign_ai_result_id=ai_result.id,
                status=new_status,
                note=note,
                changed_by=actor_id,
                changed_at=_utcnow(),
            )
            db.add(admission)
            db.flush()
            previous_status = "excluded"
        else:
            previous_status = admission.status
            admission.status = new_status
            admission.note = note
            admission.changed_by = actor_id
            admission.changed_at = _utcnow()
            db.flush()

        action = ForeignAlertAdmissionAction(
            admission_id=admission.id,
            foreign_opinion_id=opinion_id,
            foreign_ai_result_id=ai_result.id,
            previous_status=previous_status,
            new_status=new_status,
            evaluation_source="ai",
            note=note,
            actor_id=actor_id,
        )
        db.add(action)
        db.flush()
        return admission, action

    @staticmethod
    def get_current(db: Session, opinion_id: int) -> ForeignAlertAdmission | None:
        return db.scalar(
            select(ForeignAlertAdmission)
            .where(ForeignAlertAdmission.foreign_opinion_id == opinion_id)
            .order_by(ForeignAlertAdmission.updated_at.desc(), ForeignAlertAdmission.id.desc())
        )

    @staticmethod
    def list_actions(db: Session, admission_id: int) -> list[ForeignAlertAdmissionAction]:
        return list(
            db.scalars(
                select(ForeignAlertAdmissionAction)
                .where(ForeignAlertAdmissionAction.admission_id == admission_id)
                .order_by(ForeignAlertAdmissionAction.created_at.asc(), ForeignAlertAdmissionAction.id.asc())
            ).all()
        )


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

