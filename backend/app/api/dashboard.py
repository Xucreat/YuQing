"""驾驶舱统计 API（Phase 2B）。

路由（挂载在 /api 下，由 main.py 统一加前缀）：
  GET /dashboard/stats   统计总览（需 Bearer JWT）

统计逻辑全部在 app.services.dashboard_service，本文件只做：
  - 鉴权（Depends(get_current_user)）
  - 调用 service
  - 序列化为 DashboardStatsResponse

禁止提前实现：AI Service / DeepSeek / Collector / Event 聚合。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardStatsResponse
from app.services.dashboard_service import get_dashboard_stats

dashboard_router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    # 需登录（Bearer JWT）
    dependencies=[Depends(get_current_user)],
)


@dashboard_router.get("/stats", response_model=DashboardStatsResponse)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardStatsResponse:
    """驾驶舱统计总览。

    返回：total / today / high_risk / trend(近7日) / keywords(TOP10)。
    详见 app.schemas.dashboard.DashboardStatsResponse。
    """
    data = get_dashboard_stats(db)
    return DashboardStatsResponse(**data)
