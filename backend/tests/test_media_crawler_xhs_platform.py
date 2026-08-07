"""Offline Platform-2-B1 contract tests for the XHS skeleton."""
from __future__ import annotations

import inspect
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.collectors.media_crawler_platform_collector import (
    MediaCrawlerPlatformCollector,
)
from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_normalizers import get_mediacrawler_normalizer
from app.collectors.mediacrawler_platform import (
    MEDIACRAWLER_CAPABILITY,
    XHS_PLATFORM_SPEC,
    MediaCrawlerConfigurationError,
    get_mediacrawler_platform_spec,
    registered_mediacrawler_platforms,
)
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRealRunDisabledError,
    MediaCrawlerRunner,
)
from app.collectors import data_source_repository, registry
from app.collectors.registry import import_class
from app.collectors.source_config import validate_data_source_config


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "xiaohongshu.jsonl"
WEIBO_FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"
WEIBO_CLASS_PATH = (
    "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector"
)


def test_xhs_spec_is_registered_with_verified_offline_contract() -> None:
    spec = get_mediacrawler_platform_spec("xiaohongshu")

    assert spec is XHS_PLATFORM_SPEC
    assert "xiaohongshu" in registered_mediacrawler_platforms()
    assert spec.platform == "xiaohongshu"
    assert spec.source == "xiaohongshu"
    assert spec.source_type == "xhs_note"
    assert spec.cli_code == "xhs"
    assert spec.crawler_type == "search"
    assert spec.supported_crawler_types == ("search", "detail", "creator")
    assert spec.default_crawler_type == "search"
    assert spec.native_output_parts == ("xhs", "jsonl")
    assert spec.supported_login_types == frozenset({"qrcode", "phone", "cookie"})
    assert spec.allow_real_collection is True


def test_unknown_platform_remains_rejected() -> None:
    with pytest.raises(MediaCrawlerConfigurationError, match="unknown MediaCrawler platform"):
        get_mediacrawler_platform_spec("xhs")


def test_xhs_platform_is_allowed_by_config_contract_without_real_settings() -> None:
    config = validate_data_source_config(
        {
            "collector": "mediacrawler",
            "platform": "xiaohongshu",
            "keywords": ["测试"],
        }
    )

    assert config["platform"] == "xiaohongshu"


def test_xhs_normalizer_fixture_maps_unified_fields() -> None:
    row = json.loads(FIXTURE.read_text(encoding="utf-8").strip())
    item = get_mediacrawler_normalizer(XHS_PLATFORM_SPEC).normalize(row)

    assert item == {
        "title": "城市生活记录",
        "content": "城市生活记录。现场情况正在持续关注。",
        "source": "xiaohongshu",
        "source_type": "xhs_note",
        "url": "https://www.xiaohongshu.com/explore/xhs-test-1001",
        "publish_time": datetime(2024, 8, 1),
        "external_id": "xhs-test-1001",
        "author": "小红书测试用户",
        "engagement": {
            "likes": 12000,
            "comments": 8,
            "reposts": 4,
            "collections": 3000,
        },
    }


def test_xhs_normalizer_returns_none_for_empty_content_and_none_for_missing_optional_fields() -> None:
    normalizer = get_mediacrawler_normalizer("xiaohongshu")

    assert normalizer.normalize({"note_id": "empty"}) is None
    item = normalizer.normalize({"desc": "只有正文"})

    assert item is not None
    assert item["external_id"] is None
    assert item["author"] is None
    assert item["url"] is None
    assert item["publish_time"] is None
    assert item["engagement"] == {
        "likes": 0,
        "comments": 0,
        "reposts": 0,
        "collections": 0,
    }


def test_weibo_fixture_and_class_path_remain_unchanged() -> None:
    cls = import_class(WEIBO_CLASS_PATH)
    assert cls is MediaCrawlerWeiboCollector
    assert cls.platform_spec.platform == "weibo"
    assert cls.data_source_key == "weibo_mediacrawler"
    assert cls.__module__ == "app.collectors.media_crawler_weibo_collector"

    items = MediaCrawlerWeiboCollector(fixture_path=WEIBO_FIXTURE).fetch(
        keywords=["廊坊"]
    )
    assert len(items) == 3
    assert items[0]["source"] == "weibo"
    assert items[0]["source_type"] == "weibo_post"
    assert items[0]["external_id"] == "mc-1001"
    assert items[0]["engagement"] == {"likes": 12000, "comments": 3, "reposts": 5}


def test_registry_builds_generic_xhs_collector_without_real_run(monkeypatch) -> None:
    row = {
        "key": "xhs_mediacrawler_test",
        "name": "XHS skeleton",
        "class_path": (
            "app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector"
        ),
        "scope_region_codes": "",
        "config_json": {
            "collector": "mediacrawler",
            "platform": "xiaohongshu",
            "keywords": ["测试"],
        },
    }
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [row])

    result = registry.resolve_collectors_verbose(object())

    assert result.failures == []
    assert len(result.collectors) == 1
    collector = result.collectors[0]
    assert isinstance(collector, MediaCrawlerPlatformCollector)
    assert not isinstance(collector, MediaCrawlerWeiboCollector)
    assert collector.platform_spec is XHS_PLATFORM_SPEC
    assert collector.data_source_key == "xhs_mediacrawler_test"


def test_generic_collector_has_no_xhs_specific_branch() -> None:
    source = inspect.getsource(MediaCrawlerPlatformCollector).lower()

    assert "xiaohongshu" not in source
    assert "xhs" not in source
    assert MediaCrawlerPlatformCollector.platform_spec is None
    assert MEDIACRAWLER_CAPABILITY == "mediacrawler"


def test_real_run_gate_stays_closed_for_xhs(tmp_path: Path) -> None:
    marker = tmp_path / "started.txt"
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).write_text('started')",
        ],
        platform_spec=XHS_PLATFORM_SPEC,
        source_key="xhs_test",
        mock_command=False,
        enable_real_run=False,
    )

    with pytest.raises(MediaCrawlerRealRunDisabledError):
        runner.run(["测试"], timeout_seconds=5)

    assert not marker.exists()
