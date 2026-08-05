"""Enable-1 preparation tests for scheduler command discovery.

These tests construct only temporary deployment settings and never start the
MediaCrawler process or touch the production profile/runtime.
"""
from __future__ import annotations

import sys
import subprocess
from pathlib import Path

import pytest

from app.collectors.mediacrawler_runtime import (
    MediaCrawlerRuntimeConfigurationError,
    MediaCrawlerRuntimeError,
    MediaCrawlerRuntimeFactory,
)


def _runtime_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, gate: bool) -> Path:
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
    return entry


def test_scheduler_command_resolution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A complete deployment contract reaches the upstream profile boundary."""

    entry = _runtime_settings(monkeypatch, tmp_path, gate=True)
    profile = tmp_path / "profiles" / "scheduler"
    profile.mkdir(parents=True)

    runner, _, config = MediaCrawlerRuntimeFactory().create_runner("scheduled")
    command = runner.command_factory(["大厂县"], 10, tmp_path / "run" / "output")  # type: ignore[union-attr]

    assert command[:2] == [sys.executable, str(entry)]
    assert command[command.index("--lt") + 1] == "cookie"
    assert runner.browser_data == str(profile.resolve())
    assert runner.profile_name == str(profile.resolve())
    assert runner.command_cwd == (tmp_path / "mediacrawler").resolve()
    assert config.profile_path == profile.resolve()


def test_scheduler_profile_is_injected_into_subprocess_without_starting_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The wrapper receives the profile path; subprocess execution is mocked."""

    _runtime_settings(monkeypatch, tmp_path, gate=True)
    profile = tmp_path / "profiles" / "scheduler"
    profile.mkdir(parents=True)
    runner, _, config = MediaCrawlerRuntimeFactory().create_runner("scheduler")
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        output_path = Path(kwargs["env"]["MEDIA_CRAWLER_OUTPUT"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('{"content":"fixture"}\n', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("app.collectors.mediacrawler_runner.subprocess.run", fake_run)
    result = runner.run(["大厂县"], max_items=1, timeout_seconds=5)

    environment = captured["env"]
    assert environment["MEDIA_CRAWLER_PROFILE_NAME"] == str(profile.resolve())
    assert environment["MEDIA_CRAWLER_BROWSER_DATA"] == str(profile.resolve())
    assert captured["cwd"] == str(config.runtime_path)
    assert result.exit_code == 0


def test_scheduler_command_missing_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An absent deployment entry is rejected before a collector can run."""

    from app.core.config import settings

    _runtime_settings(monkeypatch, tmp_path, gate=True)
    missing_entry = tmp_path / "missing" / "main.py"
    monkeypatch.setattr(settings, "media_crawler_entry", str(missing_entry))

    with pytest.raises(MediaCrawlerRuntimeConfigurationError, match="entry does not exist"):
        MediaCrawlerRuntimeFactory().create_runner("scheduler")


def test_scheduler_gate_false_fails_closed_without_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The gate blocks scheduled command construction while remaining unchanged."""

    _runtime_settings(monkeypatch, tmp_path, gate=False)
    (tmp_path / "profiles" / "scheduler").mkdir(parents=True)
    runner, _, config = MediaCrawlerRuntimeFactory().create_runner("scheduler")

    with pytest.raises(MediaCrawlerRuntimeError, match="real-run gate is disabled"):
        runner.command_factory(["大厂县"], 10, tmp_path / "run" / "output")  # type: ignore[union-attr]

    assert config.real_run_gate is False
