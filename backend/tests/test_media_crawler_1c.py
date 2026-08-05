"""Offline tests for the Phase MediaCrawler-1C controlled real-run boundary."""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_runner import MediaCrawlerRunner
from app.collectors.service import CollectorService
from scripts.run_mediacrawler_real_verify import (
    compute_field_coverage,
    compute_jsonl_metrics,
    validate_real_verify_options,
)


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def test_missing_confirm_is_rejected() -> None:
    with pytest.raises(ValueError, match="confirm-real-run"):
        validate_real_verify_options(
            confirm_real_run=False,
            max_items=10,
            timeout_seconds=60,
            enable_real_run=True,
        )


def test_max_items_and_timeout_are_bounded() -> None:
    with pytest.raises(ValueError, match="max_items"):
        validate_real_verify_options(
            confirm_real_run=True,
            max_items=21,
            timeout_seconds=60,
            enable_real_run=True,
        )
    with pytest.raises(ValueError, match="timeout_seconds"):
        validate_real_verify_options(
            confirm_real_run=True,
            max_items=10,
            timeout_seconds=601,
            enable_real_run=True,
        )


def test_explicit_real_command_success_is_parsed_as_standard_payload(tmp_path: Path) -> None:
    script = (
        "import os; "
        "open(os.environ['MEDIA_CRAWLER_OUTPUT'], 'w', encoding='utf-8').write("
        "'{\"mid\":\"real-test-1\",\"content\":\"受控本地命令样本\",\"nickname\":\"tester\"}\\n')"
    )
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[sys.executable, "-c", script],
        mock_command=False,
        enable_real_run=True,
    )
    collector = MediaCrawlerWeiboCollector(runner=runner, max_items=20)

    items = collector.fetch(keywords=["测试"])

    assert len(items) == 1
    assert items[0]["source"] == "weibo"
    assert items[0]["source_type"] == "weibo_post"
    assert items[0]["external_id"] == "real-test-1"
    assert items[0]["engagement"] == {"likes": 0, "comments": 0, "reposts": 0}


def test_jsonl_metrics_and_field_coverage(tmp_path: Path) -> None:
    path = tmp_path / "sample.jsonl"
    path.write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    metrics = compute_jsonl_metrics(path)
    assert metrics == {
        "raw_count": 5,
        "valid_count": 4,
        "invalid_count": 1,
        "duplicate_count": 1,
        "output_count": 3,
    }
    collector = MediaCrawlerWeiboCollector(
        runner=MediaCrawlerRunner(root=tmp_path / "runtime", fixture_path=FIXTURE)
    )
    items = collector.fetch([])
    coverage = compute_field_coverage(items)
    assert coverage["content"] == 100.0
    assert coverage["external_id"] == 100.0
    assert coverage["engagement"] == 100.0


def test_collector_service_contract_accepts_mediacrawler_collector() -> None:
    collector = MediaCrawlerWeiboCollector(fixture_path=FIXTURE)
    service = CollectorService(collectors=[collector])

    assert service.collectors == [collector]
    signature = inspect.signature(collector.fetch)
    assert "keywords" in signature.parameters
    assert "region_kw" in signature.parameters
    assert "topic_kw" in signature.parameters
    assert inspect.isclass(type(service))


def test_real_run_setting_is_required_before_execution() -> None:
    with pytest.raises(ValueError, match="MEDIA_CRAWLER_ENABLE_REAL_RUN"):
        validate_real_verify_options(
            confirm_real_run=True,
            max_items=10,
            timeout_seconds=60,
            enable_real_run=False,
        )
