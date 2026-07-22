# Phase 4-Event-2A.5 生产 Rebuild 终检与迁移就绪评审

> 角色：后端工程师 + 数据迁移工程师 + 舆情事件建模评审
> 阶段性质：**严格只读**。本阶段仅对生产库 `opinion_db` 执行 `SELECT`，
> 未执行任何 `INSERT / UPDATE / DELETE / TRUNCATE / DROP`，未修改任何代码、表结构、API contract、前端。
> 生产数据库数据零改动；**未执行正式 `migrate_events(dry_run=False)`**。
>
> 核查时间（NOW/UTC）：`2026-07-22T05:39Z`，聚合窗口 cutoff：`2026-07-15T05:39Z`（event_window_days=7）。
> 证据文件（均由只读脚本落盘，可复现）：
> `backend/_readonly_audit.json`、`backend/_readonly_extra.json`、`backend/_event_table.md`。

---

## 1. 事实矛盾核验结果（Phase 1.5 ⇄ Phase 2A）

### 1.1 两条被指矛盾的旧结论

| 来源 | 原结论 |
|---|---|
| Phase 4-Event-1.5（§2） | “70 个旧 Event **全部**在 7 天窗口内，陈旧旧 Event = **0**。” |
| Phase 4-Event-2A（§6 注） | “45 个旧 Event 完全消失/变空，**是因为所有成员超出 7 天聚合窗口**。” |

两条结论若指同一时刻的同一批数据，则互斥（一边说“全在窗口内”，一边说“45 个成员超窗口”）。

### 1.2 真实 SQL 核验（当前生产库，实测）

| 核验项（真实 SQL） | 值 | 说明 |
|---|---|---|
| 当前生产 Event 总数 | **90**（非 70） | 数据库自 1.5/2A 后已漂移 |
| 当前 event_opinions 关联数 | **271**（非 220） | 同上 |
| opinions 总数 / completed 数 | 429 / 429 | 100% 已完成 |
| opinions `created_at` 范围 | **2026-07-20 04:28 → 2026-07-22 09:01** | **全部落在 7 天窗口内** |
| 按 `Event.last_time ≥ cutoff` 判“活跃” | 74 | 1.5 口径 |
| 按“≥1 个 linked opinion（`created_at≥cutoff` 且 completed）”判“保留” | **90** | 2A 迁移口径 |
| 两种口径不一致的事件数 | **16** | 关键矛盾指标 |
| `stored opinion_count` ≠ 实际关联数的事件 | **0** | 当前无孤儿关联 |

### 1.3 45 个“消失”事件的真实根因（决定性证据）

对 preflight 判为 `fully_disappeared` 的 **45 个旧 Event** 逐一核查其关联 Opinion：

| 指标 | 实测 |
|---|---|
| 45 事件关联 Opinion 总数 | 52 |
| 其中 `completed` 且 `created_at ≥ cutoff`（即在窗口内） | **52 / 52（100%）** |
| 其中 `created_at < cutoff`（超窗口） | **0** |
| 52 条 Opinion 的 `risk_score` 分布 | **全部 1–39（low1-39）** |
| 含任意 `risk_score ≥ 40` 成员的消失事件数 | **0** |
| 单成员消失事件数 | 41 / 45 |

**结论（基于真实数据，禁止推测）：**

1. **Phase 2A 关于“45 个旧 Event 消失是因为成员超出 7 天窗口”的解释是错误的。**
   实测 45 个消失事件的 52 条关联 Opinion **100% 都在 7 天窗口内**（created_at 全部落在 2026-07-20~22，而报告期 cutoff 为 2026-07-15，显然在窗口内）。它们“消失”的真实原因是：**其成员全部是 `risk_score < 40` 的低风险单条舆情，未达新规则的物化阈值 `event_singleton_min_risk=40`，因此不被构建为任何新 Event**。这是**物化阈值策略**导致的排除，与“时间窗口过期”无关。

2. **Phase 1.5 与 2A 的“矛盾”本质是两层错配，而非数据损坏：**
   - （a）**口径错配**：1.5 用 `Event.last_time` 判“窗口内”（74 个活跃），2A 的迁移用 `Opinion.created_at` 判候选窗口（90 个都含窗口内成员）。二者本就不是同一度量。
   - （b）**2A 的解释性错误**：在 429 条 Opinion 全部位于 7 天内的前提下，45 个事件“消失”根本不可能由“成员超窗口”造成；2A 把“未物化”误写成了“超窗口”。

3. **数据库已漂移，旧报告的具体计数不可直接采信：** 当前 90 个 Event（非 70）、271 条关联（非 220）。任何迁移决策都必须以**本次 fresh preflight** 为准，而非 1.5/2A 的文本数字。

> 处置：发现旧报告间存在事实性错误与口径错配，**不修改数据库、不执行迁移**，在 §7 给出 NOT READY 并停止。

---

## 2. 旧 Event 的真实生命周期统计（逐 Event 核验）

> 注：用户要求核验“70 个旧 Event”，但当前生产库实际为 **90 个 Event**（见 §1.2）。
> 以下对**全部 90 个**逐条核验，旧报告所称 70 仅是更早时刻的快照。

### 2.1 汇总（同源 preflight 预测，纯 SELECT）

| 预测类别 | 数量 |
|---|---|
| 完全无新成员（disappear） | **45** |
| 保留（→ 单一新 Event，其成员基本原样成簇） | 22 |
| 合并（与其他旧 Event 同入一个新房簇） | 14 |
| 拆分（→ 多个新 Event，原大伪聚合被打散） | 9 |
| **合计** | **90** |

preflight 同预测新规则将生成 **84** 个 Event（59 单成员 + 25 多成员），最大 5 成员，Opinion 覆盖率 119/429 = 27.7%，310 条（72.3%）不进入任何 Event（设计预期噪声过滤）。

### 2.2 关键生命周期异常：16 个 `last_time` 陈旧但含窗口内成员的事件

16 个事件的 `last_time` 早于 cutoff（最旧为 **2013-07-17**），但其关联 Opinion 的 `created_at` 全部是 2026-07-20~22（窗口内）。例如：

| event_id | last_time | 实际关联 Opinion 时间 |
|---|---|---|
| 82 | 2013-07-17 | 2026-07-20 |
| 96 | 2025-12-29 | 2026-07-21 |
| 80 | 2026-03-26 | 2026-07-20 |
| 73 | 2026-05-12 | 2026-07-20（4 条） |
| 78 / 79 / 71 / 76 / 70 / 69 / 74 / 77 / 84 / 87 … | 2026-04~07 | 2026-07-20~22 |

**含义：** `Event.last_time` 并非可靠等于 `max(关联 Opinion 时间)`。这些“陈旧壳”事件是旧关键词聚合“永久吸附”病理的残留——新舆情被关键词交集挂到多年前的旧 Event 上，但其 `last_time` 从未被重算刷新。这正是 Phase 4-Event-1 重构要根治的现象，也是 1.5 用 `last_time` 判“活跃”会高估活跃数的根因。

### 2.3 逐 Event 核验表（共 90 个，真实 SQL）

> 列：`last_time`/`first_time` 截断到分钟；`近7天`=`completed 且 created_at≥cutoff` 的成员数；`超7天`=其余成员数；`stored/实际`=存储字段/真实关联数；`新规则预测`=同源 preflight 分类。

（完整 90 行见 `backend/_event_table.md`；摘要要点：45 个 disappear 事件的 `超7天` 列**全部为 0**，再次印证 §1.3 根因。）

| event_id | last_time | 关联数 | 近7天 | 超7天 | stored/实际 | 新规则预测 |
|---:|---|---:|---:|---:|---|---|
| 27,28,29,30,33,34,35,36,37,38,39,41,42,43,44,46,47,48,54,56,57,58,59,60,61,62,63,64,65,66,67,68 | 2026-07-16 08:00 | 1 | 1 | 0 | 1/1 | 消失 |
| 31,45 | 2026-07-16 08:00 | 2 | 2 | 0 | 2/2 | 消失 |
| 55 | 2026-07-16 08:00 | 5 | 5 | 0 | 5/5 | 消失 |
| 69 / 70 / 71 / 72 / 74 / 76 / 78 / 80 / 82 | 2026-07-09 ~ 2013-07-17（陈旧） | 1~2 | =全 | 0 | =全 | 消失 |
| 83 | 2026-07-21 14:19 | 1 | 1 | 0 | 1/1 | 消失 |
| 32（16）、40（39）、49（3）、52（19）、73（4）、86（19）、93（12）、94（6）、95（22） | 各 | 各 | =全 | 0 | =全 | **拆分（原大伪聚合被打散）** |
| 50,51,53,75,77,79,81（11）,84,85,87,88（5）,90,91（2）,92 | 各 | 各 | =全 | 0 | =全 | **合并（与其他旧 Event 同入新房簇）** |
| 89,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116 | 各 | 2~4 | =全 | 0 | =全 | **保留（→ 单一新 Event）** |

---

## 3. 旧 Event → 新 Event 的真实映射

### 3.1 是否存在可确定的“旧 id → 新 id”映射？

**不存在 id 级别的确定性映射。** 原因：

- 正式迁移在单事务内 `DELETE events / event_opinions` 后，由 `compute_new_events` **重新 `INSERT`** Event 行，新 id 由数据库自增分配，**提交前不可预知**。
- preflight 的 `old_to_new_mapping` 只给出 `old_event_id → [新 plan 索引列表]`（按**成员重叠**判定），**不是**数据库新 id。plan 索引在提交时按插入顺序映射为真实 id，无法事前确定。

### 3.2 那么传播树 / 预警记录如何找回关联？

只能**按成员/舆情重新推导**，不能按 id 直接翻译：

- **PropagationNode**：迁移会把全部 221 行的 `event_id` 与 `parent_id` 置空（见 §4），随后对每个新 Event 调用 `PropagationService.rebuild_for_event` **从 EventOpinion 重新生成**传播树。即“丢弃旧树、按新成员重建”，不是“映射旧树到新 id”。
- **AlertRecord**：迁移把 9 行的 `event_id`/`event_title` 置空，**不自动重链**；需事后由 `alert_service` 的“按 `opinion_id` 重链”逻辑（见 `alert_service.py:98-108`）把每条预警重新挂到“包含该 opinion 的新 Event”上。

> 关键风险：旧→新 **id 映射不可恢复**，传播树/预警只能靠“成员/舆情重推导”。迁移脚本当前**只重建传播树（best-effort，失败静默），不重链预警**。详见 §4。

---

## 4. 传播树 / 预警记录的迁移影响（外键级核验）

读取真实 Model、ForeignKey、service 代码（`app/models/*`、`app/services/event/migration.py`、`app/services/propagation_service.py`、`app/services/alert_service.py`）：

### 4.1 外键与 ON DELETE 行为

| 引用表.列 | 是否可空 | ON DELETE（Model 未声明 → DB 默认 NO ACTION/RESTRICT） | 迁移如何处理 |
|---|---|---|---|
| `event_opinions.event_id` → `events.id` | **NOT NULL** | NO ACTION | 迁移**先** `DELETE event_opinions` **再** `DELETE events`（顺序正确，不会 FK 违例）✅ |
| `propagation_nodes.event_id` → `events.id` | 可空 | NO ACTION | 迁移置空 `event_id` + `parent_id`（221 行全清空）⚠️ |
| `alert_records.event_id` → `events.id` | 可空 | NO ACTION | 迁移置空 `event_id` + `event_title`（9 行）⚠️ |

**结论：没有任何 `ON DELETE CASCADE / SET NULL / RESTRICT` 被显式声明**，全部依赖 DB 默认 NO ACTION；迁移以“先删子表(event_opinions)再删父表(events)”的顺序规避了 FK 违例，逻辑正确。

### 4.2 影响量级（真实 SQL 实测）

| 表 | 总行数 | 引用了有效 event_id 的行 | 引用了**已不存在** event_id 的孤儿行 |
|---|---:|---:|---:|
| `propagation_nodes` | 221 | 221（100%） | 0 |
| `alert_records` | 11 | 9 | 0 |

当前无孤儿外键引用（所有 event_id 都指向现存 Event），故**迁移前**不会因外键失败。

### 4.3 迁移会导致什么？

| 风险 | 是否发生 | 是否可恢复 | 备注 |
|---|---|---|---|
| 外键约束失败 | 否 | — | 删表顺序正确 |
| 传播节点**丢失**（行删除） | 否（行保留，仅 `event_id`/`parent_id` 置空） | — | 树**结构被销毁**（parent_id 清空），靠重建恢复 |
| 传播树**结构不可恢复** | 是（旧树被丢弃） | **可重推导**：重建后由 `rebuild_for_event` 从新 Event 的 EventOpinion 重新生成 | 但重建是 **best-effort（`try/except pass`）**，若静默失败则传播节点沦为 `event_id=None` 的游离行 |
| 预警记录**失去关联** | 是（9 行 `event_id` 置空） | **可重链**：经 `alert_service` 按 `opinion_id` 重挂到新 Event | **迁移脚本不执行此重链** → 迁移后预警在 UI 中失去事件分组，直到人工/脚本跑一次重链 |
| 旧 Event id 改变后无法恢复关联 | 是 | 只能成员/舆情重推导（见 §3.2） | 快照不含 propagation/alert 行，见 §4.4 |

### 4.4 快照覆盖缺口（重要）

`migration._snapshot_to_disk` **仅落盘 `events` + `event_opinions` 两张表**，**不含 `propagation_nodes` / `alert_records`**。因此：

- 若迁移失败回滚（`db.rollback()`）：整库回到迁移前，一切完好（含传播/预警）。✅
- 若迁移**提交成功**但随后发现传播/预警有问题：快照**无法还原**传播树与预警的旧 `event_id`，因为它们在同一事务里已被置空且快照没存它们。只能靠“重新 `rebuild_for_event` + 按 `opinion_id` 重链预警”来重建，**不能靠快照 id 还原**。

> 风险标记（影响 §7 readiness）：传播/预警的关联**不是不可恢复**，但恢复路径是“重推导”而非“快照还原”，且当前脚本**漏掉预警重链、传播重建为静默 best-effort、快照不覆盖这两张表**。

---

## 5. 方案 A 与方案 B 对比（窗口外旧 Event 是否该清理）

### 5.1 先厘清三种“旧”的语义（用户给定 A/B/C）

- **A. Event 最后更新时间超过 7 天**：事件本身可能已结束，但仍是**历史研判数据**。
- **B. Event 部分成员超过 7 天**：可能是**持续事件的历史时间线**。
- **C. 所有关联 Opinion 都超过 7 天**：可能是陈旧事件，也可能是**需保留的历史事件**。

### 5.2 真实数据下“窗口外”几乎不存在

实测：**全部 429 条 Opinion 的 `created_at` 都在 2026-07-20~22，100% 落在 7 天窗口内**。因此：

- 按 C 定义（所有成员超窗口）：**当前 0 个事件满足**——90 个事件都含窗口内成员。
- 按 `Event.last_time` 定义（A）：16 个事件“陈旧”，但这 16 个**仍含窗口内成员**（见 §2.2），并非真正“无价值的历史数据”，而是“永久吸附”残留壳。

### 5.3 两种方案对当前数据的真实影响

| 维度 | 方案 A（全量重建，只保留新规则近 7 天 Event；即当前 `migration.py` 实现） | 方案 B（只重建活跃 Event，窗口外旧 Event 原样保留） |
|---|---|---|
| 实现状态 | **已实现** | **未实现**，且按当前数据**无法干净定义** |
| 新 Event 数 | 84（59 单 + 25 多） | 若按 `last_time` 活跃(74) 重建 + 保留 16 陈旧壳 → 理论上 84 + 16 = 100，但**16 壳的成员与重建池重叠**（同在 429 窗口内）→ **重复关联**，不一致 |
| 被“清理/消失”的 Event | 45（其成员是窗口内、但 `risk<40` 的低风险单条） | 若按 C 定义：0 个窗口外可保留；若按 `last_time`：保留 16 壳但引入重复关联 |
| Opinion 关联影响 | 310 条（72.3%）变“无事件关联”（含那 45 事件的 52 条窗口内低风险舆情） | 取决于定义，存在重复关联风险 |
| 传播树 / 预警 | 置空后重建/需重链（见 §4） | 同左，且因重复关联更复杂 |

### 5.4 关键纠正：不要用“清理窗口外旧 Event”来为 45 个消失事件背书

Phase 2A 把“丢弃 45 个旧 Event”表述为“清理窗口外陈旧事件”。**这是基于 §1.3 已证伪的错误前提**。真实情况是：这 45 个事件**不是陈旧**，它们含的是**窗口内、但低风险的近期舆情**，被新规则按“物化阈值”排除了。这是**“什么样的舆情算一个 Event”的策略问题**，不是“清理过期数据”的卫生问题。

> 建议：迁移前必须**显式拍板物化阈值策略**（是否允许 `risk<40` 的单条舆情独立成 Event？当前规则不允许 → 它们不进事件中心）。方案 A/B 之争在此数据下已退化——因为不存在“窗口外陈旧事件”可保留；真正要决定的是“低风险单条舆情是否成事件”。

---

## 6. Event-2 叙事升级与正式 rebuild 的先后关系

读取 `aggregator._create_event`（L419-429）与 `migration.compute_new_events`（L136-137）：

```python
# aggregator.py L419-421（明确注释）
# 临时兼容（非最终 Event Narrative 方案）：title / description 暂沿用代表性 Opinion，
# 待 Phase 4-Event-2 引入生成式标题/摘要时再替换。
event = Event(title=top.title, description=(top.content or "")[:200], ...)
```

### 6.1 逐项评估

| 问题 | 结论 |
|---|---|
| 1. Event-2 是否修改 `title`/`description` 生成逻辑？ | **会**。当前是“最高风险 Opinion 标题 + 正文前 200 字”的临时兼容值，Event-2 将以生成式 Narrative 替换。 |
| 2. 是否新增数据库字段？ | **可能**。若 Event-2 引入 `narrative`/`summary`/`generated_at` 等列，需独立 DB migration（属结构变更，与本阶段“禁改表结构”约束分离）。当前 `Event` Model 仅有 `title`/`description` 文本列。 |
| 3. 是否修改 API response？ | **基本不改形状**。`schemas/event.py` 仍返回 `title`/`description` 字段，只是内容变好；若新增字段则 schema 同步加字段（向后兼容）。 |
| 4. 是否修改前端 Event 展示？ | **可能需微调**。前端读 `title`/`description` 渲染；若 Event-2 产出更丰富的叙事结构，展示层可能要适配，但不阻塞迁移。 |
| 5. Event-2 是否需重新处理所有已存在 Event？ | **是**。叙事是内容重生成，需对全量 Event（无论新旧）跑一次 backfill。 |

### 6.2 先后建议（本评审结论）

> **建议：先执行 rebuild（用当前临时兼容字段），再独立执行 Event-2 的 Narrative backfill。**

理由：
1. **成员归属（rebuild）是紧急性、完整性关键操作**：它消除 39 成员伪聚合（id=40）、阻断“永久吸附”（§2.2 的 2013 壳），且数据库正在持续漂移（90 个且增长）。若等 Event-2 设计完成再 rebuild，关键修复被无限期推迟，漂移继续累积。
2. **表达（Event-2）是可分离、幂等的内容重生成**：它只改写 `title`/`description` 文本，不触碰成员关联，可作为独立 backfill 在“任何既有 Event（旧或新）”上运行，**无需重新迁移成员**。
3. **若 Event-2 需要新列**：应**在此之前**以独立的、向后兼容（nullable + 默认值）的 DB migration 添加，**不阻塞本次 rebuild**、也**不改变成员逻辑**；随后 rebuild 可在 `Event(...)` 构造时填列，或留 NULL 由 Event-2 backfill 补。

> 此为先 rebuild、后 Event-2 的建议；**该先后关系尚未经用户拍板确认**（见 §7 条件 6）。

---

## 7. 最终迁移 Readiness

### 7.1 七项 READY 条件逐条核对

| # | 条件 | 状态 | 证据 |
|---|---|---|---|
| 1 | 之前报告间无未解决的数据事实矛盾 | ⚠️ **已解析，但暴露旧报告错误** | §1：矛盾根因为口径错配 + 2A“超窗口”解释错误；且 DB 已 70→90 漂移，旧数字不可直接采信 |
| 2 | 旧 Event 生命周期语义已确认 | ✅ | §2：45 消失=物化阈值排除（非超窗口）；16 壳=`last_time` 不可靠的“永久吸附”残留 |
| 3 | 所有 Event 外键引用已确认 | ✅ | §4.1：仅 `event_opinions`(NOT NULL) + `propagation_nodes`/`alert_records`(可空)，均无 ON DELETE 声明，删表顺序正确 |
| 4 | 传播树/预警不发生不可恢复关联丢失 | ⚠️ **部分不满足** | §4.3–4.4：可重推导但非快照可还原；脚本**漏预警重链**、传播重建为静默 best-effort、快照**不含** propagation/alert 表 |
| 5 | 正式迁移后保留/清理策略已确认 | ❌ **不满足** | §5：45 消失的真实原因是物化阈值，非“窗口外陈旧”；方案 B 在当前数据下无法干净定义；物化阈值策略未拍板 |
| 6 | Event-2 与 rebuild 先后关系已确定 | ❌ **不满足** | §6.2 仅为本评审建议，用户尚未确认 |
| 7 | preflight 预测与正式迁移使用同源逻辑 | ✅ | `preflight` 与 `migrate_events` 均调用 `compute_new_events`/`cluster_opinions`，代码同源自证（migration.py L177 / L406） |

### 7.2 最终标记

# ❌ NOT READY（停止，未执行任何正式迁移）

**未满足项（阻塞 READY）：条件 4（部分）、5、6。**

### 7.3 进入 READY 前必须解决的阻塞清单

1. **修正迁移脚本的关联恢复缺口（条件 4）：**
   - 在 `migration.migrate_events` 提交后，**显式调用预警重链**（复用 `alert_service` 的按 `opinion_id` 重链逻辑），不应只置空不重链。
   - 传播重建 `rebuild_for_event` 的 `try/except pass` 应**改为记录失败并告警**，避免静默丢失。
   - **扩展快照** `_snapshot_to_disk` 同时落盘 `propagation_nodes` 与 `alert_records`（含其 `event_id`），使极端情况下可“快照还原”而不仅“重推导”。
2. **拍板物化阈值 / 保留策略（条件 5）：**
   - 明确：`risk<40` 的单条低风险舆情是否成 Event？当前规则“不成”→ 它们不进事件中心（即 45 个“消失”事件的实质）。
   - 重新表述迁移语义：**不是“清理窗口外陈旧事件”**（当前数据无此类），而是“按物化阈值重建成员归属”。
   - 若坚持方案 B，需重新设计（当前数据下按 `last_time` 保留会与重建池产生重复关联，须先去重）。
3. **确认 Event-2 与 rebuild 先后（条件 6）：** 采纳本评审“先 rebuild、后 Event-2 backfill”建议，或提出替代；若 Event-2 需新列，先以独立向后兼容 migration 添加。
4. **以 fresh preflight 为唯一决策基准（条件 1 延伸）：** 旧报告（70/45 等数字与“超窗口”解释）已证伪且 DB 漂移，后续一切以本次 `_readonly_audit.json` 的同源 preflight 为准。

### 7.4 合规声明（本阶段未改动项）

- 未执行任何 `INSERT / UPDATE / DELETE / TRUNCATE / DROP`。
- 未修改 `Event` / `EventOpinion` / `Opinion` / `PropagationNode` / `AlertRecord` Model 或任何数据库结构。
- 未修改 `aggregator.py` / `migration.py` / `config.py` 等任何后端代码、API contract、前端。
- 未调用 `migrate_events(dry_run=False, force=True, allow_production=True)` 的正式路径。
- 生产 `opinion_db` 数据零改动；仅 SELECT 与落盘只读 JSON/MD 证据文件。
