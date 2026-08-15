"""D2 — RBAC Enforcement 重构：新增缺失权限并绑定角色。

本迁移只做「权限目录 + 角色权限分配」数据治理，不修改任何 schema、
不修改 Enforcement 实现（require_permission / require_admin / expand_permissions
/ COMPOSITE_PERMISSIONS 均保持不变），也不触碰 Capability / 前端。

新增权限：
  - opinions:delete   删除舆情（高危，仅 system_admin）
  - events:delete     删除事件（高危，仅 system_admin；原 events:write 仅保留编辑/合并等）
  - collector:run     手动触发采集（system_admin + operator）

角色绑定（基于 D1 已建立角色）：
  - system_admin: opinions:delete, events:delete, collector:run
  - operator:      collector:run

幂等：重复执行不会重复插入权限或角色绑定。
"""
from __future__ import annotations

from typing import Sequence, Union

from sqlalchemy import column, select, table
from sqlalchemy.orm import Session

from alembic import op


revision: str = "rbac_d2_enforcement_v1"
down_revision: Union[str, Sequence[str], None] = "current_risk_adoption_v1"
branch_labels = None
depends_on = None


# (code, name, resource, action, group, description)
_NEW_PERMISSIONS = [
    ("opinions:delete", "删除舆情", "opinions", "delete", "舆情", "删除单条/批量舆情（高危）"),
    ("events:delete", "删除事件", "events", "delete", "事件", "删除事件及其关联记录（高危）"),
    ("collector:run", "触发采集", "collector", "run", "采集", "手动触发采集任务（系统基础设施操作）"),
]

# (role_code, [permission codes])
_ROLE_GRANTS = {
    "system_admin": ["opinions:delete", "events:delete", "collector:run"],
    "operator": ["collector:run"],
}


# role_permissions 关联表（core 表达，避免依赖 ORM 关系加载）
_rp = table("role_permissions", column("role_id"), column("permission_id"))


def _ensure_permissions(session: Session) -> dict[str, int]:
    """插入不存在的权限，返回 code -> id 映射（含已存在的）。"""
    from app.models.permission import Permission

    rows = session.execute(select(Permission.id, Permission.code)).all()
    by_code: dict[str, int] = {code: pid for pid, code in rows}
    for code, name, resource, action, group, description in _NEW_PERMISSIONS:
        if code not in by_code:
            perm = Permission(
                code=code,
                name=name,
                resource=resource,
                action=action,
                group=group,
                description=description,
            )
            session.add(perm)
            session.flush()
            by_code[code] = perm.id
    return by_code


def _grant_roles(session: Session, perm_ids: dict[str, int]) -> None:
    from app.models.role import Role

    role_rows = session.execute(select(Role.id, Role.code)).all()
    role_by_code = {code: rid for rid, code in role_rows}
    for role_code, codes in _ROLE_GRANTS.items():
        role_id = role_by_code.get(role_code)
        if role_id is None:
            continue  # 兜底：角色不存在则跳过（D1 应已建立）
        for code in codes:
            perm_id = perm_ids.get(code)
            if perm_id is None:
                continue
            linked = session.execute(
                select(1).where(
                    (_rp.c.role_id == role_id) & (_rp.c.permission_id == perm_id)
                )
            ).first()
            if linked is None:
                session.execute(
                    _rp.insert().values(role_id=role_id, permission_id=perm_id)
                )


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        perm_ids = _ensure_permissions(session)
        _grant_roles(session, perm_ids)
        session.flush()
    except Exception:
        session.rollback()
        raise


def downgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind)
    try:
        from app.models.permission import Permission
        from app.models.role import Role

        role_rows = session.execute(select(Role.id, Role.code)).all()
        role_by_code = {code: rid for rid, code in role_rows}
        perm_rows = session.execute(select(Permission.id, Permission.code)).all()
        perm_by_code = {code: pid for pid, code in perm_rows}

        for role_code, codes in _ROLE_GRANTS.items():
            role_id = role_by_code.get(role_code)
            if role_id is None:
                continue
            for code in codes:
                perm_id = perm_by_code.get(code)
                if perm_id is None:
                    continue
                session.execute(
                    _rp.delete().where(
                        (_rp.c.role_id == role_id) & (_rp.c.permission_id == perm_id)
                    )
                )
        # 仅删除本迁移新增、且不再被任何角色引用的权限
        for code, _n, _r, _a, _g, _d in _NEW_PERMISSIONS:
            perm_id = perm_by_code.get(code)
            if perm_id is None:
                continue
            still_used = session.execute(
                select(1).where(_rp.c.permission_id == perm_id)
            ).first()
            if still_used is None:
                session.execute(
                    Permission.__table__.delete().where(Permission.id == perm_id)
                )
        session.flush()
    except Exception:
        session.rollback()
        raise
