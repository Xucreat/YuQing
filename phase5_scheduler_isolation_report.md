# Phase 5 阶段二：调度隔离实现报告

生成时间：2026-08-19 15:58

## 结论先行

已实现 bb-browser 专用调度 lane（独立 advisory lock + 严格 allowlist + fail-closed），**默认关闭**，不改变全局 scheduler 默认行为。12 个新增测试全绿，`app.main` 接线无破坏。

## 实现内容

| 文件 | 改动 |
|------|------|
| `app/core/config.py` | 新增 `bb_browser_schedule_enabled`(默认 False)、`bb_browser_schedule_allowlist`(默认 "")、`bb_browser_tick_interval_seconds`(默认 60) |
| `app/core/scheduler.py` | 新增 `BB_BROWSER_ALLOWLIST` / `BB_BROWSER_FORBIDDEN_KEYS` / `BB_BROWSER_ADVISORY_LOCK_KEY`；`_validate_bb_browser_allowlist`（纯函数）、`_validate_bb_browser_scheduler`、`_try_acquire/release_bb_browser_lock`、`_run_bb_browser_tick`、`start/stop_bb_browser_scheduler` |
| `app/main.py` | lifespan 接线 `start_bb_browser_scheduler()` / `stop_bb_browser_scheduler()`（默认 fail-closed 不启动） |
| `tests/test_phase5_scheduler_isolation.py` | 12 个用例 |

## fail-closed 校验（4 层）

1. `bb_browser_schedule_enabled=false`（默认）→ 不启动；
2. `bb_browser_schedule_allowlist` 缺失/为空 → 拒绝；
3. allowlist ≠ `{"bb_browser"}`（含未知 key 或混入 `weibo_mediacrawler`/`xhs_mediacrawler`/`weibo_octopus`/`weibo`/`xiaohongshu`/`xhs`）→ 拒绝；
4. DB 中 source 62 不存在或 `key != "bb_browser"` → 拒绝。

## 隔离保证

- **独立 advisory lock**：`BB_BROWSER_ADVISORY_LOCK_KEY` ≠ 全局 `SCHEDULER_ADVISORY_LOCK_KEY`（实测 distinct）。
- **只派发 bb_browser**：`_run_bb_browser_tick` → `_run_collector_tick(include_data_source_keys={"bb_browser"})`，`due_scheduled_sources` 按 key 过滤，claim 按 allowlist 约束。
- **不碰 MediaCrawler**：`BB_BROWSER_FORBIDDEN_KEYS` 含全部 MediaCrawler/微博/小红书 key，混入即拒绝。

## 测试结果

12 passed / 0 failed（真实退出码 0）：
- allowlist 恰好 bb_browser / 空 / 未知 key / 混入 MediaCrawler（4 组）
- 默认关闭 / allowlist 缺失 / source 62 不存在 / key 错误 / 校验通过（5 组）
- advisory lock key distinct / 归一化回归 / 禁止 key 集合（3 组）

## 验证行为

- `app.main` import 正常。
- 默认 `start_bb_browser_scheduler()` 实测不启动（fail-closed）。

## 未做

- 未开启真实调度（`bb_browser_schedule_enabled` 保持 false）。
- 未修改 source 62 / source 40 / MediaCrawler / bb-sites。
