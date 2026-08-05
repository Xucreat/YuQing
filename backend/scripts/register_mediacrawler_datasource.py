"""Register the MediaCrawler DataSource with an explicit operator action.

Default mode is a redacted dry-run. ``--apply --confirm`` is required before
any row write. This script never changes schema or runs a collector.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.media_crawler_registration import (  # noqa: E402
    MEDIACRAWLER_DATA_SOURCE_KEY,
    build_mediacrawler_data_source_payload,
)


def _apply_registration(*, enabled: bool) -> None:
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.data_source import DataSource

    payload = build_mediacrawler_data_source_payload(
        enabled=enabled,
        schedule_enabled=False,
    )
    db = SessionLocal()
    try:
        existing = db.scalar(
            select(DataSource).where(DataSource.key == MEDIACRAWLER_DATA_SOURCE_KEY)
        )
        if existing is not None:
            raise RuntimeError(
                f"data source already exists: {MEDIACRAWLER_DATA_SOURCE_KEY}; no update performed"
            )
        db.add(DataSource(**payload))
        db.commit()
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="MediaCrawler DataSource registration")
    parser.add_argument("--apply", action="store_true", help="write the DataSource row")
    parser.add_argument("--confirm", action="store_true", help="confirm the explicit row write")
    parser.add_argument(
        "--enable-manual",
        action="store_true",
        help="enable manual execution while keeping schedule_enabled=false",
    )
    args = parser.parse_args()

    payload = build_mediacrawler_data_source_payload()
    if not args.apply:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        print("DRY-RUN: no database changes made")
        return 0
    if not args.confirm:
        print("Refusing to write: pass both --apply and --confirm", file=sys.stderr)
        return 2
    if not args.enable_manual:
        print(
            "Refusing to write: pass --enable-manual for the requested manual-only row",
            file=sys.stderr,
        )
        return 2
    _apply_registration(enabled=True)
    print(f"Registered manual-only DataSource: {MEDIACRAWLER_DATA_SOURCE_KEY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
