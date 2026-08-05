"""Acceptance tests for the MediaCrawler-2A design correction."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.collectors.media_crawler_weibo_collector import (
    MediaCrawlerWeiboCollector,
    parse_publish_time,
)
from app.collectors.mediacrawler_runner import MediaCrawlerRunner
from app.collectors.source_config import DataSourceConfig, validate_data_source_config
from app.services.opinion_region_service import OpinionRegionService


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def test_collection_scope_contract_and_legacy_compatibility() -> None:
    regional = {
        "collector": "mediacrawler",
        "platform": "weibo",
        "keywords": ["topic"],
        "max_items": 10,
        "collection_scope": "regional",
    }
    assert validate_data_source_config(regional) == regional
    assert DataSourceConfig(regional).collection_mode() == "regional"
    assert DataSourceConfig({"collection_mode": "national"}).collection_scope() == "national"
    with pytest.raises(ValueError, match="collection_mode"):
        validate_data_source_config({"collection_mode": "manual"})


@pytest.mark.parametrize("value", [0, 21, True, "10"])
def test_max_items_is_strictly_bounded(value: object) -> None:
    with pytest.raises(ValueError, match="max_items"):
        validate_data_source_config({"max_items": value})


def test_collector_uses_source_config_max_items_before_constructor(tmp_path: Path) -> None:
    collector = MediaCrawlerWeiboCollector(
        fixture_path=FIXTURE,
        max_items=20,
    )
    collector.source_config = DataSourceConfig({"max_items": 1})

    items = collector.fetch([])

    assert collector.effective_max_items == 1
    assert len(items) <= 1


def test_runner_exposes_effective_max_items_and_preserves_raw(tmp_path: Path) -> None:
    result = MediaCrawlerRunner(root=tmp_path, fixture_path=FIXTURE).run(
        [], max_items=1, timeout_seconds=10
    )

    assert result.effective_max_items == 1
    assert result.raw_count is not None and result.raw_count > result.output_count
    assert result.raw_output_path is not None and result.raw_output_path.is_file()


def test_publish_time_is_normalized_to_utc_naive() -> None:
    assert parse_publish_time("2026-08-04T12:00:00+08:00") == datetime(2026, 8, 4, 4)
    assert parse_publish_time("2026-08-04 12:00:00") == datetime(2026, 8, 4, 4)


class _RegionQuery:
    def __init__(self, region: object) -> None:
        self.region = region

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.region


class _Db:
    def __init__(self, region: object) -> None:
        self.region = region

    def query(self, *_args, **_kwargs):
        return _RegionQuery(self.region)


def test_explicit_national_scope_always_uses_sentinel_region() -> None:
    sentinel = SimpleNamespace(id=99, code="000000")
    db = _Db(sentinel)
    decision = OpinionRegionService().decide(
        db,
        {"title": "A local topic", "content": "Langfang"},
        scope_region_codes=None,
        collection_mode="national",
    )

    assert decision.region_id == 99
    assert decision.decision == "accepted_national_sentinel"
