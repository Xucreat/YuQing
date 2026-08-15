"""D3 — RBAC Enforcement 收口、Bocha 细粒度授权、*:read 一致化、system role 保护。

本迁移只做「权限目录 + 角色权限分配」数据治理，不修改任何 schema、
不修改 Enforcement 实现（require_permission / require_admin / expand_permissions
/ COMPOSITE_PERMISSIONS 均保持不变），也不触碰 Capability / 前端。

新增权限（D3 真正新增）：
  - bocha:read      查看 / 复核 Bocha 线索（搜索会话、线索列表、确认 / 拒绝）
  - bocha:promote   将 Bocha 线索提升为舆情（创建 Opinion，高危，仅 system_admin）

既有读权限（确保存在，不删除）：
  - opinions:read / events:read / alerts:read / propagation:read
    此前 domestic GET 端点仅依赖 router 级 get_current_user（任意已登录用户可读），
    未做角色级 require_permission 校验。D3 在端点补 require_permission("<res>:read")，
    并把这些读权限授予需要读取的 system_admin / operator（其有效读能力此前已通过
    get_current_user 存在，本迁移仅将其显式化，不扩大任何低权限角色）。

角色绑定（基于 D1/D2 已建立角色；analyst / viewer 的读权限保持不变）：
  - system_admin: ai:search, opinions:read, events:read, alerts:read, propagation:read,
                  bocha:read, bocha:promote
  - operator:     opinions:read, events:read, alerts:read, propagation:read
  - analyst:      bocha:read   （可搜索 / 复核线索，但不可 promote）
  - viewer:       无变更（已持 4 个读权限）

幂等：重复执行不会重复插入权限或角色绑定。
可降级：仅移除本迁移新增 / 关联的 role_permissions，并删除仅由本迁移引入的
bocha:read / bocha:promote（若已无其他角色引用）。
"""
from __future__ import annotations

from typing import Sequence, Union

from sqlalchemy import column, select, table
from sqlalchemy.orm import Session

from alembic import op


revision: str = "rbac_d3_enforcement_v2"
down_revision: Union[str, Sequence[str], None] = "rbac_d2_enforcement_v1"
branch_labels = None
depends_on = None


# (code, name, resource, action, group, description) —— 本迁移真正新增的权限
_NEW_PERMISSIONS = [
    ("bocha:read", "Bocha 线索查看", "bocha", "read", "Bocha",
     "查看 Bocha 搜索会话、线索列表，确认 / 拒绝线索（不含提升为舆情）"),
    ("bocha:promote", "Bocha 线索提升为舆情", "bocha", "promote", "Bocha",
     "将 Bocha 线索提升 / 创建为正式舆情（高危写操作，仅 system_admin）"),
]

# 仅确保存在、不在 downgrade 中删除（属历史既有读权限，非本阶段引入）
_ENSURE_READ_PERMISSIONS = [
    ("opinions:read", "查看舆情", "opinions", "read", "舆情", "查看舆情列表 / 详情"),
    ("events:read", "查看事件", "events", "read", "事件", "查看事件列表 / 详情 / 态势"),
    ("alerts:read", "查看预警", "alerts", "read", "预警", "查看预警规则 / 记录"),
    ("propagation:read", "查看传播", "propagation", "read", "传播", "查看传播事件 / 图谱"),
]

# (role_code, [permission codes])
# 注意：system_admin 必须持有 ai:search，否则 D3 将 search_bocha 的 require_admin
# 改为 require_permission("ai:search") 后，system_admin 会被错误锁死在 Bocha 搜索之外
# （回归）。ai:search 仅代表「搜索/检索」，analyst 等更低角色本就持有，授予 system_admin
# 不构成低权限角色扩张，符合 D3-01「system_admin 可完整操作」要求，亦不违反任何红线
# （红线仅禁止把 ai:search 用于 Bocha promote，以及禁止扩张 analyst/viewer）。
_ROLE_GRANTS = {
    "system_admin": [
        "ai:search",
        "opinions:read", "events:read", "alerts:read", "propagation:read",
        "bocha:read", "bocha:promote",
    ],
    "operator": [
        "opinions:read", "events:read", "alerts:read", "propagation:read",
    ],
    "analyst": [
        "bocha:read",
    ],
}


# role_permissions 关联表（core 表达，避免依赖 ORM 关系加载）
_rp = table("role_permissions", column("role_id"), column("permission_id"))


def _ensure_permissions(session: Session) -> dict[str, int]:
    """插入不存在的权限，返回 code -> id 映射（含已存在的）。"""
    from app.models.permission import Permission

    rows = session.execute(select(Permission.id, Permission.code)).all()
    by_code: dict[str, int] = {code: pid for pid, code in rows}
    for code, name, resource, action, group, description in (
        _NEW_PERMISSIONS + _ENSURE_READ_PERMISSIONS
    ):
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
