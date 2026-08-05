"""Read-only metadata check for a manually prepared Weibo profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def inspect_profile(profile_path: str | Path) -> dict[str, Any]:
    profile = Path(profile_path).expanduser()
    exists = profile.is_dir()
    file_count = 0
    size_bytes = 0
    if exists:
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
        "size_bytes": size_bytes,
        "file_count": file_count,
        "status": "PASS" if exists else "BLOCKED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Weibo profile metadata without reading files")
    parser.add_argument("--profile-path", required=True)
    args = parser.parse_args(argv)
    result = inspect_profile(args.profile_path)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["exists"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
