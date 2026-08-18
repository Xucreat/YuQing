from types import SimpleNamespace

from scripts import backfill_foreign_content_type as backfill_module
from app.services.foreign_content_type_service import (
    CONTENT_TYPE_VERSION,
    classify_foreign_content_type,
)


def test_classifies_english_risk_event_before_news():
    result = classify_foreign_content_type(title="Fire accident causes casualties")
    assert result.content_type == "risk_event"
    assert result.version == CONTENT_TYPE_VERSION


def test_classifies_chinese_content():
    result = classify_foreign_content_type(title="\u7528\u6237\u6295\u8bc9\u62d6\u6b20\u5de5\u8d44")
    assert result.content_type == "complaint"


def test_strips_html_and_normalizes_entities():
    result = classify_foreign_content_type(
        title="<h1>Government notice</h1>",
        content="&nbsp;New regulation for public services&nbsp;",
    )
    assert result.content_type == "policy"


def test_classification_priority_is_deterministic():
    result = classify_foreign_content_type(
        title="Government policy after a flood accident"
    )
    assert result.content_type == "risk_event"


def test_normal_article_falls_back_to_news():
    result = classify_foreign_content_type(title="Global markets update", content="Markets moved higher today.")
    assert result.content_type == "news"


def test_empty_content_is_unknown():
    result = classify_foreign_content_type(title="short")
    assert result.content_type == "unknown"


def test_whitespace_only_and_short_html_are_unknown():
    assert classify_foreign_content_type(title="<p> </p>").content_type == "unknown"
    assert classify_foreign_content_type(title="abc").content_type == "unknown"


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeBackfillSession:
    def __init__(self, rows):
        self.rows = rows
        self.last_id = 0
        self.scalar_calls = 0

    def scalar(self, _statement):
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return len(self.rows)
        return sum(row.content_type is None for row in self.rows)

    def scalars(self, _statement):
        rows = [
            row
            for row in self.rows
            if row.id > self.last_id and row.content_type is None
        ]
        if rows:
            self.last_id = rows[0].id
            return _FakeScalarResult(rows[:1])
        return _FakeScalarResult([])

    def commit(self):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


def test_backfill_dry_run_and_repeat_execution_are_safe(monkeypatch):
    rows = [
        SimpleNamespace(
            id=1,
            title="Fire accident causes casualties",
            summary="",
            content="A fire accident caused casualties.",
            content_type=None,
            content_type_version=None,
        ),
        SimpleNamespace(
            id=2,
            title="Global markets update",
            summary="",
            content="Markets moved higher today.",
            content_type=None,
            content_type_version=None,
        ),
    ]
    monkeypatch.setattr(
        backfill_module,
        "SessionLocal",
        lambda: _FakeBackfillSession(rows),
    )

    dry_run = backfill_module.backfill(batch_size=1, dry_run=True)
    assert dry_run["pending_count"] == 2
    assert dry_run["updated"] == 2
    assert [row.content_type for row in rows] == [None, None]

    applied = backfill_module.backfill(batch_size=1)
    assert applied["updated"] == 2
    assert [row.content_type for row in rows] == ["risk_event", "news"]

    repeat = backfill_module.backfill(batch_size=1)
    assert repeat["pending_count"] == 0
    assert repeat["updated"] == 0
