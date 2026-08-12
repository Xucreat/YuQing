"""外网 RSS 验证状态契约测试（需求一/二/四/六）。

验证「四入口统一契约」：success / empty_feed / partial / failed 在
- POST /api/foreign/sources/test
- POST /api/admin/data-sources/test (通用 RSS 分支 _build_test)
两处返回一致的 {status, ok, verified}，且：
  success    -> ok=True,  verified=True
  empty_feed -> ok=True,  verified=True  （可达但为空源）
  partial    -> ok=False, verified=False （部分失败，绝不可当成功/已验证）
  failed     -> ok=False, verified=False （验证失败）

同时验证列表接口返回脱敏的 proxy_mode（统一代理解析，避免「UI 显示未配置但采集用了系统代理」）。
前端 foreignSourceStatus.test.ts 覆盖同样的四态映射，二者共同保证「前后端 partial 一致」。
"""
from __future__ import annotations

import uuid

from app.api.admin_data_sources import RSS_CLASS_PATH, _build_test
from app.collectors.foreign_rss import ForeignRSSCollector
from app.collectors.rss_collector import RSSCollector
from app.db.session import SessionLocal
from app.models.data_source import DataSource


def _report(error_category, valid_count, raw_count, matched_count, http_status, feed="https://f.test/rss"):
    return {
        "feed": feed,
        "http_status": http_status,
        "xml_parsed": True,
        "raw_count": raw_count,
        "matched_count": matched_count,
        "valid_count": valid_count,
        "title_count": valid_count,
        "error_category": error_category,
    }


# 四态的逐 Feed 报告集合（error_category=None 表示非致命）。
STATE_REPORTS = {
    "success": [_report(None, 3, 5, 2, 200)],
    "empty_feed": [_report(None, 0, 5, 0, 200)],
    "partial": [
        _report(None, 3, 5, 2, 200, feed="https://f.test/a"),
        _report("network_failed", 0, 0, 0, None, feed="https://f.test/b"),
    ],
    "failed": [_report("network_failed", 0, 0, 0, None)],
}

EXPECT = {
    "success": (True, True),
    "empty_feed": (True, True),
    "partial": (False, False),
    "failed": (False, False),
}


def _patch_probe(monkeypatch, reports):
    monkeypatch.setattr(
        ForeignRSSCollector, "probe", lambda self: list(reports)
    )
    monkeypatch.setattr(
        "app.collectors.foreign_rss.probe_proxy_health",
        lambda *a, **k: {"mode": "direct_default", "tcp_reachable": None},
    )
    monkeypatch.setattr(
        "app.collectors.common.socket.getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )


def test_foreign_test_endpoint_four_state_contract(client, auth_headers, monkeypatch):
    created_ids = []
    try:
        for state in ("success", "empty_feed", "partial", "failed"):
            _patch_probe(monkeypatch, STATE_REPORTS[state])
            key = f"contract_{state}_{uuid.uuid4().hex[:8]}"
            created = client.post(
                "/api/foreign/sources",
                headers=auth_headers,
                json={"name": f"Contract {state}", "key": key, "feeds": ["https://f.test/rss"]},
            )
            assert created.status_code == 201, created.text
            created_ids.append(created.json()["id"])

            test_resp = client.post(
                "/api/foreign/sources/test",
                headers=auth_headers,
                json={"source_id": created.json()["id"], "fetch_full_text": False},
            )
            assert test_resp.status_code == 200, test_resp.text
            body = test_resp.json()
            exp_ok, exp_verified = EXPECT[state]
            assert body["status"] == state, body
            assert body["ok"] is exp_ok, f"{state}: ok={body['ok']}"
            assert body["verified"] is exp_verified, f"{state}: verified={body['verified']}"

            # 持久化一致性：列表项 last_probe_status / verified 与测试结果对齐。
            listing = client.get("/api/foreign/sources", headers=auth_headers)
            item = next(
                it for it in listing.json()["items"] if it["id"] == created.json()["id"]
            )
            assert item["last_probe_status"] == state, item
            assert item["verified"] is exp_verified, item
            # 代理模式脱敏返回（即使测试环境存在 HTTPS_PROXY/HTTP_PROXY 回退也应如实反映）。
            assert isinstance(item["proxy_mode"], str) and "://" not in item["proxy_mode"], item
    finally:
        db = SessionLocal()
        try:
            for sid in created_ids:
                db.query(DataSource).filter(DataSource.id == sid).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_admin_build_test_four_state_contract(monkeypatch):
    """管理端通用 RSS 分支 _build_test 使用同一套 summarize_rss_probe 契约。"""
    for state in ("success", "empty_feed", "partial", "failed"):
        monkeypatch.setattr(
            RSSCollector, "probe", lambda self: list(STATE_REPORTS[state])
        )
        res = _build_test(RSS_CLASS_PATH, {"feeds": [{"url": "https://f.test/rss"}]})
        exp_ok, exp_verified = EXPECT[state]
        assert res["status"] == state, res
        assert res["ok"] is exp_ok, f"{state}: ok={res['ok']}"
        assert res["verified"] is exp_verified, f"{state}: verified={res['verified']}"


def test_proxy_mode_reflects_env_fallback(monkeypatch):
    """列表接口 proxy_mode 必须反映实际生效的代理（含环境变量回退），不误导为「未配置」。"""
    from app.collectors.foreign_rss import resolve_proxy_mode

    # 无任何代理环境变量 -> 直连（默认）
    monkeypatch.delenv("FOREIGN_HTTP_PROXY", raising=False)
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("HTTP_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    monkeypatch.delenv("http_proxy", raising=False)
    assert resolve_proxy_mode(proxy_env="FOREIGN_HTTP_PROXY") == "direct_default"

    # 系统 HTTPS_PROXY 已设，即便 proxy_env 指向未定义变量，也应如实返回 env:HTTPS_PROXY
    monkeypatch.setenv("HTTPS_PROXY", "http://10.0.0.1:3128")
    assert resolve_proxy_mode(proxy_env="FOREIGN_HTTP_PROXY") == "env:HTTPS_PROXY"

    # 显式 proxy_env 指向已定义变量 -> env:<NAME>
    monkeypatch.setenv("MY_PROXY", "http://10.0.0.2:3128")
    assert resolve_proxy_mode(proxy_env="MY_PROXY") == "env:MY_PROXY"

    # 显式直连优先于所有代理
    assert resolve_proxy_mode(use_direct=True, proxy_env="MY_PROXY") == "direct"
