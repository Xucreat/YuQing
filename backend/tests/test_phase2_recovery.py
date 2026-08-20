"""Phase 2 §四 §五 — 失败/stale 恢复 + 错误分类测试。

运行：
  cd C:/Users/Administrator/Desktop/YQ/backend
  .venv/Scripts/python.exe -m pytest tests/test_phase2_recovery.py --noconftest -q

运行时间：2026-08-19
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.collectors.bb_browser_collector import ALLOWED_PLATFORMS, build_manifest, parse_manifest_rules
from app.collectors.bb_browser_recovery import (
    ManifestRecovery,
    classify_manifest_state,
    S_ACTIVE,
    S_ACK_CONFIRMED,
    S_ACK_PENDING,
    S_PROCESSING,
    S_REJECTED,
    S_RETRYABLE,
    S_STALE,
)
from app.collectors.bb_browser_runtime import (
    classify_adapter_error,
    classify_connectivity,
    ERR_ADAPTER_ERROR,
    ERR_ADAPTER_MISSING,
    ERR_CDP_UNREACHABLE,
    ERR_DAEMON_UNREACHABLE,
    ERR_LOGIN_REQUIRED,
)


def _write_incoming(incoming: Path, manifest_id: str, task_id: str, source_key: str) -> Path:
    incoming.mkdir(parents=True, exist_ok=True)
    p = incoming / f"{source_key}_{task_id}_{manifest_id[:6]}.txt"
    p.write_text(
        f"task_manifest_id={manifest_id}\n"
        f"task_id={task_id}\n"
        f"source_key={source_key}\n"
        f"---BEGIN CONTENT---\n{{}}\n---END CONTENT---\n",
        encoding="utf-8",
    )
    return p


def _write_manifest(outgoing: Path, manifest_id: str, n_keywords: int = 3) -> str:
    outgoing.mkdir(parents=True, exist_ok=True)
    text = build_manifest(manifest_id, [f"kw{i}" for i in range(n_keywords)], ALLOWED_PLATFORMS)
    (outgoing / f"{manifest_id}.txt").write_text(text, encoding="utf-8")
    return text


def _expected_tasks(manifest_id: str, n_keywords: int = 3):
    text = build_manifest(manifest_id, [f"kw{i}" for i in range(n_keywords)], ALLOWED_PLATFORMS)
    out = set()
    for rule_id, sources in parse_manifest_rules(text):
        for s in sources:
            out.add((rule_id, s))
    return out


# ===========================================================================
# §五 错误分类
# ===========================================================================
def test_classify_login_required():
    assert classify_adapter_error({"error": "401 Unauthorized"}) == ERR_LOGIN_REQUIRED
    assert classify_adapter_error({"error": "需要登录"}) == ERR_LOGIN_REQUIRED
    assert classify_adapter_error("please login") == ERR_LOGIN_REQUIRED


def test_classify_adapter_missing():
    assert classify_adapter_error({"error": "adapter not found"}) == ERR_ADAPTER_MISSING
    assert classify_adapter_error({"error": "module not found"}) == ERR_ADAPTER_MISSING


def test_classify_adapter_error_generic():
    assert classify_adapter_error({"error": "timeout in adapter"}) == ERR_ADAPTER_ERROR


def test_classify_connectivity():
    assert classify_connectivity(False, True) == ERR_CDP_UNREACHABLE
    assert classify_connectivity(True, False) == ERR_DAEMON_UNREACHABLE
    assert classify_connectivity(True, True) is None


# ===========================================================================
# §四 状态机（纯函数）
# ===========================================================================
def test_classify_state_transitions():
    e = {("a", "baidu"), ("a", "bilibili"), ("b", "hupu")}
    p_all = set(e)
    p_part = {("a", "baidu")}
    assert classify_manifest_state(True, p_part, e, False, 0) == S_PROCESSING
    assert classify_manifest_state(True, set(), e, False, 0) == S_ACTIVE
    assert classify_manifest_state(False, p_all, e, False, 0) == S_ACK_PENDING
    assert classify_manifest_state(False, p_part, e, False, 0) == S_RETRYABLE
    assert classify_manifest_state(False, p_part, e, False, 3, max_retries=3) == S_REJECTED
    assert classify_manifest_state(False, set(), set(), False, 0) == S_STALE
    assert classify_manifest_state(False, set(), e, True, 0) == S_ACK_CONFIRMED


# ===========================================================================
# §四 恢复：partial 只重试未完成
# ===========================================================================
def test_partial_retry_only_incomplete(tmp_path):
    ctl = tmp_path / "control"
    mid = "M1"
    text = _write_manifest(ctl / "outgoing", mid, n_keywords=3)
    exp = _expected_tasks(mid, n_keywords=3)
    # 完成 8 个（前 2 关键词 3 平台 + hot 2 平台），留下 1 个关键词 3 平台未完成
    incoming = tmp_path / "exchange" / "incoming"
    complete = {(t, s) for (t, s) in exp if ("-rule-0001" in t or "-rule-0002" in t or "-rule-hot" in t)}
    for (t, s) in complete:
        _write_incoming(incoming, mid, t, s)

    rec = ManifestRecovery(ctl, tmp_path / "exchange")
    st = rec.inspect(mid)
    assert st.state == S_RETRYABLE
    assert len(st.incomplete) == 3  # 仅 1 个关键词 × 3 平台
    assert all("-rule-0003" in t for (t, s) in st.incomplete)

    new_count = rec.retry_incomplete(mid, reason="partial_retry")
    assert new_count == 1
    # 重写后的 manifest 只含未完成 rule（rule-0003，3 平台）
    new_text = (ctl / "outgoing" / f"{mid}.txt").read_text(encoding="utf-8")
    new_rules = parse_manifest_rules(new_text)
    assert len(new_rules) == 1
    assert new_rules[0][0].endswith("-rule-0003")
    assert set(new_rules[0][1]) == {"baidu", "bilibili", "youtube"}
    # 已完成任务的 incoming 未被删除
    assert len(list(incoming.glob("*.txt"))) == len(complete)


def test_all_fail_rejected_with_reason(tmp_path):
    ctl = tmp_path / "control"
    mid = "M2"
    _write_manifest(ctl / "outgoing", mid, n_keywords=3)
    # 无任何 incoming（全失败）
    rec = ManifestRecovery(ctl, tmp_path / "exchange", max_retries=1)
    assert rec.inspect(mid).state == S_RETRYABLE
    rec.retry_incomplete(mid, reason="all_fail_retry1")  # retry_count 0 -> 1
    # 再次重试：已达上限 → rejected
    st2 = rec.inspect(mid)
    assert st2.state == S_REJECTED
    rec.reject(mid, "retry_exhausted")
    assert (ctl / "rejected" / f"{mid}.txt").exists()
    reason = json.loads((ctl / "rejected" / f"{mid}.reason.json").read_text(encoding="utf-8"))
    assert reason["code"] == "rejected"
    assert reason["retry_count"] == 1


def test_stale_recovery_never_deletes_incoming(tmp_path):
    ctl = tmp_path / "control"
    mid = "M3"
    _write_manifest(ctl / "outgoing", mid, n_keywords=2)
    incoming = tmp_path / "exchange" / "incoming"
    _write_incoming(incoming, mid, f"{mid}-rule-0001", "baidu")
    before = sorted(p.name for p in incoming.glob("*.txt"))

    rec = ManifestRecovery(ctl, tmp_path / "exchange", max_retries=2)
    rec.recover_stale()  # 会触发 retry/reject，但绝不删 incoming
    after = sorted(p.name for p in incoming.glob("*.txt"))
    assert after == before  # incoming 一个不少


def test_new_manifest_does_not_consume_old_incoming(tmp_path):
    ctl = tmp_path / "control"
    old_mid = "OLD-MANIFEST"
    new_mid = "NEW-MANIFEST"
    _write_manifest(ctl / "outgoing", old_mid, n_keywords=1)
    _write_manifest(ctl / "outgoing", new_mid, n_keywords=1)
    incoming = tmp_path / "exchange" / "incoming"
    # 只为旧 manifest 写入 incoming
    for (t, s) in _expected_tasks(old_mid, n_keywords=1):
        _write_incoming(incoming, old_mid, t, s)

    rec = ManifestRecovery(ctl, tmp_path / "exchange")
    # 新 manifest 看不到旧 manifest 的 incoming
    assert rec._present_tasks(new_mid) == set()
    assert len(rec._present_tasks(old_mid)) > 0
