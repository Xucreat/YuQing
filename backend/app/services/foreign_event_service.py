"""独立外网事件候选与人工确认服务。

该模块只消费 ``ForeignOpinion``（以及可选的外网风险快照），只写入
``foreign_event_*`` 表。它不导入国内 Event、Opinion、Alert 或 Dashboard 服务。
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_action import ForeignEventAction
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event_opinion import ForeignEventOpinion
from app.models.foreign_event_run import ForeignEventRun
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.foreign_content_sanitizer import (
    detect_foreign_language,
    normalize_foreign_article,
    normalize_foreign_text,
)


AGGREGATION_VERSION = "foreign-event-v1"
CROSS_LANGUAGE_AGGREGATION_VERSION = "foreign-cross-v1"
TIME_WINDOW_HOURS = 72
MAX_INPUTS = 500
HIGH_CONFIDENCE = 0.72
LOW_CONFIDENCE = 0.55
MONITORING_TERMS = {"中国", "china", "chinese"}
STOP_WORDS = {
    "about",
    "after",
    "against",
    "also",
    "been",
    "from",
    "have",
    "into",
    "more",
    "news",
    "over",
    "that",
    "their",
    "this",
    "with",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _article_time(opinion: ForeignOpinion) -> datetime:
    return opinion.published_at or opinion.collected_at or opinion.created_at or _utcnow()


def _article_text(opinion: ForeignOpinion) -> str:
    return normalize_foreign_article(
        opinion.title,
        opinion.summary,
        opinion.content,
    )


def _detect_language(text: str) -> str:
    return detect_foreign_language(text)


def _normalize_token(token: str) -> str:
    value = token.casefold().strip()
    return value


def _tokens(text: str, language: str) -> set[str]:
    text = normalize_foreign_text(text)
    cjk_tokens: set[str] = set()
    if language in {"zh", "mixed"}:
        for chunk in re.findall(r"[\u4e00-\u9fff]+", text):
            cjk_tokens.update(
                chunk[index : index + 2]
                for index in range(max(0, len(chunk) - 1))
                if chunk[index : index + 2] not in MONITORING_TERMS
            )
    words = re.findall(r"[a-z0-9][a-z0-9'-]{1,}", text.casefold())
    latin_tokens = {
        _normalize_token(word)
        for word in words
        if word not in STOP_WORDS and word not in MONITORING_TERMS
    }
    return cjk_tokens | latin_tokens if language == "mixed" else cjk_tokens if language == "zh" else latin_tokens


def _cross_language_tokens(text: str) -> set[str]:
    """Extract only script-neutral entity-like tokens for en/zh comparison."""
    normalized = normalize_foreign_text(text).casefold()
    words = re.findall(r"[a-z0-9][a-z0-9'-]{1,}", normalized)
    return {
        _normalize_token(word)
        for word in words
        if word not in STOP_WORDS and word not in MONITORING_TERMS
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _time_proximity(
    left: datetime,
    right: datetime,
    time_window_hours: int = TIME_WINDOW_HOURS,
) -> float:
    delta_hours = abs((left - right).total_seconds()) / 3600
    window = max(int(time_window_hours), 1)
    return max(0.0, 1.0 - (delta_hours / window))


def _risk_snapshot(db: Session, opinion_id: int) -> tuple[str, int]:
    result = db.scalar(
        select(ForeignRiskResult)
        .where(
            ForeignRiskResult.foreign_opinion_id == opinion_id,
            ForeignRiskResult.is_current.is_(True),
        )
        .order_by(ForeignRiskResult.id.desc())
    )
    if result is None:
        return "unknown", 0
    return result.risk_level or "unknown", int(result.risk_score or 0)


def _source_identity(opinion: ForeignOpinion) -> str:
    """Use the persisted source snapshot, with source_key as a stable fallback."""
    return (opinion.source_name_snapshot or opinion.source_key or "unknown").strip()


def _safe_error_summary(value: str | None) -> str | None:
    """Keep event-run errors useful without exposing driver or secret details."""
    if not value:
        return None
    message = " ".join(str(value).split())
    lowered = message.casefold()
    sensitive_markers = (
        "traceback",
        "sqlalchemy",
        "psycopg",
        "password",
        "token",
        "secret",
        "api key",
        "proxy",
        "connection string",
        "://",
        "@",
    )
    if any(marker in lowered for marker in sensitive_markers):
        return "外网事件运行失败，详细错误已隐藏"
    return message[:240]


def _normalized_request_id(value: str | None) -> str | None:
    value = (value or "").strip()
    return value[:128] or None


def recompute_foreign_event_metrics(db: Session, event_id: int) -> ForeignEvent:
    """Rebuild denormalized event metrics from its actual foreign article links.

    This function intentionally does not commit. Callers can update relationships
    and metrics in one transaction, then commit or roll back as a unit.
    """
    event = db.get(ForeignEvent, event_id)
    if event is None:
        raise LookupError("Foreign event not found")

    # Flush relationship moves/deletes before deriving counts and timestamps.
    db.flush()
    rows = db.execute(
        select(ForeignEventOpinion, ForeignOpinion)
        .join(ForeignOpinion, ForeignOpinion.id == ForeignEventOpinion.foreign_opinion_id)
        .where(ForeignEventOpinion.foreign_event_id == event_id)
    ).all()
    opinions_by_id = {opinion.id: opinion for _, opinion in rows}
    opinions = list(opinions_by_id.values())

    event.opinion_count = len(opinions_by_id)
    event.source_count = len({_source_identity(opinion) for opinion in opinions})
    if opinions:
        article_times = [_article_time(opinion) for opinion in opinions]
        event.first_seen_at = min(article_times)
        event.last_seen_at = max(article_times)
    else:
        event.first_seen_at = None
        event.last_seen_at = None

    risk_results = list(
        db.scalars(
            select(ForeignRiskResult).where(
                ForeignRiskResult.foreign_opinion_id.in_(list(opinions_by_id)),
                ForeignRiskResult.is_current.is_(True),
                ForeignRiskResult.analysis_status == "completed",
            )
        ).all()
    ) if opinions_by_id else []
    scores = [int(result.risk_score) for result in risk_results if result.risk_score is not None]
    event.heat_score = max(scores or [0])
    levels = {result.risk_level for result in risk_results if result.risk_level}
    if "high" in levels:
        event.risk_level = "high"
    elif "medium" in levels:
        event.risk_level = "medium"
    elif "low" in levels:
        event.risk_level = "low"
    else:
        event.risk_level = "unknown"
    return event


@dataclass(frozen=True)
class PairEvidence:
    score: float
    title_similarity: float
    content_similarity: float
    anchor_overlap: float
    time_proximity: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class CandidateGroup:
    opinions: tuple[ForeignOpinion, ...]
    language: str
    confidence: float
    pair_evidence: tuple[dict, ...]
    time_window_hours: int
    cross_language: bool = False
    language_pair: tuple[str, ...] = ()


def score_pair(
    left: ForeignOpinion,
    right: ForeignOpinion,
    *,
    time_window_hours: int = TIME_WINDOW_HOURS,
) -> PairEvidence:
    """Score two same-language articles using explainable lexical features."""
    text_left = _article_text(left)
    text_right = _article_text(right)
    language = _detect_language(text_left)
    title_similarity = _jaccard(
        _tokens(left.title or "", language),
        _tokens(right.title or "", language),
    )
    content_similarity = _jaccard(
        _tokens(normalize_foreign_article("", left.summary, left.content), language),
        _tokens(normalize_foreign_article("", right.summary, right.content), language),
    )
    anchor_left = _tokens(left.title or "", language)
    anchor_right = _tokens(right.title or "", language)
    anchor_overlap = _jaccard(anchor_left, anchor_right)
    matched_terms = tuple(sorted(anchor_left & anchor_right))
    time_proximity = _time_proximity(
        _article_time(left), _article_time(right), time_window_hours
    )
    # Anchor overlap is retained as evidence, but is not weighted separately:
    # it is derived from the title and would otherwise count the same signal twice.
    score = 0.40 * title_similarity + 0.45 * content_similarity + 0.15 * time_proximity
    return PairEvidence(
        score=round(score, 6),
        title_similarity=round(title_similarity, 6),
        content_similarity=round(content_similarity, 6),
        anchor_overlap=round(anchor_overlap, 6),
        time_proximity=round(time_proximity, 6),
        matched_terms=matched_terms,
    )


def score_cross_language_pair(
    left: ForeignOpinion,
    right: ForeignOpinion,
    *,
    time_window_hours: int = TIME_WINDOW_HOURS,
) -> PairEvidence:
    """Score conservative shared Latin/entity evidence across en and zh rows.

    This deliberately reuses the existing lexical formula and threshold. It
    does not translate text, call a model, or infer semantic equivalence.
    """
    left_text = _article_text(left)
    right_text = _article_text(right)
    left_language = _detect_language(left_text)
    right_language = _detect_language(right_text)
    title_similarity = _jaccard(
        _cross_language_tokens(left.title or ""),
        _cross_language_tokens(right.title or ""),
    )
    content_similarity = _jaccard(
        _cross_language_tokens(normalize_foreign_article("", left.summary, left.content)),
        _cross_language_tokens(normalize_foreign_article("", right.summary, right.content)),
    )
    anchor_left = _cross_language_tokens(left.title or "")
    anchor_right = _cross_language_tokens(right.title or "")
    anchor_overlap = _jaccard(anchor_left, anchor_right)
    matched_terms = tuple(sorted(anchor_left & anchor_right))
    time_proximity = _time_proximity(
        _article_time(left), _article_time(right), time_window_hours
    )
    score = 0.40 * title_similarity + 0.45 * content_similarity + 0.15 * time_proximity
    return PairEvidence(
        score=round(score, 6),
        title_similarity=round(title_similarity, 6),
        content_similarity=round(content_similarity, 6),
        anchor_overlap=round(anchor_overlap, 6),
        time_proximity=round(time_proximity, 6),
        matched_terms=matched_terms,
    )


def _canonical_articles(opinions: Iterable[ForeignOpinion]) -> list[ForeignOpinion]:
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    result: list[ForeignOpinion] = []
    for opinion in sorted(opinions, key=lambda row: row.id):
        if opinion.duplicate_of_id:
            continue
        url = (opinion.url or "").strip()
        digest = (opinion.content_hash or "").strip()
        if url and url in seen_urls:
            continue
        if digest and digest in seen_hashes:
            continue
        if url:
            seen_urls.add(url)
        if digest:
            seen_hashes.add(digest)
        result.append(opinion)
    return result


def _candidate_key(opinion_ids: list[int], aggregation_version: str = AGGREGATION_VERSION) -> str:
    raw = f"{aggregation_version}:{','.join(str(value) for value in sorted(opinion_ids))}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_groups(
    opinions: list[ForeignOpinion],
    *,
    time_window_hours: int = TIME_WINDOW_HOURS,
    include_cross_language: bool = False,
) -> list[CandidateGroup]:
    time_window_hours = max(int(time_window_hours), 1)
    groups: list[CandidateGroup] = []
    used: set[int] = set()
    by_language: dict[str, list[ForeignOpinion]] = {}
    for opinion in opinions:
        language = _detect_language(_article_text(opinion))
        if language not in {"zh", "en", "mixed", "unknown"}:
            language = "unknown"
        by_language.setdefault(language, []).append(opinion)

    for language, rows in by_language.items():
        for representative in sorted(rows, key=lambda row: row.id):
            if representative.id in used:
                continue
            members = [representative]
            evidence: list[dict] = []
            for other in rows:
                if other.id == representative.id or other.id in used:
                    continue
                if abs(
                    (_article_time(other) - _article_time(representative)).total_seconds()
                ) > time_window_hours * 3600:
                    continue
                pair = score_pair(
                    representative,
                    other,
                    time_window_hours=time_window_hours,
                )
                if pair.score < LOW_CONFIDENCE:
                    continue
                # Mixed/unknown articles can only form a deliberately low-confidence
                # candidate. They never join zh/en groups.
                accepted_score = min(pair.score, 0.49) if language in {"mixed", "unknown"} else pair.score
                members.append(other)
                evidence.append(
                    {
                        "opinion_id": other.id,
                        "representative_opinion_id": representative.id,
                        "score": accepted_score,
                        "title_similarity": pair.title_similarity,
                        "content_similarity": pair.content_similarity,
                        "anchor_overlap": pair.anchor_overlap,
                        "time_proximity": pair.time_proximity,
                        "matched_terms": list(pair.matched_terms),
                        "similarity_method": "lexical_jaccard",
                        "similarity_threshold": LOW_CONFIDENCE,
                        "candidate_reason": "same-language articles within the time window with lexical similarity above threshold",
                    }
                )
            if len({(row.url or "").strip() for row in members}) < 2:
                continue
            if len(members) < 2:
                continue
            used.update(row.id for row in members)
            pair_scores = [item["score"] for item in evidence] or [0.0]
            source_names = {row.source_name_snapshot for row in members}
            confidence = min(pair_scores)
            confidence = min(1.0, confidence + min(0.05, max(0, len(source_names) - 1) * 0.025))
            groups.append(
                CandidateGroup(
                    opinions=tuple(members),
                    language=language,
                    confidence=round(confidence, 6),
                    pair_evidence=tuple(evidence),
                    time_window_hours=time_window_hours,
                )
            )
    if include_cross_language:
        cross_rows = [
            row for row in opinions
            if _detect_language(_article_text(row)) in {"en", "zh"}
            and row.id not in used
        ]
        cross_pairs: list[tuple[float, ForeignOpinion, ForeignOpinion, PairEvidence]] = []
        for index, left in enumerate(cross_rows):
            left_language = _detect_language(_article_text(left))
            for right in cross_rows[index + 1 :]:
                right_language = _detect_language(_article_text(right))
                if left_language == right_language:
                    continue
                if abs((_article_time(right) - _article_time(left)).total_seconds()) > time_window_hours * 3600:
                    continue
                pair = score_cross_language_pair(
                    left, right, time_window_hours=time_window_hours
                )
                # Shared title/entity evidence is required; time alone is not a candidate.
                if pair.score < LOW_CONFIDENCE or not pair.matched_terms:
                    continue
                cross_pairs.append((pair.score, left, right, pair))
        for _, left, right, pair in sorted(cross_pairs, key=lambda item: item[0], reverse=True):
            if left.id in used or right.id in used:
                continue
            left_language = _detect_language(_article_text(left))
            right_language = _detect_language(_article_text(right))
            language_pair = tuple(sorted((left_language, right_language)))
            evidence = {
                "opinion_id": right.id,
                "representative_opinion_id": left.id,
                "score": pair.score,
                "title_similarity": pair.title_similarity,
                "content_similarity": pair.content_similarity,
                "anchor_overlap": pair.anchor_overlap,
                "time_proximity": pair.time_proximity,
                "time_delta_hours": round(abs((_article_time(right) - _article_time(left)).total_seconds()) / 3600, 6),
                "matched_terms": list(pair.matched_terms),
                "similarity_method": "cross_language_lexical_entity",
                "similarity_threshold": LOW_CONFIDENCE,
                "language_pair": list(language_pair),
                "candidate_reason": "cross-language shared entity evidence within the time window; manual review required",
                "pending_reason": "cross_language_requires_manual_review",
            }
            used.update((left.id, right.id))
            groups.append(
                CandidateGroup(
                    opinions=(left, right),
                    language="mixed",
                    confidence=round(pair.score, 6),
                    pair_evidence=(evidence,),
                    time_window_hours=time_window_hours,
                    cross_language=True,
                    language_pair=language_pair,
                )
            )
    return groups


def _candidate_payload(group: CandidateGroup, db: Session) -> dict:
    members = list(group.opinions)
    representative = members[0]
    risk_levels: list[str] = []
    heat_scores: list[int] = []
    for opinion in members:
        risk_level, risk_score = _risk_snapshot(db, opinion.id)
        risk_levels.append(risk_level)
        heat_scores.append(risk_score)
    risk_level = "high" if "high" in risk_levels else "medium" if "medium" in risk_levels else "low" if risk_levels and all(level == "low" for level in risk_levels) else "unknown"
    aggregation_version = CROSS_LANGUAGE_AGGREGATION_VERSION if group.cross_language else AGGREGATION_VERSION
    source_list = sorted({_source_identity(opinion) for opinion in members})
    time_delta_hours = round(
        (max(_article_time(opinion) for opinion in members) - min(_article_time(opinion) for opinion in members)).total_seconds() / 3600,
        6,
    )
    return {
        "candidate_key": _candidate_key([opinion.id for opinion in members], aggregation_version),
        "title": normalize_foreign_text(representative.title),
        "summary": normalize_foreign_article("", representative.summary, representative.content)[:1000],
        "language": group.language,
        "confidence": group.confidence,
        "risk_level_snapshot": risk_level,
        "heat_score_snapshot": max(heat_scores or [0]),
        "first_seen_at": min(_article_time(opinion) for opinion in members),
        "last_seen_at": max(_article_time(opinion) for opinion in members),
        "opinion_count": len(members),
        "source_count": len({_source_identity(opinion) for opinion in members}),
        "review_source": "manual",
        "aggregation_version": aggregation_version,
        "representative_opinion_id": representative.id,
        "evidence_json": {
            "formula": "0.40*title + 0.45*content + 0.15*time (anchor is evidence only)",
            "similarity_method": "cross_language_lexical_entity" if group.cross_language else "lexical_jaccard",
            "similarity_threshold": LOW_CONFIDENCE,
            "candidate_reason": (
                "cross-language shared entity evidence within the time window; manual review required"
                if group.cross_language
                else "same-language articles within the time window with lexical similarity above threshold"
            ),
            "cross_language": group.cross_language,
            "language_pair": list(group.language_pair),
            "source_list": source_list,
            "time_delta_hours": time_delta_hours,
            "common_entities": sorted({term for item in group.pair_evidence for term in item.get("matched_terms", [])}),
            "pending_reason": "cross_language_requires_manual_review" if group.cross_language else None,
            "time_window_hours": group.time_window_hours,
            "thresholds": {
                "high_confidence": HIGH_CONFIDENCE,
                "low_confidence": LOW_CONFIDENCE,
            },
            "monitoring_terms_ignored": sorted(MONITORING_TERMS),
            "opinion_ids": [opinion.id for opinion in members],
            "pair_scores": list(group.pair_evidence),
        },
    }


class ForeignEventService:
    """外网事件候选生成、人工确认和人工维护的唯一业务入口。"""

    @staticmethod
    def _existing_action(db: Session, request_id: str | None) -> ForeignEventAction | None:
        if not request_id:
            return None
        return db.scalar(
            select(ForeignEventAction).where(
                ForeignEventAction.request_id == request_id
            )
        )

    def _new_run(
        self,
        db: Session,
        *,
        user_id: int | None,
        dry_run: bool,
        trigger_type: str,
        aggregation_version: str = AGGREGATION_VERSION,
    ) -> ForeignEventRun:
        run = ForeignEventRun(
            scope="foreign",
            trigger_type="dry_run" if dry_run else trigger_type,
            aggregation_version=aggregation_version,
            dry_run=dry_run,
            created_by=user_id,
            started_at=_utcnow(),
        )
        db.add(run)
        db.flush()
        return run

    @staticmethod
    def _finish_run(
        run: ForeignEventRun,
        *,
        status: str,
        error_message: str | None = None,
    ) -> None:
        run.status = status
        run.finished_at = _utcnow()
        run.error_message = _safe_error_summary(error_message)

    def rebuild_candidates(
        self,
        db: Session,
        *,
        user_id: int | None = None,
        dry_run: bool = True,
        opinion_ids: list[int] | None = None,
        trigger_type: str = "manual",
        time_window_hours: int = TIME_WINDOW_HOURS,
        cross_language: bool = False,
        commit: bool = True,
    ) -> tuple[ForeignEventRun, list[ForeignEventCandidate], list[dict]]:
        if opinion_ids and len(opinion_ids) > MAX_INPUTS:
            raise ValueError(f"input size must be <= {MAX_INPUTS}")
        if int(time_window_hours) < 1:
            raise ValueError("time_window_hours must be at least 1")
        if cross_language and not settings.foreign_event_cross_language_enabled:
            raise ValueError("Cross-language candidate generation is disabled")
        run = self._new_run(
            db,
            user_id=user_id,
            dry_run=dry_run,
            trigger_type=trigger_type,
            aggregation_version=CROSS_LANGUAGE_AGGREGATION_VERSION if cross_language else AGGREGATION_VERSION,
        )
        try:
            stmt = select(ForeignOpinion).order_by(ForeignOpinion.id.asc())
            if opinion_ids:
                stmt = stmt.where(ForeignOpinion.id.in_(opinion_ids))
            opinions = list(db.scalars(stmt).all())
            canonical = _canonical_articles(opinions)
            groups = _build_groups(
                canonical,
                time_window_hours=int(time_window_hours),
                include_cross_language=cross_language,
            )
            previews = [_candidate_payload(group, db) for group in groups]
            run.input_count = len(opinions)
            run.deduplicated_count = len(canonical)
            run.candidate_count = len(previews)
            run.linked_count = sum(item["opinion_count"] for item in previews)
            created: list[ForeignEventCandidate] = []
            if not dry_run:
                for payload in previews:
                    existing = db.scalar(
                        select(ForeignEventCandidate).where(
                            ForeignEventCandidate.candidate_key == payload["candidate_key"]
                        )
                    )
                    if existing is None:
                        existing = ForeignEventCandidate(
                            aggregation_version=payload.get("aggregation_version", AGGREGATION_VERSION),
                            candidate_status="candidate",
                        )
                        db.add(existing)
                    if existing.candidate_status in {"candidate", "superseded"}:
                        for key, value in payload.items():
                            setattr(existing, key, value)
                        existing.updated_at = _utcnow()
                    created.append(existing)
                run.status = "success"
            else:
                run.status = "dry_run"
            self._finish_run(run, status=run.status)
            if commit:
                db.commit()
                for row in created:
                    db.refresh(row)
            else:
                db.flush()
            return run, created, previews
        except Exception as exc:
            self._finish_run(run, status="failed", error_message=_safe_error_summary(str(exc)))
            run.failed_count = 1
            if commit:
                db.commit()
            else:
                db.rollback()
            raise

    def confirm_candidate(
        self,
        db: Session,
        candidate_id: int,
        *,
        user_id: int | None,
        reason: str = "",
        request_id: str | None = None,
        confirmation_source: str = "manual",
        commit: bool = True,
        rule_risk_snapshot: dict | None = None,
        ai_risk_snapshot: dict | None = None,
        confirmation_version: str | None = None,
    ) -> ForeignEvent:
        request_id = _normalized_request_id(request_id)
        previous_action = self._existing_action(db, request_id)
        if previous_action and previous_action.foreign_event_id:
            existing_event = db.get(ForeignEvent, previous_action.foreign_event_id)
            if existing_event is not None:
                return existing_event
        candidate = db.get(ForeignEventCandidate, candidate_id)
        if candidate is None:
            raise LookupError("Foreign event candidate not found")
        if candidate.candidate_status == "converted":
            existing = db.scalar(
                select(ForeignEvent).where(
                    ForeignEvent.origin_candidate_id == candidate.id
                )
            )
            if existing is not None:
                return existing
        if candidate.candidate_status != "candidate":
            raise ValueError("Only a pending candidate can be confirmed")
        if confirmation_source not in {"manual", "auto", "manual_review_ai"}:
            raise ValueError("Invalid foreign event confirmation source")
        if candidate.language == "mixed" and confirmation_source == "auto":
            raise ValueError("Cross-language candidates require manual confirmation")
        member_ids = list((candidate.evidence_json or {}).get("opinion_ids", []))
        opinions = list(
            db.scalars(
                select(ForeignOpinion).where(ForeignOpinion.id.in_(member_ids))
            ).all()
        )
        if len(opinions) < 2 and confirmation_source != "manual_review_ai":
            raise ValueError("A confirmed foreign event requires at least two articles")
        now = _utcnow()
        event = ForeignEvent(
            title=candidate.title,
            summary=candidate.summary,
            language=candidate.language,
            event_status="active",
            confirmation_source=confirmation_source,
            event_type=candidate.event_type,
            risk_level=candidate.risk_level_snapshot,
            heat_score=candidate.heat_score_snapshot,
            first_seen_at=candidate.first_seen_at,
            last_seen_at=candidate.last_seen_at,
            opinion_count=candidate.opinion_count,
            source_count=candidate.source_count,
            confidence=candidate.confidence,
            aggregation_version=candidate.aggregation_version,
            origin_candidate_id=candidate.id,
            confirmed_by=user_id,
            confirmed_at=now,
            rule_risk_snapshot=rule_risk_snapshot or {},
            ai_risk_snapshot=ai_risk_snapshot or {},
            review_reason=reason or None,
            confirmation_version=confirmation_version,
        )
        db.add(event)
        db.flush()
        pair_by_id = {
            int(item["opinion_id"]): item
            for item in (candidate.evidence_json or {}).get("pair_scores", [])
        }
        representative_id = int(
            (candidate.evidence_json or {}).get(
                "representative_opinion_id", candidate.representative_opinion_id or opinions[0].id
            )
        )
        for opinion in opinions:
            evidence = pair_by_id.get(opinion.id, {})
            db.add(
                ForeignEventOpinion(
                    foreign_event_id=event.id,
                    foreign_opinion_id=opinion.id,
                    relation_type="primary" if opinion.id == representative_id else "secondary",
                    similarity_score=evidence.get("score"),
                    matched_terms=evidence.get("matched_terms", []),
                    evidence_json=evidence,
                    created_by=user_id,
                )
            )
        db.flush()
        recompute_foreign_event_metrics(db, event.id)
        candidate.candidate_status = "converted"
        candidate.reviewed_by = user_id
        candidate.reviewed_at = now
        db.add(
            ForeignEventAction(
                action_type="candidate_confirm",
                candidate_id=candidate.id,
                foreign_event_id=event.id,
                actor_user_id=user_id,
                new_status="active",
                reason=reason,
                request_id=request_id,
                payload_json={"opinion_ids": member_ids},
            )
        )
        if commit:
            db.commit()
            db.refresh(event)
        else:
            db.flush()
        return event

    def reject_candidate(
        self,
        db: Session,
        candidate_id: int,
        *,
        user_id: int | None,
        reason: str,
        request_id: str | None = None,
    ) -> ForeignEventCandidate:
        request_id = _normalized_request_id(request_id)
        previous_action = self._existing_action(db, request_id)
        if previous_action and previous_action.candidate_id:
            existing_candidate = db.get(
                ForeignEventCandidate, previous_action.candidate_id
            )
            if existing_candidate is not None:
                return existing_candidate
        candidate = db.get(ForeignEventCandidate, candidate_id)
        if candidate is None:
            raise LookupError("Foreign event candidate not found")
        if candidate.candidate_status == "rejected":
            return candidate
        if candidate.candidate_status != "candidate":
            raise ValueError("Only a pending candidate can be rejected")
        candidate.candidate_status = "rejected"
        candidate.rejection_reason = reason
        candidate.reviewed_by = user_id
        candidate.reviewed_at = _utcnow()
        db.add(
            ForeignEventAction(
                action_type="candidate_reject",
                candidate_id=candidate.id,
                actor_user_id=user_id,
                old_status="candidate",
                new_status="rejected",
                reason=reason,
                request_id=request_id,
            )
        )
        db.commit()
        db.refresh(candidate)
        return candidate

    def update_status(
        self,
        db: Session,
        event_id: int,
        *,
        status: str,
        user_id: int | None,
        reason: str = "",
        request_id: str | None = None,
    ) -> ForeignEvent:
        request_id = _normalized_request_id(request_id)
        previous_action = self._existing_action(db, request_id)
        if previous_action and previous_action.foreign_event_id:
            existing_event = db.get(ForeignEvent, previous_action.foreign_event_id)
            if existing_event is not None:
                return existing_event
        event = db.get(ForeignEvent, event_id)
        if event is None:
            raise LookupError("Foreign event not found")
        # 与外网「事件处置」弹窗（和国内事件中心一致）采用同一套线性流转规则：
        # active -> verifying -> processing -> resolved -> closed；
        # 任意态可直接回 active（重新关注）；active/verifying/processing 可置 deprecated（已忽略）；
        # 非 archived 态均可归档（archived 由「归档事件」按钮触发）。
        _next = {"active": "verifying", "verifying": "processing", "processing": "resolved", "resolved": "closed"}
        if status != event.event_status:
            if status == "archived":
                pass
            elif status == "active":
                pass
            elif status == "deprecated":
                if event.event_status not in ("active", "verifying", "processing"):
                    raise ValueError(f"Invalid foreign event status transition: {event.event_status} -> {status}")
            elif _next.get(event.event_status) != status:
                raise ValueError(f"Invalid foreign event status transition: {event.event_status} -> {status}")
        old = event.event_status
        event.event_status = status
        if status == "resolved":
            event.resolved_at = _utcnow()
        if status == "archived":
            event.archived_at = _utcnow()
        db.add(
            ForeignEventAction(
                action_type="status_change",
                foreign_event_id=event.id,
                actor_user_id=user_id,
                old_status=old,
                new_status=status,
                reason=reason,
                request_id=request_id,
            )
        )
        db.commit()
        db.refresh(event)
        return event

    def merge_events(
        self,
        db: Session,
        source_event_id: int,
        target_event_id: int,
        *,
        user_id: int | None,
        reason: str,
        request_id: str | None = None,
    ) -> ForeignEvent:
        request_id = _normalized_request_id(request_id)
        previous_action = self._existing_action(db, request_id)
        if previous_action and previous_action.target_event_id:
            existing_event = db.get(ForeignEvent, previous_action.target_event_id)
            if existing_event is not None:
                return existing_event
        if source_event_id == target_event_id:
            raise ValueError("source and target event must differ")
        source = db.get(ForeignEvent, source_event_id)
        target = db.get(ForeignEvent, target_event_id)
        if source is None or target is None:
            raise LookupError("Foreign event not found")
        if source.language != target.language:
            raise ValueError("Cross-language foreign event merge is not allowed")
        links = list(
            db.scalars(
                select(ForeignEventOpinion).where(
                    ForeignEventOpinion.foreign_event_id == source.id
                )
            ).all()
        )
        existing_ids = set(
            db.scalars(
                select(ForeignEventOpinion.foreign_opinion_id).where(
                    ForeignEventOpinion.foreign_event_id == target.id
                )
            ).all()
        )
        for link in links:
            if link.foreign_opinion_id in existing_ids:
                db.delete(link)
                continue
            link.foreign_event_id = target.id
        source.canonical_event_id = target.id
        source.event_status = "archived"
        recompute_foreign_event_metrics(db, target.id)
        recompute_foreign_event_metrics(db, source.id)
        db.add(
            ForeignEventAction(
                action_type="merge",
                foreign_event_id=source.id,
                target_event_id=target.id,
                actor_user_id=user_id,
                old_status="active",
                new_status="archived",
                reason=reason,
                request_id=request_id,
                payload_json={"source_event_id": source.id, "target_event_id": target.id},
            )
        )
        db.commit()
        db.refresh(target)
        return target

    def split_event(
        self,
        db: Session,
        event_id: int,
        opinion_ids: list[int],
        *,
        user_id: int | None,
        reason: str,
        request_id: str | None = None,
    ) -> ForeignEvent:
        request_id = _normalized_request_id(request_id)
        previous_action = self._existing_action(db, request_id)
        if previous_action and previous_action.target_event_id:
            existing_event = db.get(ForeignEvent, previous_action.target_event_id)
            if existing_event is not None:
                return existing_event
        event = db.get(ForeignEvent, event_id)
        if event is None:
            raise LookupError("Foreign event not found")
        if not opinion_ids:
            raise ValueError("opinion_ids must not be empty")
        links = list(
            db.scalars(
                select(ForeignEventOpinion).where(
                    ForeignEventOpinion.foreign_event_id == event.id,
                    ForeignEventOpinion.foreign_opinion_id.in_(opinion_ids),
                )
            ).all()
        )
        if not links:
            raise ValueError("No selected articles belong to the foreign event")
        current_count = db.scalar(
            select(func.count(ForeignEventOpinion.id)).where(
                ForeignEventOpinion.foreign_event_id == event.id
            )
        ) or 0
        if len(links) >= int(current_count):
            raise ValueError("A split must leave at least one article in the original foreign event")
        opinions = list(
            db.scalars(
                select(ForeignOpinion).where(
                    ForeignOpinion.id.in_([link.foreign_opinion_id for link in links])
                )
            ).all()
        )
        new_event = ForeignEvent(
            title=opinions[0].title if opinions else event.title,
            summary=opinions[0].summary if opinions else event.summary,
            language=event.language,
            event_status="active",
            event_type=event.event_type,
            risk_level=event.risk_level,
            heat_score=event.heat_score,
            first_seen_at=min(_article_time(opinion) for opinion in opinions),
            last_seen_at=max(_article_time(opinion) for opinion in opinions),
            opinion_count=len(opinions),
            source_count=len({opinion.source_name_snapshot for opinion in opinions}),
            confidence=event.confidence,
            aggregation_version=event.aggregation_version,
            confirmed_by=user_id,
            confirmed_at=_utcnow(),
        )
        db.add(new_event)
        db.flush()
        for link in links:
            link.foreign_event_id = new_event.id
        recompute_foreign_event_metrics(db, event.id)
        recompute_foreign_event_metrics(db, new_event.id)
        db.add(
            ForeignEventAction(
                action_type="split",
                foreign_event_id=event.id,
                target_event_id=new_event.id,
                actor_user_id=user_id,
                reason=reason,
                request_id=request_id,
                payload_json={"opinion_ids": opinion_ids},
            )
        )
        db.commit()
        db.refresh(new_event)
        return new_event


def serialize_candidate(candidate: ForeignEventCandidate) -> dict:
    return {
        "id": candidate.id,
        "candidate_key": candidate.candidate_key,
        "title": candidate.title,
        "summary": candidate.summary,
        "language": candidate.language,
        "candidate_status": candidate.candidate_status,
        "review_status": {
            "candidate": "pending",
            "converted": "confirmed",
            "rejected": "rejected",
            "superseded": "pending",
        }.get(candidate.candidate_status, candidate.candidate_status),
        "review_source": candidate.review_source,
        "confidence": candidate.confidence,
        "event_type": candidate.event_type,
        "risk_level_snapshot": candidate.risk_level_snapshot,
        "heat_score_snapshot": candidate.heat_score_snapshot,
        "first_seen_at": candidate.first_seen_at.isoformat() if candidate.first_seen_at else None,
        "last_seen_at": candidate.last_seen_at.isoformat() if candidate.last_seen_at else None,
        "opinion_count": candidate.opinion_count,
        "source_count": candidate.source_count,
        "aggregation_version": candidate.aggregation_version,
        "evidence_json": candidate.evidence_json or {},
        "representative_opinion_id": candidate.representative_opinion_id,
        "reviewed_by": candidate.reviewed_by,
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
        "rejection_reason": candidate.rejection_reason,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
    }


def serialize_event(event: ForeignEvent) -> dict:
    return {
        "id": event.id,
        "title": event.title,
        "summary": event.summary,
        "language": event.language,
        "event_status": event.event_status,
        # 兼容字段：统一事件处置弹窗（EventDispositionDialog）读取 data.status；
        # status 与 event_status 始终来自同一值，不引入第二状态来源。
        "status": event.event_status,
        "confirmation_source": event.confirmation_source,
        "event_type": event.event_type,
        "risk_level": event.risk_level,
        "heat_score": event.heat_score,
        "formal_risk_score": event.heat_score,
        "formal_risk_level": event.risk_level,
        "linked_opinion_current_risk": None,
        "first_seen_at": event.first_seen_at.isoformat() if event.first_seen_at else None,
        "last_seen_at": event.last_seen_at.isoformat() if event.last_seen_at else None,
        "opinion_count": event.opinion_count,
        "source_count": event.source_count,
        "confidence": event.confidence,
        "aggregation_version": event.aggregation_version,
        "origin_candidate_id": event.origin_candidate_id,
        "canonical_event_id": event.canonical_event_id,
        "confirmed_by": event.confirmed_by,
        "confirmed_at": event.confirmed_at.isoformat() if event.confirmed_at else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        "archived_at": event.archived_at.isoformat() if event.archived_at else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }


def serialize_run(run: ForeignEventRun) -> dict:
    return {
        "id": run.id,
        "scope": run.scope,
        "trigger_type": run.trigger_type,
        "aggregation_version": run.aggregation_version,
        "input_count": run.input_count,
        "deduplicated_count": run.deduplicated_count,
        "candidate_count": run.candidate_count,
        "linked_count": run.linked_count,
        "created_event_count": run.created_event_count,
        "updated_event_count": run.updated_event_count,
        "rejected_count": run.rejected_count,
        "failed_count": run.failed_count,
        "status": run.status,
        "dry_run": run.dry_run,
        "error_message": _safe_error_summary(run.error_message),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def serialize_action(action: ForeignEventAction) -> dict:
    return {
        "id": action.id,
        "action_type": action.action_type,
        "candidate_id": action.candidate_id,
        "foreign_event_id": action.foreign_event_id,
        "target_event_id": action.target_event_id,
        "actor_user_id": action.actor_user_id,
        "old_status": action.old_status,
        "new_status": action.new_status,
        "reason": action.reason,
        "request_id": action.request_id,
        "payload_json": action.payload_json or {},
        "created_at": action.created_at.isoformat() if action.created_at else None,
    }
