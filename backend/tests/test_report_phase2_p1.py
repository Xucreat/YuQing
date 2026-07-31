"""Phase Report-2-P1 模块化重构测试（隔离测试库 opinion_test）。

运行方式（仅测试库，绝不指向生产 opinion_db）：
    DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5433/opinion_test' \
    DB_IDENTITY_CHECK=off \
    ./.venv/Scripts/python.exe -m pytest tests/test_report_phase2_p1.py -v

覆盖（对应 Phase 1 测试要求 1~8）：
    1. created_at 时间过滤正确
    2. publish_time 有值时使用 publish_time
    3. publish_time NULL 时回退 created_at（COALESCE）
    4. 00:00-08:00 本地时间归属正确（方案 A：本地日期语义，非 UTC 转换）
    5. 模块任意组合 / 任意顺序生成 PDF
    6. 单模块异常（取数 / 渲染）不导致整体失败
    7. legacy POST /reports/generate 仍可正常工作
    8. viewer 调用 POST /reports/export 返回 403

安全边界：所有写操作仅作用于隔离测试库 opinion_test；若 DATABASE_URL 指向生产库整个模块跳过。
测试数据在 fixture 结束时按 id 精确删除，不修改任何既有业务数据。
"""
from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta

import pytest
from fastapi.testclient import TestClient

# 护栏：严禁触碰生产库 opinion_db
_DB_URL = os.environ.get("DATABASE_URL", "")
if "opinion_db" in _DB_URL:
    pytest.skip(
        "test_report_phase2_p1 仅允许在隔离测试库 opinion_test 运行；检测到生产库 opinion_db，已跳过",
        allow_module_level=True,
    )

from app.main import app  # noqa: E402
from app.core.dependencies import get_current_user  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.opinion import Opinion  # noqa: E402
from app.models.permission import Permission  # noqa: E402
from app.models.region import Region  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services import report_service as rs  # noqa: E402
from app.services.report_service import (  # noqa: E402
    ALL_MODULE_KEYS,
    DEFAULT_MODULE_KEYS,
    MODULE_MAP,
    REPORT_MODULES,
    ReportConfig,
    build_report,
    expand_module_keys,
    render_report_pdf,
)


# ---------------------------------------------------------------------------
# 环境播种（幂等，仅测试库）
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def ensure_p1_env() -> None:
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
                db.add(Role(name=name, code=code, display_name=name, is_system=True, is_enabled=True))
        db.flush()

        for code, cname in [
            ("reports:read", "查看报告"),
            ("reports:export", "导出报告"),
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
        db.commit()
    finally:
        db.close()


@pytest.fixture
def viewer_client() -> TestClient:
    """仅拥有 reports:read 的 viewer（无 reports:export）。"""
    fake = User(id=999, username="viewer", role="viewer", is_superuser=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: fake
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 时间口径样本（本地时间语义，直接写 naive datetime）
# ---------------------------------------------------------------------------
@pytest.fixture
def time_samples():
    """插入 3 条时间口径样本并在结束后精确删除。

    今天 = T，昨天 = Y（均为数据库 current_date 本地日期）：
      A  created_at = T 03:00（凌晨）   publish_time = NULL      -> 发布口径回退 T 03:00
      B  created_at = T 12:00          publish_time = Y 23:30   -> 发布口径落在 Y
      C  created_at = T 23:30          publish_time = T 07:00   -> 发布口径落在 T（凌晨段）
    """
    db = SessionLocal()
    ids: list[int] = []
    try:
        today: date = db.execute(rs.select(rs.func.current_date())).scalar()
        yesterday = today - timedelta(days=1)
        region = db.query(Region).first()
        assert region is not None, "测试库缺少 regions 种子数据"

        rows = [
            Opinion(
                title="P1时间口径样本A", content="", source="pytest-p1", url="",
                region_id=region.id, risk_score=80, sentiment="negative",
                summary="", keywords="测试,凌晨",
                created_at=datetime.combine(today, time(3, 0)),
                publish_time=None,
            ),
            Opinion(
                title="P1时间口径样本B", content="", source="pytest-p1", url="",
                region_id=region.id, risk_score=10, sentiment="neutral",
                summary="", keywords="测试",
                created_at=datetime.combine(today, time(12, 0)),
                publish_time=datetime.combine(yesterday, time(23, 30)),
            ),
            Opinion(
                title="P1时间口径样本C", content="", source="pytest-p1", url="",
                region_id=region.id, risk_score=90, sentiment="negative",
                summary="", keywords="测试,凌晨",
                created_at=datetime.combine(today, time(23, 30)),
                publish_time=datetime.combine(today, time(7, 0)),
            ),
        ]
        db.add_all(rows)
        db.commit()
        ids = [r.id for r in rows]
        yield {"today": today, "yesterday": yesterday, "ids": ids,
               "a": ids[0], "b": ids[1], "c": ids[2]}
    finally:
        if ids:
            db.query(Opinion).filter(Opinion.id.in_(ids)).delete(synchronize_session=False)
            db.commit()
        db.close()


def _kpi_total(db, time_field: str, d0: date, d1: date) -> int:
    cfg = ReportConfig(
        time_field=time_field,
        start_date=d0.isoformat(), end_date=d1.isoformat(),
        module_keys=["overview_kpi"],
    )
    rep = build_report(db, cfg)
    assert rep["modules"][0]["error"] is None
    return rep["modules"][0]["data"]["total"]


def _list_ids(db, time_field: str, d0: date, d1: date) -> set[int]:
    cfg = ReportConfig(
        time_field=time_field,
        start_date=d0.isoformat(), end_date=d1.isoformat(),
        module_keys=["opinion_list"],
        module_params={"opinion_list": {"limit": 200}},
    )
    rep = build_report(db, cfg)
    assert rep["modules"][0]["error"] is None
    return {i["id"] for i in rep["modules"][0]["data"]["items"]}


# ---------------------------------------------------------------------------
# 1 / 4：created_at 过滤 + 00:00-08:00 本地归属
# ---------------------------------------------------------------------------
def test_created_at_filter_and_early_morning_local_attribution(time_samples) -> None:
    db = SessionLocal()
    try:
        t, y = time_samples["today"], time_samples["yesterday"]
        ids_today = _list_ids(db, "created_at", t, t)
        # A(03:00) / B(12:00) / C(23:30) 全部归属「今天」——本地日期语义
        assert {time_samples["a"], time_samples["b"], time_samples["c"]} <= ids_today
        # 若误做 -8h UTC 转换，03:00 会被划到昨天：显式断言不会发生
        ids_yesterday = _list_ids(db, "created_at", y, y)
        assert time_samples["a"] not in ids_yesterday
        assert not ({time_samples["b"], time_samples["c"]} & ids_yesterday)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2 / 3：publish_time 有值用 publish_time，NULL 回退 created_at
# ---------------------------------------------------------------------------
def test_publish_time_used_when_present_and_fallback_when_null(time_samples) -> None:
    db = SessionLocal()
    try:
        t, y = time_samples["today"], time_samples["yesterday"]
        pub_today = _list_ids(db, "publish_time", t, t)
        pub_yesterday = _list_ids(db, "publish_time", y, y)

        # A：publish_time 为 NULL -> 回退 created_at(T 03:00) -> 落在今天
        assert time_samples["a"] in pub_today
        assert time_samples["a"] not in pub_yesterday
        # B：publish_time=Y 23:30 有值 -> 落在昨天（不是 created_at 的今天）
        assert time_samples["b"] in pub_yesterday
        assert time_samples["b"] not in pub_today
        # C：publish_time=T 07:00（凌晨段）有值 -> 落在今天
        assert time_samples["c"] in pub_today
    finally:
        db.close()


def test_publish_time_window_counts(time_samples) -> None:
    """口径差异必须体现在 KPI 总数上：采集口径 +3，发布口径 +2。"""
    db = SessionLocal()
    try:
        t = time_samples["today"]
        created_ids = _list_ids(db, "created_at", t, t)
        publish_ids = _list_ids(db, "publish_time", t, t)
        mine = set(time_samples["ids"])
        assert len(created_ids & mine) == 3
        assert len(publish_ids & mine) == 2
        # KPI 模块与明细模块口径一致
        assert _kpi_total(db, "created_at", t, t) >= 3
        assert _kpi_total(db, "publish_time", t, t) >= 2
    finally:
        db.close()


def test_no_null_publish_time_data_is_dropped(time_samples) -> None:
    """COALESCE 口径下，publish_time 为 NULL 的数据不得被丢弃。"""
    db = SessionLocal()
    try:
        t = time_samples["today"]
        total_created = db.scalar(
            rs.select(rs.func.count(Opinion.id)).where(
                rs._time_filter(rs._time_column("created_at"), t, t)
            )
        )
        total_publish_all = db.scalar(
            rs.select(rs.func.count(Opinion.id)).where(
                rs._time_filter(rs._time_column("publish_time"), t - timedelta(days=3650), t + timedelta(days=1))
            )
        )
        total_rows = db.scalar(rs.select(rs.func.count(Opinion.id)))
        assert total_created >= 3
        # 足够宽的发布口径窗口应覆盖全部数据（无 NULL 丢失）
        assert total_publish_all == total_rows
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5：模块任意组合 / 任意顺序
# ---------------------------------------------------------------------------
def test_registry_has_12_modules_and_defaults() -> None:
    assert len(REPORT_MODULES) == 12
    assert ALL_MODULE_KEYS == [
        "overview_kpi", "trend", "sentiment", "top_risky", "events",
        "source_dist", "region_dist", "keyword_dist", "risk_category",
        "alert_summary", "opinion_list", "conclusion",
    ]
    assert "distribution" not in ALL_MODULE_KEYS
    for m in REPORT_MODULES:
        for f in ("key", "name", "title", "description", "data_fn", "render_fn",
                  "default_enabled", "params"):
            assert f in m, f"模块 {m.get('key')} 缺少字段 {f}"
    assert DEFAULT_MODULE_KEYS and set(DEFAULT_MODULE_KEYS) <= set(ALL_MODULE_KEYS)


def test_all_modules_pdf() -> None:
    db = SessionLocal()
    try:
        cfg = ReportConfig(report_name="全模块报告", days=7, module_keys=list(ALL_MODULE_KEYS))
        rep = build_report(db, cfg)
        assert [m["key"] for m in rep["modules"]] == list(ALL_MODULE_KEYS)
        assert rep["meta"]["failed_modules"] == [], rep["meta"]["failed_modules"]
        pdf = render_report_pdf(rep)
        assert pdf[:4] == b"%PDF" and len(pdf) > 3000
    finally:
        db.close()


def test_subset_and_reordered_modules_pdf() -> None:
    db = SessionLocal()
    try:
        order = ["conclusion", "sentiment", "overview_kpi"]
        rep = build_report(db, ReportConfig(report_name="子集乱序", days=7, module_keys=order))
        # 章节顺序 = 用户提交顺序
        assert [m["key"] for m in rep["modules"]] == order
        pdf = render_report_pdf(rep)
        assert pdf[:4] == b"%PDF"
    finally:
        db.close()


def test_distribution_alias_expanded() -> None:
    assert expand_module_keys(["distribution"]) == ["source_dist", "region_dist", "keyword_dist"]
    # 去重且保序
    assert expand_module_keys(["overview_kpi", "distribution", "source_dist"]) == [
        "overview_kpi", "source_dist", "region_dist", "keyword_dist",
    ]
    db = SessionLocal()
    try:
        rep = build_report(db, ReportConfig(days=7, module_keys=["distribution"]))
        assert [m["key"] for m in rep["modules"]] == ["source_dist", "region_dist", "keyword_dist"]
        assert render_report_pdf(rep)[:4] == b"%PDF"
    finally:
        db.close()


def test_module_params_applied() -> None:
    db = SessionLocal()
    try:
        rep = build_report(db, ReportConfig(
            days=30, module_keys=["opinion_list"],
            module_params={"opinion_list": {"limit": 3}},
        ))
        assert len(rep["modules"][0]["data"]["items"]) <= 3
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6：单模块异常隔离
# ---------------------------------------------------------------------------
def test_data_fn_failure_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(db, ws, we, col, params=None):
        raise RuntimeError("模拟取数异常")

    monkeypatch.setitem(MODULE_MAP["trend"], "data_fn", boom)
    db = SessionLocal()
    try:
        rep = build_report(db, ReportConfig(
            days=7, module_keys=["overview_kpi", "trend", "sentiment"]
        ))
        keys = [m["key"] for m in rep["modules"]]
        assert keys == ["overview_kpi", "trend", "sentiment"]
        assert rep["modules"][1]["error"] is not None
        assert "模拟取数异常" in rep["modules"][1]["error"]
        assert rep["meta"]["failed_modules"] == ["trend"]
        # 其余模块仍取到数据
        assert rep["modules"][0]["error"] is None and "total" in rep["modules"][0]["data"]
        assert rep["modules"][2]["error"] is None
        pdf = render_report_pdf(rep)
        assert pdf[:4] == b"%PDF"
    finally:
        db.close()


def test_render_fn_failure_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(flow, d, ctx):
        raise RuntimeError("模拟渲染异常")

    monkeypatch.setitem(MODULE_MAP["sentiment"], "render_fn", boom)
    db = SessionLocal()
    try:
        rep = build_report(db, ReportConfig(days=7, module_keys=["overview_kpi", "sentiment"]))
        pdf = render_report_pdf(rep)
        assert pdf[:4] == b"%PDF"
    finally:
        db.close()


def test_export_api_not_500_when_module_fails(
    client: TestClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(db, ws, we, col, params=None):
        raise RuntimeError("模拟取数异常")

    monkeypatch.setitem(MODULE_MAP["trend"], "data_fn", boom)
    r = client.post(
        "/api/reports/export",
        headers=auth_headers,
        json={"name": "隔离测试", "time_field": "created_at", "range_type": "last_n_days",
              "range_days": 7, "modules": ["overview_kpi", "trend"]},
    )
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert r.headers.get("X-Report-Failed-Modules") == "trend"


# ---------------------------------------------------------------------------
# 接口层：/modules、/export、legacy /generate、权限
# ---------------------------------------------------------------------------
def test_modules_endpoint_contract(client: TestClient, auth_headers: dict) -> None:
    r = client.get("/api/reports/modules", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["modules"]) == 12
    keys = [m["key"] for m in body["modules"]]
    assert "distribution" not in keys
    m0 = body["modules"][0]
    for f in ("key", "name", "title", "description", "default_enabled", "params"):
        assert f in m0
    assert set(body["default_modules"]) <= set(keys)


def test_export_download_ok(client: TestClient, auth_headers: dict) -> None:
    r = client.post(
        "/api/reports/export",
        headers=auth_headers,
        json={
            "name": "P1导出测试", "time_field": "publish_time",
            "range_type": "last_n_days", "range_days": 15,
            "modules": ["overview_kpi", {"key": "top_risky", "params": {"limit": 5}}, "conclusion"],
            "delivery": "download",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type") == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_export_custom_range_validation(client: TestClient, auth_headers: dict) -> None:
    r = client.post(
        "/api/reports/export",
        headers=auth_headers,
        json={"name": "x", "range_type": "custom", "modules": ["overview_kpi"]},
    )
    assert r.status_code == 400
    assert "start_date" in r.json()["detail"]


def test_export_empty_and_unknown_modules(client: TestClient, auth_headers: dict) -> None:
    r1 = client.post("/api/reports/export", headers=auth_headers,
                     json={"name": "x", "modules": []})
    assert r1.status_code == 400 and "至少选择一个" in r1.json()["detail"]
    r2 = client.post("/api/reports/export", headers=auth_headers,
                     json={"name": "x", "modules": ["not_exists"]})
    assert r2.status_code == 400 and "未知报告模块" in r2.json()["detail"]


def test_export_email_delivery_rejected(client: TestClient, auth_headers: dict) -> None:
    r = client.post(
        "/api/reports/export", headers=auth_headers,
        json={"name": "x", "modules": ["overview_kpi"], "delivery": "email",
              "recipients": ["a@b.com"]},
    )
    assert r.status_code == 400 and "download" in r.json()["detail"]


def test_legacy_generate_still_works(client: TestClient, auth_headers: dict) -> None:
    """7：旧接口 POST /reports/generate 仍可正常工作（含历史 distribution key）。"""
    r = client.post(
        "/api/reports/generate",
        headers=auth_headers,
        json={"report_name": "legacy兼容", "time_field": "created_at", "days": 7,
              "module_keys": ["overview_kpi", "distribution", "sentiment"]},
    )
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_viewer_export_forbidden(viewer_client: TestClient) -> None:
    """8：viewer 调用 export 返回 403，但 /modules 仍可读。"""
    r = viewer_client.post(
        "/api/reports/export",
        json={"name": "x", "modules": ["overview_kpi"]},
    )
    assert r.status_code == 403, r.text
    assert viewer_client.get("/api/reports/modules").status_code == 200
