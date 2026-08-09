"""Isolated coverage for the gated cross-language candidate path."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_run import ForeignEventRun
from app.models.foreign_opinion import ForeignOpinion
from app.services.foreign_content_sanitizer import (
    detect_foreign_language,
    normalize_foreign_text,
    sanitize_foreign_html,
)
from app.services.foreign_event_auto_aggregation_service import (
    ForeignEventAutoAggregationService,
)
from app.services.foreign_event_service import ForeignEventService


def _row(db, suffix: str, *, source: str, title: str, content: str, hours: int = 0):
    now = datetime.now(timezone.utc) - timedelta(hours=hours)
    row = ForeignOpinion(
        source_key=f"cross_fixture_{suffix}_{source.casefold().replace(' ', '_')}",
        source_name_snapshot=source,
        title=title,
        summary=title,
        content=content,
        url=f"https://fixture.test/cross/{suffix}/{uuid.uuid4().hex}",
        content_hash=uuid.uuid4().hex,
        published_at=now,
        collected_at=now,
        matched_keywords=["fixture"],
    )
    db.add(row)
    db.flush()
    return row


def _cleanup(db, suffix: str) -> None:
    opinion_ids = [
        row.id
        for row in db.query(ForeignOpinion)
        .filter(ForeignOpinion.source_key.like(f"cross_fixture_{suffix}_%"))
        .all()
    ]
    opinion_id_set = set(opinion_ids)
    candidate_ids = [
        row.id
        for row in db.query(ForeignEventCandidate)
        .filter(ForeignEventCandidate.candidate_key.like("%"))
        .all()
        if opinion_id_set.intersection((row.evidence_json or {}).get("opinion_ids", []))
    ]
    event_ids = [
        row.id
        for row in db.query(ForeignEvent).filter(
            ForeignEvent.origin_candidate_id.in_(candidate_ids or [-1])
        ).all()
    ]
    if event_ids:
        db.query(ForeignEventAction).filter(ForeignEventAction.foreign_event_id.in_(event_ids)).delete(synchronize_session=False)
        db.query(ForeignEventOpinion).filter(ForeignEventOpinion.foreign_event_id.in_(event_ids)).delete(synchronize_session=False)
        db.query(ForeignEvent).filter(ForeignEvent.id.in_(event_ids)).delete(synchronize_session=False)
    if candidate_ids:
        db.query(ForeignEventAction).filter(ForeignEventAction.candidate_id.in_(candidate_ids)).delete(synchronize_session=False)
        db.query(ForeignEventCandidate).filter(ForeignEventCandidate.id.in_(candidate_ids)).delete(synchronize_session=False)
    if opinion_ids:
        db.query(ForeignOpinion).filter(ForeignOpinion.id.in_(opinion_ids)).delete(synchronize_session=False)
    db.commit()


def test_cross_language_generation_is_gated_and_same_language_remains_available(monkeypatch):
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    try:
        left = _row(db, suffix, source="Fox News", title=f"Trump Biden NATO summit {suffix}", content="Trump Biden NATO summit security response policy")
        right = _row(db, suffix, source="VOA Chinese", title=f"特朗普 Trump Biden NATO 峰会 {suffix}", content="Trump Biden NATO 中国 安全 政策")
        same = _row(db, suffix, source="The Guardian", title=f"Shared English briefing {suffix}", content="Shared English briefing leaders response policy")
        same2 = _row(db, suffix, source="BBC World", title=f"Shared English briefing {suffix}", content="Shared English briefing leaders response policy")
        db.commit()

        monkeypatch.setattr(settings, "foreign_event_cross_language_enabled", False)
        with pytest.raises(ValueError, match="disabled"):
            ForeignEventService().rebuild_candidates(db, opinion_ids=[left.id, right.id], cross_language=True)

        monkeypatch.setattr(settings, "foreign_event_cross_language_enabled", True)
        run, candidates, previews = ForeignEventService().rebuild_candidates(
            db,
            opinion_ids=[left.id, right.id, same.id, same2.id],
            cross_language=True,
            dry_run=True,
        )
        assert run.status == "dry_run"
        assert candidates == []
        assert any(item["language"] == "mixed" for item in previews)
        assert any(item["language"] == "en" for item in previews)
    finally:
        _cleanup(db, suffix)
        db.close()


def test_cross_language_candidate_is_manual_pending_and_auto_confirmation_is_rejected(monkeypatch):
    db = SessionLocal()
    suffix = uuid.uuid4().hex[:10]
    try:
        left = _row(db, suffix, source="Fox News", title="Trump Biden NATO summit", content="Trump Biden NATO summit security response policy")
        right = _row(db, suffix, source="VOA Chinese", title="特朗普 Trump Biden NATO 峰会", content="Trump Biden NATO 中国 安全 政策")
        db.commit()
        monkeypatch.setattr(settings, "foreign_event_cross_language_enabled", True)
        run, candidates, _ = ForeignEventService().rebuild_candidates(
            db, opinion_ids=[left.id, right.id], cross_language=True, dry_run=False
        )
        assert run.status == "success"
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.language == "mixed"
        assert candidate.candidate_status == "candidate"
        assert candidate.review_source == "manual"
        assert candidate.aggregation_version == "foreign-cross-v1"
        assert candidate.evidence_json["pending_reason"] == "cross_language_requires_manual_review"
        assert candidate.evidence_json["language_pair"] == ["en", "zh"]
        assert candidate.evidence_json["common_entities"]

        with pytest.raises(ValueError, match="manual confirmation"):
            ForeignEventService().confirm_candidate(
                db,
                candidate.id,
                user_id=None,
                confirmation_source="auto",
            )
        assert db.query(ForeignEvent).filter(ForeignEvent.origin_candidate_id == candidate.id).count() == 0

        monkeypatch.setattr(settings, "foreign_event_auto_aggregation_enabled", True)
        monkeypatch.setattr(settings, "foreign_event_cross_language_auto_confirm_enabled", True)
        with pytest.raises(PermissionError, match="not implemented"):
            ForeignEventAutoAggregationService().aggregate(db, dry_run=True, opinion_ids=[left.id, right.id])
    finally:
        _cleanup(db, suffix)
        db.close()


def test_sanitizer_removes_nyt_template_media_and_preserves_article_text():
    raw = (
        "<figure><img src='https://cdn.example/nyt.jpg'><figcaption>Photo Credit: NYT</figcaption></figure>"
        "<p class='caption'>Advertisement</p><p>Trump &amp; Biden discussed policy.</p>"
        "<script>alert('x')</script><style>.x{display:none}</style>"
    )
    cleaned_html = sanitize_foreign_html(raw)
    cleaned_text = normalize_foreign_text(raw)
    assert "cdn.example" not in cleaned_html
    assert "Photo Credit" not in cleaned_html
    assert "Advertisement" not in cleaned_html
    assert "Trump" in cleaned_html and "Biden" in cleaned_html
    assert "Trump & Biden discussed policy." in cleaned_text
    assert "alert" not in cleaned_text
    assert detect_foreign_language("特朗普 Trump Biden NATO 峰会") == "zh"


def test_auto_aggregate_api_rejects_cross_language_request(client, auth_headers):
    response = client.post(
        "/api/foreign/events/auto-aggregate",
        headers=auth_headers,
        json={"dry_run": True, "cross_language": True},
    )
    assert response.status_code == 409
    assert "manual review" in response.json()["detail"]
