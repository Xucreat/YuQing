"""Disposable browser-profile isolation for MediaCrawler runs.

The configured ``profiles/<trigger>`` directories are deployment templates.
Real Chromium processes must receive a batch-scoped copy so browser state,
cookies, history, and caches cannot mutate the persistent template.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path


class BrowserProfileIsolationError(RuntimeError):
    """Raised when a disposable profile cannot be safely created or removed."""


_BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class BrowserProfileIsolationManager:
    """Create and clean batch-scoped browser profiles under ``runtime_profiles``."""

    def __init__(self, runtime_root: str | Path, profile_scope: str | None = None):
        self.runtime_root = Path(runtime_root).resolve()
        self.runtime_profiles_root = self.runtime_root / "runtime_profiles"
        if profile_scope:
            parts = [part for part in str(profile_scope).replace("\\", "/").split("/") if part]
            if not parts or any(
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", part) is None
                for part in parts
            ):
                raise BrowserProfileIsolationError("invalid browser runtime profile scope")
            self.runtime_profiles_root = self.runtime_profiles_root.joinpath(*parts)

    @staticmethod
    def _validate_batch_id(batch_id: str) -> str:
        value = str(batch_id).strip()
        if not _BATCH_ID_RE.fullmatch(value):
            raise BrowserProfileIsolationError("invalid browser runtime profile batch_id")
        return value

    def create_runtime_profile(
        self,
        source_profile: str | Path,
        batch_id: str,
    ) -> Path:
        """Copy a persistent template into a new, batch-scoped directory.

        ``copytree(..., copy_function=copy2)`` preserves file metadata and
        refuses to overwrite an existing batch directory.
        """

        value = self._validate_batch_id(batch_id)
        source = Path(source_profile).resolve()
        if not source.is_dir():
            raise BrowserProfileIsolationError(
                f"browser source profile unavailable: {source}"
            )
        destination = (self.runtime_profiles_root / value).resolve()
        if destination == self.runtime_profiles_root or self.runtime_profiles_root not in destination.parents:
            raise BrowserProfileIsolationError("runtime profile destination escaped runtime root")
        if destination.exists():
            raise BrowserProfileIsolationError(
                f"browser runtime profile already exists: {destination}"
            )
        self.runtime_profiles_root.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(
                source,
                destination,
                copy_function=shutil.copy2,
                dirs_exist_ok=False,
            )
        except Exception as exc:
            # A partial copy is not a usable runtime profile. Remove only the
            # newly-created destination, never the persistent source template.
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            raise BrowserProfileIsolationError(
                f"unable to create browser runtime profile: {destination}"
            ) from exc
        return destination

    def cleanup_runtime_profile(self, runtime_profile: str | Path) -> None:
        """Remove a successful batch profile, never a persistent template."""

        target = Path(runtime_profile).resolve()
        if target == self.runtime_profiles_root or self.runtime_profiles_root not in target.parents:
            raise BrowserProfileIsolationError(
                f"refusing to remove profile outside runtime_profiles: {target}"
            )
        if target.exists():
            shutil.rmtree(target)


def create_runtime_profile(
    source_profile: str | Path,
    batch_id: str,
    *,
    runtime_root: str | Path,
) -> Path:
    """Functional wrapper for callers that do not need a manager instance."""

    return BrowserProfileIsolationManager(runtime_root).create_runtime_profile(
        source_profile,
        batch_id,
    )


def cleanup_runtime_profile(
    runtime_profile: str | Path,
    *,
    runtime_root: str | Path,
) -> None:
    """Functional wrapper for safe cleanup."""

    BrowserProfileIsolationManager(runtime_root).cleanup_runtime_profile(
        runtime_profile
    )
