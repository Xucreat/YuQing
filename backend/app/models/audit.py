"""审计日志模型（Phase RBAC-1）。

- LoginLog：登录成功/失败/登出记录。user_id 允许为空（用户名不存在的失败登录也要记）。
- OperationLog：关键业务操作审计（谁/何时/对什么/做了什么/结果）。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginLog(Base):
    __tablename__ = "user_login_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 允许为空：用户名不存在的登录失败也必须记录。
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    login_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # success | failed | logout
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<LoginLog id={self.id} user={self.username!r} status={self.status!r}>"


class OperationLog(Base):
    __tablename__ = "user_operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operator_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    # 操作者用户名快照：改名/删除后历史日志仍可读。
    operator_username_snapshot: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    # CREATE | UPDATE | DELETE | ENABLE | DISABLE | LOGIN | LOGOUT
    # | PASSWORD_RESET | ROLE_ASSIGN | PERMISSION_CHANGE ...
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    request_method: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    request_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # success | failed
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<OperationLog id={self.id} action={self.action!r} result={self.result!r}>"
