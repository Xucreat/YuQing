"""pytest 公共夹具。

关键：必须在导入 app 之前把 DATABASE_URL 指向测试库，
否则 settings（lru_cache）会锁定到其它库。
测试库为本地临时 PostgreSQL（端口 5433）上的 opinion_test。
"""
import os

import pytest

TEST_DB_URL = (
    "postgresql+psycopg://opinion_user:opinion_pass@localhost:5433/opinion_test"
)
# 允许通过环境变量覆盖测试库地址（如本机无 5433 实例时指向同实例的 opinion_test），
# 默认仍指向 5433 的 opinion_test，对原 CI/开发环境零破坏。
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)

# 测试默认采集方式 = mock（离线稳定，不触网政府站）。
# 必须在导入 app / settings（lru_cache）之前注入。
os.environ.setdefault("COLLECTOR_TYPE", "mock")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.main import app  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.region import Region  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


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
