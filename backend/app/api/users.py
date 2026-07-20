"""P2 RBAC user management API."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.permissions import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.models.role import Role
from app.schemas.user import (
    RoleOut,
    UserCreate,
    UserOut,
    UserUpdate,
    UserPasswordReset,
)

users_router = APIRouter(tags=["users"], dependencies=[Depends(get_current_user)])


@users_router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    total = db.query(User).count()
    rows = db.query(User).order_by(User.id).offset((page - 1) * size).limit(size).all()
    return {
        "items": [UserOut.model_validate(u) for u in rows],
        "total": total,
        "page": page,
        "size": size,
    }


@users_router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@users_router.put("/users/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@users_router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


@users_router.get("/users/roles")
def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)
    roles = db.query(Role).all()
    return [RoleOut.model_validate(r) for r in roles]
