"""Regression tests for Phase MediaCrawler Enable-2B Fix-3 isolation."""
from __future__ import annotations

from pathlib import Path

from app.collectors import data_source_repository, registry
from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_runtime import (
    MediaCrawlerRuntimeError,
    MediaCrawlerRuntimeFactory,
)
from app.collectors.service import CollectorRunResult, CollectorService


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def _row() -> dict[str, object]:
    return {
        "key": "weibo_mediacrawler",
        "name": "MediaCrawler Weibo",
        "class_path": (
            "app.collectors.media_crawler_weibo_collector."
            "MediaCrawlerWeiboCollector"
        ),
        "scope_region_codes": None,
        "config_json": {
            "collector": "mediacrawler",
            "platform": "weibo",
            "keywords": ["test"],
            "max_items": 10,
            "collection_scope": "national",
        },
    }


def test_scheduler_registry_resolve_has_runtime_factory(monkeypatch) -> None:
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [_row()])

    resolved = registry.resolve_collectors_verbose(
        object(),
        include_data_source_keys={"weibo_mediacrawler"},
    )

    assert len(resolved.collectors) == 1
    collector = resolved.collectors[0]
    assert isinstance(collector, MediaCrawlerWeiboCollector)
    assert isinstance(collector.runtime_factory, MediaCrawlerRuntimeFactory)
    assert collector.runner is None


def test_service_does_not_create_production_collectors_at_init() -> None:
    service = CollectorService(
        collector_type="government",
        include_data_source_keys={"weibo_mediacrawler"},
    )

    assert service._collectors_injected is False
    assert service.collectors == []


def test_scheduled_execution_resolves_factory_without_subprocess(monkeypatch) -> None:
    factory = MediaCrawlerRuntimeFactory(source_key="weibo_mediacrawler")
    collector = MediaCrawlerWeiboCollector(
        runtime_factory=factory,
        max_items=1,
    )

    class _Resolved:
        collectors = [collector]
        failures: list[dict] = []

    monkeypatch.setattr(
        "app.collectors.service.resolve_collectors_verbose",
        lambda *_args, **_kwargs: _Resolved(),
    )
    monkeypatch.setattr(
        "app.collectors.service.get_monitoring_keywords",
        lambda _db: [],
    )
    monkeypatch.setattr(
        "app.collectors.service.get_monitoring_keywords_grouped",
        lambda _db: {},
    )
    monkeypatch.setattr(
        "app.collectors.mediacrawler_runner.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("subprocess must not run in Fix-3 regression")
        ),
    )

    def _process(*_args, **_kwargs):
        assert collector.runtime_factory is factory
        assert collector.runner is None
        return CollectorRunResult(collector_type="government")

    monkeypatch.setattr(CollectorService, "_process_collector", _process)
    service = CollectorService(
        collector_type="government",
        include_data_source_keys={"weibo_mediacrawler"},
    )

    result = service.collect_and_analyze(object(), trigger_type="scheduled")

    assert result.failed == 0
    assert service.collectors == [collector]


def test_bare_mediacrawler_collector_fails_closed() -> None:
    import pytest

    with pytest.raises(MediaCrawlerRuntimeError, match="runtime factory missing"):
        MediaCrawlerWeiboCollector()


def test_fixture_collector_injection_remains_available() -> None:
    collector = MediaCrawlerWeiboCollector(fixture_path=FIXTURE)
    service = CollectorService(collectors=[collector])

    assert service._collectors_injected is True
    assert service.collectors == [collector]
