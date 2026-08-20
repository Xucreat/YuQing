# Phase 5 阶段二：调度隔离设计

生成时间：2026-08-19 15:52

## 方案选型结论

**采用方案 B（独立 bb-browser scheduler lane）为骨架，融合方案 A 的 allowlist 语义。** 理由：

- 方案 A 若直接改现有全局 tick 的 allowlist，会破坏其他数据源的既有调度（不可接受）；
- 方案 A 的「为 bb-browser 增加明确 allowlist」本质就是新增一条独立派发路径，与方案 B 的 lane 等价；
- 方案 B 的独立 PG advisory lock 才能保证「两个 bb-browser scheduler 不同时运行」，且不与全局 scheduler 锁冲突。

**默认行为零变化**：`start_scheduler()` 完全不动；新增的 bb-browser lane 仅在显式开启时才启动。

## 设计

### 1. 独立 lane 结构

```
start_bb_browser_scheduler()
  ├─ 显式开关：BB_BROWSER_SCHEDULE_ENABLED=true（环境变量，默认 false）
  ├─ fail-closed 校验 _validate_bb_browser_scheduler()
  │    1. allowlist 环境变量 BB_BROWSER_SCHEDULE_ALLOWLIST 缺失 → 拒绝
  │    2. allowlist ≠ {"bb_browser"} → 拒绝（含未知 key / 混入 MediaCrawler）
  │    3. source 62 的 key ≠ bb_browser → 拒绝（查 DB）
  ├─ 独立 advisory lock：BB_BROWSER_ADVISORY_LOCK_KEY（区别于全局 SCHEDULER_ADVISORY_LOCK_KEY）
  └─ 独立 tick：_run_bb_browser_tick() → 复用 _run_collector_tick(include_data_source_keys={"bb_browser"})
```

### 2. fail-closed 规则（必须全部满足才启动）

| # | 条件 | 不满足时 |
|---|------|---------|
| 1 | `BB_BROWSER_SCHEDULE_ALLOWLIST` 已设置 | 不启动 |
| 2 | allowlist 恰好 = `{"bb_browser"}`（无未知 key） | 不启动 |
| 3 | allowlist 不含 `weibo_mediacrawler`/`xhs_mediacrawler`/`weibo_octopus` | 不启动 |
| 4 | DB 中 source 62 存在且 `key == "bb_browser"` | 不启动 |

### 3. 复用而非重写

- `_run_collector_tick(include_data_source_keys={"bb_browser"})`：复用现有 claim-then-dispatch、zombie 回收、ack、聚合逻辑。
- `_try_acquire_scheduler_lock` 泛化为可传 lock key 的辅助，或新增等价函数。
- `due_scheduled_sources(db, include_keys={"bb_browser"})`：确保只发现 bb_browser。

### 4. 日志字段

每次 lane 启动/tick 记录：lane=bb_browser、allowlist、discovered sources、claimed sources、dispatched sources、CollectorRun id、ack 状态。

### 5. 不做什么

- 不修改 source 62（schedule_enabled 仍 false，由显式开启 + 校验控制）。
- 不修改 source 40、不修改全局 `start_scheduler` 默认行为。
- 不默认开启 lane（`BB_BROWSER_SCHEDULE_ENABLED` 默认 false，fail-closed）。
- 不新增真实采集，本阶段只交付 lane 代码 + 测试 + dry-run 验证。
