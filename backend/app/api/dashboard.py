"""Dashboard stats API (指挥大屏 Phase 1 数据契约修正)。

路由前缀 /api/dashboard（由 main 以 prefix="/api" 挂载）。

端点：
  GET /api/dashboard/stats        总览（支持 ?days=N，默认 7，范围 1-90）
  GET /api/dashboard/recent       实时快讯
  GET /api/dashboard/alerts       预警滚动
  GET /api/dashboard/hot-keywords 指挥大屏热门关键词（新增；?days=N&limit=M）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardAlertItem,
    DashboardStatsResponse,
    HotKeywordsResponse,
    RecentOpinionItem,
    RegionChildrenResponse,
)
from app.services import dashboard_service

dashboard_router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


@dashboard_router.get("/stats", response_model=DashboardStatsResponse)
def dashboard_stats(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    days: int = Query(
        default=7,
        ge=1,
        le=90,
        description="时间窗口天数（影响 trend/sentiments/sources/regions/hot_keywords；"
        "total/event_count/high_risk/today 不受其影响）",
    ),
) -> DashboardStatsResponse:
    """Dashboard 总览统计。

    累计/当日/窗口三类指标口径见 app/schemas/dashboard.DashboardStatsResponse 与
    app/services/dashboard_service 模块 docstring。
    """
    return DashboardStatsResponse(**dashboard_service.get_dashboard_stats(db, days=days))


@dashboard_router.get("/recent", response_model=list[RecentOpinionItem])
def dashboard_recent(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    limit: int = Query(default=8, ge=1, le=50, description="返回最新舆情条数"),
) -> list[RecentOpinionItem]:
    """实时快讯：最近产生的舆情（按创建时间倒序）。"""
    return [RecentOpinionItem(**d) for d in dashboard_service.get_recent_opinions(db, limit=limit)]


@dashboard_router.get("/alerts", response_model=list[DashboardAlertItem])
def dashboard_alerts(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    limit: int = Query(default=8, ge=1, le=50, description="返回最新预警条数"),
) -> list[DashboardAlertItem]:
    """预警滚动：最近触发的预警记录（按时间倒序）。"""
    return [DashboardAlertItem(**d) for d in dashboard_service.get_dashboard_alerts(db, limit=limit)]


@dashboard_router.get("/hot-keywords", response_model=HotKeywordsResponse)
def dashboard_hot_keywords(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    days: int = Query(default=7, ge=1, le=90, description="统计窗口天数"),
    limit: int = Query(default=10, ge=1, le=50, description="返回热词条数"),
) -> HotKeywordsResponse:
    """指挥大屏热门关键词：基于监测关键词表对窗口内 title+content 的真实提及频次。

    不读取 Opinion.keywords（敏感词命中集合）。空数据返回稳定空结构，不 500。
    """
    return HotKeywordsResponse(**dashboard_service.get_hot_keywords(db, days=days, limit=limit))


@dashboard_router.get("/region-children", response_model=RegionChildrenResponse)
def dashboard_region_children(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    province: str = Query(..., min_length=1, description="省级名称，如「河北省」"),
    days: int = Query(default=7, ge=1, le=90, description="统计窗口天数"),
) -> RegionChildrenResponse:
    """地区下钻：返回指定省份下属市/县舆情分布（指挥大屏地图点击下钻用）。

    按 Region.parent_code 链取该省下属市/县，市级按名称上卷以匹配市级 GeoJSON 着色；
    无匹配省份返回 404。
    """
    result = dashboard_service.get_region_children(db, province_name=province, days=days)
    if result is None:
        raise HTTPException(status_code=404, detail=f"未找到省份：{province}")
    return RegionChildrenResponse(**result)
