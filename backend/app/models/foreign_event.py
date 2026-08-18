from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignEvent(Base):
    __tablename__ = "foreign_events"
    __table_args__ = (
        CheckConstraint(
            "event_status IN ('active','verifying','processing','resolved','closed','deprecated','archived')",
            name="ck_foreign_events_status",
        ),
        CheckConstraint(
            "confirmation_source IN ('manual','auto','manual_review_ai')",
            name="ck_foreign_events_confirmation_source",
        ),
        Index("ix_foreign_events_status", "event_status"),
        Index("ix_foreign_events_language", "language"),
        Index("ix_foreign_events_last_seen", "last_seen_at"),
        Index("ix_foreign_events_confirmation_source", "confirmation_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    event_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    confirmation_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="manual", server_default="manual"
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    heat_score: Mapped[int] = mapped_column(
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
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    aggregation_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="foreign-event-v1"
    )
    origin_candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_event_candidates.id", ondelete="SET NULL"), nullable=True
    )
    canonical_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_events.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )
    confirmed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Manual-review provenance. Populated only when a human confirms an
    # AI-driven event change; never overwrites the rule/effective risk.
    rule_risk_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_risk_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
