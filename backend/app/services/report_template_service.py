""";报告模板服务（Phase Report-4-A 最小可用模板能力）。

设计要点：
  - 模板 = 一份 ReportExportRequest 配置快照（config_json），零侵入生成链路。
  - 模块 key 必须存在于 MODULE_MAP，未知 key → 400（容错：阻止绑定已失效/不存在的模块）。
  - 鉴权：仅 owner 或 superuser（admin）可编辑/删除（can_edit）。
  - 列表：返回「自己的模板」+「公共模板(is_public=true)」。
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import is_superuser_user
from app.models.report_template import ReportTemplate
from app.models.user import User
from app.schemas.report import (
    ReportTemplateConfig,
    ReportTemplateCreate,
    ReportTemplateResponse,
    ReportTemplateUpdate,
)
from app.services.report_service import MODULE_MAP


def _validate_module_keys(config: ReportTemplateConfig) -> None:
    """校验 config.modules 中每个模块的 key 是否仍存在于注册表。"""
    for item in config.modules:
        key = item if isinstance(item, str) else item.key
        if key not in MODULE_MAP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知报告模块：{key}",
            )


def _assert_name_unique(
    db: Session, user: User, name: str, exclude_id: Optional[int] = None
) -> None:
    """模板名称必须在「本人模板 + 公共模板」可见范围内唯一（大小写/首尾空格不敏感）。

    可见范围与 list_templates 一致（own | public），避免下拉框出现同名两项。
    exclude_id 用于更新场景，跳过自身。
    """
    norm = name.strip().lower()
    stmt = (
        select(ReportTemplate)
        .where(
            (ReportTemplate.owner_id == user.id)
            | (ReportTemplate.is_public == True)  # noqa: E712
        )
        .where(func.lower(func.trim(ReportTemplate.name)) == norm)
    )
    if exclude_id is not None:
        stmt = stmt.where(ReportTemplate.id != exclude_id)
    if db.scalars(stmt).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"模板名称已存在：{name.strip()}",
        )


def can_edit_template(tpl: ReportTemplate, user: User) -> bool:
    """owner 或 superuser(admin) 可编辑/删除。"""
    return tpl.owner_id == user.id or is_superuser_user(user)


def _to_response(tpl: ReportTemplate, user: User) -> ReportTemplateResponse:
    cfg = tpl.config_json or {}
    try:
        config = ReportTemplateConfig(**cfg)
    except Exception:
        # 配置结构异常时回退为空配置，避免整条记录不可读
        config = ReportTemplateConfig()
    return ReportTemplateResponse(
        id=tpl.id,
        name=tpl.name,
        description=tpl.description,
        owner_id=tpl.owner_id,
        config_json=config,
        is_public=bool(tpl.is_public),
        created_at=tpl.created_at.isoformat() if tpl.created_at else "",
        updated_at=tpl.updated_at.isoformat() if tpl.updated_at else "",
        can_edit=can_edit_template(tpl, user),
    )


def create_template(
    db: Session, user: User, payload: ReportTemplateCreate
) -> ReportTemplateResponse:
    _validate_module_keys(payload.config_json)
    _assert_name_unique(db, user, payload.name)
    tpl = ReportTemplate(
        name=payload.name.strip(),
        description=payload.description,
        owner_id=user.id,
        config_json=payload.config_json.model_dump(),
        is_public=bool(payload.is_public),
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return _to_response(tpl, user)


def list_templates(db: Session, user: User) -> List[ReportTemplateResponse]:
    """返回当前用户的模板：自己创建的 + 公共模板。"""
    stmt = select(ReportTemplate).where(
        (ReportTemplate.owner_id == user.id) | (ReportTemplate.is_public == True)  # noqa: E712
    ).order_by(ReportTemplate.is_public, ReportTemplate.name)
    rows = db.scalars(stmt).all()
    return [_to_response(t, user) for t in rows]


def get_template_or_404(db: Session, tpl_id: int) -> ReportTemplate:
    tpl = db.get(ReportTemplate, tpl_id)
    if tpl is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在"
        )
    return tpl


def update_template(
    db: Session, user: User, tpl_id: int, payload: ReportTemplateUpdate
) -> ReportTemplateResponse:
    tpl = get_template_or_404(db, tpl_id)
    if not can_edit_template(tpl, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权修改该模板（仅创建者或管理员可操作）",
        )
    if payload.name is not None:
        new_name = payload.name.strip()
        _assert_name_unique(db, user, new_name, exclude_id=tpl.id)
        tpl.name = new_name
    if payload.description is not None:
        tpl.description = payload.description
    if payload.is_public is not None:
        tpl.is_public = bool(payload.is_public)
    if payload.config_json is not None:
        _validate_module_keys(payload.config_json)
        tpl.config_json = payload.config_json.model_dump()
    db.commit()
    db.refresh(tpl)
    return _to_response(tpl, user)


def delete_template(db: Session, user: User, tpl_id: int) -> None:
    tpl = get_template_or_404(db, tpl_id)
    if not can_edit_template(tpl, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权删除该模板（仅创建者或管理员可操作）",
        )
    db.delete(tpl)
    db.commit()
