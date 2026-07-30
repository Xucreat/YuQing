from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.models.propagation import PropagationNode
from app.services.event.aggregator import (
    EventAggregator,
    _event_risk_score,
    _event_topic_category,
)


def _opinion(db, region_id: int, *, risk: int, content_type: str, risk_category: str | None = None):
    opinion = Opinion(
        title="Test event title",
        content="Test event content",
        source="phase2a_test",
        url=f"https://example.test/{uuid.uuid4().hex}",
        region_id=region_id,
        risk_score=risk,
        sentiment="negative",
        summary="",
        keywords="事故",
        content_type=content_type,
        risk_category=risk_category,
        analysis_status="completed",
        publish_time=datetime.now(timezone.utc),
    )
    db.add(opinion)
    db.flush()
    return opinion


def test_event_field_derivation_is_lightweight_and_deterministic():
    opinions = [
        SimpleNamespace(
            id=1,
            risk_score=65,
            publish_time=None,
            created_at=datetime(2026, 7, 29),
            content_type="risk_event",
            risk_category="safety_accident",
        ),
        SimpleNamespace(
            id=2,
            risk_score=40,
            publish_time=None,
            created_at=datetime(2026, 7, 29),
            content_type="complaint",
            risk_category=None,
        ),
    ]

    assert _event_risk_score(opinions) == 65
    assert _event_topic_category(opinions) == "safety"


def test_event_model_defaults_and_fields(seeded_region_id):
    db = SessionLocal()
    event = None
    try:
        event = Event(
            title="Phase 2-A test event",
            description="test",
            keyword="test",
            region_id=seeded_region_id,
            risk_score=80,
            risk_level="high",
            topic_category="safety",
        )
        db.add(event)
        db.flush()

        assert event.region_id == seeded_region_id
        assert event.status == "active"
        assert event.risk_score == 80
        assert 0 <= event.risk_score <= 100
    finally:
        if event is not None:
            db.delete(event)
            db.commit()
        db.close()


def test_event_aggregator_populates_operable_fields(seeded_region_id):
    db = SessionLocal()
    opinions = []
    try:
        opinions.append(
            _opinion(
                db,
                seeded_region_id,
                risk=65,
                content_type="risk_event",
                risk_category="safety_accident",
            )
        )
        opinions.append(
            _opinion(
                db,
                seeded_region_id,
                risk=40,
                content_type="risk_event",
                risk_category="safety_accident",
            )
        )
        db.commit()

        result = EventAggregator().aggregate(db)
        assert result["created"] == 1

        event_id = (
            db.query(EventOpinion.event_id)
            .filter(EventOpinion.opinion_id == opinions[0].id)
            .scalar()
        )
        assert event_id is not None
        event = db.get(Event, event_id)
        assert event is not None
        assert event.region_id == seeded_region_id
        assert event.risk_score == 65
        assert event.risk_level == "medium"
        assert event.topic_category == "safety"
        assert event.status == "active"
    finally:
        event_ids = [row.event_id for row in db.query(EventOpinion).all() if row.opinion_id in {o.id for o in opinions}]
        if event_ids:
            db.query(PropagationNode).filter(PropagationNode.event_id.in_(event_ids)).delete(
                synchronize_session=False
            )
            db.query(EventOpinion).filter(EventOpinion.event_id.in_(event_ids)).delete(
                synchronize_session=False
            )
            db.query(Event).filter(Event.id.in_(event_ids)).delete(
                synchronize_session=False
            )
        if opinions:
            db.query(Opinion).filter(Opinion.id.in_([o.id for o in opinions])).delete(
                synchronize_session=False
            )
        db.commit()
        db.close()


def test_event_api_returns_persisted_status(client, auth_headers, seeded_region_id):
    db = SessionLocal()
    event = Event(
        title="Phase 2-A API status test",
        description="test",
        keyword="test",
        region_id=seeded_region_id,
        status="verifying",
        risk_score=50,
        risk_level="medium",
        topic_category="livelihood",
    )
    db.add(event)
    db.commit()
    event_id = event.id
    db.close()

    try:
        response = client.get(f"/api/events?page=1&size=20", headers=auth_headers)
        assert response.status_code == 200, response.text
        row = next(item for item in response.json()["items"] if item["id"] == event_id)
        assert row["status"] == "verifying"
        assert row["region_id"] == seeded_region_id
        assert row["risk_score"] == 50
        assert row["topic_category"] == "livelihood"
    finally:
        db = SessionLocal()
        db.query(EventOpinion).filter(EventOpinion.event_id == event_id).delete()
        db.query(Event).filter(Event.id == event_id).delete()
        db.commit()
        db.close()
