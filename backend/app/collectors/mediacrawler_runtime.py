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

from app.collectors.mediacrawler_compatibility import MediaCrawlerCompatibilityPolicy
from app.collectors.mediacrawler_command_builder import MediaCrawlerCommandBuilder
from app.collectors.mediacrawler_platform import (
    MediaCrawlerConfigurationError,
    MediaCrawlerPlatformSpec,
)
from app.collectors.mediacrawler_profile import (
    MediaCrawlerProfileManager,
    MediaCrawlerProfileUnavailableError,
)
from app.collectors.mediacrawler_profile_adapter import (
    MediaCrawlerProfileAdapter,
    MediaCrawlerProfileBinding,
)
from app.collectors.mediacrawler_runner import (
    MediaCrawlerRunner,
    MediaCrawlerRunnerConfigurationError,
)
from app.core.config import settings
from app.core.browser_profile_manager import BrowserProfileIsolationManager


class MediaCrawlerRuntimeConfigurationError(MediaCrawlerRunnerConfigurationError):
    """Deployment runtime is incomplete or unsafe for the requested trigger."""


class MediaCrawlerRuntimeError(MediaCrawlerRunnerConfigurationError):
    """A runtime policy gate deliberately blocked execution."""


class MediaCrawlerLockTimeoutError(MediaCrawlerRuntimeConfigurationError):
    """Another MediaCrawler run owns the source lock."""


@dataclass(frozen=True)
class MediaCrawlerRuntimeConfig:
    trigger_type: str
    platform: str
    source_key: str
    root: Path
    runtime_path: Path
    checkout_root: Path
    profile_root: Path
    output_root: Path
    profile_path: Path
    python_executable: str
    entry: Path
    timeout_seconds: int | float
    login_type: str
    real_run_gate: bool
    artifact_name: str
    native_output_parts: tuple[str, ...]
    artifact_scope: str | None = None
    runtime_profile_path: Path | None = None
    upstream_profile_path: Path | None = None

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

    def __init__(
        self,
        *,
        source_key: str | None = None,
        platform_spec: MediaCrawlerPlatformSpec | None = None,
        compatibility_policy: MediaCrawlerCompatibilityPolicy | None = None,
        root: str | Path | None = None,
        checkout_root: str | Path | None = None,
        output_root: str | Path | None = None,
        profile_root: str | Path | None = None,
        python_executable: str | None = None,
        entry: str | Path | None = None,
        timeout_seconds: int | float | None = None,
        login_type: str | None = None,
        scheduler_login_type: str | None = None,
        real_run_gate: bool | None = None,
    ):
        if platform_spec is None:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerRuntimeFactory requires an explicit PlatformSpec"
            )
        if not source_key:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerRuntimeFactory requires an explicit source_key"
            )
        self.source_key = str(source_key)
        self.platform_spec = platform_spec
        self.compatibility_policy = compatibility_policy
        self._root_override = Path(root) if root is not None else None
        self._checkout_root_override = (
            Path(checkout_root) if checkout_root is not None else None
        )
        self._output_root_override = (
            Path(output_root) if output_root is not None else None
        )
        self._profile_root_override = (
            Path(profile_root) if profile_root is not None else None
        )
        self._python_executable_override = python_executable
        self._entry_override = Path(entry) if entry is not None else None
        self._timeout_override = timeout_seconds
        self._login_type_override = login_type
        self._scheduler_login_type_override = scheduler_login_type
        self._real_run_gate_override = real_run_gate

    @property
    def _profile_scope(self) -> str | None:
        if self.compatibility_policy is not None:
            return self.compatibility_policy.profile_scope
        return f"{self.platform_spec.platform}/{self.source_key}"

    @property
    def _artifact_scope(self) -> str | None:
        if self.compatibility_policy is not None:
            return self.compatibility_policy.artifact_scope
        return f"{self.platform_spec.platform}/{self.source_key}"

    @property
    def _isolation_scope(self) -> str | None:
        """Compatibility alias for callers that inspect the shared scope."""

        return self._profile_scope

    def config(self, trigger_type: str = "manual") -> MediaCrawlerRuntimeConfig:
        trigger = MediaCrawlerProfileManager.normalize_trigger(trigger_type)
        configured_root = (
            self._output_root_override
            or self._root_override
            or Path(getattr(settings, "media_crawler_root", "") or "runtime/mediacrawler")
        )
        runtime_path = configured_root.resolve()
        # Empty strings are normalized to None so they never shadow a later,
        # more specific candidate (a bare Path("") is truthy and would otherwise
        # resolve to the current working directory).
        checkout_setting_value = getattr(settings, "media_crawler_checkout_root", "") or None
        checkout_setting = (
            Path(checkout_setting_value) if checkout_setting_value is not None else None
        )
        mc_root_setting_value = getattr(settings, "media_crawler_root", "") or None
        mc_root_setting = (
            Path(mc_root_setting_value) if mc_root_setting_value is not None else None
        )
        # Provisional checkout root used only to anchor a relative entry before
        # the final checkout root is derived from the entry's own location.
        provisional_checkout_root = (
            self._checkout_root_override
            or checkout_setting
            or self._root_override
            or mc_root_setting
            or runtime_path
        )
        profile_root = (
            self._profile_root_override
            or Path(
                getattr(settings, "media_crawler_profile_root", "")
                or runtime_path / "profiles"
            )
        ).resolve()
        profile_manager = MediaCrawlerProfileManager(
            runtime_path,
            profile_root,
            profile_scope=self._profile_scope,
        )
        profile_path = profile_manager.profile_path(trigger)
        python_executable = str(
            self._python_executable_override
            or getattr(settings, "media_crawler_python", "")
            or sys.executable
        )
        entry_value = str(
            self._entry_override
            or getattr(settings, "media_crawler_entry", "")
            or ""
        ).strip()
        if not entry_value:
            raise MediaCrawlerRuntimeConfigurationError(
                "MEDIA_CRAWLER_ENTRY is required for MediaCrawler runtime"
            )
        entry = Path(entry_value)
        if not entry.is_absolute():
            entry = (provisional_checkout_root / entry).resolve()
        if not entry.is_file():
            raise MediaCrawlerRuntimeConfigurationError(
                f"MediaCrawler entry does not exist: {entry}"
            )
        # The upstream MediaCrawler entry uses checkout-relative imports and
        # opens files such as ``libs/douyin.js`` from its current directory.
        # The subprocess cwd must therefore be the upstream checkout root, never
        # the isolated native profile. Derive it from the entry's parent when no
        # explicit checkout root is configured so the real runtime cannot fall
        # back to the runtime/profile directory.
        checkout_root = (
            self._checkout_root_override
            or checkout_setting
            or entry.parent
        ).resolve()
        if not Path(python_executable).is_file() and shutil.which(python_executable) is None:
            raise MediaCrawlerRuntimeConfigurationError(
                f"MediaCrawler Python executable is unavailable: {python_executable}"
            )
        configured_login_type = (
            self._scheduler_login_type_override
            if trigger == "scheduler"
            else self._login_type_override
        )
        if configured_login_type is None:
            configured_login_type = getattr(
                settings,
                "media_crawler_scheduler_login_type"
                if trigger == "scheduler"
                else "media_crawler_login_type",
                "cookie" if trigger == "scheduler" else "qrcode",
            )
        login_type = str(
            configured_login_type
            or ("cookie" if trigger == "scheduler" else "qrcode")
        ).strip().lower()
        if trigger == "scheduler" and login_type in {"qrcode", "phone", "interactive"}:
            raise MediaCrawlerRuntimeConfigurationError(
                "scheduler MediaCrawler runtime requires non-interactive profile login"
            )
        timeout = (
            self._timeout_override
            if self._timeout_override is not None
            else getattr(settings, "media_crawler_timeout_seconds", 900)
        )
        real_run_gate = bool(
            self._real_run_gate_override
            if self._real_run_gate_override is not None
            else getattr(settings, "media_crawler_real_run_gate", False)
        )
        return MediaCrawlerRuntimeConfig(
            trigger_type=trigger,
            platform=self.platform_spec.platform,
            source_key=self.source_key,
            root=runtime_path,
            runtime_path=runtime_path,
            checkout_root=checkout_root,
            profile_root=profile_root,
            output_root=runtime_path,
            profile_path=profile_path.resolve(),
            python_executable=python_executable,
            entry=entry,
            timeout_seconds=timeout,
            login_type=login_type,
            real_run_gate=real_run_gate,
            artifact_name=self.platform_spec.artifact_name,
            native_output_parts=self.platform_spec.native_output_parts,
            artifact_scope=self._artifact_scope,
        )

    def create_runner(
        self,
        trigger_type: str = "manual",
        *,
        profile_path: str | Path | None = None,
        batch_id: str | None = None,
        mock_command: bool = False,
    ) -> tuple[MediaCrawlerRunner, MediaCrawlerRunLock, MediaCrawlerRuntimeConfig]:
        config = self.config(trigger_type)
        if profile_path is not None:
            config = replace(config, profile_path=Path(profile_path).resolve())
        builder = MediaCrawlerCommandBuilder(
            python_executable=config.python_executable,
            entry=str(config.entry),
            platform_spec=self.platform_spec,
        )
        profile_manager = MediaCrawlerProfileManager(
            config.runtime_path,
            config.profile_path.parent,
        )
        runtime_profile_manager: BrowserProfileIsolationManager | None = None
        runtime_profile_path: Path | None = None
        runner_profile_path = config.profile_path
        if config.trigger_type == "scheduler" and batch_id is not None:
            # Validate the persistent template before copying it. The
            # template remains immutable; Chromium receives only this copy.
            profile_manager.require(config.trigger_type)
            runtime_profile_manager = BrowserProfileIsolationManager(
                config.runtime_path,
                profile_scope=self._profile_scope,
            )
            runtime_profile_path = runtime_profile_manager.create_runtime_profile(
                config.profile_path,
                batch_id,
            )
            runner_profile_path = runtime_profile_path
            config = replace(config, runtime_profile_path=runtime_profile_path)

        profile_adapter = MediaCrawlerProfileAdapter(
            runtime_root=config.runtime_path,
            platform_spec=self.platform_spec,
            source_key=config.source_key,
            trigger_type=config.trigger_type,
            checkout_root=config.checkout_root,
        )
        profile_binding: MediaCrawlerProfileBinding | None = None

        def prepare_upstream_profile() -> MediaCrawlerProfileBinding:
            nonlocal profile_binding
            if profile_binding is None:
                profile_manager.require(config.trigger_type)
                profile_binding = profile_adapter.prepare(
                    self.platform_spec,
                    runner_profile_path,
                )
                # The profile is prepared lazily so read-only construction
                # still works without a provisioned profile. Update the
                # returned config object once the native view is resolved.
                # The subprocess cwd stays on the upstream checkout root and is
                # set once at runner construction; the adapter only owns the
                # browser/session profile lifecycle, not the working directory.
                object.__setattr__(
                    config,
                    "upstream_profile_path",
                    profile_binding.upstream_profile,
                )
                runner.browser_data = str(profile_binding.upstream_profile)
                runner.profile_name = str(profile_binding.upstream_profile)
                runner.runtime_profile_adapter = profile_adapter
                runner.runtime_profile_binding = profile_binding
            return profile_binding

        def command_factory(keywords: Iterable[str], max_items: int, output_dir: Path) -> list[str]:
            if config.trigger_type == "scheduler" and not config.real_run_gate:
                raise MediaCrawlerRuntimeError(
                    "MediaCrawler scheduler real-run gate is disabled; explicit enablement is required"
                )
            prepare_upstream_profile()
            command_options = getattr(runner, "command_options", {})
            return builder.build(
                keywords=keywords,
                max_items=max_items,
                output_dir=output_dir,
                login_type=config.login_type,
                get_comment=bool(command_options.get("get_comment", False)),
                get_sub_comment=bool(command_options.get("get_sub_comment", False)),
            )

        runner = MediaCrawlerRunner(
            root=config.runtime_path,
            output_root=config.output_root,
            python_executable=config.python_executable,
            browser_data=str(runner_profile_path),
            profile_name=str(runner_profile_path),
            command_factory=command_factory,
            # The upstream entry imports its config relative to the checkout.
            # Keep that checkout as cwd even when the configured entry is a
            # deployment wrapper outside the MediaCrawler root.
            command_cwd=config.checkout_root,
            mock_command=mock_command,
            enable_real_run=config.real_run_gate,
            platform_spec=self.platform_spec,
            source_key=config.source_key,
            artifact_scope=config.artifact_scope,
        )
        # Collector owns cleanup timing because it knows whether the runner
        # and JSONL normalization completed successfully.
        runner.runtime_profile_path = runtime_profile_path
        runner.runtime_profile_manager = runtime_profile_manager
        runner.runtime_profile_adapter = None
        runner.runtime_profile_binding = None
        runner.runtime_config = config
        if self.compatibility_policy is not None:
            lock_path = self.compatibility_policy.lock_path(
                config.output_root,
                source_key=self.source_key,
                platform=self.platform_spec.platform,
            )
        else:
            lock_path = (
                config.output_root
                / "locks"
                / self.platform_spec.platform
                / f"{self.source_key}.lock"
            )
        lock = MediaCrawlerRunLock(lock_path, timeout_seconds=1.0)
        return runner, lock, config
