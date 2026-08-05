"""Read-only diagnostics for the MediaCrawler Weibo runtime boundary."""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402


def _profile_exists(browser_data: str | None) -> bool:
    return bool(browser_data and (Path(browser_data).expanduser() / "wb_user_data_dir").is_dir())


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(1.0)
        return client.connect_ex(("127.0.0.1", port)) == 0


def _browser_process_present() -> bool:
    tasklist = shutil.which("tasklist")
    if not tasklist:
        return False
    try:
        result = subprocess.run(
            [tasklist, "/FI", "IMAGENAME eq chrome.exe", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and "chrome.exe" in result.stdout.lower()


def inspect_runtime(
    *,
    browser_data: str | None = None,
    cdp_port: int = 9222,
    browser_process_check: bool | None = None,
) -> dict[str, str]:
    configured = browser_data or os.getenv("MEDIA_CRAWLER_BROWSER_DATA") or settings.media_crawler_browser_data
    profile_ok = _profile_exists(configured)
    cdp_ok = _port_open(cdp_port)
    browser_ok = (
        _browser_process_present() if browser_process_check is None else browser_process_check
    )
    reasons: list[str] = []
    if not profile_ok:
        reasons.append("wb_user_data_dir missing")
    if not cdp_ok:
        reasons.append(f"CDP port {cdp_port} is not listening")
    if not browser_ok:
        reasons.append("Chrome process not detected")
    return {
        "profile": "PASS" if profile_ok else "BLOCKED",
        "cdp": "PASS" if cdp_ok else "BLOCKED",
        "browser": "PASS" if browser_ok else "BLOCKED",
        "reason": "; ".join(reasons),
    }


def main() -> int:
    result = inspect_runtime()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if all(result[key] == "PASS" for key in ("profile", "cdp", "browser")) else 3


if __name__ == "__main__":
    raise SystemExit(main())
