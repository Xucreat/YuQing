"""Regression coverage for disposable scheduler browser profiles.

All subprocesses in this module are mocked; no Scheduler, browser, database,
or real MediaCrawler process is started.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_runner import MediaCrawlerProcessError
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_COMPATIBILITY_POLICY,
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)
from app.core.browser_profile_manager import BrowserProfileIsolationManager


def _settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, gate: bool = True) -> Path:
    from app.core.config import settings

    root = tmp_path / "mediacrawler"
    entry = root / "main.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("# test entry\n", encoding="utf-8")
    monkeypatch.setattr(settings, "media_crawler_root", str(root))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(tmp_path / "profiles"))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", sys.executable)
    monkeypatch.setattr(settings, "media_crawler_real_run_gate", gate)
    monkeypatch.setattr(settings, "media_crawler_scheduler_login_type", "cookie")
    monkeypatch.setattr(settings, "media_crawler_login_type", "qrcode")
    return root


def _source_profile(tmp_path: Path, *, trigger: str = "scheduler") -> Path:
    profile = tmp_path / "profiles" / trigger
    (profile / "Default").mkdir(parents=True, exist_ok=True)
    (profile / "Default" / "Preferences").write_text("template", encoding="utf-8")
    (profile / "Local State").write_text("template-state", encoding="utf-8")
    return profile


def _fake_success(command, **kwargs):
    output_path = Path(kwargs["env"]["MEDIA_CRAWLER_OUTPUT"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text('{"content":"fixture","id":"1"}\n', encoding="utf-8")
    runtime_profile = Path(kwargs["env"]["MEDIA_CRAWLER_PROFILE_NAME"])
    (runtime_profile / "Default").mkdir(parents=True, exist_ok=True)
    (runtime_profile / "Default" / "Cookies").write_bytes(b"fake-cookie")
    (runtime_profile / "Default" / "History").write_bytes(b"fake-history")
    (runtime_profile / "Local State").write_bytes(b"fake-local-state")
    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


def test_runtime_profile_created(monkeypatch, tmp_path: Path) -> None:
    root = _settings(monkeypatch, tmp_path)
    source = _source_profile(tmp_path)
    destination = BrowserProfileIsolationManager(root).create_runtime_profile(
        source,
        "batch-001",
    )

    assert destination == (root / "runtime_profiles" / "batch-001").resolve()
    assert destination.is_dir()
    assert (destination / "Default" / "Preferences").read_text(encoding="utf-8") == "template"


def test_scheduler_factory_uses_isolated_profile(monkeypatch, tmp_path: Path) -> None:
    root = _settings(monkeypatch, tmp_path)
    source = _source_profile(tmp_path)
    runner, _, config = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner(
        "scheduled",
        batch_id="batch-002",
    )

    assert config.profile_path == source.resolve()
    assert config.runtime_profile_path == (root / "runtime_profiles" / "batch-002").resolve()
    assert Path(runner.browser_data) == config.runtime_profile_path
    assert Path(runner.profile_name) == config.runtime_profile_path
    assert Path(runner.browser_data) != source.resolve()


def test_original_profile_immutable_when_fake_browser_writes(
    monkeypatch, tmp_path: Path
) -> None:
    root = _settings(monkeypatch, tmp_path)
    source = _source_profile(tmp_path)
    before = {
        path.relative_to(source): (
            path.stat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in source.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr("app.collectors.mediacrawler_runner.subprocess.run", _fake_success)
    runner, _, config = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner(
        "scheduled",
        batch_id="batch-003",
    )
    runner.run(["keyword"], max_items=1, timeout_seconds=5)

    after = {
        path.relative_to(source): (
            path.stat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in source.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert config.runtime_profile_path is not None
    assert (config.runtime_profile_path / "Default" / "Cookies").is_file()


def test_cleanup_success_path(monkeypatch, tmp_path: Path) -> None:
    root = _settings(monkeypatch, tmp_path)
    _source_profile(tmp_path)
    monkeypatch.setattr("app.collectors.mediacrawler_runner.subprocess.run", _fake_success)
    collector = MediaCrawlerWeiboCollector(
        runtime_factory=MediaCrawlerRuntimeFactory(
            source_key=WEIBO_SOURCE_KEY,
            platform_spec=WEIBO_PLATFORM_SPEC,
            compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
        )
    )
    collector.fetch(keywords=["keyword"], trigger_type="scheduled", batch_id="batch-004")

    assert not (root / "runtime_profiles" / "batch-004").exists()


def test_failure_path_retains_runtime_profile(monkeypatch, tmp_path: Path) -> None:
    root = _settings(monkeypatch, tmp_path)
    _source_profile(tmp_path)

    def fake_failure(command, **kwargs):
        return subprocess.CompletedProcess(command, 7, stdout="", stderr="failure")

    monkeypatch.setattr("app.collectors.mediacrawler_runner.subprocess.run", fake_failure)
    collector = MediaCrawlerWeiboCollector(
        runtime_factory=MediaCrawlerRuntimeFactory(
            source_key=WEIBO_SOURCE_KEY,
            platform_spec=WEIBO_PLATFORM_SPEC,
            compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
        )
    )
    with pytest.raises(MediaCrawlerProcessError):
        collector.fetch(keywords=["keyword"], trigger_type="scheduled", batch_id="batch-005")

    assert (root / "runtime_profiles" / "batch-005").is_dir()


def test_manual_behavior_unchanged(monkeypatch, tmp_path: Path) -> None:
    root = _settings(monkeypatch, tmp_path, gate=False)
    manual = _source_profile(tmp_path, trigger="manual")
    runner, _, config = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner(
        "manual",
        mock_command=True,
    )

    assert config.profile_path == manual.resolve()
    assert Path(runner.browser_data) == manual.resolve()
    assert runner.profile_name == str(manual.resolve())
    command = runner.command_factory(["keyword"], 1, tmp_path / "output")  # type: ignore[union-attr]
    assert command[command.index("--lt") + 1] == "qrcode"
    assert not (root / "runtime_profiles").exists()
