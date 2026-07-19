"""Phase 3A 自测：Collector 数据采集 + 自动入库闭环。

使用真实 PostgreSQL 测试库（opinion_test@127.0.0.1:5433）。
覆盖验收：
1. MockCollector >=50 条；高风险项经 fallback 生成 negative / risk>=70 / keywords 非空
2. API 首次运行创建数据（created>=50，analyzed==created）
3. API 二次运行 URL 去重，不重复插入（created==0）
4. AI 失败单条 failed，不影响其他数据（created=3, analyzed=2, failed=1）
5. API 鉴权：无 token -> 401
6. API 返回 created / analyzed 正确（及 /status 结构与鉴权）
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector
from app.collectors.service import CollectorService
from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.services.ai import AIService


def _clean_source(db: Session, source: str) -> None:
    db.query(Opinion).filter(Opinion.source == source).delete()
    db.commit()


def _count_source(db: Session, source: str) -> int:
    return db.query(Opinion).filter(Opinion.source == source).count()


# MockCollector 生成的舆情以 url 前缀标识（其 source 字段为真实媒体名，
# 并非 "mock"，故去重/清理均以 url 前缀判断）。
MOCK_URL_PREFIX = "https://mock.dachang.gov/opinion/"


def _clean_mock(db: Session) -> None:
    db.query(Opinion).filter(Opinion.url.like(MOCK_URL_PREFIX + "%")).delete(
        synchronize_session=False
    )
    db.commit()


def _count_mock(db: Session) -> int:
    return db.query(Opinion).filter(
        Opinion.url.like(MOCK_URL_PREFIX + "%")
    ).count()


# ---------------------------------------------------------------------------
# 1) MockCollector 数据量与高风险 fallback 表现
# ---------------------------------------------------------------------------
def test_mock_collector_volume_and_high_risk() -> None:
    from app.collectors.mock_collector import MockCollector

    items = MockCollector().fetch()
    assert len(items) >= 50, f"MockCollector 应 >=50 条，实际 {len(items)}"
    # 每条必须有唯一 url（去重主键）
    urls = [it.get("url") for it in items]
    assert all(urls), "存在空 url 的 mock 数据"
    assert len(set(urls)) == len(urls), "mock url 不唯一，去重测试将失效"

    # 经 fallback 分析，至少 3 条高风险（negative + risk>=70 + keywords 非空）
    ai = AIService()
    analyses = [(it, ai.analyze(it["title"], it["content"])) for it in items]
    high = [a for _, a in analyses if a.risk_score >= 70]
    assert len(high) >= 3, f"高风险(mocked)条数不足，仅 {len(high)}"
    for a in high:
        assert a.sentiment == "negative"
        assert a.keywords, "高风险项 keywords 不应为空"


# ---------------------------------------------------------------------------
# 2) API 首次运行创建数据
# ---------------------------------------------------------------------------
def test_collector_run_creates(client: TestClient, auth_headers) -> None:
    db = SessionLocal()
    try:
        _clean_mock(db)
    finally:
        db.close()

    resp = client.post("/api/collector/run", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["created"] >= 50, body
    # 无 DeepSeek Key -> 全程 fallback，不会失败
    assert body["analyzed"] == body["created"], body
    assert body["failed"] == 0, body

    db = SessionLocal()
    try:
        assert _count_mock(db) == body["created"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3) API 二次运行 URL 去重，不重复插入
# ---------------------------------------------------------------------------
def test_collector_run_dedup_by_url(client: TestClient, auth_headers) -> None:
    db = SessionLocal()
    try:
        _clean_mock(db)
    finally:
        db.close()

    # 第一次：应创建
    r1 = client.post("/api/collector/run", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    created_first = r1.json()["created"]
    assert created_first >= 50, r1.json()

    # 第二次：同一批 url 已存在，不重复插入
    r2 = client.post("/api/collector/run", headers=auth_headers)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["created"] == 0, body2
    assert body2["analyzed"] == 0, body2

    db = SessionLocal()
    try:
        # 库中 mock 数量未增加
        assert _count_mock(db) == created_first
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4) AI 失败单条 failed，不影响其他数据
# ---------------------------------------------------------------------------
def test_collector_ai_failure_isolated(monkeypatch) -> None:
    class _FailingCollector(BaseCollector):
        source_name = "test"

        def fetch(self):
            return [
                {"title": "正常服务A", "content": "社区便民服务活动", "source": "test",
                 "url": "https://test.local/a", "publish_time": datetime(2026, 7, 16, 9, 0, 0)},
                {"title": "正常服务B", "content": "城区道路修缮完成通车", "source": "test",
                 "url": "https://test.local/b", "publish_time": datetime(2026, 7, 16, 9, 1, 0)},
                {"title": "需失败C", "content": "触发AI失败", "source": "test",
                 "url": "https://test.local/c", "publish_time": datetime(2026, 7, 16, 9, 2, 0)},
            ]

    _orig_analyze = AIService.analyze

    def _fake_analyze(self, title: str, content: str):
        if "需失败" in title:
            raise RuntimeError("simulated AI failure")
        return _orig_analyze(self, title, content)

    monkeypatch.setattr(AIService, "analyze", _fake_analyze)

    db = SessionLocal()
    try:
        _clean_source(db, "test")
        svc = CollectorService(collectors=[_FailingCollector()])
        result = svc.collect_and_analyze(db)

        assert result.created == 3, result
        assert result.analyzed == 2, result
        assert result.failed == 1, result

        # 库校验：保留 3 条，1 条 failed，2 条 completed
        total = db.query(Opinion).filter(Opinion.source == "test").count()
        failed = (
            db.query(Opinion)
            .filter(Opinion.source == "test", Opinion.analysis_status == "failed")
            .count()
        )
        completed = (
            db.query(Opinion)
            .filter(Opinion.source == "test", Opinion.analysis_status == "completed")
            .count()
        )
        assert total == 3, total
        assert failed == 1, failed
        assert completed == 2, completed
    finally:
        db.rollback()
        db.close()


# ---------------------------------------------------------------------------
# 5) API 鉴权：无 token -> 401
# ---------------------------------------------------------------------------
def test_collector_run_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/collector/run")
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# 6) API 返回 created/analyzed 正确 + /status 结构与鉴权
# ---------------------------------------------------------------------------
def test_collector_status_endpoint(client: TestClient, auth_headers) -> None:
    # 无鉴权 -> 401
    r0 = client.get("/api/collector/status")
    assert r0.status_code == 401, r0.text

    # 先运行一次，使状态被更新
    client.post("/api/collector/run", headers=auth_headers)

    # 有鉴权 -> 返回结构正确
    r1 = client.get("/api/collector/status", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert "last_run" in body
    assert "total_collected" in body
    assert isinstance(body["total_collected"], int)
