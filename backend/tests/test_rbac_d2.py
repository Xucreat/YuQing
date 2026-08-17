"""D2 Enforcement 重构与权限边界收口 —— 隔离测试（SQLite in-memory，绝不连接生产库）。

覆盖：
- 3 个新增权限（opinions:delete / events:delete / collector:run）存在
- system_admin / operator / analyst / viewer 在 D2 后的权限矩阵与 Enforcement 决策
- superuser 仍返回 ["*"]
- 角色创建权限提升防护（_assert_no_privilege_escalation）
- D2 migration 数据逻辑幂等（_ensure_permissions / _grant_roles）
- require_permission 决策：允许合法角色、403 非法角色
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.role import Role
from app.models.permission import Permission, role_permissions, user_roles
from app.models.user import User
from app.core.rbac_d1 import (
    apply_d1_role_fixes,
    SYSTEM_ADMIN_PERMS,
    OPERATOR_PERMS,
    ANALYST_ADD_PERMS,
    ANALYST_REMOVE_PERMS,
)
from app.core.permissions import expand_permissions, get_user_permissions, require_permission
from app.api.users import _assert_no_privilege_escalation
import importlib.util as _ilu
from pathlib import Path as _Path

_D2_MIG_PATH = _Path(__file__).resolve().parent.parent / "alembic" / "versions" / "rbac_d2_enforcement_v1.py"
_d2_spec = _ilu.spec_from_file_location("rbac_d2_enforcement_v1", _D2_MIG_PATH)
rbac_d2 = _ilu.module_from_spec(_d2_spec)
_d2_spec.loader.exec_module(rbac_d2)
_ensure_permissions = rbac_d2._ensure_permissions
_grant_roles = rbac_d2._grant_roles
_NEW_PERMISSIONS = rbac_d2._NEW_PERMISSIONS
_ROLE_GRANTS = rbac_d2._ROLE_GRANTS

VIEWER_BASELINE = [
    "alerts:read", "events:read", "opinions:read", "propagation:read",
    "domestic:ai:review:read", "domestic:ai:review:complete",
    "foreign:ai:review:read", "foreign:ai:review:complete",
]

D2_NEW = ["opinions:delete", "events:delete", "collector:run"]


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, Role.__table__, Permission.__table__, role_permissions, user_roles],
    )
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()

    # 真实生产基线（只读抽取于 127.0.0.1:5432/opinion_db，D1 已落地）：
    # analyst 保留 events:write/opinions:write（编辑/合并），不含 delete/collector:run/foreign:analysis
    # viewer = 8 只读；operator = OPERATOR_PERMS；system_admin = SYSTEM_ADMIN_PERMS
    ANALYST_BASELINE = {
        "ai:analyze", "ai:search", "alerts:read", "alerts:write",
        "domestic:ai:analyze", "domestic:ai:batch:cancel", "domestic:ai:batch:read",
        "domestic:ai:full-confirm", "domestic:ai:review:complete", "domestic:ai:review:read",
        "domestic:ai:review:reject", "domestic:alerts:review:confirm", "domestic:alerts:review:read",
        "domestic:events:review:confirm", "domestic:events:review:read",
        "events:read", "events:write", "foreign:ai:batch:cancel", "foreign:ai:batch:read",
        "foreign:ai:review:complete", "foreign:ai:review:read", "foreign:read",
        "keywords:read", "keywords:write", "opinions:read", "opinions:write",
        "propagation:read", "reports:export", "reports:manage", "reports:read", "sources:read",
    }

    codes = (
        set(SYSTEM_ADMIN_PERMS) | set(OPERATOR_PERMS)
        | set(VIEWER_BASELINE) | ANALYST_BASELINE
        | set(D2_NEW)
        | {"users:delete", "foreign:analysis", "foreign:alerts:manage"}
    )
    perm_id_by_code = {}
    for i, code in enumerate(sorted(codes), start=1):
        res, _, act = code.partition(":")
        p = Permission(id=i, code=code, name=code, resource=res or code, action=act, group="test")
        s.add(p)
        perm_id_by_code[code] = i
    s.flush()

    # 基础角色（id 固定，模拟生产；apply_d1_role_fixes 依赖其已存在）
    admin = Role(id=1, name="admin", code="admin", display_name="管理员", is_system=True, is_enabled=True)
    analyst = Role(id=2, name="analyst", code="analyst", display_name="分析员", is_system=True, is_enabled=True)
    viewer = Role(id=3, name="viewer", code="viewer", display_name="只读", is_system=True, is_enabled=True)
    operator = Role(id=4, name="operator", code="operator", display_name="采集员", is_system=True, is_enabled=True)
    sa_role = Role(id=5, name="system_admin", code="system_admin", display_name="系统管理员", is_system=True, is_enabled=True)
    r111 = Role(id=6, name="111", code="111", display_name="111", is_system=False, is_enabled=True)
    for r in (admin, analyst, viewer, operator, sa_role, r111):
        s.add(r)
    s.flush()

    # 通过 Core 插入 role_permissions（避免加载 ORM 集合 → 规避 cleanup_role_111 的 StaleDataError）
    def _link(role_id, code):
        s.execute(role_permissions.insert().values(role_id=role_id, permission_id=perm_id_by_code[code]))

    _link(r111.id, "opinions:read")
    for code in VIEWER_BASELINE:
        _link(viewer.id, code)
    for code in ANALYST_BASELINE:
        _link(analyst.id, code)
    for code in OPERATOR_PERMS:
        _link(operator.id, code)
    for code in SYSTEM_ADMIN_PERMS:
        _link(sa_role.id, code)
    s.commit()  # 提交并过期集合，使 apply_d1_role_fixes 以幂等方式重跑（与 D1 fixture 一致）

    apply_d1_role_fixes(s)
    # 应用 D2 数据层：新增 3 权限并绑定 system_admin / operator
    perm_ids = _ensure_permissions(s)
    _grant_roles(s, perm_ids)
    s.commit()
    yield s
    s.close()


# ---------------- 新增权限存在性 ----------------
def test_new_permissions_exist(session):
    for code in D2_NEW:
        assert session.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none() is not None, \
            f"缺少新增权限 {code}"


# ---------------- D2 migration 数据逻辑幂等 ----------------
def test_d2_migration_logic_idempotent(session):
    # 第一次应用
    perm_ids = _ensure_permissions(session)
    _grant_roles(session, perm_ids)
    session.flush()
    sa = session.execute(select(Role).where(Role.code == "system_admin")).scalar_one()
    op = session.execute(select(Role).where(Role.code == "operator")).scalar_one()
    sa_codes = {p.code for p in sa.permissions}
    op_codes = {p.code for p in op.permissions}
    for c in D2_NEW:
        assert c in sa_codes, f"system_admin 应持有 {c}"
    assert "collector:run" in op_codes
    assert "opinions:delete" not in op_codes
    rp_count_1 = session.execute(select(func.count()).select_from(role_permissions)).scalar()

    # 第二次应用（幂等，不应重复插入）
    perm_ids2 = _ensure_permissions(session)
    _grant_roles(session, perm_ids2)
    session.flush()
    rp_count_2 = session.execute(select(func.count()).select_from(role_permissions)).scalar()
    assert rp_count_1 == rp_count_2, "D2 migration 非幂等：role_permissions 重复插入"


# ---------------- 角色矩阵（D2 后） ----------------
def test_system_admin_matrix_d2(session):
    sa = session.execute(select(Role).where(Role.code == "system_admin")).scalar_one()
    codes = {p.code for p in sa.permissions}
    for c in D2_NEW:
        assert c in codes, f"system_admin 缺 {c}"
    assert "*" not in codes
    assert codes == set(SYSTEM_ADMIN_PERMS) | set(D2_NEW)


def test_operator_matrix_d2(session):
    op = session.execute(select(Role).where(Role.code == "operator")).scalar_one()
    codes = {p.code for p in op.permissions}
    assert "collector:run" in codes
    assert "opinions:delete" not in codes
    assert "events:delete" not in codes
    assert "users:read" not in codes
    assert "roles:write" not in codes
    assert "permissions:read" not in codes
    assert "foreign:analysis" not in codes
    assert "foreign:alerts:manage" not in codes


def test_analyst_no_d2_high_risk(session):
    an = session.execute(select(Role).where(Role.code == "analyst")).scalar_one()
    codes = {p.code for p in an.permissions}
    assert "opinions:delete" not in codes
    assert "events:delete" not in codes
    assert "collector:run" not in codes
    assert "events:write" in codes  # 编辑能力保留（删除独立）
    assert "foreign:analysis" not in codes
    assert "foreign:alerts:manage" not in codes


def test_viewer_unchanged_d2(session):
    vw = session.execute(select(Role).where(Role.code == "viewer")).scalar_one()
    codes = {p.code for p in vw.permissions}
    for p in VIEWER_BASELINE:
        assert p in codes
    for forbidden in ("opinions:delete", "events:delete", "collector:run",
                      "events:write", "opinions:write", "users:write", "roles:write"):
        assert forbidden not in codes


# ---------------- require_permission Enforcement 决策 ----------------
def _user(session, username, role, is_superuser=False):
    u = User(username=username, password_hash="x", role=role, is_superuser=is_superuser)
    session.add(u)
    session.flush()
    return u


def test_system_admin_enforcement_allows_d2_perms(session):
    u = _user(session, "sa", "system_admin")
    for perm in ("opinions:delete", "events:delete", "collector:run", "sources:write", "users:read"):
        require_permission(perm)(u, session)  # 不抛异常
    with pytest.raises(Exception):
        require_permission("users:delete")(u, session)  # 未持有 -> 403


def test_operator_enforcement_scoped(session):
    u = _user(session, "op", "operator")
    require_permission("collector:run")(u, session)
    require_permission("sources:write")(u, session)
    for denied in ("opinions:delete", "events:delete", "users:read", "roles:write",
                   "permissions:read", "foreign:analysis", "foreign:ai:review:read"):
        with pytest.raises(Exception):
            require_permission(denied)(u, session)


def test_analyst_enforcement_no_high_risk(session):
    u = _user(session, "an", "analyst")
    require_permission("events:write")(u, session)  # 编辑保留
    require_permission("opinions:write")(u, session)
    for denied in ("opinions:delete", "events:delete", "collector:run", "foreign:analysis"):
        with pytest.raises(Exception):
            require_permission(denied)(u, session)


def test_viewer_enforcement_read_only(session):
    u = _user(session, "vw", "viewer")
    require_permission("opinions:read")(u, session)
    for denied in ("opinions:delete", "events:delete", "collector:run", "events:write", "opinions:write"):
        with pytest.raises(Exception):
            require_permission(denied)(u, session)


def test_superuser_enforcement_passthrough(session):
    u = _user(session, "adm", "admin", is_superuser=True)
    for perm in ("opinions:delete", "events:delete", "collector:run", "users:delete", "anything:x"):
        require_permission(perm)(u, session)  # 超管始终通过
    assert get_user_permissions(u, session) == ["*"]


# ---------------- 权限提升防护 ----------------
def test_escalation_guard_blocks_system_admin(session):
    u = _user(session, "sa2", "system_admin")
    # system_admin 不持有 opinions:write -> 授予应被拒
    with pytest.raises(Exception):
        _assert_no_privilege_escalation(u, ["opinions:write"], session)
    # system_admin 持有 sources:read -> 允许
    _assert_no_privilege_escalation(u, ["sources:read"], session)
    # 授予自身已持有的多个权限 -> 允许
    _assert_no_privilege_escalation(u, ["users:read", "roles:write", "collector:run"], session)


def test_escalation_guard_allows_superuser(session):
    u = _user(session, "adm2", "admin", is_superuser=True)
    _assert_no_privilege_escalation(u, ["*", "users:delete", "opinions:write"], session)  # 超管无限制


def test_escalation_guard_blocks_foreign_high_risk_for_operator(session):
    u = _user(session, "op2", "operator")
    # operator 不持有 foreign:analysis -> 不能把高危 composite 授出
    with pytest.raises(Exception):
        _assert_no_privilege_escalation(u, ["foreign:analysis"], session)
