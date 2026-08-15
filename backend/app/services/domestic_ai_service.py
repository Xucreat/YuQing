from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.domestic_ai_result import DomesticAIResult
from app.models.opinion import Opinion
from app.schemas.ai import AIAnalysisResult
from app.services.ai.fallback import RuleFallbackProvider
from app.services.ai.providers.deepseek import DeepSeekProvider


AI_MODEL_NAME = "deepseek"
AI_MODEL_VERSION = "domestic-ai-v1"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _analysis_text(opinion: Opinion) -> str:
    return "\n".join(
        part.strip()
        for part in (opinion.title, opinion.summary, opinion.content)
        if part and part.strip()
    )


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
            "connection string",
            "://",
            "@",
        )
    ):
        return "国内 AI 分析失败，详细错误已隐藏"
    return message[:1000] or "国内 AI 分析失败"


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def serialize_domestic_ai_result(result: DomesticAIResult | None) -> dict | None:
    if result is None:
        return None
    return {
        "id": result.id,
        "opinion_id": result.opinion_id,
        "batch_run_id": result.batch_run_id,
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
        "actual_token_usage": result.actual_token_usage,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "updated_at": result.updated_at.isoformat() if result.updated_at else None,
    }


class DomesticAIService:
    """Run explicit domestic AI analysis without changing rule/effective risk."""

    def __init__(self, provider_factory=DeepSeekProvider):
        self.provider_factory = provider_factory

    def analyze_opinion_manual(
        self,
        db: Session,
        opinion_id: int,
        *,
        force: bool = False,
        batch_run_id: str | None = None,
    ) -> tuple[DomesticAIResult, bool]:
        opinion = db.get(Opinion, opinion_id)
        if opinion is None:
            raise LookupError("Opinion not found")
        text = _analysis_text(opinion)
        digest = _content_hash(text)
        if not force:
            existing = db.scalar(
                select(DomesticAIResult).where(
                    DomesticAIResult.opinion_id == opinion.id,
                    DomesticAIResult.content_hash == digest,
                    DomesticAIResult.model_name == AI_MODEL_NAME,
                    DomesticAIResult.model_version == AI_MODEL_VERSION,
                    DomesticAIResult.status == "completed",
                )
            )
            if existing is not None:
                if batch_run_id:
                    existing.batch_run_id = batch_run_id
                self._sync_projection(opinion, existing)
                db.commit()
                db.refresh(existing)
                return existing, True
        return self.analyze_opinion(db, opinion_id, batch_run_id=batch_run_id), False

    def analyze_opinion(self, db: Session, opinion_id: int, *, batch_run_id: str | None = None) -> DomesticAIResult:
        opinion = db.get(Opinion, opinion_id)
        if opinion is None:
            raise LookupError("Opinion not found")

        text = _analysis_text(opinion)
        digest = _content_hash(text)
        result = DomesticAIResult(
            opinion_id=opinion.id,
            batch_run_id=batch_run_id,
            content_hash=digest,
            model_name=AI_MODEL_NAME,
            model_version=AI_MODEL_VERSION,
            status="processing",
            actual_token_usage=_estimate_tokens(text),
        )
        db.add(result)
        opinion.ai_analysis_status = "processing"
        db.flush()

        try:
            provider = self.provider_factory()
            if provider.is_configured:
                ai = provider.analyze(text)
            else:
                # Preserve the legacy offline contract while keeping the
                # result in the domestic AI history/projection fields.
                ai = RuleFallbackProvider().analyze(text)
            result.summary = ai.summary.strip()
            result.sentiment = ai.sentiment
            result.risk_score = ai.risk_score
            result.keywords = list(dict.fromkeys(word.strip() for word in ai.keywords if word.strip()))
            result.suggestion = ai.suggestion.strip()
            result.status = "completed"
            result.error_message = None
            result.analyzed_at = _utcnow()
            db.execute(
                update(DomesticAIResult)
                .where(DomesticAIResult.opinion_id == opinion.id)
                .values(is_current=False)
            )
            result.is_current = True
            self._sync_projection(opinion, result)
        except Exception as exc:  # noqa: BLE001
            result.status = "failed"
            result.error_message = _safe_error(exc)
            result.analyzed_at = _utcnow()
            result.is_current = False
            opinion.ai_analysis_status = "failed"

        db.commit()
        db.refresh(result)
        return result

    @staticmethod
    def _sync_projection(opinion: Opinion, result: DomesticAIResult) -> None:
        """Keep legacy opinions.ai_* fields as the latest completed AI projection."""
        if result.status != "completed":
            return
        opinion.ai_summary = result.summary or ""
        opinion.ai_sentiment = result.sentiment if result.sentiment != "unknown" else "neutral"
        opinion.ai_risk_score = int(result.risk_score or 0)
        opinion.ai_keywords = ",".join(result.keywords or [])
        opinion.ai_analysis_suggestion = result.suggestion or None
        opinion.ai_analysis_status = "completed"
        opinion.ai_analysis_time = result.analyzed_at or _utcnow()
