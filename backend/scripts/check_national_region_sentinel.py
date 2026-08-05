"""Read-only audit for the national Region sentinel.

The current regions schema intentionally has no ``enabled`` column; Region
identity is represented by the unique code. This audit reports that fact
explicitly and never attempts to repair or seed data.
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.constants.region import NATIONAL_REGION_CODE  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.region import Region  # noqa: E402


def audit_sentinel() -> dict[str, object]:
    """Return a read-only audit result without mutating the database."""

    db = SessionLocal()
    try:
        rows = db.execute(
            select(Region.id, Region.code, Region.name).where(
                Region.code == NATIONAL_REGION_CODE
            )
        ).all()
    except SQLAlchemyError as exc:
        return {
            "status": "FAIL",
            "code": NATIONAL_REGION_CODE,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        db.close()

    valid_rows = [
        row
        for row in rows
        if row.id is not None and str(row.code).strip() and str(row.name).strip()
    ]
    result = {
        "status": "PASS" if len(valid_rows) == 1 and len(rows) == 1 else "FAIL",
        "exists": bool(rows),
        "unique": len(rows) == 1,
        "count": len(rows),
        "code": NATIONAL_REGION_CODE,
        "rows": [
            {
                "id": row.id,
                "code": row.code,
                "name": row.name,
                # Deliberately explicit: the existing schema has no enabled.
                "enabled": "NOT_APPLICABLE_SCHEMA_FIELD_ABSENT",
            }
            for row in rows
        ],
        "database": "READ ONLY",
        "writes_performed": False,
        "migration_changed": False,
    }
    return result


def main() -> int:
    result = audit_sentinel()
    print(f"{result['status']} National Region sentinel audit")
    print(f"Database: {result.get('database', 'READ ONLY')}")
    print(f"code={NATIONAL_REGION_CODE} exists={result.get('exists')} unique={result.get('unique')}")
    for row in result.get("rows", []):
        print(
            "id={id} code={code} name={name!r} enabled={enabled}".format(**row)
        )
    if result.get("error"):
        print(f"error={result['error']}")
    print("Writes: NONE")
    print("Migration: UNCHANGED")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
