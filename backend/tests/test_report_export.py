"""Phase Report-1.1 报告导出收口测试（隔离测试库 opinion_test）。

运行方式（仅测试库，绝不指向生产 opinion_db）：
    DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5433/opinion_test' \
    DB_IDENTITY_CHECK=off \
    ./.venv/Scripts/python.exe -m pytest tests/test_report_export.py -v

覆盖：
    1. 无 reports:export 不能生成 -> 403（权限隔离）
    2. 空模块失败 -> 400
    3. PDF 正常生成 -> 200 + PDF 魔数 + 写入 report_records 审计记录
    4. legacy 接口正常 -> /reports/overview 与 /reports/overview/pdf 均 200
    5. 拥有 reports:export 的 analyst 可正常生成（授权端到端验证）

安全边界：所有写操作仅作用于隔离测试库 opinion_test；若 DATABASE_URL 指向生产 opinion_db 整个模块跳过。
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# 护栏：严禁触碰生产库 opinion_db
_DB_URL = os.environ.get("DATABASE_URL", "")
if "opinion_db" in _DB_URL:
    pytest.skip(
        "test_report_export 仅允许在隔离测试库 opinion_test 运行；检测到生产库 opinion_db，已跳过",
        allow_module_level=True,
    )

from app.main import app  # noqa: E402
from app.core.dependencies import get_current_user  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.permission import Permission  # noqa: E402
from app.models.report_record import ReportRecord  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def ensure_test_env() -> None:
    """自洽播种隔离测试库（opinion_test）：admin 用户 + 角色 + 报告权限 + 授权。

    幂等（ON CONFLICT / 存在则跳过）。在已正确迁移的 CI 库上基本为 no-op，
    仅用于让本模块在结构已建、但数据未播种的测试库上也能独立运行。
    不触碰生产 opinion_db。
    """
    db = SessionLocal()
    try:
        # admin 用户（超管，供 auth_headers 登录）
        admin = db.query(User).filter(User.username == "admin").first()
        if admin is None:
            admin = User(username="admin", role="admin", is_superuser=True, is_active=True)
            admin.password_hash = hash_password("admin123")
            db.add(admin)
        elif not admin.password_hash:
            admin.password_hash = hash_password("admin123")

        # 系统角色
        for name, code in [("admin", "admin"), ("analyst", "analyst"), ("viewer", "viewer")]:
            if db.query(Role).filter(Role.name == name).first() is None:
                db.add(Role(name=name, code=code, display_name=name, is_system=True, is_enabled=True))
        db.flush()

        # 报告相关权限目录（幂等；reports:export 已由 p26 迁移播种）
        for code, name in [
            ("reports:read", "查看报告"),
            ("reports:write", "导出报告"),
            ("reports:export", "导出报告"),
        ]:
            if db.query(Permission).filter(Permission.code == code).first() is None:
                action = code.split(":")[1]
                db.add(Permission(
                    code=code, name=name, resource="reports", action=action,
                    group="报告", description=name,
                ))
        db.flush()

        # 角色 -> 权限授权
        def grant(role_name: str, perm_code: str) -> None:
            role = db.query(Role).filter(Role.name == role_name).first()
            perm = db.query(Permission).filter(Permission.code == perm_code).first()
            if role and perm and perm not in role.permissions:
                role.permissions.append(perm)

        grant("viewer", "reports:read")
        grant("analyst", "reports:export")
        grant("analyst", "reports:read")
        db.commit()
    finally:
        db.close()


@pytest.fixture
def viewer_client() -> TestClient:
    """模拟一个仅拥有 reports:read 的 viewer 用户（无 reports:export）。"""
    fake = User(id=999, username="viewer", role="viewer", is_superuser=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def analyst_client() -> TestClient:
    """模拟一个拥有 reports:export 的 analyst 用户。"""
    fake = User(id=998, username="analyst", role="analyst", is_superuser=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _count_records(db, status: str | None = None) -> int:
    q = db.query(ReportRecord)
    if status is not None:
        q = q.filter(ReportRecord.status == status)
    return q.count()


def test_export_requires_reports_export(viewer_client: TestClient) -> None:
    """无 reports:export 权限：生成接口与 legacy PDF 接口均返回 403。"""
    payload = {
        "report_name": "x",
        "time_field": "created_at",
        "days": 7,
        "module_keys": ["overview_kpi", "trend", "sentiment"],
    }
    r1 = viewer_client.post("/api/reports/generate", json=payload)
    assert r1.status_code == 403, r1.text
    r2 = viewer_client.get("/api/reports/overview/pdf?days=7")
    assert r2.status_code == 403, r2.text
    # 仅 reports:read 的预览接口仍可用
    assert viewer_client.get("/api/reports/overview?days=7").status_code == 200
    assert viewer_client.get("/api/reports/modules").status_code == 200


def test_analyst_with_export_can_generate(analyst_client: TestClient) -> None:
    """拥有 reports:export 的 analyst 可正常生成 PDF（授权端到端验证）。"""
    r = analyst_client.post(
        "/api/reports/generate",
        json={
            "report_name": "分析师报告",
            "time_field": "created_at",
            "days": 7,
            "module_keys": ["overview_kpi", "trend", "sentiment"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type") == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_generate_empty_modules_400(client: TestClient, auth_headers: dict) -> None:
    """空模块列表 -> 400。"""
    r = client.post(
        "/api/reports/generate",
        headers=auth_headers,
        json={"report_name": "x", "time_field": "created_at", "days": 7, "module_keys": []},
    )
    assert r.status_code == 400, r.text
    assert "请至少选择一个报告模块" in r.json()["detail"]


def test_generate_pdf_ok_and_records_audit(
    client: TestClient, auth_headers: dict
) -> None:
    """正常生成 PDF：200 + PDF 魔数，并写入 report_records 审计记录（success）。"""
    db = SessionLocal()
    try:
        before = _count_records(db)
        r = client.post(
            "/api/reports/generate",
            headers=auth_headers,
            json={
                "report_name": "测试报告",
                "time_field": "created_at",
                "days": 15,
                "module_keys": [
                    "overview_kpi", "trend", "top_risky",
                    "events", "distribution", "sentiment",
                ],
            },
        )
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type") == "application/pdf"
        assert r.content[:4] == b"%PDF"
        # 审计记录写入
        after = _count_records(db)
        assert after == before + 1, f"期望新增 1 条审计记录，实际 +{after - before}"
        rec = db.query(ReportRecord).order_by(ReportRecord.id.desc()).first()
        assert rec is not None
        assert rec.status == "success"
        assert rec.name == "测试报告"
        assert rec.created_by is not None
        assert rec.config_json.get("module_keys") == [
            "overview_kpi", "trend", "top_risky", "events", "distribution", "sentiment",
        ]
    finally:
        db.close()


def test_legacy_interfaces_ok(client: TestClient, auth_headers: dict) -> None:
    """legacy 接口正常：overview(JSON) 与 overview/pdf(PDF) 均 200。"""
    r1 = client.get("/api/reports/overview?days=7", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    assert "total" in r1.json()

    r2 = client.get("/api/reports/overview/pdf?days=7", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("content-type") == "application/pdf"
    assert r2.content[:4] == b"%PDF"
