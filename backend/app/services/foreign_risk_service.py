"""独立外网风险与情感分析服务。

该服务只消费 ``ForeignOpinion`` 与 ``foreign_keywords``(type='sensitive')，
只写入 ``foreign_analysis_runs`` 与 ``foreign_risk_results``。它不调用国内
RiskEngine、AIService、Event、Alert 或 Dashboard 服务。
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.foreign_analysis_run import ForeignAnalysisRun
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.models.foreign_risk_term import ForeignRiskTerm
from app.core.config import settings
from app.models.foreign_risk_result import ForeignRiskResult
from app.services.current_risk import sync_foreign_rule_if_not_ai_adopted
from app.services.foreign_content_sanitizer import (
    detect_foreign_language,
    normalize_foreign_article,
)


RULE_ANALYZER_TYPE = "rule"
RULE_MODEL_NAME = "foreign-rule-engine"
RULE_MODEL_VERSION = "foreign-risk-v1"
BASE_RISK_SCORE = 20
MAX_RISK_SCORE = 100
MEDIUM_RISK_THRESHOLD = 40
HIGH_RISK_THRESHOLD = 70
MIN_ANALYZABLE_CHARACTERS = 10


def _safe_error(value: object) -> str:
    message = " ".join(str(value or "").split())
    lowered = message.casefold()
    if any(
        marker in lowered
        for marker in (
            "traceback", "sqlalchemy", "psycopg", "password", "token",
            "secret", "api key", "proxy", "connection string",
        )
    ):
        return "外网规则分析失败，详细错误已隐藏"
    return message[:240] or "外网规则分析失败"


@dataclass(frozen=True)
class RiskDecision:
    content_hash: str
    language: str
    risk_score: int | None
    risk_level: str
    sentiment: str
    sentiment_confidence: float | None
    risk_category: str
    matched_terms: list[dict]
    explanation: str
    analysis_status: str


@dataclass(frozen=True)
class _SensitiveTerm:
    """把 ``foreign_keywords``(type='sensitive') 适配成 _build_decision 需要的词形。

    ``foreign_keywords`` 没有 language / term_set_version / sentiment 列，这里用
    固定适配值：
    - language="" 使 _term_applies 对任意文章语言都返回 True（敏感词按子串命中，
      不区分中英文文章）；
    - sentiment="negative" 表示敏感词命中即偏负面，符合风险语义；
    - term_set_version="" 仅用于与既有去重键保持一致。
    """

    word: str
    language: str
    category: str
    severity_weight: int
    sentiment: str
    term_set_version: str
    is_enabled: bool = True


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _analysis_text(opinion: ForeignOpinion) -> str:
    """按标题、摘要、正文顺序构造分析输入，不修改原始字段。"""
    return normalize_foreign_article(opinion.title, opinion.summary, opinion.content)


def _content_hash(text: str, fallback: str = "") -> str:
    return fallback or hashlib.sha256(text.encode("utf-8")).hexdigest()


def detect_language(text: str) -> str:
    """轻量、可解释的语言识别：zh/en/mixed/unknown。"""
    return detect_foreign_language(text)


def _risk_level(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= HIGH_RISK_THRESHOLD:
        return "high"
    if score >= MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def _term_applies(term: _SensitiveTerm, language: str) -> bool:
    if term.language in {"unknown", "mixed", ""}:
        return True
    if language == "mixed":
        return term.language in {"zh", "en"}
    return term.language == language


def _build_decision(opinion: ForeignOpinion, terms: Iterable[_SensitiveTerm]) -> RiskDecision:
    text = _analysis_text(opinion)
    digest = _content_hash(text, opinion.content_hash or "")
    if len("".join(text.split())) < MIN_ANALYZABLE_CHARACTERS:
        return RiskDecision(
            content_hash=digest,
            language=detect_language(text),
            risk_score=None,
            risk_level="unknown",
            sentiment="unknown",
            sentiment_confidence=None,
            risk_category="unknown",
            matched_terms=[],
            explanation="标题、摘要和正文均为空或内容过短，跳过风险与情感判断。",
            analysis_status="skipped",
        )

    language = detect_language(text)
    if language == "unknown":
        return RiskDecision(
            content_hash=digest,
            language=language,
            risk_score=None,
            risk_level="unknown",
            sentiment="unknown",
            sentiment_confidence=None,
            risk_category="unknown",
            matched_terms=[],
            explanation="无法可靠识别文本语言，保留文章但不伪造低风险结果。",
            analysis_status="completed",
        )

    enabled_terms = [
        term
        for term in terms
        if term.is_enabled and term.word.strip() and _term_applies(term, language)
    ]
    matched_terms: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for term in enabled_terms:
        word = term.word.strip()
        haystack = text if term.language == "zh" else text.casefold()
        needle = word if term.language == "zh" else word.casefold()
        key = (word.casefold(), term.language, term.term_set_version)
        if needle in haystack and key not in seen:
            seen.add(key)
            matched_terms.append(
                {
                    "word": word,
                    "language": term.language,
                    "category": term.category,
                    "severity_weight": term.severity_weight,
                    "sentiment": term.sentiment,
                    "term_set_version": term.term_set_version,
                }
            )

    # 外网评分契约独立于国内 RiskEngine：
    # risk_score = min(100, 20 + sum(matched severity_weight))
    # 未配置风险词时仍返回可追踪的低风险基线，不把采集关键词当成风险词。
    score = min(
        MAX_RISK_SCORE,
        BASE_RISK_SCORE + sum(int(item["severity_weight"]) for item in matched_terms),
    )
    positive_hits = sum(item["sentiment"] == "positive" for item in matched_terms)
    negative_hits = sum(item["sentiment"] == "negative" for item in matched_terms)
    if positive_hits == 0 and negative_hits == 0:
        sentiment = "neutral"
        confidence = 0.0
    elif positive_hits > negative_hits:
        sentiment = "positive"
        confidence = round(positive_hits / max(positive_hits + negative_hits, 1), 3)
    elif negative_hits > positive_hits:
        sentiment = "negative"
        confidence = round(negative_hits / max(positive_hits + negative_hits, 1), 3)
    else:
        sentiment = "neutral"
        confidence = 0.5

    categories = sorted({item["category"] for item in matched_terms if item["category"]})
    category = categories[0] if len(categories) == 1 else ("mixed" if categories else "none")
    if matched_terms:
        explanation = (
            f"外网规则分析完成：语言={language}，命中 {len(matched_terms)} 个风险词，"
            f"按基线 {BASE_RISK_SCORE} 加权后得分为 {score}。"
        )
    else:
        explanation = (
            f"外网规则分析完成：语言={language}，未命中已配置外网风险词；"
            f"使用保守基线 {BASE_RISK_SCORE}，采集关键词不参与风险评分。"
        )
    return RiskDecision(
        content_hash=digest,
        language=language,
        risk_score=score,
        risk_level=_risk_level(score),
        sentiment=sentiment,
        sentiment_confidence=confidence,
        risk_category=category,
        matched_terms=matched_terms,
        explanation=explanation,
        analysis_status="completed",
    )


def foreign_ai_is_enabled() -> bool:
    """外网 AI 研判总开关：读取 settings.foreign_ai_review_enabled（源自 .env）。"""
    return settings.foreign_ai_review_enabled


class ForeignRiskService:
    """外网规则分析的唯一业务入口。"""

    def _new_run(
        self,
        db: Session,
        *,
        foreign_opinion_id: int | None,
        analyzer_type: str,
        model_name: str | None,
        model_version: str,
    ) -> ForeignAnalysisRun:
        run = ForeignAnalysisRun(
            foreign_opinion_id=foreign_opinion_id,
            analyzer_type=analyzer_type,
            model_name=model_name,
            model_version=model_version,
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
        processed: int,
        success: int,
        failed: int,
        error_message: str | None = None,
    ) -> None:
        run.status = status
        run.finished_at = _utcnow()
        run.processed_count = processed
        run.success_count = success
        run.failed_count = failed
        run.error_message = error_message

    def _existing_result(
        self,
        db: Session,
        *,
        opinion_id: int,
        content_hash: str,
        analyzer_type: str,
        model_name: str | None,
        model_version: str,
    ) -> ForeignRiskResult | None:
        return db.scalar(
            select(ForeignRiskResult).where(
                ForeignRiskResult.foreign_opinion_id == opinion_id,
                ForeignRiskResult.content_hash == content_hash,
                ForeignRiskResult.analyzer_type == analyzer_type,
                ForeignRiskResult.model_name == model_name,
                ForeignRiskResult.model_version == model_version,
            )
        )

    def _load_sensitive_terms(self, db: Session) -> list[_SensitiveTerm]:
        """加载国外风险词：只用 foreign_keywords 中 type='sensitive' 且启用的词。

        这是国外舆情风险评分的唯一运行时配置来源，monitoring 类型绝不参与评分；
        foreign_risk_terms 已通过迁移并入 foreign_keywords，不再作为评分来源。
        """
        rows = db.scalars(
            select(ForeignKeyword)
            .where(ForeignKeyword.type == "sensitive", ForeignKeyword.is_enabled.is_(True))
            .order_by(ForeignKeyword.id.asc())
        ).all()
        terms = [
            _SensitiveTerm(
                word=kw.word,
                language=str((kw.rule_config or {}).get("language") or ""),
                category=kw.category or "general",
                severity_weight=int(kw.severity_weight or 0),
                sentiment=str((kw.rule_config or {}).get("sentiment") or "negative"),
                term_set_version=str((kw.rule_config or {}).get("term_set_version") or ""),
            )
            for kw in rows
        ]
        # Keep the versioned legacy table readable during the migration period.
        # This also makes mixed-language fixtures and older deployments obey the
        # same language applicability and idempotency contract.
        legacy_rows = db.scalars(
            select(ForeignRiskTerm)
            .where(ForeignRiskTerm.is_enabled.is_(True))
            .order_by(ForeignRiskTerm.id.asc())
        ).all()
        terms.extend(
            _SensitiveTerm(
                word=row.word,
                language=row.language or "unknown",
                category=row.category or "general",
                severity_weight=int(row.severity_weight or 0),
                sentiment=row.sentiment or "unknown",
                term_set_version=row.term_set_version or "",
            )
            for row in legacy_rows
        )
        return terms

    def _analyze_one(
        self,
        db: Session,
        opinion: ForeignOpinion,
        *,
        run: ForeignAnalysisRun,
        analyzer_type: str = RULE_ANALYZER_TYPE,
        model_name: str | None = RULE_MODEL_NAME,
        model_version: str = RULE_MODEL_VERSION,
        terms: list[_SensitiveTerm] | None = None,
        force: bool = False,
    ) -> tuple[ForeignRiskResult, bool]:
        text = _analysis_text(opinion)
        digest = _content_hash(text, opinion.content_hash or "")
        cached = self._existing_result(
            db,
            opinion_id=opinion.id,
            content_hash=digest,
            analyzer_type=analyzer_type,
            model_name=model_name,
            model_version=model_version,
        )
        if cached is not None and cached.analysis_status == "completed" and not force:
            return cached, False

        existing = cached
        try:
            if terms is None:
                terms = self._load_sensitive_terms(db)
            decision = _build_decision(opinion, terms)
            if existing is None:
                result = ForeignRiskResult(
                    foreign_opinion_id=opinion.id,
                    analysis_run_id=run.id,
                    analyzer_type=analyzer_type,
                    model_name=model_name,
                    model_version=model_version,
                )
                db.add(result)
            else:
                result = existing
                result.analysis_run_id = run.id
            result.content_hash = decision.content_hash
            result.language = decision.language
            result.risk_score = decision.risk_score
            result.risk_level = decision.risk_level
            result.sentiment = decision.sentiment
            result.sentiment_confidence = decision.sentiment_confidence
            result.risk_category = decision.risk_category
            result.matched_terms = decision.matched_terms
            result.explanation = decision.explanation
            result.analysis_status = decision.analysis_status
            result.error_message = None
            result.analyzed_at = _utcnow()
            if decision.analysis_status == "completed":
                db.execute(
                    update(ForeignRiskResult)
                    .where(ForeignRiskResult.foreign_opinion_id == opinion.id)
                    .values(is_current=False)
                )
                result.is_current = True
            else:
                result.is_current = False
            db.flush()
            sync_foreign_rule_if_not_ai_adopted(opinion, result)
            db.flush()
            return result, True
        except Exception as exc:
            if existing is None:
                result = ForeignRiskResult(
                    foreign_opinion_id=opinion.id,
                    analysis_run_id=run.id,
                    content_hash=digest,
                    language=detect_language(text),
                    risk_score=None,
                    risk_level="unknown",
                    sentiment="unknown",
                    risk_category="unknown",
                    matched_terms=[],
                    explanation="外网规则分析失败，原文仍保留。",
                    analyzer_type=analyzer_type,
                    model_name=model_name,
                    model_version=model_version,
                    analysis_status="failed",
                    error_message=_safe_error(exc),
                    analyzed_at=_utcnow(),
                    is_current=False,
                )
                db.add(result)
            else:
                result = existing
                result.analysis_run_id = run.id
                result.analysis_status = "failed"
                result.error_message = _safe_error(exc)
                result.analyzed_at = _utcnow()
            db.flush()
            return result, True

    def analyze_opinion(
        self,
        db: Session,
        opinion_id: int,
        *,
        model_version: str = RULE_MODEL_VERSION,
    ) -> ForeignRiskResult:
        opinion = db.get(ForeignOpinion, opinion_id)
        if opinion is None:
            raise LookupError("Foreign opinion not found")
        run = self._new_run(
            db,
            foreign_opinion_id=opinion.id,
            analyzer_type=RULE_ANALYZER_TYPE,
            model_name=RULE_MODEL_NAME,
            model_version=model_version,
        )
        result, processed = self._analyze_one(
            db,
            opinion,
            run=run,
            model_version=model_version,
        )
        if result.analysis_status == "failed":
            self._finish_run(
                run,
                status="failed",
                processed=1,
                success=0,
                failed=1,
                error_message=result.error_message,
            )
        elif processed:
            self._finish_run(run, status="success", processed=1, success=1, failed=0)
        else:
            self._finish_run(run, status="skipped", processed=1, success=0, failed=0)
        db.commit()
        db.refresh(result)
        return result

    def analyze_many(
        self,
        db: Session,
        opinion_ids: list[int],
        *,
        model_version: str = RULE_MODEL_VERSION,
        force: bool = False,
    ) -> tuple[ForeignAnalysisRun, list[ForeignRiskResult]]:
        if not opinion_ids:
            raise ValueError("opinion_ids must not be empty")
        if len(opinion_ids) > 50:
            raise ValueError("batch size must be <= 50")
        opinions = db.scalars(
            select(ForeignOpinion).where(ForeignOpinion.id.in_(opinion_ids))
        ).all()
        by_id = {opinion.id: opinion for opinion in opinions}
        missing = [opinion_id for opinion_id in opinion_ids if opinion_id not in by_id]
        if missing:
            raise LookupError(f"Foreign opinions not found: {missing[:5]}")
        # 同一批次共享一份敏感词快照，避免逐条查询。
        terms = self._load_sensitive_terms(db)
        run = self._new_run(
            db,
            foreign_opinion_id=None,
            analyzer_type=RULE_ANALYZER_TYPE,
            model_name=RULE_MODEL_NAME,
            model_version=model_version,
        )
        results: list[ForeignRiskResult] = []
        success = failed = 0
        for opinion_id in opinion_ids:
            result, processed = self._analyze_one(
                db,
                by_id[opinion_id],
                run=run,
                model_version=model_version,
                terms=terms,
                force=force,
            )
            results.append(result)
            if not processed:
                continue
            if result.analysis_status == "failed":
                failed += 1
            else:
                success += 1
        self._finish_run(
            run,
            status="failed" if failed and not success else "partial" if failed else "success",
            processed=len(opinion_ids),
            success=success,
            failed=failed,
        )
        db.commit()
        db.refresh(run)
        for result in results:
            db.refresh(result)
        return run, results

    def rescore_all(
        self,
        db: Session,
        *,
        chunk_size: int = 50,
        task: "Task | None" = None,
    ) -> dict:
        """对全部国外舆情重新评分（绕过 content_hash 幂等缓存）。

        用于国外敏感词增删改后，让历史舆情风险分同步到最新词库。可重复执行，
        且每次都按当前启用的敏感词重新计算。``task`` 为后台任务对象时上报进度。
        """
        ids = [row[0] for row in db.execute(select(ForeignOpinion.id)).all()]
        total = len(ids)
        done = 0
        for i in range(0, total, chunk_size):
            chunk = ids[i : i + chunk_size]
            self.analyze_many(db, chunk, force=True)
            done += len(chunk)
            if task is not None:
                task.progress = int(done / total * 100) if total else 100
                task.step = f"已重新评分 {done}/{total}"
        return {"rescored": done, "total": total}

    def manual_ai_review(self, db: Session, opinion_id: int) -> None:
        """显式保留 AI 入口，但 3A 默认拒绝外部调用。"""
        if not foreign_ai_is_enabled():
            raise RuntimeError("Foreign AI review is disabled")
        raise RuntimeError("Foreign AI provider is not configured for Phase 3A")
