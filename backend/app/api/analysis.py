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

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.opinion import Opinion
from app.models.user import User
from app.schemas.opinion import OpinionOut
from app.services.ai.providers.deepseek import DeepSeekProvider

analysis_router = APIRouter(
    tags=["analysis"],
    # 全部分析接口均需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)


@analysis_router.post(
    "/analyze/{opinion_id}",
    response_model=OpinionOut,
    status_code=status.HTTP_200_OK,
)
def analyze_opinion(
    opinion_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
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

    # 1) 开始：置 AI 分析 processing（不影响系统研判报告字段）
    opinion.ai_analysis_status = "processing"
    db.commit()

    # 2) 直接调用 DeepSeek（不走 AIService 兜底规则）：本接口即「触发 AI 分析」
    provider = DeepSeekProvider()
    if not provider.is_configured:
        opinion.ai_analysis_status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DeepSeek 未配置，无法生成 AI 研判报告",
        )

    text = f"标题：{opinion.title}\n正文：{opinion.content}"
    try:
        result = provider.analyze(text)
    except Exception:
        # 3) 失败：保留 failed 状态，返回 500（系统报告不受影响）
        db.rollback()
        opinion.ai_analysis_status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DeepSeek 调用失败，请检查 API 余额或网络后重试",
        )

    # 4) 成功：仅写 AI 研判报告字段（ai_*），不覆盖系统研判报告
    opinion.ai_summary = result.summary
    opinion.ai_sentiment = result.sentiment
    opinion.ai_risk_score = result.risk_score
    opinion.ai_keywords = ",".join(result.keywords)
    opinion.ai_analysis_suggestion = result.suggestion
    opinion.ai_analysis_status = "completed"
    opinion.ai_analysis_time = datetime.now(timezone.utc)
    db.commit()
    db.refresh(opinion)
    return opinion
