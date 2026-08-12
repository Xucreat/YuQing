"""pytest 公共夹具。

关键：必须在导入 app 之前把 DATABASE_URL 指向测试库，
否则 settings（lru_cache）会锁定到其它库。
测试库为本地临时 PostgreSQL（端口 5433）上的 opinion_test。
"""
import os
import time

import pytest

TEST_DB_URL = (
    "postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5433/opinion_test"
)
# 允许通过环境变量覆盖测试库地址（如本机无 5433 实例时指向同实例的 opinion_test），
# 默认仍指向 5433 的 opinion_test，对原 CI/开发环境零破坏。

# RBAC-2A：测试库（opinion_test）是独立于生产库的 cluster，system_identifier 不同，
# 数据库身份门禁会因此中止。测试为已知安全场景，显式关闭门禁以避免误伤。
os.environ.setdefault("DB_IDENTITY_CHECK", "off")
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
# Tests that exercise the fallback path must never inherit a developer or
# production DeepSeek key. Tests covering the configured provider set the
# provider/settings explicitly with monkeypatch.
os.environ["DEEPSEEK_API_KEY"] = ""

# 测试默认采集方式 = mock（离线稳定，不触网政府站）。
# 必须在导入 app / settings（lru_cache）之前注入。
os.environ.setdefault("COLLECTOR_TYPE", "mock")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.main import app  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.core import task_manager  # noqa: E402
from app.models.keyword import Keyword  # noqa: E402
from app.models.report_template import ReportTemplate  # noqa: E402
from app.models.region import Region  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _wait_for_background_tasks(timeout: float = 10.0) -> None:
    """Keep fixture cleanup from racing task-manager worker writes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with task_manager._tasks_lock:
            running = any(
                task.status in (task_manager.STATUS_PENDING, task_manager.STATUS_RUNNING)
                for task in task_manager._tasks.values()
            )
        if not running:
            return
        time.sleep(0.05)


@pytest.fixture(autouse=True)
def restore_keyword_lexicon():
    """Restore the domestic keyword rows after every test.

    A number of legacy integration tests exercise keyword CRUD without
    cleaning up on assertion failure.  Keeping the exact seeded rows (and
    IDs, including the rule-config row) prevents those tests from changing
    the contract observed by later governance tests in the same run.
    """
    _wait_for_background_tasks()
    db = SessionLocal()
    try:
        columns = [column.name for column in Keyword.__table__.columns]
        snapshot = [
            {name: getattr(row, name) for name in columns}
            for row in db.query(Keyword).order_by(Keyword.id).all()
        ]
    finally:
        db.close()

    yield

    _wait_for_background_tasks()
    db = SessionLocal()
    try:
        db.query(Keyword).delete(synchronize_session=False)
        db.bulk_insert_mappings(Keyword, snapshot)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture(autouse=True)
def isolate_report_templates():
    """Keep fixed-name report-template integration fixtures independent."""
    _wait_for_background_tasks()
    db = SessionLocal()
    try:
        db.query(ReportTemplate).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    yield
    _wait_for_background_tasks()
    db = SessionLocal()
    try:
        db.query(ReportTemplate).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """登录 admin 并返回带 Bearer Token 的请求头。"""
    resp = client.post(
        "/api/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seeded_region_id() -> int:
    """返回初始化种子数据中的大厂回族自治县(131028) id。"""
    db: Session = SessionLocal()
    try:
        region = db.query(Region).filter(Region.code == "131028").first()
        assert region is not None, "种子区域 131028 未初始化"
        return region.id
    finally:
        db.close()
