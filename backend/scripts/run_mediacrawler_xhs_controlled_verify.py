"""Dry-run and sandbox-only XHS MediaCrawler contract verification.

This harness never accepts a real MediaCrawler entry point. Without
``--allow-controlled-run`` it only builds argv and profile/artifact plans.
With the flag it starts a temporary fake CLI that writes sanitized native
JSONL, exercising the application runtime boundary without network, browser,
credentials, Scheduler, or database writes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors import data_source_repository, registry  # noqa: E402
from app.collectors.media_crawler_platform_collector import (  # noqa: E402
    MediaCrawlerPlatformCollector,
)
from app.collectors.mediacrawler_batch import MediaCrawlerBatchLocator  # noqa: E402
from app.collectors.mediacrawler_command_builder import (  # noqa: E402
    MediaCrawlerCommandBuilder,
)
from app.collectors.mediacrawler_platform import (  # noqa: E402
    XHS_PLATFORM_SPEC,
    get_mediacrawler_platform_spec,
)
from app.collectors.mediacrawler_profile_adapter import (  # noqa: E402
    MediaCrawlerProfileAdapter,
)
from app.collectors.mediacrawler_runtime import (  # noqa: E402
    MediaCrawlerRuntimeFactory,
)

CONTROLLED_SOURCE_KEY = "xhs_controlled_verify"
ALT_SOURCE_KEY = "xhs_controlled_verify_alt"
MAX_ITEMS_LIMIT = 20
MAX_TIMEOUT_SECONDS = 120

_FAKE_CLI = r"""
import argparse
import json
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--platform", required=True)
parser.add_argument("--lt", required=True)
parser.add_argument("--type", required=True)
parser.add_argument("--keywords", required=True)
parser.add_argument("--save_data_option", required=True)
parser.add_argument("--save_data_path", required=True)
parser.add_argument("--crawler_max_notes_count", required=True)
parser.add_argument("--get_comment", required=True)
parser.add_argument("--get_sub_comment", required=True)
args = parser.parse_args()

expected_platform = os.environ["MEDIACRAWLER_EXPECTED_PLATFORM"]
native_parts = tuple(json.loads(os.environ["MEDIACRAWLER_NATIVE_OUTPUT_PARTS"]))
if args.platform != expected_platform:
    raise SystemExit("unexpected platform")
if args.save_data_option != "jsonl":
    raise SystemExit("unexpected output option")

native_root = Path(args.save_data_path).joinpath(*native_parts)
native_root.mkdir(parents=True, exist_ok=True)
content_path = native_root / f"{args.type}_contents_controlled.jsonl"
content = {
    "note_id": f"controlled-{args.type}-001",
    "title": "受控运行验证",
    "desc": "只验证隔离 runtime 到 native JSONL 的离线闭环。",
    "nickname": "脱敏测试用户",
    "note_url": "https://example.invalid/xhs/controlled-001",
    "time": 1722470400000,
    "liked_count": "1.2万",
    "comment_count": "8",
    "collected_count": "3千",
    "share_count": "4",
}
content_path.write_text(
    json.dumps(content, ensure_ascii=False) + "\n",
    encoding="utf-8",
)

if args.get_comment == "true":
    comment_path = native_root / f"{args.type}_comments_controlled.jsonl"
    comment = {
        "comment_id": "controlled-comment-001",
        "note_id": content["note_id"],
        "content": "脱敏评论",
        "nickname": "脱敏评论用户",
        "create_time": 1722470400000,
    }
    comment_path.write_text(
        json.dumps(comment, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
"""


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "as_dict"):
        return value.as_dict()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=_json_default))


def _profile_template(path: Path, label: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "controlled-profile-marker.txt").write_text(label, encoding="utf-8")


@contextmanager
def _controlled_datasource_fixture(row: dict[str, Any]) -> Iterator[None]:
    original = data_source_repository.enabled_sources
    data_source_repository.enabled_sources = lambda _db: [row]
    try:
        yield
    finally:
        data_source_repository.enabled_sources = original


class _FixedRuntimeFactory:
    """Expose one prebuilt sandbox runner through the collector contract."""

    def __init__(self, runner, lock, platform_spec):
        self.runner = runner
        self.lock = lock
        self.platform_spec = platform_spec

    def create_runner(self, *_args, **_kwargs):
        return self.runner, self.lock, self.runner.runtime_config


def build_datasource_fixture(
    *,
    source_key: str,
    crawler_type: str,
    login_type: str,
    keywords: list[str],
    max_items: int,
    comments: bool,
) -> dict[str, Any]:
    """Build an in-memory DataSource-shaped fixture; never writes a DB row."""

    return {
        "key": source_key,
        "name": "XHS controlled verification",
        "class_path": (
            "app.collectors.media_crawler_platform_collector."
            "MediaCrawlerPlatformCollector"
        ),
        "scope_region_codes": "",
        "config_json": {
            "collector": "mediacrawler",
            "platform": XHS_PLATFORM_SPEC.platform,
            "crawler_type": crawler_type,
            "login_type": login_type,
            "keywords": keywords,
            "max_items": max_items,
            "comments": {"enabled": comments, "sub_comments": False},
        },
    }


def _isolated_factory(
    *,
    runtime_root: Path,
    profile_root: Path,
    entry: Path,
    source_key: str,
    login_type: str,
) -> MediaCrawlerRuntimeFactory:
    return MediaCrawlerRuntimeFactory(
        source_key=source_key,
        platform_spec=XHS_PLATFORM_SPEC,
        root=runtime_root,
        profile_root=profile_root,
        python_executable=sys.executable,
        entry=entry,
        timeout_seconds=30,
        login_type=login_type,
        scheduler_login_type="cookie",
        real_run_gate=False,
    )


def _profile_audit(
    *,
    runtime_root: Path,
    profile_root: Path,
    entry: Path,
    source_key: str,
    login_type: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for current_source_key, trigger in (
        (source_key, "manual"),
        (source_key, "scheduler"),
        (ALT_SOURCE_KEY, "manual"),
    ):
        factory = _isolated_factory(
            runtime_root=runtime_root,
            profile_root=profile_root,
            entry=entry,
            source_key=current_source_key,
            login_type=login_type,
        )
        config = factory.config(trigger)
        adapter = MediaCrawlerProfileAdapter(
            runtime_root=runtime_root,
            platform_spec=XHS_PLATFORM_SPEC,
            source_key=current_source_key,
            trigger_type=trigger,
            command_cwd=runtime_root,
        )
        binding = adapter.resolve_upstream_profile(
            XHS_PLATFORM_SPEC,
            config.profile_path,
        )
        result.append(
            {
                "source_key": current_source_key,
                "trigger": trigger,
                "application_profile": config.profile_path,
                "upstream_root": binding.upstream_root,
                "upstream_profile": binding.upstream_profile,
                "created_time": (
                    datetime.fromtimestamp(
                        config.profile_path.stat().st_mtime,
                        tz=timezone.utc,
                    )
                    if config.profile_path.exists()
                    else None
                ),
                "cleanup_status": "not_executed",
            }
        )
    return result


def _build_fake_entry(path: Path) -> None:
    path.write_text(_FAKE_CLI.lstrip(), encoding="utf-8")


def _validate_args(args: argparse.Namespace) -> tuple[Any, str, str]:
    spec = get_mediacrawler_platform_spec("xiaohongshu")
    crawler_type = spec.validate_crawler_type(args.crawler_type)
    login_type = spec.validate_login_type(args.login_type)
    if args.max_items < 1 or args.max_items > MAX_ITEMS_LIMIT:
        raise ValueError(f"max_items must be between 1 and {MAX_ITEMS_LIMIT}")
    if args.timeout_seconds < 1 or args.timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}"
        )
    if not args.keywords:
        raise ValueError("at least one keyword is required")
    return spec, crawler_type, login_type


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="XHS dry-run and sandbox-only controlled runtime verification"
    )
    parser.add_argument(
        "--allow-controlled-run",
        action="store_true",
        help="allow the temporary fake CLI subprocess; never enables real collection",
    )
    parser.add_argument("--crawler-type", default="search")
    parser.add_argument("--login-type", default="qrcode")
    parser.add_argument("--keywords", nargs="+", default=["controlled"])
    parser.add_argument("--max-items", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--comments",
        action="store_true",
        help="ask the fake CLI to create a sanitized comments artifact",
    )
    args = parser.parse_args(argv)

    try:
        spec, crawler_type, login_type = _validate_args(args)
    except (ValueError, KeyError) as exc:
        _emit({"status": "BLOCKED", "reason": str(exc)})
        return 3

    started = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="mediacrawler-xhs-controlled-") as temp:
        temp_root = Path(temp)
        runtime_root = temp_root / "runtime"
        profile_root = temp_root / "profiles"
        entry = temp_root / "fake_mediacrawler.py"
        _build_fake_entry(entry)
        for source_key, trigger, label in (
            (CONTROLLED_SOURCE_KEY, "manual", "manual"),
            (CONTROLLED_SOURCE_KEY, "scheduler", "scheduler"),
            (ALT_SOURCE_KEY, "manual", "alternate-source"),
        ):
            _profile_template(
                profile_root / spec.platform / source_key / trigger,
                label,
            )

        source_fixture = build_datasource_fixture(
            source_key=CONTROLLED_SOURCE_KEY,
            crawler_type=crawler_type,
            login_type=login_type,
            keywords=list(args.keywords),
            max_items=args.max_items,
            comments=args.comments,
        )
        try:
            with _controlled_datasource_fixture(source_fixture):
                resolved = registry.resolve_collectors_verbose(
                    object(),
                    include_data_source_keys=[CONTROLLED_SOURCE_KEY],
                )
        except Exception as exc:
            _emit({"status": "BLOCKED", "reason": f"registry fixture failed: {exc}"})
            return 3
        if resolved.failures or len(resolved.collectors) != 1:
            _emit(
                {
                    "status": "BLOCKED",
                    "reason": "controlled DataSource fixture did not resolve",
                    "failures": resolved.failures,
                }
            )
            return 3

        factory = _isolated_factory(
            runtime_root=runtime_root,
            profile_root=profile_root,
            entry=entry,
            source_key=CONTROLLED_SOURCE_KEY,
            login_type=login_type,
        )
        runtime_config = factory.config("manual")
        runner, lock, _ = factory.create_runner("manual", mock_command=True)
        original_command_factory = runner.command_factory
        builder = MediaCrawlerCommandBuilder(
            python_executable=sys.executable,
            entry=str(entry),
            platform_spec=spec,
        )

        def controlled_command_factory(
            keywords: Sequence[str],
            max_items: int,
            output_dir: Path,
        ) -> list[str]:
            if original_command_factory is not None:
                original_command_factory(keywords, max_items, output_dir)
            return builder.build(
                keywords=keywords,
                max_items=max_items,
                output_dir=output_dir,
                login_type=login_type,
                crawler_type=crawler_type,
                get_comment=args.comments,
            )

        runner.command_factory = controlled_command_factory
        batch_id = f"controlled-{uuid.uuid4().hex[:12]}"
        batch_paths = MediaCrawlerBatchLocator(
            runtime_root,
            platform_spec=spec,
        ).locate(
            batch_id,
            artifact_scope=runtime_config.artifact_scope,
        )
        argv_snapshot = builder.build(
            keywords=args.keywords,
            max_items=args.max_items,
            output_dir=batch_paths.output_path.parent,
            login_type=login_type,
            crawler_type=crawler_type,
            get_comment=args.comments,
        )
        print("argv_snapshot=" + json.dumps(argv_snapshot, ensure_ascii=False))
        # Prepare the adapter view before either dry-run reporting or the
        # controlled sandbox. This still does not start a subprocess.
        runner.command_factory(
            list(args.keywords),
            args.max_items,
            batch_paths.output_path.parent,
        )
        native_binding = runner.runtime_profile_binding

        profile_audit = _profile_audit(
            runtime_root=runtime_root,
            profile_root=profile_root,
            entry=entry,
            source_key=CONTROLLED_SOURCE_KEY,
            login_type=login_type,
        )
        native_binding = None
        if args.allow_controlled_run:
            controlled_collector = resolved.collectors[0]
            controlled_collector.runtime_factory = _FixedRuntimeFactory(
                runner,
                lock,
                spec,
            )
            controlled_collector.runner = None
            previous_expected_platform = os.environ.get(
                "MEDIACRAWLER_EXPECTED_PLATFORM"
            )
            previous_native_parts = os.environ.get(
                "MEDIACRAWLER_NATIVE_OUTPUT_PARTS"
            )
            os.environ["MEDIACRAWLER_EXPECTED_PLATFORM"] = spec.cli_code
            os.environ["MEDIACRAWLER_NATIVE_OUTPUT_PARTS"] = json.dumps(
                spec.native_output_parts
            )
            try:
                items = controlled_collector.fetch(
                    keywords=list(args.keywords),
                    trigger_type="manual",
                    batch_id=batch_id,
                )
            except Exception as exc:
                _emit(
                    {
                        "status": "FAIL",
                        "reason": str(exc),
                        "subprocess_allowed": True,
                        "real_collection_allowed": spec.allow_real_collection,
                    }
                )
                return 1
            finally:
                if previous_expected_platform is None:
                    os.environ.pop("MEDIACRAWLER_EXPECTED_PLATFORM", None)
                else:
                    os.environ["MEDIACRAWLER_EXPECTED_PLATFORM"] = (
                        previous_expected_platform
                    )
                if previous_native_parts is None:
                    os.environ.pop("MEDIACRAWLER_NATIVE_OUTPUT_PARTS", None)
                else:
                    os.environ["MEDIACRAWLER_NATIVE_OUTPUT_PARTS"] = (
                        previous_native_parts
                    )
            result = controlled_collector.last_run_result
            if result is None:
                _emit({"status": "FAIL", "reason": "runner returned no result"})
                return 1
            native_path = result.native_output_path
            content_candidates = (
                list(native_path.parent.glob("*_contents_*.jsonl"))
                if native_path is not None
                else []
            )
            comment_candidates = (
                list(native_path.parent.glob("*_comments_*.jsonl"))
                if native_path is not None
                else []
            )
            for record in profile_audit:
                if record["trigger"] == "manual":
                    record["cleanup_status"] = (
                        "cleaned"
                        if native_binding is None
                        or not native_binding.upstream_root.exists()
                        else "retained"
                    )
            _emit(
                {
                    "status": "PASS",
                    "mode": "controlled_sandbox",
                    "subprocess_allowed": True,
                    "real_collection_allowed": spec.allow_real_collection,
                    "scheduler_started": False,
                    "database_writes": 0,
                    "batch_id": batch_id,
                    "argv_snapshot": argv_snapshot,
                    "platform_spec": {
                        "platform": spec.platform,
                        "cli_code": spec.cli_code,
                        "crawler_type": crawler_type,
                        "login_type": login_type,
                        "native_output_parts": spec.native_output_parts,
                    },
                    "profile_audit": profile_audit,
                    "artifact": {
                        "raw_path": result.raw_output_path,
                        "output_path": result.output_path,
                        "metrics_path": result.metrics_path,
                        "native_content_paths": content_candidates,
                        "native_comment_paths": comment_candidates,
                        "contains_weibo": "weibo" in str(result.run_dir).lower(),
                    },
                    "normalized_count": len(items),
                    "normalized_sample": items[:3],
                    "cleanup_status": "success_cleaned",
                    "real_media_crawler_started": False,
                }
            )
            return 0

        binding = runner.runtime_profile_binding
        if binding is not None:
            native_binding = binding
            runner.runtime_profile_adapter.cleanup(binding)
            for record in profile_audit:
                if record["trigger"] == "manual":
                    record["cleanup_status"] = "dry_run_cleaned"
        ended = datetime.now(timezone.utc)
        _emit(
            {
                "status": "DRY_RUN",
                "mode": "dry_run",
                "subprocess_allowed": False,
                "real_collection_allowed": spec.allow_real_collection,
                "scheduler_started": False,
                "database_writes": 0,
                "start_time": started,
                "end_time": ended,
                "argv_snapshot": argv_snapshot,
                "platform_spec": {
                    "platform": spec.platform,
                    "cli_code": spec.cli_code,
                    "crawler_type": crawler_type,
                    "login_type": login_type,
                    "native_output_parts": spec.native_output_parts,
                },
                "profile_audit": profile_audit,
                "planned_artifact": batch_paths,
                "real_media_crawler_started": False,
            }
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
