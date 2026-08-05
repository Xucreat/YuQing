"""Deployment-only MediaCrawler runtime assembly.

Business configuration stays in ``DataSource.config_json``.  Executable paths,
profiles and process policy are read from deployment settings and assembled at
the last possible moment, so manual and scheduler runs share one boundary.
"""
from __future__ import annotations

import errno
import os
import shutil
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable

from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_profile import (
    MediaCrawlerProfileManager,
    MediaCrawlerProfileUnavailableError,
)
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRunner,
    MediaCrawlerRunnerConfigurationError,
)
from app.core.config import settings


class MediaCrawlerRuntimeConfigurationError(MediaCrawlerRunnerConfigurationError):
    """Deployment runtime is incomplete or unsafe for the requested trigger."""


class MediaCrawlerRuntimeError(MediaCrawlerRunnerConfigurationError):
    """A runtime policy gate deliberately blocked execution."""


class MediaCrawlerLockTimeoutError(MediaCrawlerRuntimeConfigurationError):
    """Another MediaCrawler run owns the source lock."""


@dataclass(frozen=True)
class MediaCrawlerRuntimeConfig:
    trigger_type: str
    root: Path
    runtime_path: Path
    profile_path: Path
    python_executable: str
    entry: Path
    timeout_seconds: int | float
    login_type: str
    real_run_gate: bool

    @property
    def enable_real_run(self) -> bool:
        """Backward-compatible name used by the Runner constructor."""

        return self.real_run_gate


class MediaCrawlerRunLock:
    """Cross-process source lock with OS release on abnormal process exit."""

    def __init__(self, path: str | Path, *, timeout_seconds: float = 1.0, poll_seconds: float = 0.05):
        self.path = Path(path)
        self.timeout_seconds = max(float(timeout_seconds), 0.0)
        self.poll_seconds = max(float(poll_seconds), 0.01)
        self._handle = None
        self._locked = False

    def _try_lock(self) -> bool:
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN, 13, 36):
                    return False
                raise
        import fcntl

        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return False
            raise

    def acquire(self) -> "MediaCrawlerRunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        if os.name == "nt":
            self._handle.seek(0, os.SEEK_END)
            if self._handle.tell() == 0:
                self._handle.write(b"0")
                self._handle.flush()
            self._handle.seek(0)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            if self._try_lock():
                self._locked = True
                return self
            if time.monotonic() >= deadline:
                self.release()
                raise MediaCrawlerLockTimeoutError(
                    f"MediaCrawler run lock is busy: {self.path.name}"
                )
            time.sleep(self.poll_seconds)

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if self._locked:
                if os.name == "nt":
                    import msvcrt

                    self._handle.seek(0)
                    msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._locked = False
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "MediaCrawlerRunLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class MediaCrawlerRuntimeFactory:
    """Build the same runtime contract for manual and scheduler triggers."""

    def __init__(self, *, source_key: str = "weibo_mediacrawler", root: str | Path | None = None):
        self.source_key = source_key
        self._root_override = Path(root) if root is not None else None

    def config(self, trigger_type: str = "manual") -> MediaCrawlerRuntimeConfig:
        trigger = MediaCrawlerProfileManager.normalize_trigger(trigger_type)
        root = self._root_override or Path(getattr(settings, "media_crawler_root", "") or "runtime/mediacrawler")
        runtime_path = root.resolve()
        profile_root = Path(
            getattr(settings, "media_crawler_profile_root", "") or runtime_path / "profiles"
        )
        profile_manager = MediaCrawlerProfileManager(runtime_path, profile_root)
        profile_path = profile_manager.profile_path(trigger)
        python_executable = str(getattr(settings, "media_crawler_python", "") or sys.executable)
        entry_value = str(getattr(settings, "media_crawler_entry", "") or "").strip()
        if not entry_value:
            raise MediaCrawlerRuntimeConfigurationError(
                "MEDIA_CRAWLER_ENTRY is required for MediaCrawler runtime"
            )
        entry = Path(entry_value)
        if not entry.is_absolute():
            entry = (runtime_path / entry).resolve()
        if not entry.is_file():
            raise MediaCrawlerRuntimeConfigurationError(
                f"MediaCrawler entry does not exist: {entry}"
            )
        if not Path(python_executable).is_file() and shutil.which(python_executable) is None:
            raise MediaCrawlerRuntimeConfigurationError(
                f"MediaCrawler Python executable is unavailable: {python_executable}"
            )
        login_type = str(
            getattr(
                settings,
                "media_crawler_scheduler_login_type" if trigger == "scheduler" else "media_crawler_login_type",
                "cookie" if trigger == "scheduler" else "qrcode",
            )
            or ("cookie" if trigger == "scheduler" else "qrcode")
        ).strip().lower()
        if trigger == "scheduler" and login_type in {"qrcode", "phone", "interactive"}:
            raise MediaCrawlerRuntimeConfigurationError(
                "scheduler MediaCrawler runtime requires non-interactive profile login"
            )
        timeout = getattr(settings, "media_crawler_timeout_seconds", 900)
        real_run_gate = bool(getattr(settings, "media_crawler_real_run_gate", False))
        return MediaCrawlerRuntimeConfig(
            trigger_type=trigger,
            root=runtime_path,
            runtime_path=runtime_path,
            profile_path=profile_path.resolve(),
            python_executable=python_executable,
            entry=entry,
            timeout_seconds=timeout,
            login_type=login_type,
            real_run_gate=real_run_gate,
        )

    def create_runner(
        self,
        trigger_type: str = "manual",
        *,
        profile_path: str | Path | None = None,
        mock_command: bool = False,
    ) -> tuple[MediaCrawlerRunner, MediaCrawlerRunLock, MediaCrawlerRuntimeConfig]:
        config = self.config(trigger_type)
        if profile_path is not None:
            config = replace(config, profile_path=Path(profile_path).resolve())
        builder = MediaCrawlerCommandBuilder(
            python_executable=config.python_executable,
            entry=str(config.entry),
        )
        profile_manager = MediaCrawlerProfileManager(
            config.runtime_path,
            config.profile_path.parent,
        )

        def command_factory(keywords: Iterable[str], max_items: int, output_dir: Path) -> list[str]:
            if config.trigger_type == "scheduler" and not config.real_run_gate:
                raise MediaCrawlerRuntimeError(
                    "MediaCrawler scheduler real-run gate is disabled; explicit enablement is required"
                )
            profile_manager.require(config.trigger_type)
            return builder.build(
                keywords=keywords,
                max_items=max_items,
                output_dir=output_dir,
                login_type=config.login_type,
            )

        runner = MediaCrawlerRunner(
            root=config.runtime_path,
            python_executable=config.python_executable,
            browser_data=str(config.profile_path),
            profile_name=str(config.profile_path),
            command_factory=command_factory,
            # The upstream entry imports its config relative to the checkout.
            # Keep that checkout as cwd even when the configured entry is a
            # deployment wrapper outside the MediaCrawler root.
            command_cwd=config.runtime_path,
            mock_command=mock_command,
            enable_real_run=config.real_run_gate,
        )
        lock = MediaCrawlerRunLock(
            config.runtime_path / "locks" / f"{self.source_key}.lock",
            timeout_seconds=1.0,
        )
        return runner, lock, config
