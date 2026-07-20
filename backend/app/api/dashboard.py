"""Dashboard stats API (Phase 2B + P2 指挥大屏)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.alert import AlertRecord
from app.models.opinion import Opinion
from app.models.region import Region
from app.models.user import User
from app.schemas.dashboard import (
    DashboardAlertItem,
    DashboardStatsResponse,
    RecentOpinionItem,
)
from app.services.dashboard_service import get_dashboard_stats

dashboard_router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


@dashboard_router.get("/stats", response_model=DashboardStatsResponse)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = Query(default=7, ge=7, le=30, description="Trend window in days"),
) -> DashboardStatsResponse:
    """Dashboard summary statistics."""
    data = get_dashboard_stats(db, days=days)
    return DashboardStatsResponse(**data)


@dashboard_router.get("/recent", response_model=list[RecentOpinionItem])
def dashboard_recent(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    limit: int = Query(default=8, ge=1, le=50, description="返回最新舆情条数"),
) -> list[RecentOpinionItem]:
    """实时快讯：最近产生的舆情（按创建时间倒序）。"""
    rows = (
        db.execute(
            select(
                Opinion.id,
                Opinion.title,
                Opinion.source,
                Opinion.sentiment,
                Opinion.risk_score,
                Region.name.label("region_name"),
                Opinion.created_at,
            )
            .join(Region, Region.id == Opinion.region_id)
            .order_by(Opinion.created_at.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    return [
        RecentOpinionItem(
            id=r["id"],
            title=r["title"] or "(无标题)",
            source=r["source"] or "未知",
            sentiment=r["sentiment"] or "neutral",
            risk_score=r["risk_score"] or 0,
            region_name=r["region_name"] or "未知",
            created_at=r["created_at"].isoformat() if r["created_at"] else "",
        )
        for r in rows
    ]


@dashboard_router.get("/alerts", response_model=list[DashboardAlertItem])
def dashboard_alerts(
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
    limit: int = Query(default=8, ge=1, le=50, description="返回最新预警条数"),
) -> list[DashboardAlertItem]:
    """预警滚动：最近触发的预警记录（按时间倒序）。"""
    rows = (
        db.query(AlertRecord)
        .order_by(AlertRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [
        DashboardAlertItem(
            id=r.id,
            rule_name=r.rule_name or "预警规则",
            risk_level=r.risk_level or "low",
            opinion_title=r.opinion_title or "",
            trigger_reason=r.trigger_reason or "",
            handled=bool(r.handled),
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
