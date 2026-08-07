"""Focused regression tests for the MediaCrawler-2B production blockers."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.collectors import data_source_repository, registry
from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_runner import (
    MediaCrawlerEmptyOutputError,
    MediaCrawlerRunner,
)
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)
from app.collectors.source_config import DataSourceConfig


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def test_datasource_keywords_override_runtime_and_global() -> None:
    collector = MediaCrawlerWeiboCollector(fixture_path=FIXTURE)
    collector.source_config = DataSourceConfig({"keywords": ["大厂县"]})

    assert collector.resolve_effective_keywords(["河北"], ["消防"]) == ["大厂县"]
    assert collector.effective_keywords_source == "datasource"


def test_runtime_keywords_override_global_without_datasource_keywords() -> None:
    collector = MediaCrawlerWeiboCollector(fixture_path=FIXTURE)

    assert collector.resolve_effective_keywords(["河北"], ["消防"]) == ["河北"]
    assert collector.effective_keywords_source == "runtime"


def test_global_keywords_are_last_fallback() -> None:
    collector = MediaCrawlerWeiboCollector(fixture_path=FIXTURE)

    assert collector.resolve_effective_keywords(None, ["消防"]) == ["消防"]
    assert collector.effective_keywords_source == "global"


@pytest.mark.parametrize(
    "config",
    [
        {"max_items": 0},
        {"collection_scope": "xxx"},
    ],
)
def test_registry_rejects_invalid_mediacrawler_config(monkeypatch, config) -> None:
    row = {
        "key": "weibo_mediacrawler",
        "name": "微博（MediaCrawler）",
        "class_path": (
            "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector"
        ),
        "scope_region_codes": None,
        "config_json": {"platform": "weibo", **config},
    }
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [row])

    result = registry.resolve_collectors_verbose(object())

    assert result.collectors == []
    assert len(result.failures) == 1
    assert "max_items" in result.failures[0]["error"] or "collection_scope" in result.failures[0]["error"]


def test_runner_preserves_raw_and_bounds_output(tmp_path: Path) -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    source = tmp_path / "source.jsonl"
    source.write_text("\n".join((lines * 4)[:16]) + "\n", encoding="utf-8")

    result = MediaCrawlerRunner(
        root=tmp_path,
        fixture_path=source,
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    ).run(
        [], max_items=10, timeout_seconds=10
    )

    assert result.raw_count == 16
    assert result.output_count == 10


def test_runner_rejects_raw_records_with_empty_output(tmp_path: Path, monkeypatch) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path,
        fixture_path=FIXTURE,
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    )
    monkeypatch.setattr(
        runner,
        "_write_bounded_jsonl",
        lambda _source, _output, _max_items: (16, 0),
    )

    with pytest.raises(MediaCrawlerEmptyOutputError):
        runner.run([], max_items=10, timeout_seconds=10)


def test_runner_allows_no_data_empty_success(tmp_path: Path, monkeypatch) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path,
        fixture_path=FIXTURE,
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    )
    monkeypatch.setattr(
        runner,
        "_write_bounded_jsonl",
        lambda _source, _output, _max_items: (0, 0),
    )

    result = runner.run([], max_items=10, timeout_seconds=10)

    assert result.raw_count == 0
    assert result.output_count == 0
