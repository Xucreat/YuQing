from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BochaSearchSession(Base):
    """A user-triggered Bocha AI search session.

    Sessions record active search behavior and normalized search results. They
    are intentionally separate from Collector and Opinion pipelines.
    """

    __tablename__ = "bocha_search_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    freshness: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    summary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    raw_results: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    creator = relationship("User")
    leads = relationship("BochaLead", back_populates="search_session")

    __table_args__ = (
        CheckConstraint(
            "status IN ('success','failed')",
            name="ck_bocha_search_sessions_status",
        ),
        Index("ix_bocha_search_sessions_status", "status"),
        Index("ix_bocha_search_sessions_created_at", "created_at"),
        Index("ix_bocha_search_sessions_query", "query"),
    )

    def __repr__(self) -> str:
        return f"<BochaSearchSession id={self.id} status={self.status!r} query={self.query!r}>"
