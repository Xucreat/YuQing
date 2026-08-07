"""Explicit compatibility policies for legacy MediaCrawler layouts.

The generic runtime only consumes this contract. Platform-specific legacy
knowledge belongs in the compatibility module that owns the old deployment
layout.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaCrawlerCompatibilityPolicy:
    """Optional legacy path policy supplied by a platform compatibility layer."""

    profile_scope: str | None = None
    artifact_scope: str | None = None
    lock_scope: str | None = None
    lock_name_template: str = "{source_key}.lock"

    def lock_path(
        self,
        root: Path,
        *,
        source_key: str,
        platform: str,
    ) -> Path:
        del platform
        lock_dir = root / "locks"
        if self.lock_scope:
            lock_dir = lock_dir / self.lock_scope
        lock_name = self.lock_name_template.format(source_key=source_key)
        return lock_dir / lock_name
