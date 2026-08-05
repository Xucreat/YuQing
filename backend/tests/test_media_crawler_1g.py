"""Offline acceptance tests for Phase MediaCrawler-1G gates."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.collectors.mediacrawler_command_builder import build_mediacrawler_command
from scripts.check_mediacrawler_weibo_profile import inspect_weibo_profile
from scripts.run_mediacrawler_real_verify import (
    compute_field_coverage,
    compute_jsonl_metrics,
    validate_real_verify_options,
)


def test_weibo_profile_exists_is_reported_without_internal_names(tmp_path: Path) -> None:
    browser_data = tmp_path / "browser_data"
    profile = browser_data / "wb_user_data_dir"
    profile.mkdir(parents=True)
    (profile / "state.db").write_bytes(b"12345")

    result = inspect_weibo_profile(str(browser_data))

    assert result == {
        "exists": True,
        "profile_path": str(profile),
        "file_count": 1,
        "size_bytes": 5,
        "status": "PASS",
    }
    assert "state.db" not in json.dumps(result)


def test_missing_weibo_profile_is_blocked(tmp_path: Path) -> None:
    result = inspect_weibo_profile(str(tmp_path / "browser_data"))

    assert result["exists"] is False
    assert result["file_count"] == 0
    assert result["size_bytes"] == 0
    assert result["status"] == "BLOCKED"


def test_real_gate_confirm_and_limits() -> None:
    cases = (
        ({"confirm_real_run": False, "max_items": 10, "timeout_seconds": 300, "enable_real_run": True}, "confirm-real-run"),
        ({"confirm_real_run": True, "max_items": 21, "timeout_seconds": 300, "enable_real_run": True}, "max_items"),
        ({"confirm_real_run": True, "max_items": 10, "timeout_seconds": 601, "enable_real_run": True}, "timeout_seconds"),
        ({"confirm_real_run": True, "max_items": 10, "timeout_seconds": 300, "enable_real_run": False}, "MEDIA_CRAWLER_ENABLE_REAL_RUN"),
    )
    for kwargs, expected in cases:
        try:
            validate_real_verify_options(**kwargs)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("invalid real-run options were accepted")


def test_sample_keyword_generates_native_command(tmp_path: Path) -> None:
    command = build_mediacrawler_command(
        ["大厂县"], 10, tmp_path / "output", python_executable=sys.executable, entry="main.py"
    )

    assert command[command.index("--keywords") + 1] == "大厂县"
    assert command[command.index("--crawler_max_notes_count") + 1] == "10"
    assert command[command.index("--save_data_option") + 1] == "jsonl"


def test_jsonl_quality_metrics_and_coverage(tmp_path: Path) -> None:
    path = tmp_path / "real-sample.jsonl"
    rows = [
        {"mid": "1", "text": "content", "nickname": "author", "url": "https://weibo/1", "created_at": "bad-time"},
        {"mid": "1", "text": "duplicate"},
        {"mid": "2", "text": ""},
        "invalid-json-row",
    ]
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

    assert compute_jsonl_metrics(path) == {
        "raw_count": 4,
        "valid_count": 2,
        "invalid_count": 2,
        "duplicate_count": 1,
        "output_count": 1,
    }
    assert compute_field_coverage([
        {"content": "content", "author": "author", "publish_time": None,
         "external_id": "1", "url": "https://weibo/1", "engagement": {}}
    ]) == {
        "content": 100.0,
        "author": 100.0,
        "publish_time": 0.0,
        "external_id": 100.0,
        "url": 100.0,
        "engagement": 100.0,
    }
