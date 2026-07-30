"""Phase8-D.1：monitoring 关键词停用语义测试。"""
from __future__ import annotations

import pytest

from app.models.keyword import Keyword
from app.services import keyword_service
from app.services.keyword_service import (
    clear_keyword_cache,
    get_monitoring_keywords,
    get_monitoring_keywords_grouped,
    get_sensitive_keywords,
)


class _Query:
    def __init__(self, *, count_value: int = 0, rows: list[tuple] | None = None) -> None:
        self._count_value = count_value
        self._rows = rows or []

    def filter(self, *args):  # noqa: ANN002
        return self

    def count(self) -> int:
        return self._count_value

    def all(self) -> list[tuple]:
        return self._rows


class _KeywordSession:
    """只实现 keyword_service 当前使用的只读 Query 契约。"""

    def __init__(
        self,
        *,
        monitoring_count: int,
        monitoring_words: list[tuple] | None = None,
        monitoring_grouped: list[tuple] | None = None,
        sensitive_words: list[tuple] | None = None,
    ) -> None:
        self.monitoring_count = monitoring_count
        self.monitoring_words = monitoring_words or []
        self.monitoring_grouped = monitoring_grouped or []
        self.sensitive_words = sensitive_words or []

    def query(self, *columns):  # noqa: ANN002
        keys = tuple(column.key for column in columns)
        if keys == ("id",):
            return _Query(count_value=self.monitoring_count)
        if keys == ("word",):
            return _Query(rows=self.monitoring_words)
        if keys == ("word", "category"):
            return _Query(rows=self.monitoring_grouped)
        if keys == ("word", "weight"):
            return _Query(rows=self.sensitive_words)
        raise AssertionError(f"unexpected query columns: {keys}")


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    clear_keyword_cache()
    yield
    clear_keyword_cache()


def test_no_monitoring_records_uses_environment_fallback(monkeypatch) -> None:
    monkeypatch.setattr(keyword_service.settings, "collector_keywords", "EnvA, EnvB")
    db = _KeywordSession(monitoring_count=0)

    assert get_monitoring_keywords(db) == ["EnvA", "EnvB"]
    assert get_monitoring_keywords_grouped(db) == {"general": ["EnvA", "EnvB"]}


def test_all_monitoring_records_disabled_returns_empty_list(monkeypatch) -> None:
    monkeypatch.setattr(keyword_service.settings, "collector_keywords", "EnvA, EnvB")
    db = _KeywordSession(monitoring_count=2)

    assert get_monitoring_keywords(db) == []


def test_partially_enabled_monitoring_returns_only_enabled_words() -> None:
    db = _KeywordSession(
        monitoring_count=3,
        monitoring_words=[("廊坊",), ("消防",)],
        monitoring_grouped=[("廊坊", "地域"), ("消防", "主题")],
    )

    assert get_monitoring_keywords(db) == ["廊坊", "消防"]
    assert get_monitoring_keywords_grouped(db) == {"地域": ["廊坊"], "主题": ["消防"]}


def test_all_monitoring_records_disabled_returns_empty_region_and_topic() -> None:
    db = _KeywordSession(monitoring_count=2)

    assert get_monitoring_keywords_grouped(db) == {"地域": [], "主题": []}


def test_sensitive_keywords_remain_independent_from_monitoring_state() -> None:
    db = _KeywordSession(
        monitoring_count=2,
        sensitive_words=[("火灾", 9)],
    )

    assert get_sensitive_keywords(db) == [("火灾", 9)]
