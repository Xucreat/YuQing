"""Offline acceptance tests for native MediaCrawler protocol adaptation."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRealRunDisabledError,
    MediaCrawlerRunner,
)
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)
from scripts.check_mediacrawler_env import collect_checks


def test_native_command_builder_preserves_argument_order_and_defaults(tmp_path: Path) -> None:
    command = MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="D:/MediaCrawler/main.py",
        platform_spec=WEIBO_PLATFORM_SPEC,
    ).build(
        keywords=["大厂县", "大厂县", "河北"],
        max_items=10,
        output_dir=tmp_path / "output folder",
    )

    assert command == [
        "python.exe",
        "D:/MediaCrawler/main.py",
        "--platform",
        "wb",
        "--lt",
        "qrcode",
        "--type",
        "search",
        "--keywords",
        "大厂县,河北",
        "--get_comment",
        "false",
        "--get_sub_comment",
        "false",
        "--save_data_option",
        "jsonl",
        "--crawler_max_notes_count",
        "10",
        "--save_data_path",
        str((tmp_path / "output folder").resolve()),
    ]


def test_command_builder_does_not_shell_join_untrusted_values(tmp_path: Path) -> None:
    keyword = "keyword; whoami && echo injected"
    output_dir = tmp_path / "output & keep separate"
    command = MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="main.py",
        platform_spec=WEIBO_PLATFORM_SPEC,
    ).build(keywords=[keyword], max_items=1, output_dir=output_dir)

    assert command[command.index("--keywords") + 1] == keyword
    assert command[command.index("--save_data_path") + 1] == str(output_dir.resolve())
    assert "&&" not in " ".join(command[:2])


def test_runner_discovers_and_normalizes_native_jsonl(tmp_path: Path) -> None:
    output_dir = tmp_path / "run" / "output"
    code = (
        "import json, os; from pathlib import Path; "
        "p=Path(os.environ['MEDIA_CRAWLER_OUTPUT_DIR'])/'weibo'/'jsonl'; "
        "p.mkdir(parents=True); "
        "(p/'search_contents_test.jsonl').write_text(json.dumps({'mid':'1','text':'native'}), encoding='utf-8')"
    )
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[sys.executable, "-c", code],
        mock_command=True,
        enable_real_run=True,
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    )

    result = runner.run(
        ["大厂县"],
        output_dir=output_dir,
        timeout_seconds=30,
        max_items=1,
        native_output_path=output_dir,
    )

    assert result.output_path.is_file()
    assert result.native_output_path is not None
    assert result.native_output_path.name == "search_contents_test.jsonl"
    assert result.output_path.read_text(encoding="utf-8").strip()


def test_weibo_profile_check_reports_only_safe_metadata(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "MediaCrawler"
    browser_data = root / "browser_data"
    profile = browser_data / "wb_user_data_dir"
    profile.mkdir(parents=True)
    (profile / "state.db").write_bytes(b"state")
    (root / "main.py").write_text("# entry\n", encoding="utf-8")
    monkeypatch.setenv("MEDIA_CRAWLER_ROOT", str(root))
    monkeypatch.setenv("MEDIA_CRAWLER_ENTRY", str(root / "main.py"))
    monkeypatch.setenv("MEDIA_CRAWLER_PYTHON", sys.executable)
    monkeypatch.setenv("MEDIA_CRAWLER_BROWSER_DATA", str(browser_data))

    checks = collect_checks(require_weibo_profile=True)
    profile_check = next(check for check in checks if check.name == "MEDIA_CRAWLER_WEIBO_PROFILE")

    assert profile_check.ok
    assert profile_check.detail == "exists=true file_count=1 size=5"
    assert "state" not in profile_check.detail
    assert "cookie" not in profile_check.detail.lower()


def test_missing_weibo_profile_blocks_native_environment(tmp_path: Path, monkeypatch) -> None:
    browser_data = tmp_path / "browser_data"
    browser_data.mkdir()
    monkeypatch.setenv("MEDIA_CRAWLER_BROWSER_DATA", str(browser_data))

    checks = collect_checks(require_weibo_profile=True)
    profile_check = next(check for check in checks if check.name == "MEDIA_CRAWLER_WEIBO_PROFILE")

    assert not profile_check.ok
    assert profile_check.detail == "exists=false file_count=0 size=0"


def test_real_gate_stops_before_subprocess(tmp_path: Path, monkeypatch) -> None:
    called = False

    def forbidden_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("subprocess must not run when real gate is closed")

    monkeypatch.setattr("app.collectors.mediacrawler_runner.subprocess.run", forbidden_run)
    runner = MediaCrawlerRunner(
        root=tmp_path,
        command=[sys.executable, "-c", "print('blocked')"],
        mock_command=False,
        enable_real_run=False,
        platform_spec=WEIBO_PLATFORM_SPEC,
        source_key=WEIBO_SOURCE_KEY,
    )

    with pytest.raises(MediaCrawlerRealRunDisabledError):
        runner.run(["大厂县"], timeout_seconds=30)

    assert not called
