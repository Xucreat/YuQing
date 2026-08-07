"""Set the formal Weibo and Xiaohongshu sources to national scope.

This is an idempotent data migration for deployments where those rows were
created with an earlier regional default.  Empty ``scope_region_codes`` is the
existing application representation of national coverage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.db.session import SessionLocal
from app.models.data_source import DataSource


SOURCE_KEYS = ("weibo_mediacrawler", "xhs_mediacrawler")


def migrate() -> int:
    changed = 0
    with SessionLocal() as db:
        rows = (
            db.query(DataSource)
            .filter(DataSource.key.in_(SOURCE_KEYS))
            .order_by(DataSource.key)
            .all()
        )
        for row in rows:
            config = json.loads(row.config_json or "{}")
            if not isinstance(config, dict):
                raise ValueError(f"{row.key} config_json must be a JSON object")
            config["collection_scope"] = "national"
            config["collection_mode"] = "national"
            next_config = json.dumps(config, ensure_ascii=False)
            if row.scope_region_codes is not None or row.config_json != next_config:
                row.scope_region_codes = None
                row.config_json = next_config
                changed += 1
        db.commit()
    print(f"updated={changed} found={len(rows)}")
    return changed


if __name__ == "__main__":
    migrate()
