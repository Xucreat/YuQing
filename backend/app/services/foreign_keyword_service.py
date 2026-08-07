from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.foreign_keyword import ForeignKeyword


def get_foreign_keywords(db: Session) -> list[str]:
    rows = db.scalars(
        select(ForeignKeyword.word)
        .where(ForeignKeyword.is_enabled.is_(True))
        .order_by(ForeignKeyword.id)
    ).all()
    return [word.strip() for word in rows if word and word.strip()]
