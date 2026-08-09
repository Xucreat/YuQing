from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, insert, inspect, select, update
from sqlalchemy.orm import Session

from app.models.foreign_keyword import ForeignKeyword


MANAGEMENT_COLUMNS = {
    "type",
    "source",
    "weight",
    "severity_weight",
    "rule_config",
}


def foreign_keyword_columns(db: Session) -> set[str]:
    """Return physical columns so code remains readable before 5A migration."""
    bind = db.get_bind()
    if bind is None:
        return set()
    return {item["name"] for item in inspect(bind).get_columns("foreign_keywords")}


def _keyword_select(db: Session):
    columns = foreign_keyword_columns(db)
    selected = [
        ForeignKeyword.id,
        ForeignKeyword.word,
        ForeignKeyword.category,
        ForeignKeyword.is_enabled,
        ForeignKeyword.created_at,
        ForeignKeyword.updated_at,
    ]
    for name in MANAGEMENT_COLUMNS:
        if name in columns:
            selected.append(getattr(ForeignKeyword, name))
    return select(*selected), columns


def serialize_foreign_keyword(row, columns: set[str] | None = None) -> dict:
    values = row._mapping if hasattr(row, "_mapping") else row
    data = {
        "id": values["id"],
        "word": values["word"],
        "category": values["category"],
        "is_enabled": bool(values["is_enabled"]),
        "created_at": values["created_at"].isoformat() if values["created_at"] else None,
        "updated_at": values["updated_at"].isoformat() if values["updated_at"] else None,
    }
    columns = columns or set(values.keys())
    data.update(
        {
            "type": values["type"] if "type" in columns else "monitoring",
            "source": values["source"] if "source" in columns else "system",
            "weight": values["weight"] if "weight" in columns else 10,
            "severity_weight": values["severity_weight"] if "severity_weight" in columns else 0,
            "rule_config": values["rule_config"] if "rule_config" in columns else {},
        }
    )
    return data


def list_foreign_keyword_rows(
    db: Session,
    *,
    page: int = 1,
    size: int = 50,
    q: str | None = None,
    category: str | None = None,
    type_: str | None = None,
    source: str | None = None,
    is_enabled: bool | None = None,
):
    stmt, columns = _keyword_select(db)
    if q:
        stmt = stmt.where(ForeignKeyword.word.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(ForeignKeyword.category == category)
    if is_enabled is not None:
        stmt = stmt.where(ForeignKeyword.is_enabled.is_(is_enabled))
    if type_ and "type" in columns:
        stmt = stmt.where(ForeignKeyword.type == type_)
    if source and "source" in columns:
        stmt = stmt.where(ForeignKeyword.source == source)
    count_stmt = select(__import__("sqlalchemy").func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        stmt.order_by(ForeignKeyword.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    return [serialize_foreign_keyword(row, columns) for row in rows], int(total), columns


def get_foreign_keyword_row(db: Session, keyword_id: int):
    stmt, columns = _keyword_select(db)
    row = db.execute(stmt.where(ForeignKeyword.id == keyword_id)).first()
    return (serialize_foreign_keyword(row, columns), columns) if row else (None, columns)


def create_foreign_keyword_row(
    db: Session,
    *,
    word: str,
    category: str,
    is_enabled: bool,
    type_: str = "monitoring",
    source: str = "custom",
    weight: int = 10,
    severity_weight: int = 0,
    rule_config: dict | None = None,
):
    columns = foreign_keyword_columns(db)
    values = {
        "word": word,
        "category": category,
        "is_enabled": is_enabled,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    if "type" in columns:
        values.update(
            {
                "type": type_,
                "source": source,
                "weight": weight,
                "severity_weight": severity_weight,
                "rule_config": rule_config or {},
            }
        )
    result = db.execute(insert(ForeignKeyword).values(**values))
    keyword_id = result.inserted_primary_key[0]
    db.flush()
    return get_foreign_keyword_row(db, int(keyword_id))[0]


def update_foreign_keyword_row(db: Session, keyword_id: int, values: dict):
    columns = foreign_keyword_columns(db)
    allowed = {"word", "category", "is_enabled"}
    allowed |= MANAGEMENT_COLUMNS & columns
    payload = {key: value for key, value in values.items() if key in allowed}
    payload["updated_at"] = datetime.now(timezone.utc)
    if not payload:
        return get_foreign_keyword_row(db, keyword_id)[0]
    db.execute(
        update(ForeignKeyword)
        .where(ForeignKeyword.id == keyword_id)
        .values(**payload)
    )
    db.flush()
    return get_foreign_keyword_row(db, keyword_id)[0]


def delete_foreign_keyword_row(db: Session, keyword_id: int) -> bool:
    result = db.execute(delete(ForeignKeyword).where(ForeignKeyword.id == keyword_id))
    return bool(result.rowcount)


def list_foreign_keyword_categories(db: Session) -> list[str]:
    return [
        row[0]
        for row in db.execute(
            select(ForeignKeyword.category)
            .where(ForeignKeyword.category.is_not(None))
            .distinct()
            .order_by(ForeignKeyword.category.asc())
        ).all()
        if row[0]
    ]


def get_foreign_keywords(db: Session) -> list[str]:
    rows = db.scalars(
        select(ForeignKeyword.word)
        .where(ForeignKeyword.is_enabled.is_(True))
        .order_by(ForeignKeyword.id)
    ).all()
    return [word.strip() for word in rows if word and word.strip()]
