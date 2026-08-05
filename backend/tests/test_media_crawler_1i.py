"""Offline tests for Phase MediaCrawler-1I login-state tooling."""
from __future__ import annotations

from pathlib import Path

from scripts.check_weibo_profile_switch import inspect_profile
from scripts.run_mediacrawler_login_check import (
    build_weibo_headers,
    login_check_result,
    validate_login_check_options,
)
from scripts.run_mediacrawler_real_verify import compute_jsonl_metrics


def test_profile_check_reads_metadata_only(tmp_path: Path) -> None:
    profile = tmp_path / "wb_user_data_dir_manual"
    profile.mkdir()
    (profile / "private-state").write_bytes(b"not printed")
    result = inspect_profile(profile)
    assert result == {
        "exists": True,
        "size_bytes": 11,
        "file_count": 1,
        "status": "PASS",
    }
    assert "private-state" not in str(result)


def test_missing_profile_is_blocked(tmp_path: Path) -> None:
    result = inspect_profile(tmp_path / "missing")
    assert result == {
        "exists": False,
        "size_bytes": 0,
        "file_count": 0,
        "status": "BLOCKED",
    }


def test_login_blocked_result_is_non_sensitive() -> None:
    result = login_check_result(False)
    assert result == {
        "status": "LOGIN_BLOCKED",
        "reason": "WeiboClient.pong returned login=false",
    }
    assert "cookie" not in str(result).lower()


def test_login_pass_mock_result() -> None:
    assert login_check_result(True)["status"] == "LOGIN_PASS"


def test_login_check_passes_cookie_header_to_client() -> None:
    headers = build_weibo_headers(cookie_str="opaque-value", user_agent="test-agent")
    assert headers["Cookie"] == "opaque-value"
    assert headers["Referer"] == "https://m.weibo.cn"


def test_login_timeout_is_bounded() -> None:
    validate_login_check_options(300)
    for value in (0, 301):
        try:
            validate_login_check_options(value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid timeout was accepted")


def test_json_metrics_remain_available_for_offline_validation(tmp_path: Path) -> None:
    path = tmp_path / "offline.jsonl"
    path.write_text('{"mid":"1","text":"one"}\ninvalid\n', encoding="utf-8")
    assert compute_jsonl_metrics(path) == {
        "raw_count": 2,
        "valid_count": 1,
        "invalid_count": 1,
        "duplicate_count": 0,
        "output_count": 1,
    }
