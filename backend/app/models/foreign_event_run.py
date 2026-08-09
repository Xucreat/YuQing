from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignEventRun(Base):
    __tablename__ = "foreign_event_runs"
    __table_args__ = (
        CheckConstraint("scope = 'foreign'", name="ck_foreign_event_runs_scope"),
        CheckConstraint(
            "trigger_type IN ('manual','dry_run','scheduled','auto')",
            name="ck_foreign_event_runs_trigger_type",
        ),
        Index("ix_foreign_event_runs_status", "status"),
        Index("ix_foreign_event_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="foreign", server_default="foreign"
    )
    trigger_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual"
    )
    aggregation_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="foreign-event-v1"
    )
    input_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deduplicated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    linked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="running", server_default="running"
    )
    dry_run: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
