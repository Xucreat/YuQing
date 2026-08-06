"""Safe, explicit registration specification for the MediaCrawler data source.

This module only builds a payload. It does not access a database or enable a
source. Applying the payload is intentionally left to the operator-facing
registration script.
"""
from __future__ import annotations

import json
from typing import Any

from app.collectors.source_config import validate_data_source_config

MEDIACRAWLER_DATA_SOURCE_KEY = "weibo_mediacrawler"
MEDIACRAWLER_CLASS_PATH = (
    "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector"
)
MEDIACRAWLER_CONFIG = {
    "collector": "mediacrawler",
    "platform": "weibo",
    "keywords": [],
    "max_items": 20,
    "collection_scope": "national",
}


def build_mediacrawler_data_source_payload(
    *, enabled: bool = False, schedule_enabled: bool = False
) -> dict[str, Any]:
    """Return the idempotent DataSource payload without performing I/O."""

    return {
        "key": MEDIACRAWLER_DATA_SOURCE_KEY,
        "name": "微博（MediaCrawler）",
        "type": "social",
        "class_path": MEDIACRAWLER_CLASS_PATH,
        "enabled": bool(enabled),
        "priority": 90,
        "schedule_enabled": bool(schedule_enabled),
        "schedule_interval_minutes": 60,
        "next_collect_time": None,
        "scope_region_codes": None,
        "config_json": json.dumps(MEDIACRAWLER_CONFIG, ensure_ascii=False),
    }


def parse_mediacrawler_config(config_json: str | dict[str, Any] | None) -> dict[str, Any]:
    """Validate the small manual-mode config used by the registration payload."""

    if config_json is None:
        return {}
    if isinstance(config_json, str):
        parsed = json.loads(config_json)
    elif isinstance(config_json, dict):
        parsed = dict(config_json)
    else:
        raise ValueError("config_json must be a JSON object")
    if not isinstance(parsed, dict):
        raise ValueError("config_json must be a JSON object")
    validate_data_source_config(parsed)
    return parsed
