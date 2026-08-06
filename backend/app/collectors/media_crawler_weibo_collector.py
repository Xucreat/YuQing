"""Offline JSONL adapter for MediaCrawler Weibo posts."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from app.collectors.base import BaseCollector
from app.collectors.mediacrawler_runner import MediaCrawlerRunner, MediaCrawlerRunResult
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
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

_SENTENCE_SPLIT = re.compile(r"[。！？.!?\n]")
_COUNT_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*(万|亿|w|k|千)?$", re.IGNORECASE)


def normalize_keywords(keywords: Optional[Iterable[Any]]) -> list[str]:
    """Remove blanks and duplicates while preserving the caller's order."""

    if keywords is None:
        return []
    if isinstance(keywords, str):
        keywords = [keywords]
    result: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        if keyword is None:
            continue
        value = str(keyword).strip()
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def resolve_effective_keywords(
    runtime_keywords: Optional[Iterable[Any]],
    source_config: DataSourceConfig | dict[str, Any] | None,
    global_keywords: Optional[Iterable[Any]] = None,
) -> tuple[list[str], str]:
    """Resolve MediaCrawler keywords without changing other collector contracts.

    DataSource-local keywords are authoritative.  ``runtime_keywords`` is the
    explicit caller value, while ``global_keywords`` is the service fallback.
    """

    if isinstance(source_config, DataSourceConfig):
        raw_config = source_config.raw
    elif isinstance(source_config, dict):
        raw_config = source_config
    else:
        raw_config = {}

    source_keywords = normalize_keywords(raw_config.get("keywords"))
    if source_keywords:
        return source_keywords, "datasource"

    explicit_keywords = normalize_keywords(runtime_keywords)
    if explicit_keywords:
        return explicit_keywords, "runtime"

    return normalize_keywords(global_keywords), "global"


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and _text(value):
            return value
    return None


def first_sentence(content: str, limit: int = 100) -> str:
    for segment in _SENTENCE_SPLIT.split(content):
        segment = segment.strip()
        if segment:
            return segment[:limit]
    return content.strip()[:limit]


def parse_engagement_count(value: Any) -> int:
    """Convert numeric, comma-separated and Chinese-unit counts to integers."""

    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, float, Decimal)):
        return max(0, int(value))
    match = _COUNT_RE.match(_text(value).replace(",", ""))
    if not match:
        return 0
    try:
        number = Decimal(match.group(1))
    except InvalidOperation:
        return 0
    unit = (match.group(2) or "").lower()
    multiplier = {
        "万": 10_000,
        "亿": 100_000_000,
        "w": 10_000,
        "k": 1_000,
        "千": 1_000,
    }.get(unit, 1)
    return max(0, int(number * multiplier))


def parse_publish_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=SHANGHAI_TZ)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    raw = _text(value)
    if not raw:
        return None
    for candidate in (raw.replace("Z", "+00:00"), raw):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=SHANGHAI_TZ)
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ):
        try:
            parsed = datetime.strptime(raw, fmt).replace(tzinfo=SHANGHAI_TZ)
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    return None


class MediaCrawlerWeiboCollector(BaseCollector):
    """Read MediaCrawler JSONL output and emit CollectorService dicts."""

    source_name = "微博（MediaCrawler）"
    data_source_key = "weibo_mediacrawler"

    def __init__(
        self,
        *,
        runner: MediaCrawlerRunner | None = None,
        fixture_path: str | Path | None = None,
        max_items: int | None = None,
        timeout_seconds: int | float | None = None,
        runtime_factory: MediaCrawlerRuntimeFactory | None = None,
        **_: Any,
    ) -> None:
        if runner is None and fixture_path is None and runtime_factory is None:
            raise MediaCrawlerRuntimeError("MediaCrawler runtime factory missing")
        self.runtime_factory = runtime_factory if runner is None and fixture_path is None else None
        self._runtime_lock = None
        self._runtime_trigger_type = "manual"
        self._runtime_batch_id: str | None = None
        if runner is not None:
            self.runner = runner
        elif fixture_path is not None:
            self.runner = MediaCrawlerRunner(fixture_path=fixture_path)
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
        normalized_trigger = "scheduler" if trigger_type in {"scheduled", "scheduler"} else "manual"
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
        if self.runner is None or normalized_trigger != self._runtime_trigger_type or runtime_batch_changed:
            if batch_id is None:
                # Preserve the lightweight factory contract used by older
                # fixtures and manual callers.
                self.runner, self._runtime_lock, _ = self.runtime_factory.create_runner(
                    normalized_trigger,
                )
            else:
                self.runner, self._runtime_lock, _ = self.runtime_factory.create_runner(
                    normalized_trigger,
                    batch_id=batch_id,
                )
            self._runtime_trigger_type = normalized_trigger
            self._runtime_batch_id = batch_id if normalized_trigger == "scheduler" else None
        return self.runner, self._runtime_lock

    def resolve_effective_keywords(
        self,
        runtime_keywords: Optional[Iterable[Any]] = None,
        global_keywords: Optional[Iterable[Any]] = None,
    ) -> list[str]:
        """Set and return the effective keyword list for this source."""

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
            if runtime_profile_path is not None and runtime_profile_manager is not None:
                try:
                    runtime_profile_manager.cleanup_runtime_profile(runtime_profile_path)
                finally:
                    runner.runtime_profile_path = None
                    runner.runtime_profile_manager = None
            return items

    def update_batch_metrics(self, **updates: int | str | None) -> Path | None:
        """Persist CollectorService counters beside this batch's JSONL output."""

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
            "MediaCrawler JSONL parsed batch_id=%s jsonl_path=%s read_count=%s "
            "success_count=%s failed_count=%s duplicate_count=%s",
            result.batch_id,
            result.output_path,
            read_count,
            parsed_count,
            failed_count,
            duplicate_count,
        )
        return items

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
        content = _text(_first_value(row, "content", "text"))
        if not content:
            return None
        title = _text(_first_value(row, "title")) or first_sentence(content)
        external_id = _text(_first_value(row, "mid", "id", "external_id", "note_id"))
        author = _text(_first_value(row, "nickname", "author"))
        url = _text(_first_value(row, "url", "link", "note_url"))
        engagement = {
            "likes": parse_engagement_count(_first_value(row, "likes", "like_count", "liked_count")),
            "comments": parse_engagement_count(_first_value(row, "comments", "comments_count")),
            "reposts": parse_engagement_count(_first_value(row, "reposts", "repost_count", "shared_count")),
        }
        return {
            "title": title[:512],
            "content": content,
            "source": "weibo",
            "source_type": "weibo_post",
            "url": url,
            "publish_time": parse_publish_time(
                _first_value(row, "publish_time", "created_at", "create_date_time", "create_time")
            ),
            "external_id": external_id,
            "author": author,
            "engagement": engagement,
        }

    @staticmethod
    def _dedup_key(item: dict[str, Any]) -> str:
        if item["external_id"]:
            return f"external_id:{item['external_id']}"
        if item["url"]:
            return f"url:{item['url']}"
        if item["content"]:
            return f"content:{item['content']}|{item['publish_time']}"
        return ""
