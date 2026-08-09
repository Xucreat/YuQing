from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignEventOpinion(Base):
    __tablename__ = "foreign_event_opinions"
    __table_args__ = (
        UniqueConstraint(
            "foreign_event_id",
            "foreign_opinion_id",
            name="uq_foreign_event_opinions_event_opinion",
        ),
        CheckConstraint(
            "relation_type IN ('primary','secondary','duplicate','manual')",
            name="ck_foreign_event_opinions_relation_type",
        ),
        Index("ix_foreign_event_opinions_event_id", "foreign_event_id"),
        Index("ix_foreign_event_opinions_opinion_id", "foreign_opinion_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    foreign_event_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_events.id", ondelete="CASCADE"), nullable=False
    )
    foreign_opinion_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="primary"
    )
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_terms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
