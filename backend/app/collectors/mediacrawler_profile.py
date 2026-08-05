"""Read-only MediaCrawler browser profile readiness checks.

This module deliberately has no bootstrap/copy operation. A profile directory
must be provisioned by deployment tooling after an explicit operator approval;
the application only resolves and validates its trigger-specific location.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.collectors.mediacrawler_runner import MediaCrawlerRunnerConfigurationError


class MediaCrawlerProfileUnavailableError(MediaCrawlerRunnerConfigurationError):
    """A trigger-specific profile is absent or is not a directory."""


@dataclass(frozen=True)
class MediaCrawlerProfileReadiness:
    trigger_type: str
    profile_path: Path
    exists: bool
    is_directory: bool
    entry_count: int | None

    @property
    def ready(self) -> bool:
        return self.exists and self.is_directory

    def as_dict(self) -> dict[str, object]:
        return {
            "trigger_type": self.trigger_type,
            "profile_path": str(self.profile_path),
            "exists": self.exists,
            "is_directory": self.is_directory,
            "entry_count": self.entry_count,
            "ready": self.ready,
        }


class MediaCrawlerProfileManager:
    """Resolve isolated manual/scheduler profiles without mutating the filesystem."""

    ALLOWED_TRIGGERS = frozenset({"manual", "scheduler"})

    def __init__(self, runtime_root: str | Path, profile_root: str | Path | None = None):
        self.runtime_root = Path(runtime_root).resolve()
        self.profile_root = Path(profile_root).resolve() if profile_root else self.runtime_root / "profiles"

    @classmethod
    def normalize_trigger(cls, trigger_type: str) -> str:
        if trigger_type in {"scheduled", "scheduler"}:
            trigger = "scheduler"
        elif trigger_type == "manual":
            trigger = "manual"
        else:
            raise ValueError(f"unsupported MediaCrawler trigger_type: {trigger_type}")
        if trigger not in cls.ALLOWED_TRIGGERS:
            raise ValueError(f"unsupported MediaCrawler trigger_type: {trigger_type}")
        return trigger

    def profile_path(self, trigger_type: str) -> Path:
        return self.profile_root / self.normalize_trigger(trigger_type)

    def check(self, trigger_type: str) -> MediaCrawlerProfileReadiness:
        trigger = self.normalize_trigger(trigger_type)
        path = self.profile_path(trigger)
        exists = path.exists()
        is_directory = path.is_dir()
        entry_count: int | None = None
        if is_directory:
            try:
                entry_count = sum(1 for _ in path.iterdir())
            except OSError:
                entry_count = None
        return MediaCrawlerProfileReadiness(
            trigger_type=trigger,
            profile_path=path,
            exists=exists,
            is_directory=is_directory,
            entry_count=entry_count,
        )

    def readiness(self) -> dict[str, dict[str, object]]:
        return {trigger: self.check(trigger).as_dict() for trigger in sorted(self.ALLOWED_TRIGGERS)}

    def bootstrap_check(self, trigger_type: str) -> MediaCrawlerProfileReadiness:
        """Deployment bootstrap hook that only checks; it never creates state."""

        return self.check(trigger_type)

    def require(self, trigger_type: str) -> Path:
        status = self.check(trigger_type)
        if not status.ready:
            raise MediaCrawlerProfileUnavailableError(
                f"MediaCrawler {status.trigger_type} profile unavailable: {status.profile_path}"
            )
        return status.profile_path
