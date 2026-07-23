"""Phase 2C-0 自测：

- AIService 可实例化
- Fallback Provider 可调用，返回 TODO 结构
- DeepSeek Provider 配置缺失时不报错
- Opinion 新增 AI 字段可正常读取（API 详情 + ORM 往返）
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.opinion import Opinion
from app.models.region import Region
from app.schemas.ai import AIAnalysisResult
from app.services.ai import AIService
from app.services.ai.fallback import RuleFallbackProvider
from app.services.ai.providers.base import BaseAIProvider
from app.services.ai.providers.deepseek import DeepSeekProvider


def test_ai_service_instantiable() -> None:
    svc = AIService()
    assert isinstance(svc, AIService)
    assert isinstance(svc.fallback, RuleFallbackProvider)
    assert isinstance(svc.deepseek, DeepSeekProvider)


def test_fallback_provider_typed_result() -> None:
    # 中性文本（无敏感词）-> 默认风险 20 / neutral / 空命中
    fb = RuleFallbackProvider()
    result = fb.analyze("今天天气不错，市民出行顺畅")
    assert isinstance(result, AIAnalysisResult)
    assert set(result.model_dump().keys()) >= {
        "summary",
        "sentiment",
        "risk_score",
        "keywords",
        "suggestion",
    }
    assert result.sentiment == "neutral"
    assert result.risk_score == 20
    assert result.keywords == []

    # 含敏感词 -> 风险升高、negative、命中词入列
    hit = fb.analyze("某小区发生火灾，群众质疑消防响应速度")
    assert isinstance(hit, AIAnalysisResult)
    assert hit.risk_score > 0
    assert "火灾" in hit.keywords
    assert hit.sentiment == "negative"


def test_fallback_provider_empty_keywords_uses_default() -> None:
    # 构造为空 -> 退回内置 DEFAULT_KEYWORDS
    fb = RuleFallbackProvider(keywords=[])
    r = fb.analyze("工厂爆炸导致多人伤亡")
    assert isinstance(r, AIAnalysisResult)
    assert r.risk_score > 0
    assert "爆炸" in r.keywords


def test_deepseek_provider_instantiate_without_config(monkeypatch) -> None:
    # 配置缺失（api_key 为空）时构造 Provider 不应报错。
    # 说明：当前运行环境的 .env 已注入 DEEPSEEK_API_KEY，因此显式将配置置空以
    # 确定性地模拟「未配置」状态，验证真实的 is_configured 行为（api_key 非空判定）。
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    provider = DeepSeekProvider()
    assert isinstance(provider, BaseAIProvider)
    assert provider.is_configured is False


def test_deepseek_provider_analyze_raises_when_not_configured(monkeypatch) -> None:
    # Phase 2C-1：真实实现；未配置 key 时 analyze 应上抛 RuntimeError
    # （由 AIService 捕获并降级到 RuleFallbackProvider）。
    # 显式置空 api_key 走真实 analyze -> _chat_json 路径，在发起任何网络调用前即上抛。
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    provider = DeepSeekProvider()
    assert provider.is_configured is False
    with pytest.raises(RuntimeError):
        provider.analyze("测试文本")


def test_opinion_ai_fields_readable(
    auth_headers, client: TestClient
) -> None:
    # 取种子区域 id
    db: Session = SessionLocal()
    try:
        region = db.query(Region).filter(Region.code == "131028").first()
        assert region is not None
        region_id = region.id
    finally:
        db.close()

    # 创建一条舆情
    payload = {
        "title": "AI字段测试舆情",
        "content": "内容",
        "source": "微博",
        "url": "https://example.com/ai-test",
        "region_id": region_id,
    }
    create = client.post("/api/opinions", json=payload, headers=auth_headers)
    assert create.status_code in (200, 201), create.text
    oid = create.json()["id"]

    # 读取详情，确认新增 AI 字段可正常序列化返回
    detail = client.get(f"/api/opinions/{oid}", headers=auth_headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert "analysis_status" in body
    assert "analysis_time" in body
    assert body["analysis_status"] == "pending"
    assert body["analysis_time"] is None


def test_opinion_ai_fields_orm_roundtrip() -> None:
    # 直接经 ORM 写入并读回 analysis_status / analysis_time
    db: Session = SessionLocal()
    try:
        region = db.query(Region).filter(Region.code == "131028").first()
        assert region is not None
        op = Opinion(
            title="orm-ai",
            content="c",
            source="s",
            region_id=region.id,
            analysis_status="completed",
            analysis_time=datetime.now(timezone.utc),
        )
        db.add(op)
        db.commit()
        db.refresh(op)
        assert op.analysis_status == "completed"
        assert op.analysis_time is not None
        db.delete(op)
        db.commit()
    finally:
        db.close()
