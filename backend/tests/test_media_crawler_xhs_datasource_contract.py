"""Offline formal DataSource contract tests for the XHS MediaCrawler source."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.admin_data_sources import _build_test, _validate_create
from app.collectors import data_source_repository, registry
from app.collectors.media_crawler_registration import (
    MEDIACRAWLER_CLASS_PATH,
    XHS_MEDIACRAWLER_CONFIG,
    XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
    build_mediacrawler_data_source_payload,
    build_xhs_mediacrawler_data_source_payload,
    parse_mediacrawler_config,
)
from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_platform import (
    XHS_PLATFORM_SPEC,
    get_mediacrawler_platform_spec,
)
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRealRunDisabledError,
    MediaCrawlerRunner,
)
from app.collectors.registry import import_class
from app.collectors.source_config import validate_data_source_config


def test_xhs_registration_payload_is_formal_and_disabled_by_default() -> None:
    payload = build_xhs_mediacrawler_data_source_payload()

    assert payload["key"] == XHS_MEDIACRAWLER_DATA_SOURCE_KEY
    assert payload["type"] == "social"
    assert payload["enabled"] is False
    assert payload["schedule_enabled"] is False
    assert payload["class_path"].endswith(
        "media_crawler_platform_collector.MediaCrawlerPlatformCollector"
    )
    assert parse_mediacrawler_config(payload["config_json"]) == XHS_MEDIACRAWLER_CONFIG
    assert payload["scope_region_codes"] == "131028"


def test_weibo_registration_payload_and_class_path_remain_unchanged() -> None:
    payload = build_mediacrawler_data_source_payload()

    assert payload["key"] == "weibo_mediacrawler"
    assert payload["class_path"] == MEDIACRAWLER_CLASS_PATH
    assert import_class(payload["class_path"]) is MediaCrawlerWeiboCollector
    assert payload["schedule_enabled"] is False


def test_xhs_config_validation_accepts_formal_fields_and_rejects_runtime_keys() -> None:
    config = validate_data_source_config(
        {
            **XHS_MEDIACRAWLER_CONFIG,
            "platform_options": {"verification": "offline"},
        }
    )
    assert config["platform"] == "xiaohongshu"

    with pytest.raises(ValueError, match="unsupported top-level keys"):
        validate_data_source_config(
            {**XHS_MEDIACRAWLER_CONFIG, "shell_command": "python main.py"}
        )
    with pytest.raises(ValueError, match="get_comment"):
        validate_data_source_config({**XHS_MEDIACRAWLER_CONFIG, "get_comment": "yes"})


def test_xhs_platform_spec_is_real_run_capable_only_through_existing_gates() -> None:
    assert get_mediacrawler_platform_spec("xiaohongshu") is XHS_PLATFORM_SPEC
    assert XHS_PLATFORM_SPEC.allow_real_collection is True
    assert XHS_PLATFORM_SPEC.cli_code == "xhs"
    assert XHS_PLATFORM_SPEC.native_output_parts == ("xhs", "jsonl")


def test_xhs_command_builder_uses_spec_and_comment_contract(tmp_path: Path) -> None:
    argv = MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="main.py",
        platform_spec=XHS_PLATFORM_SPEC,
    ).build(
        keywords=["大厂"],
        max_items=20,
        output_dir=tmp_path,
        login_type="qrcode",
        crawler_type="search",
        get_comment=True,
        get_sub_comment=False,
    )

    assert argv[argv.index("--platform") + 1] == "xhs"
    assert argv[argv.index("--type") + 1] == "search"
    assert argv[argv.index("--get_comment") + 1] == "true"
    assert argv[argv.index("--get_sub_comment") + 1] == "false"
    assert all("weibo" not in part.lower() and part.lower() != "wb" for part in argv)


def test_registry_resolves_xhs_through_generic_capability(monkeypatch) -> None:
    row = {
        "key": XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
        "name": "小红书（MediaCrawler）",
        "class_path": (
            "app.collectors.media_crawler_platform_collector."
            "MediaCrawlerPlatformCollector"
        ),
        "scope_region_codes": "131028",
        "config_json": json.dumps(XHS_MEDIACRAWLER_CONFIG, ensure_ascii=False),
    }
    monkeypatch.setattr(data_source_repository, "enabled_sources", lambda _db: [row])

    resolved = registry.resolve_collectors_verbose(object())

    assert resolved.failures == []
    assert len(resolved.collectors) == 1
    collector = resolved.collectors[0]
    assert collector.platform_spec is XHS_PLATFORM_SPEC
    assert collector.data_source_key == XHS_MEDIACRAWLER_DATA_SOURCE_KEY
    assert collector.__class__.__name__ == "MediaCrawlerPlatformCollector"
    assert collector.runtime_factory._login_type_override == "qrcode"


def test_admin_contract_accepts_social_xhs_without_real_collection() -> None:
    body = {
        "key": XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
        "name": "小红书（MediaCrawler）",
        "type": "social",
        "scope_region_codes": "131028",
        "schedule_enabled": False,
        "config_json": XHS_MEDIACRAWLER_CONFIG,
    }

    assert _validate_create(body) is None
    result = _build_test(
        (
            "app.collectors.media_crawler_platform_collector."
            "MediaCrawlerPlatformCollector"
        ),
        XHS_MEDIACRAWLER_CONFIG,
        data_source_key=XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
    )
    assert result["ok"] is True
    assert result["verified"] is False
    assert "subprocess" in result["note"]


def test_scheduler_contract_discovers_xhs_only_when_schedule_enabled() -> None:
    from app.collectors.data_source_repository import scheduled_enabled_sources

    class Rows:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "id": 91,
                    "key": XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
                }
            ]

    class FakeDb:
        def __init__(self):
            self.statement = ""
            self.params = None

        def execute(self, statement, params=None):
            self.statement = str(statement)
            self.params = params
            return Rows()

    db = FakeDb()
    rows = scheduled_enabled_sources(
        db,
        include_keys={XHS_MEDIACRAWLER_DATA_SOURCE_KEY},
    )

    assert [row["key"] for row in rows] == [XHS_MEDIACRAWLER_DATA_SOURCE_KEY]
    assert "enabled = true" in db.statement
    assert "schedule_enabled = true" in db.statement
    assert db.params["include_keys"] == (XHS_MEDIACRAWLER_DATA_SOURCE_KEY,)


def test_real_run_gate_remains_closed_by_default_for_formal_xhs_source(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "started.txt"
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[
            "python",
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).write_text('started')",
        ],
        platform_spec=XHS_PLATFORM_SPEC,
        source_key=XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
        mock_command=False,
        enable_real_run=False,
    )

    with pytest.raises(MediaCrawlerRealRunDisabledError):
        runner.run(["大厂"], timeout_seconds=5)

    assert not marker.exists()
