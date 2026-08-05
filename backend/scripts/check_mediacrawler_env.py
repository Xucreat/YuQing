"""Read-only MediaCrawler environment check.

The script checks files and the configured Python executable only. It never
starts a browser, imports MediaCrawler, or accesses Weibo.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    optional: bool = False


def _python_ok(executable: str) -> bool:
    candidate = shutil.which(executable) or executable
    try:
        completed = subprocess.run(
            [candidate, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _profile_stats(profile: Path | None) -> tuple[bool, int, int]:
    if profile is None or not profile.is_dir():
        return False, 0, 0
    files = list(profile.rglob("*"))
    regular_files = [path for path in files if path.is_file()]
    total_size = 0
    for path in regular_files:
        try:
            total_size += path.stat().st_size
        except OSError:
            continue
    return True, len(regular_files), total_size


def collect_checks(*, require_weibo_profile: bool = False) -> list[Check]:
    root_value = os.getenv("MEDIA_CRAWLER_ROOT") or settings.media_crawler_root
    root = Path(root_value).expanduser() if root_value else None
    root_ok = bool(root and root.is_dir())

    python_value = os.getenv("MEDIA_CRAWLER_PYTHON") or settings.media_crawler_python or sys.executable
    python_ok = _python_ok(python_value)

    browser_value = os.getenv("MEDIA_CRAWLER_BROWSER_DATA") or settings.media_crawler_browser_data
    browser_root = Path(browser_value).expanduser() if browser_value else None
    browser_ok = not browser_root or browser_root.is_dir()

    entry_value = os.getenv("MEDIA_CRAWLER_ENTRY") or settings.media_crawler_entry
    entry_candidates = [Path(entry_value).expanduser()] if entry_value else []
    if root:
        entry_candidates.append(root / "main.py")
    entry_ok = any(candidate.is_file() for candidate in entry_candidates)

    checks = [
        Check("MEDIA_CRAWLER_ROOT", root_ok, "directory exists" if root_ok else "directory missing"),
        Check("MEDIA_CRAWLER_PYTHON", python_ok, "executable" if python_ok else "not executable"),
        Check(
            "MEDIA_CRAWLER_BROWSER_DATA",
            browser_ok,
            "directory exists" if browser_value and browser_ok else ("not configured (optional)" if not browser_value else "directory missing"),
            optional=True,
        ),
        Check("MediaCrawler entry", entry_ok, "entry file exists" if entry_ok else "entry file missing"),
    ]
    if require_weibo_profile:
        profile = (browser_root / "wb_user_data_dir") if browser_root else None
        profile_exists, file_count, total_size = _profile_stats(profile)
        checks.append(
            Check(
                "MEDIA_CRAWLER_WEIBO_PROFILE",
                profile_exists,
                f"exists={str(profile_exists).lower()} file_count={file_count} size={total_size}",
            )
        )
    return checks


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Read-only MediaCrawler environment check")
    parser.add_argument("--require-weibo-profile", action="store_true")
    args = parser.parse_args()
    checks = collect_checks(require_weibo_profile=True)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"{status} {check.name}: {check.detail}")
    required_ok = all(check.ok for check in checks if not check.optional)
    print(f"Overall: {'PASS' if required_ok else 'FAIL'}")
    return 0 if required_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
