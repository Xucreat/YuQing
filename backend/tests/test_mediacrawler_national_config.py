from __future__ import annotations

import pytest

from app.collectors.source_config import (
    DataSourceConfig,
    validate_data_source_config,
    validate_mediacrawler_region_contract,
)
from scripts.migrate_social_sources_national import _reconcile_national_strategy


def test_national_keyword_scope_accepts_legacy_topic_only_alias() -> None:
    config = {
        "collector": "mediacrawler",
        "platform": "xiaohongshu",
        "collection_scope": "national",
        "collection_mode": "national",
        "keyword_scope": "topic_only",
    }

    assert validate_data_source_config(config) == config
    assert DataSourceConfig(config).keyword_scope() == "topic"


def test_national_media_crawler_accepts_region_keyword_strategy() -> None:
    config = {
        "collector": "mediacrawler",
        "platform": "xiaohongshu",
        "collection_scope": "national",
        "collection_mode": "national",
        "filter_mode": "region_or_topic",
        "keyword_scope": "region_topic",
    }

    assert validate_data_source_config(config) == config


@pytest.mark.parametrize("platform", ["weibo", "xiaohongshu"])
def test_explicit_national_scope_rejects_region_codes(platform: str) -> None:
    config = {
        "collector": "mediacrawler",
        "platform": platform,
        "collection_scope": "national",
        "collection_mode": "national",
    }

    with pytest.raises(ValueError, match="requires empty scope_region_codes"):
        validate_mediacrawler_region_contract(config, "131028")


def test_national_migration_preserves_valid_region_strategy() -> None:
    config = {
        "filter_mode": "region_only",
        "keyword_scope": "region_topic",
        "collection_mode": "national",
    }

    dropped = _reconcile_national_strategy("xhs_mediacrawler", config)

    assert config["filter_mode"] == "region_only"
    assert config["keyword_scope"] == "region_topic"
    assert dropped == []
