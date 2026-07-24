from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
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

    __table_args__ = (
        # 关联唯一约束：杜绝同一事件重复挂载同一舆情（重复采集产生的冗余舆情
        # 被聚合到同一事件时，event_opinions 会出现字面重复行，导致传播溯源节点重复）。
        # 与迁移 p7evtuniq01 (uq_event_opinions_event_opinion) 保持一致。
        UniqueConstraint(
            "event_id", "opinion_id", name="uq_event_opinions_event_opinion"
        ),
    )

    def __repr__(self) -> str:
        return f"<EventOpinion event_id={self.event_id} opinion_id={self.opinion_id}>"
