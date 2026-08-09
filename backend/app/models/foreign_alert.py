from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ForeignAlert(Base):
    __tablename__ = "foreign_alerts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('triggered','acknowledged','resolved','suppressed','failed')",
            name="ck_foreign_alerts_status",
        ),
        CheckConstraint(
            "severity IN ('low','medium','high','critical')",
            name="ck_foreign_alerts_severity",
        ),
        CheckConstraint(
            "foreign_opinion_id IS NOT NULL OR foreign_event_id IS NOT NULL OR foreign_risk_result_id IS NOT NULL",
            name="ck_foreign_alerts_has_target",
        ),
        Index("ix_foreign_alerts_status", "status"),
        Index("ix_foreign_alerts_severity", "severity"),
        Index("ix_foreign_alerts_rule_id", "rule_id"),
        Index("ix_foreign_alerts_triggered_at", "triggered_at"),
        Index("ix_foreign_alerts_deduplication_key", "deduplication_key"),
        Index(
            "uq_foreign_alerts_deduplication_key",
            "deduplication_key",
            unique=True,
        ),
        Index("ix_foreign_alerts_opinion_id", "foreign_opinion_id"),
        Index("ix_foreign_alerts_event_id", "foreign_event_id"),
        Index("ix_foreign_alerts_evaluation_source", "evaluation_source"),
        Index("ix_foreign_alerts_ai_result", "foreign_ai_result_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_alert_rules.id", ondelete="SET NULL"), nullable=True
    )
    foreign_opinion_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_opinions.id", ondelete="SET NULL"), nullable=True
    )
    foreign_risk_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_risk_results.id", ondelete="SET NULL"), nullable=True
    )
    foreign_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_events.id", ondelete="SET NULL"), nullable=True
    )
    foreign_ai_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_ai_results.id", ondelete="SET NULL"), nullable=True
    )
    foreign_alert_admission_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_alert_admissions.id", ondelete="SET NULL"), nullable=True
    )
    evaluation_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="rule", server_default="rule"
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="triggered", server_default="triggered")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    matched_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rule_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_name_snapshot: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    opinion_title_snapshot: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    event_title_snapshot: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    deduplication_key: Mapped[str] = mapped_column(String(512), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    suppressed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    suppressed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)
