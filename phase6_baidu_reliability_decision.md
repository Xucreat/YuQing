# Phase 6 阶段五：百度退避/熔断边界确认

生成时间：2026-08-19 16:38

## 结论先行

**当前仅具备计算函数，不具备实际熔断。** 保持 all-or-nothing 默认行为不变，不擅自实现 partial success 或完整熔断状态机。

## A. 已实现（Phase 5 阶段四）

| 项 | 位置 |
|----|------|
| `upstream_blocked` 错误分类 | `bb_browser_runtime.classify_adapter_error` |
| backoff 延迟计算 | `compute_backoff_delay(attempt, base, max)` |
| cooldown 时间判断 | `in_cooldown(blocked_at_ts, now_ts, cooldown_seconds)` |
| 配置项 | `baidu_max_attempts/backoff_seconds/cooldown_seconds/circuit_breaker_threshold/circuit_breaker_recovery_seconds` |

## B. 未实现

| 项 | 说明 |
|----|------|
| 连续失败计数 | 无持久化计数 |
| 跨进程持久化 | 无 |
| 熔断打开（circuit open） | 无 |
| 熔断恢复 | 无 |
| scheduler 实际跳过百度 | 无（all-or-nothing 下无法跳过单平台） |
| 平台级降级 | 无（需 partial success） |
| 平台级 ack | 无（需 partial success） |

## 决策

**保持现状，不实现完整熔断。** 理由：

1. 完整熔断需要「失败平台不影响其他平台」→ 依赖 platform-level partial（Phase 5 阶段三已决策保持 all-or-nothing）。
2. 完整熔断需跨进程持久化状态 + 平台级重试，属中等风险行为变更。
3. 遵守「禁止过度设计」「不做无关重构」「不得让百度失败伪装成成功」。

## 明确标记

- **仅具备计算函数（`compute_backoff_delay`/`in_cooldown`），不具备实际熔断。**
- 百度 `Failed to fetch` 持续归类 `upstream_blocked`（不伪装成功）。
- 若未来实现完整熔断，前置条件：partial success 落地 + 持久化状态 + 恢复时间 + 明确测试 + 默认关闭。
