from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlertRule(Base):
    __tablename__ = "foreign_alert_rules"
    __table_args__ = (
        CheckConstraint(
            "rule_type IN ('risk_score','risk_level','risk_category','confirmed_event','keyword_combo','ai_risk_score')",
            name="ck_foreign_alert_rules_type",
        ),
        CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="ck_foreign_alert_rules_severity",
        ),
        CheckConstraint("cooldown_seconds >= 0", name="ck_foreign_alert_rules_cooldown"),
        Index("ix_foreign_alert_rules_enabled", "is_enabled"),
        Index("ix_foreign_alert_rules_type", "rule_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    cooldown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deduplication_key_template: Mapped[str] = mapped_column(
        String(256), nullable=False, default="rule:{rule_id}:opinion:{opinion_id}:event:{event_id}"
    )
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False, default="foreign-alert-v1")
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
