"""bb-browser 运行时互斥 / 错误 / 锁（Phase 2 §三 §五 §八）。

绝对路径约束下的跨进程原子互斥（Windows 友好）：
- 用 os.open(O_CREAT | O_EXCL) 原子创建锁文件，杜绝 TOCTOU。
- 锁文件记录 owner_pid / manifest_id / created_at / last_seen（心跳）。
- 进程崩溃后锁不永久阻塞：stale 按 TTL 或 owner pid 死亡判定，并保留恢复证据
  （把孤儿 manifest 迁到 stale/，不删除）。
- 在任何情况下不删除 / 覆盖其它进程的 manifest（仅迁移 + 留证）。

运行时间：2026-08-19
"""
from __future__ import annotations

import datetime
import hashlib
import logging
import json
import os
import socket
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class CollectorError(RuntimeError):
    """带稳定 code 的采集错误；message 形如 "<code>: <detail>"。

    继承 RuntimeError 以兼容既有 pytest.raises(RuntimeError) 断言。
    """

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


ERR_OUTGOING_LOCKED = "outgoing_locked"
ERR_WORKER_BUSY = "worker_busy"
ERR_LOGIN_REQUIRED = "login_required"
ERR_CDP_UNREACHABLE = "cdp_unreachable"
ERR_DAEMON_UNREACHABLE = "daemon_unreachable"
ERR_ADAPTER_MISSING = "adapter_missing"
ERR_ADAPTER_ERROR = "adapter_error"
ERR_TIMEOUT = "timeout"
ERR_EMPTY_RESULT = "empty_result"
ERR_PARTIAL_RESULT = "partial_result"
ERR_STALE_TASK = "stale_task"
ERR_ACK_DEFERRED = "ack_deferred"
ERR_ACK_RECOVERY_FAILED = "ack_recovery_failed"
ERR_RUNTIME_DRIFT = "runtime_drift"
ERR_REJECTED = "rejected"
# Phase 4C：平台级错误分类补全（上游风控/阻断、manifest 非法、未知错误）。
ERR_UPSTREAM_BLOCKED = "upstream_blocked"
ERR_INVALID_MANIFEST = "invalid_manifest"
ERR_UNKNOWN_ERROR = "unknown_error"


def classify_adapter_error(error_obj, platform: str = "") -> str:
    """把 worker / adapter 返回的 error 对象分类为稳定错误码（§五 + Phase 4C）。

    分类顺序（前到后优先级递减）：
    - login_required：401/403/auth/未登录
    - adapter_missing：adapter/模块缺失
    - upstream_blocked：上游风控/阻断（failed to fetch / 安全验证 / 网络不给力 / captcha / 限流）
    - invalid_manifest：manifest 非法/格式错
    - adapter_error：其它 adapter 相关错误（含 timeout/adapter/error/退出码）
    - unknown_error：完全无法识别的最终兜底

    绝不允许把登录失败或上游风控当普通空结果。
    """
    if isinstance(error_obj, dict):
        msg = " ".join(str(v) for v in error_obj.values()).lower()
    else:
        msg = str(error_obj).lower()
    if any(k in msg for k in ("login", "401", "403", "unauthorized", "auth", "未登录", "需要登录", "请登录")):
        return ERR_LOGIN_REQUIRED
    if any(k in msg for k in ("adapter not found", "no such", "missing", "module not found", "not installed", "未安装", "不存在")):
        return ERR_ADAPTER_MISSING
    if any(k in msg for k in ("failed to fetch", "安全验证", "网络不给力", "风控", "blocked", "captcha", "验证码", "rate limit", "too many", "拒绝访问", "wappass")):
        return ERR_UPSTREAM_BLOCKED
    if any(k in msg for k in ("invalid manifest", "无效规则", "非法规则", "invalid rule", "manifest 格式", "格式错误")):
        return ERR_INVALID_MANIFEST
    if any(k in msg for k in ("adapter", "timeout", "error", "exception", "exit code", "退出码")):
        return ERR_ADAPTER_ERROR
    return ERR_UNKNOWN_ERROR


def classify_connectivity(cdp_ok: bool, daemon_ok: bool) -> Optional[str]:
    """根据连通性探测结果分类（§五）。cdp/daemon 均不可达时优先 cdp。"""
    if not cdp_ok:
        return ERR_CDP_UNREACHABLE
    if not daemon_ok:
        return ERR_DAEMON_UNREACHABLE
    return None


def compute_backoff_delay(attempt: int, base_seconds: int = 60, max_seconds: int = 3600) -> int:
    """指数退避（Phase 5 阶段四）：base * 2^(attempt-1)，上限 max_seconds。

    纯函数，供未来平台级重试/熔断状态机复用。attempt<=0 时返回 base。
    """
    if attempt <= 0:
        return min(base_seconds, max_seconds)
    return min(base_seconds * (2 ** (attempt - 1)), max_seconds)


def in_cooldown(blocked_at_ts: float, now_ts: float, cooldown_seconds: int) -> bool:
    """判断是否仍处于冷却窗口内（Phase 5 阶段四）。

    纯函数：now - blocked_at < cooldown 即冷却中。用于避免上游风控后立即高频重试。
    """
    if blocked_at_ts <= 0 or cooldown_seconds <= 0:
        return False
    return (now_ts - blocked_at_ts) < cooldown_seconds


def probe_connectivity(url: str, timeout: float = 3.0) -> bool:
    """安全的连通性 preflight（§七.7）：仅做 TCP 建连，不执行任何命令/不写文件。"""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def _platform_registry_sha256(p: Path) -> str:
    text = p.read_text(encoding="utf-8", errors="ignore")
    idx = text.index("PLATFORMS = {")
    start = text.index("{", idx)
    depth = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()


def verify_runtime_lock(
    lock_path: str | Path,
    bb_sites_dir: Optional[str | Path] = None,
) -> tuple[bool, list[dict]]:
    """§八 preflight：校验运行时与 phase2_runtime_lock.json 是否一致。

    返回 (ok, diffs)。diffs 为漂移字段列表，每项 {field, expected, actual}。
    发现漂移 → 调用方不得创建新 manifest，CollectorRun 标记 failed，code=runtime_drift。
    """
    lock_path = Path(lock_path)
    diffs: list[dict] = []
    if not lock_path.exists():
        return False, [{"field": "lock_file", "expected": "exists", "actual": "missing"}]
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, [{"field": "lock_file", "expected": "valid_json", "actual": "unreadable"}]

    def cmp_field(field: str, expected: str, actual: str) -> None:
        if expected != actual:
            diffs.append({"field": field, "expected": expected, "actual": actual})

    # worker 入口 + SHA256
    worker = lock.get("python_worker_entry")
    if worker and Path(worker).exists():
        cmp_field("python_worker_sha256", lock.get("python_worker_sha256", ""), _sha256_file(Path(worker)))
    else:
        diffs.append({"field": "python_worker_entry", "expected": worker, "actual": "missing"})

    # node CLI + SHA256
    cli = lock.get("node_cli")
    if cli and Path(cli).exists():
        cmp_field("node_cli_sha256", lock.get("node_cli_sha256", ""), _sha256_file(Path(cli)))
    else:
        diffs.append({"field": "node_cli", "expected": cli, "actual": "missing"})

    # 版本（从 package.json）
    cli_pkg = Path(cli).parent.parent / "package.json" if cli else None
    if cli_pkg and cli_pkg.exists():
        try:
            actual_ver = json.loads(cli_pkg.read_text(encoding="utf-8")).get("version")
            cmp_field("bb_browser_version", lock.get("bb_browser_version", ""), actual_ver)
        except (OSError, json.JSONDecodeError):
            diffs.append({"field": "bb_browser_version", "expected": lock.get("bb_browser_version"), "actual": "unreadable"})
    else:
        diffs.append({"field": "bb_browser_version", "expected": lock.get("bb_browser_version"), "actual": "package.json missing"})

    # bb-sites HEAD
    if bb_sites_dir and Path(bb_sites_dir).exists():
        try:
            r = subprocess.run(["git", "-C", str(bb_sites_dir), "rev-parse", "HEAD"],
                               capture_output=True, text=True, timeout=15)
            actual_head = r.stdout.strip() if r.returncode == 0 else "UNKNOWN"
        except Exception:
            actual_head = "UNKNOWN"
        cmp_field("bb_sites_head", lock.get("bb_sites_head", ""), actual_head)

    # 平台注册表 SHA256
    if worker and Path(worker).exists():
        cmp_field("platform_registry_sha256", lock.get("platform_registry_sha256", ""),
                  _platform_registry_sha256(Path(worker)))

    # 交换根 / 控制根必须存在
    for field in ("exchange_root", "control_root"):
        root = lock.get(field)
        if root and Path(root).exists():
            pass
        else:
            diffs.append({"field": field, "expected": root, "actual": "missing"})

    return (len(diffs) == 0), diffs


def pid_alive(pid: Optional[int]) -> bool:
    """跨平台进程存活探测（绝不向目标发送任何信号）。

    Windows 上 os.kill(pid, 0) 会退化为 TerminateProcess，故用 ctypes
    OpenProcess 仅做存在性探测（只读、不发送信号、不终止进程）。
    """
    if not pid or pid <= 0:
        return False
    pid = int(pid)
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def _pid_alive_windows(pid: int) -> bool:
    import ctypes

    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    err = kernel32.GetLastError()
    # 5=ERROR_ACCESS_DENIED：进程存在但无查询权限 → 视为存活
    # 87=ERROR_INVALID_PARAMETER：pid 不存在
    return err == 5


@dataclass
class LockInfo:
    owner_pid: int
    manifest_id: str
    created_at: float
    last_seen: float
    hostname: str = ""
    # Phase 3A：唯一所有权令牌。acquire 时生成，release 前必须校验，
    # 防止「旧 owner 被回收/新进程接管」后旧进程误删新锁。
    owner_token: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "LockInfo":
        data = json.loads(s)
        # 兼容旧锁（无 owner_token 字段）
        if "owner_token" not in data:
            data["owner_token"] = ""
        return cls(**data)


class OutgoingLockError(CollectorError):
    """并发获取 outgoing 互斥权被拒。code 默认 outgoing_locked。"""

    def __init__(self, detail: str, code: str = ERR_OUTGOING_LOCKED):
        super().__init__(code, detail)


class OutgoingMutex:
    """control_root/outgoing 的跨进程原子互斥锁。

    用法：
        mutex = OutgoingMutex(outgoing_dir, stale_dir)
        try:
            mutex.acquire(manifest_id)
            # ... 写 manifest + 等待 worker ...
        finally:
            mutex.release()

    - acquire 成功 → 当前进程独占 outgoing 写权。
    - 已有锁且活跃（owner 存活 + 未超 TTL）→ 抛 OutgoingLockError(outgoing_locked)。
    - 已有锁但 stale → 回收：迁移孤儿 manifest 到 stale/（留证），重建锁，继续。
    - 不删除任何其它进程的 manifest。
    """

    LOCK_NAME = ".bb_outgoing.lock"

    def __init__(
        self,
        outgoing_dir: str | Path,
        stale_dir: Optional[str | Path] = None,
        ttl_seconds: int = 300,
        heartbeat_interval: int = 10,
    ) -> None:
        self.outgoing = Path(outgoing_dir)
        self.lock_path = self.outgoing / self.LOCK_NAME
        self.stale_dir = Path(stale_dir) if stale_dir else self.outgoing.parent / "stale"
        self.ttl = int(ttl_seconds)
        self.heartbeat_interval = int(heartbeat_interval)
        self._info: Optional[LockInfo] = None
        self._manifest_id: Optional[str] = None
        self._owner_token: Optional[str] = None

    def _read_lock(self) -> Optional[LockInfo]:
        try:
            return LockInfo.from_json(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def _is_stale(self, info: LockInfo) -> bool:
        now = time.time()
        if (now - info.last_seen) > self.ttl:
            return True
        if not pid_alive(info.owner_pid):
            return True
        return False

    def acquire(self, manifest_id: str) -> None:
        self.outgoing.mkdir(parents=True, exist_ok=True)
        self.stale_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_id = manifest_id
        self._owner_token = uuid.uuid4().hex
        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            self._handle_existing_lock(manifest_id)
            return
        info = LockInfo(
            owner_pid=os.getpid(),
            manifest_id=manifest_id,
            created_at=time.time(),
            last_seen=time.time(),
            hostname=os.environ.get("COMPUTERNAME", ""),
            owner_token=self._owner_token,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(info.to_json())
        self._info = info
        self._sweep_orphans(manifest_id, reason="acquire_sweep")

    def _handle_existing_lock(self, manifest_id: str) -> None:
        info = self._read_lock()
        if info is None:
            self._reclaim(manifest_id, reason="lock_unreadable")
            return
        if not self._is_stale(info):
            raise OutgoingLockError(
                f"outgoing 已被活动进程占用(owner_pid={info.owner_pid}, "
                f"manifest_id={info.manifest_id})，worker 忙碌中，拒绝创建新任务",
                code=ERR_WORKER_BUSY,
            )
        self._reclaim(manifest_id, reason="stale_lock", stale_info=info)

    def _reclaim(self, manifest_id: str, reason: str, stale_info: Optional[LockInfo] = None) -> None:
        if stale_info is not None:
            self._relocate_manifest(stale_info.manifest_id, reason, stale_info)
        self._sweep_orphans(manifest_id, reason=f"{reason}_sweep")
        reclaimed = self.lock_path.with_name(f".bb_outgoing.lock.reclaimed-{int(time.time()*1000)}")
        try:
            os.replace(self.lock_path, reclaimed)
        except OSError:
            pass
        fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        info = LockInfo(
            owner_pid=os.getpid(),
            manifest_id=manifest_id,
            created_at=time.time(),
            last_seen=time.time(),
            hostname=os.environ.get("COMPUTERNAME", ""),
            owner_token=self._owner_token,
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(info.to_json())
        self._info = info

    def _write_lock_atomic(self, info: LockInfo) -> None:
        """临时文件 + 原子 replace 写入锁，避免并发/崩溃时锁文件半写损坏。"""
        tmp = self.lock_path.with_name(f".bb_outgoing.lock.tmp-{int(time.time()*1000)}-{os.getpid()}")
        tmp.write_text(info.to_json(), encoding="utf-8")
        os.replace(tmp, self.lock_path)

    def _relocate_manifest(self, mid: str, reason: str, stale_info: Optional[LockInfo]) -> None:
        src = self.outgoing / f"{mid}.txt"
        if not src.exists():
            return
        self.stale_dir.mkdir(parents=True, exist_ok=True)
        dst = self.stale_dir / f"{mid}.txt"
        try:
            os.replace(src, dst)
        except OSError:
            return
        ev = {
            "manifest_id": mid,
            "reason": reason,
            "reclaimed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "reclaimer_pid": os.getpid(),
            "prev_lock": stale_info.to_json() if stale_info else None,
        }
        (self.stale_dir / f"{mid}.stale.json").write_text(
            json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _sweep_orphans(self, current_manifest_id: str, reason: str) -> None:
        for f in self.outgoing.glob("*.txt"):
            if f.stem == current_manifest_id:
                continue
            self._relocate_manifest(f.stem, reason=reason, stale_info=None)

    def heartbeat(self) -> None:
        if self._info is None:
            return
        self._info.last_seen = time.time()
        try:
            self._write_lock_atomic(self._info)
        except OSError:
            pass

    def release(self) -> None:
        """释放锁：释放前校验当前锁仍属于本 (owner_pid + owner_token + manifest_id)。

        - 若锁文件已被回收 / 被新进程接管（pid/token/manifest_id 任一不符），
          旧进程不得删除新锁，仅清空自身状态后返回。
        - 兼容旧锁（无 owner_token 字段）：旧锁视为「无令牌」，只要 pid+manifest_id
          匹配即允许释放（向后兼容既有 Phase 2 测试）。
        """
        if self._info is None:
            return
        my = self._info
        try:
            cur = self._read_lock()
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            cur = None
        if cur is not None:
            token_matches = (cur.owner_token == my.owner_token) or (cur.owner_token == "" and my.owner_token == "")
            pid_matches = (cur.owner_pid == my.owner_pid)
            mid_matches = (cur.manifest_id == my.manifest_id)
            if not (token_matches and pid_matches and mid_matches):
                # 锁已被他人接管：旧 owner 不得删除新锁。
                logger.warning(
                    "OutgoingMutex.release 跳过：当前锁已属于新 owner "
                    "(cur_pid=%s cur_token=%s cur_mid=%s)，本进程 (pid=%s token=%s mid=%s) 不删除。",
                    cur.owner_pid, cur.owner_token[:8] if cur.owner_token else "", cur.manifest_id,
                    my.owner_pid, my.owner_token[:8] if my.owner_token else "", my.manifest_id,
                )
                self._info = None
                return
        try:
            self.lock_path.unlink()
        except OSError:
            pass
        self._info = None

    @property
    def lock_info(self) -> Optional[LockInfo]:
        return self._info
