"""Platform-2-D controlled XHS runtime harness tests.

The controlled run starts only the temporary fake CLI embedded in the harness.
It never starts the upstream MediaCrawler process, Scheduler, or database.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.collectors.mediacrawler_platform import XHS_PLATFORM_SPEC
from app.collectors.mediacrawler_profile import (
    MediaCrawlerProfileUnavailableError,
)
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from scripts import run_mediacrawler_xhs_controlled_verify as harness


def _json_result(output: str) -> dict:
    lines = [line for line in output.splitlines() if line.startswith("{")]
    assert lines
    return json.loads(lines[-1])


def test_default_harness_is_dry_run_and_does_not_start_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden_run(*args, **kwargs):
        raise AssertionError("dry-run must not start subprocess")

    monkeypatch.setattr(
        "app.collectors.mediacrawler_runner.subprocess.run",
        forbidden_run,
    )

    assert harness.main([]) == 0
    output = capsys.readouterr().out
    result = _json_result(output)

    assert output.startswith("argv_snapshot=")
    assert result["status"] == "DRY_RUN"
    assert result["subprocess_allowed"] is False
    assert result["real_collection_allowed"] is True
    assert result["scheduler_started"] is False
    assert result["database_writes"] == 0
    assert result["platform_spec"]["cli_code"] == XHS_PLATFORM_SPEC.cli_code
    assert result["platform_spec"]["native_output_parts"] == ["xhs", "jsonl"]
    assert all(
        "weibo" not in part.lower() and part.lower() != "wb"
        for part in result["argv_snapshot"]
    )


@pytest.mark.parametrize("crawler_type", ["search", "detail", "creator"])
def test_dry_run_argv_uses_each_spec_mode(
    crawler_type: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert harness.main(["--crawler-type", crawler_type]) == 0
    result = _json_result(capsys.readouterr().out)
    argv = result["argv_snapshot"]
    assert argv[argv.index("--platform") + 1] == "xhs"
    assert argv[argv.index("--type") + 1] == crawler_type
    assert argv[argv.index("--save_data_option") + 1] == "jsonl"
    assert "--save_data_path" in argv


def test_controlled_sandbox_runs_fake_cli_and_validates_native_artifacts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert harness.main(
        [
            "--allow-controlled-run",
            "--comments",
            "--crawler-type",
            "creator",
            "--login-type",
            "cookie",
        ]
    ) == 0
    output = capsys.readouterr().out
    result = _json_result(output)

    assert result["status"] == "PASS"
    assert result["mode"] == "controlled_sandbox"
    assert result["subprocess_allowed"] is True
    assert result["real_collection_allowed"] is True
    assert result["real_media_crawler_started"] is False
    assert result["scheduler_started"] is False
    assert result["database_writes"] == 0
    assert result["normalized_count"] == 1
    assert result["normalized_sample"][0]["source"] == "xiaohongshu"
    assert result["normalized_sample"][0]["source_type"] == "xhs_note"
    assert result["normalized_sample"][0]["external_id"].startswith("controlled-")
    assert result["artifact"]["contains_weibo"] is False
    assert len(result["artifact"]["native_content_paths"]) == 1
    assert len(result["artifact"]["native_comment_paths"]) == 1
    assert result["cleanup_status"] == "success_cleaned"
    assert {item["source_key"] for item in result["profile_audit"]} == {
        "xhs_controlled_verify",
        "xhs_controlled_verify_alt",
    }
    assert {
        (item["source_key"], item["trigger"])
        for item in result["profile_audit"]
    } == {
        ("xhs_controlled_verify", "manual"),
        ("xhs_controlled_verify", "scheduler"),
        ("xhs_controlled_verify_alt", "manual"),
    }
    assert all(
        "cookie" not in json.dumps(item).lower()
        and "token" not in json.dumps(item).lower()
        for item in result["profile_audit"]
    )


def test_unknown_mode_is_blocked_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden_run(*args, **kwargs):
        raise AssertionError("invalid mode must not start subprocess")

    monkeypatch.setattr(
        "app.collectors.mediacrawler_runner.subprocess.run",
        forbidden_run,
    )

    assert harness.main(["--allow-controlled-run", "--crawler-type", "unknown"]) == 3
    result = _json_result(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert "invalid MediaCrawler crawler_type" in result["reason"]


def test_missing_profile_and_invalid_login_fail_closed_without_process(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    profile_root = tmp_path / "profiles"
    entry = tmp_path / "fake-entry.py"
    entry.write_text("# no process is started by this test\n", encoding="utf-8")

    missing_profile_factory = MediaCrawlerRuntimeFactory(
        source_key="xhs_missing_profile",
        platform_spec=XHS_PLATFORM_SPEC,
        root=runtime_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        login_type="qrcode",
        real_run_gate=False,
    )
    missing_runner, _, _ = missing_profile_factory.create_runner(
        "manual",
        mock_command=False,
    )
    with pytest.raises(MediaCrawlerProfileUnavailableError):
        missing_runner.command_factory(["controlled"], 1, tmp_path / "output")  # type: ignore[union-attr]

    (profile_root / "xiaohongshu" / "xhs_invalid_login" / "manual").mkdir(
        parents=True
    )
    invalid_login_factory = MediaCrawlerRuntimeFactory(
        source_key="xhs_invalid_login",
        platform_spec=XHS_PLATFORM_SPEC,
        root=runtime_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        login_type="invalid-login",
        real_run_gate=False,
    )
    invalid_runner, _, _ = invalid_login_factory.create_runner(
        "manual",
        mock_command=True,
    )
    with pytest.raises(ValueError, match="invalid MediaCrawler login_type"):
        invalid_runner.command_factory(["controlled"], 1, tmp_path / "output")  # type: ignore[union-attr]
