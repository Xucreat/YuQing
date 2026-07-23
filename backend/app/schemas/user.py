"""RBAC 相关 Pydantic Schema（Phase RBAC-1）。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------- 认证 ----------------
class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = ""
    permissions: List[str] = []
    # 超级管理员标记：与后端 is_superuser_user（is_superuser OR role=='admin'）保持一致，
    # 供前端 isSuperuser() 判定全权限。仅暴露既有 User.is_superuser，不改变权限模型/库结构。
    is_superuser: bool = False


# ---------------- 权限目录 ----------------
class PermissionOut(BaseModel):
    id: int
    code: str
    name: str
    resource: str
    action: str
    description: str = ""
    group: str = "其他"
    model_config = ConfigDict(from_attributes=True)


# ---------------- 角色 ----------------
class RoleMinimal(BaseModel):
    id: int
    name: str
    display_name: str
    model_config = ConfigDict(from_attributes=True)


class RoleOut(BaseModel):
    id: int
    name: str
    code: str
    display_name: str
    description: Optional[str] = None
    is_system: bool = False
    is_enabled: bool = True
    permissions: List[str] = []  # 权限 code 列表
    user_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @field_validator("permissions", mode="before")
    @classmethod
    def _coerce_permissions(cls, v):
        # Role 的 ORM 关系 permissions 是 Permission 对象列表；
        # model_validate(role) 会直接把对象塞进 List[str] 字段导致校验失败。
        # 这里兼容：若传入的是对象，则提取 code。
        if v and not isinstance(v[0], str) and hasattr(v[0], "code"):
            return [p.code for p in v]
        return v


class RoleCreate(BaseModel):
    code: str
    name: str  # 角色名（唯一，对应 roles.name）
    display_name: str
    description: str = ""
    is_enabled: bool = True
    permissions: List[str] = []  # 权限 code 列表


class RoleUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None
    permissions: Optional[List[str]] = None  # 全量替换该角色权限


# ---------------- 用户 ----------------
class UserOut(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    roles: List[RoleMinimal] = []
    is_active: bool
    is_superuser: bool
    last_login: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    permissions: List[str] = []  # 最终权限（多角色合并；超管为 ["*"]）
    model_config = ConfigDict(from_attributes=True)


class UserDetailOut(UserOut):
    login_log_count: int = 0
    operation_log_count: int = 0


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: str = "analyst"  # 主角色（角色名）
    roles: List[int] = []  # 附加角色 id
    is_active: bool = True


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None  # 可选改密
    role: Optional[str] = None  # 主角色（角色名）
    roles: Optional[List[int]] = None  # 附加角色 id 全量替换
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None  # 提升/取消超级管理员（受最后超管保护）


class AdminPasswordReset(BaseModel):
    new_password: str


class UserPasswordReset(BaseModel):
    old_password: str
    new_password: str


# ---------------- 审计日志 ----------------
class LoginLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: str
    login_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    status: str
    failure_reason: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class OperationLogOut(BaseModel):
    id: int
    operator_user_id: Optional[int] = None
    operator_username_snapshot: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    target_user_id: Optional[int] = None
    request_method: Optional[str] = None
    request_path: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    result: str
    error_message: Optional[str] = None
    details_json: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
