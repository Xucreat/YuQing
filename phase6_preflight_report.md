# Phase 6 阶段一：生产启用前只读复核

生成时间：2026-08-19 16:27

## 结论先行

确认 Phase 5 存在 **2 个核心缺陷**（本阶段目标即修复它们）：
1. `load_run_status()` 无条件返回空字典，导致失败文件被误判为孤立文件；
2. `--apply` 会移动 `manual_review`（失败任务产物），违反"manual_review 默认保留原位"。

source 62/40 状态未变，incoming 数量 287 与 Phase 5 一致。

## 一、数据源状态

| 源 | enabled | schedule_enabled | 说明 |
|----|---------|------------------|------|
| #62 bb_browser | true | **false** | collection_mode=national，五平台 |
| #40 weibo_mediacrawler | true | true | 既有状态，未改动 |

## 二、调度关系

| 问题 | 答案 |
|------|------|
| 全局 scheduler 是否仍调度 source 40 | **是**（source 40 enabled+schedule_enabled=true，且 due_scheduled_sources 不排除 weibo_mediacrawler） |
| bb-browser lane 是否调度 source 40 | **否**（allowlist 严格 = {"bb_browser"}） |

## 三、incoming 处置工具缺陷（本阶段修复目标）

### 缺陷 1：`load_run_status()` 空返回

`load_run_status()` 无条件 `return {}`，导致 `build_plan` 中所有文件的 `run_status=None` → 全部被 `classify_file` 判为 `orphan` → `quarantine_candidate`。**实际是「映射不可用」，不是真的孤立文件**。失败任务产物（256 个）因此被误判为可归档。

### 缺陷 2：`--apply` 移动 manual_review

`apply_plan` 第 96 行 `actions = [a for a in plan if a["category"] in (CATEGORY_QUARANTINE, CATEGORY_MANUAL_REVIEW)]` —— **manual_review 会被 `--apply` 批量移动**，违反「manual_review 默认只能保留原位」「禁止隐式全量 apply」。

## 四、incoming 数量

当前 287，与 Phase 5 报告一致（256 失败 + 30 孤立 + 1 weibo）。

## 五、结论

两个缺陷必须在第二阶段、第三阶段修复，否则：
- 失败文件可能被误当孤立文件归档；
- `--apply` 可能批量移动本应人工对账的失败任务产物。

详见 `phase6_directory_tool_fix_report.md`（阶段二）与 `phase6_scheduler_gate_report.md`（阶段三）。
