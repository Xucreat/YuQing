"""Read-only runtime identity helpers for Scheduler isolation diagnostics."""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def project_root() -> Path:
    """Return the repository root for ``backend/app/core``."""

    return Path(__file__).resolve().parents[3]


def _git_dir(root: Path) -> Path:
    dot_git = root / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        # Worktrees/submodules may store ``gitdir: <path>`` in .git.
        marker = dot_git.read_text(encoding="utf-8").strip()
        if marker.startswith("gitdir:"):
            value = marker.split(":", 1)[1].strip()
            path = Path(value)
            return path if path.is_absolute() else (root / path).resolve()
    return dot_git


def git_commit(root: Path | None = None) -> str | None:
    """Read HEAD without spawning a subprocess or mutating the repository."""

    repo_root = root or project_root()
    git_root = _git_dir(repo_root)
    try:
        head = (git_root / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if head.startswith("ref:"):
        ref = head.split(":", 1)[1].strip()
        try:
            return (git_root / ref).read_text(encoding="utf-8").strip() or None
        except OSError:
            try:
                packed = (git_root / "packed-refs").read_text(encoding="utf-8")
            except OSError:
                return None
            for line in packed.splitlines():
                if line and not line.startswith("#") and " " in line:
                    commit, packed_ref = line.split(" ", 1)
                    if packed_ref.strip() == ref:
                        return commit
            return None
    return head or None


def _module_path(module: Any) -> str | None:
    value = getattr(module, "__file__", None)
    return str(Path(value).resolve()) if value else None


def build_scheduler_owner_fingerprint() -> dict[str, Any]:
    """Build a serializable, read-only identity snapshot for one process."""

    from app.collectors import media_crawler_weibo_collector
    from app.collectors import registry
    from app.collectors.mediacrawler_runtime import MediaCrawlerRuntimeFactory

    root = project_root()
    return {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "python_executable": str(Path(sys.executable).resolve()),
        "project_root": str(root),
        "git_commit": git_commit(root),
        "registry_module_path": _module_path(registry),
        "media_crawler_collector_module_path": _module_path(
            media_crawler_weibo_collector
        ),
        "runtime_factory_available": MediaCrawlerRuntimeFactory is not None,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def format_scheduler_owner_fingerprint(
    fingerprint: dict[str, Any],
) -> str:
    """Render a stable one-line JSON payload for Scheduler logs."""

    return json.dumps(
        fingerprint,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
