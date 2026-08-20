"""Phase 2 §八 — 运行时锁定 preflight 测试。

运行：
  cd C:/Users/Administrator/Desktop/YQ/backend
  .venv/Scripts/python.exe -m pytest tests/test_phase2_runtime_lock.py --noconftest -q

运行时间：2026-08-19
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.collectors.bb_browser_collector import BBBrowserCollector
from app.collectors.bb_browser_runtime import (
    CollectorError,
    ERR_RUNTIME_DRIFT,
    verify_runtime_lock,
)

REAL_LOCK = r"C:\Users\Administrator\Desktop\bb-browser 采集器\phase2_runtime_lock.json"
BB_SITES = r"C:\Users\Administrator\.bb-browser\bb-sites"


def test_real_runtime_lock_verifies_ok():
    if not Path(REAL_LOCK).exists():
        pytest.skip("真实 runtime lock 不存在")
    ok, diffs = verify_runtime_lock(REAL_LOCK, bb_sites_dir=BB_SITES)
    assert ok, f"运行时发生漂移：{diffs}"


def test_verify_detects_drift(tmp_path):
    lock = {
        "python_worker_entry": str(tmp_path / "nope.py"),
        "node_cli": str(tmp_path / "nope.js"),
        "node_cli_sha256": "deadbeef",
        "bb_browser_version": "9.9.9",
        "exchange_root": str(tmp_path / "exchange"),
        "control_root": str(tmp_path / "control"),
        "bb_sites_head": "deadbeef",
        "platform_registry_sha256": "deadbeef",
    }
    lp = tmp_path / "phase2_runtime_lock.json"
    lp.write_text(json.dumps(lock), encoding="utf-8")
    ok, diffs = verify_runtime_lock(lp, bb_sites_dir=str(tmp_path / "nope-bbsites"))
    assert not ok
    fields = {d["field"] for d in diffs}
    assert "node_cli" in fields or "python_worker_entry" in fields


def test_preflight_blocks_fetch_on_drift(tmp_path):
    control = tmp_path / "control"
    control.mkdir(parents=True)
    lock = {
        "python_worker_entry": str(tmp_path / "nope.py"),
        "node_cli": str(tmp_path / "nope.js"),
        "node_cli_sha256": "deadbeef",
        "bb_browser_version": "9.9.9",
        "exchange_root": str(tmp_path / "exchange"),
        "control_root": str(control),
        "bb_sites_head": "deadbeef",
        "platform_registry_sha256": "deadbeef",
    }
    # collector 从 control_root 父目录推导 lock 路径
    (tmp_path / "phase2_runtime_lock.json").write_text(json.dumps(lock), encoding="utf-8")

    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(control),
                              exchange_root=str(tmp_path / "exchange"))
    ok, diffs = coll.preflight()
    assert not ok

    with pytest.raises(CollectorError) as exc:
        coll.fetch()
    assert exc.value.code == ERR_RUNTIME_DRIFT
    # 生成差异报告
    assert (control / "runtime_drift.json").exists()
    report = json.loads((control / "runtime_drift.json").read_text(encoding="utf-8"))
    assert report["code"] == ERR_RUNTIME_DRIFT


def test_preflight_skips_when_lock_missing(tmp_path):
    # 测试环境（显式 test_mode=True）→ 缺失 lock 不阻断（fail-open 仅供测试）
    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path / "control"),
                              exchange_root=str(tmp_path / "exchange"))
    ok, diffs = coll.preflight(test_mode=True)
    assert ok and diffs == []
    # 等价：构造时声明 test_mode
    coll2 = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path / "control"),
                               exchange_root=str(tmp_path / "exchange"), test_mode=True)
    ok2, _ = coll2.preflight()
    assert ok2


def test_preflight_fails_when_lock_missing_in_production(tmp_path):
    # 生产环境（默认 test_mode=False）→ 缺失 lock 必须失败（runtime_drift），不得 fail-open
    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path / "control"),
                              exchange_root=str(tmp_path / "exchange"))
    ok, diffs = coll.preflight()
    assert not ok
    fields = {d["field"] for d in diffs}
    assert "lock_file" in fields
    # 同样 fetch() 在生产缺失 lock 时必须阻断
    with pytest.raises(CollectorError) as exc:
        coll.fetch()
    assert exc.value.code == ERR_RUNTIME_DRIFT
