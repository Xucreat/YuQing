"""用户相关 Pydantic 模型（Phase 2A：认证）。

禁止直接返回 ORM 对象，统一经 Pydantic 序列化。
"""
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    """登录请求体（JSON）。"""

    username: str
    password: str


class Token(BaseModel):
    """登录成功返回的 JWT。"""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """对外暴露的用户信息（不含 password_hash）。"""

    id: int
    username: str
    role: str

    model_config = ConfigDict(from_attributes=True)
