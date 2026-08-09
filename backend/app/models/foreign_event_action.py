from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignEventAction(Base):
    __tablename__ = "foreign_event_actions"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_foreign_event_actions_request_id"),
        Index("ix_foreign_event_actions_event_id", "foreign_event_id"),
        Index("ix_foreign_event_actions_candidate_id", "candidate_id"),
        Index("ix_foreign_event_actions_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_event_candidates.id", ondelete="SET NULL"), nullable=True
    )
    foreign_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_events.id", ondelete="SET NULL"), nullable=True
    )
    target_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_events.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
