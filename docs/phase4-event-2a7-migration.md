# Phase 4-Event-2A.7 正式生产迁移报告

> 执行授权：用户显式授权 `python -m scripts.migrate_events --force --allow-production`
> 范围：仅 Event 成员归属 rebuild；未执行 Event-2 Narrative backfill；未改阈值/窗口/API/前端/表结构。

## 1. 执行时间

- 开始时间：2026-07-22 14:29:06（北京时间，快照落盘时刻）
- 结束时间：2026-07-22 14:29:11（迁移完成、提交、传播重建与告警重链全部结束）
- 数据库：`opinion_db`（`127.0.0.1:5432`，经 `DATABASE_URL` 显式指向，非测试库）
- 执行命令：
  ```bash
  DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db' \
    python -m scripts.migrate_events --force --allow-production \
    --snapshot-dir "C:/Users/Administrator/Desktop/YQ/backend/_migration_snapshots"
  ```
- 退出码：`EXIT=0`

## 2. 最终 preflight（迁移前实时只读，唯一决策基准）

> 来源：迁移执行前当场重跑 `_fresh_preflight.py`，未复用任何旧 JSON。

- 当前 Event：**90**
- 当前 EventOpinion：**271**
- 当前 Opinion：**429**（全部 `completed`，全部位于 7 天窗口内）
- 当前 NOW / cutoff：2026-07-22T06:28:13Z / cutoff=2026-07-15T06:28:13Z
- 窗口内 Opinion：429
- 预测新 Event：**84**（单成员 **59** + 多成员 **25**）
- 预测 EventOpinion：**119**
- 预测未物化 Opinion：**310**（均为 `risk<40` 单条）
- 预测 disappear / retain / merge / split：**45 / 36 / 9 / 0**
- PropagationNode 数：**221**（迁移前）
- AlertRecord 数：**11**（9 条带旧 event_id）
- 预计需重链 AlertRecord：**9**
- 预计重建传播树 Event 数：**84**

与 2A.6 fresh preflight **完全一致，无异常**（Opinion 数未降、无窗口外 Opinion、无 orphan/重复关联、物化结果与 `compute_new_events` 一致）。

## 3. 实际迁移结果

| 对象 | 迁移前 | 迁移后（实际） | 预测 | 变化 |
|---|---|---|---|---|
| Event | 90 | **84** | 84 | −6 |
| EventOpinion | 271 | **119** | 119 | −152 |
| Opinion | 429 | **429** | 429 | +0（不被修改/删除） |
| 单成员 Event | — | 59 | 59 | — |
| 多成员 Event | — | 25 | 25 | — |
| 最大成员数 | — | 5 | 5 | — |

- 实际 Event 数 = 预测 84（一致）；`len(plans)==pf["predicted_event_count"]` 守卫通过。
- Opinion 总数不变，**没有任何 Opinion 因不再属于 Event 而被删除**（仅 `risk<40` 单条舆情失去 Event 关联，仍保留在 Opinion 表）。

## 4. EventOpinion 完整性（只读验收）

- orphan（event_id 或 opinion_id 不存在）：**0**
- duplicate（同 `(event_id, opinion_id)` 多行）：**0**
- count mismatch（Event.opinion_count 字段 ≠ 真实 links 数）：**0**
- 空壳 Event（opinion_count==0 或无 links）：**0**

## 5. Propagation 重建（逐 Event 可观测，禁止静默失败）

- 重建 Event 总数：**84**
- 成功：**84**
- 失败：**0**
- 状态：**all_succeeded**
- 失败详情：无
- 旧 Event → 新 Event **无 id 级确定性映射**；处理方式为：先 NULL 旧 `event_id/parent_id` → 新 Event 创建 → 按新 EventOpinion 调用 `rebuild_for_event` 重新生成传播结构（符合 §六 要求，未做 id 翻译）。
- 残留（**非失败**，属设计预期）：迁移前 221 个旧 `propagation_nodes` 的 `event_id/parent_id` 被置空，保留为「脱钩旧结构」；重建新生成 119 个有效节点（有效 `event_id`=119，NULL=221，`orphan_event_id`=0，无 FK 违例）。旧结构对事件作用域查询（`WHERE event_id=?`）不可见，不影响 UI/数据；快照已保留其迁移前完整状态，可作为恢复依据。建议后续以幂等 `DELETE FROM propagation_nodes WHERE event_id IS NULL` 清理（本次未执行，避免扩大迁移范围）。

## 6. AlertRecord 重链（按 opinion_id，禁止标题/旧 id 猜测）

- 总数：**11**
- 重链成功（event_id 回填新 Event）：**10**
- orphan（opinion_id 对应的 Opinion 未被物化为任何 Event）：**1**
  - id=19，opinion_id=200，原因 `opinion_not_in_any_event`（该 Opinion 为 `risk<40` 单条，按当前物化策略不建 Event → 正确保留为 orphan，**未静默丢失、未删除**）。
- 重链失败：**0**
- 重链依据：复用 `AlertService.sync_alert_events`，按 `AlertRecord.opinion_id` 确定性查找新 Event，**幂等、不产生重复 AlertRecord**。

## 7. Snapshot

- 创建是否成功：**是**（迁移 DELETE 之前落盘，迁移事务内，若失败则整体 rollback）
- 文件：`C:/Users/Administrator/Desktop/YQ/backend/_migration_snapshots/event_snapshot_20260722T062906.json`（184 KB）
- 包含表与行数：
  - `events`：**90**
  - `event_opinions`：**271**
  - `propagation_nodes`：**221**（含完整恢复字段 id/event_id/parent_id/opinion_id/source/title/publish_time/risk_score/…）
  - `alert_records`：**11**（含完整恢复字段 id/rule_id/opinion_id/event_id/event_title/handled/…）
- 文件是否可读：**是**（已用脚本校验 4 表齐全）

## 8. 回滚状态

- 是否发生 rollback：**否**（单一事务正常提交；一致性校验通过后才 commit）
- rollback 是否成功：N/A
- 是否需要恢复：**否**
- 恢复依据：快照文件已落盘，且迁移为单事务（已提交则数据完整），如需回退可凭快照 + 单事务边界重建旧状态。

## 9. 数据完整性最终结论

全部通过：

- Event 空壳：0；旧 Event 残留：0（当前 84 个 Event 的 id 与迁移前 90 个旧 id **无任何重叠**，证实旧 Event 已全量删除、新 Event 已全新生成）。
- EventOpinion orphan / duplicate / count-mismatch：均为 0。
- Opinion 表：429 不变，无删除。
- 物化规则正确：
  - `risk>=40` 的 67 条 Opinion **全部**归属于 Event（missing=0）；
  - `risk<40` 的 310 条单条舆情**按策略不物化**（预期行为，非数据丢失）；
  - 另有 52 条 `risk<40` 舆情因与高相似舆情聚类而被纳入多成员 Event（符合规则）；
  - 原大伪聚合已拆分（多成员 Event 最大成员数=5，无单事件过度吸附）。
- 传播树：84 个新 Event 全部重建成功（0 失败），FK orphan=0。
- first_time / last_time 与成员时间一致（基于 `_effective_time` = `publish_time or created_at`，mismatch=0）。

**唯一残留**：221 个 `event_id` 为 NULL 的脱钩旧 `propagation_nodes`（无 FK 违例、对事件作用域不可见、快照可还原），建议后续独立清理。

## 10. Event-2 后续状态

- Event-2 Narrative backfill：**未执行**（本阶段仅执行 Event 成员归属 rebuild，符合 §九 默认顺序 Phase A→B→C，未混为高不可拆分操作）。
- 当前状态：Event 成员归属已正确修复，可为 Event-2 提供准确的 `EventOpinion` 基础。
- 后续建议顺序：Phase B（本验收）→ **Phase C：单独执行 Event-2 Narrative backfill**（若 Event-2 需新增列，须先以向后兼容 migration 添加，不与成员重建耦合）。

## 11. 最终判定

# ✅ SUCCESS

依据：
- 预测与实际 Event 数一致（84=84），`compute_new_events` 同源；
- 无 Event 空壳、无旧 Event 残留、无 orphan/重复关联、无 count 不一致；
- Opinion 表零改动；
- 物化策略正确落地（高风险全物化、低风险单条预期不物化）；
- 传播树重建 **all_succeeded**（0 失败）；
- 告警按 `opinion_id` 重链 10 条、1 条 orphan 显式记录（非丢失）；
- 快照完整落盘，事务边界正确，未发生 rollback。

**未扩大范围**：未执行 Event-2、未改阈值/窗口/API/前端/表结构、未做额外 SQL。

**建议后续（非本阶段必做）**：清理 221 个脱钩旧 `propagation_nodes`（`DELETE FROM propagation_nodes WHERE event_id IS NULL`，幂等，须另行授权）。
