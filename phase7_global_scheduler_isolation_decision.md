# Phase 7 阶段三：全局 scheduler 与 source 40 隔离决策

生成时间：2026-08-19 17:10

## 结论先行

**用户尚未选择隔离方案，本阶段不修改 source 40、不开启真实灰度。** 关键事实：bb-browser lane 只 claim bb_browser（不触发 source 40），但**全局 scheduler 仍会（且一直在）运行 source 40**。

## 一、事实厘清

| 项 | 事实 |
|----|------|
| A. 专用 lane 隔离 | bb-browser lane 只 claim `bb_browser`，**不会 claim source 40** |
| B. 全局 scheduler | 仍会发现并运行 source 40（`#21364` 于 16:46:58 scheduled 触发且 failed） |

专用 lane **无法阻止**全局 scheduler 运行 source 40——两者是独立的 dispatch 路径。

## 二、三种方案评估

### 方案 1：临时关闭 source 40 schedule_enabled（推荐，若需全系统隔离）
- 动作：临时将 source 40 `schedule_enabled=false`；
- 需用户明确授权；
- 灰度结束后**不自动恢复**，需人工确认恢复；
- 这是「整个系统期间 MediaCrawler 不得运行」的唯一可靠方案。

### 方案 2：全局 scheduler 显式 allowlist/exclude
- 默认行为不变，仅灰度命令显式传入时生效；
- fail-closed，但不能误伤其他数据源；
- 实现成本高于方案 1，且需额外测试。

### 方案 3：独立 scheduler 进程
- 全局与 lane 不同进程 + 不同 advisory lock；
- 需验证重复 claim 不会发生；
- 较重；当前 lane 独立 lock 已足够，无需独立进程。

## 三、决策与建议

| 灰度诉求 | 推荐方案 |
|----------|---------|
| 仅「bb-browser 灰度不触发 MediaCrawler」 | **现有 lane 隔离已足够**（方案 A，无需额外动作） |
| 「整个系统期间 MediaCrawler 完全停止」 | **方案 1**（临时关闭 source 40，需用户授权 + 人工恢复） |

**当前状态：用户未选择方案 → 不修改 source 40、不开启真实灰度。** 等待用户明确授权。

## 四、未做

- 未修改 source 40。
- 未修改全局 scheduler 默认 source 集合。
- 未开启真实灰度。
