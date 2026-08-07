"""Offline Platform-2-C2 contracts for XHS modes and profile adaptation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.collectors.media_crawler_platform_collector import (
    MediaCrawlerPlatformCollector,
)
from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_platform import (
    MediaCrawlerConfigurationError,
    XHS_PLATFORM_SPEC,
    WEIBO_PLATFORM_SPEC,
    get_mediacrawler_platform_spec,
)
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRealRunDisabledError,
    MediaCrawlerRunner,
)
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from app.core.config import settings


def _settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    real_run_gate: bool = True,
) -> tuple[Path, Path]:
    runtime_root = tmp_path / "runtime"
    entry = runtime_root / "main.py"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("# offline fake entry\n", encoding="utf-8")
    monkeypatch.setattr(settings, "media_crawler_root", str(runtime_root))
    monkeypatch.setattr(settings, "media_crawler_profile_root", str(tmp_path / "profiles"))
    monkeypatch.setattr(settings, "media_crawler_entry", str(entry))
    monkeypatch.setattr(settings, "media_crawler_python", sys.executable)
    monkeypatch.setattr(settings, "media_crawler_real_run_gate", real_run_gate)
    monkeypatch.setattr(settings, "media_crawler_scheduler_login_type", "cookie")
    return runtime_root, tmp_path / "profiles"


def _profile(profile_root: Path, platform: str, source: str, trigger: str, marker: str) -> Path:
    path = profile_root / platform / source / trigger
    path.mkdir(parents=True, exist_ok=True)
    (path / "profile-marker.txt").write_text(marker, encoding="utf-8")
    return path


def _argv_mode(mode: str, tmp_path: Path, *, login_type: str = "qrcode") -> list[str]:
    return MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="main.py",
        platform_spec=XHS_PLATFORM_SPEC,
    ).build(
        keywords=["测试"],
        max_items=2,
        output_dir=tmp_path / mode,
        crawler_type=mode,
        login_type=login_type,
    )


def test_xhs_platform_spec_and_all_native_modes_are_verified() -> None:
    spec = get_mediacrawler_platform_spec("xiaohongshu")

    assert spec is XHS_PLATFORM_SPEC
    assert spec.cli_code == "xhs"
    assert spec.crawler_type == "search"
    assert spec.supported_crawler_types == ("search", "detail", "creator")
    assert spec.default_crawler_type == "search"
    assert spec.native_output_parts == ("xhs", "jsonl")
    assert spec.supported_login_types == frozenset({"qrcode", "phone", "cookie"})
    assert spec.allow_real_collection is True


def test_xhs_argv_snapshot_is_spec_driven_for_search_detail_creator(tmp_path: Path) -> None:
    expected = {
        "search": ("xhs", "search", "qrcode"),
        "detail": ("xhs", "detail", "phone"),
        "creator": ("xhs", "creator", "cookie"),
    }

    for mode, (platform, crawler_type, login_type) in expected.items():
        argv = _argv_mode(mode, tmp_path, login_type=login_type)
        assert argv[argv.index("--platform") + 1] == platform
        assert argv[argv.index("--type") + 1] == crawler_type
        assert argv[argv.index("--lt") + 1] == login_type
        assert argv[argv.index("--save_data_option") + 1] == "jsonl"
        assert all("weibo" not in part.lower() and part.lower() != "wb" for part in argv)


def test_xhs_unknown_mode_fails_closed_and_weibo_modes_remain_unchanged(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="invalid MediaCrawler crawler_type"):
        _argv_mode("comments", tmp_path)

    weibo = MediaCrawlerCommandBuilder(
        python_executable="python.exe",
        entry="main.py",
        platform_spec=WEIBO_PLATFORM_SPEC,
    ).build(
        keywords=["廊坊"],
        max_items=1,
        output_dir=tmp_path / "weibo",
    )
    assert weibo[weibo.index("--platform") + 1] == "wb"
    assert weibo[weibo.index("--type") + 1] == "search"


def test_profile_adapter_isolates_platform_source_and_trigger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, profile_root = _settings(monkeypatch, tmp_path)
    _profile(profile_root, "xiaohongshu", "sourceA", "manual", "A-manual")
    _profile(profile_root, "xiaohongshu", "sourceA", "scheduler", "A-scheduler")
    _profile(profile_root, "xiaohongshu", "sourceB", "manual", "B-manual")

    bindings: dict[str, tuple[Path, Path, Path]] = {}
    for source, trigger in (("sourceA", "manual"), ("sourceA", "scheduler"), ("sourceB", "manual")):
        factory = MediaCrawlerRuntimeFactory(
            source_key=source,
            platform_spec=XHS_PLATFORM_SPEC,
        )
        runner, _, config = factory.create_runner(trigger, mock_command=True)
        runner.command_factory(["测试"], 1, tmp_path / "output")  # type: ignore[union-attr]
        native_root = runtime_root / "upstream_profiles" / "xiaohongshu" / source / trigger
        native_profile = native_root / "browser_data" / "xhs_user_data_dir"
        bindings[f"{source}/{trigger}"] = (
            Path(runner.command_cwd),
            Path(runner.browser_data),
            native_profile,
        )
        assert config.profile_path == (
            profile_root / "xiaohongshu" / source / trigger
        ).resolve()
        assert Path(runner.command_cwd) == runtime_root.resolve()
        assert Path(runner.browser_data) == native_profile.resolve()
        assert native_profile.joinpath("profile-marker.txt").is_file()

    assert bindings["sourceA/manual"][2].joinpath("profile-marker.txt").read_text(
        encoding="utf-8"
    ) != bindings["sourceB/manual"][2].joinpath("profile-marker.txt").read_text(
        encoding="utf-8"
    )
    assert bindings["sourceA/manual"][2] != bindings["sourceA/scheduler"][2]


def test_fake_upstream_reads_xhs_native_profile_and_discovers_native_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, profile_root = _settings(monkeypatch, tmp_path)
    source_profile = _profile(
        profile_root,
        "xiaohongshu",
        "sourceA",
        "manual",
        "fake-upstream-profile",
    )
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        native_profile = Path(kwargs["env"]["MEDIA_CRAWLER_PROFILE_NAME"])
        assert native_profile.joinpath("profile-marker.txt").read_text(
            encoding="utf-8"
        ) == "fake-upstream-profile"
        native_output = (
            Path(kwargs["env"]["MEDIA_CRAWLER_OUTPUT_DIR"])
            / "xhs"
            / "jsonl"
            / "search_contents_20260806.jsonl"
        )
        native_output.parent.mkdir(parents=True, exist_ok=True)
        native_output.write_text(
            json.dumps(
                {
                    "note_id": "xhs-runtime-1",
                    "title": "离线运行契约",
                    "desc": "只验证 native profile 和 output discovery",
                    "nickname": "测试用户",
                    "time": 1722470400000,
                    "liked_count": "1.2万",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "app.collectors.mediacrawler_runner.subprocess.run",
        fake_run,
    )
    factory = MediaCrawlerRuntimeFactory(
        source_key="sourceA",
        platform_spec=XHS_PLATFORM_SPEC,
    )
    runner, _, _ = factory.create_runner("manual", mock_command=True)
    result = runner.run(["测试"], max_items=10, timeout_seconds=5)
    item = MediaCrawlerPlatformCollector(
        platform_spec=XHS_PLATFORM_SPEC,
        data_source_key="sourceA",
        fixture_path=result.output_path,
    ).normalizer.normalize(
        json.loads(result.output_path.read_text(encoding="utf-8").strip())
    )

    assert captured["cwd"] == str(runtime_root.resolve())
    assert item is not None
    assert item["external_id"] == "xhs-runtime-1"
    assert result.native_output_path is not None
    assert result.native_output_path.parts[-3:-1] == ("xhs", "jsonl")
    assert runner.runtime_profile_binding is not None
    assert runner.runtime_profile_adapter is not None
    runner.runtime_profile_adapter.cleanup(runner.runtime_profile_binding)
    assert not (
        runtime_root / "upstream_profiles" / "xiaohongshu" / "sourceA" / "manual"
    ).exists()
    assert source_profile.is_dir()


def test_xhs_failure_retains_native_profile_and_gate_blocks_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_root, profile_root = _settings(monkeypatch, tmp_path, real_run_gate=False)
    _profile(profile_root, "xiaohongshu", "sourceA", "manual", "retained")
    called = False

    def forbidden_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("offline gate test must not start a subprocess")

    monkeypatch.setattr(
        "app.collectors.mediacrawler_runner.subprocess.run",
        forbidden_run,
    )
    runner, _, _ = MediaCrawlerRuntimeFactory(
        source_key="sourceA",
        platform_spec=XHS_PLATFORM_SPEC,
    ).create_runner("manual", mock_command=False)

    with pytest.raises(MediaCrawlerRealRunDisabledError):
        runner.run(["测试"], max_items=1, timeout_seconds=5)

    assert called is False
    assert (
        runtime_root
        / "upstream_profiles"
        / "xiaohongshu"
        / "sourceA"
        / "manual"
        / "browser_data"
        / "xhs_user_data_dir"
    ).is_dir()


def test_xhs_fixture_and_normalized_output_have_no_sensitive_fields() -> None:
    fixture = (
        Path(__file__).parent
        / "fixtures"
        / "media_crawler"
        / "xiaohongshu.jsonl"
    )
    raw_text = fixture.read_text(encoding="utf-8").lower()
    for forbidden in ("xsec_token", "cookie", "access_token", "browser state"):
        assert forbidden not in raw_text

    row = json.loads(fixture.read_text(encoding="utf-8").strip())
    normalized = MediaCrawlerPlatformCollector(
        platform_spec=XHS_PLATFORM_SPEC,
        data_source_key="sensitive-field-test",
        fixture_path=fixture,
    ).normalizer.normalize(row)
    assert normalized is not None
    assert not any(
        key in normalized
        for key in ("xsec_token", "cookie", "access_token", "browser_state")
    )


def test_xhs_spec_allows_runner_when_global_gate_is_open(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "started.txt"
    runner = MediaCrawlerRunner(
        root=tmp_path / "runtime",
        command=[
            sys.executable,
            "-c",
            "import os; "
            "from pathlib import Path; "
            f"Path({str(marker)!r}).write_text('started'); "
            "Path(os.environ['MEDIA_CRAWLER_OUTPUT']).write_text('{}\\n')",
        ],
        platform_spec=XHS_PLATFORM_SPEC,
        source_key="xhs_source",
        mock_command=False,
        enable_real_run=True,
    )

    result = runner.run(["测试"], max_items=1, timeout_seconds=5)

    assert result.exit_code == 0
    assert marker.read_text(encoding="utf-8") == "started"
