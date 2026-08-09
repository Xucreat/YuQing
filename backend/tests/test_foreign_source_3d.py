"""Foreign visualization boundary tests.

These tests are deliberately database-free so they remain safe when the
default database has not received the later foreign migrations.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from app.main import app
from app.services import foreign_visualization_service as visualization
from app.services.foreign_visualization_service import _tokenize, _window


def test_visualization_routes_are_foreign_only():
    paths = {route.path for route in app.routes}
    assert "/api/foreign/dashboard/summary" in paths
    assert "/api/foreign/dashboard/trends" in paths
    assert "/api/foreign/hotwords" in paths
    assert "/api/foreign/hotwords/trends" in paths
    assert "/api/foreign/source-distribution" in paths
    assert "/api/foreign/language-distribution" in paths
    assert not any(path.startswith("/api/dashboard/") and "foreign" in path for path in paths)


def test_hotword_tokenizer_excludes_monitoring_terms_and_separates_languages():
    english = _tokenize("China and Chinese security conflicts", "en")
    chinese = _tokenize("中国海外安全风险", "zh")
    assert "china" not in english
    assert "chinese" not in english
    assert "security" in english
    assert "中国" not in chinese
    assert chinese


def test_window_is_bounded_and_uses_utc():
    start, end, days = _window(999)
    assert days == 90
    assert start.tzinfo is not None
    assert end > start


def test_hotword_trends_use_json_safe_word_keys(monkeypatch):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)
    monkeypatch.setattr(visualization, "_window", lambda _days: (start, end, 1))
    monkeypatch.setattr(visualization, "_trend_dates", lambda *_args: ["2026-01-01"])
    monkeypatch.setattr(
        visualization,
        "_hotword_rows",
        lambda *_args, **_kwargs: [("security", "en", "fixture")],
    )
    monkeypatch.setattr(visualization, "_opinions", lambda *_args: [])

    body = visualization.get_hotword_trends(object(), days=1)

    json.dumps(body)
    assert body["items"] == [{"date": "2026-01-01", "words": {"security": 0}}]


def test_visualization_service_does_not_import_domestic_business_models():
    source = Path(__file__).parents[1] / "app" / "services" / "foreign_visualization_service.py"
    text = source.read_text(encoding="utf-8")
    assert "app.models.opinion" not in text
    assert "app.models.event" not in text
    assert "app.models.alert" not in text
    assert "app.models.keyword" not in text
    assert "app.models.region" not in text
    assert "dashboard_service" not in text
