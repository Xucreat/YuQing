"""通用国内 RSS 数据源单元测试（Phase RSS-Support）。

覆盖：
1. RSSCollector 从 config_json.feeds 读取地址（dict / 字符串两种形态）。
2. 单 Feed 正常采集、字段转换（title/content/url/publish_time/author/source/external_id）。
3. 多 Feed 部分失败隔离（一个 Feed 失败不影响其它）。
4. 去重：guid(external_id) > link(url) > 内容哈希。
5. 非法/空 URL 在构造期被拒绝；SSRF 防护（本地/内网地址 fetch 时被跳过）。
6. RSS_URLS 环境变量 fallback。
7. 调度注册：registry 正确装配 RSSCollector（type=rss 且 class_path 指向它）。
8. 中国新闻网仍使用 ChinanewsCollector（不受 rss 映射改动影响）。
9. 后台 API 校验：_validate_rss_config / _validate_create / _build_test 对 rss 类型的处理。
10. 来源名 source_name 覆盖（使 collector_runs / opinions.source 使用正确来源名）。
11. SSRF 重定向防护：http_get_guarded 对每一跳重新校验，302 跳内网被拦截且不崩溃。

不触碰 Event / RiskEngine / Alert / 数据库迁移；全部使用 fixture 网络替代，不触网。
"""
import types

import pytest

from app.collectors.chinanews_collector import ChinanewsCollector
from app.collectors.common import http_get_guarded
from app.collectors.rss_collector import RSSCollector
from app.collectors.registry import DEFAULT_SOURCES, _attach_meta, _build_collector, import_class


RSS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<rss version="2.0"><channel>'
    '<item><title>测试标题一</title><link>https://example.com/a1</link>'
    '<guid>guid-a1</guid><description>摘要内容一</description>'
    '<author>张三</author><pubDate>Wed, 10 Aug 2026 10:00:00 GMT</pubDate></item>'
    '<item><title>测试标题二</title><link>https://example.com/a2</link>'
    '<description>摘要内容二</description></item>'
    '</channel></rss>'
)

RSS_XML2 = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<rss version="2.0"><channel>'
    '<item><title>另一源标题</title><link>https://other.com/b1</link>'
    '<guid>guid-b1</guid><description>另一源内容</description></item>'
    '</channel></rss>'
)

RSS_NOID = (
    '<?xml version="1.0"?>'
    '<rss version="2.0"><channel>'
    '<item><title>无ID标题</title><description>内容X</description></item>'
    '<item><title>无ID标题</title><description>内容X</description></item>'
    '</channel></rss>'
)


def _safe_pass(url, resolve_dns=True):
    return (True, None)


def _fake_get_factory(primary=RSS_XML, secondary=RSS_XML2):
    def fake_get(session, url, timeout=10, **_):
        if "other.com" in url:
            return secondary
        return primary
    return fake_get


# ---------------------------------------------------------------------------
# 1) feeds 读取（dict / 字符串）
# ---------------------------------------------------------------------------
def test_reads_feeds_from_config_dict(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/feed.xml"}])
    assert len(c.fetch()) == 2
    assert c.feeds == [{"url": "https://example.com/feed.xml"}]


def test_reads_feeds_from_config_string(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=["https://example.com/feed.xml"])
    assert len(c.fetch()) == 2


# ---------------------------------------------------------------------------
# 2) 字段转换
# ---------------------------------------------------------------------------
def test_field_conversion(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/feed.xml"}])
    it = c.fetch()[0]
    assert it["title"] == "测试标题一"
    assert it["content"] == "摘要内容一"
    assert it["url"] == "https://example.com/a1"
    assert it["author"] == "张三"
    assert it["source"] == "rss"
    assert it["external_id"] == "guid-a1"
    assert it["publish_time"] is not None


# ---------------------------------------------------------------------------
# 3) 多 Feed 部分失败隔离
# ---------------------------------------------------------------------------
def test_multi_feed_partial_failure_isolation(monkeypatch):
    def fake_get(session, url, timeout=10, **_):
        if "bad.com" in url:
            return None  # 模拟抓取失败
        return _fake_get_factory()(session, url, timeout)

    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", fake_get)
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[
        {"url": "https://bad.com/x.xml"},
        {"url": "https://example.com/feed.xml"},
        {"url": "https://other.com/y.xml"},
    ])
    items = c.fetch()
    assert len(items) == 3  # 失败 feed 被隔离，其余两个正常
    urls = {i["url"] for i in items}
    assert "https://example.com/a1" in urls
    assert "https://example.com/a2" in urls
    assert "https://other.com/b1" in urls


# ---------------------------------------------------------------------------
# 4) 去重：guid > link > 内容哈希
# ---------------------------------------------------------------------------
def test_dedup_guid_used_as_external_id(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/feed.xml"}])
    items = c.fetch()
    assert len(items) == 2
    assert "guid-a1" in {i["external_id"] for i in items}


def test_dedup_hash_when_no_guid_and_link(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", lambda s, u, t=10, **_: RSS_NOID)
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/nolink.xml"}])
    items = c.fetch()
    assert len(items) == 1
    assert items[0]["external_id"].startswith("sha1:")


# ---------------------------------------------------------------------------
# 5) 非法/空 URL 拒绝 + SSRF 防护
# ---------------------------------------------------------------------------
def test_invalid_url_rejected_at_construction():
    with pytest.raises(ValueError):
        RSSCollector(feeds=[{"url": "ftp://example.com/x"}])
    with pytest.raises(ValueError):
        RSSCollector(feeds=[{"url": ""}])


def test_ssrf_blocks_local_address_at_construction():
    # 本地/内网地址在构造期即被拒绝（SSRF 防护，双重拦截之一）
    with pytest.raises(ValueError):
        RSSCollector(feeds=[{"url": "http://127.0.0.1/feed.xml"}])
    with pytest.raises(ValueError):
        RSSCollector(feeds=[{"url": "http://localhost/feed.xml"}])


def test_ssrf_blocks_at_fetch_time(monkeypatch):
    def fake_safe(url, resolve_dns=True):
        # 构造期（resolve_dns=False）放行；抓取期（resolve_dns=True）拦截内网解析
        if resolve_dns and "blocked.example" in url:
            return (False, "解析到内网地址")
        return (True, None)

    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", fake_safe)
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    c = RSSCollector(feeds=[{"url": "https://blocked.example/feed.xml"}])
    assert c.fetch() == []  # 抓取期被 SSRF 拦截，未抓取


# ---------------------------------------------------------------------------
# 6) RSS_URLS 环境变量 fallback
# ---------------------------------------------------------------------------
def test_env_rss_urls_fallback(monkeypatch):
    monkeypatch.setenv("RSS_URLS", "https://example.com/feed.xml, https://other.com/y.xml")
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector()  # 无 feeds -> 回退环境变量
    assert len(c.feeds) == 2
    assert len(c.fetch()) == 3


# ---------------------------------------------------------------------------
# 10) 来源名 source_name 覆盖（collector_runs / opinions.source 正确）
# ---------------------------------------------------------------------------
def test_source_name_override(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/feed.xml"}], source_name="我的RSS源")
    assert c.source_name == "我的RSS源"
    it = c.fetch()[0]
    assert it["source"] == "我的RSS源"


def test_source_name_default_is_rss(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/feed.xml"}])
    assert c.source_name == "rss"
    assert c.fetch()[0]["source"] == "rss"


# ---------------------------------------------------------------------------
# 7) 调度注册：registry 正确装配 RSSCollector
# ---------------------------------------------------------------------------
def test_registry_builds_rss_collector():
    cls = import_class("app.collectors.rss_collector.RSSCollector")
    assert cls is RSSCollector
    meta = {
        "key": "my_rss", "name": "我的RSS",
        "class_path": "app.collectors.rss_collector.RSSCollector",
        "scope_region_codes": "",
    }
    cfg = {"feeds": [{"url": "https://example.com/feed.xml"}], "source_name": "我的RSS"}
    collector = _attach_meta(_build_collector(cls, meta, cfg), meta, cfg)
    assert isinstance(collector, RSSCollector)
    assert collector.feeds == [{"url": "https://example.com/feed.xml"}]
    assert collector.data_source_key == "my_rss"
    # 装配链把 config_json.source_name 落到采集器（与 GenericSiteCollector 约定一致）
    assert collector.source_name == "我的RSS"


# ---------------------------------------------------------------------------
# 8) 中国新闻网仍使用 ChinanewsCollector（不受 rss 映射改动影响）
# ---------------------------------------------------------------------------
def test_chinanews_still_uses_chinanews_collector():
    cls = import_class("app.collectors.chinanews_collector.ChinanewsCollector")
    assert cls is ChinanewsCollector
    cn = next(s for s in DEFAULT_SOURCES if s["key"] == "chinanews")
    assert cn["class_path"].endswith("ChinanewsCollector")
    assert cn["class_path"] != "app.collectors.rss_collector.RSSCollector"


# ---------------------------------------------------------------------------
# 9) 后台 API 校验
# ---------------------------------------------------------------------------
def test_validate_rss_config_and_create():
    from app.api.admin_data_sources import _validate_create, _validate_rss_config

    # 合法 feeds
    assert _validate_rss_config({"feeds": [{"url": "https://example.com/a.xml"}]}) is None
    # 允许 source_name 等附加键
    assert _validate_rss_config({"feeds": [{"url": "https://example.com/a.xml"}], "source_name": "X"}) is None
    # 空 feeds
    assert _validate_rss_config({"feeds": []}) is not None
    # 非法 scheme
    assert _validate_rss_config({"feeds": [{"url": "ftp://x"}]}) is not None
    # 缺 feeds（旧 RSS_URLS 兼容）允许
    assert _validate_rss_config({}) is None

    # _validate_create 将 rss 类型映射到 RSSCollector 并执行 rss 校验
    ok = _validate_create({
        "name": "测试RSS", "key": "test_rss_x", "type": "rss",
        "config_json": {"feeds": [{"url": "https://example.com/a.xml"}]},
    })
    assert ok is None, ok

    bad = _validate_create({
        "name": "测试RSS", "key": "test_rss_y", "type": "rss",
        "config_json": {"feeds": []},
    })
    assert bad is not None


def test_build_test_rss_branch_executes(monkeypatch):
    """回归：_build_test 的 RSS 分支必须在 foreign 分支之前计算 build_cfg，
    否则会 UnboundLocalError，导致「测试连接」与数据源创建（需真实抓取校验）
    一律 422 失败。"""
    import app.api.admin_data_sources as admin_mod
    from app.api.admin_data_sources import RSS_CLASS_PATH, _build_test

    monkeypatch.setattr(admin_mod, "import_class", lambda cp: RSSCollector)
    # 用 fixture 抓取替代真实网络；fetch 直接返回 3 条，避免任何 HTTP。
    monkeypatch.setattr(RSSCollector, "fetch", lambda self, keywords=None: [1, 2, 3])
    # 构造期 is_safe_rss_url(resolve_dns=False) 对公网地址放行，不触网。
    res = _build_test(RSS_CLASS_PATH, {"feeds": [{"url": "https://example.com/feed.xml"}]})
    assert res.get("ok") is True, res
    assert res.get("count") == 3
    assert res.get("feeds") == 1


# ---------------------------------------------------------------------------
# 11) SSRF 重定向防护：http_get_guarded 对每一跳重新校验
# ---------------------------------------------------------------------------
class _FakeResp:
    def __init__(self, status, location=None, text="", encoding="utf-8"):
        self.status_code = status
        self.text = text
        self.encoding = encoding
        self.apparent_encoding = "utf-8"
        self.headers = {"Location": location} if location is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _RedirectSession:
    """第一次返回 302 指向内网，第二次（若被允许）返回 200。"""

    def __init__(self, redirect_target):
        self.redirect_target = redirect_target
        self.calls = []

    def get(self, url, timeout=10, allow_redirects=False):
        self.calls.append(url)
        if len(self.calls) == 1:
            return _FakeResp(302, location=self.redirect_target)
        return _FakeResp(200, text="SECRET")


def _guard_block_local(url, resolve_dns=True):
    # 测试用确定性 guard：仅拦截本地/内网，放行其余（避免真实 DNS 解析干扰重定向逻辑）
    if "127.0.0.1" in url or "localhost" in url:
        return (False, "禁止内网地址")
    return (True, None)


def test_http_get_guarded_blocks_redirect_to_local():
    # 公网地址 302 跳转到 127.0.0.1（云元数据/内网），必须被下一跳的 SSRF 校验拦截
    sess = _RedirectSession("http://127.0.0.1/secret")
    out = http_get_guarded(sess, "https://public.example/feed.xml", 10, guard=_guard_block_local)
    assert out is None  # 未返回内网内容


def test_http_get_guarded_follows_safe_redirect():
    class Sess:
        def get(self, url, timeout=10, allow_redirects=False):
            if url == "https://public.example/feed.xml":
                return _FakeResp(302, location="https://final.example/rss")
            return _FakeResp(200, text="OK-FINAL")

    out = http_get_guarded(Sess(), "https://public.example/feed.xml", 10, guard=_guard_block_local)
    assert out == "OK-FINAL"


def test_http_get_guarded_guard_exception_does_not_crash():
    def broken_guard(url, resolve_dns=True):
        raise RuntimeError("dns boom")

    sess = _RedirectSession("http://127.0.0.1/x")
    # guard 异常不应导致服务崩溃，应安全返回 None
    assert http_get_guarded(sess, "https://public.example/feed.xml", 10, guard=broken_guard) is None


# ---------------------------------------------------------------------------
# 12) 接口兼容：fetch 必须接受 region_kw / topic_kw（CollectorService 调用约定）
# ---------------------------------------------------------------------------
# 回归：RSSCollector.fetch 曾只接受 keywords=，真实采集路径（service.py 调用
# collector.fetch(keywords=..., region_kw=..., topic_kw=...)）会抛 TypeError 导致
# 采集失败。test_connection / 单测因不传 region_kw 而无法暴露此缺陷。
def test_fetch_accepts_region_topic_kwargs(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/feed.xml"}])
    # 与 CollectorService._process_collector 完全一致的调用形态
    items = c.fetch(keywords=["通山"], region_kw=["通山", "咸宁"], topic_kw=["消防"])
    assert len(items) == 2  # region_kw/topic_kw 不在采集器内部过滤，全部返回


def test_fetch_accepts_none_region_topic(monkeypatch):
    monkeypatch.setattr("app.collectors.rss_collector.http_get_guarded", _fake_get_factory())
    monkeypatch.setattr("app.collectors.rss_collector.is_safe_rss_url", _safe_pass)
    c = RSSCollector(feeds=[{"url": "https://example.com/feed.xml"}])
    items = c.fetch(keywords=None, region_kw=None, topic_kw=None)
    assert len(items) == 2
