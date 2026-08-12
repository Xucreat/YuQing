from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignManualReview(Base):
    """Immutable snapshots and human decisions for foreign AI output."""

    __tablename__ = "foreign_manual_reviews"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending_review','confirmed','rejected','superseded')",
            name="ck_foreign_manual_reviews_status",
        ),
        CheckConstraint(
            "review_decision IS NULL OR review_decision IN ('keep_rule','use_ai_display','confirm_event_change','confirm_alert_change','reject_change')",
            name="ck_foreign_manual_reviews_decision",
        ),
        Index("ix_foreign_manual_reviews_status", "review_status"),
        Index("ix_foreign_manual_reviews_opinion", "foreign_opinion_id"),
        Index("ix_foreign_manual_reviews_batch", "batch_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    foreign_opinion_id: Mapped[int] = mapped_column(ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")
    rule_risk_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_risk_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    review_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    batch_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_preview_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_preview_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_preview: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    alert_preview: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confirmation_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
