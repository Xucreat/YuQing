"""Foreign-only AI review orchestration.

The provider is shared with the domestic AI stack, but all persistence and
permissions stay in foreign_* tables. Real provider calls are disabled unless
FOREIGN_AI_REVIEW_ENABLED is explicitly enabled by the caller.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.foreign_ai_result import ForeignAIResult
from app.models.foreign_analysis_run import ForeignAnalysisRun
from app.models.foreign_opinion import ForeignOpinion
from app.services.ai.providers.deepseek import DeepSeekProvider


AI_MODEL_VERSION = "foreign-ai-v1"
AI_ANALYZER_TYPE = "ai"
AI_MODEL_NAME = "deepseek"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _analysis_text(opinion: ForeignOpinion) -> str:
    return "\n".join(
        part.strip()
        for part in (opinion.title, opinion.summary, opinion.content)
        if part and part.strip()
    )


def _content_hash(text: str, fallback: str = "") -> str:
    return fallback or hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_error(value: object) -> str:
    message = " ".join(str(value or "").split())
    lowered = message.casefold()
    if any(
        marker in lowered
        for marker in (
            "traceback",
            "password",
            "token",
            "secret",
            "api key",
            "proxy",
            "connection string",
            "://",
            "@",
        )
    ):
        return "外网 AI 分析失败，详细错误已隐藏"
    return message[:1000] or "外网 AI 分析失败"


def foreign_ai_is_enabled() -> bool:
    return settings.foreign_ai_review_enabled


class ForeignAIService:
    """Run one explicit foreign AI analysis and persist an isolated result."""

    def _new_run(self, db: Session, opinion_id: int) -> ForeignAnalysisRun:
        run = ForeignAnalysisRun(
            foreign_opinion_id=opinion_id,
            analyzer_type=AI_ANALYZER_TYPE,
            model_name=AI_MODEL_NAME,
            model_version=AI_MODEL_VERSION,
            status="running",
            started_at=_utcnow(),
        )
        db.add(run)
        db.flush()
        return run

    @staticmethod
    def _finish_run(
        run: ForeignAnalysisRun,
        *,
        status: str,
        success: int,
        failed: int,
        error_message: str | None = None,
    ) -> None:
        run.status = status
        run.finished_at = _utcnow()
        run.processed_count = 1
        run.success_count = success
        run.failed_count = failed
        run.error_message = error_message

    def analyze_opinion_manual(
        self, db: Session, opinion_id: int, *, force: bool = False
    ) -> tuple[ForeignAIResult, bool]:
        """Manual entry point with click-level idempotency.

        Returns ``(result, reused)``. ``reused`` is True when a completed
        evaluation for exactly the same content and model already exists, in
        which case the provider is *not* called again. This is what keeps a
        double click from producing a second AI result or a second alert.
        Pass ``force=True`` to deliberately re-run the review.
        """
        opinion = db.get(ForeignOpinion, opinion_id)
        if opinion is None:
            raise LookupError("Foreign opinion not found")
        if not force:
            digest = _content_hash(_analysis_text(opinion), opinion.content_hash or "")
            existing = db.scalar(
                select(ForeignAIResult).where(
                    ForeignAIResult.foreign_opinion_id == opinion.id,
                    ForeignAIResult.model_name == AI_MODEL_NAME,
                    ForeignAIResult.model_version == AI_MODEL_VERSION,
                    ForeignAIResult.content_hash == digest,
                    ForeignAIResult.status == "completed",
                )
            )
            if existing is not None:
                return existing, True
        return self.analyze_opinion(db, opinion_id), False

    def analyze_opinion(self, db: Session, opinion_id: int) -> ForeignAIResult:
        opinion = db.get(ForeignOpinion, opinion_id)
        if opinion is None:
            raise LookupError("Foreign opinion not found")

        text = _analysis_text(opinion)
        digest = _content_hash(text, opinion.content_hash or "")
        run = self._new_run(db, opinion.id)
        result = db.scalar(
            select(ForeignAIResult).where(
                ForeignAIResult.foreign_opinion_id == opinion.id,
                ForeignAIResult.model_name == AI_MODEL_NAME,
                ForeignAIResult.model_version == AI_MODEL_VERSION,
                ForeignAIResult.content_hash == digest,
            )
        )
        if result is None:
            result = ForeignAIResult(
                foreign_opinion_id=opinion.id,
                analysis_run_id=run.id,
                content_hash=digest,
                model_name=AI_MODEL_NAME,
                model_version=AI_MODEL_VERSION,
                status="processing",
            )
            db.add(result)
        else:
            result.analysis_run_id = run.id
            result.status = "processing"
            result.error_message = None
        db.flush()

        if not foreign_ai_is_enabled():
            result.status = "failed"
            result.error_message = "Foreign AI review is disabled"
            result.analyzed_at = _utcnow()
            result.is_current = False
            self._finish_run(
                run,
                status="failed",
                success=0,
                failed=1,
                error_message=result.error_message,
            )
            db.commit()
            db.refresh(result)
            return result

        try:
            provider = DeepSeekProvider()
            if not provider.is_configured:
                raise RuntimeError("DeepSeek provider is not configured")
            ai = provider.analyze(text)
            result.summary = ai.summary.strip()
            result.sentiment = ai.sentiment
            result.risk_score = ai.risk_score
            result.keywords = list(dict.fromkeys(word.strip() for word in ai.keywords if word.strip()))
            result.suggestion = ai.suggestion.strip()
            result.status = "completed"
            result.error_message = None
            result.analyzed_at = _utcnow()
            db.execute(
                update(ForeignAIResult)
                .where(ForeignAIResult.foreign_opinion_id == opinion.id)
                .values(is_current=False)
            )
            result.is_current = True
            self._finish_run(run, status="success", success=1, failed=0)
        except Exception as exc:  # noqa: BLE001
            result.status = "failed"
            result.error_message = _safe_error(exc)
            result.analyzed_at = _utcnow()
            result.is_current = False
            self._finish_run(
                run,
                status="failed",
                success=0,
                failed=1,
                error_message=result.error_message,
            )

        db.commit()
        db.refresh(result)
        return result


def serialize_ai_result(result: ForeignAIResult | None) -> dict | None:
    if result is None:
        return None
    return {
        "id": result.id,
        "foreign_opinion_id": result.foreign_opinion_id,
        "analysis_run_id": result.analysis_run_id,
        "content_hash": result.content_hash,
        "model_name": result.model_name,
        "model_version": result.model_version,
        "status": result.status,
        "summary": result.summary,
        "sentiment": result.sentiment,
        "risk_score": result.risk_score,
        "keywords": result.keywords or [],
        "suggestion": result.suggestion,
        "error_message": result.error_message,
        "analyzed_at": result.analyzed_at.isoformat() if result.analyzed_at else None,
        "is_current": bool(result.is_current),
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "updated_at": result.updated_at.isoformat() if result.updated_at else None,
    }
