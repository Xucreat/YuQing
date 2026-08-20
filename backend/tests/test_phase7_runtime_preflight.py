"""Phase 7 阶段二：runtime preflight 补强测试。

覆盖：bb-sites HEAD / CLI SHA256 / worker SHA256 漂移、CDP/daemon 不可达、
exchange/control root 缺失、config 与 lock 不一致、profile 缺失，均拒绝启动；
全部通过才允许继续。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import scheduler as sched  # noqa: E402


def _write_lock(tmp: Path, **overrides) -> dict:
    lock = {
        "control_root": str(tmp / "collector_control"),
        "exchange_root": str(tmp / "collector_data"),
        "cdp_url": "http://127.0.0.1:9222",
        "daemon_url": "http://127.0.0.1:19824",
        "chrome_profile": str(tmp / "profile"),
    }
    lock.update(overrides)
    (tmp / "phase2_runtime_lock.json").write_text(json.dumps(lock), encoding="utf-8")
    return lock


def _cfg(lock: dict) -> dict:
    return {
        "control_root": lock["control_root"],
        "exchange_root": lock["exchange_root"],
        "cdp_url": lock["cdp_url"],
        "daemon_url": lock["daemon_url"],
        "collection_mode": "national",
    }


@pytest.fixture()
def lock_env(tmp_path: Path):
    (tmp_path / "profile").mkdir()
    (tmp_path / "collector_control").mkdir()
    (tmp_path / "collector_data").mkdir()
    lock = _write_lock(tmp_path)
    return tmp_path, lock


def _mock_verify_ok(monkeypatch):
    monkeypatch.setattr(
        "app.collectors.bb_browser_runtime.verify_runtime_lock",
        lambda path, **kw: (True, []),
    )


def _mock_probe(monkeypatch, result: bool):
    monkeypatch.setattr("app.collectors.bb_browser_runtime.probe_connectivity", lambda url, timeout=3.0: result)


# ---------------------------------------------------------------------------
# verify_runtime_lock 漂移（bb-sites / CLI / worker 统一表现为 diffs 非空）
# ---------------------------------------------------------------------------
def test_runtime_lock_drift_rejected(monkeypatch, lock_env):
    tmp, lock = lock_env
    for field in ("bb_sites_head", "node_cli_sha256", "python_worker_sha256"):
        monkeypatch.setattr(
            "app.collectors.bb_browser_runtime.verify_runtime_lock",
            lambda path, field=field, **kw: (False, [{"field": field, "expected": "a", "actual": "b"}]),
        )
        err = sched._validate_bb_browser_runtime_lock(_cfg(lock))
        assert err is not None and "runtime lock 校验失败" in err, field


def test_cdp_unreachable_rejected(monkeypatch, lock_env):
    tmp, lock = lock_env
    _mock_verify_ok(monkeypatch)
    _mock_probe(monkeypatch, False)  # CDP 与 daemon 都不可达，先命中 CDP
    err = sched._validate_bb_browser_runtime_lock(_cfg(lock))
    assert err is not None and "CDP 不可达" in err


def test_daemon_unreachable_rejected(monkeypatch, lock_env):
    tmp, lock = lock_env
    _mock_verify_ok(monkeypatch)
    def probe(url, timeout=3.0):
        return "19824" not in url  # CDP 通，daemon 不通
    monkeypatch.setattr("app.collectors.bb_browser_runtime.probe_connectivity", probe)
    err = sched._validate_bb_browser_runtime_lock(_cfg(lock))
    assert err is not None and "daemon 不可达" in err


def test_config_lock_mismatch_rejected(monkeypatch, lock_env):
    tmp, lock = lock_env
    _mock_verify_ok(monkeypatch)
    _mock_probe(monkeypatch, True)
    cfg = _cfg(lock)
    cfg["cdp_url"] = "http://127.0.0.1:9999"  # 与 lock 不一致
    err = sched._validate_bb_browser_runtime_lock(cfg)
    assert err is not None and "cdp_url" in err and "不一致" in err


def test_profile_missing_rejected(monkeypatch, lock_env):
    tmp, lock = lock_env
    _mock_verify_ok(monkeypatch)
    _mock_probe(monkeypatch, True)
    lock["chrome_profile"] = str(tmp / "nonexistent_profile")
    (tmp / "phase2_runtime_lock.json").write_text(json.dumps(lock), encoding="utf-8")
    err = sched._validate_bb_browser_runtime_lock(_cfg(lock))
    assert err is not None and "profile" in err


def test_missing_control_root_rejected(monkeypatch, lock_env):
    tmp, lock = lock_env
    cfg = _cfg(lock)
    cfg.pop("control_root")
    err = sched._validate_bb_browser_runtime_lock(cfg)
    assert err is not None and "control_root" in err


def test_all_checks_pass(monkeypatch, lock_env):
    tmp, lock = lock_env
    _mock_verify_ok(monkeypatch)
    _mock_probe(monkeypatch, True)
    err = sched._validate_bb_browser_runtime_lock(_cfg(lock))
    assert err is None
