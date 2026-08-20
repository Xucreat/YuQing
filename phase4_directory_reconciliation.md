# Phase 4B 交换目录对账报告

生成时间：2026-08-19 15:19
结论：**287 个 incoming 全部为历史失败/超时/早期测试任务的产物，无任何文件被删除或移动。可明确归属的 6 组 manifest 中，4 组对应失败 CollectorRun，2 组为无 CollectorRun 的早期测试孤立文件。**

---

## 一、incoming 完整分组（按 manifest）

| # | task_manifest_id | 文件数 | source 分布 | 时间 | 对应 CollectorRun | run 状态 | manifest 去向 |
|---|---|---|---|---|---|---|---|
| 1 | d5caf173… | 128 | baidu42+bili42+yt42+hupu1+tt1 | 14:36-14:42 | #21248 | timeout failed | archive |
| 2 | 0b41b983… | 112 | baidu26+bili42+yt42+hupu1+tt1 | 11:32-11:34 | #21118 | zombie failed | rejected |
| 3 | manifest-3154428464654 | 20 | baidu20 | 08/17 17:37 | 无（早期测试） | — | 无 |
| 4 | landing-8platform | 11 | baidu2+bili2+yt2+hupu2+tt2+**weibo1** | 08/17 18:26 | 无（landing 测试） | — | 无 |
| 5 | 0b637f17… | 8 | bili3+yt3+hupu1+tt1 | 09:39 | #21045 | timeout failed | rejected |
| 6 | 6a6c7f2e… | 8 | bili3+yt3+hupu1+tt1 | 11:47 | #21126 | zombie failed | rejected |

source 汇总：baidu 90 / bilibili 92 / youtube 92 / hupu 6 / toutiao 6 / **weibo 1**。

## 二、五类分类

### 1. 可由已有成功任务安全 ack 的文件
**无。** 成功任务（#21048/#21050/#21292）的 incoming 已全部 ack 移入 processed（processed 43 = 历史 32 + #21292 的 11）。

### 2. 有失败任务但数据可能可恢复的文件（4 组，256 个）
- **d5caf173（128）**：#21248 超时，但 worker 最终完整产出全部 128 任务，**baidu 42 个全部成功**（14:36-14:42 持续产出）。数据完整，仅采集器在 240s 时提前放弃。
- **0b41b983（112）**：#21118 卡死后回收，baidu 仅 26/42 成功（16 个 baidu 因当时风控失败），其余平台完整。
- **0b637f17（8）** / **6a6c7f2e（8）**：#21045/#21126，baidu 全失败（风控），bili/yt/hupu/tt 各 3/1/1 成功。

### 3. 没有对应任务的孤立文件（2 组，31 个）
- **manifest-3154428464654（20）**：08/17 17:37 早期测试，20 个 baidu，无 CollectorRun 记录，无 manifest 文件。
- **landing-8platform（11）**：08/17 18:26 landing 测试，8 平台（含 weibo/xhs），无 CollectorRun 记录。

### 4. manifest 缺失或格式异常文件
- 上述 2 组孤立文件（31 个）的 manifest 不存在于 outgoing/rejected/archive 任何目录 → manifest 缺失。
- 其余 4 组的 manifest 均在（rejected 或 archive），格式正常。

### 5. 历史遗留且不可自动判断的文件
- **landing-8platform 的 1 个 weibo 文件**：08/17 landing 测试产物，含 weibo 平台，与当前 source 62 配置（allow_weibo=false）不符，且 weibo 链路属禁用范围，需人工判断，禁止自动处理。

## 三、processed 与 ack_pending 一致性

- processed 43 个：08/18 10 个（Phase 2 遗留）+ 08/19 33 个（#21048/#21050/#21292 成功归档）。
- **ack_pending 目录为空**：当前无未决 ack 记录。历史 incoming 均无对应 ack_pending（因为它们对应的 run 是 failed，未走 ack 流程）。

## 四、对账结论

1. **无数据被误当作新任务处理**：incoming 的 manifest 均能对应到明确的失败 run 或早期测试，无活跃 manifest 残留（outgoing 仅 2 个 reclaimed 锁）。
2. **287 个 incoming 均不可自动 ack**：它们对应的 CollectorRun 是 failed（timeout/zombie），不满足 ack 前置条件（成功 run 才能 ack）。
3. **无任何无审计删除/移动**：本阶段仅生成清单与建议。

---

## 处理建议（详见 phase4_recovery_plan.md）

- **类 2（256 个失败任务产物）**：数据本身多已完整（尤其 d5caf173 的 baidu 42 全成功），但对应 run 为 failed。是否重新入库需用户决策——直接 ack 会把数据记为「某成功 run 的产出」，与事实不符。
- **类 3（31 个孤立文件）**：早期测试残留，建议人工确认后归档或清理（不删除，仅标记）。
- **类 5（1 个 weibo 文件）**：禁止自动处理，保留待人工。
