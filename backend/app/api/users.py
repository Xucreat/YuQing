"""RBAC 用户/角色/权限/审计 API（Phase RBAC-1）。

权限边界（后端为真正安全边界）：
  - 用户管理：users:read / users:write / users:activate
  - 角色管理：roles:read / roles:write / roles:delete
  - 权限目录：permissions:read
  - 审计日志：login_logs:read / audit_logs:read
超级管理员（is_superuser 或 role=='admin'）绕过上述检查。
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import (
    get_user_permissions,
    is_superuser_user,
    require_permission,
)
from app.core.security import hash_password
from app.db.session import get_db
from app.models.audit import LoginLog, OperationLog
from app.models.permission import Permission, user_roles
from app.models.role import Role
from app.models.user import User
from app.schemas.user import (
    AdminPasswordReset,
    LoginLogOut,
    OperationLogOut,
    PermissionOut,
    RoleCreate,
    RoleMinimal,
    RoleOut,
    RoleUpdate,
    UserCreate,
    UserDetailOut,
    UserOut,
    UserUpdate,
)
from app.services.audit_service import log_operation

users_router = APIRouter(tags=["users"], dependencies=[Depends(get_current_user)])


# ---------------- 辅助 ----------------
def _superuser_count(db: Session) -> int:
    return db.query(User).filter(
        (User.is_superuser == True) | (User.role == "admin")
    ).count()


def _active_superuser_count(db: Session) -> int:
    return db.query(User).filter(
        ((User.is_superuser == True) | (User.role == "admin")) & (User.is_active == True)
    ).count()


def _role_user_count(db: Session, role: Role) -> int:
    primary = db.query(User).filter(User.role == role.name).count()
    extra = db.query(func.count()).select_from(user_roles).filter(
        user_roles.c.role_id == role.id
    ).scalar() or 0
    return int(primary) + int(extra)


def _serialize_user(user: User, db: Session) -> UserOut:
    data = UserOut.model_validate(user)
    primary = db.scalar(select(Role).where(Role.name == user.role))
    role_list = []
    if primary:
        role_list.append(primary)
    role_list.extend(user.roles)
    data.roles = [RoleMinimal.model_validate(r) for r in role_list]
    data.permissions = get_user_permissions(user, db)
    return data


def _serialize_role(role: Role, db: Session) -> RoleOut:
    data = RoleOut.model_validate(role)
    data.permissions = [p.code for p in role.permissions]
    data.user_count = _role_user_count(db, role)
    return data


def _resolve_perms(db: Session, codes: list[str]) -> list[Permission]:
    """把权限 code 列表解析为 Permission 对象（忽略不存在的 code）。"""
    if not codes:
        return []
    return list(
        db.scalars(select(Permission).where(Permission.code.in_(codes))).all()
    )


# ================= 用户管理 =================
@users_router.get("/users", response_model=dict)
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    search: str | None = None,
    is_active: bool | None = None,
    role: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
):
    q = select(User)
    if search:
        q = q.where(User.username.ilike(f"%{search}%"))
    if is_active is not None:
        q = q.where(User.is_active == is_active)
    if role:
        q = q.where(User.role == role)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(User.id).offset((page - 1) * size).limit(size)
    ).all()
    return {
        "items": [_serialize_user(u, db).model_dump(mode="json") for u in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@users_router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:write")),
):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=400, detail="Username already exists")
    if not db.scalar(select(Role).where(Role.name == body.role)):
        raise HTTPException(status_code=400, detail=f"Role not found: {body.role}")
    extra_roles = []
    if body.roles:
        extra_roles = db.scalars(select(Role).where(Role.id.in_(body.roles))).all()
        if len(extra_roles) != len(set(body.roles)):
            raise HTTPException(status_code=400, detail="Some additional role ids are invalid")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        email=body.email,
        role=body.role,
        is_active=body.is_active,
        is_superuser=(body.role == "admin"),
    )
    user.roles = extra_roles
    db.add(user)
    db.flush()
    log_operation(
        db, action="CREATE", operator=current_user, request=request,
        resource_type="user", resource_id=str(user.id),
        target_user_id=user.id,
        details={"username": user.username, "role": user.role,
                  "extra_roles": [r.name for r in extra_roles], "is_active": user.is_active},
    )
    db.commit()
    db.refresh(user)
    return _serialize_user(user, db)


@users_router.get("/users/{user_id}", response_model=UserDetailOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    data = _serialize_user(user, db)
    detail = UserDetailOut(**data.model_dump(mode="json"))
    detail.login_log_count = db.query(LoginLog).filter(
        LoginLog.user_id == user.id
    ).count()
    detail.operation_log_count = db.query(OperationLog).filter(
        OperationLog.target_user_id == user.id
    ).count()
    return detail


@users_router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:write")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    was_super = is_superuser_user(user)
    new_role = body.role if body.role is not None else user.role
    new_is_super = body.is_superuser if body.is_superuser is not None else user.is_superuser
    will_be_super = new_is_super or (new_role == "admin")
    new_active = body.is_active if body.is_active is not None else user.is_active

    # 最后超级管理员保护
    if was_super and not will_be_super and _superuser_count(db) <= 1:
        raise HTTPException(status_code=403, detail="Cannot remove the last superuser")
    if was_super and new_active is False and _active_superuser_count(db) <= 1:
        raise HTTPException(status_code=403, detail="Cannot disable the last superuser")

    if body.role is not None:
        if not db.scalar(select(Role).where(Role.name == body.role)):
            raise HTTPException(status_code=400, detail=f"Role not found: {body.role}")
        user.role = body.role
        user.is_superuser = (body.role == "admin") or (body.is_superuser is True)
    if body.is_superuser is not None and body.role is None:
        user.is_superuser = body.is_superuser
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.roles is not None:
        extra = db.scalars(select(Role).where(Role.id.in_(body.roles))).all()
        if len(extra) != len(set(body.roles)):
            raise HTTPException(status_code=400, detail="Some additional role ids are invalid")
        user.roles = extra
    user.updated_at = datetime.now(timezone.utc)

    log_operation(
        db, action="UPDATE", operator=current_user, request=request,
        resource_type="user", resource_id=str(user.id), target_user_id=user.id,
        details={"changes": body.model_dump(exclude_unset=True, mode="json")},
    )
    db.commit()
    db.refresh(user)
    return _serialize_user(user, db)


@users_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:write")),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if is_superuser_user(user) and _superuser_count(db) <= 1:
        raise HTTPException(status_code=403, detail="Cannot delete the last superuser")

    uname = user.username
    db.delete(user)
    log_operation(
        db, action="DELETE", operator=current_user, request=request,
        resource_type="user", resource_id=str(user_id), target_user_id=user_id,
        details={"username": uname},
    )
    db.commit()


@users_router.post("/users/{user_id}/reset-password", response_model=UserOut)
def reset_password(
    user_id: int,
    body: AdminPasswordReset,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:write")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if len(body.new_password or "") < 6:
        raise HTTPException(status_code=400, detail="Password too short (>=6)")
    user.password_hash = hash_password(body.new_password)
    user.updated_at = datetime.now(timezone.utc)
    log_operation(
        db, action="PASSWORD_RESET", operator=current_user, request=request,
        resource_type="user", resource_id=str(user.id), target_user_id=user.id,
        details={"username": user.username},
    )
    db.commit()
    db.refresh(user)
    return _serialize_user(user, db)


@users_router.post("/users/{user_id}/activate", response_model=UserOut)
def activate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:activate")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    user.updated_at = datetime.now(timezone.utc)
    log_operation(db, action="ENABLE", operator=current_user, request=request,
                  resource_type="user", resource_id=str(user.id), target_user_id=user.id)
    db.commit()
    db.refresh(user)
    return _serialize_user(user, db)


@users_router.post("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:activate")),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if is_superuser_user(user) and _active_superuser_count(db) <= 1:
        raise HTTPException(status_code=403, detail="Cannot disable the last superuser")
    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    log_operation(db, action="DISABLE", operator=current_user, request=request,
                  resource_type="user", resource_id=str(user.id), target_user_id=user.id)
    db.commit()
    db.refresh(user)
    return _serialize_user(user, db)


# ================= 角色管理 =================
@users_router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    roles = db.scalars(select(Role).order_by(Role.id)).all()
    return [_serialize_role(r, db) for r in roles]


@users_router.get("/roles/{role_id}", response_model=RoleOut)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return _serialize_role(role, db)


@users_router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    body: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:write")),
):
    if db.scalar(select(Role).where(Role.name == body.name)):
        raise HTTPException(status_code=400, detail="Role name already exists")
    if db.scalar(select(Role).where(Role.code == body.code)):
        raise HTTPException(status_code=400, detail="Role code already exists")
    role = Role(
        name=body.name,
        code=body.code,
        display_name=body.display_name,
        description=body.description,
        is_system=False,
        is_enabled=body.is_enabled,
    )
    role.permissions = _resolve_perms(db, body.permissions)
    db.add(role)
    db.flush()
    log_operation(db, action="ROLE_CREATE", operator=current_user, request=request,
                  resource_type="role", resource_id=str(role.id),
                  details={"name": role.name, "code": role.code,
                          "permissions": body.permissions})
    db.commit()
    db.refresh(role)
    return _serialize_role(role, db)


@users_router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: int,
    body: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:write")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if body.display_name is not None:
        role.display_name = body.display_name
    if body.description is not None:
        role.description = body.description
    if body.is_enabled is not None:
        if role.is_system and body.is_enabled is False:
            raise HTTPException(status_code=403, detail="Cannot disable a system role")
        role.is_enabled = body.is_enabled
    if body.permissions is not None:
        role.permissions = _resolve_perms(db, body.permissions)
    role.updated_at = datetime.now(timezone.utc)
    log_operation(db, action="ROLE_UPDATE", operator=current_user, request=request,
                  resource_type="role", resource_id=str(role.id),
                  details={"changes": body.model_dump(exclude_unset=True, mode="json")})
    db.commit()
    db.refresh(role)
    return _serialize_role(role, db)


@users_router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("roles:delete")),
):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete a system role")
    if _role_user_count(db, role) > 0:
        raise HTTPException(
            status_code=400,
            detail="Role is still assigned to users; reassign them first",
        )
    db.delete(role)
    log_operation(db, action="ROLE_DELETE", operator=current_user, request=request,
                  resource_type="role", resource_id=str(role_id),
                  details={"name": role.name})
    db.commit()


# ================= 权限目录 =================
@users_router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("permissions:read")),
):
    return list(db.scalars(select(Permission).order_by(Permission.group, Permission.code)).all())


# ================= 审计日志 =================
@users_router.get("/login-logs", response_model=dict)
def list_login_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    username: str | None = None,
    status: str | None = None,
    ip: str | None = None,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("login_logs:read")),
):
    q = select(LoginLog)
    if username:
        q = q.where(LoginLog.username.ilike(f"%{username}%"))
    if status:
        q = q.where(LoginLog.status == status)
    if ip:
        q = q.where(LoginLog.ip_address.ilike(f"%{ip}%"))
    if start:
        q = q.where(LoginLog.login_at >= start)
    if end:
        q = q.where(LoginLog.login_at <= end)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(LoginLog.login_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return {
        "items": [LoginLogOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@users_router.get("/operation-logs", response_model=dict)
def list_operation_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    action: str | None = None,
    operator: str | None = None,
    target_user_id: int | None = None,
    result: str | None = None,
    start: str | None = None,
    end: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit_logs:read")),
):
    q = select(OperationLog)
    if action:
        q = q.where(OperationLog.action == action)
    if operator:
        q = q.where(OperationLog.operator_username_snapshot.ilike(f"%{operator}%"))
    if target_user_id is not None:
        q = q.where(OperationLog.target_user_id == target_user_id)
    if result:
        q = q.where(OperationLog.result == result)
    if start:
        q = q.where(OperationLog.created_at >= start)
    if end:
        q = q.where(OperationLog.created_at <= end)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(OperationLog.created_at.desc()).offset((page - 1) * size).limit(size)
    ).all()
    return {
        "items": [OperationLogOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total,
        "page": page,
        "size": size,
    }
