from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DomesticAIBatchRun(Base):
    __tablename__ = "domestic_ai_batch_runs"
    __table_args__ = (
        Index("ix_domestic_ai_batch_runs_status", "status"),
        Index("ix_domestic_ai_batch_runs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scope: Mapped[str] = mapped_column(String(24), nullable=False, default="recent")
    filters_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    opinion_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    current_step: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estimated_token_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_token_usage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failures: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    event_preview: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    alert_preview: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
