"""Phase 2C-1 自测：单条舆情 AI 分析闭环。

覆盖验收：
1. 无 Key 情况下 AIService 自动 fallback（返回类型化 AIAnalysisResult）
2. fallback 规则分析：含敏感词 -> risk_score > 0、status=completed
3. API 测试：登录 -> 创建 -> POST /api/analyze/{id} -> 返回
   summary / risk_score / sentiment / analysis_suggestion
4. 状态测试：模拟 AI 异常 -> analysis_status=failed
5. DeepSeek 解析：去 ```json 代码块 + 校验 -> AIAnalysisResult；非法 JSON 上抛
6. 鉴权：无 token -> 401；不存在 -> 404
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.schemas.ai import AIAnalysisResult
from app.services.ai import AIService
from app.services.ai.providers.deepseek import DeepSeekProvider


# ---------------------------------------------------------------------------
# 1) 无 Key -> 自动 fallback（类型化结果）
# ---------------------------------------------------------------------------
def test_aiservice_no_key_auto_fallback() -> None:
    # 本环境 DEEPSEEK_API_KEY 为空 -> DeepSeek 未配置
    ai = AIService()
    assert ai.deepseek.is_configured is False
    # 调用应自动走 fallback，返回 AIAnalysisResult 且 risk_score > 0
    result = ai.analyze("某小区发生火灾", "群众质疑消防响应速度")
    assert isinstance(result, AIAnalysisResult)
    assert result.risk_score > 0
    assert result.sentiment == "negative"
    assert "火灾" in result.keywords


# ---------------------------------------------------------------------------
# 2+3) API 成功：含敏感词 -> 写库、status=completed、返回核心字段
# ---------------------------------------------------------------------------
def test_analyze_api_success(
    client: TestClient, auth_headers, seeded_region_id
) -> None:
    # 创建含敏感词舆情
    payload = {
        "title": "某小区发生火灾",
        "content": "某小区发生火灾，群众质疑消防响应速度",
        "source": "微博",
        "url": "https://example.com/fire",
        "region_id": seeded_region_id,
    }
    create = client.post("/api/opinions", json=payload, headers=auth_headers)
    assert create.status_code in (200, 201), create.text
    oid = create.json()["id"]

    # 触发分析
    resp = client.post(f"/api/analyze/{oid}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # 返回关键字段
    assert body["id"] == oid
    assert isinstance(body["summary"], str) and body["summary"]
    assert body["risk_score"] > 0
    assert body["sentiment"] in ("positive", "negative", "neutral")
    assert isinstance(body["analysis_suggestion"], str) and body["analysis_suggestion"]

    # 状态流转
    assert body["analysis_status"] == "completed"
    assert body["analysis_time"] is not None

    # 库内确认
    db: Session = SessionLocal()
    try:
        op = db.get(Opinion, oid)
        assert op is not None
        assert op.analysis_status == "completed"
        assert op.risk_score > 0
        assert op.analysis_suggestion
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4) 状态测试：模拟 AI 异常 -> status=failed + 500
# ---------------------------------------------------------------------------
def test_analyze_api_failure_sets_failed(
    client: TestClient, auth_headers, seeded_region_id, monkeypatch
) -> None:
    # 创建舆情
    payload = {
        "title": "普通民生新闻",
        "content": "今日社区组织便民服务活动",
        "source": "微信",
        "url": "https://example.com/civic",
        "region_id": seeded_region_id,
    }
    create = client.post("/api/opinions", json=payload, headers=auth_headers)
    assert create.status_code in (200, 201), create.text
    oid = create.json()["id"]

    # 让 AIService.analyze 抛异常
    class _FailingAI:
        def analyze(self, title: str, content: str) -> AIAnalysisResult:
            raise RuntimeError("simulated AI failure")

    monkeypatch.setattr("app.api.analysis.AIService", _FailingAI)

    resp = client.post(f"/api/analyze/{oid}", headers=auth_headers)
    assert resp.status_code == 500, resp.text

    # 失败状态被保留
    db: Session = SessionLocal()
    try:
        op = db.get(Opinion, oid)
        assert op is not None
        assert op.analysis_status == "failed"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5) DeepSeek 解析：去代码块 + 校验；非法 JSON 上抛
# ---------------------------------------------------------------------------
def _make_fake_openai(content: str):
    """构造一个假的 OpenAI 客户端类（仅用于离线解析测试）。"""

    class _Msg:
        def __init__(self, text: str) -> None:
            self.content = text

    class _Choice:
        def __init__(self, text: str) -> None:
            self.message = _Msg(text)

    class _Resp:
        def __init__(self, text: str) -> None:
            self.choices = [_Choice(text)]

    class _Completions:
        def create(self, **kwargs):
            return _Resp(content)

    class _Chat:
        @property
        def completions(self):
            return _Completions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            pass

        @property
        def chat(self):
            return _Chat()

    return _FakeOpenAI


def test_deepseek_parse_strips_fence_and_validates(monkeypatch) -> None:
    import app.services.ai.providers.deepseek as ds_mod

    valid = json.dumps(
        {
            "summary": "舆情摘要",
            "sentiment": "negative",
            "risk_score": 80,
            "keywords": ["火灾", "事故"],
            "suggestion": "建议核查",
        }
    )

    # 无代码块
    monkeypatch.setattr(ds_mod, "OpenAI", _make_fake_openai(valid))
    p = DeepSeekProvider()
    p.api_key = "fake-key"  # 强制 is_configured=True
    r1 = p.analyze("某小区发生火灾")
    assert isinstance(r1, AIAnalysisResult)
    assert r1.risk_score == 80
    assert r1.sentiment == "negative"
    assert r1.keywords == ["火灾", "事故"]

    # 带 ```json 代码块，应兼容
    monkeypatch.setattr(
        ds_mod, "OpenAI", _make_fake_openai("```json\n" + valid + "\n```")
    )
    p2 = DeepSeekProvider()
    p2.api_key = "fake-key"
    r2 = p2.analyze("x")
    assert r2.risk_score == 80


def test_deepseek_parse_invalid_json_raises(monkeypatch) -> None:
    import app.services.ai.providers.deepseek as ds_mod

    monkeypatch.setattr(
        ds_mod, "OpenAI", _make_fake_openai("这不是 JSON")
    )
    p3 = DeepSeekProvider()
    p3.api_key = "fake-key"
    with pytest.raises(Exception):
        p3.analyze("x")


def test_aiservice_fallback_when_deepseek_errors(monkeypatch) -> None:
    # DeepSeek 已配置但调用失败 -> 降级到 fallback
    def _boom(self, text: str) -> AIAnalysisResult:
        raise RuntimeError("simulated API error")

    monkeypatch.setattr(DeepSeekProvider, "analyze", _boom)
    ai = AIService()
    ai._deepseek.api_key = "fake-key"  # is_configured=True，触发 DeepSeek 分支
    r = ai.analyze("某小区发生火灾", "群众质疑消防响应速度")
    assert isinstance(r, AIAnalysisResult)
    assert r.risk_score > 0  # 来自 fallback


# ---------------------------------------------------------------------------
# 6) 鉴权：无 token -> 401；不存在 -> 404
# ---------------------------------------------------------------------------
def test_analyze_api_requires_auth(client: TestClient) -> None:
    resp = client.post("/api/analyze/1")
    assert resp.status_code == 401, resp.text


def test_analyze_api_not_found(
    client: TestClient, auth_headers
) -> None:
    resp = client.post("/api/analyze/999999", headers=auth_headers)
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Opinion not found"
