from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.event.heat_service import (
    EventHeatService,
    calculate_event_heat,
)


NOW = datetime(2026, 7, 29, 12, 0, 0)


def _row(at: datetime, engagement: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        publish_time=at,
        created_at=at,
        engagement=engagement or {},
    )


def test_heat_score_is_bounded_and_explainable():
    metrics = calculate_event_heat(
        [_row(NOW, {"likes": 10000, "comments": 10000, "reposts": 10000}) for _ in range(50)],
        now=NOW,
    )

    assert 0 <= metrics.heat_score <= 100
    assert metrics.reason["opinion_count"] == 50
    assert metrics.reason["recent_24h_count"] == 50


def test_trend_calculation_covers_rising_stable_and_falling():
    rising = [_row(NOW - timedelta(days=2)) for _ in range(2)]
    rising.extend(_row(NOW - timedelta(hours=2)) for _ in range(4))
    assert calculate_event_heat(rising, now=NOW).trend == "rising"

    stable = [_row(NOW - timedelta(days=day, hours=1)) for day in range(1, 8)]
    stable.append(_row(NOW - timedelta(hours=2)))
    assert calculate_event_heat(stable, now=NOW).trend == "stable"

    falling = [_row(NOW - timedelta(days=day, hours=1)) for day in range(1, 8)]
    assert calculate_event_heat(falling, now=NOW).trend == "falling"


def test_event_heat_refresh_recalculates_after_members_change(seeded_region_id):
    db = SessionLocal()
    event = None
    opinions: list[Opinion] = []
    try:
        event = Event(
            title="Phase 2-B heat test",
            description="test",
            keyword="test",
            region_id=seeded_region_id,
            risk_level="low",
        )
        db.add(event)
        db.flush()
        for _ in range(2):
            opinion = Opinion(
                title="test opinion",
                content="test content",
                source="phase2b_test",
                url=f"https://example.test/{uuid.uuid4().hex}",
                region_id=seeded_region_id,
                risk_score=20,
                sentiment="neutral",
                summary="",
                keywords="test",
                analysis_status="completed",
                publish_time=NOW.replace(tzinfo=timezone.utc),
            )
            db.add(opinion)
            db.flush()
            opinions.append(opinion)
            db.add(EventOpinion(event_id=event.id, opinion_id=opinion.id))
        db.flush()

        first = EventHeatService().refresh(db, event, now=NOW)
        event.opinion_count = 2
        assert event.heat_score == first.heat_score

        opinion = Opinion(
            title="new opinion",
            content="new content",
            source="phase2b_test",
            url=f"https://example.test/{uuid.uuid4().hex}",
            region_id=seeded_region_id,
            risk_score=20,
            sentiment="neutral",
            summary="",
            keywords="test",
            analysis_status="completed",
            publish_time=NOW.replace(tzinfo=timezone.utc),
        )
        db.add(opinion)
        db.flush()
        opinions.append(opinion)
        db.add(EventOpinion(event_id=event.id, opinion_id=opinion.id))
        db.flush()

        second = EventHeatService().refresh(db, event, now=NOW)
        assert second.heat_score > first.heat_score
        assert event.heat_score == second.heat_score
    finally:
        if event is not None:
            db.query(EventOpinion).filter(EventOpinion.event_id == event.id).delete(
                synchronize_session=False
            )
            db.delete(event)
        if opinions:
            db.query(Opinion).filter(Opinion.id.in_([op.id for op in opinions])).delete(
                synchronize_session=False
            )
        db.commit()
        db.close()


def test_event_api_returns_heat_and_trend(client, auth_headers, seeded_region_id):
    db = SessionLocal()
    event = Event(
        title="Phase 2-B API heat test",
        description="test",
        keyword="test",
        region_id=seeded_region_id,
        risk_level="medium",
        risk_score=50,
        heat_score=72,
        trend="rising",
    )
    db.add(event)
    db.commit()
    event_id = event.id
    db.close()

    try:
        response = client.get("/api/events?page=1&size=20", headers=auth_headers)
        assert response.status_code == 200, response.text
        row = next(item for item in response.json()["items"] if item["id"] == event_id)
        assert row["heat_score"] == 72
        assert row["trend"] == "rising"

        detail = client.get(f"/api/events/{event_id}", headers=auth_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["heat_score"] == 72
        assert detail.json()["trend"] == "rising"
    finally:
        db = SessionLocal()
        db.query(EventOpinion).filter(EventOpinion.event_id == event_id).delete()
        db.query(Event).filter(Event.id == event_id).delete()
        db.commit()
        db.close()
