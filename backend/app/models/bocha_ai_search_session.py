from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BochaAISearchSession(Base):
    """Persisted, user-triggered Bocha AI Search response.

    This table is deliberately separate from ``bocha_search_sessions`` so the
    existing Web Search contract and lead foreign keys retain their meaning.
    ``raw_response`` is kept for audit/debugging of provider schema changes.
    """

    __tablename__ = "bocha_ai_search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="bocha-ai")
    query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    freshness: Mapped[str] = mapped_column(String(64), nullable=False, default="noLimit")
    include: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    answer_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    follow_up_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    images: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    modal_cards: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    web_pages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="failed")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    creator = relationship("User")
    leads = relationship("BochaAILead", back_populates="search_session")

    __table_args__ = (
        CheckConstraint("status IN ('success','failed')", name="ck_bocha_ai_search_sessions_status"),
        Index("ix_bocha_ai_search_sessions_status", "status"),
        Index("ix_bocha_ai_search_sessions_created_at", "created_at"),
        Index("ix_bocha_ai_search_sessions_query", "query"),
    )
