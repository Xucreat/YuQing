"""Phase 2B 驾驶舱统计自测：

- 未登录访问失败（401）
- 登录后访问成功
- total 统计正确
- today 统计正确（依据 created_at）
- high_risk 统计正确（risk_score >= 70）
- keywords TOP 统计正确（逗号拆分）
- trend 近 7 日、无数据日期补齐 count=0

说明：fresh_opinions 夹具会清空测试库 opinions 表（不触碰生产种子
admin / region），保证 total/today 断言为绝对值而非增量。
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.opinion import Opinion


@pytest.fixture
def fresh_opinions() -> None:
    """清空测试库 opinions 表，提供干净基准（不影响生产种子数据）。"""
    db: Session = SessionLocal()
    try:
        db.execute(text("DELETE FROM opinions"))
        db.commit()
    finally:
        db.close()


def _create(opinion_client: TestClient, headers: dict, region_id: int, *, keywords: str = "") -> dict:
    resp = opinion_client.post(
        "/api/opinions",
        json={
            "title": f"dash-{keywords or 'x'}",
            "content": "内容",
            "source": "微博",
            "url": "https://example.com/x",
            "region_id": region_id,
            "keywords": keywords,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_dashboard_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 401, resp.text


def test_dashboard_login_success(
    auth_headers, client: TestClient, fresh_opinions
) -> None:
    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"total", "today", "high_risk", "trend", "keywords"}
    assert body["trend"] is not None
    # 近 7 日，无数据日期补齐 count=0
    assert len(body["trend"]) == 7
    for item in body["trend"]:
        assert set(item.keys()) == {"date", "count"}
        assert isinstance(item["date"], str)
        assert isinstance(item["count"], int)


def test_dashboard_total_correct(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    for _ in range(3):
        _create(client, auth_headers, seeded_region_id)
    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 3


def test_dashboard_today_correct(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    for _ in range(2):
        _create(client, auth_headers, seeded_region_id)
    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["today"] == 2


def test_dashboard_high_risk(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    # 直接经 ORM 写入（API 创建默认 risk_score=0，无法设高风险）
    db: Session = SessionLocal()
    try:
        db.add(
            Opinion(
                title="高危1", content="c", source="s", region_id=seeded_region_id,
                risk_score=85, sentiment="negative",
            )
        )
        db.add(
            Opinion(
                title="高危2", content="c", source="s", region_id=seeded_region_id,
                risk_score=72, sentiment="negative",
            )
        )
        db.add(
            Opinion(
                title="低危", content="c", source="s", region_id=seeded_region_id,
                risk_score=10, sentiment="neutral",
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["high_risk"] == 2
    assert body["total"] == 3  # 全部 3 条均可统计


def test_dashboard_keywords_top(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    # 经 ORM 直接写入（create API 在 Phase2A 未含 keywords 字段，
    # dashboard 统计只读 opinions.keywords，与写入方式无关）
    # 消防,安全 / 消防,事故 / 安全  -> 消防2 安全2 事故1
    db: Session = SessionLocal()
    try:
        db.add(Opinion(title="k1", content="c", source="s", region_id=seeded_region_id,
                       keywords="消防,安全", risk_score=0, sentiment="neutral"))
        db.add(Opinion(title="k2", content="c", source="s", region_id=seeded_region_id,
                       keywords="消防,事故", risk_score=0, sentiment="neutral"))
        db.add(Opinion(title="k3", content="c", source="s", region_id=seeded_region_id,
                       keywords="安全", risk_score=0, sentiment="neutral"))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    kws = {item["word"]: item["count"] for item in resp.json()["keywords"]}
    assert kws.get("消防") == 2
    assert kws.get("安全") == 2
    assert kws.get("事故") == 1
    assert len(resp.json()["keywords"]) <= 10


def test_dashboard_trend_window(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    # 创建 2 条今日舆情（API 默认 created_at=now）
    for _ in range(2):
        _create(client, auth_headers, seeded_region_id)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    trend = resp.json()["trend"]
    assert len(trend) == 7

    # 日期应连续且按升序，末项为今日
    dates = [date.fromisoformat(item["date"]) for item in trend]
    assert dates == [dates[0] + timedelta(days=i) for i in range(7)]
    assert dates[-1] == datetime.now(timezone.utc).date()

    # 今日（末项）count 应为刚创建的 2 条
    assert trend[-1]["count"] == 2

    # 其余无数据日期 count=0（空库仅今日有数据）
    for item in trend[:-1]:
        assert item["count"] == 0
