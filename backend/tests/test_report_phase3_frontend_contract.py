"""
Phase Report-3 前端体验收口与运行时验收 —— 契约 + 运行时测试。

与 Phase 1 API 契约严格兼容，覆盖：
- export API 契约未破坏（Phase 1 契约兼容）
- 模块参数结构兼容（12 模块 + params 元数据 + default_modules）
- viewer 权限拒绝（403）
- admin 正常导出（200 + application/pdf + size>0）
- 错误响应结构兼容（400 + detail）
- 自定义组合 PDF 运行时章节顺序
  （overview_kpi → top_risky → events → keyword_dist）

说明：
- 全部走 TestClient（真实 app 代码 + 测试库 opinion_test），并以真实 JWT 登录 admin/viewer，
  属于「真实登录用户」的运行时验收；不触碰生产库。
- PDF 章节顺序用 pypdf 从真实生成的 PDF 中提取中文标题校验（已验证 reportlab 输出的中文可被提取）。
"""
import os
import tempfile

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
from pypdf import PdfReader  # noqa: E402

app = _main.app

DEFAULT_MODULES = [
    "overview_kpi", "trend", "sentiment", "top_risky", "events",
    "source_dist", "region_dist", "keyword_dist", "conclusion",
]
ALL_MODULES = set(DEFAULT_MODULES) | {
    "risk_category", "alert_summary", "opinion_list",
}


# ---------------------------------------------------------------------------
# 幂等播种（仅测试库；与 conftest 的 ensure_p1_env 互不冲突）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def ensure_p3_env() -> None:
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

        for code, cname in [("reports:read", "查看报告"), ("reports:export", "导出报告")]:
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
        db.commit()
    finally:
        db.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    """真实登录 admin 并返回 Bearer 请求头。"""
    resp = client.post("/api/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture
def viewer_client() -> TestClient:
    """仅拥有 reports:read 的 viewer（无 reports:export）。复用 Phase 1 验证过的覆盖方式。"""
    fake = User(id=999, username="viewer", role="viewer", is_superuser=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. export API 契约未破坏
# ---------------------------------------------------------------------------
def test_export_api_contract_unchanged(client: TestClient, admin_headers: dict) -> None:
    payload = {
        "name": "契约校验报告",
        "time_field": "created_at",
        "range_type": "last_n_days",
        "range_days": 7,
        "start_date": None,
        "end_date": None,
        "modules": DEFAULT_MODULES,
        "delivery": "download",
    }
    r = client.post("/api/reports/export", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf"), r.headers.get("content-type")
    assert len(r.content) > 0
    assert r.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# 2. 模块参数结构兼容
# ---------------------------------------------------------------------------
def test_modules_param_structure_compatible(client: TestClient, admin_headers: dict) -> None:
    r = client.get("/api/reports/modules", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    mods = body["modules"]
    assert len(mods) == 12
    assert {m["key"] for m in mods} == ALL_MODULES

    for m in mods:
        assert {"key", "name", "title", "description", "default_enabled", "params"}.issubset(m.keys())
        assert isinstance(m["default_enabled"], bool)
        for p in m["params"]:
            assert {"key", "label", "type", "default"}.issubset(p.keys())

    # params 元数据示例：top_risky 含 limit(int)
    tr = next(m for m in mods if m["key"] == "top_risky")
    assert any(p["key"] == "limit" and p["type"] == "int" for p in tr["params"])

    # default_modules 正确（9 个默认启用模块）
    assert body["default_modules"] == DEFAULT_MODULES


# ---------------------------------------------------------------------------
# 3. viewer 权限拒绝
# ---------------------------------------------------------------------------
def test_viewer_export_forbidden(viewer_client: TestClient) -> None:
    payload = {
        "name": "x", "time_field": "created_at", "range_type": "last_n_days",
        "range_days": 7, "start_date": None, "end_date": None,
        "modules": ["overview_kpi"], "delivery": "download",
    }
    assert viewer_client.post("/api/reports/export", json=payload).status_code == 403
    # 但 /modules 可读（reports:read 允许）
    assert viewer_client.get("/api/reports/modules").status_code == 200
    # 旧 /generate 同样 403
    assert viewer_client.post("/api/reports/generate", json=payload).status_code == 403


# ---------------------------------------------------------------------------
# 4. admin 正常导出（发布时间口径 + 全默认模块）
# ---------------------------------------------------------------------------
def test_admin_normal_export_publish_time(client: TestClient, admin_headers: dict) -> None:
    payload = {
        "name": "发布口径报告",
        "time_field": "publish_time",
        "range_type": "last_n_days",
        "range_days": 30,
        "start_date": None,
        "end_date": None,
        "modules": DEFAULT_MODULES,
        "delivery": "download",
    }
    r = client.post("/api/reports/export", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 0
    assert r.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# 5. 错误响应结构兼容（400 + detail）
# ---------------------------------------------------------------------------
def test_error_response_structure_compatible(client: TestClient, admin_headers: dict) -> None:
    # 自定义区间缺日期 -> 400 + detail
    r = client.post("/api/reports/export", json={
        "name": "x", "time_field": "created_at", "range_type": "custom",
        "range_days": 7, "start_date": None, "end_date": None,
        "modules": ["overview_kpi"], "delivery": "download",
    }, headers=admin_headers)
    assert r.status_code == 400, r.text
    detail = r.json().get("detail")
    assert isinstance(detail, str) and detail

    # 不支持的 delivery -> 400 + detail
    r2 = client.post("/api/reports/export", json={
        "name": "x", "time_field": "created_at", "range_type": "last_n_days",
        "range_days": 7, "start_date": None, "end_date": None,
        "modules": ["overview_kpi"], "delivery": "email",
    }, headers=admin_headers)
    assert r2.status_code == 400
    assert isinstance(r2.json().get("detail"), str)


# ---------------------------------------------------------------------------
# 6. 自定义组合 PDF 运行时章节顺序（真实 JWT + 真实生成 PDF）
# ---------------------------------------------------------------------------
def test_custom_combo_pdf_order_runtime(client: TestClient, admin_headers: dict) -> None:
    payload = {
        "name": "自定义组合报告",
        "time_field": "created_at",
        "range_type": "last_n_days",
        "range_days": 30,
        "start_date": None,
        "end_date": None,
        "modules": [
            "overview_kpi",
            {"key": "top_risky", "params": {"limit": 5}},
            {"key": "events", "params": {"limit": 3}},
            {"key": "keyword_dist", "params": {"limit": 10}},
        ],
        "delivery": "download",
    }
    r = client.post("/api/reports/export", json=payload, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert len(r.content) > 0

    # 落盘后用 pypdf 校验章节顺序：一、总体态势 → 二、高风险舆情 → 三、重点事件 → 四、热点关键词
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(r.content)
        path = f.name
    try:
        reader = PdfReader(path)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        markers = ["总体态势", "高风险舆情", "重点事件", "热点关键词"]
        positions = []
        for mk in markers:
            idx = text.find(mk)
            assert idx != -1, f"PDF 未包含章节标记：{mk}\n{text[:500]}"
            positions.append(idx)
        assert positions == sorted(positions), f"章节顺序错误：{positions}"
    finally:
        os.unlink(path)
