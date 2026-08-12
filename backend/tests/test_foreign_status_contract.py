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

import json
import uuid

from sqlalchemy import select

from app.api.admin_data_sources import RSS_CLASS_PATH, _build_test
from app.collectors.common import RSS_PROBE_FATAL_CATEGORIES, summarize_rss_probe
from app.collectors.foreign_rss import ForeignRSSCollector
from app.collectors.rss_collector import RSSCollector
from app.db.session import SessionLocal
from app.models.collector_run import CollectorRun
from app.models.data_source import DataSource
from app.models.foreign_keyword import ForeignKeyword
from app.models.foreign_opinion import ForeignOpinion
from app.services.foreign_collection_service import collect_foreign


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


# ---------------------------------------------------------------------------
# 需求一：混合 Feed 状态判定（可达 != 有有效文章）
# ---------------------------------------------------------------------------
def _rep(error_category, valid_count, raw_count=0):
    return {"error_category": error_category, "valid_count": valid_count, "raw_count": raw_count}


def test_summarize_rss_probe_mixed_feed_states():
    """可达性基于致命 error_category，而非 valid_count：空 Feed + 失败 Feed 必须判 partial。"""
    # 1) 空 Feed 列表 -> 兜底 empty_feed（真实空 feeds 由调用方配置校验报错，见下）
    assert summarize_rss_probe([])["status"] == "empty_feed"
    # 2) 失败 Feed
    assert summarize_rss_probe([_rep("network_failed", 0)])["status"] == "failed"
    # 3) 空 Feed(可达) + 失败 Feed -> partial（曾误判为 failed）
    s = summarize_rss_probe([_rep(None, 0), _rep("network_failed", 0)])
    assert s["status"] == "partial" and s["ok"] is False and s["verified"] is False
    # 4) 有效 Feed + 失败 Feed -> partial
    assert summarize_rss_probe([_rep(None, 3), _rep("network_failed", 0)])["status"] == "partial"
    # 5) 全部空 Feed(均可达) -> empty_feed（ok/verified=True）
    e = summarize_rss_probe([_rep(None, 0), _rep(None, 0)])
    assert e["status"] == "empty_feed" and e["ok"] is True and e["verified"] is True
    # 6) 全部失败 Feed -> failed
    assert summarize_rss_probe([_rep("http_failed", 0), _rep("network_failed", 0)])["status"] == "failed"
    # 7) 有效 Feed 且无失败 -> success
    assert summarize_rss_probe([_rep(None, 3)])["status"] == "success"
    # 8) 非空但未知的 error_category 必须 fail-closed 当成失败（不得误判为可达）
    u = summarize_rss_probe([_rep(None, 3), _rep("unknown_error", 0)])
    assert u["status"] == "partial" and u["ok"] is False and u["verified"] is False
    # 9a) 空 Feed(可达) + 未知错误 -> partial（不是 empty_feed/success）
    u2 = summarize_rss_probe([_rep(None, 0), _rep("weird_category", 0)])
    assert u2["status"] == "partial" and u2["ok"] is False
    # 9b) 有效 Feed(可达) + 未知错误 -> partial（不是 success）
    u3 = summarize_rss_probe([_rep(None, 2), _rep("mystery", 0)])
    assert u3["status"] == "partial" and u3["ok"] is False
    # 9c) 全部未知错误 -> failed（fail-closed）
    assert summarize_rss_probe([_rep("unknown_error", 0), _rep("mystery", 1)])["status"] == "failed"


def test_build_test_empty_feeds_not_masked_as_success(monkeypatch):
    """需求一：无待探测 Feed 由配置校验报错，不得伪装成 success/empty_feed。"""
    monkeypatch.setattr(RSSCollector, "probe", lambda self: [])
    res = _build_test(RSS_CLASS_PATH, {"feeds": []})
    assert res["ok"] is False
    assert res["status"] == "failed"
    assert "RSS" in (res.get("error") or "")


# ---------------------------------------------------------------------------
# 需求四：管理端测试接口顶层返回与四态契约（方案 A）
# ---------------------------------------------------------------------------
def test_admin_endpoint_four_state_contract(client, auth_headers, monkeypatch):
    created_keys = []
    try:
        for state in ("success", "empty_feed", "partial", "failed"):
            monkeypatch.setattr(RSSCollector, "probe", lambda self: list(STATE_REPORTS[state]))
            key = f"admin_contract_{state}_{uuid.uuid4().hex[:8]}"
            created_keys.append(key)
            resp = client.post(
                "/api/admin/data-sources/test",
                headers=auth_headers,
                json={
                    "name": f"Admin {state}",
                    "key": key,
                    "type": "rss",
                    "config_json": {"feeds": [{"url": "https://f.test/rss"}]},
                },
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            exp_ok, exp_verified = EXPECT[state]
            # 顶层与外网测试接口统一
            assert body["status"] == state, body
            assert body["ok"] is exp_ok, body
            assert body["verified"] is exp_verified, body
            # 旧客户端嵌套 test 仍可用
            assert body["test"]["status"] == state, body
            assert body["test"]["ok"] is exp_ok, body
    finally:
        db = SessionLocal()
        try:
            for k in created_keys:
                db.query(DataSource).filter(DataSource.key == k).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 需求五：空 Feed + 失败 Feed 持久化状态为 partial / ok=false / verified=false
# ---------------------------------------------------------------------------
def test_persist_empty_feed_plus_failed(client, auth_headers, monkeypatch):
    _patch_probe(
        monkeypatch,
        [
            _report(None, 0, 5, 0, 200, feed="https://f.test/a"),
            _report("network_failed", 0, 0, 0, None, feed="https://f.test/b"),
        ],
    )
    key = f"persist_partial_{uuid.uuid4().hex[:8]}"
    created = client.post(
        "/api/foreign/sources",
        headers=auth_headers,
        json={"name": "Persist partial", "key": key, "feeds": ["https://f.test/rss"]},
    )
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]
    try:
        test_resp = client.post(
            "/api/foreign/sources/test",
            headers=auth_headers,
            json={"source_id": source_id, "fetch_full_text": False},
        )
        assert test_resp.status_code == 200, test_resp.text
        body = test_resp.json()
        assert body["status"] == "partial", body
        assert body["ok"] is False, body
        assert body["verified"] is False, body
        listing = client.get("/api/foreign/sources", headers=auth_headers)
        item = next((it for it in listing.json()["items"] if it["id"] == source_id), None)
        assert item is not None
        assert item["last_probe_status"] == "partial", item
        assert item["verified"] is False, item
    finally:
        db = SessionLocal()
        try:
            db.query(DataSource).filter(DataSource.id == source_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 需求二：正式采集状态语义（基于 Feed 级别可达性，而非关键词命中 items）
# ---------------------------------------------------------------------------
def _foreign_source_id(db, key, name, feeds, keyword_word):
    # keyword_word 在同一测试运行中跨多个 scenario 复用，仅首次创建，避免
    # uq_foreign_keywords_word 唯一约束在后续 scenario 重复插入时冲突。
    existing = db.scalar(select(ForeignKeyword).where(ForeignKeyword.word == keyword_word))
    if existing is None:
        kw = ForeignKeyword(word=keyword_word)
        db.add(kw)
    src = DataSource(
        key=key,
        name=name,
        type="foreign_rss",
        class_path="app.collectors.foreign_rss.ForeignRSSCollector",
        enabled=True,
        schedule_enabled=False,
        config_json=json.dumps(
            {
                "is_foreign": True,
                "collector": "foreign_rss",
                "feeds": feeds,
                "keywords": [keyword_word],
                "collection_mode": "foreign",
            }
        ),
    )
    db.add(src)
    db.commit()
    return src.id


def _fake_fetch(reports, items):
    def _f(self, **kwargs):
        self.last_feed_reports = [dict(r) for r in reports]
        self.last_failed_feeds = sum(
            1 for r in reports if r.get("error_category") in RSS_PROBE_FATAL_CATEGORIES
        )
        self.last_reachable_feeds = sum(
            1 for r in reports if r.get("error_category") not in RSS_PROBE_FATAL_CATEGORIES
        )
        self.last_fetched_raw = sum(r.get("raw_count", 0) for r in reports)
        self.last_error = None
        return list(items)

    return _f


def test_collect_foreign_status_semantics(monkeypatch):
    """正式采集：success/partial/failed 与测试接口同语义；空源映射 success 但保留信息。"""
    keyword_word = f"kw_{uuid.uuid4().hex[:8]}"
    scenarios = [
        # (描述, reports, items, 期望 run.status, 期望 run.failed)
        ("all_success_no_hit", [_rep(None, 0)], [], "success", 0),
        ("empty_plus_failed", [_rep(None, 0), _rep("network_failed", 0)], [], "partial", 1),
        ("valid_plus_failed", [_rep(None, 3), _rep("network_failed", 0)],
         [{"title": "t", "url": "https://x/a", "content": "b", "summary": "s",
           "matched_keywords": [keyword_word]}], "partial", 1),
        ("all_failed", [_rep("network_failed", 0), _rep("http_failed", 0)], [], "failed", 2),
    ]
    created = []
    try:
        for desc, reports, items, exp_status, exp_failed in scenarios:
            monkeypatch.setattr(ForeignRSSCollector, "fetch", _fake_fetch(reports, items))
            key = f"collect_{desc}_{uuid.uuid4().hex[:8]}"
            name = f"Collect {desc}"
            feeds = [f"https://f.test/{desc}/rss"]
            sid = _foreign_source_id(SessionLocal(), key, name, feeds, keyword_word)
            created.append((key, name, sid))
            db = SessionLocal()
            try:
                result = collect_foreign(db, source_ids=[sid])
                assert result["sources"] == 1, result
                run = (
                    db.query(CollectorRun)
                    .filter(CollectorRun.collector_name == name, CollectorRun.scope == "foreign")
                    .order_by(CollectorRun.id.desc())
                    .first()
                )
                assert run is not None, f"{desc}: no run"
                assert run.status == exp_status, f"{desc}: status={run.status}"
                assert int(run.failed or 0) == exp_failed, f"{desc}: failed={run.failed}"
                if desc == "all_success_no_hit":
                    # 空源：映射 success 但保留「可达但无内容」信息
                    assert run.error_msg and "可达但无内容" in run.error_msg, run.error_msg
            finally:
                db.close()
    finally:
        db = SessionLocal()
        try:
            for key, name, sid in created:
                db.query(ForeignOpinion).filter(ForeignOpinion.source_key == key).delete(
                    synchronize_session=False
                )
                db.query(CollectorRun).filter(CollectorRun.collector_name == name).delete(
                    synchronize_session=False
                )
                db.query(DataSource).filter(DataSource.id == sid).delete(synchronize_session=False)
            db.query(ForeignKeyword).filter(ForeignKeyword.word == keyword_word).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()
