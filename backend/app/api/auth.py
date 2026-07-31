"""认证路由（Phase RBAC-1）：JWT 登录 + 登出 + 登录日志。

POST /login   -> { access_token, token_type, role, permissions }
POST /logout  -> { ok: true }  （记录登出日志）
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import client_meta, get_current_user
from app.core.permissions import get_user_permissions
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.user import LoginRequest, MeResponse, Token
from app.services.audit_service import log_login

auth_router = APIRouter(tags=["auth"])


def _user_permissions(db: Session, user: User) -> list[str]:
    """返回该用户拥有的权限列表（超级管理员为 ['*']）。"""
    return get_user_permissions(user, db)


@auth_router.post("/login", response_model=Token)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> Token:
    """校验用户名/密码，成功签发 JWT 并记登录日志；失败记审计日志。"""
    ip, ua = client_meta(request)
    user = db.scalar(select(User).where(User.username == payload.username))

    if user is None:
        log_login(db, username=payload.username, status="failed",
                  ip_address=ip, user_agent=ua, failure_reason="user_not_found")
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not verify_password(payload.password, user.password_hash):
        log_login(db, username=payload.username, user_id=user.id,
                  status="failed", ip_address=ip, user_agent=ua,
                  failure_reason="invalid_password")
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        log_login(db, username=payload.username, user_id=user.id,
                  status="failed", ip_address=ip, user_agent=ua,
                  failure_reason="disabled")
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )

    user.last_login = datetime.now(timezone.utc)
    user.last_login_ip = ip
    db.add(user)

    permissions = _user_permissions(db, user)
    token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "role_name": user.role},
    )
    log_login(db, username=user.username, user_id=user.id,
              status="success", ip_address=ip, user_agent=ua)
    db.commit()
    return Token(
        access_token=token,
        token_type="bearer",
        role=user.role,
        permissions=permissions,
        is_superuser=bool(user.is_superuser),
    )


@auth_router.get("/auth/me", response_model=MeResponse)
def read_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MeResponse:
    """返回当前登录用户的身份、角色与**实时**权限列表。

    动机（权限生效机制）：登录时下发的 permissions 会被前端缓存在 localStorage，
    管理员随后修改角色权限不会自动同步。前端在应用启动时调用本接口重新拉取，
    即可做到「刷新页面即生效」，而无需重构 JWT、无需引入缓存服务。

    - 仅需登录（Bearer JWT），不额外要求任何权限码，避免权限被改小后自锁。
    - 权限计算完全复用 get_user_permissions()，与 require_permission 判定同源。
    - 只读接口：不写库、不产生审计记录。
    """
    role_names: list[str] = []
    if current_user.role:
        role_names.append(current_user.role)
    for r in current_user.roles:
        if r is not None and r.name not in role_names:
            role_names.append(r.name)

    return MeResponse(
        id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name,
        role=current_user.role or "",
        roles=role_names,
        permissions=_user_permissions(db, current_user),
        is_superuser=bool(current_user.is_superuser),
        is_active=bool(current_user.is_active),
    )


@auth_router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """登出（无状态 JWT 仅前端丢弃；此处记录登出日志用于审计）。"""
    ip, ua = client_meta(request)
    log_login(db, username=current_user.username, user_id=current_user.id,
              status="logout", ip_address=ip, user_agent=ua)
    db.commit()
    return {"ok": True}
