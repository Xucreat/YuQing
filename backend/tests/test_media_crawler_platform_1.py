"""Platform-1 contracts for the MediaCrawler abstraction.

All cases are fixture, path, registry, or command tests. No subprocess is
allowed to start a real MediaCrawler process here.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.collectors import data_source_repository, registry
from app.collectors.media_crawler_platform_collector import (
    MediaCrawlerPlatformCollector,
)
from app.collectors.media_crawler_weibo_collector import (
    MediaCrawlerWeiboCollector,
    parse_publish_time,
)
from app.collectors.mediacrawler_batch import MediaCrawlerBatchLocator
from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_platform import (
    MEDIACRAWLER_CAPABILITY,
    MediaCrawlerConfigurationError,
    get_mediacrawler_platform_spec,
)
from app.collectors.mediacrawler_profile import MediaCrawlerProfileManager
from app.collectors.mediacrawler_runner import MediaCrawlerRunner
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_COMPATIBILITY_POLICY,
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)
from app.collectors.source_config import validate_data_source_config


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"


def test_weibo_spec_and_argv_snapshot_remain_compatible(tmp_path: Path) -> None:
    spec = get_mediacrawler_platform_spec("weibo")
    assert spec.cli_code == "wb"
    assert spec.crawler_type == "search"
    assert spec.artifact_name == "weibo"

    command = MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="main.py",
        platform_spec=spec,
    ).build(
        keywords=["廊坊"],
        max_items=1,
        output_dir=tmp_path / "output",
    )

    assert command[command.index("--platform") + 1] == "wb"
    assert command[command.index("--type") + 1] == "search"
    assert command[command.index("--save_data_option") + 1] == "jsonl"


def test_unknown_platform_login_and_top_level_config_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown MediaCrawler platform"):
        get_mediacrawler_platform_spec("xhs")
    with pytest.raises(ValueError, match="invalid MediaCrawler login_type"):
        validate_data_source_config({"platform": "weibo", "login_type": "phone"})
    with pytest.raises(ValueError, match="unsupported top-level keys"):
        validate_data_source_config({"platform": "weibo", "shell_command": "python main.py"})


def test_generic_mediacrawler_layers_require_explicit_platform_spec(
    tmp_path: Path,
) -> None:
    with pytest.raises(MediaCrawlerConfigurationError, match="explicit PlatformSpec"):
        MediaCrawlerPlatformCollector(
            data_source_key="test_mediacrawler",
            fixture_path=FIXTURE,
        )
    with pytest.raises(MediaCrawlerConfigurationError, match="explicit PlatformSpec"):
        MediaCrawlerCommandBuilder(python_executable="python.exe", entry="main.py")
    with pytest.raises(MediaCrawlerConfigurationError, match="explicit PlatformSpec"):
        MediaCrawlerRunner(root=tmp_path, source_key="test_mediacrawler")
    with pytest.raises(MediaCrawlerConfigurationError, match="explicit PlatformSpec"):
        MediaCrawlerBatchLocator(tmp_path)
    with pytest.raises(MediaCrawlerConfigurationError, match="explicit PlatformSpec"):
        MediaCrawlerRuntimeFactory(source_key="test_mediacrawler")


def test_weibo_compatibility_policy_preserves_legacy_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import settings

    entry = tmp_path / "MediaCrawler" / "main.py"
    entry.parent.mkdir(parents=True)
    entry.write_text("# test entry\n", encoding="utf-8")
    monkeypatch.setattr(settings, "media_crawler_root", str(tmp_path / "runtime"))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(tmp_path / "profiles"))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(
        settings,
        "media_crawler_python",
        str(Path(__import__("sys").executable)),
    )

    factory = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    )
    runner, lock, config = factory.create_runner("manual", mock_command=True)

    assert config.profile_path == (tmp_path / "profiles" / "manual").resolve()
    assert config.artifact_scope is None
    assert runner.artifact_name == "weibo"
    assert runner.native_output_parts == ("weibo", "jsonl")
    assert lock.path == (
        tmp_path / "runtime" / "locks" / "weibo_mediacrawler.lock"
    )


def test_weibo_fixture_uses_shared_platform_core_without_output_change(tmp_path: Path) -> None:
    collector = MediaCrawlerWeiboCollector(fixture_path=FIXTURE)
    assert isinstance(collector, MediaCrawlerPlatformCollector)
    assert collector.collector_capability == MEDIACRAWLER_CAPABILITY

    items = collector.fetch(keywords=["廊坊"])

    assert len(items) == 3
    assert items[0]["source"] == "weibo"
    assert items[0]["source_type"] == "weibo_post"
    assert items[0]["external_id"] == "mc-1001"
    assert items[0]["engagement"] == {"likes": 12000, "comments": 3, "reposts": 5}


def test_normalizer_accepts_string_epoch_seconds_and_milliseconds() -> None:
    expected = datetime(2024, 8, 1)
    assert parse_publish_time("2024-08-01 08:00:00") == expected
    assert parse_publish_time(1722470400) == expected
    assert parse_publish_time(1722470400000) == expected


def test_artifact_profile_and_lock_paths_are_isolated_by_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    locator = MediaCrawlerBatchLocator(
        tmp_path / "runtime",
        platform_spec=WEIBO_PLATFORM_SPEC,
    )
    legacy = locator.locate("batch-1")
    scoped = locator.locate(
        "batch-1",
        artifact_scope="weibo/weibo_shadow",
    )
    assert legacy.output_path != scoped.output_path
    assert scoped.output_path == (
        tmp_path / "runtime" / "runs" / "batch-1" / "weibo" / "weibo_shadow"
        / "output" / "weibo.jsonl"
    )

    profiles = MediaCrawlerProfileManager(
        tmp_path / "runtime",
        tmp_path / "profiles",
        profile_scope="weibo/weibo_shadow",
    )
    assert profiles.profile_path("manual") == (
        tmp_path / "profiles" / "weibo" / "weibo_shadow" / "manual"
    ).resolve()

    entry = tmp_path / "MediaCrawler" / "main.py"
    entry.parent.mkdir(parents=True)
    entry.write_text("# test entry\n", encoding="utf-8")
    from app.core.config import settings

    monkeypatch.setattr(settings, "media_crawler_root", str(tmp_path / "runtime"))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(tmp_path / "profiles"))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", str(Path(__import__("sys").executable)))
    factory = MediaCrawlerRuntimeFactory(
        source_key="weibo_shadow",
        platform_spec=WEIBO_PLATFORM_SPEC,
    )
    _, lock, config = factory.create_runner("manual", mock_command=True)
    assert config.artifact_scope == "weibo/weibo_shadow"
    assert lock.path == (
        tmp_path / "runtime" / "locks" / "weibo" / "weibo_shadow.lock"
    )


def test_registry_identifies_mediacrawler_by_capability(monkeypatch) -> None:
    row = {
        "key": "weibo_mediacrawler",
        "name": "微博（MediaCrawler）",
        "class_path": (
            "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector"
        ),
        "scope_region_codes": "131000",
        "config_json": {
            "collector": "mediacrawler",
            "platform": "weibo",
            "keywords": ["廊坊"],
            "max_items": 1,
            "collection_scope": "regional",
        },
    }
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [row])

    result = registry.resolve_collectors_verbose(object())

    assert result.failures == []
    assert len(result.collectors) == 1
    assert result.collectors[0].collector_capability == MEDIACRAWLER_CAPABILITY
