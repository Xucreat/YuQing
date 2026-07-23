from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    # 角色编码（唯一），用于稳定引用；系统角色与新角色都应有 code。
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(255), default="")
    # 系统角色受保护：不可删除、不可改名 code、不可停用（可被超管调整权限）。
    is_system: Mapped[bool] = mapped_column(default=False)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # 权限（多对多，通过 role_permissions 关联）。权限判定的权威来源。
    permissions: Mapped[list["Permission"]] = relationship(  # noqa: F821
        "Permission", secondary="role_permissions", backref="roles"
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name!r} code={self.code!r}>"
