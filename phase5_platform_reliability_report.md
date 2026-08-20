# Phase 5 阶段四：百度平台级稳定性报告

生成时间：2026-08-19 16:03

## 结论先行

保持 all-or-nothing（当前设计无法安全支持平台级降级）。新增**可配置退避参数**与**退避/冷却纯函数**（可复用、可测试），百度 `Failed to fetch` 继续归类 `upstream_blocked`（Phase 4C 已落地）。未实现完整熔断状态机（需 partial 语义支持，见阶段三决策）。

## 一、审计结论

| 保护项 | 现状 | 判定 |
|--------|------|------|
| 平台级超时 | 全局 `timeout_seconds=240` 兜底（非无限等待） | ✅ 已保护 |
| upstream_blocked 分类 | Phase 4C 已补全（Failed to fetch/安全验证→upstream_blocked） | ✅ |
| 冷却窗口 | 新增 `in_cooldown` 纯函数 + `baidu_cooldown_seconds` 配置 | ✅ 计算逻辑就绪 |
| 有限重试 | 新增 `baidu_max_attempts` 配置 + `compute_backoff_delay` | ✅ 计算逻辑就绪 |
| 指数退避 | `compute_backoff_delay`（base*2^(n-1)，上限） | ✅ |
| 失败平台不影响其他平台 | all-or-nothing 下**无法实现**（需 partial） | ⚠️ 保持 all-or-nothing |
| 连续失败熔断 | `baidu_circuit_breaker_threshold`/`recovery_seconds` 已配置，状态机未实现 | ⚠️ 需 partial |
| 熔断可观察/可恢复 | 未实现（依赖熔断状态机） | ⚠️ 待 partial |

## 二、本次实现（最小保护）

文件：`app/core/config.py` + `app/collectors/bb_browser_runtime.py`

新增可配置参数（保守默认）：
| 参数 | 默认 | 含义 |
|------|------|------|
| `baidu_max_attempts` | 3 | 单轮最大重试次数 |
| `baidu_backoff_seconds` | 60 | 指数退避基数（秒） |
| `baidu_cooldown_seconds` | 600 | 上游阻断冷却窗口（10 分钟） |
| `baidu_circuit_breaker_threshold` | 5 | 连续 upstream_blocked 熔断阈值 |
| `baidu_circuit_breaker_recovery_seconds` | 3600 | 熔断自动恢复（1 小时） |

新增纯函数（`bb_browser_runtime.py`）：
- `compute_backoff_delay(attempt, base, max)`：指数退避，`base*2^(attempt-1)`，上限 max。
- `in_cooldown(blocked_at_ts, now_ts, cooldown_seconds)`：冷却窗口判断。

测试：`tests/test_phase5_baidu_stability.py`（7 用例）+ 回归 `test_phase4_platform_reliability.py`，共 15 passed。

## 三、为何不实现完整熔断状态机

1. 熔断/降级需要「失败平台不影响其他平台」→ 依赖 platform-level partial（阶段三已决策保持 all-or-nothing）。
2. 完整熔断需跨进程持久化状态 + 平台级重试，属中等风险行为变更。
3. 遵守「禁止过度设计」「不做无关重构」。

## 四、明确记录（all-or-nothing 下的失败追踪）

- **哪些平台成功/失败**：`_wait_for_results` 超时 error_msg 的 `已就绪任务=[(task_id, source_key), ...]`。
- **哪些 incoming 保留**：失败任务 incoming 保留原位，不 ack 不删。
- **下轮重试范围**：rejected manifest `.reason` + `retry_incomplete` 精确重试未完成 (task_id, source_key)。

## 五、当前不存在「立即高频重试」的实际风险

source 62 `schedule_enabled=false`（未开启自动调度），百度不会被动高频重试。上述退避/冷却参数与纯函数是为「未来开启自动调度 + 若实现 partial」预留的可复用基础。
