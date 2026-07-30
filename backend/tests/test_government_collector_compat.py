"""GovernmentCollector 与统一 collector 接口兼容测试（最小）。

验证：
1. GovernmentCollector.fetch 能接收 service.py 统一注入的 region_kw / topic_kw，
   不再抛出 TypeError。
2. region_kw / topic_kw 不参与任何过滤逻辑（government 维持 Option B 全量采集），
   无论地域/主题词如何，返回结果一致。

不触碰 Event / RiskEngine / Alert / Dashboard / 数据库迁移 / service.py / common.py。
网络请求通过 monkeypatch 桩掉，单测可离线运行。
"""
from __future__ import annotations

from types import SimpleNamespace

from app.collectors import government_collector
from app.collectors.government_collector import GovernmentCollector

# 假栏目页：含一个真实文章链接（/数字id.jhtml）
_LIST_HTML = (
    '<html><body>'
    '<a href="/news/123.jhtml">测试文章标题</a>'
    '<a href="/about.html">非文章导航</a>'
    '</body></html>'
)
# 假详情页：含正文段落
_DETAIL_HTML = (
    '<html><body><div class="article">'
    '<p>这是一篇关于廊坊的测试正文内容，用于验证全量采集不被地域词过滤。</p>'
    '</div></body></html>'
)


def _fake_http_get(session, url, timeout):
    # 详情页（含 .jhtml）返回正文；列表页返回栏目 HTML
    if ".jhtml" in url:
        return _DETAIL_HTML
    return _LIST_HTML


def _fake_make_session(ua):
    return SimpleNamespace()


def test_fetch_accepts_region_and_topic_kw(monkeypatch) -> None:
    """fetch 能接收 region_kw/topic_kw 且不抛异常（回归修复点）。"""
    monkeypatch.setattr(government_collector, "http_get", _fake_http_get)
    monkeypatch.setattr(government_collector, "make_session", _fake_make_session)

    collector = GovernmentCollector(urls=["http://fake/col"])
    # 旧调用方式（无 region_kw/topic_kw）仍可用
    base = collector.fetch()
    # 新调用方式（service.py 统一注入 region_kw/topic_kw）不应抛 TypeError
    with_extra = collector.fetch(region_kw=["廊坊", "固安"], topic_kw=["消防", "民生"])

    assert isinstance(base, list)
    assert isinstance(with_extra, list)


def test_region_and_topic_kw_do_not_filter(monkeypatch) -> None:
    """region_kw/topic_kw 不参与过滤：即便地域/主题词与内容无关，仍全量返回。"""
    monkeypatch.setattr(government_collector, "http_get", _fake_http_get)
    monkeypatch.setattr(government_collector, "make_session", _fake_make_session)

    collector = GovernmentCollector(urls=["http://fake/col"])

    # 不传关键词
    no_kw = collector.fetch()
    # 传入与内容完全无关的地域/主题词（应不影响结果，证明无过滤）
    unrelated = collector.fetch(
        region_kw=["上海", "广州"], topic_kw=["航天", "量子"]
    )

    assert len(no_kw) == len(unrelated), "region_kw/topic_kw 不应改变返回集合"
    assert len(no_kw) == 1, "应抓到 1 篇真实文章（排除非 .jhtml 导航）"
    assert no_kw[0]["source"] == GovernmentCollector.source_name
    assert "测试文章标题" in no_kw[0]["title"]
