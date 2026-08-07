"""Platform contracts for the MediaCrawler collector family.

The registry is deliberately explicit so adding a future platform requires a
spec and a normalizer instead of silently falling through to Weibo semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MEDIACRAWLER_CAPABILITY = "mediacrawler"
SUPPORTED_LOGIN_TYPES = frozenset({"cookie", "qrcode"})


class MediaCrawlerConfigurationError(ValueError):
    """Raised when a MediaCrawler platform contract is incomplete or invalid."""


@dataclass(frozen=True)
class MediaCrawlerPlatformSpec:
    """Versioned contract for one MediaCrawler platform."""

    platform: str
    cli_code: str
    crawler_type: str
    artifact_name: str
    native_output_parts: tuple[str, ...]
    source: str
    source_type: str
    normalizer_key: str
    capabilities: frozenset[str] = frozenset()
    supported_login_types: frozenset[str] = SUPPORTED_LOGIN_TYPES
    allow_real_collection: bool = False
    supported_crawler_types: tuple[str, ...] = ()
    default_crawler_type: str | None = None
    upstream_profile_parts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        legacy_type = str(self.crawler_type or "").strip().lower()
        supported = tuple(
            dict.fromkeys(
                str(value).strip().lower()
                for value in self.supported_crawler_types
                if str(value).strip()
            )
        )
        if not supported and legacy_type and legacy_type != "unknown":
            supported = (legacy_type,)
        default = str(self.default_crawler_type or "").strip().lower() or None
        if default is None and legacy_type in supported:
            default = legacy_type
        if default is not None and default not in supported:
            raise MediaCrawlerConfigurationError(
                f"default crawler type {default!r} is not supported for {self.platform}"
            )
        object.__setattr__(self, "supported_crawler_types", supported)
        object.__setattr__(self, "default_crawler_type", default)

    def validate_login_type(self, login_type: str) -> str:
        value = str(login_type or "").strip().lower()
        if value not in self.supported_login_types:
            allowed = ", ".join(sorted(self.supported_login_types))
            raise ValueError(
                f"invalid MediaCrawler login_type for {self.platform}: "
                f"{value!r}; allowed: {allowed}"
            )
        return value

    def validate_crawler_type(self, crawler_type: str | None = None) -> str:
        """Resolve a native crawler mode and fail closed for unknown values."""

        value = str(crawler_type or self.default_crawler_type or "").strip().lower()
        if not self.supported_crawler_types or not self.default_crawler_type:
            raise MediaCrawlerConfigurationError(
                f"MediaCrawler crawler mode contract is unresolved for {self.platform}"
            )
        if value not in self.supported_crawler_types:
            allowed = ", ".join(self.supported_crawler_types)
            raise ValueError(
                f"invalid MediaCrawler crawler_type for {self.platform}: "
                f"{value!r}; allowed: {allowed}"
            )
        return value


WEIBO_PLATFORM_SPEC = MediaCrawlerPlatformSpec(
    platform="weibo",
    cli_code="wb",
    crawler_type="search",
    artifact_name="weibo",
    native_output_parts=("weibo", "jsonl"),
    source="weibo",
    source_type="weibo_post",
    normalizer_key="weibo",
    capabilities=frozenset({"keyword_rotation", "jsonl", "search"}),
    allow_real_collection=True,
    supported_crawler_types=("search",),
    default_crawler_type="search",
)


# The upstream XHS contract was verified against the pinned MediaCrawler
# checkout in Phase-2-C1.  ``artifact_name`` remains an application label;
# ``upstream_profile_parts`` describes the native relative browser path.
XHS_PLATFORM_SPEC = MediaCrawlerPlatformSpec(
    platform="xiaohongshu",
    cli_code="xhs",
    crawler_type="search",
    artifact_name="xiaohongshu",
    native_output_parts=("xhs", "jsonl"),
    source="xiaohongshu",
    source_type="xhs_note",
    normalizer_key="xiaohongshu",
    capabilities=frozenset({"jsonl", "search", "detail", "creator", "comments"}),
    supported_login_types=frozenset({"qrcode", "phone", "cookie"}),
    # Real execution remains protected by the global enable/gate settings and
    # the scheduler's explicit disabled-by-default registration payload.
    allow_real_collection=True,
    supported_crawler_types=("search", "detail", "creator"),
    default_crawler_type="search",
    upstream_profile_parts=("browser_data", "xhs_user_data_dir"),
)


_PLATFORM_SPECS: dict[str, MediaCrawlerPlatformSpec] = {
    WEIBO_PLATFORM_SPEC.platform: WEIBO_PLATFORM_SPEC,
    XHS_PLATFORM_SPEC.platform: XHS_PLATFORM_SPEC,
}


def get_mediacrawler_platform_spec(platform: str | None) -> MediaCrawlerPlatformSpec:
    """Resolve a registered platform or fail closed for unknown values."""

    value = str(platform or "").strip().lower()
    if not value:
        raise MediaCrawlerConfigurationError(
            "MediaCrawler platform must be explicit"
        )
    try:
        return _PLATFORM_SPECS[value]
    except KeyError as exc:
        allowed = ", ".join(sorted(_PLATFORM_SPECS))
        raise MediaCrawlerConfigurationError(
            f"unknown MediaCrawler platform: {value!r}; registered platforms: {allowed}"
        ) from exc


def registered_mediacrawler_platforms() -> tuple[str, ...]:
    return tuple(sorted(_PLATFORM_SPECS))


def is_mediacrawler_collector(cls: type[Any]) -> bool:
    return getattr(cls, "collector_capability", None) == MEDIACRAWLER_CAPABILITY


MEDIACRAWLER_CONFIG_KEYS = frozenset(
    {
        "schema_version",
        "collector",
        "platform",
        "crawler_type",
        "login_type",
        "keywords",
        "max_items",
        "get_comment",
        "get_sub_comment",
        "collection_scope",
        "collection_mode",
        "filter_mode",
        "keyword_scope",
        "content_type",
        "comments",
        "platform_options",
    }
)

FORBIDDEN_MEDIACRAWLER_CONFIG_KEYS = frozenset(
    {
        "command",
        "command_factory",
        "shell_command",
        "cookie",
        "cookies",
        "token",
        "password",
        "authorization",
        "browser_data",
        "profile_path",
        "python_executable",
        "entry",
    }
)
