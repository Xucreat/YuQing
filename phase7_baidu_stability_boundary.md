# Phase 7 阶段六：百度稳定性边界

生成时间：2026-08-19 17:17

## 结论先行

**百度只有错误分类 + 退避/冷却计算函数，没有真实持久化熔断状态机。** 保持 all-or-nothing，本阶段不实现 partial success 或完整熔断。

## 已实现

| 项 | 位置 |
|----|------|
| `upstream_blocked` 错误分类 | `classify_adapter_error` |
| `Failed to fetch` → upstream_blocked | 同上 |
| backoff 计算 | `compute_backoff_delay` |
| cooldown 计算 | `in_cooldown` |
| 配置项（max_attempts/backoff/cooldown/threshold/recovery） | `config.py` |

## 未实现

| 项 | 说明 |
|----|------|
| 连续失败持久化 | 无 |
| 跨进程状态 | 无 |
| circuit open / half-open / closed | 无 |
| scheduler 实际跳过百度 | 无（all-or-nothing 下无法跳过单平台） |
| 平台级 partial | 无 |
| 平台级 ack/retry | 无 |

## 决策

除非用户明确要求，本阶段不实现 partial success 或完整熔断（遵守「不做无关重构」「不得让百度失败伪装成成功」）。
