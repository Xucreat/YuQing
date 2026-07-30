"""Phase8-D.2：数据源关键词策略只读解释测试。"""
from __future__ import annotations

import json

import pytest

from app.api.admin_data_sources import _serialize
from app.models.data_source import DataSource


GOVERNMENT = "app.collectors.government_collector.GovernmentCollector"
GENERIC = "app.collectors.generic_site.GenericSiteCollector"
NATIONAL_SOURCES = [
    "app.collectors.baidu_news_collector.BaiduNewsCollector",
    "app.collectors.xinhua_collector.XinhuaCollector",
    "app.collectors.people_collector.PeopleCollector",
    "app.collectors.chinanews_collector.ChinanewsCollector",
]


def _source(class_path: str, config: dict | str = "{}") -> DataSource:
    raw = config if isinstance(config, str) else json.dumps(config, ensure_ascii=False)
    return DataSource(
        id=9001,
        key="keyword_strategy_test",
        name="Keyword Strategy Test",
        type="news_site",
        class_path=class_path,
        enabled=True,
        priority=1,
        config_json=raw,
    )


def _strategy(source: DataSource, region_keywords: list[str] | None = None) -> dict:
    return _serialize(source, {}, region_keywords=region_keywords or [])


def test_government_collector_is_full_collection() -> None:
    item = _strategy(_source(GOVERNMENT), ["廊坊"])

    assert item["keyword_mode"] == "full_collection"
    assert item["effective_keywords"] == []
    assert item["keyword_source"] == "采集器固定策略"


def test_generic_source_keywords_are_explained() -> None:
    item = _strategy(_source(GENERIC, {"keywords": "环保, 投诉"}), ["廊坊"])

    assert item["keyword_mode"] == "source_keywords"
    assert item["effective_keywords"] == ["环保", "投诉"]
    assert item["keyword_source"] == "数据源配置-config_json.keywords"


def test_generic_without_keywords_uses_global_region() -> None:
    item = _strategy(_source(GENERIC, {"list_urls": ["https://example.test"]}), ["廊坊", "大厂"])

    assert item["keyword_mode"] == "global_region"
    assert item["effective_keywords"] == ["廊坊", "大厂"]


def test_generic_empty_keywords_is_no_filter() -> None:
    item = _strategy(_source(GENERIC, {"keywords": ""}), ["廊坊"])

    assert item["keyword_mode"] == "no_filter"
    assert item["effective_keywords"] == []


@pytest.mark.parametrize("class_path", NATIONAL_SOURCES)
def test_national_sources_use_global_region(class_path: str) -> None:
    item = _strategy(_source(class_path), ["廊坊"])

    assert item["keyword_mode"] == "global_region"
    assert item["effective_keywords"] == ["廊坊"]


def test_empty_global_region_keywords_do_not_break_explanation() -> None:
    item = _strategy(_source(GENERIC, {"list_urls": ["https://example.test"]}))

    assert item["keyword_mode"] == "global_region"
    assert item["effective_keywords"] == []
