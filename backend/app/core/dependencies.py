"""认证依赖（Phase RBAC-1）。

提供 get_current_user()：
  - 从 Authorization: Bearer <token> 读取 JWT
  - 校验 token（HS256 / secret_key）
  - 查询 User 并返回对象
  - 校验 is_active（停用用户立即 401，旧 JWT 即时失效）
  - 缺失/非法/过期 token 返回 HTTP 401

所有需要保护的 API 使用 Depends(get_current_user)。
无 OAuth / refresh token / 复杂黑名单（最小兼容方案）。
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User

# auto_error=False：缺失 token 时由我们自己返回 401（而非 403）
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """从 Bearer Token 解析当前登录用户。"""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        sub = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if sub is None or not str(sub).isdigit():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, int(sub))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 关键安全边界：停用用户即使持有有效 JWT 也立即拒绝。
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def client_meta(request: Request) -> tuple[str, str]:
    """从请求中提取客户端 IP 与 User-Agent（供审计日志使用）。

    IP 优先取 X-Forwarded-For 首个值（反向代理场景），回退到直连地址。
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client is not None:
        ip = request.client.host
    else:
        ip = ""
    ua = request.headers.get("user-agent", "") or ""
    return ip, ua
