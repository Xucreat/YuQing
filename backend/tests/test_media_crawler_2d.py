"""Offline tests for MediaCrawler batch metrics observability."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_runner import (
    MediaCrawlerEmptyOutputError,
    MediaCrawlerProcessError,
    MediaCrawlerRunner,
    MediaCrawlerTimeoutError,
)
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)
from app.collectors.service import _update_media_crawler_metrics


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def _metrics(path: Path) -> dict[str, int | str]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runner_writes_raw_output_and_effective_max_metrics(tmp_path: Path) -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    source = tmp_path / "source.jsonl"
    source.write_text("\n".join((lines * 4)[:16]) + "\n", encoding="utf-8")

    result = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        fixture_path=source,
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    ).run(
        [], max_items=10, timeout_seconds=10
    )

    assert result.raw_count == 16
    assert result.output_count == 10
    assert result.effective_max_items == 10
    assert result.metrics_path is not None
    metrics = _metrics(result.metrics_path)
    assert metrics["batch_id"] == result.batch_id
    assert metrics["collector"] == "mediacrawler"
    assert metrics["raw_count"] == 16
    assert metrics["output_count"] == 10
    assert metrics["effective_max_items"] == 10


def test_collector_service_counters_update_same_batch_metrics(tmp_path: Path) -> None:
    collector = MediaCrawlerWeiboCollector(
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=FIXTURE,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=WEIBO_SOURCE_KEY,
        )
    )
    collector.fetch(keywords=["test"])

    _update_media_crawler_metrics(
        collector,
        created=6,
        duplicate=0,
        admission_filtered=4,
        failed=0,
    )

    assert collector.last_run_result is not None
    metrics = _metrics(collector.last_run_result.metrics_path)  # type: ignore[arg-type]
    assert metrics["batch_id"] == collector.last_run_result.batch_id
    assert metrics["created"] == 6
    assert metrics["duplicate"] == 0
    assert metrics["admission_filtered"] == 4
    assert metrics["failed"] == 0


def test_duplicate_counter_is_preserved_in_metrics(tmp_path: Path) -> None:
    collector = MediaCrawlerWeiboCollector(
        runner=MediaCrawlerRunner(
            root=tmp_path / "runtime",
            fixture_path=FIXTURE,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=WEIBO_SOURCE_KEY,
        )
    )
    collector.fetch(keywords=["test"])
    _update_media_crawler_metrics(collector, created=5, duplicate=2, admission_filtered=1, failed=0)

    assert collector.last_run_result is not None
    metrics = _metrics(collector.last_run_result.metrics_path)  # type: ignore[arg-type]
    assert metrics["duplicate"] == 2


def test_login_process_failure_writes_failed_metrics(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[sys.executable, "-c", "import sys; sys.exit(1)"],
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    )

    with pytest.raises(MediaCrawlerProcessError):
        runner.run([], max_items=10, timeout_seconds=5)

    assert runner.last_metrics_path is not None
    metrics = _metrics(runner.last_metrics_path)
    assert metrics["batch_id"] == runner.last_batch_id
    assert metrics["failed"] == 1


def test_timeout_writes_failed_metrics(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[sys.executable, "-c", "import time; time.sleep(1)"],
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    )

    with pytest.raises(MediaCrawlerTimeoutError):
        runner.run([], max_items=10, timeout_seconds=0.05)

    assert runner.last_metrics_path is not None
    assert _metrics(runner.last_metrics_path)["failed"] == 1


def test_raw_records_without_bounded_output_fail_and_are_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
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

    assert runner.last_metrics_path is not None
    metrics = _metrics(runner.last_metrics_path)
    assert metrics["raw_count"] == 16
    assert metrics["output_count"] == 0
    assert metrics["failed"] == 1
