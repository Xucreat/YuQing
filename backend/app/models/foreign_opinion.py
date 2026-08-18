from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ForeignOpinion(Base):
    __tablename__ = "foreign_opinions"
    __table_args__ = (
        Index(
            "ix_foreign_opinions_url_unique",
            "url",
            unique=True,
            postgresql_where=text("url IS NOT NULL AND url <> ''"),
        ),
        Index("ix_foreign_opinions_content_hash", "content_hash"),
        Index("ix_foreign_opinions_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_key: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_name_snapshot: Mapped[str] = mapped_column(
        String(128), nullable=False, default=""
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    matched_keywords: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # Content classification is independent from risk_category on the rule result.
    content_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    content_type_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Current risk is the human-adopted display risk. Rule/AI evaluations stay
    # separately queryable and formal events/alerts keep their own snapshots.
    current_risk_source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="rule", server_default="rule"
    )
    current_risk_score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    current_risk_level: Mapped[str] = mapped_column(
        String(16), nullable=False, default="low", server_default="low"
    )
    current_ai_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("foreign_ai_results.id", ondelete="SET NULL"), nullable=True
    )
    current_risk_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
