"""审计日志服务（Phase RBAC-1）。

集中记录：
  - 登录日志：成功/失败/登出
  - 操作审计：关键写操作（谁/何时/对什么/做了什么/结果）

日志记录原则：回答「谁、对什么、做了什么、结果如何」，不依赖路径字符串。
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Optional

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


@contextmanager
def audit_write(
    db: Session,
    *,
    action: str,
    operator: Optional[User],
    request,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
):
    """Phase 6 P1-4：包装一次关键写操作审计。

    - 成功：业务提交后记录 result=success 并再次提交审计（与业务同会话，保证不丢审计）。
    - 失败：回滚业务、记录 result=failed（含错误摘要），再提交审计，随后原样抛出，
      确保「业务失败不记录 success」「业务成功不丢失审计」。
    - 审计失败（极罕见 DB 异常）被静默吞掉，绝不掩盖原始业务异常或破坏操作结果。

    用法（在 with 块内完成业务变更并 commit，并设置 ctx["resource_id"]）：：

        with audit_write(db, action="DATA_SOURCE_CREATE", operator=current_user,
                         request=request, resource_type="data_source", details={...}) as ctx:
            ds = DataSource(...)
            db.add(ds)
            db.commit()
            ctx["resource_id"] = str(ds.id)
    """
    # resource_id 可在调用时直接给定（UPDATE/DELETE 的主键来自路径参数，提前已知），
    # 也可对 CREATE 等场景在 with 块内提交后通过 ctx["resource_id"] 回填。
    ctx: Dict[str, Optional[str]] = {
        "resource_id": str(resource_id) if resource_id is not None else None
    }
    try:
        yield ctx
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            log_operation(
                db,
                action=action,
                operator=operator,
                request=request,
                resource_type=resource_type,
                resource_id=ctx.get("resource_id"),
                result="failed",
                error_message=str(exc)[:1000],
                details=details,
            )
            db.commit()
        except Exception:
            pass  # 审计失败不应掩盖原始错误
        raise
    else:
        try:
            log_operation(
                db,
                action=action,
                operator=operator,
                request=request,
                resource_type=resource_type,
                resource_id=ctx.get("resource_id"),
                result="success",
                details=details,
            )
            db.commit()
        except Exception:
            pass  # 审计失败不应破坏业务结果
