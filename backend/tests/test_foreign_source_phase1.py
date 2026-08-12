"""Phase Foreign-Source-1: offline RSS and isolated persistence checks."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi.testclient import TestClient

from app.api.admin_data_sources import _validate_foreign_config
from app.collectors.data_source_repository import enabled_sources
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
    # 隔离代理环境变量：本测试聚焦去重逻辑，期望直连（proxy_used=False）。
    # 新代理解析（需求三）会回退读取 HTTPS_PROXY/HTTP_PROXY/FOREIGN_HTTP_PROXY，
    # 测试 shell 中可能已设置，故此处显式清除以得到确定性结果。
    for _v in ("HTTPS_PROXY", "HTTP_PROXY", "FOREIGN_HTTP_PROXY", "https_proxy", "http_proxy"):
        monkeypatch.delenv(_v, raising=False)
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


def test_foreign_api_requires_auth_and_filters_by_foreign_config(client: TestClient, auth_headers):
    assert client.get("/api/foreign/opinions").status_code == 401

    suffix = uuid.uuid4().hex[:10]
    key = f"phase1_nonforeign_marker_{suffix}"
    db = SessionLocal()
    try:
        db.add(
            DataSource(
                key=key,
                name=f"Nonforeign marker {suffix}",
                type="foreign_rss",
                class_path="app.collectors.foreign_rss.ForeignRSSCollector",
                enabled=False,
                schedule_enabled=False,
                schedule_interval_minutes=60,
                priority=9999,
                config_json='{"is_foreign": false, "feeds": [], "keywords": []}',
            )
        )
        db.commit()

        response = client.get("/api/foreign/sources", headers=auth_headers)
        assert response.status_code == 200, response.text
        assert all(item["key"] != key for item in response.json()["items"])

        opinions = client.get("/api/foreign/opinions", headers=auth_headers)
        runs = client.get("/api/foreign/collection-runs", headers=auth_headers)
        assert opinions.status_code == 200
        assert runs.status_code == 200
        assert all(item.get("scope") == "foreign" for item in runs.json()["items"])
    finally:
        db.query(DataSource).filter(DataSource.key == key).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_domestic_repository_excludes_foreign_class_path_even_if_config_missing():
    suffix = uuid.uuid4().hex[:10]
    key = f"phase1_foreign_guard_{suffix}"
    db = SessionLocal()
    try:
        db.add(
            DataSource(
                key=key,
                name=f"Foreign guard {suffix}",
                type="foreign_rss",
                class_path="app.collectors.foreign_rss.ForeignRSSCollector",
                enabled=True,
                schedule_enabled=False,
                schedule_interval_minutes=60,
                priority=9999,
                config_json='{"is_foreign": false, "feeds": ["https://fixture.test/rss"], "keywords": ["China"]}',
            )
        )
        db.commit()

        rows = enabled_sources(db)
        assert all(row["key"] != key for row in rows)
    finally:
        db.query(DataSource).filter(DataSource.key == key).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_collection_log_scope_isolation(client: TestClient, auth_headers):
    suffix = uuid.uuid4().hex[:10]
    domestic_batch = f"phase1_domestic_batch_{suffix}"
    foreign_batch = f"phase1_foreign_batch_{suffix}"
    db = SessionLocal()
    try:
        db.add_all(
            [
                CollectorRun(
                    collector_name=f"Domestic fixture {suffix}",
                    batch_id=domestic_batch,
                    trigger_type="manual",
                    scope="domestic",
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    status="success",
                    fetched_raw=1,
                    upstream_returned=1,
                    created=1,
                ),
                CollectorRun(
                    collector_name=f"Foreign fixture {suffix}",
                    batch_id=foreign_batch,
                    trigger_type="manual",
                    scope="foreign",
                    start_time=datetime.now(timezone.utc),
                    end_time=datetime.now(timezone.utc),
                    status="success",
                    fetched_raw=2,
                    upstream_returned=2,
                    created=2,
                ),
            ]
        )
        db.commit()

        domestic = client.get(
            "/api/admin/data-sources/collection-logs",
            headers=auth_headers,
            params={"scope": "domestic", "size": 100},
        )
        foreign = client.get(
            "/api/admin/data-sources/collection-logs",
            headers=auth_headers,
            params={"scope": "foreign", "size": 100},
        )
        assert domestic.status_code == 200, domestic.text
        assert foreign.status_code == 200, foreign.text
        domestic_keys = {item["batch_id"] for item in domestic.json()["items"]}
        foreign_keys = {item["batch_id"] for item in foreign.json()["items"]}
        assert domestic_batch in domestic_keys
        assert foreign_batch not in domestic_keys
        assert foreign_batch in foreign_keys
        assert domestic_batch not in foreign_keys
    finally:
        db.query(CollectorRun).filter(
            CollectorRun.batch_id.in_([domestic_batch, foreign_batch])
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_foreign_source_api_validates_feeds_and_keeps_schedule_manual(
    client: TestClient, auth_headers, monkeypatch
):
    invalid = client.post(
        "/api/foreign/sources",
        headers=auth_headers,
        json={
            "name": "Invalid foreign fixture",
            "key": f"phase1_invalid_{uuid.uuid4().hex[:8]}",
            "feeds": ["file:///local-fixture.xml"],
        },
    )
    assert invalid.status_code == 422

    suffix = uuid.uuid4().hex[:10]
    key = f"phase1_api_foreign_{suffix}"
    keyword_word = f"Phase1China_{suffix}"
    db = SessionLocal()
    db.add(ForeignKeyword(word=keyword_word, category="general", is_enabled=True))
    db.commit()
    db.close()

    class FakeResponse:
        status_code = 200
        encoding = "utf-8"
        apparent_encoding = "utf-8"
        text = RSS_FIXTURE

        def raise_for_status(self):
            return None

    requested: list[str] = []

    def fake_get(url, **kwargs):
        requested.append(url)
        assert url == "https://fixture.test/rss"
        return FakeResponse()

    # Patch the module-level requests.get used by ForeignRSSCollector._get_response,
    # so this API contract test cannot make a real network request.
    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    # The fixture hostname is intentionally offline; provide a public DNS
    # answer so the production DNS-level SSRF guard remains exercised.
    monkeypatch.setattr(
        "app.collectors.common.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    response = client.post(
        "/api/foreign/sources",
        headers=auth_headers,
        json={
            "name": f"API Foreign Fixture {suffix}",
            "key": key,
            "feeds": ["https://fixture.test/rss"],
            "enabled": False,
        },
    )
    assert response.status_code == 201, response.text
    # 创建期不再发起真实网络请求（仅结构 + SSRF 静态校验 + 采集器装配），
    # 目标站点宕机 / 代理抖动 / 暂时无条目都不会阻塞保存。
    assert requested == [], "创建期不得发起真实网络请求"
    assert response.json()["verified"] is False
    source_id = response.json()["id"]
    assert response.json()["enabled"] is False
    assert response.json()["schedule_enabled"] is False

    try:
        updated = client.patch(
            f"/api/foreign/sources/{source_id}",
            headers=auth_headers,
            json={"enabled": True, "schedule_enabled": True},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["enabled"] is True
        # Source-level scheduling is independent from the deployment-level
        # FOREIGN_COLLECTION_SCHEDULE_ENABLED switch.
        assert updated.json()["schedule_enabled"] is True
        assert updated.json()["config_json"]
    finally:
        db = SessionLocal()
        try:
            db.query(DataSource).filter(DataSource.id == source_id).delete(
                synchronize_session=False
            )
            db.query(ForeignKeyword).filter(ForeignKeyword.word == keyword_word).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()


def test_foreign_config_rejects_domestic_scope_and_requires_keywords():
    base = {
        "is_foreign": True,
        "feeds": ["https://fixture.test/rss"],
        "keywords": ["China"],
        "collection_mode": "foreign",
    }
    assert _validate_foreign_config(base) is None
    assert "RSS feed" in _validate_foreign_config({**base, "feeds": []})
    assert "keyword" in _validate_foreign_config({**base, "keywords": []})
    assert "domestic collection_mode" in _validate_foreign_config(
        {**base, "collection_mode": "regional"}
    )


def test_foreign_proxy_reads_only_environment_value(monkeypatch):
    monkeypatch.setenv("PHASE1_FOREIGN_PROXY", "http://fixture-proxy.invalid:8080")
    collector = ForeignRSSCollector(
        feeds=["https://fixture.test/rss"],
        keywords=["China"],
        is_foreign=True,
        proxy_env="PHASE1_FOREIGN_PROXY",
    )
    assert collector._proxies() == {
        "http": "http://fixture-proxy.invalid:8080",
        "https": "http://fixture-proxy.invalid:8080",
    }
    assert "fixture-proxy.invalid" not in str(
        {"proxy_env": collector.proxy_env, "is_foreign": True}
    )
