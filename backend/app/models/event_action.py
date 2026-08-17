from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventAction(Base):
    """User-visible event handling history."""

    __tablename__ = "event_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    old_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        CheckConstraint(
            "action_type IN ('status_change','note','assign','resolve','merge','split')",
            name="ck_event_actions_action_type",
        ),
        CheckConstraint(
            "old_status IS NULL OR old_status IN "
            "('active','verifying','processing','resolved','closed','deprecated','archived')",
            name="ck_event_actions_old_status",
        ),
        CheckConstraint(
            "new_status IS NULL OR new_status IN "
            "('active','verifying','processing','resolved','closed','deprecated','archived')",
            name="ck_event_actions_new_status",
        ),
        Index("ix_event_actions_event_id", "event_id"),
        Index("ix_event_actions_created_at", "created_at"),
    )
