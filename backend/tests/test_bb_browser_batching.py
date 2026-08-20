"""Phase1b 动态关键词批处理 + per-batch 部分结果：纯单元测试（pytest，不依赖数据库）。

全部通过 mock / synthetic 隔离真实 I/O：
- 不调用真实 bb-browser worker / daemon / CLI；
- 不触碰 production DB、不写 production 数据、不修改 keywords；
- 只验证批处理逻辑、部分结果回收、logical 聚合、状态映射。

覆盖 18 项（Test_00 .. Test_17）。
"""
from __future__ import annotations

import uuid as uuid_mod
from pathlib import Path
from unittest import mock

import pytest

import app.collectors.bb_browser_collector as mod
from app.collectors.bb_browser_collector import (
    BBBrowserCollector,
    DEFAULT_BB_BROWSER_BATCH_SIZE,
    PendingFile,
    split_keywords,
)
from app.collectors.bb_browser_runtime import CollectorError, ERR_TIMEOUT
from app.collectors.service import resolve_bb_browser_run_status


# ---------------------------------------------------------------------------
# 共享 fixture / helper
# ---------------------------------------------------------------------------
def _make_coll(tmp_path: Path, platforms=("xiaohongshu",), **kw):
    """构造一个 test_mode collector（不校验 runtime lock，不触碰真实 DB）。"""
    ctrl = tmp_path / "control"
    exch = tmp_path / "exchange"
    (ctrl / "outgoing").mkdir(parents=True, exist_ok=True)
    (exch / "incoming").mkdir(parents=True, exist_ok=True)
    return BBBrowserCollector(
        platforms=list(platforms),
        control_root=str(ctrl),
        exchange_root=str(exch),
        test_mode=True,
        **kw,
    )


class FakeMutex:
    """记录 acquire / release 次数（验证整个逻辑运行只持有一把锁）。"""

    def __init__(self, *a, **k):
        self.acquired = 0
        self.released = 0

    def acquire(self, mid):
        self.acquired += 1

    def release(self):
        self.released += 1

    def heartbeat(self):
        pass


def _patch_io(coll, tmp_path, *, ready_policy, bad_ids=None, raw_per_file=1, items_per_file=1):
    """统一打桩：manifest 写出捕获、结果等待按 ready_policy 返回、解析/归一化合成。

    ready_policy: callable(call_index, expected) -> list[(task_id, source_key)]
                  返回该批次应「就绪」的子集。
    bad_ids: set[str] 命中则 parse_record_text 返回 adapter error（测试容错）。
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
        # 模拟真实 _wait_for_results 的 partial 行为：把未就绪项记入 _partial_missing
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

    patchers_raw = [
        mock.patch.object(mod, "write_manifest_atomic", fake_write),
        mock.patch.object(coll, "_wait_for_results", side_effect=fake_wait),
        mock.patch.object(mod, "parse_record_text", side_effect=fake_parse),
        mock.patch.object(mod, "normalize_record", side_effect=fake_normalize),
        mock.patch.object(mod, "raw_item_count", side_effect=fake_raw),
    ]
    started = [p.start() for p in patchers_raw]
    calls["wait"] = started[1]
    patchers = patchers_raw
    return captured, calls, patchers


def _stop(patchers):
    # 逆序（LIFO）停止，避免嵌套 patch（如 test_13 在 parse_record_text 上叠加补丁）
    # 因顺序错误而抛异常、导致后续补丁未被清理而泄漏到其它测试模块。
    for p in reversed(patchers):
        try:
            p.stop()
        except Exception:
            pass


def _expected_of(captured):
    out = []
    for _, text in captured:
        out.append(mod.expected_tasks_for_manifest(text))
    return out


# ---------------------------------------------------------------------------
# Test_00：常量
# ---------------------------------------------------------------------------
def test_00_default_batch_size_constant():
    assert DEFAULT_BB_BROWSER_BATCH_SIZE == 8


# ---------------------------------------------------------------------------
# Test_01：split_keywords 纯函数（任意 N，不硬编码 57）
# ---------------------------------------------------------------------------
def test_01_split_keywords_arbitrary_n():
    assert split_keywords([]) == [[]]                       # 0 → [[]]
    assert split_keywords(["a"]) == [["a"]]                 # 1
    kw8 = [f"k{i}" for i in range(8)]
    assert split_keywords(kw8) == [kw8]                    # 8 → 单批
    kw9 = [f"k{i}" for i in range(9)]
    assert len(split_keywords(kw9)) == 2                   # 9 → 2 批 (8,1)
    kw57 = [f"k{i}" for i in range(57)]
    batches = split_keywords(kw57)                         # 57 → 8 批
    assert len(batches) == 8
    assert sum(len(b) for b in batches) == 57
    assert [k for b in batches for k in b] == kw57         # 顺序稳定、未去重
    kw100 = [f"k{i}" for i in range(100)]
    assert len(split_keywords(kw100)) == 13                # 100 → 13 批
    # batch_size <= 0 → 整批
    assert split_keywords(kw9, batch_size=0) == [kw9]
    assert split_keywords(kw9, batch_size=-3) == [kw9]


# ---------------------------------------------------------------------------
# Test_02：快照一次性物化 + 每批独立 manifest（按批关键词切片）
# ---------------------------------------------------------------------------
def test_02_snapshot_once_per_batch_manifest(tmp_path):
    kw = [f"kw_batch_{i}" for i in range(57)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    # 8 批 → 8 个 manifest 写出
    assert len(captured) == 8
    # 快照一次性物化，等于输入（不再回查 DB）
    assert coll._keyword_snapshot == kw
    # 每个 manifest 仅含本批关键词，不含其它批
    for i, (mid, text) in enumerate(captured):
        batch_kw = kw[i * 8:(i + 1) * 8]
        for k in batch_kw:
            assert k in text
        other = kw[(i + 1) * 8:] if i < 7 else []
        for k in other:
            assert k not in text
    assert len(items) == 57  # 全部就绪


# ---------------------------------------------------------------------------
# Test_03：240s 保持 240，per-batch 超时（每批各自调用一次，partial=True）
# ---------------------------------------------------------------------------
def test_03_per_batch_timeout_partial_flag(tmp_path):
    kw = [f"k{i}" for i in range(57)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    assert coll.timeout_seconds == 240  # 240 不变
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    try:
        coll.fetch(keywords=list(kw), batch_size=8)
        # 每批调用一次 _wait_for_results（per-batch），且为 2 参签名
        # （partial 语义由实例标志 self._partial_mode 驱动，不再经 kwarg）。
        wait = calls["wait"]
        assert calls["n"] == 8
        for args, kwargs in wait.call_args_list:
            assert len(args) == 2
            assert coll._partial_mode is True
    finally:
        _stop(patchers)


# ---------------------------------------------------------------------------
# Test_04：部分结果回收（超时不再 all-or-nothing）
# ---------------------------------------------------------------------------
def test_04_partial_recovery_no_raise(tmp_path):
    kw = [f"k{i}" for i in range(57)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    # 每批只回收一半
    def policy(idx, exp):
        k = max(1, len(exp) // 2)
        return exp[:k]
    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=policy)
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert coll.logical_status == "partial_success"
    assert coll.collection_partial is True
    assert coll.collection_failed is False
    expected = _expected_of(captured)
    assert len(items) == sum(max(1, len(exp) // 2) for exp in expected)
    assert len(coll._partial_missing) > 0


# ---------------------------------------------------------------------------
# Test_05：全部就绪 → success
# ---------------------------------------------------------------------------
def test_05_all_ready_success(tmp_path):
    kw = [f"k{i}" for i in range(57)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert coll.logical_status == "success"
    assert coll.collection_partial is False
    assert coll.collection_failed is False
    assert len(items) == 57


# ---------------------------------------------------------------------------
# Test_06：全部未就绪 → failed（返回 []，不抛）
# ---------------------------------------------------------------------------
def test_06_zero_ready_failed(tmp_path):
    kw = [f"k{i}" for i in range(57)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: [],
    )
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert coll.logical_status == "failed"
    assert coll.collection_failed is True
    assert items == []


# ---------------------------------------------------------------------------
# Test_07：混合批次（成功 + 部分）→ partial_success
# ---------------------------------------------------------------------------
def test_07_mixed_batches_partial_success(tmp_path):
    kw = [f"k{i}" for i in range(17)]  # 3 批：8,8,1
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])

    def policy(idx, exp):
        if idx == 0:
            return exp            # 第 1 批全成功
        return exp[: max(1, len(exp) // 2)]  # 其余部分

    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=policy)
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert coll.logical_status == "partial_success"
    # 第 0 批 8 条 + 第 1 批 4 条 + 第 2 批 1 条（len(exp)=1 → //2=0 → max1=1）
    assert len(items) == 8 + 4 + 1


# ---------------------------------------------------------------------------
# Test_08：整个逻辑运行只持有一把互斥锁（batch_id = 逻辑运行标识）
# ---------------------------------------------------------------------------
def test_08_single_mutex_for_logical_run(tmp_path):
    kw = [f"k{i}" for i in range(17)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    fm = FakeMutex()
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    with mock.patch.object(mod, "OutgoingMutex", lambda *a, **k: fm):
        items = coll.fetch(keywords=list(kw), batch_size=8)
    _stop(patchers)
    assert fm.acquired == 1
    assert fm.released == 1
    assert len(items) == 17


# ---------------------------------------------------------------------------
# Test_09：0 关键词 + 搜索型平台 → 跳过（不写空 manifest），但仍前置 recovery
# ---------------------------------------------------------------------------
def test_09_zero_keywords_search_skip(tmp_path):
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    rec = mock.MagicMock(return_value=[])
    with mock.patch.object(coll, "recover_prior_runs", rec):
        items = coll.fetch(keywords=[], batch_size=8)
    _stop(patchers)
    assert items == []
    assert coll.collection_skipped is True
    assert coll.logical_status == "skipped"
    assert len(captured) == 0  # 未写任何 manifest
    assert rec.called           # 仍前置 recovery


# ---------------------------------------------------------------------------
# Test_10：任意 N 不硬编码 57（N=9 → 2 批）
# ---------------------------------------------------------------------------
def test_10_arbitrary_n_nine(tmp_path):
    kw = [f"k{i}" for i in range(9)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert len(captured) == 2
    assert len(items) == 9


# ---------------------------------------------------------------------------
# Test_11：_wait_for_results(partial=True) 单元：回收就绪子集 + 记录 missing
# ---------------------------------------------------------------------------
def test_11_wait_partial_returns_ready_subset(tmp_path):
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"], timeout_seconds=3, poll_interval_seconds=0.3)
    exp = [(f"rule-{i}", "xiaohongshu") for i in range(5)]
    ready = exp[:3]
    # 每次扫描只返回就绪的 3 个（大小恒定 → 稳定）
    pfs = []
    for (tid, src) in ready:
        p = tmp_path / f"ready_{tid}.txt"
        p.write_text("x")
        pfs.append(PendingFile(manifest_id="M", task_id=tid, source_key=src, path=p, file_size=1))

    def fake_scan(mid):
        return list(pfs)

    coll._partial_missing = []
    with mock.patch.object(coll, "_scan_manifest_files", side_effect=fake_scan):
        result = coll._wait_for_results("M", exp, partial=True)
    assert len(result) == 3
    assert sorted(coll._partial_missing) == sorted(exp[3:])


# ---------------------------------------------------------------------------
# Test_12：_wait_for_results(partial=False) 向后兼容仍抛 ERR_TIMEOUT
# ---------------------------------------------------------------------------
def test_12_wait_non_partial_raises(tmp_path):
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"], timeout_seconds=0)

    def fake_scan(mid):
        return []

    coll._partial_missing = []
    with mock.patch.object(coll, "_scan_manifest_files", side_effect=fake_scan):
        with pytest.raises(CollectorError) as exc:
            coll._wait_for_results("M", [("r", "xiaohongshu")], partial=False)
    assert exc.value.code == ERR_TIMEOUT


# ---------------------------------------------------------------------------
# Test_13：就绪文件含 adapter error → 容错跳过并计入 missing（不抛）
# ---------------------------------------------------------------------------
def test_13_adapter_error_tolerated_partial(tmp_path):
    kw = [f"k{i}" for i in range(3)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    # 第一个就绪文件（按解析调用顺序）返回 adapter 401 错误，应被容错跳过
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    parse_calls = {"n": 0}

    def parse_bad(path):
        parse_calls["n"] += 1
        if parse_calls["n"] == 1:
            return {"error": "401 login required", "content": None}
        return {"error": None, "content": {"items": [{"id": 1}]}}

    extra = mock.patch.object(mod, "parse_record_text", side_effect=parse_bad)
    extra.start()
    patchers.append(extra)
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    # 1 坏 + 2 好 → 回收 2 条，logical partial
    assert len(items) == 2
    assert len(coll._partial_missing) == 1
    assert coll.logical_status == "partial_success"


# ---------------------------------------------------------------------------
# Test_14：跨批次口径累加（last_fetched_raw / normalized_count / items）
# ---------------------------------------------------------------------------
def test_14_cross_batch_accumulation(tmp_path):
    kw = [f"k{i}" for i in range(16)]  # 2 批
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    captured, calls, patchers = _patch_io(
        coll, tmp_path,
        ready_policy=lambda idx, exp: exp,
        raw_per_file=5, items_per_file=1,
    )
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    # 每批 8 个就绪文件，raw=5/file → 16*5=80
    assert coll.last_fetched_raw == 80
    assert coll.normalized_count == 16
    assert len(items) == 16


# ---------------------------------------------------------------------------
# Test_15：resolve_bb_browser_run_status 映射（纯函数）
# ---------------------------------------------------------------------------
class _FakeColl:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def test_15_resolve_run_status_mapping():
    assert resolve_bb_browser_run_status(
        _FakeColl(logical_status="skipped", collection_skipped=True), False) == "skipped"
    assert resolve_bb_browser_run_status(
        _FakeColl(logical_status="failed", collection_skipped=False), False) == "failed"
    assert resolve_bb_browser_run_status(
        _FakeColl(logical_status="partial_success", collection_skipped=False), False) == "partial_success"
    assert resolve_bb_browser_run_status(
        _FakeColl(logical_status="success", collection_skipped=False), False) == "success"
    # 采集成功但分析失败 → partial
    assert resolve_bb_browser_run_status(
        _FakeColl(logical_status="success", collection_skipped=False), True) == "partial"
    # 非 BBBrowserCollector（无 logical_status）→ 退化为分析结论
    assert resolve_bb_browser_run_status(object(), False) == "success"
    assert resolve_bb_browser_run_status(object(), True) == "partial"


# ---------------------------------------------------------------------------
# Test_16：fetch 不回查 DB（快照由调用方注入，get_monitoring_keywords 不被调用）
# ---------------------------------------------------------------------------
def test_16_fetch_does_not_query_db(tmp_path):
    import app.services.keyword_service as ks
    kw = [f"k{i}" for i in range(9)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    captured, calls, patchers = _patch_io(
        coll, tmp_path, ready_policy=lambda idx, exp: exp,
    )
    with mock.patch.object(ks, "get_monitoring_keywords", side_effect=AssertionError("DB queried!")):
        items = coll.fetch(keywords=list(kw), batch_size=8)
    _stop(patchers)
    assert len(items) == 9  # 未触发 DB 查询


# ---------------------------------------------------------------------------
# Test_17：#22078 真实场景复现——40/57 就绪，部分结果被回收而非丢弃
# ---------------------------------------------------------------------------
def test_17_run_22078_partial_recovery(tmp_path):
    kw = [f"k{i}" for i in range(57)]
    coll = _make_coll(tmp_path, platforms=["xiaohongshu"])
    # 前 5 批（40 条）全就绪，后 3 批（17 条）全缺失
    def policy(idx, exp):
        return exp if idx < 5 else []

    captured, calls, patchers = _patch_io(coll, tmp_path, ready_policy=policy)
    try:
        items = coll.fetch(keywords=list(kw), batch_size=8)
    finally:
        _stop(patchers)
    assert coll.logical_status == "partial_success"
    assert len(items) == 40           # 40 条就绪结果被回收（而非全部丢弃）
    assert len(coll._partial_missing) == 17
    assert coll.collection_failed is False


def test_z_probe_no_mock_leak():
    """确认本模块所有 patch 均已停止，未污染全局模块属性。"""
    import app.collectors.bb_browser_collector as m
    assert m.raw_item_count.__name__ == "raw_item_count"
    assert m.normalize_record.__name__ == "normalize_record"
    assert m.parse_record_text.__name__ == "parse_record_text"
    assert m.write_manifest_atomic.__name__ == "write_manifest_atomic"
