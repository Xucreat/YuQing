"""Offline XHS normalizer and generic collector pipeline contracts."""
from __future__ import annotations

import json
from pathlib import Path

from app.collectors.media_crawler_platform_collector import (
    MediaCrawlerPlatformCollector,
)
from app.collectors.mediacrawler_normalizers import get_mediacrawler_normalizer
from app.collectors.mediacrawler_platform import XHS_PLATFORM_SPEC


def test_xhs_normalizer_missing_fields_and_invalid_engagement() -> None:
    item = get_mediacrawler_normalizer(XHS_PLATFORM_SPEC).normalize(
        {
            "note_id": "xhs-missing-author",
            "desc": "正文存在，但作者和时间缺失",
            "liked_count": "not-a-number",
            "comment_count": None,
            "share_count": "-",
            "collected_count": "unknown",
        }
    )

    assert item is not None
    assert item["external_id"] == "xhs-missing-author"
    assert item["content"] == "正文存在，但作者和时间缺失"
    assert item["author"] is None
    assert item["url"] is None
    assert item["publish_time"] is None
    assert item["engagement"] == {
        "likes": 0,
        "comments": 0,
        "reposts": 0,
        "collections": 0,
    }


def test_xhs_normalizer_removes_session_query_credentials() -> None:
    item = get_mediacrawler_normalizer(XHS_PLATFORM_SPEC).normalize(
        {
            "note_id": "xhs-public-url",
            "desc": "正文",
            "note_url": (
                "https://www.xiaohongshu.com/explore/xhs-public-url"
                "?xsec_token=secret&xsec_source=pc_search&foo=bar"
            ),
        }
    )

    assert item is not None
    assert item["url"] == (
        "https://www.xiaohongshu.com/explore/xhs-public-url?foo=bar"
    )


def test_xhs_collector_fixture_normalizes_deduplicates_and_records_metrics(
    tmp_path: Path,
) -> None:
    row = {
        "note_id": "xhs-duplicate",
        "desc": "同一篇笔记",
        "nickname": "测试用户",
        "note_url": "https://example.invalid/xhs-duplicate",
        "time": 1722470400000,
        "liked_count": "2",
        "comment_count": "1",
        "share_count": "0",
        "collected_count": "3",
    }
    fixture = tmp_path / "xhs.jsonl"
    fixture.write_text(
        "\n".join(
            [
                json.dumps(row, ensure_ascii=False),
                json.dumps({**row, "desc": "重复输出"}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    collector = MediaCrawlerPlatformCollector(
        platform_spec=XHS_PLATFORM_SPEC,
        data_source_key="xhs_pipeline_test",
        fixture_path=fixture,
    )
    items = collector.fetch(keywords=["测试"])

    assert len(items) == 1
    assert items[0]["external_id"] == "xhs-duplicate"
    assert collector.last_run_result is not None
    metrics = json.loads(
        collector.last_run_result.metrics_path.read_text(encoding="utf-8")
    )
    assert metrics["raw_count"] == 2
    assert metrics["output_count"] == 2
    log = collector.last_run_result.log_path.read_text(encoding="utf-8")
    assert "duplicate_count=1" in log


def test_xhs_empty_content_is_rejected_by_generic_pipeline() -> None:
    normalizer = get_mediacrawler_normalizer(XHS_PLATFORM_SPEC)

    assert normalizer.normalize({"note_id": "empty", "desc": ""}) is None
    assert normalizer.normalize({"note_id": "missing"}) is None
