from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAIResult(Base):
    __tablename__ = "foreign_ai_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing','completed','failed')",
            name="ck_foreign_ai_results_status",
        ),
        CheckConstraint(
            "sentiment IN ('positive','negative','neutral','unknown')",
            name="ck_foreign_ai_results_sentiment",
        ),
        Index("ix_foreign_ai_results_opinion", "foreign_opinion_id"),
        Index("ix_foreign_ai_results_status", "status"),
        Index("ix_foreign_ai_results_current", "is_current"),
        Index("ix_foreign_ai_results_analyzed_at", "analyzed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    foreign_opinion_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    batch_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False, default="deepseek")
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="foreign-ai-v1")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
