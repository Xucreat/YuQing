from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.alert import AlertRecord, AlertRule
from app.models.domestic_ai_alert_candidate import DomesticAIAlertCandidate
from app.models.domestic_ai_result import DomesticAIResult
from app.models.domestic_manual_review import DomesticManualReview
from app.models.event import Event
from app.models.event_opinion import EventOpinion
from app.models.opinion import Opinion
from app.services.event.aggregator import _map_risk_level


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _risk_level(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _rule_risk_snapshot(opinion: Opinion) -> dict[str, Any]:
    return {
        "source": "rule",
        "effective_risk_source": "rule",
        "risk_score": opinion.risk_score,
        "risk_level": _risk_level(opinion.risk_score),
        "sentiment": opinion.sentiment,
        "keywords": [item.strip() for item in (opinion.keywords or "").split(",") if item.strip()],
        "risk_factors": opinion.risk_factors or {},
        "risk_model_version": opinion.risk_model_version,
    }


def _ai_risk_snapshot(result: DomesticAIResult) -> dict[str, Any]:
    return {
        "source": "ai",
        "id": result.id,
        "risk_score": result.risk_score,
        "risk_level": _risk_level(result.risk_score),
        "sentiment": result.sentiment,
        "summary": result.summary,
        "keywords": result.keywords or [],
        "suggestion": result.suggestion,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "analyzed_at": result.analyzed_at.isoformat() if result.analyzed_at else None,
    }


def _rule_snapshot(rule: AlertRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "risk_threshold": rule.risk_threshold,
        "keywords": rule.keywords,
        "sources": rule.sources,
        "risk_level": rule.risk_level,
        "enabled": rule.enabled,
    }


def _rule_keyword_match(rule: AlertRule, opinion: Opinion, ai_result: DomesticAIResult) -> bool:
    if not rule.keywords:
        return True
    haystack = "\n".join(
        [
            opinion.title or "",
            opinion.content or "",
            ",".join(ai_result.keywords or []),
            ai_result.summary or "",
        ]
    )
    return any(word.strip() and word.strip() in haystack for word in rule.keywords.split(","))


def _rule_source_match(rule: AlertRule, opinion: Opinion) -> bool:
    if not rule.sources:
        return True
    sources = [item.strip() for item in rule.sources.split(",") if item.strip()]
    return not sources or opinion.source in sources


def generate_domestic_ai_alert_candidates(
    db: Session,
    *,
    review_id: int,
    opinion_id: int,
    ai_result_id: int,
) -> list[DomesticAIAlertCandidate]:
    db.execute(
        delete(DomesticAIAlertCandidate).where(
            DomesticAIAlertCandidate.review_id == review_id,
            DomesticAIAlertCandidate.candidate_status == "pending",
        )
    )
    opinion = db.get(Opinion, opinion_id)
    ai_result = db.get(DomesticAIResult, ai_result_id)
    if opinion is None or ai_result is None or ai_result.status != "completed":
        db.flush()
        return []
    ai_score = ai_result.risk_score
    candidates: list[DomesticAIAlertCandidate] = []
    rules = db.scalars(
        select(AlertRule)
        .where(AlertRule.enabled.is_(True), AlertRule.rule_type == "ai_risk_score")
        .order_by(AlertRule.id.asc())
    ).all()
    ai_snapshot = _ai_risk_snapshot(ai_result)
    for rule in rules:
        if ai_score is None or ai_score < rule.risk_threshold:
            continue
        if not _rule_source_match(rule, opinion) or not _rule_keyword_match(rule, opinion, ai_result):
            continue
        candidate = DomesticAIAlertCandidate(
            review_id=review_id,
            opinion_id=opinion_id,
            rule_id=rule.id,
            ai_result_id=ai_result_id,
            rule_snapshot=_rule_snapshot(rule),
            ai_snapshot=ai_snapshot,
            matched_conditions={
                "ai_risk_score": ai_score,
                "threshold": rule.risk_threshold,
                "evaluation_source": "ai",
            },
            deduplication_key=f"domestic:rule:{rule.id}:opinion:{opinion_id}:ai:{ai_result_id}:review:{review_id}",
        )
        db.add(candidate)
        candidates.append(candidate)
    db.flush()
    return candidates


def _event_preview(opinion: Opinion, ai_result: DomesticAIResult) -> dict[str, Any]:
    score = int(ai_result.risk_score or 0)
    has_candidate = score >= 70 or bool(ai_result.keywords)
    item = {
        "opinion_ids": [opinion.id],
        "opinion_id": opinion.id,
        "title": opinion.title,
        "change_type": "new_candidate_event" if has_candidate else "no_change",
        "rule_risk_score": opinion.risk_score,
        "ai_risk_score": ai_result.risk_score,
        "risk_level": _risk_level(score),
        "reason": "AI 风险较高或抽取到可解释关键词，需人工确认是否生成正式事件" if has_candidate else "AI 未形成明确事件候选",
    }
    return {
        "candidate_count": 1 if has_candidate else 0,
        "items": [item] if has_candidate else [],
        "requires_manual_confirmation": True,
    }


def _refresh_review_alert_preview(db: Session, review: DomesticManualReview) -> None:
    count = int(
        db.scalar(
            select(func.count())
            .select_from(DomesticAIAlertCandidate)
            .where(DomesticAIAlertCandidate.review_id == review.id)
        ) or 0
    )
    review.alert_preview = {
        "candidate_count": count,
        "requires_manual_confirmation": True,
    }


def ensure_domestic_manual_review(
    db: Session,
    opinion_id: int,
    ai_result_id: int,
    batch_run_id: str | None = None,
    force: bool = False,
) -> tuple[DomesticManualReview, bool]:
    ai_result = db.get(DomesticAIResult, ai_result_id)
    if ai_result is None or ai_result.status != "completed":
        raise ValueError("AI completed result is required before manual review")
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise LookupError("Opinion not found")

    existing = db.scalar(
        select(DomesticManualReview)
        .where(
            DomesticManualReview.opinion_id == opinion_id,
            DomesticManualReview.review_status == "pending_review",
        )
        .order_by(DomesticManualReview.id.desc())
    )
    if existing is not None and not force:
        if batch_run_id and not existing.batch_run_id:
            existing.batch_run_id = batch_run_id
        pending = int(
            db.scalar(
                select(func.count())
                .select_from(DomesticAIAlertCandidate)
                .where(DomesticAIAlertCandidate.review_id == existing.id)
            ) or 0
        )
        if not pending:
            generate_domestic_ai_alert_candidates(
                db,
                review_id=existing.id,
                opinion_id=opinion_id,
                ai_result_id=ai_result_id,
            )
            _refresh_review_alert_preview(db, existing)
        db.flush()
        return existing, False

    if existing is not None and force:
        existing.review_status = "superseded"
        db.flush()

    review = DomesticManualReview(
        opinion_id=opinion_id,
        ai_result_id=ai_result_id,
        batch_run_id=batch_run_id,
        rule_risk_snapshot=_rule_risk_snapshot(opinion),
        ai_risk_snapshot=_ai_risk_snapshot(ai_result),
        event_preview=_event_preview(opinion, ai_result),
    )
    db.add(review)
    db.flush()
    generate_domestic_ai_alert_candidates(
        db,
        review_id=review.id,
        opinion_id=opinion_id,
        ai_result_id=ai_result_id,
    )
    _refresh_review_alert_preview(db, review)
    db.flush()
    return review, True


def confirm_event_for_review(
    db: Session,
    review: DomesticManualReview,
    *,
    user_id: int | None,
    reason: str,
    request_id: str | None,
    commit: bool = True,
) -> dict[str, Any]:
    existing = db.scalar(select(Event).where(Event.origin_review_id == review.id))
    if existing is not None:
        return {
            "candidate_count": 1,
            "created_count": 0,
            "existing_count": 1,
            "skipped_count": 0,
            "event_ids": [existing.id],
            "reason": None,
        }
    # 防止与事件中心自动聚合链路重复：若该舆情已并入某有效 Event，则认领复用，不再新建。
    opinion_id = review.opinion_id
    claimed = db.scalar(
        select(Event)
        .join(EventOpinion, EventOpinion.event_id == Event.id)
        .where(EventOpinion.opinion_id == opinion_id)
        .where(Event.status.in_(["active", "verifying", "processing"]))
        .order_by(Event.id.asc())
    )
    if claimed is not None:
        claimed.confirmation_source = "manual_review_ai"
        claimed.origin_review_id = review.id
        claimed.confirmation_version = review.confirmation_version
        claimed.confirmed_by = user_id
        claimed.confirmed_at = _utcnow()
        claimed.review_reason = reason or None
        if not db.scalar(
            select(EventOpinion).where(
                EventOpinion.event_id == claimed.id,
                EventOpinion.opinion_id == opinion_id,
            )
        ):
            db.add(EventOpinion(event_id=claimed.id, opinion_id=opinion_id))
        if commit:
            db.commit()
        else:
            db.flush()
        return {
            "candidate_count": 1,
            "created_count": 0,
            "existing_count": 1,
            "skipped_count": 0,
            "event_ids": [claimed.id],
            "reason": None,
        }
    items = list((review.event_preview or {}).get("items") or [])
    if not items:
        return {
            "candidate_count": 0,
            "created_count": 0,
            "existing_count": 0,
            "skipped_count": 0,
            "event_ids": [],
            "reason": "复核已完成，但没有可确认的事件候选。",
        }
    item = items[0]
    opinion = db.get(Opinion, review.opinion_id)
    ai_score = (review.ai_risk_snapshot or {}).get("risk_score")
    risk_score = int(ai_score if ai_score is not None else (opinion.risk_score if opinion else 0))
    event = Event(
        title=item.get("title") or (opinion.title if opinion else "AI 人工确认事件"),
        description=(opinion.content or "")[:200] if opinion else "",
        keyword=",".join((review.ai_risk_snapshot or {}).get("keywords") or []) or (opinion.keywords if opinion else ""),
        risk_level=_map_risk_level(risk_score),
        risk_score=risk_score,
        region_id=opinion.region_id if opinion else None,
        opinion_count=1,
        first_time=opinion.publish_time if opinion else None,
        last_time=opinion.publish_time if opinion else None,
        confirmation_source="manual_review_ai",
        confirmation_version=review.confirmation_version,
        rule_risk_snapshot=review.rule_risk_snapshot,
        ai_risk_snapshot=review.ai_risk_snapshot,
        review_reason=reason or None,
        confirmed_by=user_id,
        confirmed_at=_utcnow(),
        origin_review_id=review.id,
        origin_ai_result_id=review.ai_result_id,
    )
    db.add(event)
    db.flush()
    if opinion is not None:
        exists_link = db.scalar(
            select(EventOpinion).where(
                EventOpinion.event_id == event.id,
                EventOpinion.opinion_id == opinion.id,
            )
        )
        if exists_link is None:
            db.add(EventOpinion(event_id=event.id, opinion_id=opinion.id))
    if commit:
        db.commit()
    else:
        db.flush()
    return {
        "candidate_count": 1,
        "created_count": 1,
        "existing_count": 0,
        "skipped_count": 0,
        "event_ids": [event.id],
        "reason": None,
    }


def confirm_alert_for_review(
    db: Session,
    review: DomesticManualReview,
    *,
    user_id: int | None,
    reason: str,
    request_id: str | None,
    commit: bool = True,
) -> dict[str, Any]:
    candidates = list(
        db.scalars(
            select(DomesticAIAlertCandidate)
            .where(
                DomesticAIAlertCandidate.review_id == review.id,
                DomesticAIAlertCandidate.candidate_status == "pending",
            )
            .order_by(DomesticAIAlertCandidate.id.asc())
        ).all()
    )
    if not candidates:
        return {
            "matched": False,
            "created_count": 0,
            "deduplicated_count": 0,
            "alert_ids": [],
            "source": "manual_review_ai",
            "reason": "AI 风险分未命中阈值，未生成正式预警",
        }
    opinion = db.get(Opinion, review.opinion_id)
    now = _utcnow()
    created_count = 0
    deduplicated_count = 0
    alert_ids: list[int] = []
    for candidate in candidates:
        rule = db.get(AlertRule, candidate.rule_id)
        dedupe = f"manual-review-ai:domestic:rule:{candidate.rule_id}:opinion:{review.opinion_id}:ai:{candidate.ai_result_id}"
        existing = db.scalar(select(AlertRecord).where(AlertRecord.deduplication_key == dedupe))
        if existing is not None:
            candidate.candidate_status = "skipped"
            candidate.confirmed_at = now
            deduplicated_count += 1
            continue
        score = int((candidate.ai_snapshot or {}).get("risk_score") or 0)
        alert = AlertRecord(
            rule_id=candidate.rule_id,
            rule_name=rule.name if rule else "AI 风险规则",
            risk_level=_risk_level(score),
            opinion_id=review.opinion_id,
            opinion_title=opinion.title if opinion else "",
            event_id=None,
            event_title="",
            trigger_reason=f"人工确认 AI 风险预警候选，AI 风险分 {score} 达到阈值 {(candidate.rule_snapshot or {}).get('risk_threshold')}",
            handled=False,
            status="pending",
            evaluation_source="manual_review_ai",
            confirmation_source="manual_review_ai",
            confirmation_version=review.confirmation_version,
            rule_risk_snapshot=review.rule_risk_snapshot,
            ai_risk_snapshot=candidate.ai_snapshot,
            review_reason=reason or None,
            confirmed_by=user_id,
            confirmed_at=now,
            origin_review_id=review.id,
            origin_ai_result_id=candidate.ai_result_id,
            deduplication_key=dedupe,
            created_at=now,
        )
        db.add(alert)
        db.flush()
        alert_ids.append(alert.id)
        candidate.candidate_status = "confirmed"
        candidate.confirmed_at = now
        created_count += 1
    if commit:
        db.commit()
    else:
        db.flush()
    return {
        "matched": (created_count + deduplicated_count) > 0,
        "created_count": created_count,
        "deduplicated_count": deduplicated_count,
        "alert_ids": alert_ids,
        "source": "manual_review_ai",
        "reason": None if (created_count or deduplicated_count) else "AI 风险分未命中阈值，未生成正式预警",
    }
