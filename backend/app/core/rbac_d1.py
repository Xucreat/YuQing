"""Phase Security-RBAC-Redesign-D1 —— 权限目录与角色分配治理（数据层）。

本模块只做「Role -> Permission -> role_permissions」的数据层治理，
**不触碰任何 Enforcement 逻辑**（不修改 require_permission / require_admin /
expand_permissions / COMPOSITE_PERMISSIONS，也不实现 Capability）。

被 D1 Alembic 迁移与 D1 测试共同引用，保证两者逻辑一致、可幂等重跑。

治理内容：
1. 新增正式角色 system_admin / operator（is_system=true, 不持 *）。
2. 修复 foreign:* 组合权限无人持有：
   - foreign:read            -> analyst
   - foreign:data:manage     -> operator + system_admin
   （foreign:analysis / foreign:alerts:manage 因展开含高危 full-confirm 且 scope
     不明确，本阶段 BLOCKED，留待 D2/D3 能力模型拆分，不在此赋值。）
3. 补齐 analyst 业务权限缺口：
   - 新增 keywords:write, foreign:ai:review:read, foreign:ai:batch:read,
     foreign:ai:batch:cancel, foreign:read
   - 移除 analyst 不应持有的 permissions:read（系统管理目录）与 sources:write
     （幽灵权限，Enforcement 未引用，归属 system_admin/operator）
4. 清理游离角色 111（无 users.role / user_roles 引用时删除其 role_permissions 与角色）。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.permission import Permission, role_permissions, user_roles
from app.models.user import User

# 游离角色 111 的 name 与 code 均为 '111'
ROLE_111_CODE = "111"

# system_admin 持有的具体叶子（全部可审计，不含 *）
SYSTEM_ADMIN_PERMS = [
    "users:read",
    "users:write",
    "users:activate",
    "roles:read",
    "roles:write",
    "roles:delete",
    "permissions:read",
    "audit_logs:read",
    "login_logs:read",
    "sources:read",
    "sources:write",
    "foreign:sources:read",
    "foreign:sources:write",
    "foreign:sources:test",
    "foreign:data:manage",  # 组合权限：展开为 foreign 数据源/关键词 读写测采集
]

# operator 持有的具体叶子（数据源与采集基础设施，不含业务研判/用户/角色管理）
OPERATOR_PERMS = [
    "keywords:read",
    "keywords:write",
    "sources:read",
    "sources:write",
    "foreign:sources:read",
    "foreign:sources:write",
    "foreign:sources:test",
    "foreign:sources:collect",
    "foreign:data:manage",  # 组合权限：同上
    "foreign:ai:batch:read",
    "foreign:ai:batch:cancel",
]

# analyst 需补齐的业务权限
ANALYST_ADD_PERMS = [
    "keywords:write",
    "foreign:read",  # 组合权限：展开为全部 foreign 读
    "foreign:ai:review:read",
    "foreign:ai:batch:read",
    "foreign:ai:batch:cancel",
]

# analyst 不应持有的权限（移除）
ANALYST_REMOVE_PERMS = [
    "permissions:read",  # 系统管理目录，归属 system_admin
    "sources:write",  # 幽灵权限（Enforcement 未引用），归属 system_admin/operator
]


def _perm_map(session: Session) -> dict[str, Permission]:
    return {p.code: p for p in session.execute(select(Permission)).scalars().all()}


def ensure_role(
    session: Session,
    name: str,
    code: str,
    display_name: str,
    is_system: bool = True,
    is_enabled: bool = True,
    description: str = "",
) -> Role:
    """幂等创建/修正角色（不删除既有权限，仅确保存在与标志位）。"""
    role = session.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
    if role is None:
        role = Role(
            name=name,
            code=code,
            display_name=display_name,
            is_system=is_system,
            is_enabled=is_enabled,
            description=description,
        )
        session.add(role)
        session.flush()
    else:
        role.is_system = is_system
        role.is_enabled = is_enabled
        if not role.display_name:
            role.display_name = display_name
    return role


def link_perms(session: Session, role: Role, codes: list[str], pmap: dict) -> None:
    """幂等：仅追加缺失的权限，不删除既有权限。缺码即报错（BLOCKED）。"""
    for code in codes:
        perm = pmap.get(code)
        if perm is None:
            raise RuntimeError(f"D1 BLOCKED: permission code 不存在: {code}")
        if perm not in role.permissions:
            role.permissions.append(perm)


def unlink_perms(session: Session, role: Role, codes: list[str], pmap: dict) -> None:
    """移除指定权限（用于 analyst 收紧与 downgrade）。"""
    for code in codes:
        perm = pmap.get(code)
        if perm is not None and perm in role.permissions:
            role.permissions.remove(perm)


def cleanup_role_111(session: Session) -> bool:
    """删除游离角色 111（仅在无 users.role / user_roles 引用时）。

    返回 True 表示已删除；角色不存在返回 False。存在真实引用则抛错（BLOCKED）。
    """
    role = session.execute(
        select(Role).where((Role.name == ROLE_111_CODE) | (Role.code == ROLE_111_CODE))
    ).scalar_one_or_none()
    if role is None:
        return False
    users_ref = session.execute(
        select(User).where(User.role == ROLE_111_CODE)
    ).first()
    ur_ref = session.execute(
        select(user_roles).where(user_roles.c.role_id == role.id)
    ).first()
    if users_ref is not None or ur_ref is not None:
        raise RuntimeError("D1 BLOCKED: role 111 仍被 users/user_roles 引用，禁止删除")
    session.execute(role_permissions.delete().where(role_permissions.c.role_id == role.id))
    session.delete(role)
    session.flush()
    return True


def apply_d1_role_fixes(session: Session) -> None:
    """D1 升级：角色与权限分配治理（幂等、可重复执行）。"""
    pmap = _perm_map(session)

    sa = ensure_role(
        session,
        "system_admin",
        "system_admin",
        "系统管理员",
        is_system=True,
        is_enabled=True,
        description="D1 系统管理角色（非 *，可审计）",
    )
    op = ensure_role(
        session,
        "operator",
        "operator",
        "采集员",
        is_system=True,
        is_enabled=True,
        description="D1 数据源与采集角色",
    )

    link_perms(session, sa, SYSTEM_ADMIN_PERMS, pmap)
    link_perms(session, op, OPERATOR_PERMS, pmap)

    analyst = session.execute(
        select(Role).where(Role.code == "analyst")
    ).scalar_one_or_none()
    if analyst is not None:
        link_perms(session, analyst, ANALYST_ADD_PERMS, pmap)
        unlink_perms(session, analyst, ANALYST_REMOVE_PERMS, pmap)

    cleanup_role_111(session)
    session.flush()


def revert_d1_role_fixes(session: Session) -> None:
    """D1 降级：精确回滚至 BEFORE（仅移除 D1 引入的分配，不动既有授权）。"""
    pmap = _perm_map(session)

    sa = session.execute(
        select(Role).where(Role.code == "system_admin")
    ).scalar_one_or_none()
    if sa is not None:
        unlink_perms(session, sa, SYSTEM_ADMIN_PERMS, pmap)
        session.delete(sa)

    op = session.execute(
        select(Role).where(Role.code == "operator")
    ).scalar_one_or_none()
    if op is not None:
        unlink_perms(session, op, OPERATOR_PERMS, pmap)
        session.delete(op)

    analyst = session.execute(
        select(Role).where(Role.code == "analyst")
    ).scalar_one_or_none()
    if analyst is not None:
        unlink_perms(session, analyst, ANALYST_ADD_PERMS, pmap)
        link_perms(session, analyst, ANALYST_REMOVE_PERMS, pmap)

    # 还原游离角色 111（仅当本迁移创建过；无引用，安全重建）
    existing = session.execute(
        select(Role).where(Role.code == ROLE_111_CODE)
    ).scalar_one_or_none()
    if existing is None:
        r111 = Role(
            name=ROLE_111_CODE,
            code=ROLE_111_CODE,
            display_name=ROLE_111_CODE,
            is_system=False,
            is_enabled=True,
            description="",
        )
        session.add(r111)
        session.flush()
        op_read = pmap.get("opinions:read")
        if op_read is not None:
            r111.permissions.append(op_read)
    session.flush()
