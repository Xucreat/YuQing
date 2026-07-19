from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    keyword: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low")
    opinion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 事件 <-> 舆情（多对多，经 event_opinions 关联表）
    opinions: Mapped[List["Opinion"]] = relationship(
        "Opinion",
        secondary="event_opinions",
        back_populates="events",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r}>"
