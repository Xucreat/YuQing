"""Phase 2B / 指挥大屏 Phase 1 驾驶舱统计自测。

覆盖范围：
- 鉴权（未登录 401）
- stats 数据契约：total/today/high_risk/event_count 累计口径；trend/sentiments/
  sources/regions/hot_keywords 受 days 窗口控制；keywords 兼容字段保留
- regions 省级上卷（province/city/county 混级 -> 仅省级）
- hot_keywords 真实数据源（基于监测关键词表，不读 Opinion.keywords；空数据稳定）
- days 校验（1..90）与窗口语义
- 进程内 TTL 缓存：命中 / 不同参数不串 / 端点不互污染 / 过期重算

说明：fresh_opinions 夹具清空测试库 opinions 表（不触碰生产种子
admin / region / keyword），保证断言为绝对值而非增量。
_autouse _clear_cache 在每个测试前后清空进程内缓存，避免跨测试命中陈旧缓存。
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import cache as cache_mod
from app.core.cache import cache_clear, cache_keys
from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.models.region import Region
from app.services import dashboard_service
from sqlalchemy import text


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个测试前后清空进程内缓存，保证 stats 重新计算（避免跨测试陈旧命中）。"""
    cache_clear()
    yield
    cache_clear()


@pytest.fixture
def fresh_opinions() -> None:
    """清空测试库 opinions 表，提供干净基准（不影响生产种子数据）。

    使用 TRUNCATE ... CASCADE 一并清理引用 opinions 的子表
    （alert_records / event_opinions / propagation_nodes / bocha_leads），
    避免遗留数据导致裸 DELETE 触发外键约束报错。仅清数据、不改表结构。
    """
    db: Session = SessionLocal()
    try:
        db.execute(text("TRUNCATE opinions RESTART IDENTITY CASCADE"))
        db.commit()
    finally:
        db.close()


def _create(client: TestClient, headers: dict, region_id: int, *, keywords: str = "") -> dict:
    import uuid

    resp = client.post(
        "/api/opinions",
        json={
            "title": f"dash-{keywords or 'x'}",
            "content": "内容",
            "source": "微博",
            "url": f"https://example.com/{uuid.uuid4().hex}",
            "region_id": region_id,
            "keywords": keywords,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# 鉴权 & 契约
# ---------------------------------------------------------------------------
def test_dashboard_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 401, resp.text


def test_dashboard_login_success(
    auth_headers, client: TestClient, fresh_opinions
) -> None:
    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # 完整字段集合（含新增 hot_keywords、region_detail，保留兼容字段 keywords）
    assert set(body.keys()) == {
        "total", "today", "high_risk", "event_count", "trend",
        "keywords", "sources", "sentiments", "regions", "region_detail", "hot_keywords",
    }
    assert body["trend"] is not None
    # 默认 days=7，近 7 日，无数据日期补齐 count=0
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
    # high_risk 为累计指标（全量风险水位），不受 days 影响
    db: Session = SessionLocal()
    try:
        db.add(Opinion(title="高危1", content="c", source="s", region_id=seeded_region_id,
                       risk_score=85, sentiment="negative"))
        db.add(Opinion(title="高危2", content="c", source="s", region_id=seeded_region_id,
                       risk_score=72, sentiment="negative"))
        db.add(Opinion(title="低危", content="c", source="s", region_id=seeded_region_id,
                       risk_score=10, sentiment="neutral"))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["high_risk"] == 2
    assert body["total"] == 3


def test_dashboard_keywords_top(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    # keywords 兼容字段：来自 opinions.keywords（敏感词命中集合），全量统计
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
    for _ in range(2):
        _create(client, auth_headers, seeded_region_id)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    trend = resp.json()["trend"]
    assert len(trend) == 7

    dates = [datetime.fromisoformat(item["date"]).date() for item in trend]
    assert dates == [dates[0] + timedelta(days=i) for i in range(7)]
    assert dates[-1] == datetime.now(timezone.utc).date()
    assert trend[-1]["count"] == 2
    for item in trend[:-1]:
        assert item["count"] == 0


# ---------------------------------------------------------------------------
# regions 省级上卷
# ---------------------------------------------------------------------------
def test_regions_provincial_rollup(
    auth_headers, client: TestClient, fresh_opinions
) -> None:
    db: Session = SessionLocal()
    try:
        prov = db.query(Region).filter(Region.code == "130000").first()
        city = db.query(Region).filter(Region.code == "130100").first()
        county = db.query(Region).filter(Region.code == "131028").first()
        prov_id = prov.id
        for r in (prov, city, county):
            db.add(Opinion(title="r", content="c", source="s", region_id=r.id,
                           risk_score=0, sentiment="neutral"))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    regions = resp.json()["regions"]
    names = [r["region_name"] for r in regions]
    # 仅省级，且市/县名不得出现
    assert "河北省" in names
    assert "廊坊市" not in names
    assert "大厂回族自治县" not in names
    # 混级三类 region 全部上卷到河北省，计数 = 3
    hebei = next(r for r in regions if r["region_name"] == "河北省")
    assert hebei["count"] == 3
    assert hebei["region_id"] == prov_id  # 输出省级 region 的 id


# ---------------------------------------------------------------------------
# hot_keywords 真实数据源
# ---------------------------------------------------------------------------
def test_hot_keywords_real_counts(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    db: Session = SessionLocal()
    try:
        db.add(Opinion(title="河北某地事件", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        db.add(Opinion(title="河北另一事件", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        db.add(Opinion(title="河北消防演练", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        db.add(Opinion(title="消防检查", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        # 仅 keywords 字段含「事故」，标题/正文不含任何监测词 -> 不应计入热门
        db.add(Opinion(title="普通新闻", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral",
                       keywords="事故"))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/dashboard/hot-keywords", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["days"] == 7
    items = {it["keyword"]: it["count"] for it in body["items"]}
    assert items.get("河北") == 3   # 3 条标题含「河北」
    assert items.get("消防") == 2   # 2 条含「消防」（含一条同时含河北）
    assert "事故" not in items      # 仅 keywords 字段命中，不计入热门
    # 每条舆情最多计 1 次（去重），且趋势字段存在
    for it in body["items"]:
        assert it["trend"] in ("up", "down", "flat")


def test_hot_keywords_empty_stable(
    auth_headers, client: TestClient, fresh_opinions
) -> None:
    # 无舆情 -> 返回稳定空结构，不 500
    resp = client.get("/api/dashboard/hot-keywords", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["days"] == 7


# ---------------------------------------------------------------------------
# HotWord-1B：category 双模式过滤
# ---------------------------------------------------------------------------
def test_hot_keywords_category_default_compat(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    # 服务层：category=None 必须与省略 category 完全一致（旧行为零回归）
    db: Session = SessionLocal()
    try:
        a = dashboard_service.get_hot_keywords(db, days=7, limit=10)
        b = dashboard_service.get_hot_keywords(db, days=7, limit=10, category=None)
    finally:
        db.close()
    assert a == b
    # API 层：省略 category 正常返回且含 trend 字段
    resp = client.get("/api/dashboard/hot-keywords", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    for it in resp.json()["items"]:
        assert it["trend"] in ("up", "down", "flat")


def test_hot_keywords_category_topic(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    # 模式 B：category=主题 仅返回主题词，排除元词「舆情」与地域词
    db: Session = SessionLocal()
    try:
        db.add(Opinion(title="学校消防安全教育", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        db.add(Opinion(title="城市交通拥堵投诉", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        # 元词「舆情」：仅标题含「舆情」，主题模式应排除该词本身（不计入）
        db.add(Opinion(title="学生舆情事件", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        # 地域词「廊坊/河北」：标题含地域词但不含主题词 -> 不应计入主题词云
        db.add(Opinion(title="河北廊坊征地新闻", content="内容", source="s",
                       region_id=seeded_region_id, risk_score=0, sentiment="neutral"))
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/dashboard/hot-keywords?category=主题", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = {it["keyword"]: it["count"] for it in body["items"]}
    # 主题词正常返回
    assert items.get("教育") == 1
    assert items.get("消防") == 1
    assert items.get("交通") == 1
    assert items.get("投诉") == 1
    assert items.get("征地") == 1
    # 元词「舆情」被展示层过滤：不出现
    assert "舆情" not in items
    # 地域词不计入主题词云
    assert "廊坊" not in items
    assert "河北" not in items
    # trend 字段保留
    for it in body["items"]:
        assert it["trend"] in ("up", "down", "flat")


def test_hot_keywords_category_unknown_returns_empty(
    auth_headers, client: TestClient, fresh_opinions
) -> None:
    # 不存在的分类 -> 返回空列表，不 500
    resp = client.get("/api/dashboard/hot-keywords?category=不存在的分类", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["items"] == []
    assert body["days"] == 7


# ---------------------------------------------------------------------------
# days 校验与窗口语义
# ---------------------------------------------------------------------------
def test_stats_days_validation(auth_headers, client: TestClient) -> None:
    assert client.get("/api/dashboard/stats?days=0", headers=auth_headers).status_code == 422
    assert client.get("/api/dashboard/stats?days=91", headers=auth_headers).status_code == 422
    assert client.get("/api/dashboard/stats?days=1", headers=auth_headers).status_code == 200
    assert client.get("/api/dashboard/stats?days=90", headers=auth_headers).status_code == 200


def test_sentiments_sources_windowed_by_days(
    auth_headers, client: TestClient, fresh_opinions, seeded_region_id
) -> None:
    db: Session = SessionLocal()
    try:
        db.add(Opinion(title="今日负面", content="c", source="微博",
                       region_id=seeded_region_id, risk_score=0, sentiment="negative"))
        old = Opinion(title="历史正面", content="c", source="微信",
                      region_id=seeded_region_id, risk_score=0, sentiment="positive")
        db.add(old)
        db.flush()
        old.created_at = datetime.now(timezone.utc) - timedelta(days=8)  # 窗口外
        db.commit()
    finally:
        db.close()

    resp = client.get("/api/dashboard/stats?days=7", headers=auth_headers)
    body = resp.json()
    labels = {s["label"]: s["count"] for s in body["sentiments"]}
    assert labels.get("negative") == 1
    assert labels.get("positive", 0) == 0  # 8 天前被窗口排除
    sources = {s["source"]: s["count"] for s in body["sources"]}
    assert sources.get("微博") == 1
    assert sources.get("微信", 0) == 0


# ---------------------------------------------------------------------------
# 进程内 TTL 缓存
# ---------------------------------------------------------------------------
def test_dashboard_stats_cache_keys_by_days() -> None:
    cache_clear()
    db: Session = SessionLocal()
    try:
        dashboard_service.get_dashboard_stats(db, days=1)
        dashboard_service.get_dashboard_stats(db, days=7)
        dashboard_service.get_dashboard_stats(db, days=30)
    finally:
        db.close()
    keys = cache_keys()
    # 不同 days -> 不同 key，互不串缓存
    assert "dash:stats:1" in keys
    assert "dash:stats:7" in keys
    assert "dash:stats:30" in keys
    assert len({"dash:stats:1", "dash:stats:7", "dash:stats:30"}) == 3


def test_dashboard_cache_endpoint_isolation() -> None:
    cache_clear()
    db: Session = SessionLocal()
    try:
        dashboard_service.get_dashboard_stats(db, days=7)
        dashboard_service.get_hot_keywords(db, days=7, limit=10)
        dashboard_service.get_recent_opinions(db, limit=8)
        dashboard_service.get_dashboard_alerts(db, limit=8)
    finally:
        db.close()
    keys = cache_keys()
    # 各端点独立 key 前缀，互不污染（hot-keywords 默认 category=None -> '_all' 段）
    assert "dash:stats:7" in keys
    assert "dash:hot:7:10:_all" in keys
    assert "dash:recent:8" in keys
    assert "dash:alerts:8" in keys


def test_dashboard_stats_recompute_after_expiry(monkeypatch) -> None:
    cache_clear()
    db: Session = SessionLocal()
    try:
        dashboard_service.get_dashboard_stats(db, days=7)
        assert "dash:stats:7" in cache_keys()
        # 模拟时间远超 TTL，触发过期重算（不应抛错，返回新对象）
        base = cache_mod.time.time()
        monkeypatch.setattr(cache_mod.time, "time", lambda: base + 1000)
        data = dashboard_service.get_dashboard_stats(db, days=7)
        assert isinstance(data, dict) and "total" in data
    finally:
        db.close()


def test_cache_utility_expiry(monkeypatch) -> None:
    cache_clear()
    real_now = cache_mod.time.time()
    cache_mod.cache_set("k", "v", ttl=1)  # 写入于 real_now
    monkeypatch.setattr(cache_mod.time, "time", lambda: real_now + 0.5)
    assert cache_mod.cache_get("k", ttl=1) == "v"  # 0.5s 内未过期
    monkeypatch.setattr(cache_mod.time, "time", lambda: real_now + 2)
    assert cache_mod.cache_get("k", ttl=1) is None  # 2s 后过期
