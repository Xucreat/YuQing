"""Regression coverage for the foreign UI and content boundary."""
from pathlib import Path
from uuid import uuid4

from app.services.foreign_content_sanitizer import sanitize_foreign_html, sanitize_foreign_text
from app.collectors.foreign_rss import ForeignRSSCollector
from app.db.session import SessionLocal
from app.models.data_source import DataSource


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "frontend" / "src" / "views" / "ForeignWorkspace.vue"


def test_foreign_html_sanitizer_removes_external_markup_and_keeps_safe_links():
    raw = (
        "<div class='publisher' style='color:red'>Intro"
        "<img src='https://publisher.example/image.jpg'>"
        "<script>alert(1)</script><iframe src='https://publisher.example/embed'></iframe>"
        "<p onclick='steal()'>Body <strong>important</strong>"
        "<a href='javascript:alert(1)' onerror='x'>unsafe</a>"
        "<a href='https://publisher.example/story'>source</a></p></div>"
    )
    cleaned = sanitize_foreign_html(raw)
    assert "publisher.example/image.jpg" not in cleaned
    assert "style=" not in cleaned and "onclick" not in cleaned
    assert "<img" not in cleaned and "<script" not in cleaned and "<iframe" not in cleaned
    assert "javascript:" not in cleaned
    assert '<a href="https://publisher.example/story">source</a>' in cleaned
    assert "important" in cleaned
    assert "Body" in sanitize_foreign_text(raw)


def test_nyt_chinese_example_html_is_sanitized_at_the_backend_boundary():
    raw = (
        "<div class='nyt-article' id='article-body' style='font-size:16px'>"
        "<p>纽约时报中文网示例正文</p>"
        "<img src='https://static.nytimes.com/photo.jpg' srcset='https://static.nytimes.com/2x.jpg 2x'>"
        "<script>window.__NYT__ = true</script><iframe src='https://www.nytimes.com/embed'></iframe>"
        "<p onerror='leak()'><em>安全内容</em></p></div>"
    )
    cleaned = sanitize_foreign_html(raw)
    assert "纽约时报中文网示例正文" in cleaned
    assert "安全内容" in cleaned
    assert "static.nytimes.com" not in cleaned
    assert "__NYT__" not in cleaned
    assert "iframe" not in cleaned
    assert "class=" not in cleaned and "id=" not in cleaned and "style=" not in cleaned


def test_foreign_workspace_separates_alert_rules_and_opens_foreign_details():
    source = WORKSPACE.read_text(encoding="utf-8")
    assert "value: 'alertRules'" in source
    assert "activeTab === 'alertRules'" in source
    assert "@click.stop=\"openAlertDetail(row)\"" in source
    assert "historyAlert" in source
    assert "api.get(`/foreign/alerts/${row.id}`)" in source
    assert "api.patch(`/foreign/alert-rules/${alertRuleEditingId.value}`" in source
    assert ':disabled="!alertRuleEditingId || !canEnableAlertRules"' in source
    assert "alertRuleDraft.is_enabled = rule.is_enabled" in source
    assert "v-html=\"selectedForeignAlert.opinion?.content || ''\"" in source


def test_foreign_probe_reports_article_fields_and_duplicate_urls(monkeypatch):
    xml = """<?xml version='1.0'?><rss version='2.0'><channel>
      <item><title>China climate update</title><description>A summary</description><link>https://news.example/a</link><pubDate>Sun, 09 Aug 2026 00:00:00 GMT</pubDate></item>
      <item><title>China climate update copy</title><description>Another summary</description><link>https://news.example/a</link><pubDate>Sun, 09 Aug 2026 01:00:00 GMT</pubDate></item>
    </channel></rss>"""

    def fake_get(self, url):
        self.last_http_status = 200
        return xml

    monkeypatch.setattr(ForeignRSSCollector, "_get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"],
        keywords=["China"],
        max_items=20,
        max_retries=0,
        respect_robots=False,
        is_foreign=True,
    )
    report = collector.probe()[0]
    assert report["http_status"] == 200
    assert report["xml_parsed"] is True
    assert report["valid_count"] == 2
    assert report["title_count"] == 2
    assert report["summary_count"] == 2
    assert report["published_time_count"] == 2
    assert report["matched_count"] == 2
    assert report["url_duplicate_count"] == 1


def test_foreign_source_persistence_requires_probe_success(client, auth_headers, monkeypatch):
    import app.api.foreign as foreign_api

    key = f"fixture_5g_gate_{uuid4().hex[:10]}"

    def fail_probe(*args, **kwargs):
        raise ValueError("Foreign feed test failed")

    monkeypatch.setattr(foreign_api, "test_foreign_source", fail_probe)
    failed = client.post(
        "/api/foreign/sources",
        headers=auth_headers,
        json={"name": "Failed probe fixture", "key": key, "feeds": ["https://fixture.test/rss"]},
    )
    assert failed.status_code == 422
    db = SessionLocal()
    try:
        assert db.query(DataSource).filter(DataSource.key == key).count() == 0
    finally:
        db.close()

    def pass_probe(*args, **kwargs):
        return {"success": True, "valid_count": 1, "matched_count": 1, "feeds": []}

    monkeypatch.setattr(foreign_api, "test_foreign_source", pass_probe)
    created = client.post(
        "/api/foreign/sources",
        headers=auth_headers,
        json={"name": "Successful probe fixture", "key": key, "feeds": ["https://fixture.test/rss"]},
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]
    monkeypatch.setattr(foreign_api, "test_foreign_source", fail_probe)
    failed_update = client.patch(
        f"/api/foreign/sources/{source_id}",
        headers=auth_headers,
        json={"name": "Rejected update"},
    )
    assert failed_update.status_code == 422
    db = SessionLocal()
    try:
        source = db.get(DataSource, source_id)
        assert source is not None
        assert source.name == "Successful probe fixture"
        assert source.enabled is False
        assert source.schedule_enabled is False
    finally:
        db.query(DataSource).filter(DataSource.id == source_id).delete(synchronize_session=False)
        db.commit()
        db.close()
