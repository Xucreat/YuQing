from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Opinion(Base):
    __tablename__ = "opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    publish_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id"), index=True, nullable=False
    )
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False, default="neutral")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 关键词：TEXT 逗号分隔（如 "消防,事故,投诉"），不使用 Array 类型
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # ===== Phase 2C-0：AI 分析生命周期字段 =====
    # 允许值：pending / processing / completed / failed
    analysis_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    # AI 分析完成时间（可为空，未完成时为 NULL）
    analysis_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # AI 生成的研判建议（Phase 2C-1 新增，可为空）
    analysis_suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "analysis_status IN ('pending','processing','completed','failed')",
            name="ck_opinions_analysis_status",
        ),
    )

    events: Mapped[List["Event"]] = relationship(
        "Event",
        secondary="event_opinions",
        back_populates="opinions",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Opinion id={self.id} title={self.title!r}>"
