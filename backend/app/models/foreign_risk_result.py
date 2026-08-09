from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ForeignRiskResult(Base):
    __tablename__ = "foreign_risk_results"
    __table_args__ = (
        UniqueConstraint(
            "foreign_opinion_id",
            "analyzer_type",
            "model_name",
            "model_version",
            "content_hash",
            name="uq_foreign_risk_results_analysis_version",
        ),
        Index("ix_foreign_risk_results_opinion", "foreign_opinion_id"),
        Index("ix_foreign_risk_results_status", "analysis_status"),
        Index("ix_foreign_risk_results_analyzed_at", "analyzed_at"),
        Index("ix_foreign_risk_results_model_version", "model_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    foreign_opinion_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="CASCADE"),
        nullable=False,
    )
    analysis_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    sentiment_confidence: Mapped[float | None] = mapped_column(nullable=True)
    risk_category: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    matched_terms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    analyzer_type: Mapped[str] = mapped_column(String(32), nullable=False, default="rule")
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    analysis_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
