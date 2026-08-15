from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAIAlertCandidate(Base):
    """AI-driven foreign alert candidates generated during manual review.

    These are produced *only* from ``ai_risk_score`` rule matches against a
    completed ``ForeignAIResult``. They are persisted so the human reviewer can
    see exactly what the AI path would have alerted, and so confirmation is
    auditable and idempotent. No formal ``ForeignAlert`` is created until a
    human explicitly confirms the candidate via the manual-review gate.
    """

    __tablename__ = "foreign_ai_alert_candidates"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_foreign_ai_alert_candidates_key"),
        CheckConstraint(
            "candidate_status IN ('pending','confirmed','skipped')",
            name="ck_foreign_ai_alert_candidates_status",
        ),
        Index("ix_foreign_ai_alert_candidates_review", "review_id"),
        Index("ix_foreign_ai_alert_candidates_opinion", "opinion_id"),
        Index("ix_foreign_ai_alert_candidates_rule", "rule_id"),
        Index("ix_foreign_ai_alert_candidates_ai_result", "ai_result_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_manual_reviews.id", ondelete="CASCADE"), nullable=False
    )
    opinion_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    ai_result_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_ai_results.id", ondelete="CASCADE"), nullable=False
    )
    rule_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ai_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    matched_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    candidate_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    deduplication_key: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
