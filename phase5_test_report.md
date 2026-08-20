# Phase 5 测试报告

生成时间：2026-08-19 16:09

## 结果

**170 passed / 0 failed，EXIT_CODE=0**（真实退出码，未用 `| tail` 掩盖）。

## 测试命令

```
cd backend
TEMP/TMP/TMPDIR = backend/.pytest_tmp   # 项目内隔离临时目录
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

| 阶段 | 文件 | 用例数 |
|------|------|-------|
| Phase 1B | test_bb_browser_phase1b | 20 |
| Phase 2 | collector/ack_recovery/outgoing_mutex/platform_contract/recovery/runtime_lock/admin_security | 17+6+6+7+9+5+9=59 |
| Phase 3A | fixes / collector_run | 35+15=50 |
| Phase 4 | platform_reliability | 8 |
| Phase 5 | scheduler_isolation / baidu_stability / disposition / security_scan | 12+7+11+3=33 |
| **合计** | | **170** |

## Phase 5 新增测试覆盖

| 需求 | 测试 |
|------|------|
| allowlist 只发现 bb_browser / 混入 MediaCrawler 拒绝 | test_phase5_scheduler_isolation |
| 未知 source key fail-closed | 同上 |
| allowlist 缺失不派发 | 同上 |
| advisory lock 隔离（key distinct） | 同上 |
| 默认全局 scheduler 归一化回归 | 同上 |
| 百度退避/冷却纯函数 | test_phase5_baidu_stability |
| incoming dry-run 不移动 / apply 需显式 / 超批拒绝 / SHA 不匹配 / 目标存在 / 回滚 / failed 不 ack / orphan 不 ack / weibo 不处理 | test_phase5_disposition |
| 明文凭据扫描 | test_phase5_security_scan |

## 无失败用例

无失败/跳过。唯一 warning 为 Pydantic V2 弃用提示（既有，与本次无关）。
