"""Weibo-only compatibility contract for the legacy MediaCrawler deployment."""
from __future__ import annotations

from app.collectors.mediacrawler_compatibility import MediaCrawlerCompatibilityPolicy
from app.collectors.mediacrawler_platform import WEIBO_PLATFORM_SPEC


WEIBO_SOURCE_KEY = "weibo_mediacrawler"

# The empty scopes intentionally preserve the production legacy layout:
# profiles/{manual,scheduler}, runs/{batch}/..., and locks/{source_key}.lock.
WEIBO_COMPATIBILITY_POLICY = MediaCrawlerCompatibilityPolicy(
    profile_scope=None,
    artifact_scope=None,
    lock_scope=None,
    lock_name_template="{source_key}.lock",
)

__all__ = [
    "WEIBO_COMPATIBILITY_POLICY",
    "WEIBO_PLATFORM_SPEC",
    "WEIBO_SOURCE_KEY",
]
