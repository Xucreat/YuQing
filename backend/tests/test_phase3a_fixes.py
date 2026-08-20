"""Phase 3A 缺陷修复专项测试（§二/§三/§四/§六/§七）。

覆盖点：
- §二 retry manifest 四字段完整 + 真实 worker parse_rules() 可解析；
- §三 ManifestRecovery 已接入真实运行流程（fetch 前置调用、rejected、不删 incoming、结构化日志）；
- §四 OutgoingMutex owner_token 所有权（回收后旧 owner 不得删新锁、heartbeat 原子替换）；
- §六 runtime lock 生产 fail-closed / 测试显式 test mode；
- §七 ack_confirmed 精确确认（processed / ack_pending 一致性、重启可恢复、不重复 retry）。

全部为纯文件系统单元测试，不触碰生产数据库、不启动 worker/Chrome/CDP。
运行：.venv/Scripts/python.exe -m pytest tests/test_phase3a_fixes.py -q --noconftest
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import threading
import time
import uuid as uuid_mod
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collectors.bb_browser_collector import (  # noqa: E402
    BBBrowserCollector,
    build_manifest,
    parse_manifest_rules,
)
from app.collectors.bb_browser_recovery import (  # noqa: E402
    ManifestRecovery,
    S_ACK_CONFIRMED,
    S_REJECTED,
    S_RETRYABLE,
    _extract_rule_block,
    _filter_manifest_rules,
    _validate_retry_manifest,
)
from app.collectors.bb_browser_runtime import (  # noqa: E402
    ERR_RUNTIME_DRIFT,
    CollectorError,
    LockInfo,
    OutgoingMutex,
)

# 灰度五平台（严格排除 weibo / m_weibo / xiaohongshu / xhs / zhihu）
GRAY_PLATFORMS = ["baidu", "bilibili", "youtube", "hupu", "toutiao"]

WORKER_MAIN = Path(
    r"C:\Users\Administrator\Desktop\bb-browser 采集器\collector_exchange_runtime"
    r"\collector_exchange\__main__.py"
)


# ---------------------------------------------------------------------------
# 公共夹具
# ---------------------------------------------------------------------------
def _load_real_worker():
    """按文件路径加载真实 worker 模块（只读，不执行 main()）。

    模块名故意不叫 __main__，确保 ``if __name__ == '__main__'`` 分支不触发。
    """
    if not WORKER_MAIN.exists():
        pytest.skip(f"真实 worker 入口不存在：{WORKER_MAIN}")
    spec = importlib.util.spec_from_file_location("bb_worker_under_test", WORKER_MAIN)
    if spec is None or spec.loader is None:
        pytest.skip("无法为真实 worker 构造 import spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_partial(tmp_path: Path, *, keywords=("水污染", "违法排污"), platforms=None):
    """构造 control/exchange 目录 + 一个 partial manifest（部分 incoming 已到）。

    返回 (rec, manifest_id, manifest_text, control, exchange)。
    """
    platforms = list(platforms or GRAY_PLATFORMS)
    control = tmp_path / "control"
    exchange = tmp_path / "exchange"
    outgoing = control / "outgoing"
    incoming = exchange / "incoming"
    outgoing.mkdir(parents=True, exist_ok=True)
    incoming.mkdir(parents=True, exist_ok=True)

    mid = uuid_mod.uuid4().hex
    text = build_manifest(mid, list(keywords), platforms)
    (outgoing / f"{mid}.txt").write_text(text, encoding="utf-8")

    rec = ManifestRecovery(control, exchange, max_retries=3)
    return rec, mid, text, control, exchange


def _write_incoming(exchange: Path, manifest_id: str, task_id: str, source_key: str) -> Path:
    incoming = exchange / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    p = incoming / f"{source_key}_{task_id}_{manifest_id[:6]}.txt"
    p.write_text(
        "\n".join([
            f"task_manifest_id={manifest_id}",
            f"task_id={task_id}",
            f"source_key={source_key}",
            "status=ok",
            "items=0",
        ]),
        encoding="utf-8",
    )
    return p


def _write_processed(exchange: Path, manifest_id: str, task_id: str, source_key: str) -> Path:
    processed = exchange / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    p = processed / f"{source_key}_{task_id}_{manifest_id[:6]}.txt"
    p.write_text(
        "\n".join([
            f"task_manifest_id={manifest_id}",
            f"task_id={task_id}",
            f"source_key={source_key}",
            "status=ok",
            "items=0",
        ]),
        encoding="utf-8",
    )
    return p


# ===========================================================================
# §二 retry manifest 缺陷修复
# ===========================================================================
def test_retry_manifest_每条规则含四字段(tmp_path):
    """重写后的每条 rule 必须含 rule_id / rule_action / match_terms / sources。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    assert len(rules) >= 2

    # 让第一条 rule 的全部 source 完成，其余保持未完成 → partial
    done_rule, done_sources = rules[0]
    for src in done_sources:
        _write_incoming(exchange, mid, done_rule, src)

    st = rec.inspect(mid)
    assert st.state == S_RETRYABLE, f"应为可重试 partial，实际 {st.state}"

    assert rec.retry_incomplete(mid, reason="unit_partial") == 1

    retry_text = (control / "outgoing" / f"{mid}.txt").read_text(encoding="utf-8")
    retry_rules = parse_manifest_rules(retry_text)
    assert retry_rules, "重试 manifest 必须至少含一条 rule"
    for rule_id, sources in retry_rules:
        block = _extract_rule_block(retry_text, rule_id)
        for field in ("rule_id", "rule_action", "match_terms", "sources"):
            assert block.get(field, "").strip(), f"rule {rule_id} 缺少字段 {field}"
        assert block["rule_action"] == "collect"
        assert sources, f"rule {rule_id} sources 为空"


def test_retry_manifest_可被真实worker解析(tmp_path):
    """用真实 worker 的 parse_rules() 解析重试 manifest（§二-3/§二-4）。"""
    worker = _load_real_worker()
    assert hasattr(worker, "parse_rules"), "真实 worker 缺少 parse_rules"

    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    done_rule, done_sources = rules[0]
    for src in done_sources:
        _write_incoming(exchange, mid, done_rule, src)

    rec.retry_incomplete(mid, reason="worker_parse_check")
    retry_path = control / "outgoing" / f"{mid}.txt"

    # 真实 worker 解析：rule_id 与 match_terms 必须同时存在，否则该 rule 被丢弃
    parsed = worker.parse_rules(retry_path, ["baidu"])
    assert parsed, "真实 worker 未能解析出任何 rule（说明重写 manifest 无效）"
    for item in parsed:
        assert item.get("rule_id"), "worker 解析结果缺少 rule_id"
        assert item.get("match_terms"), "worker 解析结果缺少 match_terms"
        assert item.get("sources"), "worker 解析结果缺少 sources"
        assert isinstance(item["sources"], list)


def test_retry_manifest_不含已完成任务(tmp_path):
    """已完成的 rule 不得重复进入重试 manifest（§二-5）。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    done_rule, done_sources = rules[0]
    for src in done_sources:
        _write_incoming(exchange, mid, done_rule, src)

    rec.retry_incomplete(mid, reason="exclude_done")
    retry_text = (control / "outgoing" / f"{mid}.txt").read_text(encoding="utf-8")
    retry_ids = {rid for rid, _ in parse_manifest_rules(retry_text)}
    assert done_rule not in retry_ids, "已完成 rule 不得出现在重试 manifest"
    assert retry_ids, "重试 manifest 不应为空"

    # 真实 worker 也看不到已完成 rule
    worker = _load_real_worker()
    parsed = worker.parse_rules(control / "outgoing" / f"{mid}.txt", ["baidu"])
    assert done_rule not in {i["rule_id"] for i in parsed}


def test_retry_manifest_部分source完成时保留该rule(tmp_path):
    """同一 rule 只有部分 source 完成 → 该 rule 仍需重试（只重试未完成 source 所属 rule）。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    rule_id, sources = rules[0]
    assert len(sources) >= 2, "该用例需要一条 rule 覆盖多个 source"
    _write_incoming(exchange, mid, rule_id, sources[0])  # 只完成一个 source

    st = rec.inspect(mid)
    assert (rule_id, sources[0]) in st.present
    assert (rule_id, sources[1]) in st.incomplete

    rec.retry_incomplete(mid, reason="partial_source")
    retry_text = (control / "outgoing" / f"{mid}.txt").read_text(encoding="utf-8")
    assert rule_id in {rid for rid, _ in parse_manifest_rules(retry_text)}


def test_validate_retry_manifest_拒绝只写关键词字符串():
    """回归防御：只写关键词字符串（缺 match_terms= 键）必须被校验拒绝。"""
    bad = "\n".join([
        "RULE_VERSION=1",
        "rule_manifest_id=deadbeef",
        "",
        "---BEGIN RULE---",
        "rule_id=deadbeef-rule-0001",
        "rule_action=collect",
        "水污染",                      # ← 旧缺陷：裸关键词，没有 match_terms=
        "sources=baidu,bilibili",
        "---END RULE---",
    ])
    with pytest.raises(ValueError) as ei:
        _validate_retry_manifest(bad, {"deadbeef-rule-0001"})
    assert "match_terms" in str(ei.value)


def test_filter_manifest_rules_保留原始match_terms():
    """重写时必须沿用原 rule 的 match_terms，而非一律占位。"""
    mid = "abc123"
    text = build_manifest(mid, ["水污染"], ["baidu"])
    keep = {rid for rid, _ in parse_manifest_rules(text)}
    out = _filter_manifest_rules(text, keep, mid)
    block = _extract_rule_block(out, sorted(keep)[0])
    assert block["match_terms"] == "水污染"


# ===========================================================================
# §三 ManifestRecovery 接入真实运行流程
# ===========================================================================
def test_fetch_前置调用recover_prior_runs(tmp_path, monkeypatch):
    """fetch() 在创建新任务前必须调用 recover_prior_runs（禁止代码存在但不调用）。"""
    control = tmp_path / "control"
    exchange = tmp_path / "exchange"
    (control / "outgoing").mkdir(parents=True, exist_ok=True)
    coll = BBBrowserCollector(
        platforms=["hupu"],
        control_root=str(control),
        exchange_root=str(exchange),
        test_mode=True,
        timeout_seconds=1,
    )
    calls: list = []
    monkeypatch.setattr(
        coll, "recover_prior_runs",
        lambda **kw: calls.append(kw) or [],
    )
    with pytest.raises(Exception):
        # 无 worker 消费 → 超时失败；此处只验证 recovery 已被前置调用
        coll.fetch(keywords=["水污染"])
    assert calls, "fetch() 未调用 recover_prior_runs（recovery 未接入真实流程）"
    assert calls[0].get("reason") == "pre_create_recovery"


def test_recover_prior_runs_重试残留partial(tmp_path):
    """遗留 partial manifest → 新任务前被 retry_incomplete。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    done_rule, done_sources = rules[0]
    for src in done_sources:
        _write_incoming(exchange, mid, done_rule, src)

    coll = BBBrowserCollector(
        platforms=["hupu"], control_root=str(control),
        exchange_root=str(exchange), test_mode=True,
    )
    acted = coll.recover_prior_runs(reason="unit_pre_create")
    assert (mid, "retry_incomplete") in acted
    assert rec._retry_count(mid) == 1


def test_recover_prior_runs_超上限移入rejected并写reason(tmp_path):
    """retry 超上限 → 移入 rejected/ 并写 reason（§三-4）。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    done_rule, done_sources = rules[0]
    for src in done_sources:
        _write_incoming(exchange, mid, done_rule, src)
    rec._set_retry_count(mid, 3, "exhausted_by_unit")  # 已达 max_retries=3

    coll = BBBrowserCollector(
        platforms=["hupu"], control_root=str(control),
        exchange_root=str(exchange), test_mode=True,
    )
    acted = coll.recover_prior_runs(reason="unit_exhausted")
    assert (mid, "rejected") in acted

    reason_file = control / "rejected" / f"{mid}.reason.json"
    assert reason_file.exists(), "rejected reason 文件必须写入"
    payload = json.loads(reason_file.read_text(encoding="utf-8"))
    assert payload["manifest_id"] == mid
    assert payload["reason"]
    assert (control / "rejected" / f"{mid}.txt").exists(), "manifest 应被移入 rejected（不得删除）"
    assert not (control / "outgoing" / f"{mid}.txt").exists()


def test_recovery_绝不删除incoming(tmp_path):
    """失败任务产生的 incoming 绝不能被恢复流程删除（§三-5）。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    done_rule, done_sources = rules[0]
    kept = [_write_incoming(exchange, mid, done_rule, src) for src in done_sources]

    rec._set_retry_count(mid, 3, "force_reject")
    coll = BBBrowserCollector(
        platforms=["hupu"], control_root=str(control),
        exchange_root=str(exchange), test_mode=True,
    )
    coll.recover_prior_runs(reason="unit_no_delete")
    for p in kept:
        assert p.exists(), f"incoming 被误删：{p}"


def test_recovery_结构化日志(tmp_path):
    """recovery 必须产出结构化 jsonl 日志（§三-7）。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rules = parse_manifest_rules(text)
    done_rule, done_sources = rules[0]
    for src in done_sources:
        _write_incoming(exchange, mid, done_rule, src)

    rec.retry_incomplete(mid, reason="log_check")
    log_path = control / "recovery" / "recovery_log.jsonl"
    assert log_path.exists(), "缺少 recovery_log.jsonl"
    lines = [json.loads(x) for x in log_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lines
    entry = lines[-1]
    for key in ("at", "manifest_id", "action", "previous_state", "incomplete", "retry_count", "reason"):
        assert key in entry, f"recovery 日志缺少字段 {key}"
    assert entry["action"] == "retry_incomplete"
    assert entry["retry_count"] == 1


def test_新任务不误消费旧manifest的incoming(tmp_path):
    """按 task_manifest_id 精确匹配：旧 manifest 的 incoming 不得算作新任务进度（§三-6）。"""
    rec_old, old_mid, old_text, control, exchange = _mk_partial(tmp_path)
    old_rules = parse_manifest_rules(old_text)
    for src in old_rules[0][1]:
        _write_incoming(exchange, old_mid, old_rules[0][0], src)

    new_mid = uuid_mod.uuid4().hex
    new_text = build_manifest(new_mid, ["水污染"], GRAY_PLATFORMS)
    (control / "outgoing" / f"{new_mid}.txt").write_text(new_text, encoding="utf-8")

    rec_new = ManifestRecovery(control, exchange, max_retries=3)
    st_new = rec_new.inspect(new_mid)
    assert st_new.present == set(), "新 manifest 不得把旧 manifest 的 incoming 算作已完成"
    assert st_new.expected, "新 manifest 期望任务集合不应为空"


def test_recover_prior_runs_跳过当前manifest(tmp_path):
    """recover_prior_runs 绝不处理当前新任务自身的 manifest。"""
    control = tmp_path / "control"
    exchange = tmp_path / "exchange"
    (control / "outgoing").mkdir(parents=True, exist_ok=True)
    cur = uuid_mod.uuid4().hex
    (control / "outgoing" / f"{cur}.txt").write_text(
        build_manifest(cur, ["水污染"], GRAY_PLATFORMS), encoding="utf-8"
    )
    coll = BBBrowserCollector(
        platforms=["hupu"], control_root=str(control),
        exchange_root=str(exchange), test_mode=True,
    )
    coll._current_manifest_id = cur
    acted = coll.recover_prior_runs(reason="skip_self")
    assert all(mid != cur for mid, _ in acted), "不得对当前 manifest 自我重试"


def test_recover_prior_runs_同时扫描stale目录(tmp_path):
    """§三-1：新任务前需检查 outgoing + stale。"""
    control = tmp_path / "control"
    exchange = tmp_path / "exchange"
    stale = control / "stale"
    stale.mkdir(parents=True, exist_ok=True)
    (control / "outgoing").mkdir(parents=True, exist_ok=True)
    (exchange / "incoming").mkdir(parents=True, exist_ok=True)

    mid = uuid_mod.uuid4().hex
    text = build_manifest(mid, ["水污染", "违法排污"], GRAY_PLATFORMS)
    (stale / f"{mid}.txt").write_text(text, encoding="utf-8")
    rules = parse_manifest_rules(text)
    for src in rules[0][1]:
        _write_incoming(exchange, mid, rules[0][0], src)

    coll = BBBrowserCollector(
        platforms=["hupu"], control_root=str(control),
        exchange_root=str(exchange), test_mode=True,
    )
    acted = coll.recover_prior_runs(reason="scan_stale")
    assert (mid, "retry_incomplete") in acted, "stale 目录中的 partial manifest 未被恢复"


# ===========================================================================
# §四 OutgoingMutex 所有权
# ===========================================================================
def test_lock_含唯一owner_token(tmp_path):
    outgoing = tmp_path / "outgoing"
    m1 = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m1.acquire("m-aaa")
    info1 = LockInfo.from_json((outgoing / ".bb_outgoing.lock").read_text(encoding="utf-8"))
    assert info1.owner_token, "锁文件必须含 owner_token"
    m1.release()

    m2 = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m2.acquire("m-bbb")
    info2 = LockInfo.from_json((outgoing / ".bb_outgoing.lock").read_text(encoding="utf-8"))
    assert info2.owner_token and info2.owner_token != info1.owner_token, "owner_token 必须唯一"
    m2.release()


def test_旧owner被回收后release不得删除新锁(tmp_path):
    """§四-2/§四-3：锁已被新进程接管，旧 owner 的 release 绝不能删掉新锁。"""
    outgoing = tmp_path / "outgoing"
    lock_path = outgoing / ".bb_outgoing.lock"
    old = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    old.acquire("m-old")
    old_info = LockInfo.from_json(lock_path.read_text(encoding="utf-8"))

    # 模拟锁被回收 + 新进程接管（owner_token 与 manifest_id 均已变化）
    new_info = LockInfo(
        owner_pid=os.getpid(),
        manifest_id="m-new",
        created_at=time.time(),
        last_seen=time.time(),
        hostname=old_info.hostname,
        owner_token=uuid_mod.uuid4().hex,
    )
    lock_path.write_text(new_info.to_json(), encoding="utf-8")

    old.release()  # 旧 owner 释放
    assert lock_path.exists(), "旧 owner 删除了新 owner 的锁（所有权校验失效）"
    cur = LockInfo.from_json(lock_path.read_text(encoding="utf-8"))
    assert cur.owner_token == new_info.owner_token
    assert cur.manifest_id == "m-new"


def test_release仅在owner完全匹配时删除(tmp_path):
    outgoing = tmp_path / "outgoing"
    lock_path = outgoing / ".bb_outgoing.lock"
    m = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m.acquire("m-own")
    assert lock_path.exists()
    m.release()
    assert not lock_path.exists(), "owner 完全匹配时应正常删除自己的锁"


def test_release_manifest_id不匹配时不删除(tmp_path):
    """同 pid、同 token，但 manifest_id 被换掉 → 视为非本次持有，不得删除。"""
    outgoing = tmp_path / "outgoing"
    lock_path = outgoing / ".bb_outgoing.lock"
    m = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m.acquire("m-x")
    info = LockInfo.from_json(lock_path.read_text(encoding="utf-8"))
    info.manifest_id = "m-y"
    lock_path.write_text(info.to_json(), encoding="utf-8")
    m.release()
    assert lock_path.exists(), "manifest_id 不匹配时不得删除锁"


def test_heartbeat与acquire并发锁文件不损坏(tmp_path):
    """§四-4/§四-5：heartbeat 用临时文件 + 原子替换，并发下锁文件始终可解析。"""
    outgoing = tmp_path / "outgoing"
    lock_path = outgoing / ".bb_outgoing.lock"
    m = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m.acquire("m-hb")

    errors: list = []
    stop = threading.Event()

    def _beat():
        while not stop.is_set():
            try:
                m.heartbeat()
            except Exception as exc:  # pragma: no cover
                errors.append(("heartbeat", repr(exc)))

    reads_ok = {"n": 0}

    def _read():
        while not stop.is_set():
            try:
                raw = lock_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                # 原子替换的瞬间目标可能短暂不可见
                continue
            except PermissionError:
                # Windows os.replace 期间的 sharing violation：属于原子替换的正常表现，
                # 关键在于「一旦读到内容，内容必须是完整可解析的」——绝不能读到半写文本。
                continue
            except Exception as exc:
                errors.append(("read", repr(exc)))
                continue
            if not raw.strip():
                continue
            try:
                LockInfo.from_json(raw)  # 必须始终可解析（无半写/截断内容）
                reads_ok["n"] += 1
            except Exception as exc:
                errors.append(("corrupt", f"{exc!r} raw={raw[:120]!r}"))

    threads = [threading.Thread(target=_beat), threading.Thread(target=_read),
               threading.Thread(target=_read)]
    for t in threads:
        t.daemon = True
        t.start()
    time.sleep(0.8)
    stop.set()
    for t in threads:
        t.join(timeout=3)

    assert not errors, f"并发 heartbeat/读取出现锁文件损坏：{errors[:5]}"
    assert reads_ok["n"] > 0, "并发期间未能成功读到任何完整锁内容，判定无意义"
    final = LockInfo.from_json(lock_path.read_text(encoding="utf-8"))
    assert final.manifest_id == "m-hb"
    assert final.last_seen >= final.created_at
    m.release()


def test_heartbeat不产生残留临时文件(tmp_path):
    outgoing = tmp_path / "outgoing"
    m = OutgoingMutex(outgoing, stale_dir=tmp_path / "stale")
    m.acquire("m-tmp")
    for _ in range(30):
        m.heartbeat()
    leftovers = [p.name for p in outgoing.glob(".bb_outgoing.lock.*")
                 if ".reclaimed-" not in p.name]
    assert not leftovers, f"heartbeat 残留临时文件：{leftovers}"
    m.release()


# ===========================================================================
# §六 runtime lock fail-open 修复
# ===========================================================================
def test_preflight_生产缺锁返回runtime_drift(tmp_path):
    """§六-1：生产配置（test_mode=False）缺 lock → 必须失败，绝不 fail-open。"""
    coll = BBBrowserCollector(
        platforms=["hupu"],
        control_root=str(tmp_path / "control"),
        exchange_root=str(tmp_path / "exchange"),
        test_mode=False,
    )
    ok, diffs = coll.preflight()
    assert ok is False, "生产环境缺失 runtime lock 必须失败"
    assert diffs and diffs[0]["field"] == "lock_file"
    assert diffs[0]["actual"] == "missing"


def test_fetch_生产缺锁被阻断(tmp_path):
    """缺锁时 fetch 必须抛 runtime_drift 并生成差异报告。"""
    control = tmp_path / "control"
    coll = BBBrowserCollector(
        platforms=["hupu"],
        control_root=str(control),
        exchange_root=str(tmp_path / "exchange"),
        test_mode=False,
        timeout_seconds=1,
    )
    with pytest.raises(CollectorError) as ei:
        coll.fetch(keywords=["水污染"])
    assert ei.value.code == ERR_RUNTIME_DRIFT
    report = control / "runtime_drift.json"
    assert report.exists(), "runtime_drift 必须落盘差异报告"
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["code"] == ERR_RUNTIME_DRIFT
    assert payload["diffs"]


def test_preflight_显式test_mode跳过(tmp_path):
    """§六-2：单元测试用显式 test mode，而非生产 fail-open。"""
    coll = BBBrowserCollector(
        platforms=["hupu"],
        control_root=str(tmp_path / "control"),
        exchange_root=str(tmp_path / "exchange"),
        test_mode=True,
    )
    ok, diffs = coll.preflight()
    assert ok is True and diffs == []


def test_preflight_环境变量test_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("BBBROWSER_TEST_MODE", "1")
    coll = BBBrowserCollector(
        platforms=["hupu"],
        control_root=str(tmp_path / "control"),
        exchange_root=str(tmp_path / "exchange"),
    )
    ok, diffs = coll.preflight()
    assert ok is True and diffs == []


def test_preflight_参数可显式覆盖实例模式(tmp_path):
    coll = BBBrowserCollector(
        platforms=["hupu"],
        control_root=str(tmp_path / "control"),
        exchange_root=str(tmp_path / "exchange"),
        test_mode=True,
    )
    ok, _ = coll.preflight(test_mode=False)
    assert ok is False, "显式 test_mode=False 必须走生产 fail-closed 判定"


def test_runtime_lock_修复不影响mediacrawler():
    """§六-3：runtime lock / test_mode 逻辑只属于 bb-browser。

    静态断言 MediaCrawler、微博、小红书相关采集链路源码中不出现 bb-browser 专属符号，
    确保 Phase 3A 的 fail-closed 改造不会波及既有链路。
    """
    collectors_dir = Path(__file__).resolve().parents[1] / "app" / "collectors"
    targets = [
        "media_crawler_platform_collector.py",
        "media_crawler_weibo_collector.py",
        "mediacrawler_runner.py",
        "mediacrawler_runtime.py",
        "weibo_collector.py",
        "weibo_octopus_collector.py",
    ]
    forbidden = ("runtime_lock_path", "verify_runtime_lock", "BBBROWSER_TEST_MODE",
                 "OutgoingMutex", "ManifestRecovery")
    checked = 0
    for name in targets:
        p = collectors_dir / name
        if not p.exists():
            continue
        checked += 1
        src = p.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden:
            assert token not in src, f"{name} 被 bb-browser 逻辑污染：出现 {token}"
    assert checked >= 3, f"待检查的既有采集链路文件过少（checked={checked}）"


# ===========================================================================
# §七 ack_confirmed 状态
# ===========================================================================
def test_all_in_processed_不再固定返回False(tmp_path):
    """§七-1：processed 中已含全部期望任务 → 必须为 True。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    for rule_id, sources in parse_manifest_rules(text):
        for src in sources:
            _write_processed(exchange, mid, rule_id, src)
    expected = rec._expected_tasks(mid)
    assert expected
    assert rec._all_in_processed(mid, expected) is True


def test_ack_confirmed状态精确确认(tmp_path):
    """incoming 已清空 + processed 齐全 → 状态为 ack_confirmed。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    for rule_id, sources in parse_manifest_rules(text):
        for src in sources:
            _write_processed(exchange, mid, rule_id, src)
    st = rec.inspect(mid)
    assert st.state == S_ACK_CONFIRMED, f"应为 ack_confirmed，实际 {st.state}"


def test_ack_pending记录也认定为已ack(tmp_path):
    """§七-2：存在本 manifest 的 ack_pending 记录 → 视为已 ack（跨进程可恢复）。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    ack_dir = exchange / "ack_pending"
    ack_dir.mkdir(parents=True, exist_ok=True)
    (ack_dir / f"{mid}.json").write_text(
        json.dumps({"manifest_id": mid, "collector_run_id": 999, "files": []}),
        encoding="utf-8",
    )
    st = rec.inspect(mid)
    assert st.state == S_ACK_CONFIRMED


def test_已ack任务不得再次retry(tmp_path):
    """§七-3：ack_confirmed 的 manifest 不得进入 retry。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    for rule_id, sources in parse_manifest_rules(text):
        for src in sources:
            _write_processed(exchange, mid, rule_id, src)

    before = rec._retry_count(mid)
    coll = BBBrowserCollector(
        platforms=["hupu"], control_root=str(control),
        exchange_root=str(exchange), test_mode=True,
    )
    acted = coll.recover_prior_runs(reason="ack_no_retry")
    assert (mid, "archived_ack_confirmed") in acted
    assert rec._retry_count(mid) == before, "ack_confirmed 任务被错误地重试"
    assert (control / "archived" / f"{mid}.txt").exists()


def test_ack_confirmed进程重启后可恢复(tmp_path):
    """§七-4：新建实例（模拟重启）后仍能从磁盘恢复 ack_confirmed 判定。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    for rule_id, sources in parse_manifest_rules(text):
        for src in sources:
            _write_processed(exchange, mid, rule_id, src)

    fresh = ManifestRecovery(control, exchange, max_retries=3)  # 全新实例 = 重启
    assert fresh.inspect(mid).state == S_ACK_CONFIRMED


def test_processed缺项时不得判定ack_confirmed(tmp_path):
    """一致性：processed 少一项且无 ack_pending 记录 → 不得判为已 ack。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    all_tasks = [(rid, s) for rid, srcs in parse_manifest_rules(text) for s in srcs]
    for rule_id, src in all_tasks[:-1]:
        _write_processed(exchange, mid, rule_id, src)
    expected = rec._expected_tasks(mid)
    assert rec._all_in_processed(mid, expected) is False
    assert rec.inspect(mid).state != S_ACK_CONFIRMED


def test_processed中他manifest文件不得计入(tmp_path):
    """精确按 manifest_id 匹配：别的 manifest 的 processed 文件不得计入本次。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    other = uuid_mod.uuid4().hex
    for rule_id, sources in parse_manifest_rules(text):
        for src in sources:
            _write_processed(exchange, other, rule_id, src)
    expected = rec._expected_tasks(mid)
    assert rec._all_in_processed(mid, expected) is False


def test_ack_pending与processed一致性恢复(tmp_path):
    """§七-5：recover_pending_ack 幂等补齐 incoming→processed，并清理记录。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rule_id, sources = parse_manifest_rules(text)[0]
    src_file = _write_incoming(exchange, mid, rule_id, sources[0])

    ack_dir = exchange / "ack_pending"
    ack_dir.mkdir(parents=True, exist_ok=True)
    target = exchange / "processed" / src_file.name
    (ack_dir / f"{mid}.json").write_text(
        json.dumps({
            "manifest_id": mid,
            "collector_run_id": 12345,
            "files": [{"source": str(src_file), "target": str(target)}],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = BBBrowserCollector.recover_pending_ack(exchange)
    assert result["recovered"] == 1 and result["failed"] == 0
    assert target.exists(), "incoming 应被移入 processed"
    assert not src_file.exists()
    assert not (ack_dir / f"{mid}.json").exists(), "成功后应清理 ack_pending 记录"

    # 幂等：再执行一次不报错、不重复
    again = BBBrowserCollector.recover_pending_ack(exchange)
    assert again["recovered"] == 0 and again["failed"] == 0


def test_ack恢复不自动ack孤立incoming(tmp_path):
    """没有 ack_pending 记录的孤立 incoming 绝不能被自动 ack。"""
    rec, mid, text, control, exchange = _mk_partial(tmp_path)
    rule_id, sources = parse_manifest_rules(text)[0]
    orphan = _write_incoming(exchange, mid, rule_id, sources[0])
    result = BBBrowserCollector.recover_pending_ack(exchange)
    assert result["recovered"] == 0
    assert orphan.exists(), "孤立 incoming 必须原样保留"
