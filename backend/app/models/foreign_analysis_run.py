from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ForeignAnalysisRun(Base):
    __tablename__ = "foreign_analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    foreign_opinion_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    batch_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    analyzer_type: Mapped[str] = mapped_column(String(32), nullable=False, default="rule")
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
