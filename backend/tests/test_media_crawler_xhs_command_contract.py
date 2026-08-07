"""Offline XHS command and isolation contracts for Platform-2-B2."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.collectors.mediacrawler_batch import MediaCrawlerBatchLocator
from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_platform import (
    XHS_PLATFORM_SPEC,
    MediaCrawlerConfigurationError,
)
from app.collectors.mediacrawler_profile import MediaCrawlerProfileManager
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRealRunDisabledError,
    MediaCrawlerRunner,
)
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from app.core.config import settings


def test_verified_xhs_contract_generates_an_argv() -> None:
    builder = MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="main.py",
        platform_spec=XHS_PLATFORM_SPEC,
    )

    argv = builder.build(
        keywords=["测试"],
        max_items=1,
        output_dir="runtime-output",
    )

    assert argv[argv.index("--platform") + 1] == "xhs"
    assert argv[argv.index("--type") + 1] == "search"


def test_xhs_contract_generates_spec_driven_argv_without_weibo_tokens(
    tmp_path: Path,
) -> None:
    spec = XHS_PLATFORM_SPEC
    output_dir = tmp_path / "xhs-output"
    argv = MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="main.py",
        platform_spec=spec,
    ).build(
        keywords=["测试"],
        max_items=2,
        output_dir=output_dir,
        login_type="qrcode",
    )

    assert argv[argv.index("--platform") + 1] == spec.cli_code
    assert argv[argv.index("--type") + 1] == "search"
    assert argv[argv.index("--lt") + 1] == "qrcode"
    assert argv[argv.index("--save_data_path") + 1] == str(output_dir.resolve())
    assert all("weibo" not in part.lower() and part.lower() != "wb" for part in argv)


def test_xhs_artifact_contract_isolated_by_platform_source_and_batch(
    tmp_path: Path,
) -> None:
    locator = MediaCrawlerBatchLocator(
        tmp_path / "runtime",
        platform_spec=XHS_PLATFORM_SPEC,
    )
    first = locator.locate(
        "batch-a",
        artifact_scope="xiaohongshu/xhs_source",
    )
    second = locator.locate(
        "batch-b",
        artifact_scope="xiaohongshu/xhs_source",
    )

    assert first.raw_path.name == "xiaohongshu.jsonl"
    assert first.output_path.name == "xiaohongshu.jsonl"
    assert first.metrics_path.name == "metrics.json"
    assert "weibo" not in str(first.run_dir).lower()
    assert first.output_path != second.output_path
    assert first.raw_path.parent == first.output_path.parent.parent / "raw"


def test_xhs_lock_and_profile_paths_are_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "runtime"
    profile_root = tmp_path / "profiles"
    entry = tmp_path / "MediaCrawler" / "main.py"
    entry.parent.mkdir(parents=True)
    entry.write_text("# offline entry\n", encoding="utf-8")
    monkeypatch.setattr(settings, "media_crawler_root", str(runtime_root))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(profile_root))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", sys.executable)

    factory = MediaCrawlerRuntimeFactory(
        source_key="xhs_source",
        platform_spec=XHS_PLATFORM_SPEC,
    )
    _, lock, config = factory.create_runner("manual", mock_command=True)

    assert config.profile_path == (
        profile_root / "xiaohongshu" / "xhs_source" / "manual"
    ).resolve()
    assert config.artifact_scope == "xiaohongshu/xhs_source"
    assert lock.path == (
        runtime_root / "locks" / "xiaohongshu" / "xhs_source.lock"
    )
    assert MediaCrawlerProfileManager(
        runtime_root,
        profile_root,
        profile_scope="xiaohongshu/xhs_source",
    ).profile_path("manual") == config.profile_path


def test_real_run_gate_closed_does_not_execute_xhs_command(tmp_path: Path) -> None:
    marker = tmp_path / "started.txt"
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[
            sys.executable,
            "-c",
            f"from pathlib import Path; Path({str(marker)!r}).write_text('started')",
        ],
        platform_spec=XHS_PLATFORM_SPEC,
        source_key="xhs_source",
        mock_command=False,
        enable_real_run=False,
    )

    with pytest.raises(MediaCrawlerRealRunDisabledError):
        runner.run(["测试"], timeout_seconds=5)

    assert not marker.exists()
