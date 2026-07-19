from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class PropagationNode(Base):
    __tablename__ = "propagation_nodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[Optional[int]] = mapped_column(ForeignKey("events.id"), index=True, nullable=True)
    opinion_id: Mapped[Optional[int]] = mapped_column(ForeignKey("opinions.id"), index=True, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("propagation_nodes.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    publish_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False, default="neutral")
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="")
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
