from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")

    def __repr__(self) -> str:
        return f"<Keyword word={self.word!r} weight={self.weight}>"
