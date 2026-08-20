# Phase 4D 受控自动调度验证报告

生成时间：2026-08-19 15:29
结论：**无法可靠隔离 → 不开启真实自动调度，仅完成 scheduler 等价模拟。全部验证项通过，source 62 schedule_enabled 保持 false。**

---

## 一、核心决策依据

`weibo_mediacrawler`(#40) 当前已处于 `enabled=true + schedule_enabled=true`（每 360 分钟，next=16:46:30）的**既有状态**，且其 scheduled run 长期 failed（#21088/#20867/#20661）。

scheduler 的 `_run_collector_tick` 会一次性派发所有 due 源。若开启 bb_browser 真实自动调度，bb_browser 与 weibo_mediacrawler 将**共存于同一 tick 派发**，无法做到「只调度 bb_browser、绝不触碰 MediaCrawler」。因此：

> **不具备可靠隔离条件 → 本阶段只做 scheduler tick simulation，不创建灰度数据源、不开启真实自动调度。**（符合任务 Phase 4D 兜底条款）

## 二、调度等价模拟结果（全部通过）

| 验证项 | 结果 | 判定 |
|--------|------|------|
| 是否正确发现 source 62 | `due_scheduled_sources` 对 bb_browser 返回空（schedule_enabled=false） | ✅ |
| 若开启后是否被发现 | id=62，`would_be_due_if_enabled=true`（置 true 且 next 到期即被发现） | ✅ |
| 是否遵守 schedule interval | per_source 模式，`schedule_interval_minutes` 逐源生效（claim 用 `make_interval(mins=>interval)`） | ✅ |
| PG advisory lock | `pg_try_advisory_lock` 返回 false → 锁已被生产 uvicorn 持有，跨进程单例生效 | ✅ |
| 避免重复 run | claim-then-dispatch：单条原子 UPDATE 推进 next_collect_time，tick 内不重复选中 | ✅ |
| 失败/超时/partial 处理 | `_run_collector_tick` 每次 tick 开头 `reclaim_zombie_runs`；失败源不推进（见 §五 修复） | ✅ |
| ack 执行 | `collect_and_analyze_concurrent` 内 ack_pending_export（成功 run 才 ack） | ✅ |
| 回收 zombie run | tick 开头 + 线程级 finally + 启动对账 三层兜底 | ✅ |
| 触发 MediaCrawler？ | 若开启会连带（#40 同在 due 候选），**故不开启** | ⚠️ 已规避 |

## 三、模拟证据

详见 `phase4_scheduler_sim.json`。关键字段：
- `bb_browser_discovered_now.rows = []`（当前不被发现）
- `advisory_lock.held_by_other_process = true`（单例锁被生产进程持有）
- `schedule_enabled_sources.mediacrawler_among_them = [#40 weibo_mediacrawler]`

## 四、未执行的真实灰度

按任务「若执行真实灰度：连续 3~5 轮、每轮 3 关键词、记录五平台/run/ack/目录/确认 running 归零/确认 MediaCrawler 未触发」——**因无法可靠隔离 MediaCrawler（#40），本阶段不执行真实自动调度灰度**。

## 五、结论

1. **source 62 schedule_enabled 仍为 false**，未开启任何自动调度。
2. 调度框架对 bb_browser 的发现/claim/防重复/advisory lock 逻辑经模拟验证正确，若未来允许开启（且先解决 #40 隔离问题），可安全启用。
3. **MediaCrawler 微博 #40 的 schedule_enabled=true 是既有状态**（非本阶段修改），其 scheduled 采集持续 failed——建议后续单独评估是否应由用户关闭，但本阶段按约束未触碰。
