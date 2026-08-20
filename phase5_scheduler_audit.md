# Phase 5 阶段一：scheduler 只读复核

生成时间：2026-08-19 15:50

## 结论先行

调度框架**已具备 allowlist 机制**（`include_data_source_keys`），但**生产启动未启用**（`SCHEDULER_SOURCE_ALLOWLIST` 未设置，全源模式）。**不存在独立的 bb-browser 调度入口**。`due_scheduled_sources` 排除 `weibo_octopus` 但**不排除 `weibo_mediacrawler`(#40)**，因此直接开启 source 62 会自动连带 #40。

---

## 八个问题的明确回答

### 1. 是否支持 include_data_source_keys 白名单？
**支持。** `_run_collector_tick(include_data_source_keys=None)` 参数，经 `_normalize_source_allowlist` 归一化。

### 2. 白名单是否实际用于生产 scheduler 启动？
**未启用。** `start_scheduler(source_allowlist=None)` → 回退 `_configured_source_allowlist()` 读环境变量 `SCHEDULER_SOURCE_ALLOWLIST`（当前未设置，返回 None）→ 全源模式。

### 3. `_scheduler_source_allowlist` 从哪里读取？
`os.getenv("SCHEDULER_SOURCE_ALLOWLIST")`（逗号分隔 CSV），经 `_normalize_source_allowlist` 转 `frozenset`。

### 4. `due_scheduled_sources()` 是否支持按 key 过滤？
**支持。** `include_keys` 非 None 时追加 `AND key IN :include_keys`（bindparam expanding）。

### 5. claim SQL 是否同时受 source allowlist 约束？
**受约束。** `source_allowlist` 非 None 时 claim 语句追加 `AND key IN :include_keys`。

### 6. CollectorService 是否合并同一 tick 多个源执行？
**是。** `CollectorService(include_data_source_keys=set(due_keys), exclude_data_source_keys=set())` 单次调用并发执行所有 due 源。

### 7. source 40 与 62 在什么条件下同 tick 派发？
两者同时满足 `enabled=true AND schedule_enabled=true AND (next_collect_time IS NULL OR <= now())`。
- 当前 #62 `schedule_enabled=false` → 不派发；
- #40 `schedule_enabled=true` → due 即派发；
- **若 #62 开启且 due，会与 #40 合并派发**（`due_scheduled_sources` 不排除 `weibo_mediacrawler`）。

### 8. 是否存在不触发 MediaCrawler 的独立 bb-browser 调度入口？
**不存在。** 需新增独立 lane。

## 关键代码事实

| 项 | 值 |
|----|-----|
| due_scheduled_sources 排除 | `weibo_octopus`（仅此一个） |
| due_scheduled_sources **未排除** | `weibo_mediacrawler`、`xhs_mediacrawler` |
| collector_tick exclude | 空 set（不排除任何） |
| collector_job cron exclude | `{"weibo_octopus"}`（不排除 weibo_mediacrawler） |
| 新建源 schedule 默认 | MediaCrawler/foreign/external_browser=False，**其余（含 bb_browser）=True** |

> 注：source 62 现有 `schedule_enabled=false` 是 Phase 3A 手动设置，并非 `_schedule_enabled_default` 的返回值（该函数对 bb_browser 返回 True）。

## 当前运行时

- `collector_schedule_enabled=true`，`per_source` 模式，tick 60s。
- scheduler 单例锁被生产 uvicorn 持有（`pg_try_advisory_lock` 返回 false）。

## 结论

调度隔离**必须新增独立 bb-browser lane**（不能仅靠现有全局 tick 的 allowlist 参数，因为生产启动时该参数未绑定 bb_browser）。设计见 `phase5_scheduler_isolation_design.md`。
