"""RBAC 权限校验（Phase RBAC-1）。

- require_admin: 依赖工厂，仅超级管理员/ admin 角色可通过（用户管理等纯管理员接口）。
- require_permission(perm): 按 User → Role(s) → Permission 链路校验操作权限。
- get_user_permissions(user, db): 计算用户最终权限（多角色合并，超管返回 ["*"]）。

权限判定权威来源是 role_permissions 关联表（替代旧的 Role.permissions JSONB）。
现有权限编码（如 keywords:write）保持不变，require_permission 行为向后兼容。
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role


def is_superuser_user(user: User) -> bool:
    """超级管理员判定：显式 is_superuser 或历史 admin 角色，二者等价。"""
    return bool(user.is_superuser) or user.role == "admin"


# ================= 外网「四类组合权限」-> 旧细粒度权限 展开表 =================
# 设计目标（见需求「六、外网权限简化」）：
#   - 角色配置组合权限（如 foreign:read）后，后端 require_permission(旧细粒度) 仍判定通过；
#   - 超管 * 行为不变；现有细粒度权限码继续有效，互不冲突；
#   - 解析层在 get_user_permissions 中一次性展开，单一事实来源，前端 /me 复用同一结果。
# 注意：每个组合只展开到「当前后端实际 require_permission 检查且属于该业务范围的
#      foreign:* 细粒度码」，避免把事件写入等不相关能力授予数据管理角色。
COMPOSITE_PERMISSIONS: dict[str, list[str]] = {
    "foreign:read": [
        "foreign:opinions:read",
        "foreign:risk:read",
        "foreign:risk:terms:read",
        "foreign:events:read",
        "foreign:events:candidates:read",
        "foreign:alerts:read",
        "foreign:alerts:rules:read",
        "foreign:keywords:read",
        "foreign:sources:read",
    ],
    "foreign:data:manage": [
        "foreign:keywords:read",
        "foreign:keywords:write",
        "foreign:sources:read",
        "foreign:sources:write",
        "foreign:sources:test",
        "foreign:sources:collect",
        "foreign:sources:collect_all",
    ],
    "foreign:analysis": [
        "foreign:risk:read",
        "foreign:events:read",
        "foreign:events:candidates:read",
        "foreign:risk:analyze",
        "foreign:risk:batch",
        "foreign:risk:ai",
        "foreign:ai:analyze",
        "foreign:events:confirm",
        "foreign:events:merge",
        "foreign:events:split",
        "foreign:events:status",
        "foreign:events:rebuild",
        "foreign:events:auto-aggregate",
        "foreign:alerts:evaluate",
        "foreign:alerts:ai-admit",
    ],
    "foreign:alerts:manage": [
        "foreign:alerts:read",
        "foreign:alerts:rules:read",
        "foreign:alerts:rules:write",
        "foreign:alerts:acknowledge",
        "foreign:alerts:resolve",
        "foreign:alerts:suppress",
        "foreign:alerts:enable",
    ],
}


def expand_permissions(codes: list[str]) -> list[str]:
    """将组合权限展开为等价的细粒度权限集合（幂等、可重复调用）。

    仅做集合展开并去重；不依赖数据库，便于单元测试与权限解析层复用。
    """
    expanded: set[str] = set(codes)
    for code in list(expanded):
        subs = COMPOSITE_PERMISSIONS.get(code)
        if subs:
            expanded.update(subs)
    return sorted(expanded)


def get_user_permissions(user: User, db: Session) -> list[str]:
    """返回用户拥有的最终权限码列表。

    - 超级管理员返回 ["*"]（代表全部）。
    - 普通用户：主角色(user.role) + 附加角色(user_roles) 的权限并集。
    """
    if is_superuser_user(user):
        return ["*"]
    codes: set[str] = set()
    primary = db.scalar(select(Role).where(Role.name == user.role))
    roles = [primary] if primary else []
    roles.extend(user.roles)
    for role in roles:
        if role is None or not role.is_enabled:
            continue
        for perm in role.permissions:
            codes.add(perm.code)
    # 组合权限 -> 旧细粒度权限展开（四类组合权限方案）。
    # 展开后 require_permission(细粒度) 与前端 /me 缓存均一致通过。
    return expand_permissions(sorted(codes))


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """仅允许超级管理员（is_superuser 或 admin 角色）；否则 403。"""
    if not is_superuser_user(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return current_user


def require_permission(permission: str):
    """依赖工厂：校验当前用户是否具有指定操作权限。

    用法：
        @router.delete("/{opinion_id}")
        def delete_opinion(
            opinion_id: int,
            _: User = Depends(require_permission("opinions:write")),
            db: Session = Depends(get_db),
        ):
            ...
    """

    def checker(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if is_superuser_user(current_user):
            return current_user
        perms = get_user_permissions(current_user, db)
        if "*" in perms or permission in perms:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    return checker
