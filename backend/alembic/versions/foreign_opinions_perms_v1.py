"""Add foreign opinion write/delete permissions and grant to roles."""
from typing import Sequence, Union

from sqlalchemy import column, select, table
from sqlalchemy.orm import Session
from alembic import op


revision: str = "foreign_opinions_perms_v1"
down_revision: Union[str, None] = "foreign_opinions_ops_v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (code, name, resource, action, group, description)
_NEW_PERMISSIONS = [
    ("foreign:opinions:write", "外网舆情情感修改", "foreign", "opinions:write", "外网舆情",
     "修改外网舆情情感（人工覆盖，管理员与分析员）"),
    ("foreign:opinions:delete", "外网舆情删除", "foreign", "opinions:delete", "外网舆情",
     "删除外网舆情（仅管理员，硬删除并解除预警关联）"),
]

# 管理员类角色持有 write + delete；分析员仅 write。
_ROLE_GRANTS = {
    "admin": ["foreign:opinions:write", "foreign:opinions:delete"],
    "system_admin": ["foreign:opinions:write", "foreign:opinions:delete"],
    "analyst": ["foreign:opinions:write"],
}

_rp = table("role_permissions", column("role_id"), column("permission_id"))


def _ensure_permissions(session: Session) -> dict[str, int]:
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
            continue
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
