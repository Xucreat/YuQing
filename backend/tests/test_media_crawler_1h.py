"""Offline tests for Phase MediaCrawler-1H runtime diagnostics."""
from __future__ import annotations

import sys
from pathlib import Path

from app.collectors.mediacrawler_command_builder import build_mediacrawler_command
from scripts.check_mediacrawler_weibo_runtime import inspect_runtime
from scripts.check_mediacrawler_weibo_profile import inspect_weibo_profile
from scripts.run_mediacrawler_real_verify import compute_jsonl_metrics


def test_runtime_diagnostic_passes_injected_healthy_state(tmp_path: Path) -> None:
    (tmp_path / "wb_user_data_dir").mkdir()
    result = inspect_runtime(
        browser_data=str(tmp_path),
        cdp_port=65530,
        browser_process_check=True,
    )
    assert result["profile"] == "PASS"
    assert result["cdp"] == "BLOCKED"
    assert result["browser"] == "PASS"


def test_runtime_diagnostic_blocks_missing_profile(tmp_path: Path) -> None:
    result = inspect_runtime(
        browser_data=str(tmp_path),
        cdp_port=65530,
        browser_process_check=False,
    )
    assert result == {
        "profile": "BLOCKED",
        "cdp": "BLOCKED",
        "browser": "BLOCKED",
        "reason": "wb_user_data_dir missing; CDP port 65530 is not listening; Chrome process not detected",
    }


def test_profile_metadata_remains_content_free(tmp_path: Path) -> None:
    profile = tmp_path / "wb_user_data_dir"
    profile.mkdir()
    (profile / "private-state").write_bytes(b"secret")
    result = inspect_weibo_profile(str(tmp_path))
    assert result["status"] == "PASS"
    assert result["file_count"] == 1
    assert "private-state" not in str(result)


def test_standard_native_command_uses_debug_entry(tmp_path: Path) -> None:
    command = build_mediacrawler_command(
        ["大厂县"], 10, tmp_path / "output", python_executable=sys.executable, entry="standard_entry.py"
    )
    assert command[1] == "standard_entry.py"
    assert command[command.index("--platform") + 1] == "wb"
    assert command[command.index("--type") + 1] == "search"
    assert command[command.index("--save_data_option") + 1] == "jsonl"


def test_quality_metrics_read_jsonl_only(tmp_path: Path) -> None:
    path = tmp_path / "sample.jsonl"
    path.write_text('{"mid":"1","text":"a"}\nnot-json\n', encoding="utf-8")
    assert compute_jsonl_metrics(path) == {
        "raw_count": 2,
        "valid_count": 1,
        "invalid_count": 1,
        "duplicate_count": 0,
        "output_count": 1,
    }
