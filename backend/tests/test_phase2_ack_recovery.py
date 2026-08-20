"""Phase 2 §六 — 跨进程 ack 恢复测试。

运行：
  cd C:/Users/Administrator/Desktop/YQ/backend
  .venv/Scripts/python.exe -m pytest tests/test_phase2_ack_recovery.py --noconftest -q

运行时间：2026-08-19
"""
from __future__ import annotations

import json
from pathlib import Path

from app.collectors.bb_browser_collector import BBBrowserCollector


def _mk_incoming(exchange: Path, name: str, content: str = "hello") -> Path:
    incoming = exchange / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    p = incoming / name
    p.write_text(content, encoding="utf-8")
    return p


def _write_record(exchange: Path, manifest_id: str, run_id: int, files: list) -> Path:
    ack = exchange / "ack_pending"
    ack.mkdir(parents=True, exist_ok=True)
    p = ack / f"{manifest_id}.json"
    p.write_text(json.dumps({
        "manifest_id": manifest_id,
        "collector_run_id": run_id,
        "created_at": "2026-08-19T00:00:00+00:00",
        "files": files,
    }, ensure_ascii=False), encoding="utf-8")
    return p


def test_ack_writes_record_and_clears_on_success(tmp_path):
    exchange = tmp_path / "exchange"
    f = _mk_incoming(exchange, "baidu_a.txt")
    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path / "control"),
                              exchange_root=str(exchange))
    coll._current_manifest_id = "M1"
    coll._pending_files = [f]
    ok = coll.ack_pending_export(collector_run_id=123)
    assert ok is True
    assert not (exchange / "incoming" / "baidu_a.txt").exists()  # 已移到 processed
    assert (exchange / "processed" / "baidu_a.txt").exists()
    assert not (exchange / "ack_pending" / "M1.json").exists()  # 记录已清理


def test_ack_failure_keeps_record_for_recovery(tmp_path):
    exchange = tmp_path / "exchange"
    f = _mk_incoming(exchange, "baidu_b.txt")
    # 目标已存在且内容不同 → 拒绝覆盖
    processed = exchange / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    (processed / "baidu_b.txt").write_text("DIFFERENT", encoding="utf-8")
    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path / "control"),
                              exchange_root=str(exchange))
    coll._current_manifest_id = "M2"
    coll._pending_files = [f]
    ok = coll.ack_pending_export(collector_run_id=456)
    assert ok is False
    # ack-pending 记录保留（供跨进程恢复）
    rec = json.loads((exchange / "ack_pending" / "M2.json").read_text(encoding="utf-8"))
    assert rec["collector_run_id"] == 456
    assert rec["manifest_id"] == "M2"


def test_new_instance_recovers_pending_ack(tmp_path):
    exchange = tmp_path / "exchange"
    # 模拟：旧实例写了记录但移动前崩溃，incoming 文件仍在
    f = _mk_incoming(exchange, "baidu_c.txt", "payload")
    rec_files = [{"source": str(f), "target": str(exchange / "processed" / "baidu_c.txt")}]
    _write_record(exchange, "M3", 789, rec_files)

    # 新实例（无 _pending_files）恢复
    new_coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path / "control"),
                                  exchange_root=str(exchange))
    result = new_coll.recover_pending_ack(exchange)
    assert result["recovered"] == 1
    assert (exchange / "processed" / "baidu_c.txt").read_text(encoding="utf-8") == "payload"
    assert not (exchange / "ack_pending" / "M3.json").exists()  # 记录已清


def test_ack_files_idempotent_four_cases(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir(parents=True, exist_ok=True)

    # 1. source 存在 target 不存在 → move
    s1 = tmp_path / "s1.txt"; s1.write_text("a", encoding="utf-8")
    ok, _ = BBBrowserCollector._ack_files([{"source": str(s1), "target": str(processed / "s1.txt")}], processed)
    assert ok and (processed / "s1.txt").exists()

    # 2. source 缺失 target 内容一致 → confirmed
    ok, _ = BBBrowserCollector._ack_files([{"source": str(tmp_path / "gone.txt"), "target": str(processed / "s1.txt")}], processed)
    assert ok

    # 3. source/target 内容不一致 → 拒绝覆盖
    s3 = tmp_path / "s3.txt"; s3.write_text("new", encoding="utf-8")
    (processed / "s3.txt").write_text("old", encoding="utf-8")
    ok, detail = BBBrowserCollector._ack_files([{"source": str(s3), "target": str(processed / "s3.txt")}], processed)
    assert not ok and "differ" in detail
    assert (processed / "s3.txt").read_text(encoding="utf-8") == "old"  # 未覆盖

    # 4. 两者都不存在 → recovery_failed
    ok, detail = BBBrowserCollector._ack_files([{"source": str(tmp_path / "nope.txt"), "target": str(processed / "nope.txt")}], processed)
    assert not ok and "missing" in detail


def test_recover_does_not_ack_orphan_incoming(tmp_path):
    exchange = tmp_path / "exchange"
    # 孤立 incoming（无对应 ack-pending 记录）
    orphan = _mk_incoming(exchange, "orphan.txt")
    # 另一个合法记录
    f = _mk_incoming(exchange, "baidu_d.txt")
    _write_record(exchange, "M4", 1, [{"source": str(f), "target": str(exchange / "processed" / "baidu_d.txt")}])

    BBBrowserCollector.recover_pending_ack(exchange)
    assert orphan.exists()  # 孤立 incoming 未被 ack
    assert not (exchange / "incoming" / "baidu_d.txt").exists()  # 有记录的已 ack


def test_recover_preserves_old_incoming(tmp_path):
    exchange = tmp_path / "exchange"
    old = _mk_incoming(exchange, "OLD_historical.txt", "historical")
    # 只对旧文件做一次恢复（无记录），旧 incoming 必须保持不变
    result = BBBrowserCollector.recover_pending_ack(exchange)
    assert result["recovered"] == 0
    assert old.read_text(encoding="utf-8") == "historical"
