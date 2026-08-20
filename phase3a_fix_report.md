# Phase 3A 缺陷修复报告

生成时间：2026-08-19 14:20
范围：bb-browser 聚合采集器（`data_sources.key=bb_browser`，id=62）

## 结论先行

- 6 处缺陷已修复（§二~§七），新增 50 个专项测试全部通过；bb-browser 核心 Phase 2 基线（70 个用例）无回归，合计 **120 passed / 0 failed**。
- **21118 / 21126 卡 running 的根因已定位并修复**：旧代码 `_process_collector` 的 except 分支引用了未导入的 `CollectorError`，异常在「标记 failed 之前」逃逸为 `NameError`；且旧代码主会话 `db.commit()` 失败时静默 `rollback()`，failed 状态无落盘路径。
- `schedule_enabled` 保持 false，未开启任何长期自动调度。

---

## §二 恢复 manifest 缺陷修复

文件：`backend/app/collectors/bb_browser_recovery.py`

`_filter_manifest_rules()` 重写后的每条规则现在都包含完整四字段：

- `rule_id`（保持原 id，用于 (task_id, source_key) 精确匹配）
- `rule_action=collect`
- `match_terms`（优先从原文提取，缺失时回退 `__bb_browser_hot__`）
- `sources`（保持原平台）

不再只写关键词字符串。新增 `_validate_retry_manifest()` 在 `retry_incomplete()` 落盘前校验四字段完整且只含 keep rule。

测试（`test_phase3a_fixes.py`）：
- retry manifest 四字段完整
- 用真实 worker `parse_rules()` 解析重试 manifest 成功
- 已完成任务不进入重试 manifest
- 部分 source 只重试未完成项
- 拒绝只写关键词

---

## §三 ManifestRecovery 接入真实运行流程

文件：`backend/app/collectors/bb_browser_collector.py`

`fetch()` 在创建新任务前（mutex.acquire 之前）调用 `recover_prior_runs(reason="pre_create_recovery")`，扫描范围扩展到 `outgoing` + `stale`：

1. 新任务创建前检查 outgoing/stale/recovery ✓
2. 发现 partial 任务优先 `retry_incomplete()` ✓
3. 只重试未完成的 (task_id, source_key)，按 manifest_id 精确匹配 ✓
4. retry 超上限 → 移 `rejected/` 并写 `.reason` ✓
5. 不删除失败任务产生的 incoming ✓
6. 新任务不误消费旧 manifest（跳过 `self._current_manifest_id`）✓
7. 结构化 recovery 日志（追加 `recovery_log.jsonl`）✓

---

## §四 OutgoingMutex 所有权修复

文件：`backend/app/collectors/bb_browser_runtime.py`

- 每个锁生成唯一 `owner_token`（`uuid.uuid4().hex`）
- `release()` 前校验 `owner_pid + owner_token + manifest_id` 三者完全匹配才删除
- 旧 owner 被回收后执行 release → 不删新锁（校验不通过）
- `heartbeat()` 用临时文件 + `os.replace()` 原子替换，避免并发损坏

测试（`test_phase2_outgoing_mutex.py` + `test_phase3a_fixes.py`）：
- 旧 owner 回收后 release 不删新锁
- 新 owner 锁不能被旧 owner 删除
- heartbeat 与 acquire 并发不损坏锁文件（Windows 原子替换期间的 PermissionError 视为正常，只校验「一旦读到内容必须完整可解析」）

---

## §五 CollectorRun 卡 running 修复（核心）

文件：`backend/app/collectors/service.py`

### 根因（证据链）

1. **未导入的 `CollectorError`**：旧代码 except 分支 `isinstance(exc, CollectorError)` 引用了未导入的类，当 fetch 抛出异常时，except 分支在「标记 failed 之前」就抛 `NameError`，run 永久停留 running。
2. **主会话 commit 静默失败**：旧代码 except 分支 `db.commit()` 失败仅 `db.rollback()`，failed 状态无落盘路径。
3. **僵尸回收覆盖不足**：旧 `reclaim_zombie_runs()` 只在应用启动时执行，且强制要求 `start_time < now - timeout`，覆盖不到同进程/同批次卡死。

### 修复

- 补 `from app.collectors.bb_browser_runtime import CollectorError`（bb_browser_runtime 是零依赖叶子模块，无循环 import）
- 新增 `_force_mark_run_failed()`：主会话 commit 失败时用独立会话把 running 强制改 failed（幂等，只改 running，异常只记日志）
- `_process_collector` 提前固化 `run_id_snapshot = int(run.id)`
- `collect_and_analyze_concurrent` 每个采集器线程 `finally` 兜底：按 `(batch_id, collector_name, timeout_minutes=0)` 回收本采集器僵尸 run
- 批次结束后全批回收：`reclaim_zombie_runs(rb, batch_id=batch_id, timeout_minutes=0)`
- `reclaim_zombie_runs()` 新增 `batch_id` / `collector_name` 过滤参数
- 稳定错误码前缀：`timeout:` / `adapter_error:` / `worker_busy:` / `collector_error:` / `zombie_reclaim:` / `db_commit_failed`

### 实测验证

重启后端后，启动对账将 21118 / 21126 回收为 failed，error_msg 带 `zombie_reclaim:` 前缀：

```
#21118 status=failed  err=zombie_reclaim: 采集运行超时/异常中断回收...
#21126 status=failed  err=zombie_reclaim: 采集运行超时/异常中断回收...
```

测试（`test_phase3a_collector_run.py`，15 个用例）：timeout/adapter_error/worker_busy/非 CollectorError/直接抛异常均落 failed + 稳定错误码；主会话 commit 失败用独立会话回收；force_mark_run_failed 幂等且不覆盖终态；reclaim 按 batch_id/collector_name 精确限定、不误杀同批其它源；并发链路线程级 finally 回收卡死 run。

---

## §六 运行时锁 fail-open 修复

文件：`backend/app/collectors/bb_browser_collector.py`、`backend/app/collectors/bb_browser_runtime.py`

- `preflight(test_mode=None)`：生产（test_mode=False）缺锁 → 返回 `(False, [lock_file missing])`，即 runtime_drift，fetch() 阻断并生成差异报告；显式 `test_mode=True` → 跳过（单元测试用）
- 实测 `verify_runtime_lock(phase2_runtime_lock.json)` 返回 `(True, [])`（无漂移）
- 不影响 MediaCrawler（静态扫描 media_crawler_*/weibo_* 确认不含 bb-browser 符号）

---

## §七 ack_confirmed 状态完善

文件：`backend/app/collectors/bb_browser_recovery.py`、`bb_browser_collector.py`

- `_all_in_processed()` 不再固定返回 False：检查 processed 目录按 manifest_id 精确匹配 (task_id, source_key)，或 `ack_pending/<mid>.json` 存在
- 已完成 ack 的任务不再次 retry
- 进程重启后 ack_confirmed 状态可恢复（ack_pending 记录持久化）
- processed / ack_pending 一致性测试通过

---

## 修改文件清单

| 文件 | 变更 |
|------|------|
| `backend/app/collectors/service.py` | 补 import CollectorError；新增 _force_mark_run_failed；线程级 finally + 全批 reclaim；reclaim 扩展过滤参数 |
| `backend/app/collectors/bb_browser_recovery.py` | _filter_manifest_rules 四字段；_validate_retry_manifest；recovery 日志 |
| `backend/app/collectors/bb_browser_runtime.py` | OutgoingMutex owner_token + release 校验 + heartbeat 原子替换 |
| `backend/app/collectors/bb_browser_collector.py` | fetch 前 recover_prior_runs；preflight test_mode；drift 报告 mkdir；ack 链 |
| `backend/scripts/_phase2_gray_run.py` | 删除硬编码密码改环境变量（§九） |
| `backend/tests/test_phase3a_fixes.py` | 新增 35 用例（§二~§七） |
| `backend/tests/test_phase3a_collector_run.py` | 新增 15 用例（§五） |
| `backend/tests/test_phase2_runtime_lock.py` | 补显式 test_mode（§六） |
| `backend/tests/test_bb_browser_phase1b.py` | 3 用例加 test_mode=True（§六） |
| `backend/tests/quarantine/` | 隔离 4 个临时文件（§九） |

## 测试命令与结果

```
.venv/Scripts/python.exe -m pytest \
  tests/test_bb_browser_collector.py tests/test_bb_browser_phase1b.py \
  tests/test_phase2_ack_recovery.py tests/test_phase2_outgoing_mutex.py \
  tests/test_phase2_platform_contract.py tests/test_phase2_recovery.py \
  tests/test_phase2_runtime_lock.py \
  tests/test_phase3a_fixes.py tests/test_phase3a_collector_run.py \
  -q --noconftest
```

结果：**120 passed, 0 failed**（Phase 3A 新增 50 + bb-browser Phase 2 基线 70）

## 未验证项清单

1. 五平台手动灰度（§十，需 `collector:run` 权限触发，待授权）
2. 灰度后的 CollectorRun 最终 status=success / ack_status=success 未验证
3. outgoing stale 锁（6a6c7f2e）与 159 个历史 incoming 文件的回收，待灰度时由新代码 `recover_prior_runs` 处理验证
4. 其余 Phase 2 测试（test_phase2a/2b/2c/2e、test_report_phase2_p1 等）依赖 conftest + 生产 DB 夹具，本次未纳入 `--noconftest` 隔离验证（属既有环境依赖，非本次改动范围）
