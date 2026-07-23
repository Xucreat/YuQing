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
    return sorted(codes)


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
