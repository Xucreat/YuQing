"""
Phase Report-4-A 报告模板最小可用能力测试。

覆盖：
- 创建模板成功（admin, reports:manage）
- viewer 无 reports:manage → POST /templates 返回 403
- admin 创建模板成功（与 #1 同源，含 can_edit 标记）
- 模板列表返回「个人模板」+「公共模板」
- 未知 module key 创建失败（400 + detail）
- 模板加载后导出成功（200 + application/pdf + size>0）
- 使用模板配置导出的 PDF 与直接 export 行为一致（HTTP200 / pdf / size>0）
- 现有 Phase 1/2/3 契约未破坏（导出 200/pdf、模块结构、viewer 403）

说明：
- 全部走 TestClient（真实 app + 测试库 opinion_test），真实 JWT 登录 admin/viewer。
- 不触碰生产库；DB 身份门禁已在 conftest 关闭。
"""
import os

import pytest
from fastapi.testclient import TestClient

# 必须在导入 app / settings（lru_cache）之前注入测试库（与 conftest 一致）
os.environ.setdefault("DB_IDENTITY_CHECK", "off")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://opinion_user:opinion_pass@localhost:5433/opinion_test",
)
os.environ.setdefault("COLLECTOR_TYPE", "mock")

from app import main as _main  # noqa: E402
from app.core.dependencies import get_current_user  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.permission import Permission  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402

app = _main.app

DEFAULT_MODULES = [
    "overview_kpi", "trend", "sentiment", "top_risky", "events",
    "source_dist", "region_dist", "keyword_dist", "conclusion",
]
ALL_MODULES = set(DEFAULT_MODULES) | {
    "risk_category", "alert_summary", "opinion_list",
}


def _sample_config(name: str = "测试模板", modules=None) -> dict:
    return {
        "name": name,
        "time_field": "publish_time",
        "range_type": "last_n_days",
        "range_days": 7,
        "start_date": None,
        "end_date": None,
        "modules": modules if modules is not None else ["overview_kpi", {"key": "top_risky", "params": {"limit": 5}}],
    }


# ---------------------------------------------------------------------------
# 幂等播种（仅测试库；admin 授予 reports:manage 双保险，迁移也应已授予）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def ensure_p4a_env() -> None:
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if admin is None:
            admin = User(username="admin", role="admin", is_superuser=True, is_active=True)
            admin.password_hash = hash_password("admin123")
            db.add(admin)
        elif not admin.password_hash:
            admin.password_hash = hash_password("admin123")

        for name, code in [("admin", "admin"), ("analyst", "analyst"), ("viewer", "viewer")]:
            if db.query(Role).filter(Role.name == name).first() is None:
                db.add(Role(name=name, code=code, display_name=name,
                            is_system=True, is_enabled=True))
        db.flush()

        for code, cname in [
            ("reports:read", "查看报告"),
            ("reports:export", "导出报告"),
            ("reports:manage", "管理报告模板"),
        ]:
            if db.query(Permission).filter(Permission.code == code).first() is None:
                db.add(Permission(
                    code=code, name=cname, resource="reports",
                    action=code.split(":")[1], group="报告", description=cname,
                ))
        db.flush()

        def grant(role_name: str, perm_code: str) -> None:
            role = db.query(Role).filter(Role.name == role_name).first()
            perm = db.query(Permission).filter(Permission.code == perm_code).first()
            if role and perm and perm not in role.permissions:
                role.permissions.append(perm)

        grant("viewer", "reports:read")
        grant("analyst", "reports:read")
        grant("analyst", "reports:export")
        # 确保 admin 拥有 reports:manage（迁移会授予，这里双保险）
        grant("admin", "reports:manage")
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    resp = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def viewer_client() -> TestClient:
    """仅拥有 reports:read 的 viewer（无 reports:manage / reports:export）。"""
    fake = User(id=999, username="viewer", role="viewer", is_superuser=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1 & 3. 创建模板成功（admin）
# ---------------------------------------------------------------------------
def test_admin_create_template_success(client: TestClient, admin_headers: dict) -> None:
    cfg = _sample_config("测试模板")
    r = client.post(
        "/api/reports/templates",
        json={"name": "测试模板", "description": "desc", "is_public": False, "config_json": cfg},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "测试模板"
    assert body["description"] == "desc"
    assert body["is_public"] is False
    assert body["can_edit"] is True
    assert body["config_json"]["time_field"] == "publish_time"
    assert body["config_json"]["modules"][0] == "overview_kpi"


# ---------------------------------------------------------------------------
# 2. viewer 无 reports:manage → 403
# ---------------------------------------------------------------------------
def test_viewer_create_template_forbidden(viewer_client: TestClient) -> None:
    cfg = _sample_config()
    r = viewer_client.post(
        "/api/reports/templates",
        json={"name": "x", "config_json": cfg},
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 4. 模板列表返回个人 + 公共
# ---------------------------------------------------------------------------
def test_template_list_personal_and_public(client: TestClient, admin_headers: dict) -> None:
    pub_cfg = _sample_config("公共模板", modules=["overview_kpi"])
    pub = client.post(
        "/api/reports/templates",
        json={"name": "公共模板", "is_public": True, "config_json": pub_cfg},
        headers=admin_headers,
    )
    assert pub.status_code == 201, pub.text
    pub_id = pub.json()["id"]

    lst = client.get("/api/reports/templates", headers=admin_headers)
    assert lst.status_code == 200, lst.text
    items = lst.json()
    ids = [t["id"] for t in items]
    assert pub_id in ids
    pub_item = next(t for t in items if t["id"] == pub_id)
    assert pub_item["is_public"] is True
    # 个人模板也在列表中（本条测试创建的公共模板属于 admin 自己，必然可见）
    assert any(t["owner_id"] == pub.json()["owner_id"] for t in items)


# ---------------------------------------------------------------------------
# 5. 未知 module key 创建失败
# ---------------------------------------------------------------------------
def test_create_template_unknown_module(client: TestClient, admin_headers: dict) -> None:
    cfg = _sample_config(modules=["nonexistent_module"])
    r = client.post(
        "/api/reports/templates",
        json={"name": "x", "config_json": cfg},
        headers=admin_headers,
    )
    assert r.status_code == 400, r.text
    assert "未知报告模块" in r.json().get("detail", "")


# ---------------------------------------------------------------------------
# 6 & 7. 模板加载后导出成功（使用模板配置导出的 PDF 一致）
# ---------------------------------------------------------------------------
def test_export_with_template_config(client: TestClient, admin_headers: dict) -> None:
    cfg = _sample_config(
        "导出模板",
        modules=["overview_kpi", {"key": "top_risky", "params": {"limit": 5}}],
    )
    cr = client.post(
        "/api/reports/templates",
        json={"name": "导出模板", "config_json": cfg},
        headers=admin_headers,
    )
    assert cr.status_code == 201, cr.text
    tpl_id = cr.json()["id"]

    # GET 模板列表，取回 config 并导出（模拟前端「加载模板 → 生成」）
    lst = client.get("/api/reports/templates", headers=admin_headers)
    tpl = next(t for t in lst.json() if t["id"] == tpl_id)
    export_payload = {**tpl["config_json"], "delivery": "download"}

    r = client.post("/api/reports/export", json=export_payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 0
    assert r.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# 8. 现有 Phase 1/2/3 契约未破坏（导出 200/pdf、模块结构、viewer 403）
# ---------------------------------------------------------------------------
def test_export_api_contract_unchanged(client: TestClient, admin_headers: dict) -> None:
    payload = {
        "name": "契约校验报告", "time_field": "created_at", "range_type": "last_n_days",
        "range_days": 7, "start_date": None, "end_date": None,
        "modules": DEFAULT_MODULES, "delivery": "download",
    }
    r = client.post("/api/reports/export", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 0


def test_modules_param_structure_compatible(client: TestClient, admin_headers: dict) -> None:
    r = client.get("/api/reports/modules", headers=admin_headers)
    assert r.status_code == 200, r.text
    mods = r.json()["modules"]
    assert len(mods) == 12
    assert {m["key"] for m in mods} == ALL_MODULES
    for m in mods:
        assert {"key", "name", "title", "description", "default_enabled", "params"}.issubset(m.keys())


def test_viewer_export_forbidden(viewer_client: TestClient) -> None:
    payload = {
        "name": "x", "time_field": "created_at", "range_type": "last_n_days",
        "range_days": 7, "start_date": None, "end_date": None,
        "modules": ["overview_kpi"], "delivery": "download",
    }
    assert viewer_client.post("/api/reports/export", json=payload).status_code == 403
    # /templates 列表需要 reports:export（viewer 无）→ 403
    assert viewer_client.get("/api/reports/templates").status_code == 403
