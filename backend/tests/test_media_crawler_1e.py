"""Offline acceptance tests for Phase MediaCrawler-1E safeguards."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector
from scripts.check_mediacrawler_env import collect_checks
from scripts.run_mediacrawler_real_verify import (
    build_real_command,
    compute_field_coverage,
    compute_jsonl_metrics,
    validate_real_verify_options,
)


def test_environment_check_does_not_treat_missing_weibo_profile_as_real_login(
    tmp_path: Path, monkeypatch
) -> None:
    root = tmp_path / "MediaCrawler"
    root.mkdir()
    (root / "main.py").write_text("# entry\n", encoding="utf-8")
    browser_data = root / "browser_data"
    browser_data.mkdir()

    monkeypatch.setenv("MEDIA_CRAWLER_ROOT", str(root))
    monkeypatch.setenv("MEDIA_CRAWLER_ENTRY", str(root / "main.py"))
    monkeypatch.setenv("MEDIA_CRAWLER_PYTHON", sys.executable)
    monkeypatch.setenv("MEDIA_CRAWLER_BROWSER_DATA", str(browser_data))

    checks = collect_checks()

    assert all(check.ok for check in checks)
    assert not (browser_data / "wb_user_data_dir").exists()


def test_native_weibo_command_must_be_explicit() -> None:
    native_command = [
        sys.executable,
        "main.py",
        "--platform",
        "wb",
        "--lt",
        "qrcode",
        "--type",
        "search",
        "--keywords",
        "大厂县",
        "--get_comment",
        "false",
        "--get_sub_comment",
        "false",
        "--save_data_option",
        "jsonl",
        "--crawler_max_notes_count",
        "10",
        "--save_data_path",
        "runtime-output",
    ]

    assert build_real_command(
        native_command,
        root="unused",
        python_executable=sys.executable,
        entry="main.py",
    ) == native_command


def test_real_gate_rejects_without_operator_confirmation() -> None:
    try:
        validate_real_verify_options(
            confirm_real_run=False,
            max_items=10,
            timeout_seconds=300,
            enable_real_run=True,
        )
    except ValueError as exc:
        assert "confirm-real-run" in str(exc)
    else:
        raise AssertionError("real run was not rejected")


def test_real_sample_jsonl_metrics_and_contract(tmp_path: Path) -> None:
    path = tmp_path / "native-weibo.jsonl"
    rows = [
        {
            "mid": "1",
            "text": "sample content",
            "nickname": "author",
            "created_at": "2026-08-04T10:00:00+08:00",
            "url": "https://weibo.com/1",
            "like_count": "1.2万",
            "comments_count": "3",
            "repost_count": 4,
        },
        {"mid": "1", "text": "duplicate"},
        {"mid": "2", "text": ""},
        "not-json",
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    metrics = compute_jsonl_metrics(path)
    item = MediaCrawlerWeiboCollector._normalize_row(rows[0])

    assert metrics == {
        "raw_count": 4,
        "valid_count": 2,
        "invalid_count": 2,
        "duplicate_count": 1,
        "output_count": 1,
    }
    assert item is not None
    assert set(item) == {
        "title",
        "content",
        "source",
        "source_type",
        "url",
        "publish_time",
        "external_id",
        "author",
        "engagement",
    }
    assert item["engagement"] == {"likes": 12000, "comments": 3, "reposts": 4}
    assert compute_field_coverage([item])["content"] == 100.0

