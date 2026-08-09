from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ForeignRiskTerm(Base):
    __tablename__ = "foreign_risk_terms"
    __table_args__ = (
        UniqueConstraint(
            "word",
            "language",
            "term_set_version",
            name="uq_foreign_risk_terms_word_language_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    severity_weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentiment: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="manual")
    term_set_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="foreign-risk-terms-v1"
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
