# Phase 4C 平台级稳定性审计报告

生成时间：2026-08-19 15:25

## 结论先行

- **已修复**：`classify_adapter_error` 补全平台级错误分类（新增 `upstream_blocked`/`invalid_manifest`/`unknown_error`），百度风控 `Failed to fetch` 现可被准确归类，不再笼统记为 `adapter_error`。
- **现状已满足**：全局 `timeout_seconds=240` 兜底（不允许无限等待）+ all-or-nothing（不伪装成功）+ 空结果检测（`ERR_EMPTY_RESULT`）。
- **未实施（增强项，需用户确认）**：partial success（平台级降级）与百度退避。详见下文。

---

## 一、六类故障审计

| 故障类型 | 现有保护 | 判定 |
|---------|---------|------|
| TypeError: Failed to fetch（百度风控） | 原归 `adapter_error`，无法区分 | ⚠️ 已修复 → `upstream_blocked` |
| timeout | `_wait_for_results` 全局 240s 超时抛 `ERR_TIMEOUT` | ✅ 已保护（非无限等待） |
| 401/403/login_required | `classify_adapter_error` 识别 → `login_required` | ✅ 已保护 |
| adapter 返回空结果 | fetch 末尾 `if not items: raise ERR_EMPTY_RESULT` | ✅ 已保护 |
| 页面成功但结构空 | `normalize_record` 返回空 → 最终 `ERR_EMPTY_RESULT` | ✅ 已保护 |
| 单平台失败拖垮整批 | `_wait_for_results` all-or-nothing，单平台缺失→整批超时 | ⚠️ 存在（见下） |

## 二、单平台失败拖垮整批（已确认存在，未改）

现状：`_wait_for_results` 要求**全部**期望任务就绪，任一平台失败/慢 → 240s 超时 → 整批 failed。`fetch` 逐条解析时单文件 error 也直接 raise。

后果（#21248 现场）：42 关键词 × 3 平台 + 2 热榜 = 128 任务，youtube 慢导致整批超时，尽管 **baidu 42 个已全部成功产出**。

**为什么不改**：改为 partial success（平台级降级）需要：
1. `_wait_for_results` 检测 worker 的 reject 信号（manifest 移入 rejected + .reason）；
2. fetch 对失败平台降级而非 raise；
3. ack 语义调整（partial 时只 ack 成功文件）；
4. CollectorRun 增加 partial 状态与 per-platform 明细。

这是**行为变更**，与 Phase 3A 的 all-or-nothing「不伪装成功」设计存在张力，且涉及 ack/状态连锁影响，风险中等。按「不做无关重构」「禁止过度设计」原则，**标记为需用户确认的增强项，本阶段未实施**。当前 all-or-nothing 已满足验收条件 E（平台级 timeout/登录失败/风控不会造成伪成功——宁可整批失败）。

## 三、百度退避（未实施，需确认）

现状：无退避/冷却机制。scheduler 下一轮会立即重试百度。

建议（若实施）：在 control_root 写 `baidu_cooldown.json` 记录上次 `upstream_blocked` 时间，冷却窗口内跳过百度（不触发高频风控）。但「跳过百度」本质也是 partial success 的一部分，故与上节一并留待确认。

## 四、本次实际改动

文件：`backend/app/collectors/bb_browser_runtime.py`
- 新增常量 `ERR_UPSTREAM_BLOCKED` / `ERR_INVALID_MANIFEST` / `ERR_UNKNOWN_ERROR`。
- `classify_adapter_error` 分类顺序：login_required → adapter_missing → upstream_blocked → invalid_manifest → adapter_error → unknown_error（保留 adapter_error 兜底语义，不破坏既有测试）。

测试：`tests/test_phase4_platform_reliability.py`（8 用例）+ 回归 `test_phase2_recovery.py`，共 17 passed。

## 五、per-platform 指标可追踪性

现状：fetch 内有 `per_platform` 计数，但仅写日志；CollectorRun 无 per-platform 明细字段。验收 G 要求「每轮平台级指标和错误码可追踪」——当前通过 error_msg（含平台名+错误码）+ 日志满足基本追踪，但**无结构化 per-platform 明细**。若需结构化，属增强项（需 DB 字段/JSONB），留待确认。
