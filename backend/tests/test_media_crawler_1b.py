"""Offline acceptance tests for the MediaCrawler Phase 1B controls."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.collectors.media_crawler_registration import (
    MEDIACRAWLER_CLASS_PATH,
    MEDIACRAWLER_DATA_SOURCE_KEY,
    build_mediacrawler_data_source_payload,
    parse_mediacrawler_config,
)
from app.collectors.mediacrawler_runner import (
    MediaCrawlerProcessError,
    MediaCrawlerRealRunDisabledError,
    MediaCrawlerRunner,
)
from app.core.config import settings


FIXTURE = Path(__file__).parent / "fixtures" / "media_crawler" / "weibo.jsonl"
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_mediacrawler_datasource_payload_is_national_and_disabled() -> None:
    payload = build_mediacrawler_data_source_payload()

    assert payload["key"] == MEDIACRAWLER_DATA_SOURCE_KEY
    assert payload["type"] == "social"
    assert payload["class_path"] == MEDIACRAWLER_CLASS_PATH
    assert payload["enabled"] is False
    assert payload["schedule_enabled"] is False
    assert payload["schedule_interval_minutes"] == 60
    assert parse_mediacrawler_config(payload["config_json"]) == {
        "collector": "mediacrawler",
        "platform": "weibo",
        "keywords": ["大厂县"],
        "max_items": 10,
        "collection_scope": "national",
    }


def test_reject_collection_mode_manual() -> None:
    with pytest.raises(ValueError, match="collection_mode"):
        parse_mediacrawler_config({"collection_mode": "manual"})


def test_real_command_is_blocked_without_explicit_enable(tmp_path: Path, monkeypatch) -> None:
    called = []

    def forbidden_run(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("subprocess must not run when real mode is disabled")

    monkeypatch.setattr(
        "app.collectors.mediacrawler_runner.subprocess.run", forbidden_run
    )
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[sys.executable, "-c", "raise SystemExit(0)"],
        mock_command=False,
        enable_real_run=False,
    )

    with pytest.raises(MediaCrawlerRealRunDisabledError):
        runner.run([], timeout_seconds=5)
    assert called == []


def test_environment_check_is_read_only_and_does_not_expose_browser_path(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "MediaCrawler"
    root.mkdir()
    (root / "main.py").write_text("# fixture entry\n", encoding="utf-8")
    browser_data = tmp_path / "browser-data"
    browser_data.mkdir()
    monkeypatch.setenv("MEDIA_CRAWLER_ROOT", str(root))
    monkeypatch.setenv("MEDIA_CRAWLER_PYTHON", sys.executable)
    monkeypatch.setenv("MEDIA_CRAWLER_BROWSER_DATA", str(browser_data))
    monkeypatch.delenv("MEDIA_CRAWLER_ENTRY", raising=False)

    from scripts import check_mediacrawler_env

    checks = check_mediacrawler_env.collect_checks()
    assert all(check.ok for check in checks)
    output = " ".join(f"{check.name} {check.detail}" for check in checks)
    assert str(browser_data) not in output


def test_manual_script_uses_fixture_and_does_not_write_database() -> None:
    script = BACKEND_ROOT / "scripts" / "test_mediacrawler_manual.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--keywords",
            "廊坊",
            "消防",
            "--max-items",
            "2",
            "--fixture",
            str(FIXTURE),
        ],
        cwd=str(BACKEND_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["count"] == 2
    assert result["items"][0]["source_type"] == "weibo_post"
    assert "INSERT" not in completed.stdout.upper()


def test_mock_command_nonzero_exit_preserves_redacted_stderr(tmp_path: Path) -> None:
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('token=secret-value\\n'); sys.exit(7)",
        ],
        mock_command=True,
    )

    with pytest.raises(MediaCrawlerProcessError) as exc_info:
        runner.run([], timeout_seconds=5)
    assert exc_info.value.exit_code == 7
    assert "secret-value" not in exc_info.value.stderr
    log_path = next((tmp_path / "runtime" / "runs").glob("*/crawler.log"))
    log = log_path.read_text(encoding="utf-8")
    assert "secret-value" not in log
    assert "[REDACTED]" in log


def test_real_run_setting_defaults_closed() -> None:
    assert settings.media_crawler_enable_real_run is False
    assert hasattr(settings, "media_crawler_entry")
