from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventOpinion(Base):
    __tablename__ = "event_opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id"), index=True, nullable=False
    )
    opinion_id: Mapped[int] = mapped_column(
        ForeignKey("opinions.id"), index=True, nullable=False
    )

    def __repr__(self) -> str:
        return f"<EventOpinion event_id={self.event_id} opinion_id={self.opinion_id}>"
