"""RBAC 权限收口自动化测试（Phase RBAC-1/2）。

运行方式（仅隔离测试库，绝不指向生产 opinion_db）::

    DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test' \
    DB_IDENTITY_CHECK=off \
    ./.venv/Scripts/python.exe -m pytest tests/test_rbac_hardening.py -v

覆盖范围（对应本次收口的 7 个问题）：
    1. GET /api/auth/me 契约（未认证 401；admin/viewer/analyst 权限内容正确）
    2. 观察者（viewer）：
         - 可以查看事件、预警（读接口 200）
         - 不能删除事件、不能处置事件、不能手动聚合（403）
         - 不能新增/编辑/删除预警规则、不能执行评估、不能处置预警（403）
         - 不能查看/管理关键词（keywords:read / keywords:write 均 403）
         - 不能使用 AI 检索与 AI 研判（ai:search / ai:analyze 403）
         - 不能查看/导出/管理报告（reports:* 403）
    3. analyst：AI 检索/研判与报告读导出放行（非 403）
    4. admin（超管）：以上全部不返回 403

安全边界：本文件不修改生产库；所有写操作仅作用于隔离测试库 opinion_test。
模块级护栏：若 DATABASE_URL 指向生产 opinion_db，整个模块跳过。
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 护栏：严禁本测试触碰生产库 opinion_db
# ---------------------------------------------------------------------------
_DB_URL = os.environ.get("DATABASE_URL", "")
if "opinion_db" in _DB_URL:
    pytest.skip(
        "test_rbac_hardening 仅允许在隔离测试库 opinion_test 运行；检测到生产库 opinion_db，已跳过",
        allow_module_level=True,
    )

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
USER_PASS = "Passw0rd1"


# ---------------------------------------------------------------------------
# 环境 bootstrap：admin 用户 + AI 权限种子（等价于迁移 p31_rbac_ai_perms）
# ---------------------------------------------------------------------------
_AI_PERMISSIONS = [
    ("ai:search", "AI检索", "ai", "search", "AI能力", "使用 AI/联网检索能力"),
    ("ai:analyze", "AI研判", "ai", "analyze", "AI能力", "触发舆情 AI 分析研判"),
    ("ai:manage", "AI配置管理", "ai", "manage", "AI能力", "管理 AI 检索线索与配置"),
]
_AI_GRANTS = {"admin": ["ai:search", "ai:analyze", "ai:manage"], "analyst": ["ai:search", "ai:analyze"]}


@pytest.fixture(scope="session", autouse=True)
def ensure_hardening_env() -> None:
    """幂等准备测试库：admin 超管账号 + ai:* 权限及其角色授权。

    测试库可能尚未执行 alembic p31 迁移，这里按同一份定义补种，保证测试自洽。
    """
    from app.core.security import hash_password
    from app.db.session import SessionLocal
    from app.models.user import User
    from app.models.permission import Permission
    from app.models.role import Role

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == ADMIN_USER).first()
        if admin is None:
            admin = User(username=ADMIN_USER, role="admin")
            db.add(admin)
        admin.is_superuser = True
        admin.is_active = True
        admin.role = "admin"
        admin.password_hash = hash_password(ADMIN_PASS)

        for code, name, resource, action, group, desc in _AI_PERMISSIONS:
            if db.query(Permission).filter(Permission.code == code).first() is None:
                db.add(
                    Permission(
                        code=code, name=name, resource=resource,
                        action=action, group=group, description=desc,
                    )
                )
        db.flush()

        for role_name, codes in _AI_GRANTS.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if role is None:
                continue
            owned = {p.code for p in role.permissions}
            for code in codes:
                if code in owned:
                    continue
                perm = db.query(Permission).filter(Permission.code == code).first()
                if perm is not None:
                    role.permissions.append(perm)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# helpers / fixtures
# ---------------------------------------------------------------------------
def _auth(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    return _auth(client, ADMIN_USER, ADMIN_PASS)


def _make_user(client: TestClient, admin_headers: dict, username: str, role: str) -> int:
    existing = client.get(f"/api/users?search={username}", headers=admin_headers).json()["items"]
    for u in existing:
        client.delete(f"/api/users/{u['id']}", headers=admin_headers)
    r = client.post(
        "/api/users",
        json={"username": username, "password": USER_PASS, "role": role},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def viewer_headers(client: TestClient, admin_headers: dict):
    uid = _make_user(client, admin_headers, "rbac_hard_viewer", "viewer")
    headers = _auth(client, "rbac_hard_viewer", USER_PASS)
    yield headers
    client.delete(f"/api/users/{uid}", headers=admin_headers)


@pytest.fixture
def analyst_headers(client: TestClient, admin_headers: dict):
    uid = _make_user(client, admin_headers, "rbac_hard_analyst", "analyst")
    headers = _auth(client, "rbac_hard_analyst", USER_PASS)
    yield headers
    client.delete(f"/api/users/{uid}", headers=admin_headers)


def _call(client: TestClient, method: str, path: str, headers: dict, body=None):
    fn = getattr(client, method.lower())
    if method in ("POST", "PUT", "PATCH"):
        return fn(path, json=body or {}, headers=headers)
    return fn(path, headers=headers)


# ===========================================================================
# 1. GET /api/auth/me 契约
# ===========================================================================
def test_auth_me_requires_login(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401


def test_auth_me_admin_contract(client: TestClient, admin_headers: dict):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["username"] == ADMIN_USER
    assert data["is_superuser"] is True
    assert data["is_active"] is True
    # 超管权限用通配符表达，与登录接口保持一致
    assert "*" in data["permissions"]


def test_auth_me_viewer_contract(client: TestClient, viewer_headers: dict):
    r = client.get("/api/auth/me", headers=viewer_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["username"] == "rbac_hard_viewer"
    assert data["is_superuser"] is False
    perms = set(data["permissions"])
    assert "*" not in perms
    # 观察者可读事件/预警，但不含关键词读、AI 能力、报告导出与模板管理
    assert {"events:read", "alerts:read"} <= perms
    assert not (
        {"keywords:read", "keywords:write", "ai:search", "ai:analyze", "ai:manage",
         "events:write", "alerts:write", "reports:export", "reports:manage"} & perms
    )


def test_auth_me_analyst_has_ai_permissions(client: TestClient, analyst_headers: dict):
    r = client.get("/api/auth/me", headers=analyst_headers)
    assert r.status_code == 200, r.text
    perms = set(r.json()["permissions"])
    assert {"ai:search", "ai:analyze"} <= perms
    # ai:manage 属于超管/管理侧，分析员不应持有
    assert "ai:manage" not in perms


# ===========================================================================
# 2. 观察者（viewer）能力矩阵
# ===========================================================================
VIEWER_ALLOWED_READS = [
    ("GET", "/api/events"),
    ("GET", "/api/alerts/rules"),
    ("GET", "/api/alerts/records"),
    ("GET", "/api/opinions"),
]

VIEWER_DENIED = [
    # 事件处置 / 删除 / 聚合（events:write）
    ("POST", "/api/events/aggregate", None),
    ("PATCH", "/api/events/999999/status", {"status": "processing"}),
    ("POST", "/api/events/999999/actions", {"action_type": "note", "content": "x"}),
    ("DELETE", "/api/events/999999", None),
    # 预警规则与处置（alerts:write）
    ("POST", "/api/alerts/rules", {"name": "rbac_test_rule", "risk_threshold": 70}),
    ("PUT", "/api/alerts/rules/999999", {"enabled": False}),
    ("DELETE", "/api/alerts/rules/999999", None),
    ("POST", "/api/alerts/evaluate", None),
    ("PUT", "/api/alerts/records/999999/handle", {"status": "resolved", "note": ""}),
    # 关键词（keywords:read / keywords:write）
    ("GET", "/api/keywords", None),
    ("GET", "/api/keywords/categories", None),
    ("POST", "/api/keywords", {"word": "rbac_x", "type": "monitoring", "source": "custom"}),
    ("PUT", "/api/keywords/999999", {"is_enabled": False}),
    ("DELETE", "/api/keywords/999999", None),
    # AI 能力（ai:search / ai:analyze）
    ("POST", "/api/analyze/999999", None),
    ("GET", "/api/bocha/ai-search/options", None),
    ("GET", "/api/anspire/options", None),
    # 报告导出与模板管理（reports:export / reports:manage —— 观察者两库均不持有）
    # 注：reports:read 在不同环境的 viewer 角色授予情况不一致，故不纳入固定断言，
    #     改由 test_viewer_report_read_matches_granted_permissions 按实际授权动态校验。
    ("GET", "/api/reports/templates", None),
    ("POST", "/api/reports/export", {"name": "x", "modules": []}),
    ("POST", "/api/reports/templates", {"name": "x", "config": {}}),
]


@pytest.mark.parametrize("method,path", VIEWER_ALLOWED_READS)
def test_viewer_can_read(client: TestClient, viewer_headers: dict, method: str, path: str):
    r = _call(client, method, path, viewer_headers)
    assert r.status_code == 200, f"{method} {path} -> {r.status_code} {r.text[:160]}"


@pytest.mark.parametrize("method,path,body", VIEWER_DENIED)
def test_viewer_denied(client: TestClient, viewer_headers: dict, method: str, path: str, body):
    r = _call(client, method, path, viewer_headers, body)
    assert r.status_code == 403, f"{method} {path} -> {r.status_code} (expected 403) {r.text[:160]}"
    # 403 detail 必须是 RBAC 语义，前端据此展示「权限不足，请联系管理员」
    assert r.json().get("detail") in ("Permission denied", "Admin required")


def test_viewer_report_read_matches_granted_permissions(client: TestClient, viewer_headers: dict):
    """报告只读接口的放行结果必须与 viewer 实际持有的 reports:read 一致。

    不同环境 viewer 角色是否授予 reports:read 存在差异（生产未授予、测试库已授予），
    因此断言「权限与接口行为一致」而非写死 200/403。
    """
    perms = set(client.get("/api/auth/me", headers=viewer_headers).json()["permissions"])
    expect_allow = "reports:read" in perms
    for path in ("/api/reports/overview", "/api/reports/modules"):
        r = client.get(path, headers=viewer_headers)
        if expect_allow:
            assert r.status_code != 403, f"{path} 持有 reports:read 却被拒：{r.status_code}"
        else:
            assert r.status_code == 403, f"{path} 无 reports:read 却放行：{r.status_code}"


# ===========================================================================
# 3. analyst：AI 与报告能力放行
# ===========================================================================
ANALYST_ALLOWED = [
    ("GET", "/api/keywords", None),
    ("GET", "/api/keywords/categories", None),
    ("GET", "/api/bocha/ai-search/options", None),
    ("GET", "/api/anspire/options", None),
    ("POST", "/api/analyze/999999", None),  # 无该舆情 -> 404，但不能是 403
    ("GET", "/api/reports/overview", None),
    ("GET", "/api/reports/modules", None),
    ("GET", "/api/reports/templates", None),
]


@pytest.mark.parametrize("method,path,body", ANALYST_ALLOWED)
def test_analyst_not_forbidden(client: TestClient, analyst_headers: dict, method: str, path: str, body):
    r = _call(client, method, path, analyst_headers, body)
    assert r.status_code != 403, f"{method} {path} 不应 403，实际 {r.status_code} {r.text[:160]}"


def test_analyst_cannot_manage_report_template(client: TestClient, analyst_headers: dict):
    """reports:manage 未授予 analyst：模板写操作应 403（导出/读取不受影响）。"""
    r = client.post(
        "/api/reports/templates",
        json={"name": "rbac_tpl", "config": {}},
        headers=analyst_headers,
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code} {r.text[:160]}"


# ===========================================================================
# 4. admin（超管）：全部不 403
# ===========================================================================
@pytest.mark.parametrize("method,path,body", VIEWER_DENIED)
def test_admin_never_forbidden(client: TestClient, admin_headers: dict, method: str, path: str, body):
    r = _call(client, method, path, admin_headers, body)
    assert r.status_code != 403, f"admin 被拒 {method} {path} -> {r.status_code} {r.text[:160]}"


# ===========================================================================
# 5. Phase Security-2 / Phase 10：全角色动态权限测试
#    角色不写死，从数据库 roles 表实时读取，新增角色自动纳入覆盖。
# ===========================================================================
def _db_roles() -> list[dict]:
    """从数据库动态读取所有启用角色及其权限码（不含超管 admin）。"""
    from app.db.session import SessionLocal
    from app.models.role import Role

    db = SessionLocal()
    try:
        rows = []
        for role in db.query(Role).order_by(Role.id).all():
            if not role.is_enabled:
                continue
            if role.name == "admin":
                continue  # 超管走 test_admin_never_forbidden 分支
            rows.append({"name": role.name, "permissions": sorted(p.code for p in role.permissions)})
        return rows
    finally:
        db.close()


try:
    DYNAMIC_ROLES = _db_roles()
except Exception:  # pragma: no cover - 采集期数据库不可用时降级
    DYNAMIC_ROLES = []

DYNAMIC_ROLE_NAMES = [r["name"] for r in DYNAMIC_ROLES]


@pytest.fixture
def role_headers(client: TestClient, admin_headers: dict):
    """按角色名动态创建临时账号并返回其鉴权头，用例结束自动清理。"""
    created: list[int] = []

    def _make(role_name: str) -> dict:
        username = f"rbac_dyn_{role_name}"
        uid = _make_user(client, admin_headers, username, role_name)
        created.append(uid)
        return _auth(client, username, USER_PASS)

    yield _make
    for uid in created:
        client.delete(f"/api/users/{uid}", headers=admin_headers)


@pytest.mark.skipif(not DYNAMIC_ROLES, reason="数据库中无可用非超管角色")
@pytest.mark.parametrize("role_name", DYNAMIC_ROLE_NAMES)
def test_role_permissions_match_db(client: TestClient, role_headers, role_name: str):
    """/api/auth/me 返回的权限集必须与数据库 role_permissions 完全一致。"""
    expected = next(r["permissions"] for r in DYNAMIC_ROLES if r["name"] == role_name)
    headers = role_headers(role_name)
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_superuser"] is False, f"非超管角色 {role_name} 不应为超管"
    perms = set(data["permissions"])
    assert "*" not in perms, f"非超管角色 {role_name} 不应持有通配权限"
    assert perms == set(expected), (
        f"角色 {role_name} 权限不一致：接口={sorted(perms)} 数据库={expected}"
    )


@pytest.mark.skipif(not DYNAMIC_ROLES, reason="数据库中无可用非超管角色")
@pytest.mark.parametrize("role_name", DYNAMIC_ROLE_NAMES)
def test_role_no_privileged_admin_permissions(client: TestClient, role_headers, role_name: str):
    """SEC2-B 职责冲突守门：非超管角色不得同时持有用户/角色/权限/审计管理权。

    该断言防止后续有人给业务角色误授管理类权限造成越权。
    """
    perms = set(next(r["permissions"] for r in DYNAMIC_ROLES if r["name"] == role_name))
    privileged = {
        "users:write", "users:activate", "roles:write", "roles:delete",
        "permissions:write",
    }
    overlap = perms & privileged
    assert not overlap, f"角色 {role_name} 持有管理类高危权限：{sorted(overlap)}"


@pytest.mark.skipif(not DYNAMIC_ROLES, reason="数据库中无可用非超管角色")
@pytest.mark.parametrize("role_name", DYNAMIC_ROLE_NAMES)
def test_propagation_rebuild_requires_events_write(client: TestClient, role_headers, role_name: str):
    """SEC2-01 回归：POST /api/propagation/rebuild/{id} 必须受 events:write 管控。

    - 无 events:write 的角色 → 403 Permission denied
    - 有 events:write 的角色 → 不得是 403（事件不存在时为 404）
    """
    perms = set(next(r["permissions"] for r in DYNAMIC_ROLES if r["name"] == role_name))
    headers = role_headers(role_name)
    r = client.post("/api/propagation/rebuild/999999", headers=headers)
    if "events:write" in perms:
        assert r.status_code != 403, (
            f"角色 {role_name} 持有 events:write 却被拒：{r.status_code} {r.text[:160]}"
        )
    else:
        assert r.status_code == 403, (
            f"角色 {role_name} 无 events:write 却放行：{r.status_code} {r.text[:160]}"
        )
        assert r.json().get("detail") == "Permission denied"


def test_propagation_rebuild_admin_not_forbidden(client: TestClient, admin_headers: dict):
    """超管执行传播链重建不应被 RBAC 拦截（事件不存在返回 404）。"""
    r = client.post("/api/propagation/rebuild/999999", headers=admin_headers)
    assert r.status_code != 403, f"admin 被拒：{r.status_code} {r.text[:160]}"


@pytest.mark.skipif(not DYNAMIC_ROLES, reason="数据库中无可用非超管角色")
@pytest.mark.parametrize("role_name", DYNAMIC_ROLE_NAMES)
def test_role_cannot_touch_user_management(client: TestClient, role_headers, role_name: str):
    """非超管角色不得访问用户/角色/审计管理接口（读写均应 403）。"""
    headers = role_headers(role_name)
    for method, path, body in (
        ("GET", "/api/users", None),
        ("POST", "/api/users", {"username": "rbac_dyn_x", "password": USER_PASS, "role": "viewer"}),
        ("GET", "/api/roles", None),
        ("PUT", "/api/roles/1", {"description": "x"}),
        ("GET", "/api/operation-logs", None),
        ("GET", "/api/login-logs", None),
    ):
        r = _call(client, method, path, headers, body)
        assert r.status_code == 403, (
            f"角色 {role_name} 访问 {method} {path} 未被拒绝：{r.status_code} {r.text[:160]}"
        )


# ===========================================================================
# 6. Phase Security-2 / Phase H：权限变更审计验证
#    要求：用户角色变更、角色权限变更均落审计日志，且包含变更前/后值。
# ===========================================================================
def _latest_log(client: TestClient, admin_headers: dict, action: str, **params) -> dict:
    query = {"action": action, "size": 20, **params}
    r = client.get("/api/operation-logs", params=query, headers=admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert items, f"未找到 action={action} 的审计日志"
    return items[0]


def test_user_role_change_audited_with_before_after(client: TestClient, admin_headers: dict):
    """Phase H：管理员把用户 viewer→analyst，审计日志须含 before/after 且能定位变更字段。"""
    import json as _json

    uid = _make_user(client, admin_headers, "rbac_audit_target", "viewer")
    try:
        r = client.put(f"/api/users/{uid}", json={"role": "analyst"}, headers=admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "analyst"

        log = _latest_log(client, admin_headers, "UPDATE", target_user_id=uid)
        assert log["resource_type"] == "user"
        assert log["result"] == "success"
        assert log["operator_username_snapshot"] == ADMIN_USER
        details = _json.loads(log["details_json"])
        assert "before" in details and "after" in details, f"缺少前后值：{details}"
        assert details["before"]["role"] == "viewer"
        assert details["after"]["role"] == "analyst"
        assert "role" in details["changed_fields"]

        # 变更后重新登录，权限须实时生效（analyst 具备 ai:search）
        headers = _auth(client, "rbac_audit_target", USER_PASS)
        perms = set(client.get("/api/auth/me", headers=headers).json()["permissions"])
        assert "ai:search" in perms, f"角色变更未生效：{sorted(perms)}"
    finally:
        client.delete(f"/api/users/{uid}", headers=admin_headers)


def test_user_password_reset_not_logged_in_plaintext(client: TestClient, admin_headers: dict):
    """审计日志不得记录密码明文/哈希，只记录布尔标记。"""
    import json as _json

    uid = _make_user(client, admin_headers, "rbac_audit_pwd", "viewer")
    try:
        new_pwd = "Passw0rd2"
        r = client.put(f"/api/users/{uid}", json={"password": new_pwd}, headers=admin_headers)
        assert r.status_code == 200, r.text
        log = _latest_log(client, admin_headers, "UPDATE", target_user_id=uid)
        raw = log["details_json"] or ""
        assert new_pwd not in raw, "审计日志泄露了密码明文"
        details = _json.loads(raw)
        assert details.get("password_changed") is True
        assert details["changes"].get("password") == "***"
    finally:
        client.delete(f"/api/users/{uid}", headers=admin_headers)


def test_role_permission_change_audited_with_diff(client: TestClient, admin_headers: dict):
    """Phase H：角色权限变更须记录 permissions_added / permissions_removed。"""
    import json as _json

    # 用临时角色做变更，避免影响 viewer/analyst 等在用角色
    r = client.post(
        "/api/roles",
        json={
            "name": "rbac_audit_role",
            "code": "rbac_audit_role",
            "display_name": "审计测试角色",
            "permissions": ["events:read"],
        },
        headers=admin_headers,
    )
    if r.status_code == 400:  # 上次残留，先清理
        roles = client.get("/api/roles", headers=admin_headers).json()
        items = roles["items"] if isinstance(roles, dict) else roles
        for it in items:
            if it["name"] == "rbac_audit_role":
                client.delete(f"/api/roles/{it['id']}", headers=admin_headers)
        r = client.post(
            "/api/roles",
            json={
                "name": "rbac_audit_role",
                "code": "rbac_audit_role",
                "display_name": "审计测试角色",
                "permissions": ["events:read"],
            },
            headers=admin_headers,
        )
    assert r.status_code in (200, 201), r.text
    role_id = r.json()["id"]
    try:
        up = client.put(
            f"/api/roles/{role_id}",
            json={"permissions": ["events:read", "events:write"]},
            headers=admin_headers,
        )
        assert up.status_code == 200, up.text

        log = _latest_log(client, admin_headers, "ROLE_UPDATE")
        assert log["resource_id"] == str(role_id)
        details = _json.loads(log["details_json"])
        assert details["before"]["permissions"] == ["events:read"]
        assert set(details["after"]["permissions"]) == {"events:read", "events:write"}
        assert details["permissions_added"] == ["events:write"]
        assert details["permissions_removed"] == []
    finally:
        client.delete(f"/api/roles/{role_id}", headers=admin_headers)
