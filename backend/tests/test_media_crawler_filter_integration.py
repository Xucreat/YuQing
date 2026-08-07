"""Shared MediaCrawler keyword-scope, cursor, and admission tests."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.collectors.media_crawler_platform_collector import (
    MediaCrawlerPlatformCollector,
)
from app.collectors.mediacrawler_platform import XHS_PLATFORM_SPEC, WEIBO_PLATFORM_SPEC
from app.collectors.mediacrawler_runner import MediaCrawlerRunner
from app.collectors.service import CollectorService
from app.collectors.source_config import DataSourceConfig


class _Query:
    def __init__(self, row) -> None:
        self.row = row

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.row


class _Db:
    def __init__(self, row) -> None:
        self.row = row

    def query(self, _model):
        return _Query(self.row)


@pytest.mark.parametrize("platform_spec", [WEIBO_PLATFORM_SPEC, XHS_PLATFORM_SPEC])
@pytest.mark.parametrize(
    ("scope", "expected_pool"),
    [
        ("region", ["region-a", "region-b"]),
        ("region_only", ["region-a", "region-b"]),
        ("topic", ["topic-a", "topic-b"]),
        ("topic_only", ["topic-a", "topic-b"]),
        (
            "region_topic",
            ["region-a", "region-b", "topic-a", "topic-b"],
        ),
    ],
)
def test_keyword_scope_cursor_pool_is_shared_by_weibo_and_xhs(
    tmp_path: Path,
    platform_spec,
    scope: str,
    expected_pool: list[str],
) -> None:
    fixture = tmp_path / f"{platform_spec.platform}.jsonl"
    row = (
        {"mid": "scope-1", "content": "scope test"}
        if platform_spec.platform == "weibo"
        else {"note_id": "scope-1", "desc": "scope test"}
    )
    fixture.write_text(json.dumps(row) + "\n", encoding="utf-8")

    source_key = f"{platform_spec.platform}_scope_test"
    collector = MediaCrawlerPlatformCollector(
        platform_spec=platform_spec,
        data_source_key=source_key,
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=fixture,
            platform_spec=platform_spec,
            source_key=source_key,
        ),
    )
    collector.source_config = DataSourceConfig(
        {"keyword_scope": scope},
        source_key=source_key,
    )
    source = SimpleNamespace(keyword_cursor=0)
    db = _Db(source)
    service = CollectorService(collectors=[collector])
    monitoring = ["region-a", "region-b", "topic-a", "topic-b"]
    region_kw = ["region-a", "region-b"]
    topic_kw = ["topic-a", "topic-b"]

    selected_keywords: list[str] = []
    for _ in expected_pool:
        selected, next_cursor = service._mediacrawler_keyword_turn(
            db,
            collector,
            monitoring,
            region_kw,
            topic_kw,
        )
        assert len(selected) == 1
        selected_keywords.extend(selected)
        source.keyword_cursor = next_cursor

    assert selected_keywords == expected_pool


@pytest.mark.parametrize("platform_spec", [WEIBO_PLATFORM_SPEC, XHS_PLATFORM_SPEC])
def test_selected_round_robin_keyword_is_the_only_search_keyword(
    tmp_path: Path,
    platform_spec,
) -> None:
    fixture = tmp_path / f"{platform_spec.platform}.jsonl"
    row = (
        {"mid": "selected-1", "content": "selected keyword test"}
        if platform_spec.platform == "weibo"
        else {"note_id": "selected-1", "desc": "selected keyword test"}
    )
    fixture.write_text(json.dumps(row) + "\n", encoding="utf-8")

    source_key = f"{platform_spec.platform}_selected_test"
    collector = MediaCrawlerPlatformCollector(
        platform_spec=platform_spec,
        data_source_key=source_key,
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=fixture,
            platform_spec=platform_spec,
            source_key=source_key,
        ),
    )
    collector.source_config = DataSourceConfig(
        {"keyword_scope": "region_topic"},
        source_key=source_key,
    )

    collector.fetch(
        keyword_override=["topic-a"],
        global_keywords=["region-a", "topic-a"],
        region_kw=["region-a"],
        topic_kw=["topic-a"],
    )

    config_path = next((tmp_path / "runtime" / "runs").glob("*/config/crawler.json"))
    crawler_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert crawler_config["keywords"] == ["topic-a"]


def test_empty_scoped_pool_does_not_start_runner_or_advance_cursor(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "weibo.jsonl"
    fixture.write_text(
        json.dumps({"mid": "empty-scope", "content": "should not run"}) + "\n",
        encoding="utf-8",
    )
    source_key = "weibo_empty_scope_test"
    collector = MediaCrawlerPlatformCollector(
        platform_spec=WEIBO_PLATFORM_SPEC,
        data_source_key=source_key,
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=fixture,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=source_key,
        ),
    )
    collector.source_config = DataSourceConfig(
        {"keyword_scope": "region_only"},
        source_key=source_key,
    )
    source = SimpleNamespace(keyword_cursor=0)
    selected, next_cursor = CollectorService(
        collectors=[collector]
    )._mediacrawler_keyword_turn(
        _Db(source),
        collector,
        ["topic-a"],
        [],
        ["topic-a"],
    )

    assert selected == []
    assert next_cursor is None
    assert source.keyword_cursor == 0
    assert collector.fetch(keyword_override=selected) == []
    assert not (tmp_path / "runtime" / "runs").exists()


def test_empty_config_keeps_all_keyword_cursor_and_legacy_admission(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "weibo.jsonl"
    fixture.write_text(
        json.dumps({"mid": "legacy-1", "content": "content without configured region"}) + "\n",
        encoding="utf-8",
    )
    source_key = "weibo_empty_config_test"
    collector = MediaCrawlerPlatformCollector(
        platform_spec=WEIBO_PLATFORM_SPEC,
        data_source_key=source_key,
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=fixture,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=source_key,
        ),
    )
    collector.source_config = DataSourceConfig({}, source_key=source_key)
    source = SimpleNamespace(keyword_cursor=0)
    service = CollectorService(collectors=[collector])

    selected, next_cursor = service._mediacrawler_keyword_turn(
        _Db(source),
        collector,
        ["region-a", "topic-a"],
        ["region-a"],
        ["topic-a"],
    )

    assert selected == ["region-a"]
    assert next_cursor == 1
    source.keyword_cursor = next_cursor
    items = collector.fetch(
        keyword_override=selected,
        region_kw=["region-a"],
        topic_kw=["topic-a"],
    )

    assert [item["external_id"] for item in items] == ["legacy-1"]
    assert collector.last_filter_skipped == 0


def test_max_items_applies_to_one_selected_keyword(tmp_path: Path) -> None:
    fixture = tmp_path / "weibo.jsonl"
    rows = [
        {"mid": f"max-{index}", "content": f"item {index}"}
        for index in range(25)
    ]
    fixture.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    source_key = "weibo_max_items_test"
    collector = MediaCrawlerPlatformCollector(
        platform_spec=WEIBO_PLATFORM_SPEC,
        data_source_key=source_key,
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=fixture,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=source_key,
        ),
    )
    collector.source_config = DataSourceConfig(
        {"keyword_scope": "region_only", "max_items": 20},
        source_key=source_key,
    )

    items = collector.fetch(
        keyword_override=["region-a"],
        region_kw=["region-a"],
        topic_kw=[],
    )

    assert len(items) == 20
    assert collector.last_run_result is not None
    assert collector.last_run_result.output_count == 20
    config_path = next((tmp_path / "runtime" / "runs").glob("*/config/crawler.json"))
    crawler_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert crawler_config["keywords"] == ["region-a"]


@pytest.mark.parametrize("platform_spec", [WEIBO_PLATFORM_SPEC, XHS_PLATFORM_SPEC])
def test_filter_mode_rejects_non_region_and_accepts_region(
    tmp_path: Path,
    platform_spec,
) -> None:
    fixture = tmp_path / f"{platform_spec.platform}.jsonl"
    rows = (
        [
            {
                "mid": "reject",
                "content": "\u5317\u4eac\u4e92\u8054\u7f51\u5927\u5382\u88c1\u5458",
            },
            {
                "mid": "accept",
                "content": "\u5eca\u574a\u5927\u5382\u53bf\u53d1\u751f\u4e8b\u6545",
            },
        ]
        if platform_spec.platform == "weibo"
        else [
            {
                "note_id": "reject",
                "desc": "\u5317\u4eac\u4e92\u8054\u7f51\u5927\u5382\u88c1\u5458",
            },
            {
                "note_id": "accept",
                "desc": "\u5eca\u574a\u5927\u5382\u53bf\u53d1\u751f\u4e8b\u6545",
            },
        ]
    )
    fixture.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    source_key = f"{platform_spec.platform}_filter_test"
    collector = MediaCrawlerPlatformCollector(
        platform_spec=platform_spec,
        data_source_key=source_key,
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=fixture,
            platform_spec=platform_spec,
            source_key=source_key,
        ),
    )
    collector.source_config = DataSourceConfig(
        {"filter_mode": "region_only"},
        source_key=source_key,
    )

    items = collector.fetch(
        keyword_override=["dachang-county"],
        region_kw=["\u5927\u5382\u53bf"],
        topic_kw=[],
    )

    assert [item["external_id"] for item in items] == ["accept"]
    assert collector.last_filter_skipped == 1
    metrics_path = next((tmp_path / "runtime" / "runs").glob("*/metrics.json"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["filter_skipped"] == 1


def test_filter_text_includes_social_metadata(tmp_path: Path) -> None:
    fixture = tmp_path / "weibo.jsonl"
    fixture.write_text(
        json.dumps(
            {
                "mid": "metadata-1",
                "title": "no region in title",
                "content": "no region in body",
                "hashtags": ["Langfang"],
                "tags": ["Dachang County"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    source_key = "weibo_filter_text_test"
    collector = MediaCrawlerPlatformCollector(
        platform_spec=WEIBO_PLATFORM_SPEC,
        data_source_key=source_key,
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=fixture,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=source_key,
        ),
    )
    collector.source_config = DataSourceConfig(
        {"filter_mode": "region_only"},
        source_key=source_key,
    )

    items = collector.fetch(
        keyword_override=["Langfang"],
        region_kw=["Langfang"],
        topic_kw=[],
    )

    assert len(items) == 1
