"""Foreign-only automatic event confirmation behind an explicit feature gate."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.foreign_event import ForeignEvent
from app.models.foreign_event_candidate import ForeignEventCandidate
from app.models.foreign_event_run import ForeignEventRun
from app.services.foreign_event_service import (
    ForeignEventService,
    serialize_candidate,
    serialize_event,
)


@dataclass(frozen=True)
class ForeignAutoAggregationResult:
    run: ForeignEventRun
    created_events: list[ForeignEvent]
    pending_candidates: list[ForeignEventCandidate | dict]


class ForeignEventAutoAggregationService:
    """Auto-confirm only high-confidence, same-language, multi-source groups."""

    @staticmethod
    def is_enabled() -> bool:
        return bool(settings.foreign_event_auto_aggregation_enabled)

    @staticmethod
    def _eligible(candidate: ForeignEventCandidate) -> bool:
        return (
            candidate.candidate_status == "candidate"
            and candidate.language in {"zh", "en"}
            and candidate.confidence >= settings.foreign_event_auto_confidence_threshold
            and candidate.opinion_count >= 2
            and candidate.source_count >= 2
        )

    def aggregate(
        self,
        db: Session,
        *,
        user_id: int | None = None,
        dry_run: bool = True,
        opinion_ids: list[int] | None = None,
    ) -> ForeignAutoAggregationResult:
        if not self.is_enabled():
            raise PermissionError("Foreign event auto aggregation is disabled")
        if settings.foreign_event_cross_language_auto_confirm_enabled:
            raise PermissionError("Cross-language automatic confirmation is not implemented")
        service = ForeignEventService()
        try:
            run, candidates, previews = service.rebuild_candidates(
                db,
                user_id=user_id,
                dry_run=dry_run,
                opinion_ids=opinion_ids,
                trigger_type="auto",
                time_window_hours=settings.foreign_event_auto_time_window_hours,
                commit=dry_run,
            )
        except Exception as exc:
            if not dry_run:
                db.rollback()
                failed_run = ForeignEventRun(
                    scope="foreign",
                    trigger_type="auto",
                    aggregation_version="foreign-event-v1",
                    dry_run=False,
                    status="failed",
                    failed_count=1,
                    error_message=_safe_error_summary(str(exc)),
                    started_at=_utcnow(),
                    finished_at=_utcnow(),
                )
                db.add(failed_run)
                db.commit()
            raise
        if dry_run:
            return ForeignAutoAggregationResult(
                run=run, created_events=[], pending_candidates=previews
            )

        created_events: list[ForeignEvent] = []
        pending_candidates: list[ForeignEventCandidate] = []
        try:
            for candidate in candidates:
                if not self._eligible(candidate):
                    pending_candidates.append(candidate)
                    continue
                candidate.review_source = "auto"
                db.flush()
                event = service.confirm_candidate(
                    db,
                    candidate.id,
                    user_id=user_id,
                    reason=(
                        "Automatic foreign aggregation: same-language, high-confidence, "
                        "time-window and multi-source candidate"
                    ),
                    request_id=f"foreign-auto-confirm:{run.id}:{candidate.id}",
                    confirmation_source="auto",
                    commit=False,
                )
                created_events.append(event)
                run.created_event_count += 1
            run.status = "success"
            db.commit()
        except Exception as exc:
            snapshot = {
                "aggregation_version": run.aggregation_version,
                "input_count": run.input_count,
                "candidate_count": run.candidate_count,
                "created_event_count": run.created_event_count,
                "started_at": run.started_at,
            }
            db.rollback()
            failed_run = ForeignEventRun(
                scope="foreign",
                trigger_type="auto",
                aggregation_version=snapshot["aggregation_version"],
                input_count=snapshot["input_count"],
                candidate_count=snapshot["candidate_count"],
                created_event_count=0,
                failed_count=1,
                status="failed",
                dry_run=False,
                error_message=_safe_error_summary(str(exc)),
                started_at=snapshot["started_at"],
            )
            failed_run.finished_at = _utcnow()
            db.add(failed_run)
            db.commit()
            raise
        for event in created_events:
            db.refresh(event)
        return ForeignAutoAggregationResult(
            run=run,
            created_events=created_events,
            pending_candidates=pending_candidates,
        )


def serialize_auto_result(result: ForeignAutoAggregationResult) -> dict:
    return {
        "run": {
            "id": result.run.id,
            "scope": result.run.scope,
            "trigger_type": result.run.trigger_type,
            "status": result.run.status,
            "dry_run": result.run.dry_run,
            "input_count": result.run.input_count,
            "candidate_count": result.run.candidate_count,
            "created_event_count": result.run.created_event_count,
            "failed_count": result.run.failed_count,
        },
        "created_events": [serialize_event(event) for event in result.created_events],
        "pending_candidates": [
            serialize_candidate(item) if isinstance(item, ForeignEventCandidate) else item
            for item in result.pending_candidates
        ],
    }


def _utcnow():
    return datetime.now(timezone.utc)


def _safe_error_summary(value: str | None) -> str:
    text = " ".join(str(value or "").split())
    lowered = text.casefold()
    if any(marker in lowered for marker in ("traceback", "sqlalchemy", "psycopg", "password", "token", "secret", "api key", "proxy", "connection string")):
        return "外网事件自动聚合失败，详细错误已隐藏"
    return text[:240] or "foreign event auto aggregation failed"
