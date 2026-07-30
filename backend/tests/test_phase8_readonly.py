"""Phase 8 read-only health and event situation tests."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
import uuid

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.data_source_health import DataSourceHealthSummaryService
from app.services.error_codes import normalize_error_code
from app.services.event.risk_shadow import EventRiskShadowService
from app.services.event.situation import EventSituationService


def _run(start, status="success", *, failed=0, fetched=1, created=1, error=None, ident=1):
    return SimpleNamespace(
        id=ident, start_time=start, status=status, failed=failed,
        fetched_raw=fetched, created=created, error_msg=error,
    )


def test_phase8_token_expired_mapping():
    assert normalize_error_code("Octopus HTTP 401 unauthorized") == "TOKEN_EXPIRED"
    assert normalize_error_code("access token expired") == "TOKEN_EXPIRED"


def test_phase8_consecutive_failures_and_recovery():
    now = datetime(2026, 7, 30, 12)
    ds = SimpleNamespace(id=1, enabled=True)
    service = DataSourceHealthSummaryService()
    failed = [_run(now - timedelta(hours=i), "failed", failed=1, fetched=0, created=0, ident=i, error="timeout") for i in (1, 2, 3)]
    assert service.summarize(ds, failed, now=now)["health_status"] == "unhealthy"
    recovered = [_run(now, "success", ident=10), *failed]
    summary = service.summarize(ds, recovered, now=now)
    assert summary["health_status"] == "healthy"
    assert summary["consecutive_failures"] == 0


def test_phase8_empty_success_is_not_failure():
    now = datetime(2026, 7, 30, 12)
    summary = DataSourceHealthSummaryService().summarize(
        SimpleNamespace(id=1, enabled=True),
        [_run(now, "success", fetched=0, created=0)],
        now=now,
    )
    assert summary["consecutive_failures"] == 0
    assert summary["health_status"] == "healthy"


def test_phase8_disabled_and_independent_sources():
    now = datetime(2026, 7, 30, 12)
    service = DataSourceHealthSummaryService()
    failed = service.summarize(SimpleNamespace(id=1, enabled=True), [_run(now, "failed", failed=1, error="HTTP 500")], now=now)
    healthy = service.summarize(SimpleNamespace(id=2, enabled=True), [_run(now, "success")], now=now)
    paused = service.summarize(SimpleNamespace(id=3, enabled=False), [], now=now)
    assert failed["health_status"] == "degraded"
    assert healthy["health_status"] == "healthy"
    assert paused["health_status"] == "paused"


def _new_event(region_id: int) -> Event:
    return Event(
        title=f"phase8-{uuid.uuid4().hex}", description="", keyword="phase8",
        region_id=region_id, risk_level="low", risk_score=5,
        topic_category="safety", status="active",
    )


def _new_opinion(region_id: int, *, source: str, risk: int, when: datetime, keywords: str = "") -> Opinion:
    return Opinion(
        title="phase8 opinion", content="content", source=source,
        url=f"https://phase8.example/{uuid.uuid4().hex}", region_id=region_id,
        risk_score=risk, sentiment="negative" if risk >= 70 else "neutral",
        keywords=keywords, publish_time=when,
    )


def test_phase8_event_situation_empty_and_sufficient_data(seeded_region_id):
    db = SessionLocal()
    event = _new_event(seeded_region_id)
    db.add(event)
    db.commit()
    try:
        empty = EventSituationService().build(db, event.id)
        assert empty["data_sufficiency"]["level"] == "insufficient"
        when = datetime(2026, 7, 29, 12)
        opinions = [
            _new_opinion(seeded_region_id, source="微博", risk=85, when=when, keywords="安全,事故"),
            _new_opinion(seeded_region_id, source="新闻", risk=30, when=when + timedelta(days=1), keywords="安全"),
            _new_opinion(seeded_region_id, source="政府网站", risk=20, when=when + timedelta(days=2), keywords="通报"),
        ]
        db.add_all(opinions)
        db.flush()
        db.add_all(EventOpinion(event_id=event.id, opinion_id=item.id) for item in opinions)
        db.commit()
        data = EventSituationService().build(db, event.id)
        assert len(data["source_distribution"]) == 3
        assert data["data_sufficiency"]["level"] == "sufficient"
        assert data["risk_factors"]
        assert data["trend_summary"]["direction"] in {"rising", "stable", "falling"}
    finally:
        db.query(EventOpinion).filter(EventOpinion.event_id == event.id).delete(synchronize_session=False)
        db.query(Opinion).filter(Opinion.url.like("https://phase8.example/%")).delete(synchronize_session=False)
        db.query(Event).filter(Event.id == event.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_phase8_single_high_opinion_does_not_make_event_high():
    event = SimpleNamespace(region_id=1, topic_category="safety")
    opinion = SimpleNamespace(risk_score=100, region_id=1, publish_time=datetime(2026, 7, 29), sentiment="negative")
    result = EventRiskShadowService.calculate(event, [opinion])
    assert result["score"] < 70
    assert result["score_version"] == "event-risk-shadow-v1"
    assert {factor["factor"] for factor in result["factors"]} == {"content_risk", "volume", "growth", "locality", "event_type"}

