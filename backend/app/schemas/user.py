"""P2 RBAC user schemas."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str = ""
    permissions: List[str] = []


class RoleOut(BaseModel):
    id: int
    name: str
    display_name: str
    permissions: List[str] = []
    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "analyst"


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserPasswordReset(BaseModel):
    old_password: str
    new_password: str
