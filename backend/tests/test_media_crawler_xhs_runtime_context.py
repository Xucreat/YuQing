"""Platform-2-E1 runtime context separation contracts."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path

from app.collectors.media_crawler_platform_collector import (
    MediaCrawlerPlatformCollector,
)
from app.collectors.mediacrawler_platform import (
    WEIBO_PLATFORM_SPEC,
    XHS_PLATFORM_SPEC,
)
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_COMPATIBILITY_POLICY,
    WEIBO_SOURCE_KEY,
)


def _write_fake_checkout(checkout_root: Path) -> Path:
    (checkout_root / "libs").mkdir(parents=True)
    (checkout_root / "libs" / "__init__.py").write_text("", encoding="utf-8")
    (checkout_root / "libs" / "relative_contract.py").write_text(
        "VALUE = 'checkout-relative-import-ok'\n",
        encoding="utf-8",
    )
    entry = checkout_root / "main.py"
    entry.write_text(
        """
import json
import os
from pathlib import Path

from libs.relative_contract import VALUE

checkout = Path(os.environ["EXPECTED_CHECKOUT"]).resolve()
if Path.cwd().resolve() != checkout:
    raise SystemExit(f"wrong cwd: {Path.cwd()}")

profile = Path(os.environ["MEDIA_CRAWLER_PROFILE_NAME"])
if not profile.joinpath("profile-marker.txt").is_file():
    raise SystemExit("isolated profile marker is missing")

output_root = Path(os.environ["MEDIA_CRAWLER_OUTPUT_DIR"])
(output_root / "cwd.txt").write_text(str(Path.cwd()), encoding="utf-8")
native = output_root / "xhs" / "jsonl"
native.mkdir(parents=True, exist_ok=True)
(native / "search_contents_context.jsonl").write_text(
    json.dumps(
        {
            "note_id": VALUE,
            "title": "runtime context",
            "desc": "checkout and profile are isolated",
            "nickname": "offline user",
            "note_url": "https://example.invalid/xhs/runtime-context",
            "time": 1722470400000,
            "liked_count": "1",
        },
        ensure_ascii=False,
    ) + "\\n",
    encoding="utf-8",
)
""".lstrip(),
        encoding="utf-8",
    )
    return entry


def test_xhs_checkout_profile_output_contexts_are_separate(tmp_path: Path) -> None:
    checkout_root = tmp_path / "checkout"
    output_root = tmp_path / "output"
    profile_root = tmp_path / "profiles"
    entry = _write_fake_checkout(checkout_root)
    application_profile = (
        profile_root / "xiaohongshu" / "context-source" / "manual"
    )
    application_profile.mkdir(parents=True)
    (application_profile / "profile-marker.txt").write_text(
        "context-profile",
        encoding="utf-8",
    )

    spec = replace(XHS_PLATFORM_SPEC, allow_real_collection=True)
    factory = MediaCrawlerRuntimeFactory(
        source_key="context-source",
        platform_spec=spec,
        root=output_root,
        checkout_root=checkout_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        login_type="qrcode",
        real_run_gate=True,
    )
    runner, _, config = factory.create_runner("manual", mock_command=False)

    previous = os.environ.get("EXPECTED_CHECKOUT")
    os.environ["EXPECTED_CHECKOUT"] = str(checkout_root.resolve())
    try:
        result = runner.run(
            ["测试"],
            max_items=1,
            timeout_seconds=10,
        )
    finally:
        if previous is None:
            os.environ.pop("EXPECTED_CHECKOUT", None)
        else:
            os.environ["EXPECTED_CHECKOUT"] = previous

    native_root = (
        output_root
        / "upstream_profiles"
        / "xiaohongshu"
        / "context-source"
        / "manual"
    )
    native_profile = native_root / "browser_data" / "xhs_user_data_dir"

    assert config.checkout_root == checkout_root.resolve()
    assert config.profile_root == profile_root.resolve()
    assert config.output_root == output_root.resolve()
    assert runner.command_cwd == checkout_root.resolve()
    assert runner.output_root == output_root
    assert Path(runner.profile_name) == native_profile.resolve()
    assert native_profile.joinpath("profile-marker.txt").read_text(
        encoding="utf-8"
    ) == "context-profile"
    assert (result.run_dir / "output" / "cwd.txt").read_text(
        encoding="utf-8"
    ) == str(checkout_root.resolve())
    assert result.native_output_path is not None
    assert result.native_output_path.parts[-3:-1] == ("xhs", "jsonl")
    assert result.output_path.is_file()

    item = MediaCrawlerPlatformCollector(
        platform_spec=spec,
        data_source_key="context-source",
        fixture_path=result.output_path,
    ).normalizer.normalize(
        json.loads(result.output_path.read_text(encoding="utf-8").strip())
    )
    assert item is not None
    assert item["external_id"] == "checkout-relative-import-ok"
    assert item["source"] == "xiaohongshu"

    assert runner.runtime_profile_adapter is not None
    assert runner.runtime_profile_binding is not None
    runner.runtime_profile_adapter.cleanup(runner.runtime_profile_binding)
    assert not native_root.exists()
    assert application_profile.is_dir()


def test_weibo_legacy_runtime_keeps_checkout_and_profile_contract(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "runtime"
    checkout_root = tmp_path / "weibo-checkout"
    profile_root = tmp_path / "profiles"
    entry = checkout_root / "main.py"
    checkout_root.mkdir(parents=True)
    entry.write_text("# legacy entry\n", encoding="utf-8")
    legacy_profile = profile_root / "manual"
    legacy_profile.mkdir(parents=True)

    factory = MediaCrawlerRuntimeFactory(
        source_key=WEIBO_SOURCE_KEY,
        platform_spec=WEIBO_PLATFORM_SPEC,
        compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
        root=output_root,
        checkout_root=checkout_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        real_run_gate=False,
    )
    runner, _, config = factory.create_runner("manual", mock_command=True)
    runner.command_factory(["廊坊"], 1, output_root / "run" / "output")  # type: ignore[union-attr]

    assert config.checkout_root == checkout_root.resolve()
    assert config.output_root == output_root.resolve()
    assert config.profile_path == legacy_profile.resolve()
    assert runner.command_cwd == checkout_root.resolve()
    assert Path(runner.browser_data) == legacy_profile.resolve()
    assert Path(runner.profile_name) == legacy_profile.resolve()
    assert runner.platform_spec is WEIBO_PLATFORM_SPEC


def test_xhs_checkout_root_auto_derived_from_entry_parent(tmp_path: Path) -> None:
    """Production regression: when checkout_root is not configured, the runtime
    must derive the subprocess cwd from the entry's parent (the upstream
    MediaCrawler checkout) so checkout-relative imports like libs/douyin.js
    resolve. The native profile lives elsewhere and must not become the cwd."""

    output_root = tmp_path / "output"
    profile_root = tmp_path / "profiles"
    checkout_root = tmp_path / "upstream_checkout"
    entry = _write_fake_checkout(checkout_root)
    application_profile = (
        profile_root / "xiaohongshu" / "auto-source" / "manual"
    )
    application_profile.mkdir(parents=True)
    (application_profile / "profile-marker.txt").write_text(
        "auto-profile", encoding="utf-8"
    )

    spec = replace(XHS_PLATFORM_SPEC, allow_real_collection=True)
    # NOTE: checkout_root is deliberately NOT passed here.
    factory = MediaCrawlerRuntimeFactory(
        source_key="auto-source",
        platform_spec=spec,
        root=output_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        login_type="qrcode",
        real_run_gate=True,
    )
    runner, _, config = factory.create_runner("manual", mock_command=False)

    previous = os.environ.get("EXPECTED_CHECKOUT")
    os.environ["EXPECTED_CHECKOUT"] = str(checkout_root.resolve())
    try:
        result = runner.run(["测试"], max_items=1, timeout_seconds=10)
    finally:
        if previous is None:
            os.environ.pop("EXPECTED_CHECKOUT", None)
        else:
            os.environ["EXPECTED_CHECKOUT"] = previous

    native_root = (
        output_root
        / "upstream_profiles"
        / "xiaohongshu"
        / "auto-source"
        / "manual"
    )
    native_profile = native_root / "browser_data" / "xhs_user_data_dir"

    # Auto-derived cwd must be the upstream checkout, never the profile dir.
    assert config.checkout_root == checkout_root.resolve()
    assert runner.command_cwd == checkout_root.resolve()
    assert runner.command_cwd != native_root.resolve()
    # Profile isolation is preserved in a separate directory.
    assert Path(runner.profile_name) == native_profile.resolve()
    assert native_profile.joinpath("profile-marker.txt").read_text(
        encoding="utf-8"
    ) == "auto-profile"
    # Checkout-relative import succeeded and produced the native artifact.
    assert result.native_output_path is not None
    assert result.native_output_path.parts[-3:-1] == ("xhs", "jsonl")
    assert result.output_path.is_file()


def test_xhs_profile_adapter_does_not_own_subprocess_cwd(tmp_path: Path) -> None:
    """The profile adapter only creates/manages the browser/session profile; the
    subprocess cwd is owned by the runtime contract and must remain the checkout
    root regardless of where the isolated native profile is materialized."""

    output_root = tmp_path / "output"
    profile_root = tmp_path / "profiles"
    checkout_root = tmp_path / "checkout"
    entry = _write_fake_checkout(checkout_root)
    application_profile = profile_root / "xiaohongshu" / "owner-source" / "manual"
    application_profile.mkdir(parents=True)
    (application_profile / "profile-marker.txt").write_text(
        "owner-profile", encoding="utf-8"
    )

    spec = replace(XHS_PLATFORM_SPEC, allow_real_collection=True)
    factory = MediaCrawlerRuntimeFactory(
        source_key="owner-source",
        platform_spec=spec,
        root=output_root,
        checkout_root=checkout_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        login_type="qrcode",
        real_run_gate=True,
    )
    runner, _, config = factory.create_runner("manual", mock_command=False)
    # Before any run the adapter/binding are not yet materialized (lazy). The
    # subprocess cwd is fixed by the runtime contract, independent of the profile.
    assert runner.command_cwd == config.checkout_root == checkout_root.resolve()
    assert Path(runner.profile_name).resolve() != checkout_root.resolve()

    previous = os.environ.get("EXPECTED_CHECKOUT")
    os.environ["EXPECTED_CHECKOUT"] = str(checkout_root.resolve())
    try:
        result = runner.run(["测试"], max_items=1, timeout_seconds=10)
    finally:
        if previous is None:
            os.environ.pop("EXPECTED_CHECKOUT", None)
        else:
            os.environ["EXPECTED_CHECKOUT"] = previous

    adapter = runner.runtime_profile_adapter
    binding = runner.runtime_profile_binding
    assert adapter is not None
    assert binding is not None
    # The adapter owns only the profile lifecycle; it never changes the runner's
    # command cwd, which remains the upstream checkout root.
    assert runner.command_cwd == config.checkout_root == checkout_root.resolve()
    assert result.output_path.is_file()
    adapter.cleanup(binding)

