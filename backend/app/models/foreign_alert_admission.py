from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlertAdmission(Base):
    __tablename__ = "foreign_alert_admissions"
    __table_args__ = (
        UniqueConstraint(
            "foreign_opinion_id",
            "foreign_ai_result_id",
            name="uq_foreign_alert_admissions_opinion_ai",
        ),
        CheckConstraint(
            "status IN ('excluded','included')",
            name="ck_foreign_alert_admissions_status",
        ),
        Index("ix_foreign_alert_admissions_status", "status"),
        Index("ix_foreign_alert_admissions_opinion", "foreign_opinion_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    foreign_opinion_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False
    )
    foreign_ai_result_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_ai_results.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="excluded", server_default="excluded"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

