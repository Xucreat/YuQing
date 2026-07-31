from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BochaLead(Base):
    """Auxiliary Bocha search lead.

    These rows are intentionally isolated from the Collector pipeline. They are
    search candidates only and must not trigger risk scoring, event aggregation,
    or alert generation until a later explicit promotion flow creates Opinion.
    """

    __tablename__ = "bocha_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="bocha", server_default="bocha")
    query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    provider_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    publish_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    opinion_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("opinions.id"), nullable=True, index=True
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    search_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("bocha_search_sessions.id"), nullable=True, index=True
    )
    result_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    opinion = relationship("Opinion")
    creator = relationship("User")
    search_session = relationship("BochaSearchSession", back_populates="leads")

    @property
    def creator_name(self) -> str | None:
        """显示名：优先 display_name，回退 username；无创建人则返回 None。"""
        if self.creator is None:
            return None
        return self.creator.display_name or self.creator.username

    __table_args__ = (
        CheckConstraint(
            "status IN ('new','confirmed','rejected','promoted')",
            name="ck_bocha_leads_status",
        ),
        Index("ix_bocha_leads_status", "status"),
        Index("ix_bocha_leads_url", "url"),
        Index("ix_bocha_leads_created_at", "created_at"),
        Index("ix_bocha_leads_search_result", "search_session_id", "result_index"),
        Index("ix_bocha_leads_provider_status_created", "provider", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<BochaLead id={self.id} status={self.status!r} title={self.title!r}>"
