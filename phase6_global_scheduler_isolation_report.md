# Phase 6 阶段四：全局 scheduler 与 source 40 关系审计

生成时间：2026-08-19 16:36

## 结论先行

**不需要关闭或修改 source 40**，也**不需要独立 scheduler 进程**。bb-browser lane 通过独立 allowlist + 独立 advisory lock 已实现可靠隔离，不会 claim source 40。当前 source 62 schedule_enabled=false，无灰度时间重叠。

## 审计结论

| 问题 | 答案 |
|------|------|
| 全局 scheduler 是否发现 source 40 | **是**（enabled+schedule_enabled=true，due_scheduled_sources 不排除 weibo_mediacrawler） |
| source 40 何时 due | 16:46:30（每 360 分钟一次） |
| 是否与 bb-browser 灰度时间重叠 | **否**（source 62 未开启灰度；且 bb-browser lane 只 claim bb_browser） |
| bb-browser lane 是否只隔离自己的 dispatch | **是**（allowlist={"bb_browser"}） |
| 是否需要临时关闭 source 40 | **否** |
| 进程级 allowlist/排除隔离是否可行 | **是**（已实现） |
| 是否需要单独 scheduler 进程 | **否**（独立 advisory lock 足够） |

## 关键判断

1. source 40 的 `schedule_enabled=true` 是既有状态，其 scheduled 采集持续 failed（历史记录），但**不是本阶段问题**，按约束不触碰。
2. bb-browser lane 的 claim 严格限定 `{"bb_browser"}`，即使 source 40 与 bb-browser 同时 due，lane 也只 claim bb_browser。
3. 未来若授权开启 bb-browser 灰度，source 40 每 6 小时 due 一次，与 bb-browser lane 派发**互不干扰**（不同 source，不同 dispatch）。

## 未做

- 未关闭 source 40、未修改 source 40。
- 未修改全局 scheduler 默认 source 集合。
- 未开启真实灰度。
