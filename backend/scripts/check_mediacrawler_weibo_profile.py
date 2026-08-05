"""Read-only check for the MediaCrawler Weibo browser profile."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.core.config import settings  # noqa: E402


def inspect_weibo_profile(browser_data: str | None = None) -> dict[str, object]:
    configured = browser_data or os.getenv("MEDIA_CRAWLER_BROWSER_DATA") or settings.media_crawler_browser_data
    profile = (Path(configured).expanduser() / "wb_user_data_dir") if configured else None
    exists = bool(profile and profile.is_dir())
    file_count = 0
    size_bytes = 0
    if exists and profile is not None:
        for path in profile.rglob("*"):
            if not path.is_file():
                continue
            file_count += 1
            try:
                size_bytes += path.stat().st_size
            except OSError:
                continue
    return {
        "exists": exists,
        "profile_path": str(profile) if profile else "",
        "file_count": file_count,
        "size_bytes": size_bytes,
        "status": "PASS" if exists else "BLOCKED",
    }


def main() -> int:
    result = inspect_weibo_profile()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["exists"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
