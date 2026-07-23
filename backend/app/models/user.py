from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # 主角色（与 roles.name 字符串匹配）。保留以实现最小兼容；
    # 附加角色通过 user_roles 多对多提供，构成「一个或多个角色」。
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="analyst")
    is_active: Mapped[bool] = mapped_column(default=True)
    # 超级管理员：拥有全部权限，且受「最后超级管理员」保护。
    # 与 role == "admin" 等价视为超级用户（向后兼容历史 admin 角色）。
    is_superuser: Mapped[bool] = mapped_column(default=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 附加角色（多对多）。主角色仍是 self.role。
    roles: Mapped[list["Role"]] = relationship(  # noqa: F821
        "Role", secondary="user_roles", backref="users"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
