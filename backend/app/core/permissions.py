"""P2 RBAC 权限校验。

- require_admin: 依赖工厂，仅 admin 角色可通过（用于用户管理等纯管理员接口）。
- require_permission(perm): 依赖工厂，按角色查 roles 表校验某项操作权限；
  admin 始终放行（"*"）。用于在各写操作上做操作级 RBAC。
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """仅允许 admin 角色；否则 403。"""
    if current_user.role != "admin":
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
        if current_user.role == "admin":
            return current_user
        role = db.query(Role).filter(Role.name == current_user.role).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No role assigned")
        perms = role.permissions if isinstance(role.permissions, list) else []
        if "*" not in perms and permission not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return current_user

    return checker
