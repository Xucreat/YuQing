from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlertRun(Base):
    __tablename__ = "foreign_alert_runs"
    __table_args__ = (
        CheckConstraint(
            "run_type IN ('manual','dry_run','auto')",
            name="ck_foreign_alert_runs_run_type",
        ),
        CheckConstraint(
            "status IN ('running','success','dry_run','failed')",
            name="ck_foreign_alert_runs_status",
        ),
        Index("ix_foreign_alert_runs_status", "status"),
        Index("ix_foreign_alert_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", server_default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    triggered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deduplicated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    suppressed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
