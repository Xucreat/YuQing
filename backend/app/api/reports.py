"""舆情报告 API（P2 报告自动生成 + PDF 导出）。

- GET /api/reports/overview      返回报告总览 JSON（供前端预览）
- GET /api/reports/overview/pdf  返回 application/pdf 下载（reportlab 生成）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import ReportOverviewResponse
from app.services.report_service import build_overview, render_pdf

reports_router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_user)],
)


@reports_router.get("/overview", response_model=ReportOverviewResponse)
def report_overview(
    db: Session = Depends(get_db),
    _u: User = Depends(require_permission("reports:read")),
    days: int = Query(default=7, ge=7, le=30, description="统计周期（天）"),
) -> ReportOverviewResponse:
    """舆情报告总览数据。"""
    return ReportOverviewResponse(**build_overview(db, days=days))


@reports_router.get("/overview/pdf")
def report_overview_pdf(
    db: Session = Depends(get_db),
    _u: User = Depends(require_permission("reports:read")),
    days: int = Query(default=7, ge=7, le=30, description="统计周期（天）"),
) -> Response:
    """生成并下载舆情报告 PDF。"""
    data = build_overview(db, days=days)
    pdf_bytes = render_pdf(data)
    # HTTP 头文件名必须为 ASCII；内容中文由 reportlab 字体处理
    safe_ts = data["generated_at"].replace(":", "-").replace(" ", "_")
    filename = f"opinion_report_{safe_ts}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
