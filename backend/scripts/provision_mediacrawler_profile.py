"""Provision an empty, trigger-scoped MediaCrawler profile template.

This is deployment preparation only. It creates a directory and a sanitized
marker; it never accepts or writes cookies, tokens, passwords, QR codes, or
browser state.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.collectors.mediacrawler_profile import MediaCrawlerProfileManager  # noqa: E402

PROVISIONING_MARKER = "PROFILE_PROVISIONING.json"


def provision_profile(
    *,
    runtime_root: str | Path,
    profile_root: str | Path,
    platform: str,
    source_key: str,
    trigger_type: str = "scheduler",
) -> dict[str, Any]:
    """Create one empty profile directory and a non-secret provisioning marker."""

    normalized_platform = str(platform).strip().lower()
    if not normalized_platform:
        raise ValueError("platform is required")
    manager = MediaCrawlerProfileManager(
        runtime_root=runtime_root,
        profile_root=profile_root,
        profile_scope=f"{normalized_platform}/{source_key}",
    )
    trigger = manager.normalize_trigger(trigger_type)
    profile_path = manager.profile_path(trigger).resolve()
    profile_path.mkdir(parents=True, exist_ok=True)

    marker = {
        "schema_version": 1,
        "status": "provisioned_empty",
        "platform": normalized_platform,
        "source_key": str(source_key),
        "trigger": trigger,
        "profile_contract": "platform/source/trigger",
        "credentials_persisted": False,
        "requires_operator_login": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    marker_path = profile_path / PROVISIONING_MARKER
    marker_path.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    readiness = manager.check(trigger)
    return {
        **marker,
        "profile_path": str(profile_path),
        "marker_path": str(marker_path),
        "exists": readiness.exists,
        "is_directory": readiness.is_directory,
        "entry_count": readiness.entry_count,
        "ready": readiness.ready,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create an empty MediaCrawler profile template without credentials."
    )
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--profile-root", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--source-key", required=True)
    parser.add_argument(
        "--trigger",
        default="scheduler",
        choices=("manual", "scheduler"),
    )
    args = parser.parse_args(argv)
    result = provision_profile(
        runtime_root=args.runtime_root,
        profile_root=args.profile_root,
        platform=args.platform,
        source_key=args.source_key,
        trigger_type=args.trigger,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
