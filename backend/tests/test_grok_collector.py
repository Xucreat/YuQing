"""GrokCollector 单元测试（Phase Grok-2）。

全程 Mock，绝不调用真实 Grok API / 不触真实数据库：
  - 通过 monkeypatch 替换 app.collectors.grok_collector.OpenAI 为内存 FakeOpenAI；
  - 通过 monkeypatch 注入 settings.grok_api_key（仅测试用，不落库、不提交真实 Key）；
  - registry「enabled=false 不加载」测试用 FakeDB/FakeQuery 模拟装配边界，
    不连接任何数据库。

覆盖：
  T1 正常 citations -> 返回标准 dict（title/content/source/url/publish_time）
  T2 无 url citation -> 直接丢弃
  T3 单关键词失败隔离 -> A 失败不影响 B 返回
  T4 enabled=false -> registry 不加载 GrokCollector（含 enabled=true 正控）
"""
from types import SimpleNamespace
from typing import Any, List

import pytest

from app.collectors.base import BaseCollector
from app.collectors.grok_collector import GrokCollector
from app.collectors.registry import resolve_collectors_verbose


# ---------------------------------------------------------------------------
# Fake OpenAI（仅内存，不触网）
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, citations: List[dict], annotations: List[dict] | None = None):
        self.citations = citations
        self.choices = [SimpleNamespace(message=SimpleNamespace(annotations=annotations or []))]


class _FakeCompletions:
    def __init__(self, scripted):
        # scripted(user_text: str) -> _FakeResponse | Exception
        self._scripted = scripted

    def create(self, model=None, messages=None, **kwargs):
        user_text = ""
        for m in messages or []:
            if m.get("role") == "user":
                user_text = m.get("content", "")
                break
        out = self._scripted(user_text)
        if isinstance(out, Exception):
            raise out
        return out


class _FakeOpenAI:
    def __init__(self, completions: _FakeCompletions, **kwargs):
        self.chat = SimpleNamespace(completions=completions)


def _make_openai(scripted) -> _FakeOpenAI:
    return _FakeOpenAI(_FakeCompletions(scripted))


# ---------------------------------------------------------------------------
# T1：正常 citations -> 标准 dict
# ---------------------------------------------------------------------------
def test_grok_normal_citations(monkeypatch):
    monkeypatch.setattr(
        "app.collectors.grok_collector.OpenAI",
        lambda *a, **k: _make_openai(
            lambda text: _FakeResponse(
                citations=[{"url": "https://example.com", "title": "测试", "snippet": "摘要"}]
            )
        ),
    )
    monkeypatch.setattr("app.core.config.settings.grok_api_key", "test-key")
    monkeypatch.setattr("app.core.config.settings.grok_search_count", 5)

    collector = GrokCollector()
    results = collector.fetch(keywords=["廊坊"])

    assert len(results) == 1
    item = results[0]
    assert set(item.keys()) == {"title", "content", "source", "url", "publish_time"}
    assert item["title"] == "测试"
    assert item["content"] == "摘要"  # 仅来自 citation snippet
    assert item["source"] == "Grok实时搜索"
    assert item["url"] == "https://example.com"
    assert item["publish_time"] is None
    # 关键约束：绝不使用 Grok 生成回答正文作为 content
    assert "Grok" not in item["content"]


# ---------------------------------------------------------------------------
# T2：无 url citation -> 直接丢弃
# ---------------------------------------------------------------------------
def test_grok_discard_no_url_citation(monkeypatch):
    monkeypatch.setattr(
        "app.collectors.grok_collector.OpenAI",
        lambda *a, **k: _make_openai(
            lambda text: _FakeResponse(
                citations=[{"url": "", "title": "xxx"}]
            )
        ),
    )
    monkeypatch.setattr("app.core.config.settings.grok_api_key", "test-key")

    collector = GrokCollector()
    results = collector.fetch(keywords=["廊坊"])
    assert results == [], "无 url 的 citation 必须被丢弃"


# ---------------------------------------------------------------------------
# T3：单关键词失败隔离（A 失败，B 成功）
# ---------------------------------------------------------------------------
def test_grok_single_keyword_failure_isolated(monkeypatch):
    def _script(user_text: str):
        if "关键词A" in user_text:
            return RuntimeError("simulated Grok API failure for A")
        # 关键词B 成功
        return _FakeResponse(
            citations=[
                {"url": "https://ok.example/b", "title": "B结果", "snippet": "B摘要"}
            ]
        )

    monkeypatch.setattr(
        "app.collectors.grok_collector.OpenAI",
        lambda *a, **k: _make_openai(_script),
    )
    monkeypatch.setattr("app.core.config.settings.grok_api_key", "test-key")

    collector = GrokCollector()
    results = collector.fetch(keywords=["关键词A", "关键词B"])

    assert len(results) == 1, "关键词A 失败不应拖垮关键词B"
    assert results[0]["url"] == "https://ok.example/b"
    assert results[0]["title"] == "B结果"


# ---------------------------------------------------------------------------
# T4：enabled=false -> registry 不加载 GrokCollector
# ---------------------------------------------------------------------------
class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *a, **k):
        return _FakeQuery(self._rows)


def _row(**kw):
    return SimpleNamespace(**kw)


def test_grok_enabled_false_not_loaded():
    # 模拟 SQL 层 enabled=True 过滤后，结果集不含 grok（即 enabled=false 被排除）
    rows = [
        _row(
            key="government",
            name="大厂县政府网站",
            class_path="app.collectors.government_collector.GovernmentCollector",
            scope_region_codes="131028",
            config_json="{}",
        )
    ]
    resolved = resolve_collectors_verbose(db=_FakeDB(rows))
    assert resolved.failures == [], resolved.failures
    assert not any(isinstance(c, GrokCollector) for c in resolved.collectors)
    assert all(not isinstance(c, GrokCollector) for c in resolved.collectors)


def test_grok_enabled_true_loaded():
    # 正控：enabled=true 时应装配出 GrokCollector 实例
    rows = [
        _row(
            key="grok_search",
            name="Grok实时搜索",
            class_path="app.collectors.grok_collector.GrokCollector",
            scope_region_codes="131000",
            config_json="{}",
        )
    ]
    resolved = resolve_collectors_verbose(db=_FakeDB(rows))
    assert any(isinstance(c, GrokCollector) for c in resolved.collectors), resolved.failures
    grok = next(c for c in resolved.collectors if isinstance(c, GrokCollector))
    assert grok.source_name == "Grok实时搜索"
    assert grok.data_source_key == "grok_search"


# ---------------------------------------------------------------------------
# 补充：API Key 缺失 -> fetch 硬失败（交由 CollectorService 记录失败）
# ---------------------------------------------------------------------------
def test_grok_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.grok_api_key", "")
    collector = GrokCollector()
    with pytest.raises(RuntimeError):
        collector.fetch(keywords=["廊坊"])
