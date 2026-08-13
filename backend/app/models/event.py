from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keyword: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    region_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("regions.id"), index=True, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    risk_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    topic_category: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default="other"
    )
    heat_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    trend: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default="unknown"
    )
    opinion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    confirmation_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    confirmation_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rule_risk_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ai_risk_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    review_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    origin_review_id: Mapped[Optional[int]] = mapped_column(ForeignKey("domestic_manual_reviews.id", ondelete="SET NULL"), nullable=True)
    origin_ai_result_id: Mapped[Optional[int]] = mapped_column(ForeignKey("domestic_ai_results.id", ondelete="SET NULL"), nullable=True)

    # 事件 <-> 舆情（多对多，经 event_opinions 关联表）
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('active','verifying','processing','resolved','closed','deprecated')",
            name="ck_events_status",
        ),
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name="ck_events_risk_score",
        ),
        CheckConstraint(
            "topic_category IS NULL OR topic_category IN "
            "('livelihood','traffic','education','healthcare','environment',"
            "'safety','market','gov_service','social_security',"
            "'public_emergency','other')",
            name="ck_events_topic_category",
        ),
        CheckConstraint(
            "heat_score >= 0 AND heat_score <= 100",
            name="ck_events_heat_score",
        ),
        CheckConstraint(
            "trend IN ('rising','stable','falling','unknown')",
            name="ck_events_trend",
        ),
        CheckConstraint(
            "confirmation_source IS NULL OR confirmation_source IN ('manual','auto','manual_review_ai')",
            name="ck_events_confirmation_source",
        ),
    )

    opinions: Mapped[List["Opinion"]] = relationship(
        "Opinion",
        secondary="event_opinions",
        back_populates="events",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r}>"
