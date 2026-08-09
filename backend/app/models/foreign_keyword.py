from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ForeignKeyword(Base):
    __tablename__ = "foreign_keywords"
    __table_args__ = (
        UniqueConstraint("word", name="uq_foreign_keywords_word"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="monitoring", server_default="monitoring"
    )
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="system", server_default="system"
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=10, server_default="10")
    severity_weight: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    rule_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
