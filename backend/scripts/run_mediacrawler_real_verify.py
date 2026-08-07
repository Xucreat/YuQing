"""Run one explicitly confirmed, bounded MediaCrawler verification.

This entry point is intentionally not a scheduler job and never calls
CollectorService. It emits an audit-friendly JSON result and keeps the
DataSource registration payload in memory only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.media_crawler_registration import (  # noqa: E402
    build_mediacrawler_data_source_payload,
)
from app.collectors.mediacrawler_command_builder import (  # noqa: E402
    build_mediacrawler_command,
)
from app.collectors.media_crawler_weibo_collector import (  # noqa: E402
    MediaCrawlerWeiboCollector,
    normalize_keywords,
)
from app.collectors.mediacrawler_runner import (  # noqa: E402
    MediaCrawlerProcessError,
    MediaCrawlerRunner,
    MediaCrawlerRunnerError,
)
from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory  # noqa: E402
from app.collectors.mediacrawler_weibo_compatibility import (  # noqa: E402
    WEIBO_COMPATIBILITY_POLICY,
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)
from app.core.config import settings  # noqa: E402
from scripts.check_mediacrawler_env import collect_checks  # noqa: E402
from scripts.check_weibo_profile_switch import inspect_profile  # noqa: E402

MAX_ITEMS_LIMIT = 20
MAX_TIMEOUT_SECONDS = 600


def validate_real_verify_options(
    *, confirm_real_run: bool, max_items: int, timeout_seconds: int, enable_real_run: bool
) -> None:
    """Validate all operator confirmations before any process can be started."""

    if not confirm_real_run:
        raise ValueError("refusing real run: --confirm-real-run is required")
    if max_items < 1 or max_items > MAX_ITEMS_LIMIT:
        raise ValueError(f"max_items must be between 1 and {MAX_ITEMS_LIMIT}")
    if timeout_seconds < 1 or timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise ValueError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
    if not enable_real_run:
        raise ValueError(
            "real run is disabled: set MEDIA_CRAWLER_ENABLE_REAL_RUN=true explicitly"
        )


def build_real_command(
    explicit_command: Sequence[str] | None, *, root: str, python_executable: str, entry: str
) -> list[str]:
    """Resolve an explicit command or the configured Python + entry pair."""

    if explicit_command:
        return list(explicit_command)
    if not root or not entry:
        raise ValueError(
            "MEDIA_CRAWLER_ROOT and MEDIA_CRAWLER_ENTRY are required when --command is absent"
        )
    entry_path = Path(entry).expanduser()
    if not entry_path.is_absolute():
        entry_path = Path(root).expanduser() / entry_path
    if not entry_path.is_file():
        raise ValueError("MediaCrawler entry file does not exist")
    return [python_executable, str(entry_path)]


def validate_native_profile(*, root: str, profile_path: str | None) -> Path | None:
    if not profile_path:
        return None
    root_path = Path(root).expanduser().resolve()
    profile = Path(profile_path).expanduser().resolve()
    expected_parent = root_path / "browser_data"
    if profile.parent != expected_parent:
        raise ValueError("native profile must be a direct child of MEDIA_CRAWLER_ROOT/browser_data")
    if not inspect_profile(profile)["exists"]:
        raise ValueError("native profile directory does not exist")
    return profile


def compute_jsonl_metrics(path: str | Path) -> dict[str, int]:
    """Count raw, valid, invalid and duplicate JSONL records independently."""

    raw_count = valid_count = invalid_count = duplicate_count = 0
    seen: set[str] = set()
    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            raw_count += 1
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("JSONL row must be an object")
                item = MediaCrawlerWeiboCollector._normalize_row(row)
                if item is None:
                    raise ValueError("content is empty")
            except (json.JSONDecodeError, TypeError, ValueError):
                invalid_count += 1
                continue
            valid_count += 1
            dedup_key = MediaCrawlerWeiboCollector._dedup_key(item)
            if dedup_key and dedup_key in seen:
                duplicate_count += 1
            elif dedup_key:
                seen.add(dedup_key)
    return {
        "raw_count": raw_count,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "duplicate_count": duplicate_count,
        "output_count": valid_count - duplicate_count,
    }


def compute_field_coverage(items: Sequence[dict[str, Any]]) -> dict[str, float]:
    """Return percentages for the fields entering the CollectorService contract."""

    total = len(items)
    if not total:
        return {
            key: 0.0
            for key in (
                "content",
                "author",
                "publish_time",
                "external_id",
                "url",
                "engagement",
            )
        }
    checks = {
        "content": lambda item: bool(item.get("content")),
        "author": lambda item: bool(item.get("author")),
        "publish_time": lambda item: item.get("publish_time") is not None,
        "external_id": lambda item: bool(item.get("external_id")),
        "url": lambda item: bool(item.get("url")),
        "engagement": lambda item: isinstance(item.get("engagement"), dict),
    }
    return {
        key: round(sum(bool(check(item)) for item in items) * 100 / total, 2)
        for key, check in checks.items()
    }


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _print_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, ensure_ascii=False, default=_json_default))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded manual MediaCrawler real verification")
    parser.add_argument("--keywords", nargs="+")
    parser.add_argument("--sample-keyword", default="大厂县")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--confirm-real-run", action="store_true")
    parser.add_argument("--native-mode", action="store_true")
    parser.add_argument(
        "--profile-path",
        help="explicit persistent profile; native mode requires it to be under MEDIA_CRAWLER_ROOT/browser_data",
    )
    parser.add_argument(
        "--disable-cdp",
        action="store_true",
        help="use the controlled standard-browser debug entry instead of existing CDP",
    )
    parser.add_argument(
        "--command",
        nargs="+",
        help="optional explicit command; otherwise MEDIA_CRAWLER_PYTHON + MEDIA_CRAWLER_ENTRY is used",
    )
    args = parser.parse_args(argv)

    try:
        validate_real_verify_options(
            confirm_real_run=args.confirm_real_run,
            max_items=args.max_items,
            timeout_seconds=args.timeout_seconds,
            # The environment result is reported below before the real-run
            # gate so an absent root is visible as BLOCKED to the operator.
            enable_real_run=True,
        )
    except ValueError as exc:
        _print_result({"status": "BLOCKED", "reason": str(exc)})
        return 3

    root = os.getenv("MEDIA_CRAWLER_ROOT") or settings.media_crawler_root
    python_executable = os.getenv("MEDIA_CRAWLER_PYTHON") or settings.media_crawler_python or sys.executable
    entry = os.getenv("MEDIA_CRAWLER_ENTRY") or settings.media_crawler_entry
    try:
        native_profile = validate_native_profile(
            root=root,
            profile_path=args.profile_path if args.native_mode else None,
        )
    except ValueError as exc:
        _print_result({"status": "BLOCKED", "reason": str(exc)})
        return 3

    checks = collect_checks(require_weibo_profile=False)
    required_failures = [check.name for check in checks if not check.ok and not check.optional]
    if required_failures:
        _print_result(
            {
                "status": "BLOCKED",
                "reason": "MediaCrawler environment is not ready",
                "failed_checks": required_failures,
                "data_source": build_mediacrawler_data_source_payload(),
            }
        )
        return 3

    if not settings.media_crawler_enable_real_run:
        _print_result(
            {
                "status": "BLOCKED",
                "reason": "set MEDIA_CRAWLER_ENABLE_REAL_RUN=true explicitly",
            }
        )
        return 3

    keywords = normalize_keywords(args.keywords or [args.sample_keyword])
    started = datetime.now(timezone.utc)
    runtime_root = _BACKEND_ROOT.parent / "runtime" / "mediacrawler"
    output_dir = None
    command_cwd = None
    runtime_lock = None
    runtime_factory = None
    runner = None
    try:
        if args.native_mode:
            batch_dir = runtime_root / "runs" / uuid.uuid4().hex
            output_dir = batch_dir / "output"
            runtime_factory = MediaCrawlerRuntimeFactory(
                root=runtime_root,
                source_key=WEIBO_SOURCE_KEY,
                platform_spec=WEIBO_PLATFORM_SPEC,
                compatibility_policy=WEIBO_COMPATIBILITY_POLICY,
            )
            runner, runtime_lock, runtime_config = runtime_factory.create_runner(
                "manual", profile_path=native_profile
            )
            if args.disable_cdp:
                # The standard entry remains an explicit operator override, while
                # argv construction still flows through the shared Runner seam.
                runner.command_factory = lambda kw, limit, out: build_mediacrawler_command(
                    python_executable=python_executable,
                    entry=str(_BACKEND_ROOT / "scripts" / "mediacrawler_standard_entry.py"),
                    keywords=kw,
                    max_items=limit,
                    output_dir=out,
                    login_type=runtime_config.login_type,
                    platform_spec=WEIBO_PLATFORM_SPEC,
                )
            runner.enable_real_run = True
            runner.command_cwd = Path(root)
        else:
            command = build_real_command(
                args.command, root=root, python_executable=python_executable, entry=entry
            )
    except ValueError as exc:
        _print_result({"status": "BLOCKED", "reason": str(exc)})
        return 3

    if runner is None:
        runner = MediaCrawlerRunner(
            root=runtime_root if args.native_mode else root,
            python_executable=python_executable,
            browser_data=os.getenv("MEDIA_CRAWLER_BROWSER_DATA") or settings.media_crawler_browser_data,
            command=command,
            command_cwd=command_cwd,
            mock_command=False,
            enable_real_run=True,
            platform_spec=WEIBO_PLATFORM_SPEC,
            source_key=WEIBO_SOURCE_KEY,
        )
    collector = MediaCrawlerWeiboCollector(
        runner=runner, max_items=args.max_items, timeout_seconds=args.timeout_seconds
    )
    try:
        previous_profile_name = os.environ.get("MEDIA_CRAWLER_PROFILE_NAME")
        if native_profile is not None:
            os.environ["MEDIA_CRAWLER_PROFILE_NAME"] = native_profile.name
        run_kwargs = {
            "output_dir": output_dir,
            "timeout_seconds": args.timeout_seconds,
            "max_items": args.max_items,
            "crawler_config": {"collection_scope": "national", "max_items": args.max_items},
            "native_output_path": output_dir if args.native_mode else None,
        }
        if runtime_lock is not None:
            with runtime_lock:
                run_result = runner.run(keywords, **run_kwargs)
        else:
            run_result = runner.run(keywords, **run_kwargs)
        items = collector._read_jsonl(run_result)
        ended = datetime.now(timezone.utc)
        output_metrics = compute_jsonl_metrics(run_result.jsonl_path)
        if run_result.raw_count is not None:
            output_metrics["raw_count"] = run_result.raw_count
        if run_result.output_count is not None:
            output_metrics["output_count"] = run_result.output_count
        _print_result(
            {
                "status": "PASS",
                "batch_id": run_result.batch_id,
                "start_time": started,
                "end_time": ended,
                "duration_seconds": round((ended - started).total_seconds(), 3),
                "exit_code": run_result.exit_code,
                "jsonl_path": str(run_result.jsonl_path),
                "native_output_path": (
                    str(run_result.native_output_path)
                    if run_result.native_output_path
                    else None
                ),
                "stderr": run_result.stderr,
                "timeout_seconds": args.timeout_seconds,
                "jsonl": output_metrics,
                "field_coverage": compute_field_coverage(items),
                "sample": items[:3],
                "data_source": build_mediacrawler_data_source_payload(),
            }
        )
        return 0
    except MediaCrawlerProcessError as exc:
        _print_result(
            {
                "status": "FAIL",
                "error": str(exc),
                "exit_code": exc.exit_code,
                "stderr": exc.stderr,
            }
        )
        return 1
    except MediaCrawlerRunnerError as exc:
        _print_result({"status": "FAIL", "error": str(exc)})
        return 1
    finally:
        if native_profile is not None:
            if previous_profile_name is None:
                os.environ.pop("MEDIA_CRAWLER_PROFILE_NAME", None)
            else:
                os.environ["MEDIA_CRAWLER_PROFILE_NAME"] = previous_profile_name


if __name__ == "__main__":
    raise SystemExit(main())
