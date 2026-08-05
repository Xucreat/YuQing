"""Offline acceptance tests for the MediaCrawler Phase 1A boundary."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.collectors.media_crawler_weibo_collector import (
    MediaCrawlerWeiboCollector,
    normalize_keywords,
    parse_engagement_count,
)
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRunner,
    MediaCrawlerRunnerError,
    MediaCrawlerTimeoutError,
)
from app.collectors.registry import import_class
from app.core.config import settings


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def test_normalize_keywords_preserves_order_and_deduplicates() -> None:
    assert normalize_keywords([" 廊坊 ", "", "廊坊", "消防", None]) == ["廊坊", "消防"]


def test_engagement_count_supports_chinese_units_and_invalid_values() -> None:
    assert parse_engagement_count("1.2万") == 12000
    assert parse_engagement_count("3,456") == 3456
    assert parse_engagement_count(None) == 0
    assert parse_engagement_count("abc") == 0


def test_fixture_jsonl_is_normalized_and_deduplicated(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(root=tmp_path / "runtime", fixture_path=FIXTURE)
    collector = MediaCrawlerWeiboCollector(runner=runner)

    items = collector.fetch(
        keywords=[" 廊坊 ", "", "廊坊", "消防"],
        region_kw=["廊坊"],
        topic_kw=["消防"],
    )

    assert len(items) == 3
    first = items[0]
    assert first["title"] == "廊坊突发消防事件"
    assert first["content"] == "廊坊突发消防事件。现场正在处置。"
    assert first["source"] == "weibo"
    assert first["source_type"] == "weibo_post"
    assert first["url"] == "https://weibo.com/1001/mc-1001"
    assert first["external_id"] == "mc-1001"
    assert first["author"] == "廊坊观察"
    assert first["engagement"] == {"likes": 12000, "comments": 3, "reposts": 5}
    assert first["publish_time"].year == 2026
    assert items[1]["title"] == "第二条微博正文首句"
    assert items[1]["external_id"] == "mc-1002"
    assert items[2]["engagement"] == {"likes": 0, "comments": 0, "reposts": 0}

    log_files = list((tmp_path / "runtime" / "runs").glob("*/crawler.log"))
    assert len(log_files) == 1
    log = log_files[0].read_text(encoding="utf-8")
    assert "batch_id=" in log
    assert "keywords_count=2" in log
    assert "jsonl_path=" in log
    assert "read_count=5" in log
    assert "success_count=4" in log
    assert "failed_count=1" in log
    assert "duplicate_count=1" in log


def test_runner_mock_command_writes_jsonl(tmp_path: Path) -> None:
    script = (
        "import json, os; "
        "handle=open(os.environ['MEDIA_CRAWLER_OUTPUT'], 'w', encoding='utf-8'); "
        "json.dump({'mid':'mock-1','content':'mock content'}, handle, ensure_ascii=False); "
        "handle.write('\\n'); handle.close()"
    )
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[sys.executable, "-c", script],
    )
    result = runner.run(["廊坊"], output_dir=None, timeout_seconds=5)

    assert result.exit_code == 0
    assert result.output_path.name == "weibo.jsonl"
    assert result.output_path.is_file()
    assert json.loads(result.output_path.read_text(encoding="utf-8"))["mid"] == "mock-1"
    assert "mock_command_finished exit_code=0" in result.log_path.read_text(encoding="utf-8")


def test_runner_timeout_is_reported(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[sys.executable, "-c", "import time; time.sleep(1)"],
    )
    with pytest.raises(MediaCrawlerTimeoutError):
        runner.run([], output_dir=None, timeout_seconds=0.05)

    log_files = list((tmp_path / "runtime" / "runs").glob("*/crawler.log"))
    assert len(log_files) == 1
    assert "timeout=1" in log_files[0].read_text(encoding="utf-8")


def test_no_command_does_not_start_real_mediacrawler(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(root=tmp_path / "runtime")
    with pytest.raises(MediaCrawlerRunnerError, match="no MediaCrawler command"):
        runner.run([], output_dir=None, timeout_seconds=5)


def test_dynamic_import_and_configuration_fields() -> None:
    cls = import_class("app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector")
    assert cls is MediaCrawlerWeiboCollector
    assert cls.source_name == "微博（MediaCrawler）"
    assert cls.data_source_key == "weibo_mediacrawler"
    assert hasattr(settings, "media_crawler_root")
    assert hasattr(settings, "media_crawler_python")
    assert hasattr(settings, "media_crawler_timeout_seconds")
    assert hasattr(settings, "media_crawler_browser_data")
