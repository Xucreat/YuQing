"""认证路由（Phase 2A）：JWT 登录。

POST /login  ->  { access_token, token_type }
使用已有 app/core/security.py 的 bcrypt 校验 + JWT 签发。
仅单 admin；无 OAuth / refresh token / RBAC。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import LoginRequest, Token

auth_router = APIRouter(tags=["auth"])


@auth_router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """校验用户名/密码，成功签发简单 JWT（HS256）。"""
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(subject=user.id)
    return Token(access_token=token, token_type="bearer")
