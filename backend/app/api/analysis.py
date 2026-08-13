"""AI 单条舆情分析 API（手动「触发 AI 分析」）。

路由（挂载在 /api 下，由 main.py 统一加前缀）：
  POST /analyze/{opinion_id}   触发单条舆情 DeepSeek 分析并写库（Bearer JWT 保护）

设计（与「系统研判报告」区分）：
- 采集阶段已由 RuleFallbackProvider 生成「系统研判报告」（opinion.summary/sentiment/...），
  情感列恒以该规则路径为准。
- 本接口仅由用户手动触发，直接调用 DeepSeekProvider 生成「AI 研判报告」，
  结果写入独立的 ai_* 字段，**不覆盖**系统研判报告字段。
- DeepSeek 未配置或调用失败 -> 置 ai_analysis_status='failed' 并返回 500，
  前端在 AI 研判报告卡片中展示失败状态；系统报告不受影响。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.opinion import Opinion
from app.models.user import User
from app.schemas.opinion import DomesticAIAnalysisOut, OpinionOut
from app.services.ai.fallback import RuleFallbackProvider
from app.services.ai.providers.deepseek import DeepSeekProvider
from app.services.domestic_ai_service import DomesticAIService
from app.services.domestic_manual_review_service import ensure_domestic_manual_review
from app.services.current_risk import sync_domestic_rule_if_not_ai_adopted

analysis_router = APIRouter(
    tags=["analysis"],
    # 全部分析接口均需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)


@analysis_router.post(
    "/analyze/{opinion_id}",
    response_model=DomesticAIAnalysisOut,
    status_code=status.HTTP_200_OK,
)
def analyze_opinion(
    opinion_id: int,
    db: Session = Depends(get_db),
    # RBAC 收口：AI 研判由「仅登录」收敛为需要 ai:analyze（会消耗外部模型额度）。
    _current_user: User = Depends(require_permission("ai:analyze")),
) -> Opinion:
    """对指定舆情触发 AI 分析，更新结果并返回完整 Opinion。

    不存在：404 "Opinion not found"。
    AI 调用失败：置 analysis_status=failed，返回 500。
    """
    opinion = db.get(Opinion, opinion_id)
    if opinion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opinion not found",
        )

    try:
        # Keep the historical endpoint patch point used by existing callers
        # and tests, while the batch worker uses the service default provider.
        result, _ = DomesticAIService(provider_factory=DeepSeekProvider).analyze_opinion_manual(
            db, opinion_id, force=False
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if result.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error_message or "DeepSeek 调用失败，请检查 API 余额或网络后重试",
        )
    # Newly-created opinions historically received their rule projection from
    # this endpoint. Initialize only an untouched zero-score projection; never
    # overwrite an existing rule score with the AI score.
    if opinion.analysis_status == "pending" and opinion.risk_score == 0:
        rule = RuleFallbackProvider().analyze("\n".join(part for part in (opinion.title, opinion.summary, opinion.content) if part))
        opinion.summary = rule.summary
        opinion.sentiment = rule.sentiment
        opinion.risk_score = rule.risk_score
        opinion.keywords = ",".join(rule.keywords)
        opinion.analysis_status = "completed"
        opinion.analysis_time = result.analyzed_at
        opinion.analysis_suggestion = rule.suggestion
        sync_domestic_rule_if_not_ai_adopted(opinion)
    review, _ = ensure_domestic_manual_review(db, opinion_id, result.id, force=False)
    db.commit()
    db.refresh(opinion)
    payload = OpinionOut.model_validate(opinion).model_dump()
    payload.update(
        {
            "analysis_id": result.id,
            "review_id": review.id,
            "review_status": review.review_status,
            "event_preview": review.event_preview or {},
            "alert_preview": review.alert_preview or {},
            "message": "AI 研判完成，已进入人工复核",
        }
    )
    return payload
