# Phase 7 阶段一：只读前置审计

生成时间：2026-08-19 17:05

## 结论先行

运行环境与 Phase 6 一致且健康，无漂移。**全局 scheduler 仍在运行并持续调度 source 40（#21364 于 16:46:58 scheduled 触发且 failed，属既有行为）；bb-browser lane 未启动（默认关闭）。** source 62/40 状态未变，287 incoming 原位。

## 一、数据源状态

| 源 | enabled | schedule_enabled |
|----|---------|------------------|
| #62 bb_browser | true | **false** |
| #40 weibo_mediacrawler | true | true（既有） |

## 二、scheduler 运行状态

| 项 | 状态 |
|----|------|
| 全局 scheduler | **运行中**（advisory lock 被生产进程持有） |
| bb-browser 专用 lane | **未运行**（lock 未持有，默认关闭） |
| collector_schedule_mode | per_source（tick 60s） |
| bb_browser_schedule_enabled | false |

## 三、运行时锁定（逐项匹配）

| 项 | 结果 |
|----|------|
| Python worker SHA256 | ✅ 匹配 |
| Node CLI SHA256 | ✅ 匹配 |
| bb-browser 版本 | ✅ 0.14.2 |
| bb-sites HEAD | ✅ 3984c849… 未变 |
| CDP | ✅ HTTP 200 + TCP 通 |
| daemon | ✅ TCP 通（HTTP 401=需 token，正常） |
| Chrome profile | ✅ C:\cdp-profile |
| exchange/control root | ✅ 与 lock 一致 |

## 四、关键词与目录

- 启用监测关键词：3 个（霸州/通山县/慈口乡）
- 目录：incoming 287 / processed 43 / outgoing 2 / rejected 6 / stale 0 / ack_pending 不存在 / archive 8

## 五、最近 CollectorRun

- bb-browser：#21292 success（Phase 3A 灰度成功）、#21273/#21248 failed（历史）
- MediaCrawler：#21364 **scheduled failed**（16:46:58，source 40 既有调度）、#21291 success（manual）

## 六、关键观察

1. source 40 的 scheduled 采集在 16:46:58（next_collect_time 到期）触发且 failed —— 确认「全局 scheduler 仍会调度 source 40」这一既有行为，与 Phase 6 审计一致。
2. 无卡死 running（全局 running=0）。
3. 运行环境无漂移，具备进入后续阶段的只读基础。

## 七、结论

进入阶段二（补强 runtime preflight）与阶段三（隔离决策）的前置条件已满足；真实灰度仍被「凭据未轮换 + 未授权」阻塞。
