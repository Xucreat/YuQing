"""Phase Foreign-Source-1: offline RSS and isolated persistence checks."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from app.collectors.foreign_rss import ForeignRSSCollector
from app.db.session import SessionLocal
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.models.opinion import Opinion
from app.services.foreign_collection_service import collect_foreign


RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>China policy update</title><link>https://fixture.test/1</link>
    <description>Domestic summary without the exact case-sensitive spelling.</description>
    <pubDate>Fri, 07 Aug 2026 08:00:00 GMT</pubDate></item>
  <item><title>Unrelated headline</title><link>https://fixture.test/2</link>
    <description>Chinese officials discussed the issue.</description></item>
  <item><title>Another headline</title><link>https://fixture.test/3</link>
    <description>No match here.</description></item>
</channel></rss>"""


def test_foreign_rss_matches_or_case_insensitive_and_ignores_domestic_args(monkeypatch):
    collector = ForeignRSSCollector(
        feeds=["https://fixture.test/rss"],
        keywords=["china", "Chinese"],
        is_foreign=True,
        max_items=10,
    )
    monkeypatch.setattr(collector, "_get", lambda _url: RSS_FIXTURE)

    items = collector.fetch(
        keywords=["河北"],
        region_kw=["廊坊"],
        topic_kw=["国内"],
    )

    assert [item["url"] for item in items] == [
        "https://fixture.test/1",
        "https://fixture.test/2",
    ]
    assert items[0]["matched_keywords"] == ["china"]
    assert items[1]["matched_keywords"] == ["Chinese"]


def test_foreign_rss_body_match_and_body_failure_fallback(monkeypatch):
    collector = ForeignRSSCollector(
        feeds=["https://fixture.test/rss"],
        keywords=["China"],
        is_foreign=True,
        fetch_full_text=True,
    )
    monkeypatch.setattr(collector, "_get", lambda url: RSS_FIXTURE if url.endswith("rss") else "<article>China appears in body.</article>")
    items = collector.fetch()
    assert items[0]["content"] == "China appears in body."

    failing = ForeignRSSCollector(
        feeds=["https://fixture.test/rss"],
        keywords=["Chinese"],
        is_foreign=True,
        fetch_full_text=True,
    )
    monkeypatch.setattr(failing, "_get", lambda _url: RSS_FIXTURE)
    monkeypatch.setattr(failing, "_fetch_full_text", lambda _url: "")
    items = failing.fetch()
    assert len(items) == 1
    assert "Chinese officials" in items[0]["summary"]


def test_foreign_collection_deduplicates_url_and_content_without_opinions(monkeypatch):
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    source_key = f"phase1_foreign_{suffix}"
    source_name = f"Phase 1 Foreign Fixture {suffix}"
    keyword_word = f"PhaseChina_{suffix}"
    url = f"https://fixture.test/dedupe/{suffix}"
    try:
        keyword = ForeignKeyword(word=keyword_word, category="general", is_enabled=True)
        source = DataSource(
            key=source_key,
            name=source_name,
            type="foreign_rss",
            class_path="app.collectors.foreign_rss.ForeignRSSCollector",
            enabled=True,
            schedule_enabled=False,
            schedule_interval_minutes=60,
            priority=900,
            config_json=(
                '{"is_foreign": true, "collector": "foreign_rss", '
                f'"feeds": ["https://fixture.test/rss"], "keywords": ["{keyword_word}"], '
                '"collection_mode": "foreign"}'
            ),
        )
        db.add_all([keyword, source])
        db.commit()
        source_id = source.id

        monkeypatch.setattr(
            ForeignRSSCollector,
            "_get",
            lambda self, _url: (
                    f'<rss><channel><item><title>{keyword_word} item</title>'
                f"<link>{url}</link><description>fixture body</description></item>"
                "</channel></rss>"
            ),
        )
        first = collect_foreign(db, source_ids=[source_id])
        second = collect_foreign(db, source_ids=[source_id])
        assert first["created"] == 1
        assert second["created"] == 0
        assert second["duplicate"] == 1
        assert db.query(ForeignOpinion).filter(ForeignOpinion.source_id == source_id).count() == 1
        assert db.query(Opinion).filter(Opinion.url == url).count() == 0
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == source_name)
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert run is not None
        assert run.scope == "foreign"
        assert run.proxy_used is False
    finally:
        db.query(ForeignOpinion).filter(ForeignOpinion.source_key == source_key).delete(
            synchronize_session=False
        )
        db.query(CollectorRun).filter(CollectorRun.collector_name == source_name).delete(
            synchronize_session=False
        )
        db.query(DataSource).filter(DataSource.key == source_key).delete(
            synchronize_session=False
        )
        db.query(ForeignKeyword).filter(ForeignKeyword.word == keyword_word).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()
