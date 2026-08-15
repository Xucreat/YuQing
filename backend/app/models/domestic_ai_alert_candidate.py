from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DomesticAIAlertCandidate(Base):
    __tablename__ = "domestic_ai_alert_candidates"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_domestic_ai_alert_candidates_key"),
        CheckConstraint(
            "candidate_status IN ('pending','confirmed','skipped')",
            name="ck_domestic_ai_alert_candidates_status",
        ),
        Index("ix_domestic_ai_alert_candidates_review", "review_id"),
        Index("ix_domestic_ai_alert_candidates_opinion", "opinion_id"),
        Index("ix_domestic_ai_alert_candidates_rule", "rule_id"),
        Index("ix_domestic_ai_alert_candidates_ai_result", "ai_result_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("domestic_manual_reviews.id", ondelete="CASCADE"), nullable=False
    )
    opinion_id: Mapped[int] = mapped_column(
        ForeignKey("opinions.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    ai_result_id: Mapped[int] = mapped_column(
        ForeignKey("domestic_ai_results.id", ondelete="CASCADE"), nullable=False
    )
    rule_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    matched_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    deduplication_key: Mapped[str] = mapped_column(String(512), nullable=False)
    candidate_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
