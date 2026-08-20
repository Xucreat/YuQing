# Phase 5 阶段三：partial success 策略决策

生成时间：2026-08-19 16:00

## 结论先行

**默认保持 all-or-nothing（策略 1），不启用 platform-level partial（策略 2）。** 现有 `partial`/`ack_status=deferred` 语义只服务于 MediaCrawler/微博的评论与 ack 导出，**不适用于 bb-browser**（其 fetch 是 all-or-nothing）。

## 一、审计：当前 partial 语义

| 语义 | 位置 | 适用范围 |
|------|------|---------|
| `run.status = "success" if c_failed == 0 else "partial"` | service.py:808 | 单源「创建了 Opinion 但部分 AI 分析失败」 |
| `ack_status` pending/deferred/success/failed | service.py:827-859 | MediaCrawler/微博 ack_pending_export 状态机 |
| `run.status = "warning"`（region_kw 空 fail-safe） | service.py:812 | 配置异常保护 |

**bb-browser 不进入上述 partial 分支**：其 `fetch()` 是 all-or-nothing——任一平台失败即抛异常 → `except` 分支 `run.status=failed`。因此 bb-browser 的 run 只有 success 或 failed 两态，不存在 partial。

## 二、两种策略对比

| | 策略 1：all-or-nothing（当前） | 策略 2：platform-level partial |
|---|---|---|
| 任一平台失败 | 整批 failed，incoming 不 ack | 成功平台入库+ack，失败平台 retry |
| CollectorRun | success / failed | partial / warning |
| 伪装成功风险 | 无（宁可整批失败） | 需严格标记，风险中 |
| 实现成本 | 已实现 | 需平台级状态/ack/retry/错误码/统计/重启恢复/幂等 |

## 三、决策

**采用策略 1（all-or-nothing），默认保持不变。** 理由：

1. 任务明确「默认继续保持 all-or-nothing，除非有明确配置项显式启用 partial 模式」。
2. 策略 2 需改造 `_wait_for_results`（all-or-nothing → 检测 worker reject 信号 + 平台级降级）、ack 语义（partial 时只 ack 成功文件）、CollectorRun 状态（partial）与重启恢复——是中等风险行为变更，与 Phase 3A「不伪装成功」设计存在张力。
3. 遵守「禁止过度设计」「不做无关重构」。

**当前 all-or-nothing 已满足关键安全要求**：
- 平台失败不伪装成功（宁可整批失败）；
- 失败平台的 incoming 保留原位（不 ack、不删）；
- `_wait_for_results` 超时的 error_msg 含「已就绪任务」列表（明确记录哪些平台成功、哪些失败）；
- 下轮重试范围由 rejected manifest 的 `.reason` + `retry_incomplete` 精确界定。

## 四、若未来启用策略 2 的前置实现清单（本阶段未实施）

- 平台级状态（per-platform status）；
- 平台级 ack（只 ack 成功文件）；
- 平台级 retry（失败平台单独重试）；
- 平台级错误码（已具备 upstream_blocked 等分类）；
- 平台级统计（per-platform created/duplicate/failed）；
- 重启恢复（ack_pending 按 platform 恢复）；
- 幂等测试。
- 显式配置项（如 `bb_browser_partial_enabled=false`）作为启用开关。

## 五、明确记录（all-or-nothing 下的平台成功/失败追踪）

- 平台成功/失败：`_wait_for_results` 超时 error_msg 的 `已就绪任务=[(task_id, source_key), ...]` 列表；
- incoming 保留：失败任务的 incoming 一律保留原位，不删除不 ack；
- 下轮重试范围：rejected manifest 的 `.reason` 文件 + `recover_prior_runs`/`retry_incomplete` 精确重试未完成任务。
