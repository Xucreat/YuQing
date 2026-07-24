"""RBAC-2C 后端自动化测试（隔离测试库 opinion_test）。

运行方式（仅测试库，绝不指向生产 opinion_db）：
    DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test' \
    DB_IDENTITY_CHECK=off \
    ./.venv/Scripts/python.exe -m pytest tests/test_rbac.py -v

覆盖范围：
    1. 未认证访问受保护接口 -> 401
    2. 无效/缺失/格式错误/过期 Token -> 401
    3. 停用用户无法登录 + 旧 Token 立即失效 -> 401
    4. viewer 权限（允许读 / 拒绝写）
    5. analyst 权限（13 项已迁移权限可用；管理写被拒）
    6. admin 超级管理员（role_permissions=0 仍可访问全部）
    7. 越权测试（viewer/analyst 修改关键词/数据源/用户/角色全部 403）

安全边界：本文件不修改生产库；所有写操作仅作用于隔离测试库 opinion_test。
模块级护栏：若 DATABASE_URL 指向生产 opinion_db，整个模块跳过。
"""
from __future__ import annotations

import os

import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, hash_password

# ---------------------------------------------------------------------------
# 护栏：严禁本测试触碰生产库 opinion_db
# ---------------------------------------------------------------------------
_DB_URL = os.environ.get("DATABASE_URL", "")
if "opinion_db" in _DB_URL:
    pytest.skip(
        "test_rbac 仅允许在隔离测试库 opinion_test 运行；检测到生产库 opinion_db，已跳过",
        allow_module_level=True,
    )

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# 测试用 region 的实际主键 id（由 ensure_test_env 填充）。
# 注意：Opinion.region_id 是 Region.id 外键；Region.code="130000" 是独立唯一列，
# 端点用 db.get(Region, region_id) 按主键 id 查找，故测试必须传真实 id 而非 code。
_REGION_ID: int | None = None


# ---------------------------------------------------------------------------
# 测试环境 bootstrap（仅隔离测试库，幂等）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def ensure_test_env() -> None:
    """确保测试库存在 admin 用户（admin123, is_superuser）与测试用 region。

    仅写隔离测试库；不触碰生产 opinion_db。
    """
    global _REGION_ID
    from app.db.session import SessionLocal
    from app.models.user import User
    from app.models.region import Region

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
        region = db.query(Region).filter(Region.code == "130000").first()
        if region is None:
            region = Region(code="130000", name="河北省", level="province", parent_code=None)
            db.add(region)
            db.flush()
        _REGION_ID = region.id
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _login(client: TestClient, username: str, password: str):
    return client.post("/api/login", json={"username": username, "password": password})


def _auth(client: TestClient, username: str, password: str) -> dict:
    r = _login(client, username, password)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    return _auth(client, ADMIN_USER, ADMIN_PASS)


def _make_user(client, admin_headers, username, role):
    # 清理可能残留的同名用户，保证可重复运行
    existing = client.get(f"/api/users?search={username}", headers=admin_headers).json()["items"]
    for u in existing:
        client.delete(f"/api/users/{u['id']}", headers=admin_headers)
    r = client.post(
        "/api/users",
        json={"username": username, "password": "Passw0rd1", "role": role},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def viewer_user(client: TestClient, admin_headers: dict):
    uid = _make_user(client, admin_headers, "rbac_viewer", "viewer")
    headers = _auth(client, "rbac_viewer", "Passw0rd1")
    yield headers, uid
    client.delete(f"/api/users/{uid}", headers=admin_headers)


@pytest.fixture
def analyst_user(client: TestClient, admin_headers: dict):
    uid = _make_user(client, admin_headers, "rbac_analyst", "analyst")
    headers = _auth(client, "rbac_analyst", "Passw0rd1")
    yield headers, uid
    client.delete(f"/api/users/{uid}", headers=admin_headers)


# ===========================================================================
# 1. 未认证访问 -> 401
# ===========================================================================
def test_unauthenticated_protected_endpoints_401(client: TestClient):
    targets = [
        ("GET", "/api/users", None),
        ("GET", "/api/roles", None),
        ("GET", "/api/permissions", None),
        ("GET", "/api/login-logs", None),
        ("POST", "/api/keywords", {"word": "x_unauth", "type": "monitoring", "source": "custom"}),
    ]
    for method, path, body in targets:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json=body)
        assert r.status_code == 401, f"{method} {path} -> {r.status_code} (expected 401)"


# ===========================================================================
# 2. 无效 Token
# ===========================================================================
def test_invalid_tokens_401(client: TestClient):
    cases = [
        {},  # 缺失 Authorization
        {"Authorization": "Bearer not-a-real-jwt"},  # 非法 JWT
        {"Authorization": "Bearer"},  # 格式错误（无 token 体）
        {"Authorization": "Token abcdef"},  # 错误 scheme
    ]
    for h in cases:
        r = client.get("/api/users", headers=h)
        assert r.status_code == 401, f"headers={h} -> {r.status_code} (expected 401)"

    # 过期 Token（exp 已在过去）
    expired = create_access_token("1", expires_minutes=-10)
    r = client.get("/api/users", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401, f"expired token -> {r.status_code} (expected 401)"


# ===========================================================================
# 3. inactive 用户
# ===========================================================================
def test_inactive_user_rejected_and_token_invalidated(client: TestClient, admin_headers: dict):
    uid = _make_user(client, admin_headers, "rbac_inactive", "viewer")
    try:
        # 激活状态下可登录
        tok = _auth(client, "rbac_inactive", "Passw0rd1")["Authorization"]
        # 停用
        r = client.post(f"/api/users/{uid}/deactivate", headers=admin_headers)
        assert r.status_code == 200, r.text
        # 旧 Token 立即失效（get_current_user 校验 is_active）
        r = client.get("/api/opinions", headers={"Authorization": tok})
        assert r.status_code == 401, f"old token after deactivate -> {r.status_code} (expected 401)"
        # 停用后登录被拒（auth 返回 403 disabled）
        r = _login(client, "rbac_inactive", "Passw0rd1")
        assert r.status_code in (401, 403), f"login while disabled -> {r.status_code} (expected 401/403)"
    finally:
        client.delete(f"/api/users/{uid}", headers=admin_headers)


# ===========================================================================
# 4. viewer 权限
# ===========================================================================
def test_viewer_allowed_reads(client: TestClient, viewer_user):
    headers, _ = viewer_user
    for path in ["/dashboard/stats", "/api/events", "/api/opinions", "/api/reports/overview"]:
        r = client.get(path, headers=headers)
        assert r.status_code == 200, f"viewer GET {path} -> {r.status_code} {r.text[:200]}"


def test_viewer_denied_writes(client: TestClient, viewer_user):
    headers, _ = viewer_user
    denied = [
        ("POST", "/api/keywords", {"word": "vkw", "type": "monitoring", "source": "custom"}),
        ("PUT", "/api/keywords/999999", {"word": "vkw"}),
        ("DELETE", "/api/keywords/999999", None),
        ("POST", "/api/events/aggregate", None),
        ("POST", "/api/opinions", {"title": "t", "content": "c", "source": "s", "url": "http://x", "region_id": 130000}),
        ("PUT", "/api/users/999999", {"display_name": "x"}),
        ("POST", "/api/users", {"username": "v_x", "password": "Passw0rd1", "role": "viewer"}),
        ("PUT", "/api/roles/999999", {"display_name": "x"}),
        ("POST", "/api/roles", {"code": "v_x", "name": "v_x", "display_name": "x"}),
        ("POST", "/api/admin/data-sources/test", {
            "key": "test_src_v", "name": "Test", "type": "generic_site",
            "class_path": "app.collectors.generic_site.GenericSiteCollector", "config_json": "{}",
        }),
    ]
    for method, path, body in denied:
        if method == "POST":
            r = client.post(path, json=body, headers=headers)
        elif method == "PUT":
            r = client.put(path, json=body, headers=headers)
        elif method == "DELETE":
            r = client.delete(path, headers=headers)
        assert r.status_code == 403, f"viewer {method} {path} -> {r.status_code} {r.text[:200]} (expected 403)"


# ===========================================================================
# 5. analyst 权限
# ===========================================================================
def test_analyst_allowed_writes(client: TestClient, analyst_user):
    headers, _ = analyst_user
    # 每次运行使用唯一关键词，避免与历史残留（唯一约束 word+type）冲突
    kw_word = f"akw_{uuid.uuid4().hex[:8]}"
    # keywords:write
    r = client.post("/api/keywords", json={"word": kw_word, "type": "monitoring", "source": "custom"}, headers=headers)
    assert r.status_code == 201, r.text
    kid = r.json()["id"]
    # events:write
    r = client.post("/api/events/aggregate", headers=headers)
    assert r.status_code == 200, r.text
    # opinions:write（region_id 必须是 Region 真实主键 id，而非 code）
    assert _REGION_ID is not None, "ensure_test_env 未填充 _REGION_ID"
    r = client.post(
        "/api/opinions",
        json={"title": "at", "content": "ac", "source": "as", "url": "http://a", "region_id": _REGION_ID},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    # 清理（analyst 自身具备写权限）
    client.delete(f"/api/keywords/{kid}", headers=headers)
    client.delete(f"/api/opinions/{oid}", headers=headers)


def test_analyst_denied_admin_writes(client: TestClient, analyst_user):
    headers, _ = analyst_user
    denied = [
        ("PUT", "/api/users/999999", {"display_name": "x"}),
        ("POST", "/api/users", {"username": "a_x", "password": "Passw0rd1", "role": "viewer"}),
        ("PUT", "/api/roles/999999", {"display_name": "x"}),
        ("POST", "/api/roles", {"code": "a_x", "name": "a_x", "display_name": "x"}),
        ("POST", "/api/admin/data-sources/test", {
            "key": "test_src_a", "name": "Test", "type": "generic_site",
            "class_path": "app.collectors.generic_site.GenericSiteCollector", "config_json": "{}",
        }),
    ]
    for method, path, body in denied:
        if method == "POST":
            r = client.post(path, json=body, headers=headers)
        else:
            r = client.put(path, json=body, headers=headers)
        assert r.status_code == 403, f"analyst {method} {path} -> {r.status_code} {r.text[:200]} (expected 403)"


# ===========================================================================
# 6. admin 超级管理员
# ===========================================================================
def test_admin_superuser_full_access(client: TestClient, admin_headers: dict):
    r = _login(client, ADMIN_USER, ADMIN_PASS)
    assert r.status_code == 200
    assert r.json()["permissions"] == ["*"], "admin permissions 应为 ['*']"

    for path in ["/api/users", "/api/roles", "/api/permissions", "/api/login-logs", "/api/operation-logs"]:
        r = client.get(path, headers=admin_headers)
        assert r.status_code == 200, f"admin GET {path} -> {r.status_code}"

    # admin 即使 role_permissions=0 仍可写
    r = client.post("/api/keywords", json={"word": f"admin_kw_{uuid.uuid4().hex[:8]}", "type": "monitoring", "source": "custom"}, headers=admin_headers)
    assert r.status_code == 201, r.text
    kid = r.json()["id"]
    # 越权尝试（admin 对不存在资源 PUT，应被授权访问而非 401/403）
    r = client.put("/api/users/999999", json={"display_name": "x"}, headers=admin_headers)
    assert r.status_code not in (401, 403), f"admin PUT non-existent user -> {r.status_code} (应已授权)"
    client.delete(f"/api/keywords/{kid}", headers=admin_headers)


# ===========================================================================
# 7. 越权测试（明确场景）
# ===========================================================================
def test_privilege_escalation_denied(client: TestClient, viewer_user, analyst_user):
    vh, _ = viewer_user
    ah, _ = analyst_user
    scenarios = [
        (vh, "PUT", "/api/keywords/1", {"word": "x"}),
        (vh, "DELETE", "/api/keywords/1", None),
        (vh, "POST", "/api/admin/data-sources/test", {
            "key": "t1", "name": "t", "type": "generic_site",
            "class_path": "app.collectors.generic_site.GenericSiteCollector", "config_json": "{}",
        }),
        (vh, "PUT", "/api/users/1", {"display_name": "x"}),
        (vh, "PUT", "/api/roles/1", {"display_name": "x"}),
        (ah, "PUT", "/api/users/1", {"display_name": "x"}),
        (ah, "PUT", "/api/roles/1", {"display_name": "x"}),
    ]
    for headers, method, path, body in scenarios:
        if method == "PUT":
            r = client.put(path, json=body, headers=headers)
        elif method == "DELETE":
            r = client.delete(path, headers=headers)
        else:
            r = client.post(path, json=body, headers=headers)
        assert r.status_code == 403, f"escalation {method} {path} -> {r.status_code} {r.text[:200]} (expected 403)"


# ===========================================================================
# 8. RBAC 收口回归：collector 收敛 + sources:read 分层 + viewer 领导查看
# ===========================================================================
def test_collector_run_requires_admin(client: TestClient, admin_headers, analyst_user, viewer_user):
    # 未认证 -> 401
    r = client.post("/api/collector/run")
    assert r.status_code == 401, r.status_code
    # 管理员 -> 200（立即返回 task_id，后台异步执行）
    r = client.post("/api/collector/run", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert "task_id" in r.json(), r.text
    # 非管理员（analyst / viewer）-> 403（采集收敛为 admin-only）
    for label, (headers, _) in [("analyst", analyst_user), ("viewer", viewer_user)]:
        r = client.post("/api/collector/run", headers=headers)
        assert r.status_code == 403, f"{label} POST /api/collector/run -> {r.status_code} (expected 403)"


def test_collector_status_login_only(client: TestClient, viewer_user):
    # 状态查询保持登录可读（低风险只读）
    headers, _ = viewer_user
    r = client.get("/api/collector/status", headers=headers)
    assert r.status_code == 200, r.text


def test_data_sources_read_permission_split(client: TestClient, admin_headers, analyst_user, viewer_user):
    # 管理员可读
    r = client.get("/api/admin/data-sources", headers=admin_headers)
    assert r.status_code == 200, r.text
    # analyst 持有 sources:read -> 200
    ah, _ = analyst_user
    r = client.get("/api/admin/data-sources", headers=ah)
    assert r.status_code == 200, r.text
    # viewer 无 sources:read -> 403
    vh, _ = viewer_user
    r = client.get("/api/admin/data-sources", headers=vh)
    assert r.status_code == 403, r.text


def test_viewer_leader_reads_after_migration(client: TestClient, viewer_user):
    """viewer 经迁移获得 alerts:read / propagation:read（领导查看预警与传播）。"""
    headers, _ = viewer_user
    r = _login(client, "rbac_viewer", "Passw0rd1")
    perms = r.json()["permissions"]
    assert "alerts:read" in perms, perms
    assert "propagation:read" in perms, perms
    # 读接口（后端仅校验登录，但权限已授予，前端路由放行）
    for path in ["/api/alerts/records", "/api/propagation/events"]:
        rr = client.get(path, headers=headers)
        assert rr.status_code == 200, f"viewer GET {path} -> {rr.status_code} {rr.text[:200]}"
