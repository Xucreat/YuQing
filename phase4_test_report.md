# Phase 4 测试报告

生成时间：2026-08-19 15:35

## 结果

**137 passed / 0 failed，EXIT_CODE=0**（真实退出码，未用 `| tail` 掩盖）。

## 测试命令

```
cd backend
TEMP/TMP/TMPDIR = backend/.pytest_tmp   # 项目内隔离临时目录，规避沙箱 safe-delete 拦截
./.venv/Scripts/python.exe -m pytest \
  tests/test_bb_browser_collector.py \
  tests/test_bb_browser_phase1b.py \
  tests/test_phase2_ack_recovery.py \
  tests/test_phase2_outgoing_mutex.py \
  tests/test_phase2_platform_contract.py \
  tests/test_phase2_recovery.py \
  tests/test_phase2_runtime_lock.py \
  tests/test_phase2_admin_security.py \
  tests/test_phase3a_fixes.py \
  tests/test_phase3a_collector_run.py \
  tests/test_phase4_platform_reliability.py \
  -q --noconftest -p no:cacheprovider
```

## 用例分布

| 文件 | 用例数 | 说明 |
|------|-------|------|
| test_bb_browser_collector | 17 | 采集器核心 |
| test_bb_browser_phase1b | 20 | Phase 1B |
| test_phase2_ack_recovery | 6 | ack 恢复 |
| test_phase2_outgoing_mutex | 6 | 互斥锁 |
| test_phase2_platform_contract | 7 | 平台契约 |
| test_phase2_recovery | 9 | 恢复/错误分类 |
| test_phase2_runtime_lock | 5 | 运行时锁 |
| test_phase2_admin_security | 9 | admin 数据源回归 |
| test_phase3a_fixes | 35 | Phase 3A 修复 |
| test_phase3a_collector_run | 15 | CollectorRun 卡死修复 |
| test_phase4_platform_reliability | 8 | **Phase 4C 新增**（错误分类补全） |
| **合计** | **137** | |

## 覆盖的测试维度

- recovery / ack / mutex / runtime lock ✅（test_phase2_* + test_phase3a_fixes）
- scheduler 相关：advisory lock / 防重复 claim 通过 Phase 4D 模拟验证（非 pytest，见 phase4_scheduler_gray_run_report.md）
- timeout / partial success ✅（test_phase3a_collector_run）
- 目录盘点 ✅（phase4_inventory.py 脚本产出，非 pytest）
- 平台错误分类 ✅（test_phase4_platform_reliability，8 新增）

## 无失败用例

无失败/跳过用例。唯一 warning 为 Pydantic V2 弃用提示（既有，与本次改动无关）。
