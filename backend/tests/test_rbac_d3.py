"""D3 —— RBAC Enforcement 收口、Bocha 细粒度授权、*:read 一致化、system role 保护。

隔离测试（SQLite in-memory，绝不连接生产库 127.0.0.1:5432 / 测试库 5433）。

覆盖 D3 最终验收的 6 个维度：
  1. Bocha 细粒度：analyst 可搜索/读取线索，不可 promote；system_admin 全操作；viewer 全拒。
  2. *:read Enforcement：opinions/events/alerts/propagation 四个读权限按角色正确授予，
     viewer 不扩张。
  3. Foreign 高危 composite：foreign:analysis / foreign:alerts:manage 保持 orphan，
     不授予 analyst/operator；其展开的高危叶子（foreign:ai:full-confirm 等）analyst 不持有。
  4. Role management 权限提升防护：_assert_no_privilege_escalation 对 bocha:promote 生效。
  5. System role 保护：update_role 的系统角色修改守卫（mirror users.py:515）。
  6. superuser 继续返回 ["*"]。

Fixture 基线 = 真实生产只读抽取（127.0.0.1:5432/opinion_db，D1/D2 已落地），
依次重放 D1 → D2 → D3 数据层逻辑（apply_d1_role_fixes / D2 ensure+grant / D3 ensure+grant）。
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
from app.core.permissions import (
    expand_permissions,
    get_user_permissions,
    require_permission,
    is_superuser_user,
    COMPOSITE_PERMISSIONS,
)
from app.api.users import _assert_no_privilege_escalation
import importlib.util as _ilu
from pathlib import Path as _Path

_D2_MIG_PATH = _Path(__file__).resolve().parent.parent / "alembic" / "versions" / "rbac_d2_enforcement_v1.py"
_d2_spec = _ilu.spec_from_file_location("rbac_d2_enforcement_v1", _D2_MIG_PATH)
rbac_d2 = _ilu.module_from_spec(_d2_spec)
_d2_spec.loader.exec_module(rbac_d2)
_d2_ensure_permissions = rbac_d2._ensure_permissions
_d2_grant_roles = rbac_d2._grant_roles

_D3_MIG_PATH = _Path(__file__).resolve().parent.parent / "alembic" / "versions" / "rbac_d3_enforcement_v2.py"
_d3_spec = _ilu.spec_from_file_location("rbac_d3_enforcement_v2", _D3_MIG_PATH)
rbac_d3 = _ilu.module_from_spec(_d3_spec)
_d3_spec.loader.exec_module(rbac_d3)
_d3_ensure_permissions = rbac_d3._ensure_permissions
_d3_grant_roles = rbac_d3._grant_roles
_D3_NEW_PERMISSIONS = rbac_d3._NEW_PERMISSIONS

VIEWER_BASELINE = [
    "alerts:read", "events:read", "opinions:read", "propagation:read",
    "domestic:ai:review:read", "domestic:ai:review:complete",
    "foreign:ai:review:read", "foreign:ai:review:complete",
]

D2_NEW = ["opinions:delete", "events:delete", "collector:run"]

D3_NEW = ["bocha:read", "bocha:promote"]

# 既有的四个读权限（D3 仅"确保存在 + 显式授予 system_admin/operator"，不新增）
_READ_PERMS = ["opinions:read", "events:read", "alerts:read", "propagation:read"]


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, Role.__table__, Permission.__table__, role_permissions, user_roles],
    )
    SessionLocal = sessionmaker(bind=engine)
    s = SessionLocal()

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
        | set(D2_NEW) | set(D3_NEW) | set(_READ_PERMS)
        | {"users:delete", "foreign:analysis", "foreign:alerts:manage"}
    )
    perm_id_by_code = {}
    for i, code in enumerate(sorted(codes), start=1):
        res, _, act = code.partition(":")
        p = Permission(id=i, code=code, name=code, resource=res or code, action=act, group="test")
        s.add(p)
        perm_id_by_code[code] = i
    s.flush()

    admin = Role(id=1, name="admin", code="admin", display_name="管理员", is_system=True, is_enabled=True)
    analyst = Role(id=2, name="analyst", code="analyst", display_name="分析员", is_system=True, is_enabled=True)
    viewer = Role(id=3, name="viewer", code="viewer", display_name="只读", is_system=True, is_enabled=True)
    operator = Role(id=4, name="operator", code="operator", display_name="采集员", is_system=True, is_enabled=True)
    sa_role = Role(id=5, name="system_admin", code="system_admin", display_name="系统管理员", is_system=True, is_enabled=True)
    r111 = Role(id=6, name="111", code="111", display_name="111", is_system=False, is_enabled=True)
    for r in (admin, analyst, viewer, operator, sa_role, r111):
        s.add(r)
    s.flush()

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
    s.commit()  # 提交并过期集合，与 D2 fixture 一致的 StaleDataError 规避

    apply_d1_role_fixes(s)
    # D2 数据层
    perm_ids = _d2_ensure_permissions(s)
    _d2_grant_roles(s, perm_ids)
    # D3 数据层（本阶段新增）
    perm_ids3 = _d3_ensure_permissions(s)
    _d3_grant_roles(s, perm_ids3)
    s.commit()
    yield s
    s.close()


def _user(session, username, role, is_superuser=False):
    u = User(username=username, password_hash="x", role=role, is_superuser=is_superuser)
    session.add(u)
    session.flush()
    return u


def _role_codes(session, code):
    role = session.execute(select(Role).where(Role.code == code)).scalar_one()
    return {p.code for p in role.permissions}


# ---------------- D3 新增权限存在性 ----------------
def test_d3_new_permissions_exist(session):
    for code, _n, _r, _a, _g, _d in _D3_NEW_PERMISSIONS:
        assert session.execute(
            select(Permission).where(Permission.code == code)
        ).scalar_one_or_none() is not None, f"缺少 D3 新增权限 {code}"


# ---------------- D3 migration 数据逻辑幂等 ----------------
def test_d3_migration_logic_idempotent(session):
    before = session.execute(select(func.count()).select_from(role_permissions)).scalar()
    perm_ids = _d3_ensure_permissions(session)
    _d3_grant_roles(session, perm_ids)
    session.flush()
    after = session.execute(select(func.count()).select_from(role_permissions)).scalar()
    assert before == after, "D3 migration 非幂等：role_permissions 重复插入"

    sa = session.execute(select(Role).where(Role.code == "system_admin")).scalar_one()
    an = session.execute(select(Role).where(Role.code == "analyst")).scalar_one()
    sa_codes = {p.code for p in sa.permissions}
    an_codes = {p.code for p in an.permissions}
    assert "bocha:promote" in sa_codes
    assert "bocha:read" in sa_codes
    assert "ai:search" in sa_codes  # 回归防护：system_admin 必须能搜索
    assert "bocha:promote" not in an_codes  # analyst 不可 promote
    assert "bocha:read" in an_codes


# ================= 1. Bocha 细粒度 =================
def test_bocha_analyst_can_search_and_read_but_not_promote(session):
    u = _user(session, "an", "analyst")
    require_permission("ai:search")(u, session)   # 搜索
    require_permission("bocha:read")(u, session)  # 查看/复核线索
    for denied in ("bocha:promote",):
        with pytest.raises(Exception):
            require_permission(denied)(u, session)


def test_bocha_system_admin_full_operation(session):
    u = _user(session, "sa", "system_admin")
    for perm in ("ai:search", "bocha:read", "bocha:promote"):
        require_permission(perm)(u, session)  # 搜索 + 查看 + 提升 全部通过


def test_bocha_viewer_denied_all(session):
    u = _user(session, "vw", "viewer")
    for denied in ("ai:search", "bocha:read", "bocha:promote"):
        with pytest.raises(Exception):
            require_permission(denied)(u, session)


# ================= 2. *:read Enforcement =================
def test_read_perms_granted_to_privileged_roles(session):
    for rc in ("system_admin", "operator", "analyst", "viewer"):
        u = _user(session, f"u_{rc}", rc)
        for rp in _READ_PERMS:
            require_permission(rp)(u, session)  # 四角色均持有四个读权限


def test_viewer_not_expanded(session):
    vw_codes = _role_codes(session, "viewer")
    for p in VIEWER_BASELINE:
        assert p in vw_codes
    for forbidden in ("bocha:read", "bocha:promote", "ai:search",
                      "opinions:write", "events:write", "opinions:delete",
                      "events:delete", "collector:run", "foreign:analysis"):
        assert forbidden not in vw_codes, f"viewer 不应持有 {forbidden}"


def test_system_admin_read_matrix(session):
    codes = _role_codes(session, "system_admin")
    for rp in _READ_PERMS:
        assert rp in codes
    assert "ai:search" in codes
    assert "bocha:read" in codes
    assert "bocha:promote" in codes
    # 高危 composite 仍不授予
    assert "foreign:analysis" not in codes
    assert "foreign:alerts:manage" not in codes


def test_operator_read_matrix_no_high_risk(session):
    codes = _role_codes(session, "operator")
    for rp in _READ_PERMS:
        assert rp in codes
    assert "bocha:read" not in codes       # operator 不接触 Bocha
    assert "bocha:promote" not in codes
    assert "foreign:analysis" not in codes
    assert "foreign:alerts:manage" not in codes
    assert "opinions:write" not in codes   # 业务研判不授予采集员


# ================= 3. Foreign 高危 composite =================
def test_foreign_high_risk_composites_orphan(session):
    for rc in ("system_admin", "operator", "analyst", "viewer"):
        codes = _role_codes(session, rc)
        assert "foreign:analysis" not in codes, f"{rc} 不应持有 foreign:analysis"
        assert "foreign:alerts:manage" not in codes, f"{rc} 不应持有 foreign:alerts:manage"


def test_foreign_composite_expansion_correct(session):
    analysis_leaves = expand_permissions(["foreign:analysis"])
    assert "foreign:ai:full-confirm" in analysis_leaves
    assert "foreign:ai:review:reject" in analysis_leaves
    assert "foreign:events:review:confirm" in analysis_leaves
    assert "foreign:alerts:review:confirm" in analysis_leaves
    # 这些高危叶子不应出现在 analyst 的有效权限中
    an = _user(session, "an2", "analyst")
    an_codes = set(get_user_permissions(an, session))
    for leaf in ("foreign:ai:full-confirm", "foreign:ai:review:reject",
                 "foreign:events:review:confirm", "foreign:alerts:review:confirm"):
        assert leaf not in an_codes, f"analyst 不应持有高危叶子 {leaf}"
    # analyst 持有的是 foreign 读能力，而非 analysis 写能力
    assert "foreign:read" in an_codes
    assert "foreign:ai:review:read" in an_codes


# ================= 4. Role management 权限提升防护 =================
def test_escalation_guard_blocks_bocha_promote_for_operator(session):
    u = _user(session, "op3", "operator")  # operator 不持有 bocha:promote，也非 system_admin/超管
    with pytest.raises(Exception):
        _assert_no_privilege_escalation(u, ["bocha:promote"], session)


def test_escalation_guard_allows_superuser_any(session):
    u = _user(session, "adm3", "admin", is_superuser=True)
    _assert_no_privilege_escalation(u, ["bocha:promote", "users:delete", "opinions:write"], session)


# ================= 5. System role 保护（mirror users.py:515） =================
def _system_role_guard_ok(role_is_system: bool, current_user: User) -> bool:
    # 与 app/api/users.py update_role 中系统角色守卫完全一致的条件
    return not (role_is_system and not (is_superuser_user(current_user) or current_user.role == "system_admin"))


def test_system_role_guard_blocks_non_privileged(session):
    sa_user = _user(session, "g_sa", "system_admin")
    super_user = _user(session, "g_su", "admin", is_superuser=True)
    analyst_user = _user(session, "g_an", "analyst")
    operator_user = _user(session, "g_op", "operator")
    # 系统角色 + 非特权（analyst/operator）-> 拒绝
    assert _system_role_guard_ok(True, analyst_user) is False
    assert _system_role_guard_ok(True, operator_user) is False
    # 系统角色 + system_admin / 超管 -> 允许
    assert _system_role_guard_ok(True, sa_user) is True
    assert _system_role_guard_ok(True, super_user) is True
    # 非系统角色 -> 允许（守卫不约束）
    assert _system_role_guard_ok(False, analyst_user) is True


# ================= 6. superuser ["*"] =================
def test_superuser_passthrough(session):
    u = _user(session, "adm", "admin", is_superuser=True)
    for perm in ("bocha:promote", "opinions:delete", "foreign:analysis", "anything:x"):
        require_permission(perm)(u, session)
    assert get_user_permissions(u, session) == ["*"]
