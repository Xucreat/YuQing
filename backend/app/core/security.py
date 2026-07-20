"""安全工具：bcrypt 密码哈希 + 简单 JWT。

仅实现基础能力：
  - hash_password / verify_password（bcrypt，禁止明文）
  - create_access_token（仅 sub + exp，无 refresh / RBAC / OAuth）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import jwt
from jose import JWTError

from app.core.config import settings


def decode_access_token(token: str) -> str | int | None:
    """校验 JWT 并返回 sub（用户标识）。

    非法/过期 token 抛出 jose.JWTError，由调用方转成 401。
    """
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    return payload.get("sub")


def hash_password(password: str) -> str:
    """bcrypt 加密明文密码，返回哈希字符串（已 salt）。"""
    pwd_bytes = password.encode("utf-8")
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与存储哈希是否匹配。"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str | int,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """签发 JWT（包含 sub、exp，可附加额外声明如 role）。"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
