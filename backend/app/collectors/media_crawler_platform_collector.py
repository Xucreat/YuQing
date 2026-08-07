"""Platform-neutral MediaCrawler Collector lifecycle."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable, Optional

from app.collectors.base import BaseCollector
from app.collectors.mediacrawler_normalizers import (
    get_mediacrawler_normalizer,
    normalize_keywords,
    resolve_effective_keywords,
)
from app.collectors.mediacrawler_platform import (
    MEDIACRAWLER_CAPABILITY,
    MediaCrawlerConfigurationError,
    MediaCrawlerPlatformSpec,
)
from app.collectors.mediacrawler_compatibility import MediaCrawlerCompatibilityPolicy
from app.collectors.mediacrawler_runner import MediaCrawlerRunResult, MediaCrawlerRunner
from app.collectors.mediacrawler_runtime import (
    MediaCrawlerRuntimeError,
    MediaCrawlerRuntimeFactory,
)
from app.collectors.source_config import DataSourceConfig

logger = logging.getLogger(__name__)


class _NoopContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


DEFAULT_MAX_ITEMS = 10


class MediaCrawlerPlatformCollector(BaseCollector):
    """Shared fetch, artifact, error-isolation and normalization lifecycle."""

    collector_capability = MEDIACRAWLER_CAPABILITY
    source_name = "MediaCrawler"
    platform_spec: MediaCrawlerPlatformSpec | None = None
    compatibility_policy: MediaCrawlerCompatibilityPolicy | None = None

    @classmethod
    def build_runtime_factory(
        cls,
        *,
        source_key: str,
        platform_spec: MediaCrawlerPlatformSpec,
        login_type: str | None = None,
        factory_cls: type[MediaCrawlerRuntimeFactory] = MediaCrawlerRuntimeFactory,
    ) -> MediaCrawlerRuntimeFactory:
        if cls.platform_spec is not None and cls.platform_spec.platform != platform_spec.platform:
            raise MediaCrawlerConfigurationError(
                f"collector {cls.__name__} does not support platform "
                f"{platform_spec.platform!r}"
            )
        return factory_cls(
            source_key=source_key,
            platform_spec=platform_spec,
            compatibility_policy=cls.compatibility_policy,
            login_type=login_type,
        )

    def __init__(
        self,
        *,
        platform: str | None = None,
        platform_spec: MediaCrawlerPlatformSpec | None = None,
        data_source_key: str | None = None,
        source_name: str | None = None,
        runner: MediaCrawlerRunner | None = None,
        fixture_path: str | Path | None = None,
        max_items: int | None = None,
        timeout_seconds: int | float | None = None,
        runtime_factory: MediaCrawlerRuntimeFactory | None = None,
        **_: Any,
    ) -> None:
        if platform_spec is None:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerPlatformCollector requires an explicit PlatformSpec"
            )
        if platform and platform not in {
            platform_spec.platform,
            platform_spec.cli_code,
        }:
            raise MediaCrawlerConfigurationError(
                f"collector platform {platform!r} does not match "
                f"spec {platform_spec.platform!r}"
            )
        self.platform_spec = platform_spec
        self.platform = self.platform_spec.platform
        self.normalizer = get_mediacrawler_normalizer(self.platform_spec)
        if not data_source_key:
            raise MediaCrawlerConfigurationError(
                "MediaCrawlerPlatformCollector requires an explicit data_source_key"
            )
        self.data_source_key = str(data_source_key)
        self.source_name = source_name or f"MediaCrawler[{self.platform}]"

        if runner is None and fixture_path is None and runtime_factory is None:
            raise MediaCrawlerRuntimeError("MediaCrawler runtime factory missing")
        runtime_platform_spec = getattr(runtime_factory, "platform_spec", None)
        if (
            runtime_platform_spec is not None
            and runtime_platform_spec.platform != self.platform
        ):
            raise MediaCrawlerConfigurationError(
                "runtime factory PlatformSpec does not match collector PlatformSpec"
            )
        runner_platform_spec = getattr(runner, "platform_spec", None)
        if (
            runner_platform_spec is not None
            and runner_platform_spec.platform != self.platform
        ):
            raise MediaCrawlerConfigurationError(
                "runner PlatformSpec does not match collector PlatformSpec"
            )
        self.runtime_factory = (
            runtime_factory if runner is None and fixture_path is None else None
        )
        self._runtime_lock = None
        self._runtime_trigger_type = "manual"
        self._runtime_batch_id: str | None = None
        if runner is not None:
            self.runner = runner
        elif fixture_path is not None:
            self.runner = MediaCrawlerRunner(
                fixture_path=fixture_path,
                platform_spec=self.platform_spec,
                source_key=self.data_source_key,
            )
        else:
            self.runner = None
        self.max_items = max_items
        self.timeout_seconds = timeout_seconds
        self.effective_max_items: int | None = None
        self.effective_keywords: list[str] = []
        self.effective_keywords_source = "global"
        self.last_run_result: MediaCrawlerRunResult | None = None

    def _ensure_runtime(self, trigger_type: str, batch_id: str | None = None):
        if self.runtime_factory is None:
            if self.runner is None:
                raise MediaCrawlerRuntimeError("MediaCrawler runtime factory missing")
            return self.runner, None
        normalized_trigger = (
            "scheduler" if trigger_type in {"scheduled", "scheduler"} else "manual"
        )
        if (
            normalized_trigger == "scheduler"
            and batch_id is None
            and isinstance(self.runtime_factory, MediaCrawlerRuntimeFactory)
        ):
            raise MediaCrawlerRuntimeError(
                "scheduled MediaCrawler runtime requires a Collector batch_id"
            )
        runtime_batch_changed = (
            normalized_trigger == "scheduler"
            and batch_id is not None
            and batch_id != self._runtime_batch_id
        )
        if (
            self.runner is None
            or normalized_trigger != self._runtime_trigger_type
            or runtime_batch_changed
        ):
            if batch_id is None:
                self.runner, self._runtime_lock, _ = self.runtime_factory.create_runner(
                    normalized_trigger,
                )
            else:
                self.runner, self._runtime_lock, _ = self.runtime_factory.create_runner(
                    normalized_trigger,
                    batch_id=batch_id,
                )
            self._runtime_trigger_type = normalized_trigger
            self._runtime_batch_id = (
                batch_id if normalized_trigger == "scheduler" else None
            )
        return self.runner, self._runtime_lock

    def resolve_effective_keywords(
        self,
        runtime_keywords: Optional[Iterable[Any]] = None,
        global_keywords: Optional[Iterable[Any]] = None,
    ) -> list[str]:
        keywords, source = resolve_effective_keywords(
            runtime_keywords,
            self.source_config,
            global_keywords,
        )
        self.effective_keywords = keywords
        self.effective_keywords_source = source
        return keywords

    def fetch(
        self,
        keywords: Optional[list[str]] = None,
        region_kw: Optional[list[str]] = None,
        topic_kw: Optional[list[str]] = None,
        global_keywords: Optional[list[str]] = None,
        keyword_override: Optional[list[str]] = None,
        trigger_type: str = "manual",
        batch_id: str | None = None,
    ) -> list[dict[str, Any]]:
        del region_kw, topic_kw
        runner, run_lock = self._ensure_runtime(trigger_type, batch_id)
        if keyword_override is not None:
            normalized = normalize_keywords(keyword_override)
            self.effective_keywords = normalized
            self.effective_keywords_source = "round_robin"
        else:
            normalized = self.resolve_effective_keywords(keywords, global_keywords)
        configured_max_items = self.source_config.max_items(
            self.max_items if self.max_items is not None else DEFAULT_MAX_ITEMS
        )
        self.effective_max_items = configured_max_items
        raw_config = self.source_config.raw
        comments = raw_config.get("comments")
        comments = comments if isinstance(comments, dict) else {}
        runner.command_options = {
            "get_comment": bool(
                self.source_config.get_bool(
                    "get_comment",
                    comments.get("enabled", False),
                )
            ),
            "get_sub_comment": bool(
                self.source_config.get_bool(
                    "get_sub_comment",
                    comments.get("sub_comments", False),
                )
            ),
        }
        if run_lock is not None and batch_id:
            runner.initialize_batch_metrics(batch_id)
        lock_context = run_lock if run_lock is not None else _NoopContext()
        with lock_context:
            result = runner.run(
                normalized,
                output_dir=None,
                timeout_seconds=self.timeout_seconds,
                max_items=configured_max_items,
                batch_id=batch_id,
                crawler_config={
                    "max_items": configured_max_items,
                    "effective_keywords_source": self.effective_keywords_source,
                    "selected_keywords": normalized,
                    **runner.command_options,
                },
            )
        try:
            self.last_run_result = result
            MediaCrawlerRunner.append_log(
                result.log_path,
                f"effective_keywords_source={self.effective_keywords_source} "
                f"keywords_count={len(normalized)}",
            )
            items = self._read_jsonl(result)
        except Exception:
            # Failure evidence is intentionally retained for audit.
            raise
        else:
            runtime_profile_path = getattr(runner, "runtime_profile_path", None)
            runtime_profile_manager = getattr(runner, "runtime_profile_manager", None)
            runtime_profile_adapter = getattr(runner, "runtime_profile_adapter", None)
            runtime_profile_binding = getattr(runner, "runtime_profile_binding", None)
            try:
                if (
                    runtime_profile_adapter is not None
                    and runtime_profile_binding is not None
                ):
                    runtime_profile_adapter.cleanup(runtime_profile_binding)
            finally:
                try:
                    if (
                        runtime_profile_path is not None
                        and runtime_profile_manager is not None
                    ):
                        runtime_profile_manager.cleanup_runtime_profile(
                            runtime_profile_path
                        )
                finally:
                    runner.runtime_profile_path = None
                    runner.runtime_profile_manager = None
                    runner.runtime_profile_adapter = None
                    runner.runtime_profile_binding = None
            return items

    def update_batch_metrics(self, **updates: int | str | None) -> Path | None:
        return self.runner.update_metrics(**updates)

    def _read_jsonl(self, result: MediaCrawlerRunResult) -> list[dict[str, Any]]:
        read_count = 0
        parsed_count = 0
        failed_count = 0
        duplicate_count = 0
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            lines = result.output_path.open("r", encoding="utf-8")
        except OSError as exc:
            MediaCrawlerRunner.append_log(
                result.log_path,
                f"jsonl_open_failed error={type(exc).__name__}: {exc}",
            )
            raise

        with lines:
            for line_number, raw_line in enumerate(lines, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                read_count += 1
                try:
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError("JSONL row must be an object")
                    item = self._normalize_row(row)
                    if item is None:
                        raise ValueError("content is empty")
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    failed_count += 1
                    MediaCrawlerRunner.append_log(
                        result.log_path,
                        f"line_failed line={line_number} error={type(exc).__name__}",
                    )
                    continue

                parsed_count += 1
                dedup_key = self._dedup_key(item)
                if dedup_key and dedup_key in seen:
                    duplicate_count += 1
                    continue
                if dedup_key:
                    seen.add(dedup_key)
                items.append(item)

        MediaCrawlerRunner.append_log(
            result.log_path,
            f"batch_id={result.batch_id} read_count={read_count} "
            f"success_count={parsed_count} failed_count={failed_count} "
            f"duplicate_count={duplicate_count} returned_count={len(items)}",
        )
        logger.info(
            "MediaCrawler JSONL parsed platform=%s batch_id=%s jsonl_path=%s "
            "read_count=%s success_count=%s failed_count=%s duplicate_count=%s",
            self.platform,
            result.batch_id,
            result.output_path,
            read_count,
            parsed_count,
            failed_count,
            duplicate_count,
        )
        return items

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any] | None:
        return self.normalizer.normalize(row)

    def _dedup_key(self, item: dict[str, Any]) -> str:
        return self.normalizer.dedup_key(item)
