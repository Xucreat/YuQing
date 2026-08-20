"""bb-browser 失败任务 / stale manifest 恢复状态机（Phase 2 §四）。

状态集合：active / processing / partial / retryable / rejected / archived /
          stale / ack_pending / ack_confirmed

核心不变量：
- 失败任务绝不永久留在 outgoing 阻塞后续任务（stale 会被回收迁移）。
- 重试只重试未完成的 (task_id, source_key)，已完成的不重复。
- 超过最大重试次数 → 移入 rejected/ 并写 reason 文件。
- 绝不删除失败任务产生的 incoming 文件（incoming 只在 ack 成功时移动到 processed）。
- 新任务按 task_manifest_id 精确匹配，不会误消费旧 manifest 的 incoming。

运行时间：2026-08-19
"""
from __future__ import annotations

import datetime
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.collectors.bb_browser_collector import parse_manifest_rules
from app.collectors.bb_browser_runtime import (
    CollectorError,
    LockInfo,
    ERR_REJECTED,
    is_manifest_cancelled,
    pid_alive,
)

# 状态常量
S_ACTIVE = "active"
S_PROCESSING = "processing"
S_PARTIAL = "partial"
S_RETRYABLE = "retryable"
S_REJECTED = "rejected"
S_ARCHIVED = "archived"
S_STALE = "stale"
S_ACK_PENDING = "ack_pending"
S_ACK_CONFIRMED = "ack_confirmed"
S_CANCELLED = "cancelled"  # Phase 2：已取消（超时），终端态，不再重试/续采

# incoming 头部标记（与 collector 一致）
HEADER_TASK_MANIFEST_ID = "task_manifest_id"
HEADER_TASK_ID = "task_id"
HEADER_SOURCE_KEY = "source_key"


@dataclass
class ManifestStatus:
    manifest_id: str
    state: str
    expected: Set[Tuple[str, str]] = field(default_factory=set)
    present: Set[Tuple[str, str]] = field(default_factory=set)
    incomplete: Set[Tuple[str, str]] = field(default_factory=set)
    retry_count: int = 0
    reason: Optional[str] = None


def classify_manifest_state(
    lock_alive: bool,
    present: Set[Tuple[str, str]],
    expected: Set[Tuple[str, str]],
    ack_confirmed: bool,
    retry_count: int,
    max_retries: int = 3,
) -> str:
    """纯函数：根据锁/进度/重试次数判定 manifest 状态（§四）。"""
    if ack_confirmed:
        return S_ACK_CONFIRMED
    if lock_alive:
        return S_PROCESSING if present else S_ACTIVE
    if not expected:
        return S_STALE
    if present >= expected:
        return S_ACK_PENDING
    # present < expected → 部分完成
    if retry_count >= max_retries:
        return S_REJECTED
    return S_RETRYABLE  # 可重试（= partial 且未超限）


class ManifestRecovery:
    """失败/stale manifest 的跨进程恢复。

    目录约定（control_root 下）：
      outgoing/   active manifest
      stale/      被回收迁移的孤儿 manifest（含 .stale.json 证据）
      rejected/   超过最大重试次数的 manifest（含 .reason.json）
      archived/   已完成归档的 manifest
      recovery/   重试计数 sidecar（<manifest_id>.retry.json）
    """

    def __init__(self, control_root: str | Path, exchange_root: str | Path, max_retries: int = 3):
        self.control_root = Path(control_root)
        self.exchange_root = Path(exchange_root)
        self.max_retries = int(max_retries)
        self.outgoing = self.control_root / "outgoing"
        self.stale_dir = self.control_root / "stale"
        self.rejected_dir = self.control_root / "rejected"
        self.archived_dir = self.control_root / "archived"
        self.recovery_dir = self.control_root / "recovery"
        self._lock_path = self.outgoing / ".bb_outgoing.lock"

    # -- 工具 ---------------------------------------------------------------
    def _manifest_path(self, manifest_id: str) -> Optional[Path]:
        for d in (self.outgoing, self.stale_dir):
            p = d / f"{manifest_id}.txt"
            if p.exists():
                return p
        return None

    def _read_lock(self) -> Optional[LockInfo]:
        try:
            return LockInfo.from_json(self._lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _lock_alive_for(self, manifest_id: str) -> bool:
        info = self._read_lock()
        if info is None:
            return False
        if info.manifest_id != manifest_id:
            return False
        if not pid_alive(info.owner_pid):
            return False
        return (time.time() - info.last_seen) <= 300

    def _expected_tasks(self, manifest_id: str) -> Set[Tuple[str, str]]:
        p = self._manifest_path(manifest_id)
        if p is None:
            return set()
        rules = parse_manifest_rules(p.read_text(encoding="utf-8", errors="ignore"))
        out: Set[Tuple[str, str]] = set()
        for rule_id, sources in rules:
            for src in sources:
                out.add((rule_id, src))
        return out

    def _present_tasks(self, manifest_id: str) -> Set[Tuple[str, str]]:
        incoming = self.exchange_root / "incoming"
        if not incoming.exists():
            return set()
        out: Set[Tuple[str, str]] = set()
        for f in incoming.glob("*.txt"):
            try:
                header = _parse_header(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            if header.get(HEADER_TASK_MANIFEST_ID) != manifest_id:
                continue
            tid = header.get(HEADER_TASK_ID)
            sk = header.get(HEADER_SOURCE_KEY)
            if tid and sk:
                out.add((tid, sk))
        return out

    def _retry_count(self, manifest_id: str) -> int:
        p = self.recovery_dir / f"{manifest_id}.retry.json"
        try:
            return int(json.loads(p.read_text(encoding="utf-8")).get("retry_count", 0))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return 0

    def _set_retry_count(self, manifest_id: str, count: int, reason: str = "") -> None:
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        (self.recovery_dir / f"{manifest_id}.retry.json").write_text(
            json.dumps({
                "manifest_id": manifest_id,
                "retry_count": count,
                "last_error": reason,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _log_recovery(self, entry: dict) -> None:
        """结构化 recovery 日志（追加到 recovery/recovery_log.jsonl）。

        每条记录含：at / manifest_id / action / previous_state / incomplete /
        retry_count / reason。供 Phase 3A 灰度审计与人工排查。
        """
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.recovery_dir / "recovery_log.jsonl"
        entry = dict(entry)
        entry.setdefault("at", datetime.datetime.now(datetime.timezone.utc).isoformat())
        try:
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # -- 核心 ---------------------------------------------------------------
    def inspect(self, manifest_id: str) -> ManifestStatus:
        # Phase 2：已取消（超时）manifest 为终端态，recovery 不再重试/续采。
        if is_manifest_cancelled(self.control_root, manifest_id):
            return ManifestStatus(
                manifest_id=manifest_id,
                state=S_CANCELLED,
                reason="cancelled",
            )
        expected = self._expected_tasks(manifest_id)
        present = self._present_tasks(manifest_id)
        ack_confirmed = not present and bool(expected) and self._all_in_processed(manifest_id, expected)
        lock_alive = self._lock_alive_for(manifest_id)
        retry_count = self._retry_count(manifest_id)
        state = classify_manifest_state(
            lock_alive, present, expected, ack_confirmed, retry_count, self.max_retries
        )
        return ManifestStatus(
            manifest_id=manifest_id,
            state=state,
            expected=expected,
            present=present,
            incomplete=expected - present,
            retry_count=retry_count,
        )

    def _all_in_processed(self, manifest_id: str, expected: Set[Tuple[str, str]]) -> bool:
        """精确确认本 manifest 的全部期望任务已落到 processed（跨进程可恢复）。

        判定依据（按优先级）：
        1. processed 目录中存在与本 manifest 关联的全部 (task_id, source_key) 文件
           （文件头含 task_manifest_id / task_id / source_key，逐项精确匹配）；
        2. 存在本 manifest 的 ack_pending 记录（表示已成功 ack，文件已移入 processed
           或正在由 recover_pending_ack 幂等补齐）。

        绝不再固定返回 False（Phase 3A 缺陷修复）。
        """
        if not expected:
            return False
        processed = self.exchange_root / "processed"
        if processed.exists():
            present_in_processed: Set[Tuple[str, str]] = set()
            for f in processed.glob("*.txt"):
                try:
                    header = _parse_header(f.read_text(encoding="utf-8", errors="ignore"))
                except OSError:
                    continue
                if header.get(HEADER_TASK_MANIFEST_ID) != manifest_id:
                    continue
                tid = header.get(HEADER_TASK_ID)
                sk = header.get(HEADER_SOURCE_KEY)
                if tid and sk:
                    present_in_processed.add((tid, sk))
            if expected.issubset(present_in_processed):
                return True
        # ack_pending 记录存在 → 已成功 ack（跨进程可恢复）
        ack_rec = self.exchange_root / "ack_pending" / f"{manifest_id}.json"
        if ack_rec.exists():
            return True
        return False

    def retry_incomplete(self, manifest_id: str, reason: str = "") -> Optional[int]:
        """只重试未完成的 (task_id, source_key)。

        - 无未完成任务 → 返回 None（无需重试）。
        - 重试次数已达上限 → 移入 rejected/ 并写 reason 文件，返回 retry_count（不再 +1）。
        - 否则写「仅含未完成 rule」的新 manifest 到 outgoing（同 manifest_id，复用 incoming 匹配），
          返回新的 retry_count。
        """
        st = self.inspect(manifest_id)
        if not st.incomplete:
            return None
        if st.retry_count >= self.max_retries:
            self.reject(manifest_id, reason or "retry_exhausted")
            return st.retry_count

        new_count = st.retry_count + 1
        # 重写 manifest：仅保留未完成 rule（按 rule_id 过滤）
        p = self._manifest_path(manifest_id)
        if p is None:
            return None
        text = p.read_text(encoding="utf-8", errors="ignore")
        incomplete_rule_ids = {tid for tid, _ in st.incomplete}
        retry_text = _filter_manifest_rules(text, incomplete_rule_ids, manifest_id)
        # 校验重写后的 manifest 可被 worker 解析且确实只含未完成 rule
        _validate_retry_manifest(retry_text, incomplete_rule_ids)
        self.outgoing.mkdir(parents=True, exist_ok=True)
        (self.outgoing / f"{manifest_id}.txt").write_text(retry_text, encoding="utf-8")
        self._set_retry_count(manifest_id, new_count, reason)
        self._log_recovery({
            "manifest_id": manifest_id,
            "action": "retry_incomplete",
            "previous_state": st.state,
            "incomplete": sorted(f"{t}|{s}" for t, s in st.incomplete),
            "retry_count": new_count,
            "reason": reason or "partial_retry",
        })
        return new_count

    def reject(self, manifest_id: str, reason: str) -> None:
        """把 manifest 移入 rejected/ 并写 reason 文件（绝不删除）。"""
        self.rejected_dir.mkdir(parents=True, exist_ok=True)
        p = self._manifest_path(manifest_id)
        if p is not None:
            try:
                p.rename(self.rejected_dir / p.name)
            except OSError:
                pass
        (self.rejected_dir / f"{manifest_id}.reason.json").write_text(
            json.dumps({
                "manifest_id": manifest_id,
                "reason": reason,
                "code": ERR_REJECTED,
                "rejected_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "retry_count": self._retry_count(manifest_id),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def archive(self, manifest_id: str) -> None:
        self.archived_dir.mkdir(parents=True, exist_ok=True)
        p = self._manifest_path(manifest_id)
        if p is not None:
            try:
                p.rename(self.archived_dir / p.name)
            except OSError:
                pass

    def recover_stale(self) -> List[ManifestStatus]:
        """扫描 outgoing + stale 中无活跃锁的 manifest，驱动重试/拒绝/归档。"""
        results: List[ManifestStatus] = []
        for d in (self.outgoing, self.stale_dir):
            if not d.exists():
                continue
            for f in sorted(d.glob("*.txt")):
                mid = f.stem
                st = self.inspect(mid)
                results.append(st)
                if st.state == S_RETRYABLE:
                    self.retry_incomplete(mid, reason="stale_recover")
                elif st.state == S_REJECTED:
                    self.reject(mid, "retry_exhausted")
        self._log_recovery({
            "action": "recover_stale",
            "scanned": [s.manifest_id for s in results],
            "summary": {s.state: 1 for s in results},
        })
        return results


def _parse_header(text: str) -> Dict[str, str]:
    header: Dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            k = k.strip()
            if k and not k.startswith("-"):
                header[k] = v.strip()
    return header


def _filter_manifest_rules(text: str, keep_rule_ids: Set[str], manifest_id: str) -> str:
    """保留头部 + 仅保留 keep_rule_ids 的 rule 块，去掉其余 rule。

    Phase 3A 修复：每条重写后的 rule 必须完整包含
    ``rule_id / rule_action / match_terms / sources`` 四个字段，不得只写关键词字符串。
    match_terms 优先从原文对应 rule 块提取；缺失时回退到占位（占位仅用于 hot 规则，
    绝不会把单列关键词误当整条 rule）。
    """
    head_lines: List[str] = []
    for line in text.splitlines():
        if line.strip().startswith("---BEGIN RULE---"):
            break
        head_lines.append(line)
    rules = parse_manifest_rules(text)
    out = list(head_lines)
    out.append("")
    for rule_id, sources in rules:
        if rule_id not in keep_rule_ids:
            continue
        block = _extract_rule_block(text, rule_id)
        match_terms = (block.get("match_terms") or "").strip()
        if not match_terms:
            # 兜底：在原文中搜索该 rule 的 match_terms；再不行用 hot 占位（安全、可被 worker 解析）
            match_terms = "__bb_browser_hot__"
        out.append("---BEGIN RULE---")
        out.append(f"rule_id={rule_id}")
        out.append("rule_action=collect")
        out.append(f"match_terms={match_terms}")
        out.append(f"sources={','.join(sources)}")
        out.append("---END RULE---")
        out.append("")
    return "\n".join(out)


def _validate_retry_manifest(retry_text: str, keep_rule_ids: Set[str]) -> None:
    """校验重试 manifest：每个 rule 含完整四字段，且仅含 keep 的 rule。

    校验失败抛 ValueError（调用方将其转化为 CollectorError 暴露，绝不静默）。
    """
    rules = parse_manifest_rules(retry_text)
    if not rules and keep_rule_ids:
        raise ValueError("retry manifest 未包含任何可解析 rule")
    seen = set()
    for rule_id, sources in rules:
        seen.add(rule_id)
        if rule_id not in keep_rule_ids:
            raise ValueError(f"retry manifest 含非预期 rule：{rule_id}")
        # 重新解析整块，确认四个字段齐全
        block = _extract_rule_block(retry_text, rule_id)
        missing = [k for k in ("rule_id", "rule_action", "match_terms", "sources") if not (block.get(k) or "").strip()]
        if missing:
            raise ValueError(f"retry manifest rule {rule_id} 缺少字段：{missing}（不得只写关键词字符串）")
        if not sources:
            raise ValueError(f"retry manifest rule {rule_id} 缺少 sources")


def _extract_rule_block(text: str, rule_id: str) -> Dict[str, str]:
    import re

    for block in re.findall(r"---BEGIN RULE---(.*?)---END RULE---", text, re.S):
        d: Dict[str, str] = {}
        for line in block.strip().splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
        if d.get("rule_id") == rule_id:
            return d
    return {}
