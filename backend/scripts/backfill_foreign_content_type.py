"""Backfill foreign opinion content types in small, repeatable batches."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import func, select  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.foreign_opinion import ForeignOpinion  # noqa: E402
from app.services.foreign_content_type_service import (  # noqa: E402
    classify_foreign_content_type,
)


def backfill(
    *,
    batch_size: int = 500,
    dry_run: bool = False,
    reclassify_version: str | None = None,
) -> dict:
    """Classify rows without changing any risk-analysis fields.

    The default filter is deliberately limited to ``content_type IS NULL``.
    Passing ``reclassify_version`` opts into reclassifying an existing version.
    """
    batch_size = max(1, int(batch_size))
    db = SessionLocal()
    distribution: Counter[str] = Counter()
    failed_ids: list[int] = []
    counts: dict = {
        "total_records": 0,
        "pending_count": 0,
        "scanned": 0,
        "updated": 0,
        "distribution": distribution,
        "failed_ids": failed_ids,
        "dry_run": dry_run,
        "batch_size": batch_size,
        "reclassify_version": reclassify_version,
    }
    try:
        counts["total_records"] = (
            db.scalar(select(func.count()).select_from(ForeignOpinion)) or 0
        )
        row_filter = (
            ForeignOpinion.content_type_version == reclassify_version
            if reclassify_version
            else ForeignOpinion.content_type.is_(None)
        )
        counts["pending_count"] = (
            db.scalar(
                select(func.count())
                .select_from(ForeignOpinion)
                .where(row_filter)
            )
            or 0
        )

        last_id = 0
        while True:
            rows = db.scalars(
                select(ForeignOpinion)
                .where(ForeignOpinion.id > last_id, row_filter)
                .order_by(ForeignOpinion.id.asc())
                .limit(batch_size)
            ).all()
            if not rows:
                break

            batch_ids: list[int] = []
            batch_updated = 0
            for row in rows:
                last_id = row.id
                batch_ids.append(row.id)
                counts["scanned"] += 1
                try:
                    decision = classify_foreign_content_type(
                        title=row.title,
                        summary=row.summary,
                        content=row.content,
                    )
                    distribution[decision.content_type] += 1
                    if not dry_run:
                        row.content_type = decision.content_type
                        row.content_type_version = decision.version
                    counts["updated"] += 1
                    batch_updated += 1
                except Exception:
                    failed_ids.append(row.id)

            if dry_run:
                db.rollback()
            else:
                try:
                    db.commit()
                except Exception:
                    db.rollback()
                    failed_ids.extend(batch_ids)
                    counts["updated"] -= batch_updated
        return counts
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Backfill foreign_opinions.content_type in batches"
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--version",
        "--reclassify-version",
        dest="reclassify_version",
        help="Reclassify only rows with this existing content_type_version",
    )
    args = parser.parse_args()
    result = backfill(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        reclassify_version=args.reclassify_version,
    )
    result["distribution"] = dict(result["distribution"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
