"""Backward-compatible Weibo facade for the MediaCrawler platform collector."""
from __future__ import annotations

from app.collectors.media_crawler_platform_collector import (
    MediaCrawlerPlatformCollector,
)
from app.collectors.mediacrawler_weibo_compatibility import (
    WEIBO_COMPATIBILITY_POLICY,
    WEIBO_PLATFORM_SPEC,
    WEIBO_SOURCE_KEY,
)
from app.collectors.mediacrawler_normalizers import (
    first_sentence,
    get_mediacrawler_normalizer,
    normalize_keywords,
    parse_engagement_count,
    parse_publish_time,
    resolve_effective_keywords,
)


class MediaCrawlerWeiboCollector(MediaCrawlerPlatformCollector):
    """Keep the production class path stable while using the shared core."""

    source_name = "微博（MediaCrawler）"
    data_source_key = WEIBO_SOURCE_KEY
    platform = WEIBO_PLATFORM_SPEC.platform
    platform_spec = WEIBO_PLATFORM_SPEC
    compatibility_policy = WEIBO_COMPATIBILITY_POLICY

    def __init__(self, **kwargs):
        kwargs.pop("platform", None)
        kwargs.pop("data_source_key", None)
        kwargs.pop("source_name", None)
        kwargs.pop("platform_spec", None)
        super().__init__(
            platform_spec=WEIBO_PLATFORM_SPEC,
            data_source_key=WEIBO_SOURCE_KEY,
            source_name=self.source_name,
            **kwargs,
        )

    @staticmethod
    def _normalize_row(row):
        return get_mediacrawler_normalizer(WEIBO_PLATFORM_SPEC).normalize(row)

    @staticmethod
    def _dedup_key(item):
        return get_mediacrawler_normalizer(WEIBO_PLATFORM_SPEC).dedup_key(item)


__all__ = [
    "MediaCrawlerWeiboCollector",
    "first_sentence",
    "normalize_keywords",
    "parse_engagement_count",
    "parse_publish_time",
    "resolve_effective_keywords",
]
