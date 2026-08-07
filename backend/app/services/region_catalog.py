from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.region import Region


CATALOG_PATH = (
    Path(__file__).resolve().parent.parent / "static" / "regions" / "pcas-code.json"
)
VIRTUAL_NODE_NAMES = {"市辖区", "郊县"}
LEVEL_ORDER = {"province": 1, "city": 2, "county": 3, "street": 4}


@dataclass(frozen=True)
class RegionCatalogItem:
    code: str
    name: str
    level: str
    parent_code: str | None


def _normalize_code(raw_code: str) -> tuple[str, str] | None:
    raw = str(raw_code).strip()
    if len(raw) == 2:
        return raw + "0000", "province"
    if len(raw) == 4:
        return raw + "00", "city"
    if len(raw) == 6:
        return raw, "county"
    if len(raw) == 9:
        return raw, "street"
    return None


def _flatten_nodes(
    nodes: list[dict],
    parent_code: str | None = None,
) -> list[RegionCatalogItem]:
    flattened: list[RegionCatalogItem] = []
    for node in nodes:
        normalized = _normalize_code(node.get("code", ""))
        if normalized is None:
            continue
        code, level = normalized
        children = node.get("children") or []

        # Direct-controlled municipalities have a synthetic city layer. Keep
        # the real county nodes directly under the province in the UI tree.
        if node.get("name") in VIRTUAL_NODE_NAMES:
            flattened.extend(_flatten_nodes(children, parent_code))
            continue

        flattened.append(
            RegionCatalogItem(
                code=code,
                name=str(node.get("name") or code),
                level=level,
                parent_code=parent_code,
            )
        )
        flattened.extend(_flatten_nodes(children, code))
    return flattened


@lru_cache(maxsize=1)
def _load_catalog() -> tuple[RegionCatalogItem, ...]:
    with CATALOG_PATH.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return tuple(_flatten_nodes(raw))


def region_catalog_items(db: Session | None = None) -> list[dict]:
    """Return the complete flattened directory, optionally overlaid by DB rows."""
    by_code = {item.code: asdict(item) for item in _load_catalog()}
    if db is not None:
        for row in db.query(Region).all():
            if row.code == "000000":
                continue
            catalog_item = by_code.get(row.code)
            if catalog_item is None:
                by_code[row.code] = {
                    "code": row.code,
                    "name": row.name,
                    "level": row.level,
                    "parent_code": row.parent_code,
                }
                continue
            # The static catalog is the hierarchy authority. DB rows are
            # sparse operational bindings and may contain stale parent data.
            by_code[row.code] = {
                "code": row.code,
                "name": row.name or catalog_item["name"],
                "level": catalog_item["level"],
                "parent_code": catalog_item["parent_code"],
            }
    return sorted(
        by_code.values(),
        key=lambda item: (
            LEVEL_ORDER.get(item["level"], 5),
            item["parent_code"] or "",
            item["name"],
            item["code"],
        ),
    )


def region_catalog_map(db: Session | None = None) -> dict[str, str]:
    return {item["code"]: item["name"] for item in region_catalog_items(db)}


def sync_region_codes(db: Session, codes: Iterable[str] | None) -> None:
    """Persist selected catalog nodes and their ancestors for collector binding."""
    catalog = {item.code: item for item in _load_catalog()}
    required: set[str] = set()
    for raw_code in codes or []:
        code = str(raw_code or "").strip()
        while code and code in catalog:
            required.add(code)
            code = catalog[code].parent_code or ""

    if not required:
        return

    rows = {
        row.code: row
        for row in db.query(Region).filter(Region.code.in_(required)).all()
    }
    for code in required:
        item = catalog[code]
        row = rows.get(code)
        if row is None:
            db.add(
                Region(
                    code=item.code,
                    name=item.name,
                    level=item.level,
                    parent_code=item.parent_code,
                )
            )
        else:
            # Preserve existing operator-maintained names, but repair missing
            # hierarchy metadata so newly selected descendants remain usable.
            if row.parent_code is None and item.parent_code is not None:
                row.parent_code = item.parent_code
            if not row.level:
                row.level = item.level
