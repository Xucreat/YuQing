# -*- coding: utf-8 -*-
"""Phase 2：Worker Cancellation & Orphan Prevention —— 纯合成测试（零真实采集）。

约定（与 Implementation-1 一致，并强化）：
- 绝不触发真实 bb-browser 子进程 / 平台搜索 / 生产 DB 写入。
- 全部 IO 经 tmp_path；assert 验证没有任何真实 runtime lock / subprocess 被调用。
- 仅验证「取消契约」：<manifest_id>.cancelled sidecar + collector 超时钩子 + worker 检查。
- 外部 Node worker（bb-browser 采集/collector_exchange）不在本仓库，本测试用 FakeWorker
  模拟其在每个 source/rule 边界调用 is_manifest_cancelled 的决策逻辑。
"""
from pathlib import Path
from unittest import mock

from app.collectors import bb_browser_collector as mod
from app.collectors.bb_browser_collector import (
    BBBrowserCollector,
    PendingFile,
    build_manifest,
)
from app.collectors.bb_browser_runtime import (
    MANIFEST_CANCELLED_EXT,
    is_manifest_cancelled,
    mark_manifest_cancelled,
    clear_manifest_cancelled,
    verify_runtime_lock,
)
from app.collectors.bb_browser_recovery import (
    ManifestRecovery,
    S_CANCELLED,
    S_RETRYABLE,
)


# ---------------------------------------------------------------------------
# 合成 harness（与 test_bb_browser_batching 同构，确保零真实采集）
# ---------------------------------------------------------------------------
def _make_coll(tmp_path, platforms=("xiaohongshu",)):
    ctrl = tmp_path / "control"
    exch = tmp_path / "exchange"
    (ctrl / "outgoing").mkdir(parents=True, exist_ok=True)
    (exch / "incoming").mkdir(parents=True, exist_ok=True)
    return BBBrowserCollector(
        platforms=list(platforms),
        control_root=str(ctrl),
        exchange_root=str(exch),
        test_mode=True,
    )


def _patch_io(coll, tmp_path, *, ready_policy, bad_ids=None, raw_per_file=1, items_per_file=1):
    """统一打桩：manifest 写出捕获、结果等待按 ready_policy 返回、解析/归一化合成。

    ready_policy: callable(call_index, expected) -> list[(task_id, source_key)]
                  返回该批次应「就绪」的子集（未就绪项模拟超时未完成）。
    """
    captured = []
    calls = {"n": 0}
    bad_ids = bad_ids or set()

    def fake_write(outgoing, manifest_id, text):
        captured.append((manifest_id, text))

    def fake_wait(manifest_id, expected, partial=False):
        calls["n"] += 1
        chosen = list(ready_policy(calls["n"] - 1, expected))
        chosen_set = set(chosen)
        coll._partial_missing.extend([e for e in expected if e not in chosen_set])
        pfs = []
        for (tid, src) in chosen:
            p = tmp_path / f"{manifest_id}_{tid}_{src}.txt"
            p.write_text("{}")
            pfs.append(PendingFile(
                manifest_id=manifest_id, task_id=tid, source_key=src,
                path=p, file_size=2,
            ))
        return pfs

    def fake_parse(path):
        name = Path(str(path)).name
        if any(b in name for b in bad_ids):
            return {"error": "401 login required", "content": None}
        return {"error": None, "content": {"items": [{"id": 1}]}}

    def fake_normalize(src, content, max_items=None):
        return [{"source": src, "id": i} for i in range(items_per_file)]

    def fake_raw(src, content):
        return raw_per_file

    patchers = [
        mock.patch.object(mod, "write_manifest_atomic", fake_write),
        mock.patch.object(coll, "_wait_for_results", side_effect=fake_wait),
        mock.patch.object(mod, "parse_record_text", side_effect=fake_parse),
        mock.patch.object(mod, "normalize_record", side_effect=fake_normalize),
        mock.patch.object(mod, "raw_item_count", side_effect=fake_raw),
    ]
    started = [p.start() for p in patchers]
    calls["wait"] = started[1]
    return captured, calls, patchers


def _stop(patchers):
    for p in reversed(patchers):
        try:
            p.stop()
        except Exception:
            pass


def _fake_worker(control_root, manifest_id, sources):
    """模拟外部 worker：在每个 source 前检查 cancellation，已取消则停止未来工作。"""
    if is_manifest_cancelled(control_root, manifest_id):
        return 0
    return len(sources)


# ---------------------------------------------------------------------------
# Test 1：cancellation marker 写入/读取
# ---------------------------------------------------------------------------
def test_1_cancellation_marker_write_read(tmp_path):
    ctrl = tmp_path / "control"
    (ctrl / "outgoing").mkdir(parents=True, exist_ok=True)
    mid = "abc123"
    p = mark_manifest_cancelled(ctrl, mid, reason="batch_timeout")
    assert p is not None and p.exists()
    assert p.name == f"{mid}{MANIFEST_CANCELLED_EXT}"
    import json
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["manifest_id"] == mid and data["reason"] == "batch_timeout"
    assert is_manifest_cancelled(ctrl, mid) is True
    assert is_manifest_cancelled(ctrl, "other") is False


# ---------------------------------------------------------------------------
# Test 2：worker 看到 cancelled → 未来 source 采集 = 0
# ---------------------------------------------------------------------------
def test_2_worker_sees_cancelled(tmp_path):
    ctrl = tmp_path / "control"
    (ctrl / "outgoing").mkdir(parents=True, exist_ok=True)
    mid_cancel = "cancel01"
    mid_ok = "ok01"
    mark_manifest_cancelled(ctrl, mid_cancel, reason="batch_timeout")
    sources = [("t1", "baidu"), ("t2", "xiaohongshu")]
    assert _fake_worker(ctrl, mid_cancel, sources) == 0
    assert _fake_worker(ctrl, mid_ok, sources) == len(sources)


# ---------------------------------------------------------------------------
# Test 3：batch 隔离（仅取消其中一个 manifest）
# ---------------------------------------------------------------------------
def test_3_batch_isolation(tmp_path):
    ctrl = tmp_path / "control"
    (ctrl / "outgoing").mkdir(parents=True, exist_ok=True)
    m1, m2 = "batch_a", "batch_b"
    mark_manifest_cancelled(ctrl, m1)
    sources = [("t1", "baidu")]
    res = {
        "a": _fake_worker(ctrl, m1, sources),
        "b": _fake_worker(ctrl, m2, sources),
    }
    assert res["a"] == 0 and res["b"] == len(sources)


# ---------------------------------------------------------------------------
# Test 4：幂等性（重复标记不产生多文件 / 不覆盖时间戳）；clear 幂等
# ---------------------------------------------------------------------------
def test_4_idempotency(tmp_path):
    ctrl = tmp_path / "control"
    (ctrl / "outgoing").mkdir(parents=True, exist_ok=True)
    mid = "idem1"
    p1 = mark_manifest_cancelled(ctrl, mid)
    t1 = p1.stat().st_mtime_ns
    p2 = mark_manifest_cancelled(ctrl, mid)
    t2 = p2.stat().st_mtime_ns
    assert p1 == p2 and p1.exists()
    assert t1 == t2  # 幂等：不覆盖既有内容
    markers = list((ctrl / "outgoing").glob(f"{mid}{MANIFEST_CANCELLED_EXT}"))
    assert len(markers) == 1
    clear_manifest_cancelled(ctrl, mid)
    assert is_manifest_cancelled(ctrl, mid) is False
    clear_manifest_cancelled(ctrl, mid)  # 再次清除不报错
    assert is_manifest_cancelled(ctrl, mid) is False


# ---------------------------------------------------------------------------
# Test 5：batch 超时 → collector 写入 cancellation marker（仅超时批）
# ---------------------------------------------------------------------------
def test_5_timeout_triggers_cancellation(tmp_path):
    kw = [f"kw{i}" for i in range(16)]  # 2 批 × 8
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    runtime_called = {"n": 0}

    def _vrl_guard(*a, **k):
        runtime_called["n"] += 1
        return verify_runtime_lock(*a, **k)

    def ready_policy(idx, expected):
        if idx == 0:
            return list(expected)[:4]   # 第一批发部分（240s 超时未完成）
        return list(expected)            # 第二批发完整

    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=ready_policy)
    guard = mock.patch.object(mod, "verify_runtime_lock", side_effect=_vrl_guard)
    guard.start()
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
        guard.stop()

    assert len(captured) == 2
    mid0, mid1 = captured[0][0], captured[1][0]
    assert is_manifest_cancelled(coll.control_root, mid0) is True   # 超时批已取消
    assert is_manifest_cancelled(coll.control_root, mid1) is False  # 完整批不取消
    assert len(items) == 12       # 4 (partial) + 8 (full)
    assert coll.logical_status == "partial_success"
    assert runtime_called["n"] == 0   # 未触发真实 runtime lock（证明无真实采集）


# ---------------------------------------------------------------------------
# Test 6：全部成功 → 不写 cancellation marker
# ---------------------------------------------------------------------------
def test_6_full_success_no_cancellation(tmp_path):
    kw = [f"kw{i}" for i in range(16)]
    coll = _make_coll(tmp_path)
    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=lambda idx, exp: list(exp))
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert len(captured) == 2
    for mid, _ in captured:
        assert is_manifest_cancelled(coll.control_root, mid) is False
    assert coll.logical_status == "success"
    assert len(items) == 16


# ---------------------------------------------------------------------------
# Test 7：全部失败（超时 0 就绪）→ 两批均取消
# ---------------------------------------------------------------------------
def test_7_all_failed_cancels(tmp_path):
    kw = [f"kw{i}" for i in range(16)]
    coll = _make_coll(tmp_path)
    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=lambda idx, exp: [])
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert len(items) == 0
    for mid, _ in captured:
        assert is_manifest_cancelled(coll.control_root, mid) is True
    assert coll.logical_status == "failed"


# ---------------------------------------------------------------------------
# Test 8：incoming 保留（既有 incoming 与被 collector 产出的 partial 文件均不删除）
# ---------------------------------------------------------------------------
def test_8_incoming_preservation(tmp_path):
    kw = [f"kw{i}" for i in range(16)]
    coll = _make_coll(tmp_path)
    exch = tmp_path / "exchange"
    incoming = exch / "incoming"
    pre = [incoming / f"pre_{i}.txt" for i in range(5)]
    for f in pre:
        f.write_text("PRE")  # 既有 incoming（非本 collector 产出）
    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=lambda idx, exp: list(exp)[:4])
    try:
        coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    for f in pre:
        assert f.exists() and f.read_text() == "PRE"
    mid0 = captured[0][0]
    produced = list(tmp_path.glob(f"{mid0}_*.txt"))
    assert len(produced) >= 1  # partial 产出文件不被 collector 删除


# ---------------------------------------------------------------------------
# Test 9：孤儿隔离（晚到 incoming 不被 recover 重试；已取消 manifest 终止）
# ---------------------------------------------------------------------------
def test_9_late_incoming_isolation(tmp_path):
    coll = _make_coll(tmp_path)
    mid = "late1"
    ctrl = Path(coll.control_root)
    text = build_manifest(mid, ["kw"], ["xiaohongshu"], keyword_config_version="1", policy_version="1")
    (ctrl / "outgoing" / f"{mid}.txt").write_text(text)
    mark_manifest_cancelled(ctrl, mid, reason="batch_timeout")
    incoming = Path(coll.exchange_root) / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    (incoming / f"{mid}_late.txt").write_text("late incoming")  # worker 取消后才产出的晚到 incoming

    acted = coll.recover_prior_runs(reason="pre_create_recovery")
    assert all(m != mid for m, _ in acted)          # 已取消 → 不被重试/拒绝/归档
    assert is_manifest_cancelled(ctrl, mid) is True  # 取消态保持
    assert (incoming / f"{mid}_late.txt").exists()   # 晚到 incoming 不被 collector 删除

    # 终端态：inspect 返回 S_CANCELLED（recovery 据此不再续采）
    rec = ManifestRecovery(coll.control_root, coll.exchange_root, max_retries=3)
    assert rec.inspect(mid).state == S_CANCELLED


# ---------------------------------------------------------------------------
# Test 10：竞态模拟（worker 在下一个 source 前读到取消标记 → 干净停止）
# ---------------------------------------------------------------------------
def test_10_race_simulation(tmp_path):
    ctrl = tmp_path / "control"
    (ctrl / "outgoing").mkdir(parents=True, exist_ok=True)
    mid = "race1"
    sources = [("t0", "baidu"), ("t1", "baidu"), ("t2", "baidu")]
    collected = []

    def worker():
        for i, (tid, src) in enumerate(sources):
            if i == 1:  # 模拟「刚要开始下一个 source 时」collector 写入取消标记
                mark_manifest_cancelled(ctrl, mid)
            if is_manifest_cancelled(ctrl, mid):
                break  # 停止未来工作（不杀在途子进程，仅停止新 source）
            collected.append((tid, src))

    worker()
    assert collected == [("t0", "baidu")]   # 仅采集了取消前那一个 source
    assert is_manifest_cancelled(ctrl, mid) is True
    assert is_manifest_cancelled(ctrl, mid) is True  # 重复读取不报错


# ---------------------------------------------------------------------------
# Test 11：零真实采集守卫（全测试期间无真实 runtime lock / subprocess）
# ---------------------------------------------------------------------------
def test_11_no_real_collection_guard(tmp_path):
    kw = [f"kw{i}" for i in range(16)]
    coll = _make_coll(tmp_path)
    real_calls = {"n": 0}

    def _guard(*a, **k):
        real_calls["n"] += 1
        return verify_runtime_lock(*a, **k)

    guard = mock.patch.object(mod, "verify_runtime_lock", side_effect=_guard)
    guard.start()
    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=lambda idx, exp: list(exp)[:4])
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
        guard.stop()

    assert real_calls["n"] == 0            # 真实 runtime lock 从未被调用
    assert calls["wait"].called            # 结果等待由合成 fake 接管（无真实子进程）
    assert len(items) > 0
