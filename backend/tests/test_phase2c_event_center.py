from datetime import datetime, timedelta
import uuid

from app.db.session import SessionLocal
from app.models.event import Event
from app.models.event_opinion import EventOpinion


def _event(region_id: int, *, title: str, risk: int, heat: int, trend: str, status: str, topic: str, offset: int) -> Event:
    now = datetime(2026, 7, 29, 12, 0, 0)
    return Event(
        title=f"{title}-{uuid.uuid4().hex[:8]}",
        description="phase2c test",
        keyword="phase2c",
        region_id=region_id,
        risk_level="high" if risk >= 70 else "medium" if risk >= 40 else "low",
        risk_score=risk,
        heat_score=heat,
        trend=trend,
        status=status,
        topic_category=topic,
        opinion_count=2,
        first_time=now - timedelta(days=offset + 1),
        last_time=now - timedelta(days=offset),
    )


def test_event_list_returns_phase2_fields_and_default_priority_order(
    client, auth_headers, seeded_region_id
):
    db = SessionLocal()
    rows = [
        _event(seeded_region_id, title="Phase2C sort", risk=90, heat=50, trend="stable", status="active", topic="traffic", offset=1),
        _event(seeded_region_id, title="Phase2C sort", risk=90, heat=80, trend="rising", status="processing", topic="livelihood", offset=2),
        _event(seeded_region_id, title="Phase2C sort", risk=70, heat=80, trend="rising", status="active", topic="safety", offset=0),
    ]
    db.add_all(rows)
    db.commit()
    ids = [row.id for row in rows]
    try:
        response = client.get(
            "/api/events",
            params={"title": "Phase2C sort", "page": 1, "size": 20},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        returned_ids = [item["id"] for item in data["items"]]
        assert returned_ids[:3] == [rows[1].id, rows[0].id, rows[2].id]
        item = next(item for item in data["items"] if item["id"] == rows[1].id)
        assert {"region_id", "status", "risk_score", "risk_level", "topic_category", "heat_score", "trend"} <= item.keys()
        assert item["heat_score"] == 80
        assert item["trend"] == "rising"
    finally:
        db = SessionLocal()
        db.query(EventOpinion).filter(EventOpinion.event_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.query(Event).filter(Event.id.in_(ids)).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_event_list_filters_by_region_topic_status_trend_and_heat(
    client, auth_headers, seeded_region_id
):
    db = SessionLocal()
    row = _event(
        seeded_region_id,
        title="Phase2C filter",
        risk=80,
        heat=75,
        trend="rising",
        status="processing",
        topic="traffic",
        offset=0,
    )
    db.add(row)
    db.commit()
    event_id = row.id
    try:
        response = client.get(
            "/api/events",
            params={
                "title": "Phase2C filter",
                "region_id": seeded_region_id,
                "topic_category": "traffic",
                "status": "processing",
                "trend": "rising",
                "heat_min": 70,
                "heat_max": 80,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["items"]] == [event_id]
    finally:
        db = SessionLocal()
        db.query(EventOpinion).filter(EventOpinion.event_id == event_id).delete()
        db.query(Event).filter(Event.id == event_id).delete()
        db.commit()
        db.close()


def test_event_detail_returns_phase2_fields(client, auth_headers, seeded_region_id):
    db = SessionLocal()
    row = _event(
        seeded_region_id,
        title="Phase2C detail",
        risk=75,
        heat=65,
        trend="rising",
        status="verifying",
        topic="safety",
        offset=0,
    )
    db.add(row)
    db.commit()
    event_id = row.id
    try:
        response = client.get(f"/api/events/{event_id}", headers=auth_headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["region_id"] == seeded_region_id
        assert data["status"] == "verifying"
        assert data["risk_score"] == 75
        assert data["risk_level"] == "high"
        assert data["topic_category"] == "safety"
        assert data["heat_score"] == 65
        assert data["trend"] == "rising"
        assert data["first_time"] is not None
        assert data["last_time"] is not None
    finally:
        db = SessionLocal()
        db.query(EventOpinion).filter(EventOpinion.event_id == event_id).delete()
        db.query(Event).filter(Event.id == event_id).delete()
        db.commit()
        db.close()
