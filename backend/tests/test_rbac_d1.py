"""D1 权限目录与角色分配治理 —— 隔离测试（SQLite in-memory，绝不连接生产库）。

覆盖：
- 4 个 foreign:* 组合权限的 expand_permissions 结果
- system_admin / operator 角色创建与权限矩阵（不含 *、不含越权）
- analyst 权限补齐与收紧
- get_user_permissions 在 D1 后的展开结果
- superuser 仍返回 ["*"]
- 游离角色 111 清理
- revert 精确回滚至 BEFORE
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.role import Role
from app.models.permission import Permission, role_permissions, user_roles
from app.models.user import User
from app.core.rbac_d1 import (
    apply_d1_role_fixes,
    revert_d1_role_fixes,
    SYSTEM_ADMIN_PERMS,
    OPERATOR_PERMS,
    ANALYST_ADD_PERMS,
    ANALYST_REMOVE_PERMS,
)
from app.core.permissions import expand_permissions, get_user_permissions

# viewer 基线权限（用于验证 D1 不扩大 viewer）
VIEWER_BASELINE = [
    "alerts:read",
    "events:read",
    "opinions:read",
    "propagation:read",
    "domestic:ai:review:read",
    "domestic:ai:review:complete",
    "foreign:ai:review:read",
    "foreign:ai:review:complete",
]


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, Role.__table__, Permission.__table__, role_permissions, user_roles],
    )
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()
    codes = (
        set(SYSTEM_ADMIN_PERMS)
        | set(OPERATOR_PERMS)
        | set(ANALYST_ADD_PERMS)
        | set(ANALYST_REMOVE_PERMS)
        | set(VIEWER_BASELINE)
    )
    for i, code in enumerate(sorted(codes), start=1):
        res, _, act = code.partition(":")
        s.add(
            Permission(
                id=i,
                code=code,
                name=code,
                resource=res or code,
                action=act,
                group="test",
            )
        )
    s.add(Role(id=1, name="admin", code="admin", display_name="管理员", is_system=True, is_enabled=True))
    s.add(Role(id=2, name="analyst", code="analyst", display_name="分析员", is_system=True, is_enabled=True))
    s.add(Role(id=3, name="viewer", code="viewer", display_name="只读", is_system=True, is_enabled=True))
    r111 = Role(id=5, name="111", code="111", display_name="111", is_system=False, is_enabled=True)
    s.add(r111)
    op_read = s.execute(select(Permission).where(Permission.code == "opinions:read")).scalar_one()
    r111.permissions.append(op_read)
    # viewer baseline
    viewer = s.execute(select(Role).where(Role.code == "viewer")).scalar_one()
    for code in VIEWER_BASELINE:
        perm = s.execute(select(Permission).where(Permission.code == code)).scalar_one()
        viewer.permissions.append(perm)
    s.commit()
    yield s
    s.close()


# ---------------- expand_permissions 单元测试 ----------------
def test_expand_foreign_read():
    exp = expand_permissions(["foreign:read"])
    for leaf in ["foreign:opinions:read", "foreign:risk:read", "foreign:events:read",
                 "foreign:alerts:read", "foreign:keywords:read", "foreign:sources:read"]:
        assert leaf in exp


def test_expand_foreign_data_manage():
    exp = expand_permissions(["foreign:data:manage"])
    for leaf in ["foreign:sources:write", "foreign:sources:test",
                 "foreign:sources:collect", "foreign:sources:collect_all",
                 "foreign:keywords:write"]:
        assert leaf in exp


def test_expand_foreign_analysis_includes_high_risk_full_confirm():
    exp = expand_permissions(["foreign:analysis"])
    assert "foreign:ai:full-confirm" in exp
    assert "foreign:events:review:confirm" in exp
    assert "foreign:alerts:review:confirm" in exp


def test_expand_foreign_alerts_manage():
    exp = expand_permissions(["foreign:alerts:manage"])
    for leaf in ["foreign:alerts:enable", "foreign:alerts:resolve", "foreign:alerts:suppress"]:
        assert leaf in exp


def test_expand_ai_analyze():
    # D6 consolidated domestic:ai:review:read -> ai:review:read (unified capability)
    exp = expand_permissions(["ai:analyze"])
    assert "domestic:ai:analyze" in exp
    assert "ai:review:read" in exp


# ---------------- D1 角色/权限分配 ----------------
def test_apply_creates_roles_and_cleans_111(session):
    apply_d1_role_fixes(session)
    sa = session.execute(select(Role).where(Role.code == "system_admin")).scalar_one_or_none()
    assert sa is not None and sa.is_system is True and sa.is_enabled is True
    op = session.execute(select(Role).where(Role.code == "operator")).scalar_one_or_none()
    assert op is not None and op.is_system is True and op.is_enabled is True
    r111 = session.execute(select(Role).where(Role.code == "111")).scalar_one_or_none()
    assert r111 is None


def test_system_admin_matrix(session):
    apply_d1_role_fixes(session)
    sa = session.execute(select(Role).where(Role.code == "system_admin")).scalar_one()
    codes = {p.code for p in sa.permissions}
    for p in SYSTEM_ADMIN_PERMS:
        assert p in codes, f"system_admin 缺 {p}"
    assert "*" not in codes
    for forbidden in ("opinions:write", "events:write", "alerts:write",
                      "foreign:analysis", "foreign:alerts:manage", "foreign:ai:review:read",
                      "foreign:ai:batch:read"):
        assert forbidden not in codes, f"system_admin 不应持有 {forbidden}"


def test_operator_matrix(session):
    apply_d1_role_fixes(session)
    op = session.execute(select(Role).where(Role.code == "operator")).scalar_one()
    codes = {p.code for p in op.permissions}
    for p in OPERATOR_PERMS:
        assert p in codes, f"operator 缺 {p}"
    assert "*" not in codes
    for forbidden in ("users:read", "roles:read", "permissions:read",
                      "audit_logs:read", "login_logs:read", "opinions:write",
                      "events:write", "alerts:write", "foreign:analysis",
                      "foreign:ai:review:read"):
        assert forbidden not in codes, f"operator 不应持有 {forbidden}"


def test_analyst_matrix(session):
    apply_d1_role_fixes(session)
    an = session.execute(select(Role).where(Role.code == "analyst")).scalar_one()
    codes = {p.code for p in an.permissions}
    for p in ANALYST_ADD_PERMS:
        assert p in codes, f"analyst 缺 {p}"
    assert "permissions:read" not in codes
    assert "sources:write" not in codes
    # foreign:analysis 本阶段 BLOCKED，不赋值给 analyst
    assert "foreign:analysis" not in codes
    assert "foreign:alerts:manage" not in codes


def test_viewer_unchanged(session):
    apply_d1_role_fixes(session)
    vw = session.execute(select(Role).where(Role.code == "viewer")).scalar_one()
    codes = {p.code for p in vw.permissions}
    for p in VIEWER_BASELINE:
        assert p in codes, f"viewer 基线权限丢失 {p}"
    # 不应因 D1 获得任何写/管理/系统权限
    for forbidden in ("users:write", "roles:write", "opinions:write", "events:write",
                      "alerts:write", "foreign:analysis", "foreign:alerts:manage",
                      "system_admin", "operator"):
        assert forbidden not in codes, f"viewer 被意外扩大 {forbidden}"


def test_get_user_permissions_system_admin(session):
    apply_d1_role_fixes(session)
    u = User(username="sa", password_hash="x", role="system_admin", is_superuser=False)
    perms = get_user_permissions(u, session)
    assert perms != ["*"]
    assert "users:read" in perms
    assert "foreign:sources:write" in perms  # 来自 foreign:data:manage 展开


def test_get_user_permissions_analyst(session):
    apply_d1_role_fixes(session)
    u = User(username="an", password_hash="x", role="analyst", is_superuser=False)
    perms = get_user_permissions(u, session)
    assert "foreign:read" in perms
    assert "foreign:opinions:read" in perms  # 展开
    assert "keywords:write" in perms
    assert "permissions:read" not in perms
    assert "sources:write" not in perms


def test_superuser_still_star(session):
    u1 = User(username="adm", password_hash="x", role="admin", is_superuser=True)
    assert get_user_permissions(u1, session) == ["*"]
    u2 = User(username="adm2", password_hash="x", role="admin", is_superuser=False)
    assert get_user_permissions(u2, session) == ["*"]  # role==admin 等价超管


def test_revert_restores_before(session):
    apply_d1_role_fixes(session)
    revert_d1_role_fixes(session)
    assert session.execute(select(Role).where(Role.code == "system_admin")).scalar_one_or_none() is None
    assert session.execute(select(Role).where(Role.code == "operator")).scalar_one_or_none() is None
    r111 = session.execute(select(Role).where(Role.code == "111")).scalar_one_or_none()
    assert r111 is not None
    an = session.execute(select(Role).where(Role.code == "analyst")).scalar_one()
    codes = {p.code for p in an.permissions}
    assert "permissions:read" in codes
    assert "sources:write" in codes
    assert "foreign:read" not in codes
