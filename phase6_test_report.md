# Phase 6 测试报告

生成时间：2026-08-19 16:42

## 结果

**185 passed / 0 failed，EXIT_CODE=0**（真实退出码，未用 `| tail` 掩盖）。

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
  -q --noconftest -p no:cacheprovider
```

## 用例分布

| 阶段 | 用例数 |
|------|-------|
| Phase 1B | 20 |
| Phase 2 | 59 |
| Phase 3A | 50 |
| Phase 4 | 8 |
| Phase 5 | 33（scheduler 12 + baidu 7 + disposition 11 + security 3） |
| Phase 6 新增/更新 | +15（disposition +10 + scheduler_gate +4 + security_gate +1） |
| **合计** | **185** |

## Phase 6 新增测试覆盖

| 需求 | 测试 |
|------|------|
| mapping 不可用不误判 orphan | test_phase5_disposition |
| manual_review 默认不移动 / 需 allow 标志 | 同上 |
| quarantine 需显式文件 / weibo/keep 永不移动 | 同上 |
| SHA256/目标存在/回滚/超批拒绝 | 同上 |
| source 62 schedule_enabled/enabled/key/collection_mode 门禁 | test_phase5_scheduler_isolation |
| 双钥匙全满足才允许启动 | 同上 |
| 灰度脚本凭据门禁 | test_phase5_security_scan |

## 无失败用例

无失败/跳过。唯一 warning 为 Pydantic V2 弃用提示（既有）。
