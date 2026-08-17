"""D4 —— RBAC 统一回归基线（Unified RBAC Regression Suite）。

隔离测试（SQLite in-memory，绝不连接生产库 5432 / 测试库 5433）。

本套件不重复 D1/D2/D3 的行为测试，只负责「最终安全矩阵」的自动回归，
覆盖 D4-03 / D4-04 的全部断言：

  1. 角色基线（admin / system_admin / operator / analyst / viewer 五角色存在）
  2. superuser 返回 ["*"]
  3. 无通配符（system_admin / operator / analyst / viewer 均 != ["*"]）
  4. 危险权限按角色正确分布（opinions:delete / events:delete / collector:run /
     bocha:promote / foreign:analysis / foreign:alerts:manage / foreign:ai:full-confirm）
  5. 读基线（system_admin 与 operator 均持有 4 个读权限）
  6. Bocha 三权分离（analyst 可搜索/复核不可 promote；system_admin 全操作；
     operator/viewer 全拒）
  7. Foreign 安全（foreign:analysis / foreign:alerts:manage / foreign:ai:full-confirm
     无任何角色持有）

基线构造：复用 D1/D2/D3 数据层逻辑（apply_d1_role_fixes / D2 ensure+grant /
D3 ensure+grant），与 test_rbac_d3.py 同源，保证与生产 D3 基线一致。

任何一条失败都意味着 RBAC 状态偏离已确认的 D3 设计 —— 此时应 STOP 并报告，
绝不自动修复生产权限。
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
)
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

VIEWER_BASELINE = [
    "alerts:read", "events:read", "opinions:read", "propagation:read",
    "domestic:ai:review:read", "domestic:ai:review:complete",
    "foreign:ai:review:read", "foreign:ai:review:complete",
]
D2_NEW = ["opinions:delete", "events:delete", "collector:run"]
D3_NEW = ["bocha:read", "bocha:promote"]
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
    s.commit()

    apply_d1_role_fixes(s)
    _d2_ensure_permissions(s)
    _d2_grant_roles(s, _d2_ensure_permissions(s))
    _d3_ensure_permissions(s)
    _d3_grant_roles(s, _d3_ensure_permissions(s))
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


def _expanded(session, username, role, is_superuser=False):
    u = _user(session, username, role, is_superuser=is_superuser)
    return set(get_user_permissions(u, session))


# ================= 1. 角色基线 =================
def test_role_baseline_has_five_roles(session):
    expected = {"admin", "system_admin", "operator", "analyst", "viewer"}
    actual = {r.code for r in session.execute(select(Role)).scalars().all()}
    assert actual == expected, f"角色基线不符：{actual}"


def test_admin_role_is_superuser_designation(session):
    admin = session.execute(select(Role).where(Role.code == "admin")).scalar_one()
    assert admin.is_system is True


# ================= 2. superuser ["*"] =================
def test_admin_superuser_returns_wildcard(session):
    u = _user(session, "adm", "admin", is_superuser=True)
    assert get_user_permissions(u, session) == ["*"]


# ================= 3. 无通配符 =================
def test_no_role_holds_wildcard_except_admin(session):
    for rc in ("system_admin", "operator", "analyst", "viewer"):
        u = _user(session, f"nw_{rc}", rc)
        perms = get_user_permissions(u, session)
        assert perms != ["*"], f"{rc} 不应持有通配符 ['*']"
        assert "*" not in perms, f"{rc} 的有效权限不应包含 '*'"


# ================= 4. 危险权限分布 =================
def test_opinions_delete_only_system_admin(session):
    sa = _role_codes(session, "system_admin")
    assert "opinions:delete" in sa
    for rc in ("operator", "analyst", "viewer"):
        assert "opinions:delete" not in _role_codes(session, rc), f"{rc} 不应持有 opinions:delete"


def test_events_delete_only_system_admin(session):
    sa = _role_codes(session, "system_admin")
    assert "events:delete" in sa
    for rc in ("operator", "analyst", "viewer"):
        assert "events:delete" not in _role_codes(session, rc), f"{rc} 不应持有 events:delete"


def test_collector_run_system_admin_and_operator(session):
    sa = _role_codes(session, "system_admin")
    op = _role_codes(session, "operator")
    assert "collector:run" in sa
    assert "collector:run" in op
    for rc in ("analyst", "viewer"):
        assert "collector:run" not in _role_codes(session, rc), f"{rc} 不应持有 collector:run"


def test_bocha_promote_system_admin_only(session):
    sa = _role_codes(session, "system_admin")
    assert "bocha:promote" in sa
    for rc in ("operator", "analyst", "viewer"):
        assert "bocha:promote" not in _role_codes(session, rc), f"{rc} 不应持有 bocha:promote"


def test_foreign_high_risk_composites_unassigned(session):
    for rc in ("system_admin", "operator", "analyst", "viewer"):
        codes = _role_codes(session, rc)
        assert "foreign:analysis" not in codes, f"{rc} 不应持有 foreign:analysis"
        assert "foreign:alerts:manage" not in codes, f"{rc} 不应持有 foreign:alerts:manage"
        # 展开后也不应出现高危叶子（foreign:ai:full-confirm 等）
        expanded = _expanded(session, f"exp_{rc}", rc)
        assert "foreign:ai:full-confirm" not in expanded, f"{rc} 展开后不应含 foreign:ai:full-confirm"
        assert "foreign:analysis" not in expanded
        assert "foreign:alerts:manage" not in expanded


# ================= 5. 读基线 =================
def test_system_admin_and_operator_have_four_reads(session):
    sa = _role_codes(session, "system_admin")
    op = _role_codes(session, "operator")
    for rp in _READ_PERMS:
        assert rp in sa, f"system_admin 缺少读权限 {rp}"
        assert rp in op, f"operator 缺少读权限 {rp}"


# ================= 6. Bocha 三权分离 =================
def test_bocha_separation_matrix(session):
    analyst = _expanded(session, "b_an", "analyst")
    sa = _expanded(session, "b_sa", "system_admin")
    op = _expanded(session, "b_op", "operator")
    vw = _expanded(session, "b_vw", "viewer")

    # analyst：可搜索 + 可复核，不可 promote
    assert "ai:search" in analyst
    assert "bocha:read" in analyst
    assert "bocha:promote" not in analyst
    # system_admin：全操作
    assert "ai:search" in sa and "bocha:read" in sa and "bocha:promote" in sa
    # operator：不接触 Bocha
    assert "bocha:read" not in op and "bocha:promote" not in op and "ai:search" not in op
    # viewer：全拒
    assert "bocha:read" not in vw and "bocha:promote" not in vw and "ai:search" not in vw


# ================= 7. Foreign 安全（展开校验） =================
def test_foreign_ai_full_confirm_no_role(session):
    for rc in ("system_admin", "operator", "analyst", "viewer"):
        expanded = _expanded(session, f"fk_{rc}", rc)
        assert "foreign:ai:full-confirm" not in expanded, f"{rc} 不应持有 foreign:ai:full-confirm"


def test_foreign_composite_expansion_contains_full_confirm(session):
    # 反向校验：组合权限展开确实包含其高危叶子（证明 orphan 状态是「未赋值」而非「展开缺失」）
    leaves = expand_permissions(["foreign:analysis"])
    assert "foreign:ai:full-confirm" in leaves
    assert "foreign:alerts:review:confirm" in leaves
    leaves2 = expand_permissions(["foreign:alerts:manage"])
    assert "foreign:alerts:rules:write" in leaves2
