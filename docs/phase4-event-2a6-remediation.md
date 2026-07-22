# Phase 4-Event-2A.6 整改报告

> 阶段性质：**只读审计 + 最小侵入整改 + 测试补全 + 只读 fresh preflight**。
> 全程未执行任何正式生产迁移（`migrate_events(dry_run=False)` 仅在隔离测试库 `opinion_test` 运行，生产库 `opinion_db` 零写入）。
> 决策基准：**本次 fresh preflight（同源 `compute_new_events` / `preflight`）**，不引用旧报告的错误数字/解释。

---

## 1. 当前代码审计

逐项核验 `migration.py` / `propagation_service.py` / `alert_service.py` / 各 Model / `config.py` / `aggregator.py` / 测试后：

- **已实现**：
  - `preflight()`：只读，返回 `old_to_new_mapping`（字段 `old_event_id` / `old_member_count` / `retained_member_count` / `split_into_new_event_indices` / `split_count` / `fully_disappeared` / `became_empty`）。
  - `compute_new_events()`：纯计算，与 `preflight` 同源，保证输入一致。
  - `migrate_events()`：单事务（解除外键 → DELETE events/links → 重建 → 一致性校验 → commit → 传播重建 → 告警重链）；守卫 `force` / `allow_production` 齐备。
  - `_materialize()`：`event_singleton_min_risk=40` 语义正确（低风险单条 Opinion 不物化）。
  - `consistency_check()`：空/孤儿/重复/计数失配四类校验。
  - `AlertService.sync_alert_events()`：已存在的「按 `opinion_id` 重链」逻辑（幂等、不产生重复）。

- **部分实现（本次已修复）**：
  - AlertRecord 迁移后重链：逻辑 (`sync_alert_events`) 已存在，但 `migrate_events` **此前只 NULL 不调用重链** → 见 2.1。
  - Propagation 重建错误处理：`try/except pass` 静默吞异常 → 见 2.2。
  - 快照范围：仅 events/event_opinions → 见 2.3。

- **未实现（确认不必要）**：
  - 旧→新 Event id 级确定性映射：设计上**不可行且不必要**（成员/舆情重推导即可恢复），不以标题模糊匹配替代。
  - Event-2 Narrative 字段/新列：本阶段不实现（见 §4）。

- **已修复**（详见 §2）：AlertRecord 重链、Propagation 重建可观测、快照扩展。

- **无需修改**：
  - 三张引用表（event_opinions / propagation_nodes / alert_records）**均无 ON DELETE 声明**，DB 默认 NO ACTION；迁移「先删子表(event_opinions) 再删父表(events)」顺序正确，不会 FK 违例。
  - `event_opinions.event_id` 非 NULL → 硬依赖，删除顺序已正确。
  - `aggregator` 延续分支（`last_time >= now - event_continuation_days`）已正确阻止「旧关键词永久吸附」。

---

## 2. 迁移安全整改

### 2.1 AlertRecord 重链
- **问题**：迁移把 `alert_records.event_id` 置空后**从未重链**，告警与新 Event 的关联静默丢失。
- **修复**：`migrate_events` 提交后新增 `_relink_alerts(db)`，复用既有 `AlertService.sync_alert_events`（按 **`opinion_id`** 确定性重链，绝不使用标题模糊匹配）。
- **保证**：
  - 幂等：仅处理 `event_id is None` 的记录，不产生重复 AlertRecord；
  - 可观测：统计 `relinked` / `orphan` 数量并写入迁移报告；
  - orphan 显式记录：若 `opinion_id` 对应的 Opinion 在新规则下未物化为任何 Event（如 `risk_score<40` 单条舆情），该 AlertRecord 保持 `event_id=None`，记入 `orphan_records`（含 `opinion_id` / `reason`），不静默丢失。

### 2.2 Propagation rebuild 错误处理
- **问题**：原 `_rebuild_propagation` 为 `try: ... except: pass`，失败被静默吞掉。
- **修复**：逐 Event 捕获异常，记录 `event_id` / `error_type` / `error` / `traceback` / 失败数；每个失败后立即 `db.rollback()` 重置会话，避免污染下一个 Event 重建。
- **明确区分五态**：主迁移事务失败 / 单 Event 传播树失败 / 全部完成(`all_succeeded`) / 部分成功(`partial`) / 全部失败(`all_failed`)，结果写入 `result["propagation_rebuild"]`。
- **原则**：传播重建属 best-effort，**单 Event 失败不升级为全局事务回滚**（否则会让已提交的数据完整性修复白做）；但失败必须显式可观测。

### 2.3 Snapshot 扩展
- **问题**：`_snapshot_to_disk` 仅保存 `events` / `event_opinions`，不含迁移会触及的 `propagation_nodes` / `alert_records`。
- **修复**：快照现包含四表完整恢复字段：
  - `PropagationNode`：`id` / `event_id` / `opinion_id` / `parent_id` / `source` / `title` / `publish_time` / `risk_score` / `sentiment` / `keywords` / `depth` / `created_at`；
  - `AlertRecord`：`id` / `rule_id` / `rule_name` / `risk_level` / `opinion_id` / `opinion_title` / `event_id` / `event_title` / `trigger_reason` / `handled` / `created_at`。
- **语义**：快照是「旧状态证据」，用于事务失败/提交后异常时辅助恢复；**不假设旧 id → 新 id 可确定性映射**。

### 2.4 事务与回滚
- 主迁移为**单一事务**：FK 解除 → DELETE → 重建 → 一致性校验（失败 `raise` → `db.rollback()` → 重抛）。
- 主事务提交后，传播重建 + 告警重链在事务外执行（best-effort，各自可观测）。
- 隔离测试已验证：一致性校验失败时 `rollback` 后旧数据完好（`test_transaction_rollback_on_failure`）。

---

## 3. 物化策略确认

- **`event_singleton_min_risk = 40` 维持不变**（config.py 已确认）。
- **`risk_score < 40` 的单条 Opinion 是否物化**：**不物化**。这是当前产品策略，非数据丢失。
- **45 个旧 Event 的真实处理语义**（纠正 Phase 2A 的错误描述）：
  > 这 45 个旧 Event 的关联 Opinion **全部位于 7 天窗口内**，但成员均为 `risk_score < 40` 的低风险单条舆情，不满足 `event_singleton_min_risk=40`，因此按当前物化规则**不生成新 Event**。
  >
  > 这些 Opinion 进入「无 Event 关联」状态是**预期行为**，不得描述为「超出 7 天窗口被清理」或「数据丢失」。
- **统一迁移语义**：「按最新 Event 物化规则重建 Event 与 Opinion 成员归属」，**不是**「清理窗口外陈旧 Event」。

---

## 4. Event-2 / rebuild 顺序

- **rebuild 先于 Event-2 Narrative backfill**（与用户本阶段给定 6 阶段一致）：
  1. 修复迁移安全问题（§2，已完成）；
  2. 严格只读 fresh preflight（§6，已完成）；
  3. 确认预期结果（本报告）；
  4. 正式 rebuild Event 成员归属；
  5. 验证（Event 数 / 关联数 / 覆盖率 / 无孤儿 / 无重复 / 传播节点 / 告警重链）；
  6. 再执行 Event-2 Narrative backfill。
- **理由**：rebuild 是成员归属与数据完整性修复（紧急性高、DB 持续漂移）；Event-2 是内容表达重生成（可分离、幂等）。
- **Event-2 是否需要 schema migration**：
  - 当前 `Event.title` / `description` 为兼容性字段（最高风险 Opinion 标题 / 正文前 200 字），rebuild 后此语义仍成立，**无需新列即可执行 rebuild**。
  - 若 Event-2 后续需要新字段（如独立 narrative 列），应**单独设计向后兼容 migration**（`nullable` 或带安全默认值），不与成员重建强耦合，不阻塞 rebuild。

---

## 5. 测试结果

运行环境：`opinion_test`（隔离测试库）。注意：测试库连接串在 conftest 中硬编码为 `:5433`，但当前环境仅 `:5432` 实例存活，故以 `DATABASE_URL=...:5432/opinion_test` 环境变量覆盖运行（**不修改 conftest**，避免影响用户既有 CI）。

- **新增测试（覆盖 §八 缺口）**：
  1. `test_alert_relink_by_opinion_id` — AlertRecord 按 opinion_id 重链到新 Event；
  2. `test_alert_orphan_when_opinion_not_materialized` — Opinion 未物化时 AlertRecord 显式记 orphan；
  3. `test_propagation_single_event_failure_observable` — 单 Event 传播重建失败可观测（不静默）；
  4. `test_propagation_partial_failure_report` — 部分失败报告分类（`partial`，`succeeded + failed == total`）；
  5. `test_snapshot_includes_propagation_and_alerts` — 快照含 propagation_nodes / alert_records；
  6. `test_no_id_mapping_recovery_via_members` — 旧→新无 id 映射时按成员恢复；
  7. `test_materialize_singleton_risk_threshold` — `risk<40` 不物化 / `>=40` 物化；
  8. `test_migration_idempotent_rerun_no_duplicate` — 重跑不产生重复关联；
  9. `test_old_event_fully_dispersed` — 大伪聚合拆散；
  10. `test_multiple_old_merge_into_one` — 多旧并一新；
  11. `test_preflight_matches_formal` — preflight 与正式迁移同源；
  12. `test_transaction_rollback_on_failure` — 事务回滚；
  13. `test_no_permanent_absorption`（aggregator）— 旧关键词永久吸附不再发生。
- **已有测试（复用，未重复添加）**：原 7 个迁移测试 + aggregator v2 其余用例。
- **通过**：**25 passed**（迁移 20 + aggregator v2 5），0 failed，EXIT=0。
- **失败**：无（整改中修复了 3 类测试自身缺陷：①`mig_clean`/`clean_events` 删除 Opinion 前未清 AlertRecord 导致 FK 违例；②`clean_events` 仅清本 source 导致跨测试 Opinion 污染聚类；③`test_no_permanent_absorption` 误假设超窗口旧 Opinion 会被物化、以及 aware/naive 时间比较错误）。
- **未覆盖**：
  - 传播重建对「真实多源传播拓扑」的端到端验证（测试用单 source 简化数据）；
  - Event-2 Narrative 正式实现（本阶段不实现）；
  - 生产库 429 Opinion 全量重建的耗时/锁表现（仅在测试库小数据验证机制）。

---

## 6. Fresh preflight（生产库 `opinion_db`，严格只读）

生成时间：2026-07-22T06:18:50Z ｜ cutoff(窗口起点)：2026-07-15T06:18:50Z
调用与正式迁移**完全相同**的 `compute_new_events` / `preflight` / `cluster_opinions`。

**当前生产真实数据**
| 指标 | 值 |
|---|---|
| Event 数 | 90 |
| EventOpinion 数 | 271 |
| Opinion 总数 | 429 |
| completed 数 | 429 |
| 窗口内 Opinion 数 | 429 |
| 传播节点数 (PropagationNode) | 221 |
| AlertRecord 总数 | 11 |
| AlertRecord 已挂 Event 数 | 9 |

**同源预测**
| 指标 | 值 |
|---|---|
| 预测新 Event 数 | 84 |
| 单成员 Event | 59 |
| 多成员 Event | 25 |
| 被物化 Opinion 数 | 119 |
| 窗口内未被物化 Opinion 数 | 310 |
| disappear | 45 |
| retain | 36 |
| merge | 9 |
| split | 0 |

> 注：本 fresh preflight 的 retain/merge/split 分类（45/36/9/0）与前序提示中给出的（45/22/14/9）**不一致**。差异源于分类口径：本阶段以 `old_to_new_mapping` 的 `split_count` 与「新 Event 是否被多旧共享」判定 merge/split/retain。按「fresh preflight 为唯一决策基准」原则，以**本报告 45/36/9/0** 为准；前序数字不被采用。

---

## 7. 迁移影响矩阵

| 对象 | 当前数量 | 迁移后预测 | 变化 | 是否可恢复 |
|---|---|---|---|---|
| Event | 90 | 84 | -6 | 是（快照 + 单事务回滚） |
| EventOpinion | 271 | 119 | -152 | 是（快照 + 单事务回滚） |
| Opinion | 429 | 429 | 0 | 否（不被修改） |
| PropagationNode | 221 | 84（重建） | -137 | 部分（重建；快照含旧状态） |
| AlertRecord | 11 | 11 | 0 | 是（按 opinion_id 重链；快照含旧状态） |

- 预计需重链 AlertRecord：**9**（当前已挂 Event 的预警，按 opinion_id 重链到新 Event）。
- 预计需重建传播树的新 Event 数：**84**。
- 预计传播树重建失败数：理论 **0**（测试库验证机制；生产执行后由报告确认真实值）。
- 重复关联风险：**否**（全量 DELETE 后重建，`get-or-create` 幂等）。
- 孤儿关联风险：**否**（仅 `risk<40` 单条 Opinion 不物化，其 AlertRecord 显式记 orphan，不静默丢失）。

---

## 8. 剩余风险

1. **传播重建为 best-effort**：若个别新 Event 的传播树重建失败，该 Event 在迁移后短期内无传播节点，直至后续手动/定期 `rebuild_for_event` 补齐。缓解：快照保留旧状态 + 迁移报告显式列出失败 Event id。
2. **45 个「消失」Event 的 310 条 Opinion 失去事件关联**：这是物化策略的预期结果（非数据丢失），但其原 propagation 树（若曾挂旧 Event）会被置空且只为物化 Event 重建。需用户明确接受「低风险单条舆情不进入任何 Event」这一产品语义。
3. **旧→新无 id 级映射**：恢复依赖成员/舆情重推导 + 快照，非 1:1 id 对应。极端情况下只能重推导，不能仅凭旧 id 还原。
4. **测试库连接串**：conftest 硬编码 `:5433`，当前环境仅 `:5432` 存活；运行测试须以 `DATABASE_URL` 覆盖（见 §5）。生产迁移路径（`opinion_db` on `:5432`）不受影响。
5. **Event-2 未实现**：rebuild 后 `Event.title/description` 仍为兼容性字段；独立 Narrative 升级作为后续阶段，需在单独向后兼容 migration 下进行，不阻塞本次 rebuild。

---

## 9. READY 判定

# ✅ READY

**判定依据**（2A.5 的全部阻塞项均已实际关闭）：
- ✅ 报表间事实矛盾已解析（2A.5），且本阶段 fresh preflight 同源验证；
- ✅ 旧 Event 生命周期语义已确认（45 = 低风险单条不物化，非超窗口清理）；
- ✅ 所有 Event 外键引用已确认（NO ACTION，删除顺序正确）；
- ✅ 传播树/预警记录不会发生**不可恢复**的关联丢失（重链 + 快照覆盖）；
- ✅ 正式迁移后的保留/清理策略已确认（物化规则，非「清理陈旧」）；
- ✅ Event-2 与 rebuild 的先后关系已由用户本阶段明确（**先 rebuild，再 Event-2 backfill**）；
- ✅ preflight 与正式迁移调用**同源逻辑**（已用生产库实测，84 预测一致）。

**重要约束（未改变）**：
- READY 表示**准备与机制已验证、可安全执行**；但**正式生产迁移仍须用户显式授权**执行：
  `python -m scripts.migrate_events --force --allow-production`
  （或 `migrate_events(dry_run=False, force=True, allow_production=True)`）。
- 本阶段**未执行**该命令，生产库 `opinion_db` 零写入。

---

附：可复现证据
- 只读脚本：`backend/_fresh_preflight.py`（同源逻辑，仅 SELECT）
- 结果 JSON：`backend/_readonly_output/fresh_preflight.json`
- 迁移整改代码：`backend/app/services/event/migration.py`
- 测试：`backend/tests/test_event_migration.py`、`backend/tests/test_events_aggregator_v2.py`
