from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlertAction(Base):
    __tablename__ = "foreign_alert_actions"
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('acknowledge','resolve','suppress')",
            name="ck_foreign_alert_actions_type",
        ),
        CheckConstraint(
            "previous_status IN ('triggered','acknowledged','resolved','suppressed','failed')",
            name="ck_foreign_alert_actions_previous_status",
        ),
        CheckConstraint(
            "new_status IN ('triggered','acknowledged','resolved','suppressed','failed')",
            name="ck_foreign_alert_actions_new_status",
        ),
        Index("ix_foreign_alert_actions_alert_id", "foreign_alert_id"),
        Index("ix_foreign_alert_actions_created_at", "created_at"),
        Index("ix_foreign_alert_actions_type", "action_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    foreign_alert_id: Mapped[int] = mapped_column(
        ForeignKey("foreign_alerts.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(16), nullable=False)
    new_status: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    metadata_json: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
