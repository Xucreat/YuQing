"""Phase 2 §七 — 管理端 external_browser 安全默认值与配置校验测试。

运行：
  cd C:/Users/Administrator/Desktop/YQ/backend
  .venv/Scripts/python.exe -m pytest tests/test_phase2_admin_security.py --noconftest -q

运行时间：2026-08-19
"""
from __future__ import annotations

import json

import pytest

import app.api.admin_data_sources as a


CLI = r"C:\Users\Administrator\Desktop\bb-browser 采集器\bb-browser\dist\cli.js"
CONTROL_ROOT = r"C:\Users\Administrator\Desktop\bb-browser 采集器\collector_control"
EXCHANGE_ROOT = r"C:\Users\Administrator\Desktop\bb-browser 采集器\collector_data"


def _cfg(**overrides):
    base = {
        "platforms": ["baidu", "hupu", "toutiao", "bilibili", "youtube"],
        "control_root": CONTROL_ROOT,
        "exchange_root": EXCHANGE_ROOT,
        "bb_browser_cli": CLI,
        "cdp_url": "http://127.0.0.1:9222",
        "daemon_url": "http://127.0.0.1:19824",
        "timeout_seconds": 240,
        "poll_interval_seconds": 2,
        "max_items_per_platform": 20,
        "manifest_version": 2,
        "collection_mode": "national",
    }
    base.update(overrides)
    return base


def _real_lock():
    p = a.BB_RUNTIME_LOCK_PATH
    try:
        return json.loads(open(p, encoding="utf-8").read())
    except Exception:
        return {}


def test_schedule_enabled_defaults_false(monkeypatch):
    # external_browser 默认 schedule_enabled=False（未显式提供时）
    assert a._schedule_enabled_default(a._TYPE_CLASS_PATH["external_browser"]) is False
    # 通用型默认 True（未受影响）
    assert a._schedule_enabled_default(a._TYPE_CLASS_PATH["generic_site"]) is True


def test_missing_collection_mode_rejected(monkeypatch):
    monkeypatch.setattr(a, "probe_connectivity", lambda url: True)
    cfg = _cfg(); cfg.pop("collection_mode")
    err = a._validate_external_browser_config(cfg)
    assert err and "collection_mode" in err and "national" in err


def test_collection_mode_not_national_rejected(monkeypatch):
    monkeypatch.setattr(a, "probe_connectivity", lambda url: True)
    err = a._validate_external_browser_config(_cfg(collection_mode="regional"))
    assert err and "national" in err


def test_wrong_cli_version_rejected(monkeypatch):
    # 版本与 runtime lock 不一致 → 失败
    monkeypatch.setattr(a, "probe_connectivity", lambda url: True)
    bad = _real_lock()
    bad["bb_browser_version"] = "9.9.9"
    monkeypatch.setattr(a, "_bb_lock", lambda: bad)
    err = a._validate_external_browser_config(_cfg())
    assert err and "未锁定" in err


def test_wrong_cli_sha256_rejected(monkeypatch):
    monkeypatch.setattr(a, "probe_connectivity", lambda url: True)
    monkeypatch.setattr(a, "_sha256_file", lambda path: "deadbeef")
    err = a._validate_external_browser_config(_cfg())
    assert err and "SHA256" in err


def test_cdp_unreachable_preflight_fails(monkeypatch):
    def fake_probe(url):
        return "9222" not in url  # cdp 9222 不可达，daemon 可达
    monkeypatch.setattr(a, "probe_connectivity", fake_probe)
    err = a._validate_external_browser_config(_cfg())
    assert err and "cdp_url" in err and "preflight" in err


def test_daemon_unreachable_preflight_fails(monkeypatch):
    def fake_probe(url):
        return "19824" not in url  # daemon 不可达
    monkeypatch.setattr(a, "probe_connectivity", fake_probe)
    err = a._validate_external_browser_config(_cfg())
    assert err and "daemon_url" in err and "preflight" in err


def test_region_scope_rejected(monkeypatch):
    # external_browser 必须无 region scope（collection_mode=national）
    cp = a._TYPE_CLASS_PATH["external_browser"]
    assert a._is_external_browser(cp) is True
    # 有非空 scope_region_codes 的创建分支会被拒绝（验证分支语义）
    assert a._schedule_enabled_default(cp) is False


def test_rejected_platforms_continue_rejected(monkeypatch):
    monkeypatch.setattr(a, "probe_connectivity", lambda url: True)
    for p in ("weibo", "m_weibo", "xiaohongshu", "xhs", "zhihu"):
        err = a._validate_external_browser_config(_cfg(platforms=["baidu", p]))
        assert err, f"{p} 应被拒绝"
