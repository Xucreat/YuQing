"""Shared manual-review orchestration for foreign AI analysis.

This module is the single integration point that ties together:

* AI analysis (``ForeignAIResult``)
* rule risk (``ForeignRiskResult``)
* human review (``ForeignManualReview``)
* AI alert candidates (``ForeignAIAlertCandidate``)
* formal foreign events / alerts (only after explicit human confirmation)

Single and batch AI analysis BOTH call :func:`ensure_foreign_manual_review`,
so they share one code path. AI never creates a formal event or alert on its
own; it only produces candidates that a human confirms.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.foreign_ai_alert_candidate import ForeignAIAlertCandidate
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_alert import ForeignAlert
from app.models.foreign_alert_rule import ForeignAlertRule
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_manual_review import ForeignManualReview
from app.models.foreign_opinion import ForeignOpinion
from app.services.foreign_content_sanitizer import detect_foreign_language, normalize_foreign_article
from app.services.foreign_effective_risk import resolve_one
from app.services.foreign_event_service import ForeignEventService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_foreign_error(value: object) -> str:
    message = " ".join(str(value or "").split())
    lowered = message.casefold()
    if any(
        marker in lowered
        for marker in ("traceback", "password", "token", "secret", "api key", "proxy", "connection string", "://", "@")
    ):
        return "外网人工复核操作失败，详细错误已隐藏"
    return message[:1000] or "外网人工复核操作失败"


def _ai_risk_level(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "low"
    return "unknown"


def _rule_snapshot(rule: ForeignAlertRule) -> dict[str, Any]:
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "conditions": rule.conditions or {},
        "severity": rule.severity,
        "rule_version": rule.rule_version,
    }


def _ai_risk_matches(rule: ForeignAlertRule, ai_score: int | None) -> bool:
    """Match an ``ai_risk_score`` rule against a completed AI result score."""
    if ai_score is None:
        return False
    conditions = rule.conditions or {}
    threshold = conditions.get("threshold", conditions.get("min_score"))
    if threshold is None:
        raise ValueError("ai_risk_score rule requires conditions.threshold")
    try:
        return float(ai_score) >= float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("ai_risk_score threshold must be numeric") from exc


def _enabled_ai_risk_score_rules(db: Session) -> list[ForeignAlertRule]:
    return list(
        db.scalars(
            select(ForeignAlertRule)
            .where(ForeignAlertRule.is_enabled.is_(True), ForeignAlertRule.rule_type == "ai_risk_score")
            .order_by(ForeignAlertRule.id.asc())
        ).all()
    )


def generate_ai_alert_candidates(
    db: Session, *, review_id: int, opinion_id: int, ai_result_id: int
) -> list[ForeignAIAlertCandidate]:
    """Persist AI alert candidates for one review.

    Candidates come *only* from enabled ``ai_risk_score`` rules that match the
    completed AI result. Re-running clears the previous pending candidates so a
    forced re-analysis always reflects the latest AI result.
    """
    db.execute(
        delete(ForeignAIAlertCandidate).where(
            ForeignAIAlertCandidate.review_id == review_id,
            ForeignAIAlertCandidate.candidate_status == "pending",
        )
    )
    ai_result = db.get(ForeignAIResult, ai_result_id)
    candidates: list[ForeignAIAlertCandidate] = []
    if ai_result is None or ai_result.status != "completed":
        db.flush()
        return candidates
    ai_snapshot = {
        "id": ai_result.id,
        "risk_score": ai_result.risk_score,
        "sentiment": ai_result.sentiment,
        "summary": ai_result.summary,
        "model_name": ai_result.model_name,
        "model_version": ai_result.model_version,
        "analyzed_at": ai_result.analyzed_at.isoformat() if ai_result.analyzed_at else None,
    }
    for rule in _enabled_ai_risk_score_rules(db):
        if not _ai_risk_matches(rule, ai_result.risk_score):
            continue
        conditions = rule.conditions or {}
        threshold = conditions.get("threshold", conditions.get("min_score"))
        candidate = ForeignAIAlertCandidate(
            review_id=review_id,
            opinion_id=opinion_id,
            rule_id=rule.id,
            ai_result_id=ai_result_id,
            rule_snapshot=_rule_snapshot(rule),
            ai_snapshot=ai_snapshot,
            matched_conditions={
                "ai_risk_score": ai_result.risk_score,
                "threshold": threshold,
                "evaluation_source": "ai",
            },
            candidate_status="pending",
            deduplication_key=f"rule:{rule.id}:opinion:{opinion_id}:ai:{ai_result_id}:review:{review_id}",
        )
        db.add(candidate)
        candidates.append(candidate)
    db.flush()
    return candidates


def ensure_foreign_manual_review(
    db: Session,
    opinion_id: int,
    ai_result_id: int,
    batch_run_id: str | None = None,
    force: bool = False,
) -> tuple[ForeignManualReview, bool]:
    """Create or reuse the manual-review record for one foreign opinion.

    Returns ``(review, created)``. This is the single shared entry point used by
    both the single-opinion AI analyze endpoint and the batch worker, so single
    and batch reviews follow exactly the same lifecycle.

    Idempotency:
    * an existing ``pending_review`` is reused (candidates regenerated only when
      missing) unless ``force`` is set;
    * with ``force``, the old ``pending_review`` is marked ``superseded`` and a
      fresh review (with fresh AI candidates) is created.
    """
    existing = db.scalar(
        select(ForeignManualReview)
        .where(
            ForeignManualReview.foreign_opinion_id == opinion_id,
            ForeignManualReview.review_status == "pending_review",
        )
        .order_by(ForeignManualReview.id.desc())
    )
    if existing is not None and not force:
        pending = db.scalar(
            select(func.count())
            .select_from(ForeignAIAlertCandidate)
            .where(
                ForeignAIAlertCandidate.review_id == existing.id,
                ForeignAIAlertCandidate.candidate_status == "pending",
            )
        ) or 0
        if not pending:
            generate_ai_alert_candidates(db, review_id=existing.id, opinion_id=opinion_id, ai_result_id=ai_result_id)
        return existing, False

    resolved = resolve_one(db, opinion_id)
    if existing is not None and force:
        existing.review_status = "superseded"
        existing.review_decision = existing.review_decision or None
        db.flush()
    review = ForeignManualReview(
        foreign_opinion_id=opinion_id,
        source_type="ai",
        rule_risk_snapshot=resolved.get("rule_risk") or {},
        ai_risk_snapshot=resolved.get("latest_ai_risk") or {},
        batch_run_id=batch_run_id,
    )
    db.add(review)
    db.flush()
    try:
        event_run, _, event_items = ForeignEventService().rebuild_candidates(
            db, user_id=None, dry_run=True, opinion_ids=[opinion_id], commit=False
        )
        review.event_preview = {
            "run_id": event_run.id,
            "candidate_count": len(event_items),
            "items": event_items,
            "requires_manual_confirmation": True,
        }
    except Exception:
        db.rollback()
    generate_ai_alert_candidates(db, review_id=review.id, opinion_id=opinion_id, ai_result_id=ai_result_id)
    db.flush()
    return review, True


def confirm_event_for_review(
    db: Session,
    review: ForeignManualReview,
    *,
    user_id: int | None,
    reason: str,
    request_id: str | None,
    commit: bool = True,
) -> dict[str, Any]:
    """Confirm ONLY the event candidate(s) explicitly linked to this review.

    Event candidates are materialized for this review's opinion cluster and then
    tagged with ``review_id`` so confirmation is strictly scoped: a candidate
    belonging to *another* review is never confirmed, and there is no global
    fallback scan over the whole candidate table. Idempotent: an already
    converted candidate returns its existing event instead of creating a second.
    """
    opinion_id = review.foreign_opinion_id
    # Short-circuit fully converted review-scoped candidates before refreshing
    # the clustering engine. Otherwise a repeated confirmation can materialize
    # a fresh candidate after the original one has already become an event.
    existing_candidates = list(
        db.scalars(
            select(ForeignEventCandidate).where(
                ForeignEventCandidate.review_id == review.id,
            )
        ).all()
    )
    existing_candidate_ids = [candidate.id for candidate in existing_candidates if candidate.id is not None]
    if existing_candidate_ids and all(
        candidate.candidate_status == "converted" for candidate in existing_candidates
    ):
        existing_events = list(
            db.scalars(
                select(ForeignEvent).where(
                    ForeignEvent.origin_candidate_id.in_(existing_candidate_ids)
                )
            ).all()
        )
        if len(existing_events) == len(existing_candidates):
            return {
                "candidate_count": 0,
                "created_count": 0,
                "existing_count": len(existing_events),
                "skipped_count": 0,
                "event_ids": [event.id for event in existing_events],
                "reason": "没有可确认的事件候选，复核已完成且正式事件已存在。",
            }

    # Materialize / refresh event candidates for this opinion cluster. Any
    # candidate that references this opinion AND can become a real event
    # (>= 2 member opinions) is tagged with this review's id.
    try:
        _, created, _ = ForeignEventService().rebuild_candidates(
            db, user_id=user_id, dry_run=False, opinion_ids=[opinion_id], commit=False
        )
    except Exception:
        db.rollback()
        created = []
    for candidate in created:
        member_ids = list((candidate.evidence_json or {}).get("opinion_ids", []))
        if candidate.candidate_status == "candidate" and len(member_ids) >= 2:
            candidate.review_id = review.id
    db.flush()
    relevant = list(
        db.scalars(
            select(ForeignEventCandidate).where(
                ForeignEventCandidate.review_id == review.id,
                ForeignEventCandidate.candidate_status == "candidate",
            )
        ).all()
    )
    if not relevant:
        # A single opinion cannot be produced by the clustering engine, but an
        # explicit AI-review confirmation still represents a valid user decision.
        # Materialize it as a review-scoped candidate so the normal confirmation
        # path creates the formal event and keeps the operation idempotent.
        converted_candidate = db.scalar(
            select(ForeignEventCandidate).where(
                ForeignEventCandidate.review_id == review.id,
                ForeignEventCandidate.candidate_status == "converted",
            )
        )
        if converted_candidate is not None:
            existing_event = db.scalar(
                select(ForeignEvent).where(
                    ForeignEvent.origin_candidate_id == converted_candidate.id
                )
            )
            if existing_event is not None:
                return {
                    "candidate_count": 1,
                    "created_count": 0,
                    "existing_count": 1,
                    "skipped_count": 0,
                    "event_ids": [existing_event.id],
                    "reason": None,
                }
        opinion = db.get(ForeignOpinion, opinion_id)
        if opinion is not None:
            ai_score = (review.ai_risk_snapshot or {}).get("risk_score")
            rule_score = (review.rule_risk_snapshot or {}).get("risk_score")
            score = int(ai_score if ai_score is not None else (rule_score or 0))
            risk_level = _ai_risk_level(score)
            candidate = ForeignEventCandidate(
                candidate_key=f"manual-review:{review.id}",
                title=opinion.title or "AI 人工复核确认事件",
                summary=normalize_foreign_article("", opinion.summary, opinion.content)[:1000],
                language=detect_foreign_language(opinion.title or opinion.content or ""),
                candidate_status="candidate",
                review_source="manual",
                confidence=1.0,
                event_type="other",
                risk_level_snapshot=risk_level,
                heat_score_snapshot=score,
                first_seen_at=opinion.published_at or opinion.collected_at,
                last_seen_at=opinion.published_at or opinion.collected_at,
                opinion_count=1,
                source_count=1,
                aggregation_version="foreign-manual-review-v1",
                evidence_json={
                    "opinion_ids": [opinion.id],
                    "candidate_reason": "explicit_ai_manual_review_confirmation",
                    "pair_scores": [],
                },
                review_id=review.id,
                representative_opinion_id=opinion.id,
            )
            db.add(candidate)
            db.flush()
            relevant = [candidate]
    candidate_count = len(relevant)
    event_ids: list[int] = []
    created_count = 0
    existing_count = 0
    skipped_count = 0
    for candidate in relevant:
        if candidate.candidate_status == "converted":
            prior = db.scalar(
                select(ForeignEvent).where(ForeignEvent.origin_candidate_id == candidate.id)
            )
            if prior is not None:
                event_ids.append(prior.id)
                existing_count += 1
            else:
                skipped_count += 1
            continue
        try:
            event = ForeignEventService().confirm_candidate(
                db,
                candidate.id,
                user_id=user_id,
                reason=reason or "AI 人工复核确认事件变化",
                request_id=request_id,
                commit=False,
                rule_risk_snapshot=review.rule_risk_snapshot,
                ai_risk_snapshot=review.ai_risk_snapshot,
                confirmation_source="manual_review_ai",
                confirmation_version=review.confirmation_version,
            )
            event_ids.append(event.id)
            created_count += 1
        except ValueError:
            skipped_count += 1
    if commit:
        db.commit()
    else:
        db.flush()
    if not relevant:
        return {
            "candidate_count": 0,
            "created_count": 0,
            "existing_count": 0,
            "skipped_count": 0,
            "event_ids": [],
            "reason": "复核已完成，但没有可确认的事件候选。",
        }
    return {
        "candidate_count": candidate_count,
        "created_count": created_count,
        "existing_count": existing_count,
        "skipped_count": skipped_count,
        "event_ids": event_ids,
        "reason": None,
    }


def confirm_alert_for_review(
    db: Session,
    review: ForeignManualReview,
    *,
    user_id: int | None,
    reason: str,
    request_id: str | None,
    commit: bool = True,
) -> dict[str, Any]:
    """Confirm AI alert candidates for this review into formal alerts.

    Only the candidates linked to this review are read — the normal rule
    evaluation path is never used to create these alerts. Every confirmed alert
    carries ``evaluation_source='manual_review_ai'`` and the full rule/AI
    snapshots. Dedup is by ``deduplication_key`` so re-confirmation never
    produces a second formal alert.
    """
    opinion_id = review.foreign_opinion_id
    candidates = list(
        db.scalars(
            select(ForeignAIAlertCandidate)
            .where(
                ForeignAIAlertCandidate.review_id == review.id,
                ForeignAIAlertCandidate.candidate_status == "pending",
            )
            .order_by(ForeignAIAlertCandidate.id.asc())
        ).all()
    )
    if not candidates:
        return {
            "matched": False,
            "created_count": 0,
            "deduplicated_count": 0,
            "alert_ids": [],
            "source": "manual_review_ai",
            "reason": "未命中 AI 预警规则候选",
        }
    opinion = db.get(ForeignOpinion, opinion_id)
    opinion_title = opinion.title if opinion else ""
    now = _utcnow()
    created_count = 0
    deduplicated_count = 0
    alert_ids: list[int] = []
    for candidate in candidates:
        rule = db.get(ForeignAlertRule, candidate.rule_id)
        ai_result = db.get(ForeignAIResult, candidate.ai_result_id)
        score = ai_result.risk_score if ai_result else None
        level = _ai_risk_level(score)
        rule_name = rule.name if rule else "AI 风险规则"
        deduplication_key = f"manual-review:rule:{candidate.rule_id}:opinion:{opinion_id}:ai:{candidate.ai_result_id}"
        existing = db.scalar(
            select(ForeignAlert).where(ForeignAlert.deduplication_key == deduplication_key)
        )
        if existing is not None:
            deduplicated_count += 1
            candidate.candidate_status = "skipped"
            candidate.confirmed_at = now
            db.flush()
            continue
        ttl_hours = max(int(settings.foreign_alert_active_ttl_hours or 0), 0)
        expires_at = now + timedelta(hours=ttl_hours) if ttl_hours else None
        alert = ForeignAlert(
            rule_id=candidate.rule_id,
            foreign_opinion_id=opinion_id,
            foreign_risk_result_id=None,
            foreign_event_id=None,
            foreign_ai_result_id=candidate.ai_result_id,
            evaluation_source="manual_review_ai",
            severity=rule.severity if rule else "medium",
            status="triggered",
            title=f"外网 AI 风险告警：{opinion_title or '无标题舆情'}",
            message=f"外网文章满足 AI 风险规则「{rule_name}」，AI 风险分={score if score is not None else '-'}。",
            matched_conditions=candidate.matched_conditions,
            rule_snapshot=candidate.rule_snapshot,
            source_name_snapshot=opinion.source_name_snapshot if opinion else "",
            opinion_title_snapshot=opinion_title,
            event_title_snapshot="",
            risk_score=score,
            risk_level=level,
            deduplication_key=deduplication_key,
            triggered_at=now,
            expires_at=expires_at,
            rule_risk_snapshot=review.rule_risk_snapshot,
            ai_risk_snapshot=candidate.ai_snapshot,
            review_reason=reason or None,
            confirmation_version=review.confirmation_version,
            confirmed_by=user_id,
            confirmed_at=now,
        )
        db.add(alert)
        db.flush()
        alert_ids.append(alert.id)
        created_count += 1
        candidate.candidate_status = "confirmed"
        candidate.confirmed_at = now
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
