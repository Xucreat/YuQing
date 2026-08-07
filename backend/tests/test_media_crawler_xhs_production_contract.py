"""Offline production-contract checks for the formal XHS DataSource."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.collectors.data_source_repository import scheduled_enabled_sources
from app.collectors.media_crawler_registration import (
    XHS_MEDIACRAWLER_CONFIG,
    XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
    build_xhs_mediacrawler_data_source_payload,
)
from app.collectors.mediacrawler_platform import XHS_PLATFORM_SPEC
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from app.collectors.source_config import validate_data_source_config
from app.core.config import settings


def test_formal_xhs_datasource_defaults_to_manual_only() -> None:
    payload = build_xhs_mediacrawler_data_source_payload(
        enabled=True,
        schedule_enabled=False,
    )
    assert payload["key"] == XHS_MEDIACRAWLER_DATA_SOURCE_KEY
    assert payload["type"] == "social"
    assert payload["enabled"] is True
    assert payload["schedule_enabled"] is False
    assert json.loads(payload["config_json"])["platform"] == "xiaohongshu"


def test_xhs_runtime_context_has_separate_checkout_profile_and_output(
    monkeypatch, tmp_path: Path
) -> None:
    checkout_root = tmp_path / "checkout"
    checkout_root.mkdir()
    entry = checkout_root / "entry.py"
    entry.write_text("print('offline')\n", encoding="utf-8")
    runtime_root = tmp_path / "runtime"
    profile_root = tmp_path / "profiles"
    profile = profile_root / "xiaohongshu" / "xhs_mediacrawler" / "manual"
    profile.mkdir(parents=True)

    monkeypatch.setattr(settings, "media_crawler_real_run_gate", True)
    factory = MediaCrawlerRuntimeFactory(
        source_key=XHS_MEDIACRAWLER_DATA_SOURCE_KEY,
        platform_spec=XHS_PLATFORM_SPEC,
        root=runtime_root,
        checkout_root=checkout_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        real_run_gate=True,
    )
    config = factory.config("manual")

    assert config.checkout_root == checkout_root.resolve()
    assert config.profile_root == profile_root.resolve()
    assert config.output_root == runtime_root.resolve()
    assert config.checkout_root != config.profile_root
    assert config.profile_root != config.output_root
    assert config.profile_path == profile.resolve()


def test_xhs_security_contract_rejects_runtime_and_credential_keys() -> None:
    for forbidden in ("cookie", "token", "password", "profile_path", "shell_command", "command"):
        config = {**XHS_MEDIACRAWLER_CONFIG, forbidden: "blocked"}
        try:
            validate_data_source_config(config)
        except ValueError as exc:
            assert forbidden in str(exc)
        else:
            raise AssertionError(f"forbidden key accepted: {forbidden}")


def test_scheduler_contract_keeps_xhs_out_when_schedule_is_disabled() -> None:
    class EmptyRows:
        def mappings(self):
            return self

        def all(self):
            return []

    class FakeDb:
        def __init__(self):
            self.statement = ""
            self.params = None

        def execute(self, statement, params=None):
            self.statement = str(statement)
            self.params = params
            return EmptyRows()

    db = FakeDb()
    assert scheduled_enabled_sources(
        db,
        include_keys={XHS_MEDIACRAWLER_DATA_SOURCE_KEY},
    ) == []
    assert "enabled = true" in db.statement
    assert "schedule_enabled = true" in db.statement

