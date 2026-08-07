"""Read-only readiness and artifact-locator regression tests for Phase 2F."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.collectors.mediacrawler_batch import MediaCrawlerBatchLocator
from app.collectors.mediacrawler_profile import MediaCrawlerProfileManager
from app.collectors.mediacrawler_runtime import (
    MediaCrawlerProfileUnavailableError,
    MediaCrawlerRuntimeError,
    MediaCrawlerRuntimeFactory,
)
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_COMPATIBILITY_POLICY,
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)


def _runtime_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, gate: bool) -> Path:
    from app.core.config import settings

    entry = tmp_path / "MediaCrawler" / "main.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("# test entry\n", encoding="utf-8")
    monkeypatch.setattr(settings, "media_crawler_root", str(tmp_path / "runtime"))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(tmp_path / "profiles"))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", sys.executable)
    monkeypatch.setattr(settings, "media_crawler_real_run_gate", gate)
    monkeypatch.setattr(settings, "media_crawler_login_type", "qrcode")
    return entry


def test_profile_manager_resolves_isolated_paths_without_bootstrap(tmp_path: Path) -> None:
    manager = MediaCrawlerProfileManager(tmp_path / "runtime")

    readiness = manager.readiness()

    assert manager.profile_path("manual") == (tmp_path / "runtime" / "profiles" / "manual").resolve()
    assert manager.profile_path("scheduler") == (tmp_path / "runtime" / "profiles" / "scheduler").resolve()
    assert readiness["manual"]["exists"] is False
    assert readiness["scheduler"]["exists"] is False
    assert not (tmp_path / "runtime" / "profiles").exists()


def test_missing_profile_is_an_explicit_failure(tmp_path: Path) -> None:
    manager = MediaCrawlerProfileManager(tmp_path / "runtime")

    with pytest.raises(MediaCrawlerProfileUnavailableError, match="profile unavailable"):
        manager.require("scheduler")


def test_scheduler_gate_false_blocks_before_command_or_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _runtime_settings(monkeypatch, tmp_path, gate=False)
    profile = tmp_path / "profiles" / "scheduler"
    profile.mkdir(parents=True)
    runner, _, _ = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner("scheduler")

    with pytest.raises(MediaCrawlerRuntimeError, match="real-run gate is disabled"):
        runner.command_factory(["大厂县"], 10, tmp_path / "output")  # type: ignore[union-attr]


def test_scheduler_gate_true_allows_valid_mock_command_assembly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _runtime_settings(monkeypatch, tmp_path, gate=True)
    profile = tmp_path / "profiles" / "scheduler"
    profile.mkdir(parents=True)
    runner, _, config = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner("scheduler")

    command = runner.command_factory(["大厂县"], 10, tmp_path / "output")  # type: ignore[union-attr]

    assert config.real_run_gate is True
    assert command[0] == sys.executable
    assert command[command.index("--lt") + 1] == "cookie"


def test_manual_gate_false_can_construct_explicit_mock_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _runtime_settings(monkeypatch, tmp_path, gate=False)
    (tmp_path / "profiles" / "manual").mkdir(parents=True)
    runner, _, config = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
    ).create_runner("manual", mock_command=True)

    command = runner.command_factory(["大厂县"], 10, tmp_path / "output")  # type: ignore[union-attr]

    assert config.real_run_gate is False
    assert runner.mock_command is True
    assert command[command.index("--lt") + 1] == "qrcode"


def test_batch_locator_returns_all_paths_without_creating_legacy_batch(tmp_path: Path) -> None:
    locator = MediaCrawlerBatchLocator(
        tmp_path / "runtime",
        platform_spec=WEIBO_PLATFORM_SPEC,
    )
    paths = locator.locate("e62641b78a9449d0b9874c380a4aa8b5")

    assert paths.run_dir == tmp_path / "runtime" / "runs" / paths.batch_id
    assert paths.metrics_path == paths.run_dir / "metrics.json"
    assert paths.raw_path == paths.run_dir / "raw" / "weibo.jsonl"
    assert paths.output_path == paths.run_dir / "output" / "weibo.jsonl"
    assert locator.inspect(paths.batch_id)["metrics_exists"] is False
    assert not paths.run_dir.exists()


def test_batch_locator_rejects_path_traversal(tmp_path: Path) -> None:
    locator = MediaCrawlerBatchLocator(
        tmp_path / "runtime",
        platform_spec=WEIBO_PLATFORM_SPEC,
    )

    with pytest.raises(ValueError, match="invalid MediaCrawler batch_id"):
        locator.locate("../legacy")
