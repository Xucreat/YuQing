"""AI 单条舆情分析 API（Phase 2C-1）。

路由（挂载在 /api 下，由 main.py 统一加前缀）：
  POST /analyze/{opinion_id}   触发单条舆情 AI 分析并写库（Bearer JWT 保护）

严格范围（本阶段）：
- 仅「手动触发单条分析」，不做批量 / 定时 / Celery / Redis。
- 业务不直接调用 DeepSeek / Provider，统一经 AIService。
- 流程：404 校验 -> 置 processing -> 调用 AIService.analyze ->
  成功写库（summary/sentiment/risk_score/keywords/analysis_suggestion/
          analysis_status=completed/analysis_time=now）/
  失败置 analysis_status=failed 并返回 500。
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
from app.services.ai import AIService

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

    # 1) 开始：置 processing
    opinion.analysis_status = "processing"
    db.commit()

    # 2) 调用 AIService（不直接连 DeepSeek / Provider）
    ai_service = AIService()
    try:
        result = ai_service.analyze(opinion.title, opinion.content)
    except Exception:
        # 3) 失败：保留 failed 状态，返回 500
        db.rollback()
        opinion.analysis_status = "failed"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI 分析失败，请稍后重试",
        )

    # 4) 成功：写库
    opinion.summary = result.summary
    opinion.sentiment = result.sentiment
    opinion.risk_score = result.risk_score
    # keywords 在库中为 TEXT 逗号分隔
    opinion.keywords = ",".join(result.keywords)
    opinion.analysis_suggestion = result.suggestion
    opinion.analysis_status = "completed"
    opinion.analysis_time = datetime.now(timezone.utc)
    db.commit()
    db.refresh(opinion)
    return opinion
