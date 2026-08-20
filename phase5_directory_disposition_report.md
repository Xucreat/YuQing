# Phase 5 阶段五：历史 incoming 处置报告

生成时间：2026-08-19 16:06

## 结论先行

已实现 dry-run 默认的 incoming 处置工具（`backend/scripts/phase5_incoming_disposition.py`），**本阶段未执行任何移动/删除**（未传 `--apply`）。287 个历史文件保持原位。11 个测试全绿。

## 一、工具能力

| 能力 | 实现 |
|------|------|
| 默认 dry-run | ✅ 未传 `--apply` 仅输出建议，不移动 |
| 显式 `--apply` 才移动 | ✅ `--apply` + `--target` + `--audit` |
| 每批 ≤ 10 文件 | ✅ `--max-batch`（默认 10，超限拒绝） |
| SHA256 校验 | ✅ 移动前校验，不匹配拒绝 |
| 目标存在拒绝覆盖 | ✅ 拒绝并回滚 |
| 中途失败回滚 | ✅ 已移动文件逆序回滚 |
| 审计 JSON | ✅ 记录 source/target/sha256/category/reason |
| 禁止 ack failed run | ✅ failed → manual_review（不自动 ack） |
| 禁止 ack orphan | ✅ orphan → quarantine_candidate（不自动 ack） |
| weibo/xhs 单独标记 | ✅ → weibo_do_not_touch（禁止自动处理） |

## 二、分类规则（核心纯函数 `classify_file`）

| 类别 | 触发条件 | 处置建议 |
|------|---------|---------|
| `keep` | run status ∈ success/partial | 保留原位（理论上应已 ack，需人工核对） |
| `manual_review` | run status = failed | 需人工决定是否补录（禁止自动 ack） |
| `quarantine_candidate` | 无对应 CollectorRun | 可在人工确认后 quarantine/archive |
| `weibo_do_not_touch` | source_key ∈ weibo/xhs/m_weibo/xiaohongshu | 禁止自动处理，单独标记 |

## 三、287 个 incoming 的实际分类（基于 Phase 4B 对账）

| 类别 | 数量 | 说明 |
|------|------|------|
| `manual_review`（失败任务产物） | 256 | d5caf173(128)/0b41b983(112)/0b637f17(8)/6a6c7f2e(8)，run=failed |
| `quarantine_candidate`（孤立文件） | 30 | manifest-3154428464654(20) + landing-8platform 非 weibo(10) |
| `weibo_do_not_touch` | 1 | landing-8platform 的 weibo 文件 |

> 精确数量以工具 dry-run 输出为准（本报告为 Phase 4B 对账推算）。

## 四、测试结果

11 passed / 0 failed（真实退出码 0）：dry-run 不移动 / 超批拒绝 / SHA256 不匹配拒绝 / 目标存在拒绝 / 移动校验 / 禁止/keep 不动 / 中途回滚 / 分类纯函数（failed/orphan/weibo/success）/ build_plan 分类。

## 五、未执行

- 未执行任何 `--apply`（未移动、未删除任何文件）。
- 未对 failed run / orphan / weibo 文件做任何 ack 或处理。
