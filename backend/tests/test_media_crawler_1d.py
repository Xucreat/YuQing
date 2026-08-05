"""Offline tests for Phase MediaCrawler-1D environment and sample validation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.check_mediacrawler_env import collect_checks
from scripts.run_mediacrawler_real_verify import (
    build_real_command,
    compute_field_coverage,
    compute_jsonl_metrics,
)
from app.collectors.media_crawler_weibo_collector import MediaCrawlerWeiboCollector


def test_real_environment_configuration_detection(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "MediaCrawler"
    root.mkdir()
    (root / "main.py").write_text("# controlled entry\n", encoding="utf-8")
    browser_data = tmp_path / "browser-data"
    browser_data.mkdir()
    (browser_data / "state.db").write_bytes(b"state")
    monkeypatch.setenv("MEDIA_CRAWLER_ROOT", str(root))
    monkeypatch.setenv("MEDIA_CRAWLER_ENTRY", str(root / "main.py"))
    monkeypatch.setenv("MEDIA_CRAWLER_PYTHON", sys.executable)
    monkeypatch.setenv("MEDIA_CRAWLER_BROWSER_DATA", str(browser_data))

    checks = collect_checks()

    assert all(check.ok for check in checks)
    assert str(browser_data) not in " ".join(check.detail for check in checks)


def test_real_command_resolution(tmp_path: Path) -> None:
    root = tmp_path / "crawler"
    root.mkdir()
    entry = root / "main.py"
    entry.write_text("# entry\n", encoding="utf-8")

    assert build_real_command(
        None, root=str(root), python_executable=sys.executable, entry="main.py"
    ) == [sys.executable, str(entry)]
    assert build_real_command(
        ["custom-python", "crawler.py"],
        root=str(root),
        python_executable=sys.executable,
        entry="main.py",
    ) == ["custom-python", "crawler.py"]


def test_real_sample_shape_is_normalized() -> None:
    row = {
        "mid": "real-sample-1",
        "text": "真实样本字段协议测试。",
        "nickname": "样本账号",
        "created_at": "2026-08-04T10:00:00+08:00",
        "url": "https://weibo.com/real-sample-1",
        "like_count": "1.2万",
        "comments_count": "3",
        "repost_count": 4,
    }

    item = MediaCrawlerWeiboCollector._normalize_row(row)

    assert item is not None
    assert item["external_id"] == "real-sample-1"
    assert item["content"] == "真实样本字段协议测试。"
    assert item["url"] == "https://weibo.com/real-sample-1"
    assert item["engagement"] == {"likes": 12000, "comments": 3, "reposts": 4}


def test_field_coverage_includes_url() -> None:
    items = [
        {
            "content": "a",
            "author": "u",
            "publish_time": "t",
            "external_id": "1",
            "url": "https://example/1",
            "engagement": {},
        },
        {
            "content": "b",
            "author": "",
            "publish_time": None,
            "external_id": "",
            "url": "",
            "engagement": {},
        },
    ]

    coverage = compute_field_coverage(items)

    assert coverage == {
        "content": 100.0,
        "author": 50.0,
        "publish_time": 50.0,
        "external_id": 50.0,
        "url": 50.0,
        "engagement": 100.0,
    }


def test_anomalous_jsonl_is_counted_without_crashing(tmp_path: Path) -> None:
    path = tmp_path / "anomalous.jsonl"
    rows = [
        {"content": "valid", "mid": "1", "url": "https://example/1"},
        {"content": "", "mid": "2"},
        {"content": "no id", "created_at": "not-a-time"},
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        + "\nnot-json\n",
        encoding="utf-8",
    )

    metrics = compute_jsonl_metrics(path)

    assert metrics["raw_count"] == 4
    assert metrics["valid_count"] == 2
    assert metrics["invalid_count"] == 2
    assert metrics["output_count"] == 2
