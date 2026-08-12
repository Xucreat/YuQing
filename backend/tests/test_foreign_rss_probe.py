"""外网 RSS 代理与连通性测试语义修复 — 探测/代理/入口一致性回归。

覆盖需求（一）~（七）的 14 个场景：
  1. 代理端口不可达
  2. 代理可达但 Feed 超时 -> network_failed
  3. Feed 返回 HTTP 500 -> http_failed
  4. 非法 XML -> invalid_feed
  5. 合法空 Feed -> empty_feed
  6. 合法含条目 Feed -> success
  7. 多 Feed 部分失败 -> partial
  8. 代理变量优先级
  9. 显式直连非默认
 10. 创建不发起真实网络请求
 11. 测试连接接口确实发起探测并持久化验证状态
 12. 敏感 URL/密码/Token 不出现在响应/日志
 13. SSRF + 重定向回归（跳转到内网被拦截）
 14. 旧 FOREIGN_HTTP_PROXY 兼容
"""
from __future__ import annotations

import json
import uuid

import pytest
import requests

from app.collectors.common import RSSParseError, mask_url, summarize_rss_probe
from app.collectors.foreign_rss import (
    ForeignRSSCollector,
    _mask_proxy_url,
    probe_proxy_health,
)
from app.db.session import SessionLocal
from app.models.data_source import DataSource


VALID_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>China policy update</title><link>https://news.example/a</link>
    <description>summary a</description><pubDate>Sun, 09 Aug 2026 00:00:00 GMT</pubDate></item>
  <item><title>Market report</title><link>https://news.example/b</link>
    <description>summary b</description></item>
</channel></rss>"""

EMPTY_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>empty</title></channel></rss>"""


class FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200, headers: dict | None = None):
        self.text = text
        self.status_code = status_code
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            exc = requests.exceptions.HTTPError(f"{self.status_code} Error")
            exc.response = self  # 模拟 requests 的 raise_for_status 行为，便于探测层读取状态码
            raise exc

    def json(self):
        return {}


@pytest.fixture
def fixed_dns(monkeypatch):
    """固定 DNS 答案为公网 IP，使 SSRF 防护运行期放行 fixture 域名（不依赖真实 DNS）。"""
    monkeypatch.setattr(
        "app.collectors.common.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )


# ---------------------------------------------------------------------------
# 场景 1：代理端口不可达
# ---------------------------------------------------------------------------
def test_proxy_health_port_unreachable():
    # 127.0.0.1:1 必然拒绝连接（无真实代理），应快速返回不可达，不抛异常。
    health = probe_proxy_health("http://127.0.0.1:1", timeout=1)
    assert health["tcp_reachable"] is False
    assert health["tcp_error_category"] == "network_failed"
    # 地址脱敏（无凭据时仅回显主机）。
    assert health["proxy_url_masked"] == "http://127.0.0.1:1"


# ---------------------------------------------------------------------------
# 场景 2：代理可达但 Feed 超时 -> network_failed
# ---------------------------------------------------------------------------
def test_feed_network_timeout(monkeypatch, fixed_dns):
    def fake_get(*args, **kwargs):
        raise requests.exceptions.Timeout("read timed out")

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["China"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "network_failed"
    assert report["error_category"] == "network_failed"
    assert collector.last_failed_feeds == 1


# ---------------------------------------------------------------------------
# 场景 3：Feed 返回 HTTP 500 -> http_failed
# ---------------------------------------------------------------------------
def test_feed_http_500(monkeypatch, fixed_dns):
    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=500)

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["China"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "http_failed"
    assert report["error_category"] == "http_failed"
    assert report["http_status"] == 500


# ---------------------------------------------------------------------------
# 场景 4：非法 XML -> invalid_feed
# ---------------------------------------------------------------------------
def test_feed_invalid_xml(monkeypatch, fixed_dns):
    # probe() 先发起 _get() 再 parse_rss，需先 stub 网络层返回内容，才能使 parse_rss 的异常被触达。
    def fake_get(*args, **kwargs):
        return FakeResponse(text=VALID_RSS)

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)

    def fake_parse(*args, **kwargs):
        raise RSSParseError("not well-formed XML")

    monkeypatch.setattr("app.collectors.foreign_rss.parse_rss", fake_parse)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["China"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "invalid_feed"
    assert report["error_category"] == "invalid_feed"


# ---------------------------------------------------------------------------
# 场景 5：合法空 Feed -> empty_feed（确实收到并解析，仅无条目）
# ---------------------------------------------------------------------------
def test_feed_empty(monkeypatch, fixed_dns):
    def fake_get(*args, **kwargs):
        return FakeResponse(text=EMPTY_RSS)

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["China"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "empty_feed"
    assert report["xml_parsed"] is True
    assert report["valid_count"] == 0
    assert collector.last_failed_feeds == 0


# ---------------------------------------------------------------------------
# 场景 6：合法含条目 Feed -> success
# ---------------------------------------------------------------------------
def test_feed_success(monkeypatch, fixed_dns):
    def fake_get(*args, **kwargs):
        return FakeResponse(text=VALID_RSS)

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["China"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "success"
    assert report["valid_count"] == 2
    assert report["xml_parsed"] is True


# ---------------------------------------------------------------------------
# 场景 7：多 Feed 部分失败 -> partial
# ---------------------------------------------------------------------------
def test_multi_feed_partial(monkeypatch, fixed_dns):
    def fake_get(url, **kwargs):
        if "bad" in url:
            raise requests.exceptions.ConnectionError("refused")
        return FakeResponse(text=VALID_RSS)

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/bad", "https://news.example/ok"],
        keywords=["China"], is_foreign=True, max_retries=0,
    )
    reports = collector.probe()
    statuses = {r["feed"]: r["status"] for r in reports}
    assert statuses["https://news.example/bad"] == "network_failed"
    assert statuses["https://news.example/ok"] == "success"
    # 顶层状态应为 partial（有失败但也有有效条目）。
    from app.services.foreign_collection_service import _summarize_probe
    assert _summarize_probe(reports) == "partial"


# ---------------------------------------------------------------------------
# 场景 8：代理变量优先级
# ---------------------------------------------------------------------------
def test_proxy_var_priority(monkeypatch):
    for var in ("X_PROXY_ENV", "FOREIGN_HTTP_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
        monkeypatch.delenv(var, raising=False)

    # 1) 显式 proxy 覆盖优先于 proxy_env 环境变量
    c = ForeignRSSCollector(feeds=["https://x/rss"], proxy="http://explicit:1", proxy_env="X_PROXY_ENV", is_foreign=True)
    monkeypatch.setenv("X_PROXY_ENV", "http://envval:1")
    r = c._resolve_proxy()
    assert r["mode"] == "explicit" and r["url"] == "http://explicit:1"

    # 2) proxy_env 环境变量优先于 FOREIGN_HTTP_PROXY
    c = ForeignRSSCollector(feeds=["https://x/rss"], proxy_env="X_PROXY_ENV", is_foreign=True)
    monkeypatch.setenv("FOREIGN_HTTP_PROXY", "http://foreign:1")
    r = c._resolve_proxy()
    assert r["url"] == "http://envval:1"

    # 3) FOREIGN_HTTP_PROXY 兜底
    monkeypatch.delenv("X_PROXY_ENV", raising=False)
    c = ForeignRSSCollector(feeds=["https://x/rss"], is_foreign=True)
    r = c._resolve_proxy()
    assert r["url"] == "http://foreign:1"

    # 4) HTTPS_PROXY 兜底
    monkeypatch.delenv("FOREIGN_HTTP_PROXY", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://httpsp:1")
    r = c._resolve_proxy()
    assert r["url"] == "http://httpsp:1"

    # 5) HTTP_PROXY 兜底
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.setenv("HTTP_PROXY", "http://httpp:1")
    r = c._resolve_proxy()
    assert r["url"] == "http://httpp:1"

    # 6) 全部缺失 -> 直连默认值（mode=direct_default），不静默回退到任何代理
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    r = c._resolve_proxy()
    assert r["url"] is None and r["mode"] == "direct_default" and r["proxies"] is None


# ---------------------------------------------------------------------------
# 场景 9：显式直连非默认启用
# ---------------------------------------------------------------------------
def test_explicit_direct_not_default(monkeypatch):
    monkeypatch.setenv("FOREIGN_HTTP_PROXY", "http://foreign:1")
    # use_direct=True 强制直连，即便存在代理环境变量
    c = ForeignRSSCollector(feeds=["https://x/rss"], use_direct=True, is_foreign=True)
    r = c._resolve_proxy()
    assert r["mode"] == "direct" and r["proxies"] is None
    # 默认（未显式 use_direct）且存在代理环境变量 -> 应使用代理，而非直连
    c2 = ForeignRSSCollector(feeds=["https://x/rss"], is_foreign=True)
    r2 = c2._resolve_proxy()
    assert r2["mode"] == "env:FOREIGN_HTTP_PROXY" and r2["proxies"] is not None


# ---------------------------------------------------------------------------
# 场景 10 + 11：创建不联网；测试连接接口发起探测并持久化验证状态
# ---------------------------------------------------------------------------
def test_create_no_network_and_test_endpoint_probes(client, auth_headers, monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(text=VALID_RSS)

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    monkeypatch.setattr(
        "app.collectors.foreign_rss.probe_proxy_health",
        lambda *a, **k: {"mode": "direct_default", "tcp_reachable": None},
    )
    # 用固定 DNS 答案，使 SSRF 防护在运行期也放行 fixture.test（无真实 DNS）。
    monkeypatch.setattr(
        "app.collectors.common.socket.getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )

    key = f"probe_gate_{uuid.uuid4().hex[:10]}"
    created = client.post(
        "/api/foreign/sources",
        headers=auth_headers,
        json={"name": "Probe gate fixture", "key": key, "feeds": ["https://fixture.test/rss"]},
    )
    assert created.status_code == 201, created.text
    # 场景 10：创建期不发起真实网络请求
    assert calls == [], "创建期不得发起真实网络请求"
    assert created.json()["verified"] is False

    source_id = created.json()["id"]
    # 场景 11：测试连接接口确实发起探测
    test_resp = client.post(
        "/api/foreign/sources/test",
        headers=auth_headers,
        json={"source_id": source_id, "fetch_full_text": False},
    )
    assert test_resp.status_code == 200, test_resp.text
    assert calls == ["https://fixture.test/rss"], "测试连接接口必须发起真实探测"
    assert test_resp.json()["status"] == "success"
    assert test_resp.json()["verified"] is True

    # 验证状态已持久化回数据源 config_json
    listing = client.get("/api/foreign/sources", headers=auth_headers)
    item = next((it for it in listing.json()["items"] if it["id"] == source_id), None)
    assert item is not None and item["verified"] is True

    db = SessionLocal()
    try:
        db.query(DataSource).filter(DataSource.id == source_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 场景 12：敏感 URL/密码/Token 不出现在响应/日志
# ---------------------------------------------------------------------------
def test_sensitive_proxy_url_not_leaked(monkeypatch, fixed_dns):
    # 12a) proxy_health 的脱敏字段不含密码
    health = probe_proxy_health("http://user:topsecret@127.0.0.1:7897", timeout=1)
    assert "topsecret" not in str(health)
    assert health["proxy_url_masked"] == "http://***:***@127.0.0.1:7897"

    # 12b) _mask_proxy_url 不泄露凭据
    assert "topsecret" not in (_mask_proxy_url("http://user:topsecret@127.0.0.1:7897") or "")

    # 12c) 通过 proxy_env 引用含密码的代理时，对外仅暴露脱敏 url_masked
    monkeypatch.setenv("SECRET_PROXY", "http://user:topsecret@127.0.0.1:7897")
    c = ForeignRSSCollector(feeds=["https://x/rss"], proxy_env="SECRET_PROXY", is_foreign=True)
    r = c._resolve_proxy()
    # 内部 url/proxies 仅供 requests 发起调用使用，绝不对外序列化；
    # 对外仅暴露 url_masked，且密码已脱敏。
    assert r["url_masked"] == "http://***:***@127.0.0.1:7897"
    assert "topsecret" not in (r["url_masked"] or "")

    # 12d) 传输层异常消息含认证 URL 时被脱敏
    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError(
            "Failed to connect to http://user:topsecret@proxy.internal:7897"
        )

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["x"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "network_failed"
    assert "topsecret" not in (report["error"] or "")


# ---------------------------------------------------------------------------
# 场景 13：SSRF + 重定向回归（跳转内网被拦截）
# ---------------------------------------------------------------------------
def test_ssrf_redirect_to_localhost_blocked(monkeypatch, fixed_dns):
    # 13a) 字面量内网地址静态拦截
    ok, _reason = __import__("app.collectors.common", fromlist=["is_safe_rss_url"]).is_safe_rss_url(
        "http://127.0.0.1/rss", resolve_dns=False
    )
    assert ok is False

    # 13b) 302 跳转到内网地址 -> 探测状态 blocked（不绕过 SSRF）
    def fake_get(*args, **kwargs):
        return FakeResponse(status_code=302, headers={"Location": "http://127.0.0.1/evil"})

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["x"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "blocked"
    assert report["error_category"] == "blocked"


# ---------------------------------------------------------------------------
# 场景 14：旧 FOREIGN_HTTP_PROXY 兼容
# ---------------------------------------------------------------------------
def test_legacy_foreign_http_proxy_compat(monkeypatch):
    for var in ("X_PROXY_ENV", "HTTPS_PROXY", "HTTP_PROXY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FOREIGN_HTTP_PROXY", "http://legacy:7897")
    # 默认 proxy_env 即为 FOREIGN_HTTP_PROXY，兼容旧数据（未显式配置 proxy 字段）。
    c = ForeignRSSCollector(feeds=["https://x/rss"], is_foreign=True)
    r = c._resolve_proxy()
    assert r["mode"] == "env:FOREIGN_HTTP_PROXY"
    assert r["url"] == "http://legacy:7897"
    # 代理地址格式非法时构造即报错（不静默忽略）。
    monkeypatch.setenv("FOREIGN_HTTP_PROXY", "not-a-url")
    bad = ForeignRSSCollector(feeds=["https://x/rss"], is_foreign=True)
    with pytest.raises(ValueError):
        bad._resolve_proxy()


# ---------------------------------------------------------------------------
# 场景 15：统一 URL 脱敏（user/pass、敏感 query、fragment、Feed 地址）
# ---------------------------------------------------------------------------
def test_mask_url_sensitive_fields():
    # 15a) user/pass 脱敏
    assert mask_url("http://user:topsecret@proxy.example:7897") == "http://***:***@proxy.example:7897"
    # 15b) query token
    m = mask_url("http://proxy.example:7897/?token=secret")
    assert "secret" not in m and "token=<redacted>" in m
    # 15c) query api_key
    m2 = mask_url("http://proxy.example:7897/?api_key=abc123")
    assert "abc123" not in m2 and "api_key=<redacted>" in m2
    # 15d) fragment 丢弃
    m3 = mask_url("http://proxy.example:7897/path#sessiontoken")
    assert "#" not in m3 and "sessiontoken" not in m3
    # 15e) 三个显式示例
    assert mask_url("http://proxy.example:7897/?token=secret") == "http://proxy.example:7897/?token=<redacted>"
    assert mask_url("http://proxy.example:7897/?api_key=secret") == "http://proxy.example:7897/?api_key=<redacted>"
    assert mask_url("http://user:pass@proxy.example:7897/path?token=secret") == "http://***:***@proxy.example:7897/path?token=<redacted>"
    # 15f) 保留协议/主机/端口/路径用于排障
    assert mask_url("http://proxy.example:7897/path") == "http://proxy.example:7897/path"


def test_feed_url_sensitive_query_masked():
    # Feed 地址含敏感 query 也必须脱敏
    m = mask_url("https://news.example/rss?api_key=LEAK&token=X")
    assert "LEAK" not in m and "X" not in m
    # 经 _feed_label 截断同样安全（仅 scheme://netloc/path，丢弃 query）
    assert "LEAK" not in ForeignRSSCollector._feed_label("https://news.example/rss?api_key=LEAK")


def test_request_exception_url_no_leak(monkeypatch, fixed_dns):
    # 异常消息携带完整认证 URL 时不泄露凭据
    def fake_get(*args, **kwargs):
        raise requests.exceptions.ConnectionError(
            "Failed to connect to http://user:topsecret@proxy.internal:7897/?token=secret"
        )

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["x"], is_foreign=True, max_retries=0
    )
    report = collector.probe()[0]
    assert report["status"] == "network_failed"
    assert "topsecret" not in (report["error"] or "")
    assert "secret" not in (report["error"] or "")


def test_api_response_no_proxy_credential(client, auth_headers, monkeypatch):
    # API 响应与列表接口均不得泄露代理凭据
    monkeypatch.setenv("SECRET_PROXY", "http://user:topsecret@127.0.0.1:7897")
    monkeypatch.setattr(
        "app.collectors.foreign_rss.probe_proxy_health",
        lambda *a, **k: {
            "mode": "env:SECRET_PROXY",
            "proxy_url_masked": "http://***:***@127.0.0.1:7897",
            "tcp_reachable": None,
        },
    )
    key = f"mask_resp_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/foreign/sources",
        headers=auth_headers,
        json={"name": "Mask resp", "key": key, "feeds": ["https://fixture.test/rss"],
              "proxy_env": "SECRET_PROXY"},
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]
    try:
        resp = client.post(
            "/api/foreign/sources/test",
            headers=auth_headers,
            json={"source_id": source_id, "fetch_full_text": False},
        )
        assert resp.status_code == 200, resp.text
        assert "topsecret" not in json.dumps(resp.json())
        listing = client.get("/api/foreign/sources", headers=auth_headers)
        assert "topsecret" not in json.dumps(listing.json())
    finally:
        db = SessionLocal()
        try:
            db.query(DataSource).filter(DataSource.id == source_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


MANY_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>Alpha</title><link>https://news.example/1</link><description>topic a</description></item>
  <item><title>Beta</title><link>https://news.example/2</link><description>topic b</description></item>
  <item><title>Gamma</title><link>https://news.example/3</link><description>topic c</description></item>
  <item><title>Delta</title><link>https://news.example/4</link><description>topic d</description></item>
  <item><title>Epsilon</title><link>https://news.example/5</link><description>topic e</description></item>
</channel></rss>"""


# ---------------------------------------------------------------------------
# 需求一（补全）：probe / fetch 的 feed_reports 中 Feed URL 必须脱敏
# ---------------------------------------------------------------------------
def test_probe_feed_reports_masked(monkeypatch, fixed_dns):
    secret_feed = "http://user:pass@news.example/feed?token=secret#frag"
    monkeypatch.setattr(
        "app.collectors.foreign_rss.requests.get",
        lambda url, **kw: FakeResponse(text=VALID_RSS),
    )
    collector = ForeignRSSCollector(
        feeds=[secret_feed], keywords=["China"], is_foreign=True, max_retries=0
    )
    reports = collector.probe()
    assert len(reports) == 1
    feed = reports[0]["feed"]
    assert feed == mask_url(secret_feed)
    assert "pass" not in feed and "secret" not in feed and "token=secret" not in feed


def test_fetch_feed_reports_masked(monkeypatch, fixed_dns):
    secret_feed = "https://user:topsecret@news.example/rss?api_key=LEAK#sess"
    monkeypatch.setattr(
        "app.collectors.foreign_rss.requests.get",
        lambda url, **kw: FakeResponse(text=VALID_RSS),
    )
    collector = ForeignRSSCollector(
        feeds=[secret_feed], keywords=["China"], is_foreign=True, max_retries=0
    )
    collector.fetch()
    reports = collector.last_feed_reports
    assert len(reports) == 1
    feed = reports[0]["feed"]
    assert feed == mask_url(secret_feed)
    assert "topsecret" not in feed and "LEAK" not in feed and "sess" not in feed


# ---------------------------------------------------------------------------
# 需求二：valid_count / matched_count 语义统一（不受关键词影响；probe==fetch）
# ---------------------------------------------------------------------------
def test_valid_count_independent_of_keyword(monkeypatch, fixed_dns):
    """Feed 有有效文章但无关键词命中：valid_count>0 且 matched_count=0；
    单 Feed 级别状态为 empty_feed（无命中），但顶层四态基于 valid_count 仍为 success（可达且有有效条目），
    绝不可能是 failed；正式采集不写入 opinion，运行状态仍表达「可达」。"""
    monkeypatch.setattr(
        "app.collectors.foreign_rss.requests.get",
        lambda url, **kw: FakeResponse(text=VALID_RSS),
    )
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"],
        keywords=["NonexistentKeywordXYZ"], is_foreign=True, max_retries=0,
    )
    probe_reports = collector.probe()
    # valid_count 不受关键词影响（仍为 2），matched_count 为 0。
    assert probe_reports[0]["valid_count"] == 2
    assert probe_reports[0]["matched_count"] == 0
    # 单 Feed 级别状态反映相关性：可达但无命中 -> empty_feed。
    assert probe_reports[0]["status"] == "empty_feed"
    # 顶层四态（基于 error_category + valid_count）不得误判为 failed/partial。
    summary = summarize_rss_probe(probe_reports)
    assert summary["status"] in ("success", "empty_feed")
    assert summary["status"] != "failed"

    items = collector.fetch()
    # 无命中则不写 opinion，但运行状态仍表达「可达」。
    assert items == []
    assert collector.last_feed_reports[0]["reachable"] is True
    assert collector.last_feed_reports[0]["valid_count"] == 2
    assert collector.last_feed_reports[0]["status"] == "empty_feed"


def test_probe_fetch_consistent_valid_count(monkeypatch, fixed_dns):
    """probe 与 fetch 对同一 RSS 内容应得到一致的 valid_count。"""
    monkeypatch.setattr(
        "app.collectors.foreign_rss.requests.get",
        lambda url, **kw: FakeResponse(text=VALID_RSS),
    )
    collector = ForeignRSSCollector(
        feeds=["https://news.example/rss"], keywords=["China"], is_foreign=True, max_retries=0
    )
    probe_reports = collector.probe()
    collector.fetch()
    fetch_reports = collector.last_feed_reports
    assert probe_reports[0]["valid_count"] == fetch_reports[0]["valid_count"] == 2


# ---------------------------------------------------------------------------
# 需求三：即使达到 max_items，仍继续请求并记录后续 Feed（发现后续失败 -> partial）
# ---------------------------------------------------------------------------
def test_max_items_processes_all_feeds(monkeypatch, fixed_dns):
    def fake_get(url, **kwargs):
        if "bad" in url:
            raise requests.exceptions.ConnectionError("refused")
        return FakeResponse(text=MANY_RSS)

    monkeypatch.setattr("app.collectors.foreign_rss.requests.get", fake_get)
    collector = ForeignRSSCollector(
        feeds=["https://news.example/ok", "https://news.example/bad"],
        keywords=["topic"], is_foreign=True, max_items=2, max_retries=0,
    )
    items = collector.fetch()
    reports = collector.last_feed_reports
    # 两个 Feed 都必须被请求并记录（不得因达到 max_items 而跳过后续 Feed）。
    assert len(reports) == 2, reports
    # 第一个 Feed 有 5 条有效条目，max_items=2 仅限制写入数量，不限制计数。
    assert len(items) == 2
    assert reports[0]["valid_count"] == 5
    # 第二个 Feed 失败 -> 整体必须为 partial（不是 success）。
    assert reports[1]["error_category"] == "network_failed"
    assert summarize_rss_probe(reports)["status"] == "partial"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
