"""Phase Foreign-Source-3B isolated event candidate and review tests."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import or_, text

from app.db.session import SessionLocal
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_run import ForeignEventRun
from app.models.foreign_opinion import ForeignOpinion
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.foreign_event_service import ForeignEventService


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _opinion(
    db,
    *,
    suffix: str,
    title: str,
    summary: str,
    content: str,
    source: str,
    language_marker: str = "en",
) -> ForeignOpinion:
    row = ForeignOpinion(
        source_key=f"fixture_{language_marker}_{suffix}",
        source_name_snapshot=source,
        title=title,
        summary=summary,
        content=content,
        url=f"https://fixture.test/foreign-event/{suffix}/{source.replace(' ', '-')}",
        published_at=datetime.now(timezone.utc),
        collected_at=datetime.now(timezone.utc),
        matched_keywords=["China"],
        content_hash=f"{suffix}{source}".encode().hex()[:64].ljust(64, "0"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _cleanup(db, suffix: str, since: datetime | None = None) -> None:
    opinion_ids = [
        row[0]
        for row in db.execute(
            text("select id from foreign_opinions where source_key like :prefix"),
            {"prefix": f"fixture_%_{suffix}"},
        ).all()
    ]
    candidate_rows = db.query(ForeignEventCandidate).all()
    candidate_ids = [
        row.id
        for row in candidate_rows
        if any(int(value) in opinion_ids for value in (row.evidence_json or {}).get("opinion_ids", []))
    ]
    event_ids = [
        row[0]
        for row in db.query(ForeignEventOpinion.foreign_event_id)
        .filter(ForeignEventOpinion.foreign_opinion_id.in_(opinion_ids))
        .distinct()
        .all()
    ] if opinion_ids else []
    action_filter = []
    if candidate_ids:
        action_filter.append(ForeignEventAction.candidate_id.in_(candidate_ids))
    if event_ids:
        action_filter.extend(
            [
                ForeignEventAction.foreign_event_id.in_(event_ids),
                ForeignEventAction.target_event_id.in_(event_ids),
            ]
        )
    action_filter.append(ForeignEventAction.request_id.like(f"%{suffix}%"))
    db.query(ForeignEventAction).filter(or_(*action_filter)).delete(
        synchronize_session=False
    )
    if event_ids:
        db.query(ForeignEventOpinion).filter(
            ForeignEventOpinion.foreign_event_id.in_(event_ids)
        ).delete(synchronize_session=False)
        db.query(ForeignEvent).filter(ForeignEvent.id.in_(event_ids)).delete(
            synchronize_session=False
        )
    if opinion_ids:
        if candidate_ids:
            db.query(ForeignEventCandidate).filter(
                ForeignEventCandidate.id.in_(candidate_ids)
            ).delete(synchronize_session=False)
        db.query(ForeignOpinion).filter(ForeignOpinion.id.in_(opinion_ids)).delete(
            synchronize_session=False
        )
    if since is not None:
        db.query(ForeignEventRun).filter(
            ForeignEventRun.started_at >= since
        ).delete(synchronize_session=False)
    db.commit()


def test_foreign_candidate_rebuild_is_idempotent_and_does_not_touch_domestic_tables():
    db = SessionLocal()
    suffix = _suffix()
    started = datetime.now(timezone.utc)
    domestic_counts = {
        "opinions": db.execute(text("select count(*) from opinions")).scalar(),
        "events": db.execute(text("select count(*) from events")).scalar(),
        "event_opinions": db.execute(text("select count(*) from event_opinions")).scalar(),
    }
    left = _opinion(
        db,
        suffix=suffix,
        title="Trade talks continue after China policy meeting",
        summary="Officials discuss tariffs and trade talks after a policy meeting.",
        content="The same trade talks continue with officials discussing tariffs and policy.",
        source="Fox Fixture",
    )
    right = _opinion(
        db,
        suffix=suffix,
        title="Trade talks continue after China policy meeting",
        summary="Officials discuss tariffs and trade talks after a policy meeting.",
        content="The same trade talks continue with officials discussing tariffs and policy.",
        source="Guardian Fixture",
    )
    try:
        service = ForeignEventService()
        dry_run, dry_candidates, previews = service.rebuild_candidates(
            db, dry_run=True, opinion_ids=[left.id, right.id]
        )
        assert dry_run.dry_run is True
        assert dry_run.status == "dry_run"
        assert dry_candidates == []
        assert len(previews) == 1
        assert previews[0]["language"] == "en"
        assert previews[0]["confidence"] >= 0.55
        assert previews[0]["evidence_json"]["similarity_method"] == "lexical_jaccard"
        assert previews[0]["evidence_json"]["similarity_threshold"] == 0.55
        assert previews[0]["evidence_json"]["candidate_reason"]
        assert db.query(ForeignEventCandidate).count() == 0

        run, candidates, _ = service.rebuild_candidates(
            db, dry_run=False, opinion_ids=[left.id, right.id]
        )
        assert run.status == "success"
        assert len(candidates) == 1
        repeat_run, repeated, _ = service.rebuild_candidates(
            db, dry_run=False, opinion_ids=[left.id, right.id]
        )
        assert repeat_run.status == "success"
        assert len(repeated) == 1
        assert db.query(ForeignEventCandidate).filter(
            ForeignEventCandidate.candidate_key == candidates[0].candidate_key
        ).count() == 1

        event = service.confirm_candidate(
            db, candidates[0].id, user_id=None, reason="fixture review"
        )
        assert event.event_status == "active"
        assert db.query(ForeignEventOpinion).filter(
            ForeignEventOpinion.foreign_event_id == event.id
        ).count() == 2
        assert all(
            row.matched_terms is not None
            for row in db.query(ForeignEventOpinion).filter(
                ForeignEventOpinion.foreign_event_id == event.id
            ).all()
        )
        assert db.query(ForeignEventCandidate).get(candidates[0].id).candidate_status == "converted"
        assert db.execute(text("select count(*) from opinions")).scalar() == domestic_counts["opinions"]
        assert db.execute(text("select count(*) from events")).scalar() == domestic_counts["events"]
        assert db.execute(text("select count(*) from event_opinions")).scalar() == domestic_counts["event_opinions"]
    finally:
        _cleanup(db, suffix, started)
        db.close()


def test_cross_language_articles_are_not_automatically_grouped():
    db = SessionLocal()
    suffix = _suffix()
    started = datetime.now(timezone.utc)
    english = _opinion(
        db,
        suffix=suffix,
        title="China policy meeting draws international attention",
        summary="Officials discuss trade policy and regional stability.",
        content="The policy meeting discusses trade and regional stability.",
        source="English Fixture",
    )
    chinese = _opinion(
        db,
        suffix=suffix,
        title="中国政策会议引发关注",
        summary="官员讨论贸易政策和地区稳定。",
        content="这次政策会议讨论贸易和地区稳定。",
        source="Chinese Fixture",
        language_marker="zh",
    )
    try:
        _, _, previews = ForeignEventService().rebuild_candidates(
            db, dry_run=True, opinion_ids=[english.id, chinese.id]
        )
        assert previews == []
    finally:
        _cleanup(db, suffix, started)
        db.close()


def test_duplicate_url_is_removed_before_candidate_generation():
    db = SessionLocal()
    suffix = _suffix()
    started = datetime.now(timezone.utc)
    left = _opinion(
        db,
        suffix=suffix,
        title="China duplicate fixture",
        summary="Same source article.",
        content="Same source article content.",
        source="Duplicate A",
    )
    right = _opinion(
        db,
        suffix=suffix,
        title="China duplicate fixture",
        summary="Same source article.",
        content="Same source article content.",
        source="Duplicate B",
    )
    right.url = left.url
    right.url = f"https://fixture.test/{suffix}/duplicate"
    right.duplicate_of_id = left.id
    db.commit()
    try:
        run, _, previews = ForeignEventService().rebuild_candidates(
            db, dry_run=True, opinion_ids=[left.id, right.id]
        )
        assert run.input_count == 2
        assert run.deduplicated_count == 1
        assert previews == []
    finally:
        _cleanup(db, suffix, started)
        db.close()


def test_foreign_event_api_isolated_and_rebuild_defaults_to_dry_run(client, auth_headers):
    db = SessionLocal()
    suffix = _suffix()
    started = datetime.now(timezone.utc)
    left = _opinion(
        db,
        suffix=suffix,
        title="API China event fixture",
        summary="Officials discuss shared trade policy.",
        content="The same officials discuss shared trade policy and tariffs.",
        source="API Fox",
    )
    right = _opinion(
        db,
        suffix=suffix,
        title="API China event fixture",
        summary="Officials discuss shared trade policy.",
        content="The same officials discuss shared trade policy and tariffs.",
        source="API Guardian",
    )
    try:
        response = client.post(
            "/api/foreign/events/rebuild",
            headers=auth_headers,
            json={"opinion_ids": [left.id, right.id]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["run"]["dry_run"] is True
        assert response.json()["items"] == []
        assert len(response.json()["previews"]) == 1

        response = client.post(
            "/api/foreign/events/rebuild",
            headers=auth_headers,
            json={"opinion_ids": [left.id, right.id], "dry_run": False},
        )
        assert response.status_code == 200, response.text
        candidate_id = response.json()["items"][0]["id"]

        candidate_list = client.get(
            "/api/foreign/events/candidates",
            headers=auth_headers,
            params={"q": "API China event fixture"},
        )
        assert candidate_list.status_code == 200
        assert candidate_list.json()["items"][0]["id"] == candidate_id

        confirmed = client.post(
            f"/api/foreign/events/candidates/{candidate_id}/confirm",
            headers=auth_headers,
            json={"reason": "manual fixture confirmation", "request_id": f"confirm-{suffix}"},
        )
        assert confirmed.status_code == 200, confirmed.text
        foreign_event_id = confirmed.json()["id"]
        assert client.get(
            f"/api/foreign/events/{foreign_event_id}",
            headers=auth_headers,
        ).status_code == 200
        assert client.get(
            "/api/events",
            headers=auth_headers,
            params={"title": "API China event fixture"},
        ).json()["items"] == []
        assert client.get(
            "/api/foreign/event-actions",
            headers=auth_headers,
        ).json()["total"] >= 1
    finally:
        _cleanup(db, suffix, started)
        db.close()
