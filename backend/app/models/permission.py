"""RBAC 权限目录与关联表（Phase RBAC-1）。

- Permission：权限目录（code 唯一，形如 ``resource:action``），是所有权限的「定义源」。
- role_permissions / user_roles：多对多关联表，构成 User → Role → Permission 链路。
- 权限判定的权威来源是 ``role_permissions``（替代旧的 Role.permissions JSONB）。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# 角色 → 权限（多对多）。删除角色或权限时级联清理，不产生孤儿。
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
)


# 用户 → 角色（多对多，附加角色）。保留 User.role 主角色，user_roles 提供「一个或多个角色」。
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    UniqueConstraint("user_id", "role_id", name="uq_user_role"),
)


class Permission(Base):
    """权限目录条目。

    code 采用 ``resource:action`` 形式（如 ``keywords:write``），与历史权限编码完全一致，
    保证 require_permission("keywords:write") 等行为不回归。
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(255), default="")
    group: Mapped[str] = mapped_column(String(32), default="其他")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:
        return f"<Permission code={self.code!r}>"
