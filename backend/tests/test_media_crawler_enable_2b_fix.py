"""Regression tests for the MediaCrawler Enable-2B scheduler injection fix."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.collectors import data_source_repository, registry
from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_runner import MediaCrawlerRunner
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeError
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def _row() -> dict[str, object]:
    return {
        "key": "weibo_mediacrawler",
        "name": "MediaCrawler Weibo",
        "class_path": (
            "app.collectors.media_crawler_weibo_collector."
            "MediaCrawlerWeiboCollector"
        ),
        "scope_region_codes": "131000",
        "config_json": {
            "collector": "mediacrawler",
            "platform": "weibo",
            "keywords": ["test"],
            "max_items": 10,
            "collection_scope": "regional",
            "collection_mode": "regional",
        },
    }


class _StubRuntimeFactory:
    """Factory double that records trigger selection without subprocesses."""

    instances: list["_StubRuntimeFactory"] = []

    def __init__(self, *, source_key: str = "weibo_mediacrawler", **_kwargs) -> None:
        self.source_key = source_key
        self.calls: list[str] = []
        self.runner = MediaCrawlerRunner(
            fixture_path=FIXTURE,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=WEIBO_SOURCE_KEY,
        )
        self.instances.append(self)

    def create_runner(self, trigger_type: str):
        self.calls.append(trigger_type)
        return self.runner, None, object()


def test_registry_scheduled_construction_injects_runtime_factory(monkeypatch) -> None:
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [_row()])
    monkeypatch.setattr(registry, "MediaCrawlerRuntimeFactory", _StubRuntimeFactory)
    _StubRuntimeFactory.instances.clear()

    resolved = registry.resolve_collectors_verbose(object())

    assert len(resolved.collectors) == 1
    collector = resolved.collectors[0]
    assert isinstance(collector, MediaCrawlerWeiboCollector)
    assert isinstance(collector.runtime_factory, _StubRuntimeFactory)

    collector.fetch(trigger_type="scheduled")
    assert collector.runtime_factory.calls == ["scheduler"]


def test_missing_runtime_factory_fails_closed() -> None:
    with pytest.raises(MediaCrawlerRuntimeError, match="runtime factory missing"):
        MediaCrawlerWeiboCollector()


def test_manual_and_scheduler_share_the_same_factory_boundary() -> None:
    factory = _StubRuntimeFactory()
    collector = MediaCrawlerWeiboCollector(runtime_factory=factory)

    collector.fetch(trigger_type="manual")
    collector.fetch(trigger_type="scheduled")

    assert factory.calls == ["manual", "scheduler"]
    assert collector.runtime_factory is factory


def test_registry_does_not_mutate_datasource_row(monkeypatch) -> None:
    row = _row()
    before = dict(row)
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [row])
    monkeypatch.setattr(registry, "MediaCrawlerRuntimeFactory", _StubRuntimeFactory)

    registry.resolve_collectors_verbose(object())

    assert row == before
    assert row["key"] == "weibo_mediacrawler"


def test_registry_fix_does_not_start_scheduler(monkeypatch) -> None:
    started = False

    def _start(*_args, **_kwargs):
        nonlocal started
        started = True

    monkeypatch.setattr("app.core.scheduler.start_scheduler", _start)
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [_row()])
    monkeypatch.setattr(registry, "MediaCrawlerRuntimeFactory", _StubRuntimeFactory)

    registry.resolve_collectors_verbose(object())

    assert started is False


def test_registry_fix_never_calls_real_mediacrawler(monkeypatch) -> None:
    calls: list[object] = []

    def _run(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("real MediaCrawler must not be called")

    monkeypatch.setattr(
        "app.collectors.mediacrawler_runner.subprocess.run",
        _run,
    )
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [_row()])
    monkeypatch.setattr(registry, "MediaCrawlerRuntimeFactory", _StubRuntimeFactory)

    resolved = registry.resolve_collectors_verbose(object())
    assert resolved.collectors
    assert calls == []
