# Phase 7 测试报告

生成时间：2026-08-19 17:23

## 结果

**192 passed / 0 failed，EXIT_CODE=0**（真实退出码，未用 `| tail` 掩盖）。

## 测试命令

```
cd backend
TEMP/TMP/TMPDIR = backend/.pytest_tmp
./.venv/Scripts/python.exe -m pytest \
  tests/test_bb_browser_collector.py tests/test_bb_browser_phase1b.py \
  tests/test_phase2_ack_recovery.py tests/test_phase2_outgoing_mutex.py \
  tests/test_phase2_platform_contract.py tests/test_phase2_recovery.py \
  tests/test_phase2_runtime_lock.py tests/test_phase2_admin_security.py \
  tests/test_phase3a_fixes.py tests/test_phase3a_collector_run.py \
  tests/test_phase4_platform_reliability.py \
  tests/test_phase5_scheduler_isolation.py tests/test_phase5_baidu_stability.py \
  tests/test_phase5_disposition.py tests/test_phase5_security_scan.py \
  tests/test_phase7_runtime_preflight.py \
  -q --noconftest -p no:cacheprovider
```

## 用例分布

| 阶段 | 用例数 |
|------|-------|
| Phase 1B | 20 |
| Phase 2 | 59 |
| Phase 3A | 50 |
| Phase 4 | 8 |
| Phase 5 | 33 |
| Phase 6（disposition/scheduler/security 更新） | 15 |
| Phase 7 新增（runtime preflight） | 7 |
| **合计** | **192** |

## Phase 7 新增测试覆盖

`test_phase7_runtime_preflight.py`（7 用例）：bb-sites/CLI/worker SHA256 漂移拒绝、CDP 不可达拒绝、daemon 不可达拒绝、config-lock 不一致拒绝、profile 缺失拒绝、control_root 缺失拒绝、全部通过允许继续。

## 无失败用例

无失败/跳过。唯一 warning 为 Pydantic V2 弃用提示（既有）。
