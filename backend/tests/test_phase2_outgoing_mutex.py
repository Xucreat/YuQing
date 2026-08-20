"""Phase 2 §三 — outgoing 跨进程原子互斥测试。

运行：
  cd C:/Users/Administrator/Desktop/YQ/backend
  .venv/Scripts/python.exe -m pytest tests/test_phase2_outgoing_mutex.py --noconftest -q

运行时间：2026-08-19
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.collectors.bb_browser_runtime import (
    OutgoingLockError,
    OutgoingMutex,
    pid_alive,
)

BACKEND = Path(__file__).resolve().parents[2]  # .../backend


def _write_lock(outgoing: Path, owner_pid: int, manifest_id: str, last_seen: float) -> None:
    (outgoing / ".bb_outgoing.lock").write_text(json.dumps({
        "owner_pid": owner_pid,
        "manifest_id": manifest_id,
        "created_at": 0.0,
        "last_seen": last_seen,
        "hostname": "",
    }), encoding="utf-8")


def test_acquire_release_roundtrip(tmp_path):
    # 锁释放后下一次任务可以执行
    m1 = OutgoingMutex(tmp_path / "outgoing", stale_dir=tmp_path / "stale")
    m1.acquire("RUN1")
    assert (tmp_path / "outgoing" / ".bb_outgoing.lock").exists()
    m1.release()
    assert not (tmp_path / "outgoing" / ".bb_outgoing.lock").exists()
    m2 = OutgoingMutex(tmp_path / "outgoing", stale_dir=tmp_path / "stale")
    m2.acquire("RUN2")  # 不抛异常
    assert m2.lock_info.manifest_id == "RUN2"
    m2.release()


def test_two_acquire_one_rejected(tmp_path):
    # 一个成功、一个被拒绝（worker_busy）
    m1 = OutgoingMutex(tmp_path / "outgoing", stale_dir=tmp_path / "stale")
    m1.acquire("HOLDER")
    m2 = OutgoingMutex(tmp_path / "outgoing", stale_dir=tmp_path / "stale")
    with pytest.raises(OutgoingLockError) as exc:
        m2.acquire("INTRUDER")
    assert exc.value.code == "worker_busy"
    assert m1.lock_info.manifest_id == "HOLDER"  # 原持有者未受影响
    m1.release()


def test_stale_dead_pid_recovers(tmp_path):
    # owner pid 已死 → 回收并继续，不阻塞
    outgoing = tmp_path / "outgoing"
    outgoing.mkdir()
    (outgoing / "dead-task.txt").write_text("old", encoding="utf-8")
    _write_lock(outgoing, 99999999, "dead-task", time.time())  # 死 pid
    m = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m.acquire("NEW")  # 不抛异常
    assert m.lock_info.manifest_id == "NEW"
    # 旧 manifest 迁到 stale/ 并留证，未删除
    assert (tmp_path / "stale" / "dead-task.txt").exists()
    assert (tmp_path / "stale" / "dead-task.stale.json").exists()
    m.release()


def test_stale_ttl_recovers(tmp_path):
    # owner 仍存活但 last_seen 超过 TTL → 判定 stale 并回收
    outgoing = tmp_path / "outgoing"
    outgoing.mkdir()
    _write_lock(outgoing, os.getpid(), "ghost", 0.0)  # last_seen 极旧
    m = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale", ttl_seconds=1)
    m.acquire("NEW2")  # 不抛异常（TTL 判定）
    assert m.lock_info.manifest_id == "NEW2"
    m.release()


def test_no_delete_other_manifest(tmp_path):
    # 活跃锁存在时拒绝，且绝不删除 / 覆盖他人 manifest
    outgoing = tmp_path / "outgoing"
    outgoing.mkdir()
    other = outgoing / "other-process-manifest.txt"
    other.write_text("DO-NOT-DELETE", encoding="utf-8")
    m1 = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m1.acquire("other-process-manifest")  # 活跃锁，manifest 即 others
    m2 = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    with pytest.raises(OutgoingLockError):
        m2.acquire("INTRUDER2")
    assert other.read_text(encoding="utf-8") == "DO-NOT-DELETE"  # 未被删除/覆盖
    m1.release()


def test_cross_process_holder_rejected_then_acquire(tmp_path):
    # 真跨进程：子进程持有锁，父进程被拒；子进程退出后父进程可获取
    outgoing = str(tmp_path / "outgoing")
    stale = str(tmp_path / "stale")
    held = tmp_path / "held"
    holder_code = (
        "import sys, time\n"
        f"sys.path.insert(0, {str(BACKEND)!r})\n"
        "from app.collectors.bb_browser_runtime import OutgoingMutex\n"
        f"m = OutgoingMutex({outgoing!r}, stale_dir={stale!r})\n"
        "m.acquire('HOLDER')\n"
        f"open({str(held)!r}, 'w').write('ok')\n"
        "time.sleep(3)\n"
        "m.release()\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", holder_code])
    try:
        deadline = time.time() + 15
        while not held.exists() and time.time() < deadline:
            time.sleep(0.1)
        assert held.exists(), "holder 子进程未在限时内获取锁"
        assert pid_alive(proc.pid) is True  # 子进程确在运行
        parent = OutgoingMutex(tmp_path / "outgoing", stale_dir=tmp_path / "stale")
        with pytest.raises(OutgoingLockError) as exc:
            parent.acquire("PARENT")
        assert exc.value.code == "worker_busy"
    finally:
        proc.wait(timeout=15)
    # 子进程退出并释放后，父进程可获取
    after = OutgoingMutex(tmp_path / "outgoing", stale_dir=tmp_path / "stale")
    after.acquire("PARENT2")
    assert after.lock_info.manifest_id == "PARENT2"
    after.release()
