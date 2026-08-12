from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignEventCandidate(Base):
    __tablename__ = "foreign_event_candidates"
    __table_args__ = (
        UniqueConstraint("candidate_key", name="uq_foreign_event_candidates_key"),
        CheckConstraint(
            "review_source IN ('manual','auto')",
            name="ck_foreign_event_candidates_review_source",
        ),
        Index("ix_foreign_event_candidates_status", "candidate_status"),
        Index("ix_foreign_event_candidates_language", "language"),
        Index("ix_foreign_event_candidates_last_seen", "last_seen_at"),
        Index("ix_foreign_event_candidates_review_source", "review_source"),
        Index("ix_foreign_event_candidates_review", "review_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_key: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    candidate_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate", server_default="candidate"
    )
    review_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual", server_default="manual"
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    risk_level_snapshot: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown"
    )
    heat_score_snapshot: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opinion_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    source_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    aggregation_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="foreign-event-v1"
    )
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_manual_reviews.id", ondelete="SET NULL"), nullable=True
    )
    representative_opinion_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
