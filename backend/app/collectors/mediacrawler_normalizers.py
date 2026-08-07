"""Shared MediaCrawler parsing helpers and platform normalizer registry."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from app.collectors.mediacrawler_platform import (
    MediaCrawlerPlatformSpec,
    get_mediacrawler_platform_spec,
)
from app.collectors.source_config import DataSourceConfig


SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_SENTENCE_SPLIT = re.compile(r"[。！？.!?\n]")
_COUNT_RE = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*(万|亿|w|k|千)?$", re.IGNORECASE)
_EPOCH_RE = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?$")


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


def _parse_epoch(value: Any) -> datetime | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
    elif isinstance(value, str) and _EPOCH_RE.fullmatch(value.strip()):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if not (-100_000_000_000_000 < number < 100_000_000_000_000):
        return None
    seconds = number / 1000 if abs(number) >= 100_000_000_000 else number
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return None


def parse_publish_time(value: Any) -> datetime | None:
    epoch = _parse_epoch(value)
    if epoch is not None:
        return epoch
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


def _first_value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and _text(value):
            return value
    return None


def _sanitize_xhs_url(value: Any) -> str | None:
    """Keep public XHS URLs free of request/session query credentials."""

    raw = _text(value)
    if not raw:
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    if not parts.query:
        return raw
    blocked = {"xsec_token", "xsec_source"}
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in blocked
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment)
    )


class MediaCrawlerNormalizer(Protocol):
    def normalize(self, row: dict[str, Any]) -> dict[str, Any] | None:
        ...

    def dedup_key(self, item: dict[str, Any]) -> str:
        ...


class WeiboNormalizer:
    """Preserve the existing Weibo JSONL -> CollectorService contract."""

    def normalize(self, row: dict[str, Any]) -> dict[str, Any] | None:
        content = _text(_first_value(row, "content", "text"))
        if not content:
            return None
        title = _text(_first_value(row, "title")) or first_sentence(content)
        external_id = _text(_first_value(row, "mid", "id", "external_id", "note_id"))
        author = _text(_first_value(row, "nickname", "author"))
        url = _text(_first_value(row, "url", "link", "note_url"))
        engagement = {
            "likes": parse_engagement_count(
                _first_value(row, "likes", "like_count", "liked_count")
            ),
            "comments": parse_engagement_count(
                _first_value(row, "comments", "comments_count")
            ),
            "reposts": parse_engagement_count(
                _first_value(row, "reposts", "repost_count", "shared_count")
            ),
        }
        return {
            "title": title[:512],
            "content": content,
            "source": "weibo",
            "source_type": "weibo_post",
            "url": url,
            "publish_time": parse_publish_time(
                _first_value(
                    row,
                    "publish_time",
                    "created_at",
                    "create_date_time",
                    "create_time",
                )
            ),
            "external_id": external_id,
            "author": author,
            "engagement": engagement,
        }

    @staticmethod
    def dedup_key(item: dict[str, Any]) -> str:
        if item["external_id"]:
            return f"external_id:{item['external_id']}"
        if item["url"]:
            return f"url:{item['url']}"
        if item["content"]:
            return f"content:{item['content']}|{item['publish_time']}"
        return ""


class XhsNormalizer:
    """Normalize the offline XHS skeleton schema without claiming upstream parity."""

    def normalize(self, row: dict[str, Any]) -> dict[str, Any] | None:
        content = _text(_first_value(row, "desc", "content", "text", "description"))
        if not content:
            return None

        title = _text(_first_value(row, "title", "note_title")) or first_sentence(content)
        external_id = _text(_first_value(row, "note_id", "id", "external_id")) or None
        author = _text(_first_value(row, "nickname", "author", "user_nickname")) or None
        url = _sanitize_xhs_url(_first_value(row, "note_url", "url", "link"))
        engagement = {
            "likes": parse_engagement_count(
                _first_value(row, "liked_count", "like_count", "likes")
            ),
            "comments": parse_engagement_count(
                _first_value(row, "comment_count", "comments_count", "comments")
            ),
            "reposts": parse_engagement_count(
                _first_value(row, "share_count", "shared_count", "reposts")
            ),
            "collections": parse_engagement_count(
                _first_value(row, "collected_count", "collect_count", "collections")
            ),
        }
        return {
            "title": title[:512],
            "content": content,
            "source": "xiaohongshu",
            "source_type": "xhs_note",
            "url": url,
            "publish_time": parse_publish_time(
                _first_value(row, "publish_time", "time", "create_time", "created_at")
            ),
            "external_id": external_id,
            "author": author,
            "engagement": engagement,
        }

    @staticmethod
    def dedup_key(item: dict[str, Any]) -> str:
        if item["external_id"]:
            return f"external_id:{item['external_id']}"
        if item["url"]:
            return f"url:{item['url']}"
        if item["content"]:
            return f"content:{item['content']}|{item['publish_time']}"
        return ""


_NORMALIZERS: dict[str, MediaCrawlerNormalizer] = {
    "weibo": WeiboNormalizer(),
    "xiaohongshu": XhsNormalizer(),
}


def get_mediacrawler_normalizer(
    platform: str | MediaCrawlerPlatformSpec,
) -> MediaCrawlerNormalizer:
    spec = (
        platform
        if isinstance(platform, MediaCrawlerPlatformSpec)
        else get_mediacrawler_platform_spec(platform)
    )
    try:
        return _NORMALIZERS[spec.normalizer_key]
    except KeyError as exc:
        raise ValueError(
            f"no MediaCrawler normalizer registered for platform: {spec.platform}"
        ) from exc
