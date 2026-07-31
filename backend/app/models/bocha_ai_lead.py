from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BochaAILead(Base):
    """AI Search lead, isolated from the Web Search/admin promotion pipeline."""

    __tablename__ = "bocha_ai_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("bocha_ai_search_sessions.id"), nullable=False)
    result_index: Mapped[int] = mapped_column(Integer, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_domain: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="web")
    publish_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    search_session = relationship("BochaAISearchSession", back_populates="leads")
    creator = relationship("User")

    __table_args__ = (
        Index("ix_bocha_ai_leads_session_result", "session_id", "result_index", unique=True),
        Index("ix_bocha_ai_leads_url", "url"),
        CheckConstraint("result_index >= 0", name="ck_bocha_ai_leads_result_index"),
    )
