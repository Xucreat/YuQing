"""舆情报告 API（P2 报告自动生成 + PDF 导出 / Phase Report-1 可配置生成器）。

- GET  /api/reports/overview      返回报告总览 JSON（供前端预览，Legacy 兼容）
- GET  /api/reports/overview/pdf  返回 application/pdf 下载（reportlab 生成，Legacy 兼容）
- GET  /api/reports/modules       返回可配置报告的可选模块清单
- POST /api/reports/export        【正式入口】按配置生成并下载 PDF 报告
- POST /api/reports/generate      【Deprecated】Phase Report-1.1 入口，转调 export 逻辑
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.core.dependencies import get_current_user
from app.core.permissions import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.report import (
    ReportExportRequest,
    ReportGenerateRequest,
    ReportModuleDef,
    ReportModuleParamDef,
    ReportModulesResponse,
    ReportOverviewResponse,
    ReportTemplateCreate,
    ReportTemplateResponse,
    ReportTemplateUpdate,
)
from app.services.audit_service import log_operation
from app.services.report_service import (
    DEFAULT_MODULE_KEYS,
    MODULE_MAP,
    REPORT_MODULES,
    ReportConfig,
    build_overview,
    build_report,
    expand_module_keys,
    render_pdf,
    render_report_pdf,
)
from app.services.report_template_service import (
    create_template,
    delete_template,
    list_templates,
    update_template,
)
from app.models.report_record import ReportRecord

logger = logging.getLogger(__name__)

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
    request: Request,
    db: Session = Depends(get_db),
    _u: User = Depends(require_permission("reports:export")),
    days: int = Query(default=7, ge=7, le=30, description="统计周期（天）"),
) -> Response:
    """生成并下载舆情报告 PDF（Legacy 兼容）。需 reports:export 权限。"""
    data = build_overview(db, days=days)
    try:
        pdf_bytes = render_pdf(data)
    except Exception as exc:
        # 报告生成失败也记录审计（failed），不掩盖异常。
        log_operation(
            db, action="GENERATE", operator=_u, request=request,
            resource_type="report", result="failed", error_message=str(exc)[:1000],
            details={"days": days, "legacy": "overview/pdf"},
        )
        # Phase Report-1.1：写轻量导出审计记录（failed）
        db.add(ReportRecord(
            name="舆情监测报告(总览)",
            config_json={"days": days, "legacy": "overview/pdf", "time_field": "created_at"},
            status="failed",
            created_by=_u.id,
        ))
        db.commit()
        raise
    log_operation(
        db, action="GENERATE", operator=_u, request=request,
        resource_type="report", result="success", details={"days": days, "legacy": "overview/pdf"},
    )
    # Phase Report-1.1：写轻量导出审计记录（success）
    db.add(ReportRecord(
        name="舆情监测报告(总览)",
        config_json={"days": days, "legacy": "overview/pdf", "time_field": "created_at"},
        status="success",
        created_by=_u.id,
    ))
    db.commit()
    # HTTP 头文件名必须为 ASCII；内容中文由 reportlab 字体处理
    safe_ts = data["generated_at"].replace(":", "-").replace(" ", "_")
    filename = f"opinion_report_{safe_ts}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ---------------------------------------------------------------------------
# Phase Report-1：可配置报告生成器
# ---------------------------------------------------------------------------
@reports_router.get("/modules", response_model=ReportModulesResponse)
def report_modules(
    _u: User = Depends(require_permission("reports:read")),
) -> ReportModulesResponse:
    """返回可配置报告的全部可选模块及默认选中项。

    注：历史 key `distribution` 已拆分为 source_dist / region_dist / keyword_dist，
    不在本清单中展示，但导出请求中仍可提交（服务层自动展开）。
    """
    modules = [
        ReportModuleDef(
            key=m["key"],
            name=m["name"],
            title=m["title"],
            description=m["description"],
            default_enabled=bool(m.get("default_enabled", True)),
            params=[ReportModuleParamDef(**p) for p in (m.get("params") or [])],
        )
        for m in REPORT_MODULES
    ]
    return ReportModulesResponse(modules=modules, default_modules=list(DEFAULT_MODULE_KEYS))


# ---------------------------------------------------------------------------
# Phase Report-2-P1：统一导出执行体（/export 与 legacy /generate 共用）
# ---------------------------------------------------------------------------
def _do_export(
    *,
    request: Request,
    db: Session,
    user: User,
    report_name: str,
    time_field: str,
    start_date: str | None,
    end_date: str | None,
    days: int,
    module_keys: List[str],
    module_params: Dict[str, Dict[str, Any]],
    config_snapshot: dict,
    entry: str,
) -> Response:
    """生成 PDF 并落审计（成功/失败均写 report_records）。"""
    expanded = expand_module_keys(module_keys)
    invalid = [k for k in expanded if k not in MODULE_MAP]
    if invalid:
        raise HTTPException(status_code=400, detail=f"未知报告模块：{invalid}")
    if not expanded:
        raise HTTPException(status_code=400, detail="请至少选择一个报告模块")

    report_name = (report_name or "舆情监测报告").strip() or "舆情监测报告"
    cfg = ReportConfig(
        report_name=report_name,
        time_field=time_field,
        start_date=start_date,
        end_date=end_date,
        days=days,
        module_keys=expanded,
        module_params=module_params or {},
    )
    try:
        report = build_report(db, cfg)
        pdf_bytes = render_report_pdf(report)
    except Exception as exc:  # 仅整体性异常（单模块失败已在服务层隔离）
        log_operation(
            db, action="GENERATE", operator=user, request=request,
            resource_type="report", result="failed", error_message=str(exc)[:1000],
            details={"report_name": report_name, "modules": expanded, "entry": entry},
        )
        db.add(ReportRecord(
            name=report_name, config_json=config_snapshot,
            status="failed", created_by=user.id,
        ))
        db.commit()
        raise

    failed_modules = report.get("meta", {}).get("failed_modules") or []
    if failed_modules:
        logger.warning("报告生成完成但存在失败模块：%s（entry=%s）", failed_modules, entry)
    log_operation(
        db, action="GENERATE", operator=user, request=request,
        resource_type="report", result="success",
        details={
            "report_name": report_name, "modules": expanded,
            "entry": entry, "failed_modules": failed_modules,
        },
    )
    db.add(ReportRecord(
        name=report_name,
        config_json={**config_snapshot, "failed_modules": failed_modules, "entry": entry},
        status="success",
        created_by=user.id,
    ))
    db.commit()

    safe_name = report_name.replace("/", "_").replace("\\", "_")
    ascii_name = safe_name.encode("ascii", "ignore").decode() or "report"
    filename = f"{safe_name}.pdf"
    headers = {
        "Content-Disposition": (
            f"attachment; filename={ascii_name}.pdf; "
            f"filename*=UTF-8''{quote(filename)}"
        )
    }
    if failed_modules:
        # 供前端提示「部分模块生成失败」，不影响下载本身
        headers["X-Report-Failed-Modules"] = ",".join(failed_modules)
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@reports_router.post("/export")
def report_export(
    request: Request,
    payload: ReportExportRequest,
    db: Session = Depends(get_db),
    _u: User = Depends(require_permission("reports:export")),
) -> Response:
    """【正式入口】按配置生成并下载 PDF 报告。需 reports:export 权限。

    时间口径为本地日期语义（不做 UTC 转换）；publish_time 缺失时回退 created_at。
    当前仅支持 delivery=download，邮件投递将在后续阶段提供。
    """
    if payload.delivery != "download":
        raise HTTPException(status_code=400, detail="当前仅支持 delivery=download，邮件投递尚未开放")

    if payload.range_type == "custom":
        if not (payload.start_date and payload.end_date):
            raise HTTPException(status_code=400, detail="自定义区间需同时提供 start_date 与 end_date")
        start_date, end_date = payload.start_date, payload.end_date
    else:
        start_date = end_date = None

    module_keys: List[str] = []
    module_params: Dict[str, Dict[str, Any]] = {}
    for item in payload.modules:
        if isinstance(item, str):
            module_keys.append(item)
        else:
            module_keys.append(item.key)
            if item.params:
                module_params[item.key] = dict(item.params)

    return _do_export(
        request=request, db=db, user=_u,
        report_name=payload.name,
        time_field=payload.time_field,
        start_date=start_date, end_date=end_date,
        days=payload.range_days,
        module_keys=module_keys,
        module_params=module_params,
        config_snapshot=payload.model_dump(),
        entry="export",
    )


@reports_router.post("/generate", deprecated=True)
def report_generate(
    request: Request,
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    _u: User = Depends(require_permission("reports:export")),
) -> Response:
    """【Deprecated】Phase Report-1.1 导出入口，保留兼容；请改用 POST /reports/export。

    本接口现为薄适配层，内部调用与 /export 完全一致的模块化生成逻辑。
    """
    return _do_export(
        request=request, db=db, user=_u,
        report_name=payload.report_name,
        time_field=payload.time_field,
        start_date=payload.start_date, end_date=payload.end_date,
        days=payload.days,
        module_keys=payload.module_keys,
        module_params={},
        config_snapshot=payload.model_dump(),
        entry="generate(deprecated)",
    )


# ---------------------------------------------------------------------------
# Phase Report-4-A：报告模板（最小可用：保存/加载）
# 设计：模板仅描述「怎么生成」，不扩展 /export 端点；
#       GET 列表用 reports:export（与导出同源权限），写操作用 reports:manage。
# ---------------------------------------------------------------------------
@reports_router.get("/templates", response_model=List[ReportTemplateResponse])
def report_templates_list(
    _u: User = Depends(require_permission("reports:export")),
    db: Session = Depends(get_db),
) -> List[ReportTemplateResponse]:
    """加载当前用户可访问的模板：自己创建的 + 公共模板。"""
    return list_templates(db, _u)


@reports_router.post("/templates", response_model=ReportTemplateResponse, status_code=201)
def report_template_create(
    payload: ReportTemplateCreate,
    _u: User = Depends(require_permission("reports:manage")),
    db: Session = Depends(get_db),
) -> ReportTemplateResponse:
    """保存当前导出配置为模板（需 reports:manage）。"""
    return create_template(db, _u, payload)


@reports_router.put("/templates/{template_id}", response_model=ReportTemplateResponse)
def report_template_update(
    template_id: int,
    payload: ReportTemplateUpdate,
    _u: User = Depends(require_permission("reports:manage")),
    db: Session = Depends(get_db),
) -> ReportTemplateResponse:
    """更新模板（需 reports:manage；仅 owner 或 admin 可操作，否则 403）。"""
    return update_template(db, _u, template_id, payload)


@reports_router.delete("/templates/{template_id}", status_code=204, response_model=None)
def report_template_delete(
    template_id: int,
    _u: User = Depends(require_permission("reports:manage")),
    db: Session = Depends(get_db),
) -> None:
    """删除模板（需 reports:manage；仅 owner 或 admin 可操作，否则 403）。"""
    delete_template(db, _u, template_id)
