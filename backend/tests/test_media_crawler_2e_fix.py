"""Regression coverage for the MediaCrawler scheduler runtime boundary."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRunnerConfigurationError,
    MediaCrawlerTimeoutError,
)
from app.collectors.mediacrawler_runtime import (
    MediaCrawlerLockTimeoutError,
    MediaCrawlerProfileUnavailableError,
    MediaCrawlerRunLock,
    MediaCrawlerRuntimeFactory,
)


def _settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "media_crawler_root", str(tmp_path / "runtime"))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(tmp_path / "profiles"))
    entry = tmp_path / "MediaCrawler" / "main.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("# test entry\n", encoding="utf-8")
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", sys.executable)
    monkeypatch.setattr(settings, "media_crawler_enable_real_run", False)
    monkeypatch.setattr(settings, "media_crawler_real_run_gate", False)


def test_runtime_factory_isolates_manual_and_scheduler_profiles(monkeypatch, tmp_path: Path) -> None:
    _settings(monkeypatch, tmp_path)
    factory = MediaCrawlerRuntimeFactory()

    manual, _, manual_cfg = factory.create_runner("manual")
    scheduler, _, scheduler_cfg = factory.create_runner("scheduled")

    assert manual_cfg.profile_path == (tmp_path / "profiles" / "manual").resolve()
    assert scheduler_cfg.profile_path == (tmp_path / "profiles" / "scheduler").resolve()
    assert manual.browser_data != scheduler.browser_data
    assert manual.command is None
    assert scheduler.command is None


def test_runtime_factory_does_not_read_runtime_values_from_datasource(monkeypatch, tmp_path: Path) -> None:
    _settings(monkeypatch, tmp_path)
    factory = MediaCrawlerRuntimeFactory()
    _, _, cfg = factory.create_runner("scheduler")

    # Runtime paths are deployment settings only; a business config is never an input.
    assert "cookie" not in str(cfg.profile_path).lower()
    assert cfg.entry == (tmp_path / "MediaCrawler" / "main.py").resolve()


def test_manual_and_scheduler_use_one_command_builder(monkeypatch, tmp_path: Path) -> None:
    _settings(monkeypatch, tmp_path)
    builder = MediaCrawlerCommandBuilder(python_executable=sys.executable, entry="entry.py")
    manual = builder.build(keywords=["大厂县"], max_items=10, output_dir=tmp_path / "manual", login_type="qrcode")
    scheduler = builder.build(keywords=["大厂县"], max_items=10, output_dir=tmp_path / "scheduler", login_type="cookie")

    assert manual[:2] == scheduler[:2]
    assert manual[manual.index("--platform") : manual.index("--platform") + 2] == scheduler[
        scheduler.index("--platform") : scheduler.index("--platform") + 2
    ]
    assert manual[manual.index("--lt") + 1] == "qrcode"
    assert scheduler[scheduler.index("--lt") + 1] == "cookie"


def test_source_lock_conflict_and_release(tmp_path: Path) -> None:
    path = tmp_path / "locks" / "weibo_mediacrawler.lock"
    first = MediaCrawlerRunLock(path, timeout_seconds=0)
    second = MediaCrawlerRunLock(path, timeout_seconds=0)
    first.acquire()
    try:
        with pytest.raises(MediaCrawlerLockTimeoutError):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_factory_rejects_qrcode_scheduler(monkeypatch, tmp_path: Path) -> None:
    _settings(monkeypatch, tmp_path)
    from app.core.config import settings

    monkeypatch.setattr(settings, "media_crawler_scheduler_login_type", "qrcode")
    with pytest.raises(Exception, match="non-interactive"):
        MediaCrawlerRuntimeFactory().create_runner("scheduler")


def test_missing_profile_fails_closed_at_command_build(monkeypatch, tmp_path: Path) -> None:
    _settings(monkeypatch, tmp_path)
    from app.core.config import settings

    monkeypatch.setattr(settings, "media_crawler_real_run_gate", True)
    runner, _, _ = MediaCrawlerRuntimeFactory().create_runner("scheduler")
    with pytest.raises(MediaCrawlerProfileUnavailableError, match="profile unavailable"):
        runner.command_factory(["大厂县"], 10, tmp_path / "output")  # type: ignore[union-attr]


def test_no_command_is_a_failed_runner_path(tmp_path: Path) -> None:
    from app.collectors.mediacrawler_runner import MediaCrawlerRunner

    runner = MediaCrawlerRunner(root=tmp_path)
    with pytest.raises(MediaCrawlerRunnerConfigurationError, match="no MediaCrawler command"):
        runner.run(["大厂县"], max_items=10, timeout_seconds=5)


def test_timeout_is_preserved_as_failure(tmp_path: Path) -> None:
    from app.collectors.mediacrawler_runner import MediaCrawlerRunner

    runner = MediaCrawlerRunner(
        root=tmp_path,
        command=[sys.executable, "-c", "import time; time.sleep(1)"],
    )
    with pytest.raises(MediaCrawlerTimeoutError):
        runner.run(["大厂县"], max_items=10, timeout_seconds=0.05)
