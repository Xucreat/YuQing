"""Phase 1B 可靠性修复专项测试（pytest --noconftest，不依赖数据库）。

覆盖：
  1. 多关键词：list[PendingFile] 扫描，同平台多文件不互相覆盖，旧 manifest 不混入。
  2. external_id 碰撞：无 URL 的 baidu/hupu 两条不同；重复稳定；空 title+content 跳过；
     绝不生成 *:none / 不含 record_id / 不含 uuid。
  3. ack 半成功：全成功 / 源缺失失败 / 移动中途失败回滚 / 目标已存在且一致=已确认 /
     目标已存在但不一致=失败 / 重复 ack 安全 / 失败后重试成功。
  4. outgoing 并发（Plan A）：空 outgoing 通过；其它任务文件存在→拒绝且不删除他人文件；
     陈旧锁可恢复。
  5. CollectorRun 口径：last_fetched_raw=上游原始（截断前），returned=截断后 len(items)。
     hupu raw=60 max_items=20 → raw=60 returned=20。
"""
from __future__ import annotations

import json
import os
import re
import uuid as uuid_mod
from pathlib import Path
from unittest import mock

import pytest

import app.collectors.bb_browser_collector as mod
from app.collectors.bb_browser_collector import (
    BBBrowserCollector,
    build_manifest,
    expected_tasks_for_manifest,
    normalize_item,
    normalize_record,
    raw_item_count,
    stable_external_id,
)
from app.collectors.bb_browser_runtime import OutgoingLockError, OutgoingMutex


# ---------------------------------------------------------------------------
# 工具：构造一个合法的 incoming 记录文件
# ---------------------------------------------------------------------------
def _write_incoming(incoming_dir: Path, manifest_id: str, task_id: str,
                    source_key: str, content: dict) -> Path:
    incoming_dir.mkdir(parents=True, exist_ok=True)
    p = incoming_dir / f"{source_key}_{task_id}_{manifest_id[:6]}.txt"
    text = (
        f"task_manifest_id={manifest_id}\n"
        f"task_id={task_id}\n"
        f"source_key={source_key}\n"
        f"source_name={source_key}\n"
        f"---BEGIN CONTENT---\n{json.dumps(content, ensure_ascii=False)}\n"
        f"---END CONTENT---\n"
    )
    p.write_text(text, encoding="utf-8")
    return p


def _fake_uuid(hexval: str):
    return type("FakeUUID", (), {"hex": hexval})()


# ===========================================================================
# 1. 多关键词扫描：同平台多文件不互相覆盖，旧 manifest 不混入
# ===========================================================================
def test_multikw_all_files_scanned_no_loss(tmp_path):
    kws = ["北三县", "廊坊", "河北"]
    plats = ["baidu", "bilibili", "youtube", "hupu", "toutiao"]
    MID = "MIDMULTI001"
    text = build_manifest(MID, kws, plats)
    expected = expected_tasks_for_manifest(text)
    # 3 kw × 3 搜索平台 + 1 热榜 × 2 = 11 个任务
    assert len(expected) == 11

    incoming = tmp_path / "incoming"
    # 为每个 (task_id, source_key) 生成一个 incoming 文件
    seen = set()
    for task_id, src in expected:
        # 每个文件至少 1 条，确保归一化后有内容
        content = _sample_content(src, 1)
        _write_incoming(incoming, MID, task_id, src, content)
        seen.add((task_id, src))
    assert len(seen) == 11

    coll = BBBrowserCollector(
        platforms=plats, control_root=str(tmp_path), exchange_root=str(tmp_path)
    )
    found = coll._scan_manifest_files(MID)
    got = {(pf.task_id, pf.source_key) for pf in found}
    assert got == seen  # 全部命中，无丢失
    assert len(found) == 11


def test_multikw_same_platform_multi_file_not_overwritten(tmp_path):
    # baidu 在 3 个关键词下会生成 3 个 task_id 文件；list API 必须全部保留
    MID = "MIDSAMEPLAT"
    kws = ["kwA", "kwB", "kwC"]
    plats = ["baidu"]
    text = build_manifest(MID, kws, plats)
    expected = expected_tasks_for_manifest(text)
    assert len(expected) == 3  # 3 个 baidu 文件

    incoming = tmp_path / "incoming"
    for task_id, src in expected:
        _write_incoming(incoming, MID, task_id, src, _sample_content("baidu", 1))

    coll = BBBrowserCollector(
        platforms=plats, control_root=str(tmp_path), exchange_root=str(tmp_path)
    )
    found = coll._scan_manifest_files(MID)
    baidu_files = [pf for pf in found if pf.source_key == "baidu"]
    assert len(baidu_files) == 3  # 没有按 source_key 单一覆盖


def test_multikw_old_manifest_not_mixed(tmp_path):
    incoming = tmp_path / "incoming"
    # 旧 manifest 的残留文件
    _write_incoming(incoming, "OLD-MANIFEST", "OLD-MANIFEST-rule-0001", "baidu",
                    _sample_content("baidu", 1))
    # 新 manifest 的 2 个文件（2 关键词 × baidu）
    MID = "NEW-MANIFEST"
    text = build_manifest(MID, ["x", "y"], ["baidu"])
    expected = expected_tasks_for_manifest(text)
    for task_id, src in expected:
        _write_incoming(incoming, MID, task_id, src, _sample_content("baidu", 1))

    coll = BBBrowserCollector(
        platforms=["baidu"], control_root=str(tmp_path), exchange_root=str(tmp_path)
    )
    found = coll._scan_manifest_files(MID)
    assert all(pf.manifest_id == MID for pf in found)
    assert len(found) == 2
    assert all("OLD-MANIFEST" not in pf.path.name for pf in found)


def _sample_content(platform: str, n: int) -> dict:
    if platform == "baidu":
        return {"result": {"count": n, "results": [
            {"title": f"b{i}", "url": f"http://b/{i}", "snippet": f"s{i}"} for i in range(n)
        ]}}
    if platform == "hupu":
        return {"result": {"items": [
            {"tid": str(i), "title": f"h{i}"} for i in range(n)
        ]}}
    if platform == "toutiao":
        return {"result": {"items": [
            {"rank": str(i), "title": f"t{i}",
             "url": f"https://www.toutiao.com/trending/{i}/"} for i in range(n)
        ]}}
    if platform == "bilibili":
        return {"result": {"videos": [
            {"bvid": f"BV{i}", "title": f"v{i}", "author": "up",
             "url": f"https://www.bilibili.com/video/BV{i}"} for i in range(n)
        ]}}
    if platform == "youtube":
        return {"result": {"videos": [
            {"videoId": f"v{i}", "title": f"y{i}", "channel": "c",
             "url": f"https://www.youtube.com/watch?v=v{i}"} for i in range(n)
        ]}}
    return {"result": {"items": [{"title": "x"} for _ in range(n)]}}


# ===========================================================================
# 2. external_id 碰撞：禁止 *:none，无 URL 两条不同，重复稳定
# ===========================================================================
def test_external_id_no_url_baidu_distinct():
    a = stable_external_id("baidu", {"title": "标题甲", "snippet": "摘要甲"}, None)
    b = stable_external_id("baidu", {"title": "标题乙", "snippet": "摘要乙"}, None)
    assert a.startswith("baidu:")
    assert b.startswith("baidu:")
    assert a != b  # 两条无 URL 不同内容 → 不同 id
    assert "none" not in a and "none" not in b


def test_external_id_no_tid_hupu_distinct():
    a = stable_external_id("hupu", {"title": "帖甲"}, None)
    b = stable_external_id("hupu", {"title": "帖乙"}, None)
    assert a.startswith("hupu:")
    assert b.startswith("hupu:")
    assert a != b
    assert "none" not in a


def test_external_id_repeat_stable():
    item = {"title": "稳定标题", "snippet": "稳定摘要"}
    a = stable_external_id("baidu", item, None)
    b = stable_external_id("baidu", item, None)
    assert a == b


def test_external_id_empty_title_content_skipped():
    # title+content 全空 → 返回 None（绝不生成 *:none）
    assert stable_external_id("baidu", {}, None) is None
    assert stable_external_id("baidu", {"title": "", "snippet": ""}, None) is None
    assert stable_external_id("hupu", {"title": ""}, None) is None


def test_external_id_no_record_id_no_uuid():
    eid = stable_external_id("baidu", {"title": "X", "snippet": "Y",
                                       "url": "http://x/1"}, None)
    assert "record_id" not in eid
    # uuid4 形如 8-4-4-4-12 带连字符；我们的 id 不应包含该模式
    assert re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", eid) is None
    # normalize_item 也不应产出 *:none
    norm = normalize_item("youtube", {"title": "频道视频", "description": "d",
                                      "videoId": "abc"})
    assert norm["external_id"] == "youtube:abc"


# ===========================================================================
# 3. ack 半成功：幂等、可恢复、回滚
# ===========================================================================
def _setup_ack(tmp_path, files: dict) -> BBBrowserCollector:
    exchange = tmp_path
    incoming = exchange / "incoming"
    incoming.mkdir()
    paths = []
    for name, content in files.items():
        p = incoming / name
        p.write_text(content, encoding="utf-8")
        paths.append(p)
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(exchange))
    coll._pending_files = paths
    return coll


def test_ack_all_success(tmp_path):
    coll = _setup_ack(tmp_path, {"baidu_a.txt": "x", "hupu_b.txt": "y"})
    ok = coll.ack_pending_export()
    assert ok is True
    assert (tmp_path / "processed" / "baidu_a.txt").exists()
    assert (tmp_path / "processed" / "hupu_b.txt").exists()
    assert not (tmp_path / "incoming" / "baidu_a.txt").exists()
    assert coll._pending_files == []


def test_ack_source_missing_returns_false(tmp_path):
    # f1 存在，f2 不存在 → 计划阶段即发现缺失，整体不移动任何文件
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    f1 = incoming / "baidu_a.txt"
    f1.write_text("x", encoding="utf-8")
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(tmp_path))
    coll._pending_files = [f1, incoming / "baidu_missing.txt"]
    ok = coll.ack_pending_export()
    assert ok is False
    assert f1.exists()  # f1 未被移动
    assert coll._pending_files  # 未清空


def test_ack_move_failure_rolls_back(tmp_path):
    coll = _setup_ack(tmp_path, {"baidu_a.txt": "x", "hupu_b.txt": "y"})
    calls = {"n": 0}
    orig = mod.os.replace

    def fake_replace(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:  # 第二个移动失败
            raise OSError("simulated failure")
        return orig(src, dst)

    with mock.patch.object(mod.os, "replace", side_effect=fake_replace):
        ok = coll.ack_pending_export()
    assert ok is False
    # f1 已移动后被回滚，仍在 incoming；f2 仍在 incoming
    assert (tmp_path / "incoming" / "baidu_a.txt").exists()
    assert (tmp_path / "incoming" / "hupu_b.txt").exists()
    assert coll._pending_files  # 未清空


def test_ack_target_exists_content_equal(tmp_path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()
    f1 = incoming / "baidu_a.txt"
    f1.write_text("SAME", encoding="utf-8")
    (processed / "baidu_a.txt").write_text("SAME", encoding="utf-8")  # 内容一致
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(tmp_path))
    coll._pending_files = [f1]
    ok = coll.ack_pending_export()
    assert ok is True  # 视为已确认
    assert f1.exists()  # 不重复移动
    assert coll._pending_files == []


def test_ack_target_exists_content_differ(tmp_path):
    incoming = tmp_path / "incoming"
    processed = tmp_path / "processed"
    incoming.mkdir()
    processed.mkdir()
    f1 = incoming / "baidu_a.txt"
    f1.write_text("SRC", encoding="utf-8")
    (processed / "baidu_a.txt").write_text("DST-OTHER", encoding="utf-8")
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(tmp_path))
    coll._pending_files = [f1]
    ok = coll.ack_pending_export()
    assert ok is False  # 内容不一致，拒绝覆盖
    assert f1.exists()


def test_ack_repeat_after_success(tmp_path):
    coll = _setup_ack(tmp_path, {"baidu_a.txt": "x"})
    assert coll.ack_pending_export() is True
    assert coll._pending_files == []
    # 重复调用：pending 空 → 直接 True（幂等）
    assert coll.ack_pending_export() is True


def test_ack_retry_after_failure(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    f1 = incoming / "baidu_a.txt"
    f1.write_text("x", encoding="utf-8")
    f2_missing = incoming / "baidu_b.txt"
    coll = BBBrowserCollector(control_root=str(tmp_path), exchange_root=str(tmp_path))
    coll._pending_files = [f1, f2_missing]
    assert coll.ack_pending_export() is False  # 首次失败（f2 缺失）
    assert f1.exists()
    # 修复：补上 f2
    f2_missing.write_text("y", encoding="utf-8")
    assert coll.ack_pending_export() is True  # 重试成功
    assert (tmp_path / "processed" / "baidu_a.txt").exists()
    assert (tmp_path / "processed" / "baidu_b.txt").exists()


# ===========================================================================
# 4. outgoing 并发（§三：跨进程原子互斥，替代旧 Plan A TOCTOU）
# ===========================================================================
def test_outgoing_empty_proceeds(tmp_path):
    # 空 outgoing → 互斥锁可正常获取 / 释放，不拒绝
    mutex = OutgoingMutex(tmp_path / "outgoing", stale_dir=tmp_path / "stale")
    mutex.acquire("RUN1")
    assert mutex.lock_info is not None
    assert mutex.lock_info.owner_pid == os.getpid()
    assert mutex.lock_info.manifest_id == "RUN1"
    assert (tmp_path / "outgoing" / ".bb_outgoing.lock").exists()
    mutex.release()
    assert not (tmp_path / "outgoing" / ".bb_outgoing.lock").exists()


def test_outgoing_other_present_rejects(tmp_path):
    # 另一活跃进程持有锁 → fetch 拒绝（worker_busy），且不删除他人的 manifest
    outgoing = tmp_path / "outgoing"
    outgoing.mkdir()
    other_manifest = outgoing / "other-task-xyz.txt"
    other_manifest.write_text("stale", encoding="utf-8")
    m1 = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m1.acquire("other-task-xyz")  # 活跃锁（owner=当前进程，未超 TTL）
    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path),
                              exchange_root=str(tmp_path), test_mode=True)
    with mock.patch.object(uuid_mod, "uuid4", return_value=_fake_uuid("RUN001")):
        with pytest.raises(OutgoingLockError) as exc:
            coll.fetch()
    assert exc.value.code == "worker_busy"
    # 他人的 manifest 未被删除
    assert other_manifest.exists()
    m1.release()


def test_outgoing_stale_lock_recoverable(tmp_path):
    # 陈旧锁（owner 已死 + last_seen 超 TTL）→ 回收并迁移孤儿 manifest，不拒绝
    outgoing = tmp_path / "outgoing"
    outgoing.mkdir()
    stale_manifest = outgoing / "stale-lock.txt"
    stale_manifest.write_text("old", encoding="utf-8")
    (outgoing / ".bb_outgoing.lock").write_text(json.dumps({
        "owner_pid": 99999999, "manifest_id": "stale-lock",
        "created_at": 0.0, "last_seen": 0.0, "hostname": "",
    }), encoding="utf-8")

    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path),
                              exchange_root=str(tmp_path), test_mode=True)
    with mock.patch.object(uuid_mod, "uuid4", return_value=_fake_uuid("RUN002")):
        with mock.patch.object(coll, "_wait_for_results", return_value=[]):
            try:
                coll.fetch()
            except RuntimeError as e:
                # 不再是 outgoing 并发错误；应是「0 条有效条目」类错误
                assert "outgoing" not in str(e)
    # 陈旧 manifest 被迁移到 stale/（留证，不删除）
    assert (tmp_path / "stale" / "stale-lock.txt").exists()
    assert (tmp_path / "stale" / "stale-lock.stale.json").exists()
    assert not stale_manifest.exists()  # 已从 outgoing 迁走


# ===========================================================================
# 5. CollectorRun 口径：raw（截断前）vs returned（截断后）
# ===========================================================================
def test_stat_caliber_raw_vs_returned(tmp_path):
    MID = "MIDSTAT001"
    incoming = tmp_path / "incoming"
    # hupu 上游原始 60 条，max_items_per_platform=20
    content = {"result": {"count": 60, "items": [
        {"tid": str(i), "title": f"t{i}"} for i in range(60)
    ]}}
    _write_incoming(incoming, MID, f"{MID}-rule-hot-0001", "hupu", content)

    coll = BBBrowserCollector(platforms=["hupu"], control_root=str(tmp_path),
                              exchange_root=str(tmp_path), max_items_per_platform=20,
                              timeout_seconds=1, test_mode=True)
    # 绕过 worker：直接扫描并归一化
    with mock.patch.object(uuid_mod, "uuid4", return_value=_fake_uuid(MID)):
        with mock.patch.object(coll, "_wait_for_results",
                               side_effect=lambda mid, exp: coll._scan_manifest_files(mid)):
            items = coll.fetch()

    # 口径断言
    assert raw_item_count("hupu", content) == 60            # 上游原始
    assert coll.last_fetched_raw == 60                       # 截断前
    assert coll.normalized_count == 20                       # 归一化后（被 max_items 截断）
    assert len(items) == 20                                  # fetch 返回（截断后）
    assert coll.last_not_exported_returned == 20
    assert "hupu" not in {p.path.name for p in []} or True   # 占位


def test_normalize_record_truncation():
    content = {"result": {"items": [{"tid": str(i), "title": f"t{i}"} for i in range(50)]}}
    out = normalize_record("hupu", content, max_items=10)
    assert len(out) == 10
    # 不传 max_items → 全量
    out2 = normalize_record("hupu", content)
    assert len(out2) == 50
