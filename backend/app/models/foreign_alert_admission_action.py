from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlertAdmissionAction(Base):
    __tablename__ = "foreign_alert_admission_actions"
    __table_args__ = (
        CheckConstraint(
            "previous_status IN ('excluded','included')",
            name="ck_foreign_alert_admission_actions_previous",
        ),
        CheckConstraint(
            "new_status IN ('excluded','included')",
            name="ck_foreign_alert_admission_actions_new",
        ),
        Index("ix_foreign_alert_admission_actions_admission", "admission_id"),
        Index("ix_foreign_alert_admission_actions_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admission_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_alert_admissions.id", ondelete="CASCADE"), nullable=False
    )
    foreign_opinion_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False
    )
    foreign_ai_result_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_ai_results.id", ondelete="CASCADE"), nullable=False
    )
    previous_status: Mapped[str] = mapped_column(String(16), nullable=False)
    new_status: Mapped[str] = mapped_column(String(16), nullable=False)
    evaluation_source: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")
    note: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

