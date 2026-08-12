"""Phase Foreign-Source-1.1 acceptance and isolation checks.

All network-facing cases use local RSS fixtures or monkeypatches.  The tests
only use the isolated test database configured by backend/tests/conftest.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.collectors.data_source_repository import (
    due_scheduled_sources,
    enabled_sources,
    scheduled_enabled_sources,
)
from app.collectors.foreign_rss import ForeignRSSCollector
from app.db.session import SessionLocal
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.models.opinion import Opinion
from app.services.foreign_collection_service import collect_foreign


FOX_NEWS_RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>China policy fixture</title>
    <link>https://fixture.test/fox/1</link>
    <description>Fox summary fixture.</description>
  </item>
</channel></rss>"""

GUARDIAN_RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>Guardian fixture</title>
    <link>https://fixture.test/guardian/1</link>
    <description>Chinese officials appear in the summary.</description>
  </item>
</channel></rss>"""

NYT_CHINESE_RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>纽约时报中文网 fixture</title>
    <link>https://fixture.test/nyt/1</link>
    <description>China appears in the RSS fixture before optional body retrieval.</description>
  </item>
</channel></rss>"""


@pytest.mark.parametrize(
    ("source_name", "fixture"),
    [
        ("Fox News", FOX_NEWS_RSS_FIXTURE),
        ("The Guardian", GUARDIAN_RSS_FIXTURE),
        ("纽约时报中文网", NYT_CHINESE_RSS_FIXTURE),
    ],
)
def test_three_foreign_rss_fixtures_parse_offline(
    monkeypatch, source_name: str, fixture: str
):
    collector = ForeignRSSCollector(
        feeds=[f"https://fixture.test/{source_name}/rss"],
        keywords=["中国", "Chinese", "China"],
        is_foreign=True,
        source_name=source_name,
        request_interval=0,
    )
    monkeypatch.setattr(collector, "_get", lambda _url: fixture)

    rows = collector.fetch()

    assert len(rows) == 1
    assert rows[0]["source"] == source_name
    assert rows[0]["matched_keywords"]


def test_foreign_rss_matches_title_summary_and_body_independently(monkeypatch):
    cases = [
        (
            "<title>China title hit</title><description>ordinary summary</description>",
            "<article>ordinary body</article>",
            ["China"],
        ),
        (
            "<title>ordinary title</title><description>Chinese summary hit</description>",
            "<article>ordinary body</article>",
            ["Chinese"],
        ),
        (
            "<title>ordinary title</title><description>ordinary summary</description>",
            "<article>\u4e2d\u56fd body hit</article>",
            ["\u4e2d\u56fd"],
        ),
    ]
    for index, (fields, body, expected) in enumerate(cases):
        rss = f"""<?xml version="1.0"?>
        <rss version="2.0"><channel><item>
          {fields}
          <link>https://fixture.test/body/{index}</link>
        </item></channel></rss>"""
        collector = ForeignRSSCollector(
            feeds=["https://fixture.test/rss"],
            keywords=["\u4e2d\u56fd", "Chinese", "China"],
            is_foreign=True,
            fetch_full_text=True,
            respect_robots=False,
            request_interval=0,
        )
        monkeypatch.setattr(
            collector,
            "_get",
            lambda url, rss=rss, body=body: rss if url.endswith("/rss") else body,
        )
        rows = collector.fetch()
        assert len(rows) == 1
        assert rows[0]["matched_keywords"] == expected


def test_foreign_collection_dry_run_logs_foreign_without_writing_opinion(monkeypatch):
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    keyword_word = f"Phase11DryRun_{suffix}"
    source_key = f"phase11_dry_run_{suffix}"
    source_name = f"Phase 1.1 dry run {suffix}"
    url = f"https://fixture.test/dry-run/{suffix}"
    try:
        db.add(ForeignKeyword(word=keyword_word, category="general", is_enabled=True))
        source = DataSource(
            key=source_key,
            name=source_name,
            type="foreign_rss",
            class_path="app.collectors.foreign_rss.ForeignRSSCollector",
            enabled=True,
            schedule_enabled=False,
            schedule_interval_minutes=60,
            priority=9999,
            config_json=json.dumps(
                {
                    "is_foreign": True,
                    "collector": "foreign_rss",
                    "feeds": ["https://fixture.test/rss"],
                    "keywords": [keyword_word],
                    "collection_mode": "foreign",
                }
            ),
        )
        db.add(source)
        db.commit()
        source_id = source.id
        monkeypatch.setattr(
            ForeignRSSCollector,
            "_get",
            lambda self, _url: (
                f'<rss><channel><item><title>{keyword_word}</title>'
                f"<link>{url}</link><description>fixture</description></item>"
                "</channel></rss>"
            ),
        )

        result = collect_foreign(db, source_ids=[source_id], dry_run=True)

        assert result["dry_run"] is True
        assert result["matched"] == 1
        assert result["created"] == 0
        assert db.query(ForeignOpinion).filter(ForeignOpinion.url == url).count() == 0
        run = (
            db.query(CollectorRun)
            .filter(CollectorRun.collector_name == source_name)
            .order_by(CollectorRun.id.desc())
            .first()
        )
        assert run is not None
        assert run.scope == "foreign"
        assert run.created == 0
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


def test_domestic_registry_and_scheduler_exclude_both_foreign_markers():
    suffix = uuid.uuid4().hex[:10]
    db = SessionLocal()
    keys = [f"phase11_foreign_config_{suffix}", f"phase11_foreign_class_{suffix}"]
    try:
        db.add_all(
            [
                DataSource(
                    key=keys[0],
                    name=keys[0],
                    type="rss",
                    class_path="app.collectors.rss_collector.RSSCollector",
                    enabled=True,
                    schedule_enabled=True,
                    schedule_interval_minutes=30,
                    priority=9998,
                    config_json=json.dumps(
                        {
                            "is_foreign": True,
                            "feeds": ["https://fixture.test/rss"],
                            "keywords": ["China"],
                        }
                    ),
                ),
                DataSource(
                    key=keys[1],
                    name=keys[1],
                    type="foreign_rss",
                    class_path="app.collectors.foreign_rss.ForeignRSSCollector",
                    enabled=True,
                    schedule_enabled=True,
                    schedule_interval_minutes=30,
                    priority=9999,
                    config_json=json.dumps(
                        {
                            "is_foreign": False,
                            "feeds": ["https://fixture.test/rss"],
                            "keywords": ["China"],
                        }
                    ),
                ),
            ]
        )
        db.commit()

        domestic_rows = {row["key"] for row in enabled_sources(db)}
        due_rows = {row["key"] for row in due_scheduled_sources(db)}
        cron_rows = {row["key"] for row in scheduled_enabled_sources(db)}
        assert not domestic_rows.intersection(keys)
        assert not due_rows.intersection(keys)
        assert not cron_rows.intersection(keys)
    finally:
        db.query(DataSource).filter(DataSource.key.in_(keys)).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_domestic_and_foreign_opinion_apis_are_bidirectionally_isolated(
    client: TestClient, auth_headers, seeded_region_id: int
):
    suffix = uuid.uuid4().hex[:10]
    domestic_url = f"https://fixture.test/phase11/domestic/{suffix}"
    foreign_url = f"https://fixture.test/phase11/foreign/{suffix}"
    db = SessionLocal()
    domestic_id = None
    foreign_id = None
    try:
        domestic = Opinion(
            title=f"Domestic isolation {suffix}",
            content="domestic fixture",
            summary="domestic fixture",
            source=f"Domestic fixture {suffix}",
            url=domestic_url,
            region_id=seeded_region_id,
        )
        foreign = ForeignOpinion(
            source_key=f"foreign_{suffix}",
            source_name_snapshot=f"Foreign fixture {suffix}",
            title=f"Foreign isolation {suffix}",
            summary="China fixture",
            content="China fixture",
            url=foreign_url,
            published_at=datetime.now(timezone.utc),
            collected_at=datetime.now(timezone.utc),
            matched_keywords=["China"],
            content_hash=("a" * 63) + suffix[:1],
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([domestic, foreign])
        db.commit()
        domestic_id, foreign_id = domestic.id, foreign.id

        domestic_response = client.get(
            "/api/opinions",
            headers=auth_headers,
            params={"keyword": suffix, "include_low_value": True},
        )
        foreign_response = client.get(
            "/api/foreign/opinions",
            headers=auth_headers,
            params={"q": suffix},
        )
        assert domestic_response.status_code == 200, domestic_response.text
        assert foreign_response.status_code == 200, foreign_response.text
        assert all(row["id"] != foreign_id for row in domestic_response.json()["items"])
        assert all(row["id"] != domestic_id for row in foreign_response.json()["items"])
    finally:
        if domestic_id is not None:
            db.query(Opinion).filter(Opinion.id == domestic_id).delete(
                synchronize_session=False
            )
        if foreign_id is not None:
            db.query(ForeignOpinion).filter(ForeignOpinion.id == foreign_id).delete(
                synchronize_session=False
            )
        db.commit()
        db.close()


def test_domestic_source_api_rejects_invalid_foreign_enable_bypass(
    client: TestClient, auth_headers
):
    suffix = uuid.uuid4().hex[:10]
    db = SessionLocal()
    source = DataSource(
        key=f"phase11_invalid_foreign_{suffix}",
        name=f"Phase 1.1 invalid foreign {suffix}",
        type="foreign_rss",
        class_path="app.collectors.foreign_rss.ForeignRSSCollector",
        enabled=False,
        schedule_enabled=False,
        schedule_interval_minutes=30,
        priority=9999,
        config_json=json.dumps(
            {
                "is_foreign": True,
                "feeds": [],
                "keywords": [],
            }
        ),
    )
    db.add(source)
    db.commit()
    source_id = source.id
    try:
        response = client.patch(
            f"/api/admin/data-sources/{source_id}",
            headers=auth_headers,
            json={"enabled": True, "schedule_enabled": True},
        )
        assert response.status_code == 422, response.text
        db.refresh(source)
        assert source.enabled is False
        assert source.schedule_enabled is False
    finally:
        db.query(DataSource).filter(DataSource.id == source_id).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_foreign_seed_defaults_and_physical_keyword_isolation():
    db = SessionLocal()
    try:
        words = db.scalars(
            select(ForeignKeyword.word).order_by(ForeignKeyword.id)
        ).all()
        assert words[:3] == ["中国", "Chinese", "China"]
        assert db.query(ForeignKeyword).count() >= 3
        # Phase 5A extends only the foreign keyword table; these fields must
        # remain physically isolated from the domestic keyword model.
        assert hasattr(ForeignKeyword, "type")
        assert hasattr(ForeignKeyword, "source")
        assert hasattr(ForeignKeyword, "weight")
        assert hasattr(ForeignKeyword, "severity_weight")
        assert hasattr(ForeignKeyword, "rule_config")

        sources = db.query(DataSource).filter(
            DataSource.key.in_(
                ["foreign_fox_news", "foreign_guardian", "foreign_nyt_chinese"]
            )
        ).all()
        assert len(sources) == 3
        assert all(source.enabled is False for source in sources)
        assert all(source.schedule_enabled is False for source in sources)
        assert all(json.loads(source.config_json)["is_foreign"] is True for source in sources)
    finally:
        db.close()


def test_foreign_source_snapshot_survives_source_delete():
    suffix = uuid.uuid4().hex[:10]
    db = SessionLocal()
    source = DataSource(
        key=f"phase11_snapshot_{suffix}",
        name=f"Snapshot source {suffix}",
        type="foreign_rss",
        class_path="app.collectors.foreign_rss.ForeignRSSCollector",
        enabled=False,
        schedule_enabled=False,
        schedule_interval_minutes=30,
        priority=9999,
        config_json=json.dumps(
            {
                "is_foreign": True,
                "feeds": ["https://fixture.test/rss"],
                "keywords": ["China"],
            }
        ),
    )
    db.add(source)
    db.flush()
    opinion = ForeignOpinion(
        source_id=source.id,
        source_key=source.key,
        source_name_snapshot=source.name,
        title="Snapshot fixture",
        summary="China",
        content="China",
        url=f"https://fixture.test/snapshot/{suffix}",
        matched_keywords=["China"],
        content_hash=("b" * 64),
        collected_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(opinion)
    db.commit()
    opinion_id = opinion.id
    try:
        db.delete(source)
        db.commit()
        row = db.get(ForeignOpinion, opinion_id)
        assert row is not None
        assert row.source_id is None
        assert row.source_name_snapshot == f"Snapshot source {suffix}"
    finally:
        db.query(ForeignOpinion).filter(ForeignOpinion.id == opinion_id).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_frontend_scope_navigation_contract():
    root = Path(__file__).resolve().parents[2]
    alerts = (root / "frontend/src/views/Alerts.vue").read_text(encoding="utf-8")
    foreign = (root / "frontend/src/views/ForeignWorkspace.vue").read_text(encoding="utf-8")
    layout = (root / "frontend/src/components/AppLayout.vue").read_text(
        encoding="utf-8-sig"
    )

    assert "activeTab" in alerts and "scope" in alerts
    assert 'label="foreign"' in alerts
    assert "/foreign/alert-rules" in alerts and "/foreign/alerts" in alerts
    assert "visibleTabs" in foreign
    assert "tab === 'alerts' || tab === 'alertRules'" in foreign
    assert "path: '/alerts'" in foreign
    assert "/foreign/sources/approved" in foreign
    assert "selectedSourceIds" in foreign
    assert "{ all_sources: true }" in foreign
    assert "to: '/alerts'" in layout
    assert "to: '/foreign?tab=alerts'" not in layout
