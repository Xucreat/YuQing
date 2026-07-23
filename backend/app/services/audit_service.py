"""审计日志服务（Phase RBAC-1）。

集中记录：
  - 登录日志：成功/失败/登出
  - 操作审计：关键写操作（谁/何时/对什么/做了什么/结果）

日志记录原则：回答「谁、对什么、做了什么、结果如何」，不依赖路径字符串。
"""
from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.dependencies import client_meta
from app.models.audit import LoginLog, OperationLog
from app.models.user import User


def log_login(
    db: Session,
    *,
    username: str,
    status: str,  # success | failed | logout
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    failure_reason: Optional[str] = None,
) -> None:
    """记录一条登录日志（用户名不存在时 user_id 传 None）。"""
    db.add(
        LoginLog(
            user_id=user_id,
            username=username,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )
    )


def log_operation(
    db: Session,
    *,
    action: str,
    operator: Optional[User] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    target_user_id: Optional[int] = None,
    request=None,  # fastapi.Request | None
    result: str = "success",
    error_message: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """记录一条操作审计日志。

    operator: 当前操作者 User 对象（取其 id + 用户名快照）。
    request: FastAPI Request，用于提取 method/path/ip/ua。
    details: 任意可 JSON 序列化的业务上下文。
    """
    ip_address = None
    user_agent = None
    method = None
    path = None
    if request is not None:
        ip_address, user_agent = client_meta(request)
        method = request.method
        path = request.url.path

    details_json = None
    if details is not None:
        try:
            details_json = json.dumps(details, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            details_json = None

    db.add(
        OperationLog(
            operator_user_id=operator.id if operator else None,
            operator_username_snapshot=operator.username if operator else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            target_user_id=target_user_id,
            request_method=method,
            request_path=path,
            ip_address=ip_address,
            user_agent=user_agent,
            result=result,
            error_message=error_message,
            details_json=details_json,
        )
    )
