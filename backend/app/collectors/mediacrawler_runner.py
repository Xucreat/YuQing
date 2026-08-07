"""Offline-safe runner boundary for MediaCrawler.

The first integration phase deliberately has no default crawler command. A
caller must inject either a fixture path or an explicit mock command, which
keeps importing and testing this module disconnected from Weibo.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from app.core.config import settings
from app.collectors.mediacrawler_batch import MediaCrawlerBatchLocator
from app.collectors.mediacrawler_platform import (
    MediaCrawlerConfigurationError,
    MediaCrawlerPlatformSpec,
)


class MediaCrawlerRunnerError(RuntimeError):
    """Base error for a failed or incorrectly configured runner invocation."""


class MediaCrawlerRunnerConfigurationError(MediaCrawlerRunnerError):
    """Raised when neither fixture mode nor an explicit command is configured."""


class MediaCrawlerTimeoutError(MediaCrawlerRunnerError):
    """Raised when the subprocess exceeds its configured timeout."""


class MediaCrawlerProcessError(MediaCrawlerRunnerError):
    """Raised when the subprocess exits unsuccessfully or emits no output."""

    def __init__(self, message: str, *, stderr: str = "", exit_code: int | None = None) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code


class MediaCrawlerEmptyOutputError(MediaCrawlerProcessError):
    """Raised when native raw records cannot produce bounded output."""


class MediaCrawlerRealRunDisabledError(MediaCrawlerRunnerError):
    """Raised when a real subprocess is requested without explicit opt-in."""


@dataclass(frozen=True)
class MediaCrawlerRunResult:
    """Paths and process status for one isolated runner invocation."""

    batch_id: str
    run_dir: Path
    output_path: Path
    log_path: Path
    exit_code: int
    timed_out: bool = False
    stderr: str = ""
    native_output_path: Path | None = None
    raw_output_path: Path | None = None
    raw_count: int | None = None
    output_count: int | None = None
    effective_max_items: int | None = None
    metrics_path: Path | None = None

    @property
    def jsonl_path(self) -> Path:
        return self.output_path


_SECRET_RE = re.compile(
    r"(?i)(xsec[_-]?token|xsec[_-]?source|cookie|password|token|authorization|browser[_ -]?data)\s*[:=]\s*[^\s,;]+"
)
_STRUCTURED_SECRET_RE = re.compile(
    r"""(?ix)
    (["']?)
    (xsec[_-]?token|xsec[_-]?source|cookie|password|token|authorization|browser[_ -]?data)
    (["']?\s*:\s*["']?)
    [^"',\s}]+
    """
)


def _redact(value: str) -> str:
    value = _SECRET_RE.sub(r"\1=[REDACTED]", value)
    return _STRUCTURED_SECRET_RE.sub(r"\1\2\3[REDACTED]", value)


class MediaCrawlerRunner:
    """Create an isolated run directory and execute an injected command.

    ``fixture_path`` is the offline mode used by Phase MediaCrawler-1A.
    ``command`` is reserved for a mock or future adapter command and is never
    inferred from configuration, so this class cannot start MediaCrawler by
    accident.
    """

    def __init__(
        self,
        *,
        root: str | Path | None = None,
        output_root: str | Path | None = None,
        python_executable: str | None = None,
        browser_data: str | None = None,
        profile_name: str | None = None,
        command: Sequence[str] | None = None,
        command_factory: Callable[[Sequence[str], int, Path], Sequence[str]] | None = None,
        command_cwd: str | Path | None = None,
        fixture_path: str | Path | None = None,
        mock_command: bool = True,
        enable_real_run: bool | None = None,
        platform_spec: MediaCrawlerPlatformSpec | None = None,
        source_key: str | None = None,
        artifact_scope: str | None = None,
    ) -> None:
        if platform_spec is None:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerRunner requires an explicit PlatformSpec"
            )
        if not source_key:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerRunner requires an explicit source_key"
            )
        configured_root = (
            output_root
            or root
            or settings.media_crawler_root
            or "runtime/mediacrawler"
        )
        self.output_root = Path(configured_root)
        # ``root`` remains the public compatibility name for artifact callers.
        self.root = self.output_root
        self.platform_spec = platform_spec
        self.batch_locator = MediaCrawlerBatchLocator(
            self.output_root,
            platform_spec=platform_spec,
        )
        self.artifact_name = platform_spec.artifact_name
        self.native_output_parts = tuple(platform_spec.native_output_parts)
        self.artifact_scope = artifact_scope
        self.platform = platform_spec.platform
        self.source_key = str(source_key)
        self.python_executable = python_executable or settings.media_crawler_python or sys.executable
        self.browser_data = browser_data or settings.media_crawler_browser_data or ""
        # The upstream MediaCrawler entry reads MEDIA_CRAWLER_PROFILE_NAME and
        # maps it to config.USER_DATA_DIR. Keep this separate from the legacy
        # browser-data variable, which the upstream entry does not consume.
        self.profile_name = str(profile_name or "")
        self.command_options: dict[str, bool] = {}
        self.command = list(command) if command is not None else None
        self.command_factory = command_factory
        self.command_cwd = Path(command_cwd) if command_cwd else None
        self.fixture_path = Path(fixture_path) if fixture_path else None
        self.mock_command = bool(mock_command)
        self.enable_real_run = (
            settings.media_crawler_enable_real_run
            if enable_real_run is None
            else bool(enable_real_run)
        )
        self.last_batch_id: str | None = None
        self.last_metrics_path: Path | None = None

    @staticmethod
    def append_log(log_path: Path, message: str) -> None:
        """Append one sanitized line without exposing credentials."""

        log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} {_redact(message)}\n")

    def _write_metrics(self, **updates: int | str | None) -> Path:
        """Persist auditable counters for the current batch without DB writes."""

        if self.last_batch_id is None or self.last_metrics_path is None:
            raise MediaCrawlerRunnerError("MediaCrawler batch metrics are not initialized")
        payload: dict[str, Any] = {
            "batch_id": self.last_batch_id,
            "collector": "mediacrawler",
            "platform": self.platform,
            "source_key": self.source_key,
            "raw_count": 0,
            "output_count": 0,
            "effective_max_items": 0,
            "created": 0,
            "duplicate": 0,
            "admission_filtered": 0,
            "filter_skipped": 0,
            "failed": 0,
        }
        if self.last_metrics_path.is_file():
            try:
                existing = json.loads(self.last_metrics_path.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    payload.update(existing)
            except (OSError, ValueError):
                pass
        payload.update({key: value for key, value in updates.items() if value is not None})
        payload["batch_id"] = self.last_batch_id
        payload["collector"] = "mediacrawler"
        payload["platform"] = self.platform
        payload["source_key"] = self.source_key
        for key in (
            "raw_count",
            "output_count",
            "effective_max_items",
            "created",
            "duplicate",
            "admission_filtered",
            "filter_skipped",
            "failed",
        ):
            payload[key] = int(payload.get(key) or 0)
        self.last_metrics_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.last_metrics_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self.last_metrics_path)
        return self.last_metrics_path

    def update_metrics(self, **updates: int | str | None) -> Path | None:
        """Update counters after CollectorService admission/analysis completes."""

        if self.last_metrics_path is None:
            return None
        return self._write_metrics(**updates)

    def initialize_batch_metrics(self, batch_id: str) -> Path:
        """Create the metrics envelope before a pre-run failure (for example a lock conflict)."""

        self.last_batch_id = batch_id
        self.last_metrics_path = self.batch_locator.locate(
            batch_id,
            artifact_scope=self.artifact_scope,
        ).metrics_path
        return self._write_metrics()

    def _prepare_paths(
        self, output_dir: str | Path | None, batch_id_override: str | None = None
    ) -> tuple[str, Path, Path, Path, Path]:
        if output_dir is None:
            batch_id = batch_id_override or uuid.uuid4().hex
            run_dir = self.batch_locator.locate(
                batch_id,
                artifact_scope=self.artifact_scope,
            ).run_dir
            output_path_dir = run_dir / "output"
        else:
            output_path_dir = Path(output_dir)
            run_dir = output_path_dir.parent
            batch_id = run_dir.name or uuid.uuid4().hex
        config_dir = run_dir / "config"
        output_path_dir.mkdir(parents=True, exist_ok=True)
        config_dir.mkdir(parents=True, exist_ok=True)
        log_path = run_dir / "crawler.log"
        output_path = output_path_dir / f"{self.artifact_name}.jsonl"
        return batch_id, run_dir, config_dir, output_path, log_path

    @staticmethod
    def _snapshot_jsonl(run_dir: Path) -> dict[Path, tuple[int, int]]:
        snapshot: dict[Path, tuple[int, int]] = {}
        for path in run_dir.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[path] = (stat.st_mtime_ns, stat.st_size)
        return snapshot

    @staticmethod
    def _write_bounded_jsonl(
        source_path: Path,
        output_path: Path,
        max_items: int | None,
    ) -> tuple[int, int]:
        """Preserve source JSONL and write a bounded standard JSONL copy."""

        raw_count = 0
        output_count = 0
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with source_path.open("rb") as source, output_path.open("wb") as output:
            for line in source:
                if not line.strip():
                    continue
                raw_count += 1
                if max_items is None or output_count < max_items:
                    output.write(line)
                    output_count += 1
        return raw_count, output_count

    @staticmethod
    def _raise_on_empty_bounded_output(
        raw_count: int, output_count: int, log_path: Path
    ) -> None:
        if raw_count > 0 and output_count == 0:
            MediaCrawlerRunner.append_log(
                log_path,
                f"empty_output=1 raw_count={raw_count} output_count={output_count}",
            )
            raise MediaCrawlerEmptyOutputError(
                "MediaCrawler produced raw records but no bounded output",
            )

    @staticmethod
    def _preserve_raw(
        source_path: Path,
        run_dir: Path,
        artifact_name: str,
    ) -> Path:
        raw_path = run_dir / "raw" / f"{artifact_name}.jsonl"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != raw_path.resolve():
            shutil.copyfile(source_path, raw_path)
        return raw_path

    @staticmethod
    def _discover_native_output(
        run_dir: Path,
        output_path: Path,
        before: dict[Path, tuple[int, int]],
        started_ns: int,
        native_output_path: Path | None = None,
        native_output_parts: tuple[str, ...] = (),
    ) -> Path | None:
        native_root = native_output_path or output_path.parent
        native_dir = native_root.joinpath(*native_output_parts)
        candidates = list(native_dir.glob("*.jsonl")) if native_dir.is_dir() else []
        if not candidates:
            candidates = list(run_dir.rglob("*.jsonl"))
        candidates = [path for path in candidates if path != output_path]

        changed: list[Path] = []
        for path in candidates:
            try:
                stat = path.stat()
            except OSError:
                continue
            prior = before.get(path)
            if prior is None or (stat.st_mtime_ns, stat.st_size) != prior or stat.st_mtime_ns >= started_ns:
                changed.append(path)
        content_candidates = [
            path for path in changed if "_contents_" in path.name.lower()
        ]
        if content_candidates:
            changed = content_candidates
        return max(changed, key=lambda path: path.stat().st_mtime_ns) if changed else None

    def run(
        self,
        keywords: Sequence[str],
        output_dir: str | Path | None = None,
        timeout_seconds: int | float | None = None,
        max_items: int | None = None,
        crawler_config: dict[str, Any] | None = None,
        native_output_path: str | Path | None = None,
        batch_id: str | None = None,
    ) -> MediaCrawlerRunResult:
        """Run fixture/mock MediaCrawler and return the produced JSONL path."""

        batch_id, run_dir, config_dir, output_path, log_path = self._prepare_paths(
            output_dir, batch_id
        )
        self.last_batch_id = batch_id
        self.last_metrics_path = self.batch_locator.locate(
            batch_id,
            artifact_scope=self.artifact_scope,
        ).metrics_path
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.media_crawler_timeout_seconds
        )
        if timeout is None or float(timeout) <= 0:
            raise MediaCrawlerRunnerConfigurationError("timeout_seconds must be greater than zero")
        if max_items is not None and (
            isinstance(max_items, bool)
            or not isinstance(max_items, int)
            or max_items < 1
            or max_items > 20
        ):
            raise MediaCrawlerRunnerConfigurationError("max_items must be between 1 and 20")

        effective_max_items = max_items
        self._write_metrics(effective_max_items=effective_max_items)

        normalized_keywords = [str(item).strip() for item in keywords if str(item).strip()]
        config_path = config_dir / "crawler.json"
        config_path.write_text(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "keywords": normalized_keywords,
                    "max_items": max_items,
                    "crawler_config": crawler_config or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self.append_log(
            log_path,
            f"batch_id={batch_id} keywords_count={len(normalized_keywords)} "
            f"jsonl_path={output_path} timeout_seconds={timeout}",
        )

        if self.fixture_path is not None:
            if not self.fixture_path.is_file():
                message = f"fixture not found: {self.fixture_path}"
                self.append_log(log_path, message)
                self.update_metrics(failed=1)
                raise MediaCrawlerProcessError(message)
            raw_output_path = self._preserve_raw(
                self.fixture_path,
                run_dir,
                self.artifact_name,
            )
            raw_count, output_count = self._write_bounded_jsonl(
                raw_output_path,
                output_path,
                max_items,
            )
            self.append_log(log_path, f"fixture_mode=1 exit_code=0 source={self.fixture_path}")
            self.append_log(log_path, f"raw_count={raw_count} output_count={output_count}")
            self.update_metrics(raw_count=raw_count, output_count=output_count)
            if raw_count > 0 and output_count == 0:
                self.update_metrics(failed=1)
            self._raise_on_empty_bounded_output(raw_count, output_count, log_path)
            return MediaCrawlerRunResult(
                batch_id,
                run_dir,
                output_path,
                log_path,
                0,
                raw_output_path=raw_output_path,
                raw_count=raw_count,
                output_count=output_count,
                effective_max_items=effective_max_items,
                metrics_path=self.last_metrics_path,
            )

        command: list[str] | None = list(self.command) if self.command else None
        if command is None and self.command_factory is not None:
            try:
                command = list(self.command_factory(normalized_keywords, int(max_items or 0), output_path.parent))
            except MediaCrawlerRunnerError:
                self.update_metrics(failed=1)
                raise
            except Exception as exc:
                message = f"unable to build MediaCrawler command: {exc}"
                self.append_log(log_path, message)
                self.update_metrics(failed=1)
                raise MediaCrawlerRunnerConfigurationError(message) from exc

        if not command:
            message = "no MediaCrawler command configured; use fixture_path or an explicit mock command"
            self.append_log(log_path, message)
            self.update_metrics(failed=1)
            raise MediaCrawlerRunnerConfigurationError(message)

        if not self.mock_command and not self.enable_real_run:
            message = (
                "real MediaCrawler run is disabled; set "
                "MEDIA_CRAWLER_ENABLE_REAL_RUN=true and trigger it explicitly"
            )
            self.append_log(log_path, "real_run_blocked=1")
            self.update_metrics(failed=1)
            raise MediaCrawlerRealRunDisabledError(message)
        if not self.mock_command and not self.platform_spec.allow_real_collection:
            message = (
                "real MediaCrawler collection is disabled by PlatformSpec: "
                f"{self.platform_spec.platform}"
            )
            self.append_log(log_path, "platform_real_run_blocked=1")
            self.update_metrics(failed=1)
            raise MediaCrawlerRealRunDisabledError(message)

        if command[0] == "__MEDIA_CRAWLER_PYTHON__":
            command[0] = self.python_executable
        environment = os.environ.copy()
        environment.update(
            {
                "MEDIA_CRAWLER_BATCH_ID": batch_id,
                "MEDIA_CRAWLER_OUTPUT": str(output_path),
                "MEDIA_CRAWLER_OUTPUT_DIR": str(output_path.parent),
                "MEDIA_CRAWLER_KEYWORDS": json.dumps(normalized_keywords, ensure_ascii=False),
                "MEDIA_CRAWLER_CONFIG": str(config_path),
            }
        )
        if self.browser_data:
            environment["MEDIA_CRAWLER_BROWSER_DATA"] = self.browser_data
        if self.profile_name:
            environment["MEDIA_CRAWLER_PROFILE_NAME"] = self.profile_name

        configured_native_path: Path | None = None
        if native_output_path is not None:
            configured_native_path = Path(native_output_path)
            if not configured_native_path.is_absolute():
                configured_native_path = run_dir / configured_native_path

        command_kind = "mock" if self.mock_command else "real"
        jsonl_snapshot = self._snapshot_jsonl(run_dir)
        process_started_ns = time.time_ns()
        self.append_log(log_path, f"{command_kind}_command_started executable={command[0]}")
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.command_cwd or run_dir),
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=float(timeout),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = _redact((exc.stderr or "") if isinstance(exc.stderr, str) else "")
            self.append_log(log_path, f"timeout=1 stderr={stderr[:1000]}")
            self.update_metrics(failed=1)
            raise MediaCrawlerTimeoutError(
                f"MediaCrawler command timed out after {timeout} seconds"
            ) from exc
        except OSError as exc:
            self.append_log(log_path, f"process_start_failed error={type(exc).__name__}: {exc}")
            self.update_metrics(failed=1)
            raise MediaCrawlerProcessError(f"unable to start MediaCrawler command: {exc}") from exc

        stderr = _redact(completed.stderr or "")
        if stderr:
            self.append_log(log_path, f"stderr={stderr[:4000]}")
        self.append_log(
            log_path,
            f"{command_kind}_command_finished exit_code={completed.returncode}",
        )
        if completed.returncode != 0:
            self.update_metrics(failed=1)
            raise MediaCrawlerProcessError(
                f"MediaCrawler command exited with code {completed.returncode}",
                stderr=stderr,
                exit_code=completed.returncode,
            )
        if not output_path.is_file():
            discovered_native_output = self._discover_native_output(
                run_dir,
                output_path,
                jsonl_snapshot,
                process_started_ns,
                configured_native_path,
                self.native_output_parts,
            )
            if discovered_native_output is not None:
                self.append_log(
                    log_path,
                    f"native_output_path={discovered_native_output} normalized_output={output_path}",
                )
        else:
            discovered_native_output = None

        if discovered_native_output is None and not output_path.is_file():
            self.update_metrics(failed=1)
            raise MediaCrawlerProcessError(
                f"MediaCrawler command exited successfully but did not create {output_path}",
                stderr=stderr,
                exit_code=completed.returncode,
            )

        source_path = discovered_native_output or output_path
        raw_output_path = self._preserve_raw(
            source_path,
            run_dir,
            self.artifact_name,
        )
        raw_count, output_count = self._write_bounded_jsonl(
            raw_output_path,
            output_path,
            max_items,
        )
        self.append_log(log_path, f"raw_count={raw_count} output_count={output_count}")
        self.update_metrics(raw_count=raw_count, output_count=output_count)
        if raw_count > 0 and output_count == 0:
            self.update_metrics(failed=1)
        self._raise_on_empty_bounded_output(raw_count, output_count, log_path)

        return MediaCrawlerRunResult(
            batch_id=batch_id,
            run_dir=run_dir,
            output_path=output_path,
            log_path=log_path,
            exit_code=completed.returncode,
            stderr=stderr,
            native_output_path=discovered_native_output,
            raw_output_path=raw_output_path,
            raw_count=raw_count,
            output_count=output_count,
            effective_max_items=effective_max_items,
            metrics_path=self.last_metrics_path,
        )
