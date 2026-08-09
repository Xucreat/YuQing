"""Focused Phase 5A-5E tests for the isolated opinion_test database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid

from sqlalchemy import func, select, text

from app.db.session import SessionLocal
from app.models.collector_run import CollectorRun
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_analysis_run import ForeignAnalysisRun
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.schemas.ai import AIAnalysisResult
from app.services.foreign_event_service import (
    ForeignEventService,
    recompute_foreign_event_metrics,
)


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _opinion(db, suffix: str) -> ForeignOpinion:
    row = ForeignOpinion(
        source_key=f"phase5_{suffix}",
        source_name_snapshot="Phase 5 fixture",
        title=f"Phase 5 article {suffix}",
        summary="A foreign fixture summary.",
        content="A sufficiently long foreign fixture article body.",
        url=f"https://fixture.test/phase5/{suffix}",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        matched_keywords=["China"],
        content_hash=(suffix * 8)[:64],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_foreign_detail_and_mocked_ai_are_isolated(client, auth_headers, monkeypatch):
    suffix = _suffix()
    monkeypatch.setenv("FOREIGN_AI_REVIEW_ENABLED", "true")

    class FakeProvider:
        is_configured = True

        def analyze(self, text: str) -> AIAnalysisResult:
            assert "Phase 5 article" in text
            return AIAnalysisResult(
                summary="mocked foreign summary",
                sentiment="negative",
                risk_score=81,
                keywords=["China"],
                suggestion="mocked review suggestion",
            )

    monkeypatch.setattr("app.services.foreign_ai_service.DeepSeekProvider", FakeProvider)
    db = SessionLocal()
    opinion = _opinion(db, suffix)
    try:
        detail = client.get(f"/api/foreign/opinions/{opinion.id}/detail", headers=auth_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["rule_result"] is None
        response = client.post(
            f"/api/foreign/opinions/{opinion.id}/ai-analyze",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
        db.expire_all()
        result = db.scalar(
            select(ForeignAIResult).where(ForeignAIResult.foreign_opinion_id == opinion.id)
        )
        assert result is not None and result.is_current is True
        assert db.scalar(
            select(func.count()).select_from(ForeignAnalysisRun).where(
                ForeignAnalysisRun.foreign_opinion_id == opinion.id,
                ForeignAnalysisRun.analyzer_type == "ai",
            )
        ) == 1
        refreshed = client.get(f"/api/foreign/opinions/{opinion.id}/detail", headers=auth_headers)
        assert refreshed.json()["ai_result"]["summary"] == "mocked foreign summary"
        assert "opinions" not in refreshed.json()["ai_result"]
    finally:
        db.query(ForeignAIResult).filter(ForeignAIResult.foreign_opinion_id == opinion.id).delete(synchronize_session=False)
        db.query(ForeignAnalysisRun).filter(ForeignAnalysisRun.foreign_opinion_id == opinion.id).delete(synchronize_session=False)
        db.query(ForeignOpinion).filter(ForeignOpinion.id == opinion.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_foreign_source_probe_does_not_write_rows(client, auth_headers, monkeypatch):
    from app.collectors.foreign_rss import ForeignRSSCollector

    def fake_probe(self):
        self.last_fetched_raw = 3
        self.last_failed_feeds = 0
        self.last_error = None
        self.last_feed_reports = [{
            "feed": "https://fixture.test/rss",
            "http_status": 200,
            "xml_parsed": True,
            "raw_count": 3,
            "matched_count": 2,
            "failure_count": 0,
            "error": None,
        }]
        return self.last_feed_reports

    monkeypatch.setattr(ForeignRSSCollector, "probe", fake_probe)
    db = SessionLocal()
    try:
        opinions_before = db.scalar(select(func.count()).select_from(ForeignOpinion))
        runs_before = db.scalar(select(func.count()).select_from(CollectorRun).where(CollectorRun.scope == "foreign"))
        response = client.post(
            "/api/foreign/sources/test",
            headers=auth_headers,
            json={"name": "Probe fixture", "feeds": ["https://fixture.test/rss"], "fetch_full_text": False},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["feeds"][0]["http_status"] == 200
        assert db.scalar(select(func.count()).select_from(ForeignOpinion)) == opinions_before
        assert db.scalar(select(func.count()).select_from(CollectorRun).where(CollectorRun.scope == "foreign")) == runs_before
    finally:
        db.close()


def test_foreign_source_probe_hides_sensitive_request_errors(client, auth_headers, monkeypatch):
    from app.collectors.foreign_rss import ForeignRSSCollector

    def fake_probe(self):
        self.last_fetched_raw = 0
        self.last_failed_feeds = 1
        self.last_error = "GET https://user:password@proxy.test/feed?token=secret failed"
        self.last_feed_reports = [{
            "feed": "https://fixture.test/rss",
            "http_status": 502,
            "xml_parsed": False,
            "raw_count": 0,
            "matched_count": 0,
            "failure_count": 1,
            "error": "RSS feed request or XML parsing failed",
        }]
        return self.last_feed_reports

    monkeypatch.setattr(ForeignRSSCollector, "probe", fake_probe)
    response = client.post(
        "/api/foreign/sources/test",
        headers=auth_headers,
        json={"name": "Sensitive probe fixture", "feeds": ["https://fixture.test/rss"]},
    )
    assert response.status_code == 200, response.text
    body = response.text.casefold()
    assert "password" not in body
    assert "proxy.test" not in body
    assert "secret" not in body


def test_foreign_keyword_crud_bulk_and_alert_rule_gate(client, auth_headers):
    suffix = _suffix()
    db = SessionLocal()
    keyword_id = None
    try:
        created = client.post(
            "/api/foreign/keywords",
            headers=auth_headers,
            json={"word": f"phase5-{suffix}", "category": "phase5", "type": "sensitive", "weight": 70, "severity_weight": 80},
        )
        assert created.status_code == 201, created.text
        keyword_id = created.json()["id"]
        updated = client.patch(
            f"/api/foreign/keywords/{keyword_id}",
            headers=auth_headers,
            json={"weight": 90, "is_enabled": False},
        )
        assert updated.status_code == 200 and updated.json()["weight"] == 90
        bulk = client.post(
            "/api/foreign/keywords/bulk-status",
            headers=auth_headers,
            json={"keyword_ids": [keyword_id], "is_enabled": True},
        )
        assert bulk.status_code == 200 and bulk.json()["changed"] == 1
        duplicate = client.post(
            "/api/foreign/keywords",
            headers=auth_headers,
            json={"word": f"phase5-{suffix}"},
        )
        assert duplicate.status_code == 409
        invalid_rule = client.post(
            "/api/foreign/alert-rules",
            headers=auth_headers,
            json={"name": f"phase5 {suffix}", "rule_type": "risk_score", "conditions": {"threshold": 1}, "is_enabled": True},
        )
        assert invalid_rule.status_code == 422
    finally:
        if keyword_id is not None:
            db.query(ForeignKeyword).filter(ForeignKeyword.id == keyword_id).delete(synchronize_session=False)
            db.commit()
        db.close()


def test_confirmed_foreign_event_can_be_closed_and_frontend_uses_probe_contract():
    suffix = _suffix()
    db = SessionLocal()
    event = ForeignEvent(
        title=f"Phase 5 close {suffix}",
        summary="fixture",
        language="en",
        event_status="confirmed",
        risk_level="unknown",
        heat_score=0,
        opinion_count=0,
        source_count=0,
        confidence=0.8,
    )
    db.add(event)
    db.commit()
    try:
        closed = ForeignEventService().update_status(
            db,
            event.id,
            status="resolved",
            user_id=None,
            reason="fixture close",
            request_id=f"close-{suffix}",
        )
        assert closed.event_status == "resolved"
        workspace = (Path(__file__).resolve().parents[2] / "frontend/src/views/ForeignWorkspace.vue").read_text(encoding="utf-8")
        assert "sourceTestResult.success" in workspace
        assert "sourceTestResult.ok" not in workspace
    finally:
        db.query(ForeignEvent).filter(ForeignEvent.id == event.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_foreign_event_merge_split_recomputes_metrics_and_keeps_domestic_snapshot():
    suffix = _suffix()
    db = SessionLocal()
    # Query domestic tables explicitly so this assertion remains independent of
    # the SQLAlchemy model registry used by the foreign fixture.
    domestic_before = {
        table: db.execute(text(f"select count(*) from {table}")).scalar()
        for table in ("opinions", "events", "event_opinions", "alert_records")
    }
    opinions: list[ForeignOpinion] = []
    event_ids: list[int] = []
    risk_ids: list[int] = []
    action_ids: list[int] = []
    base_time = datetime.now(timezone.utc) - timedelta(hours=4)

    def utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    try:
        for index, source in enumerate(("Merge Fox", "Merge Guardian", "Split Fox", "Split Guardian")):
            row = _opinion(db, f"{suffix}-{index}")
            row.source_key = f"phase5_merge_{suffix}_{index}"
            row.source_name_snapshot = source
            row.published_at = base_time + timedelta(hours=index)
            row.collected_at = base_time + timedelta(hours=index)
            db.commit()
            opinions.append(row)
            risk = ForeignRiskResult(
                foreign_opinion_id=row.id,
                content_hash=row.content_hash,
                language="en",
                risk_score=90 if index == 3 else 40 + index,
                risk_level="high" if index == 3 else "medium",
                sentiment="negative",
                risk_category="security",
                matched_terms=[{"word": "conflict", "severity_weight": 70}],
                explanation="phase 5 merge/split fixture",
                analyzer_type="rule",
                model_version="phase5-fixture-v1",
                analysis_status="completed",
                is_current=True,
                analyzed_at=base_time + timedelta(hours=index),
            )
            db.add(risk)
            db.flush()
            risk_ids.append(risk.id)

        def make_event(title: str, members: list[ForeignOpinion]) -> ForeignEvent:
            event = ForeignEvent(
                title=title,
                summary="phase 5 merge/split fixture",
                language="en",
                event_status="confirmed",
                risk_level="unknown",
                heat_score=0,
                opinion_count=0,
                source_count=0,
                confidence=0.8,
            )
            db.add(event)
            db.flush()
            for member in members:
                db.add(ForeignEventOpinion(foreign_event_id=event.id, foreign_opinion_id=member.id))
            recompute_foreign_event_metrics(db, event.id)
            db.flush()
            event_ids.append(event.id)
            return event

        target = make_event(f"Phase 5 target {suffix}", opinions[:2])
        source = make_event(f"Phase 5 source {suffix}", opinions[2:])
        db.commit()
        article_times = {
            row.id: utc(row.published_at or row.collected_at)
            for row in opinions
        }

        service = ForeignEventService()
        merged = service.merge_events(
            db,
            source.id,
            target.id,
            user_id=None,
            reason="phase 5 merge fixture",
            request_id=f"merge-{suffix}",
        )
        db.refresh(merged)
        assert merged.id == target.id
        assert merged.opinion_count == 4
        assert merged.source_count == 4
        assert utc(merged.first_seen_at) == min(article_times.values())
        assert utc(merged.last_seen_at) == max(article_times.values())
        assert merged.heat_score == 90
        assert merged.risk_level == "high"
        db.refresh(source)
        assert source.event_status == "archived"
        assert source.opinion_count == 0

        split = service.split_event(
            db,
            merged.id,
            [opinions[2].id, opinions[3].id],
            user_id=None,
            reason="phase 5 split fixture",
            request_id=f"split-{suffix}",
        )
        event_ids.append(split.id)
        db.refresh(merged)
        assert split.event_status == "confirmed"
        assert split.opinion_count == 2
        assert split.source_count == 2
        assert utc(split.first_seen_at) == min(article_times[opinions[2].id], article_times[opinions[3].id])
        assert utc(split.last_seen_at) == max(article_times[opinions[2].id], article_times[opinions[3].id])
        assert split.heat_score == 90
        assert split.risk_level == "high"
        assert merged.opinion_count == 2
        assert merged.source_count == 2
        assert utc(merged.first_seen_at) == min(article_times[opinions[0].id], article_times[opinions[1].id])
        assert utc(merged.last_seen_at) == max(article_times[opinions[0].id], article_times[opinions[1].id])
        assert merged.heat_score == 41
        assert merged.risk_level == "medium"
        actions = db.query(ForeignEventAction).filter(
            ForeignEventAction.request_id.in_([f"merge-{suffix}", f"split-{suffix}"])
        ).all()
        action_ids.extend(row.id for row in actions)
        assert {row.action_type for row in actions} == {"merge", "split"}
        for table, expected in domestic_before.items():
            assert db.execute(text(f"select count(*) from {table}")).scalar() == expected
    finally:
        if action_ids:
            db.query(ForeignEventAction).filter(ForeignEventAction.id.in_(action_ids)).delete(synchronize_session=False)
        if event_ids:
            db.query(ForeignEventOpinion).filter(ForeignEventOpinion.foreign_event_id.in_(event_ids)).delete(synchronize_session=False)
            db.query(ForeignEvent).filter(ForeignEvent.id.in_(event_ids)).delete(synchronize_session=False)
        if risk_ids:
            db.query(ForeignRiskResult).filter(ForeignRiskResult.id.in_(risk_ids)).delete(synchronize_session=False)
        if opinions:
            db.query(ForeignOpinion).filter(ForeignOpinion.id.in_([row.id for row in opinions])).delete(synchronize_session=False)
        db.commit()
        db.close()
