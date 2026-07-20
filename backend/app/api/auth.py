"""认证路由（Phase 2A）：JWT 登录。

POST /login  ->  { access_token, token_type, role, permissions }
使用已有 app/core/security.py 的 bcrypt 校验 + JWT 签发。仅单 admin 概念已被
P2 RBAC 取代：登录时根据角色计算权限列表返回给前端，供前端按角色控制 UI。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from datetime import datetime, timezone
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.user import LoginRequest, Token

auth_router = APIRouter(tags=["auth"])


def _role_permissions(db: Session, user: User) -> list[str]:
    """返回该用户拥有的权限列表（admin 固定为 ['*']）。"""
    if user.role == "admin":
        return ["*"]
    role = db.scalar(select(Role).where(Role.name == user.role))
    if not role:
        return []
    perms = role.permissions
    return perms if isinstance(perms, list) else []


@auth_router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """校验用户名/密码，成功签发 JWT（含 role 声明）并返回角色与权限。"""
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    permissions = _role_permissions(db, user)
    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "role_name": user.role},
    )
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        permissions=permissions,
    )
