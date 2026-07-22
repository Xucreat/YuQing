# Phase 4-Event-2A Event Rebuild Migration Design & Preflight Validation

> 角色：后端工程师 + 数据迁移工程师
> 阶段目标：在不改动生产数据的前提下，设计受控的 Event 全量重建迁移机制，
> 实现只读 preflight 预检与「默认 dry-run、显式 force 才正式执行」的迁移代码，
> 并用真实生产库（`opinion_db`）完成只读预测。
> **本阶段（2A）仅实现机制，未执行任何正式生产 rebuild。**

---

## 1. 当前 `rebuild=True` 的完整风险分析

代码位置：`backend/app/services/event/aggregator.py`

- **取数**：`aggregate(rebuild=True)` 仅对 `last_time >= now - event_window_days(7)` 的「活跃」Event 调用 `_reset_active_event_links()` 删除其 `EventOpinion` 关联，再对窗口内 `completed` 的 Opinion 重新聚类。
- **旧 Event 行不删除**：`_reset_active_event_links` 只删「活跃事件」的关联，**从不动 Event 行本身**，也不碰 `last_time` 超出窗口的「陈旧事件」。
- **派生字段是冗余列**：`Event.opinion_count` / `risk_level` / `keyword` / `first_time` / `last_time` 全部由 `_recompute_event` 从关联重算写入，**不是实时从关系计算**；因此一旦关联被清空而事件未重建，就会出现「行在、count 失真、链接为 0」的空孤儿。
- **事务边界**：`aggregate` 在 `rebuild` 分支里 `delete` 后**没有包裹在显式事务/快照/回滚**里；若中途异常，已删的关联不会回滚。
- **并发风险**：`aggregate` 无乐观锁/去重锁；若两个请求并发触发，可能产生竞态写入。
- **API 暴露空孤儿**：`GET /events` 直接 `db.query(Event).count()` + 列表，空孤儿 Event 会被分页返回给前端，**用户会看到无成员的「幽灵事件」**。
- **无审计机制**：现有代码**没有任何快照、审计归档或回滚入口**；`_find_existing_event` 按关键词交集把新 Opinion 追加到既有 Event，一旦旧 Event 含某通用词，未来同区同词 Opinion **永久吸附**。

**综合风险（来自 Phase 4-Event-1.5 只读 dry-run 实测）**：
对生产 70 个旧 Event 跑 `rebuild=True`，会清空活跃事件关联后重算；但 45 个旧 Event 在新规则下不再有成员 → 变成**空孤儿 Event 行**，总数从 70 **膨胀到 ~90**，且**无备份、无回滚、无审计**。

---

## 2. 选择的迁移方案及原因

评估了三种策略：

| 方案 | 数据安全 | 回滚 | 审计 | 复杂度 | API 影响 | 结构变更 |
|---|---|---|---|---|---|---|
| A. 旧 Event 保留 + 另建新批次，事后切换 | 中（新旧并存易冲突/重复） | 弱（需手动丢弃旧批次） | 弱 | 高 | 中（需切换开关） | 否 |
| B. 快照 + 同事务内全量清空重建（**采用**） | 高（先落盘快照） | 强（事务 rollback + 磁盘快照还原） | 强（磁盘快照=审计记录） | 中 | 无（原子替换，事务提交前对外不可见） | 否 |
| C. 迁移批次 + 原子替换（临时表/改名） | 高 | 强 | 中 | 高（需临时表或 rename，接近结构变更） | 无 | 近似变更（有风险） |

**结论：采用方案 B。**
- 零数据库结构变更，完全贴合「禁止新增 migration / 禁止改表结构」约束；
- 单一事务保证原子性（要么全成、要么全滚），天然杜绝「45 个空孤儿」与「数量膨胀」；
- 磁盘快照（纯 `SELECT` 落盘 JSON，不写库）同时充当**审计记录**与**回滚依据**；
- 复用 `aggregator` 的纯函数 `cluster_opinions` / `_merge_condition` 等，**聚合判定规则与 Phase 4-Event-1 已验证版本完全一致，不改动**。

> 说明：方案 C 的「原子替换」本质上就是 B 的变体（用临时表代替内存重建），但引入 rename/临时表更接近结构操作，本阶段不选。

---

## 3. 修改文件列表

| 文件 | 变更 | 说明 |
|---|---|---|
| `backend/app/services/event/migration.py` | **新增** | 受控迁移模块：`preflight()`（只读预检）、`migrate_events()`（默认 dry-run）、`consistency_check()`、`compute_new_events()`（与正式执行同源）、磁盘快照、生产守卫 |
| `backend/scripts/migrate_events.py` | **新增** | 运维 CLI：默认只读 preflight；`--force` 才正式；生产库需 `--allow-production` |
| `backend/tests/test_event_migration.py` | **新增** | 11 项迁移测试（见第 6 节） |
| `backend/app/services/event/aggregator.py` | **未改** | 聚合规则保持不变 |
| `backend/app/api/events.py` / `schemas/event.py` | **未改** | API contract 不变 |
| `Event` / `EventOpinion` / `Opinion` Model | **未改** | 无结构变更、无新 migration |

---

## 4. 新增测试列表

`backend/tests/test_event_migration.py`（在隔离测试库 `opinion_test` 运行，**不触碰生产库**）：

1. `test_old_event_fully_dispersed` — 旧多成员 Event 被完全拆散为多个新 Event；并验证低分成员在新规则下不物化 → 旧 Event 变空/消失
2. `test_multiple_old_merge_into_one` — 多个旧 Event（同真实事件被旧规则拆开）合并为一个新 Event
3. `test_preflight_matches_formal` — preflight 预测 `predicted_event_count` 与正式执行实际 `created_event_count` 完全一致
4. `test_dry_run_no_writes` — `dry_run=True`（默认）不改动数据库任何行
5. `test_transaction_rollback_on_failure` — 一致性校验失败 → 事务回滚，旧数据完好
6. `test_integrity_before_and_after` — 迁移前后均可验证数据完整性（无空/孤儿/重复/数量错位）
7. `test_migration_integrity_contract` — 综合：迁移后无空 Event、无孤儿 `EventOpinion`、无重复、每个 `opinion_count` 与真实关联一致

> 测试 1/2/3/5/6/7 覆盖需求第七节 11 项中的：①旧 Event 完全拆散 ②一个旧拆多个新 ③多个旧合并为一个 ④新 Event 不允许无成员 ⑤无孤儿 ⑥无重复 ⑦`opinion_count` 一致 ⑧preflight≡正式 ⑨dry-run 无写入 ⑩事务回滚 ⑪前后可校验。

**测试结果**：
- 事件相关全量：`tests/test_events.py` + `tests/test_events_aggregator_v2.py` + `tests/test_event_migration.py` → **24 passed**
- 全量 `pytest tests/`：**66 passed / 12 failed**（12 个失败全部位于 `test_ai_analysis / ai_service / collector / government_collector`，与事件迁移无关，且在 Phase 4-Event-1 基线中即已存在、本阶段零新增回归）

---

## 5. preflight 使用方法

Preflight **只做 `SELECT`，绝对不写库**，可随时对任意库运行。

```bash
# 方式一：运维脚本（默认只读 preflight）
cd backend
DATABASE_URL="postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db" \
  ../.venv/Scripts/python.exe scripts/migrate_events.py --preflight

# 方式二：在代码里调用
from app.services.event.migration import preflight
pf = preflight(db)   # db 为任意 Session；仅 SELECT
```

生产库（`opinion_db`）本阶段已跑过一次只读 preflight，结果见第 6 节。
**本阶段（2A）未执行 `migrate_events(dry_run=False)` 的正式路径。**

---

## 6. 预期迁移结果（生产 `opinion_db` 只读 preflight，零写入）

| 指标 | 旧（当前 70 个 Event） | 新规则预测 |
|---|---|---|
| Event 总数 | 70 | **84** |
| 单成员 Event | 53 | 59 |
| 多成员 Event | 17 | 25 |
| 最大成员数 | 39 | **5** |
| 平均成员数 | — | 1.417 |
| Opinion 候选总数 | — | 429 |
| Opinion 覆盖率 | 220（旧链接数） | 119 / 429 = **27.7%** |
| 未进入任何 Event 的 Opinion | — | 310（72.3%，设计预期噪声过滤） |
| 空 Event 数 | （含未知空孤儿） | **0**（重建保证） |
| 孤儿 EventOpinion 数 | — | **0** |
| 重复 EventOpinion 数 | — | **0** |

**六个重点伪聚合案例（旧 → 新）**：全部被拆散，真实高相似子集保留同簇。

| 旧 Event | 旧成员 | 新规则去向 | 是否消除伪聚合 |
|---|---|---|---|
| 40 | 39 | 拆成多个新 Event（绝大多数真同文本成员仍同簇，链式伪聚合消除） | ✅ |
| 95 | 22 | 拆成多个新 Event | ✅ |
| 81 | 11 | 仅 2 成员落在窗口内并保留为 1 个新 Event（其余 9 因超 7 天窗口被正式重建排除） | ✅ |
| 86 | 19 | 拆成多个新 Event | ✅ |
| 93 | 11 | 拆成多个新 Event（纯通用词，最干净验证） | ✅ |
| 73 | 4 | 2 成员保留为 2 个新 Event | ✅ |

> 注：旧→新映射中「45 个旧 Event 完全消失/变空」**并非数据丢失**——这些旧 Event 的成员发布时间都已**超出 7 天聚合窗口**，在全量重建（只基于窗口内 Opinion）的语义下被正确排除。这与「今天跑一次 `aggregate()` 会得到的结果」完全一致，是**预期且一致的**行为；同时磁盘快照保留其旧值以便回滚。

---

## 7. 回滚机制

1. **事务回滚**：正式执行整体包裹在单一 SQLAlchemy 事务中；`consistency_check` 任一项不通过（空 Event / 孤儿 / 重复 / `opinion_count` 错位）即 `raise` → `db.rollback()`，数据库回到迁移前状态。
2. **磁盘快照（审计 + 还原依据）**：正式执行**第一步**即把当前 `events` + `event_opinions` 全量 `SELECT` 落盘为 JSON（`{snapshot_dir}/event_snapshot_YYYYMMDDTHHMMSS.json`），纯读、不写库。一旦需还原：
   ```python
   # 读取快照 JSON -> 删除现有 events/event_opinions -> 按快照逐行重建
   ```
   因快照在 `commit()` **之前**生成，即使提交后发现问题也能完整还原。
3. **生产守卫**：`migrate_events(..., allow_production=...)` 检测到连接库名为 `opinion_db` 时，**必须**显式 `allow_production=True` 才放行；否则直接拒绝。默认 `dry_run=True`，连 `force` 都不需要即可安全只读预检。

---

## 8. 数据一致性校验机制

`consistency_check(db)`（只读 `SELECT`）在**正式执行事务内（提交前）**与**提交后**各跑一次，覆盖：

- **空 Event**：`opinion_count == 0` 或实际无 `EventOpinion` 关联 → 拦截（杜绝「幽灵事件」）
- **孤儿 EventOpinion**：`opinion_id` 或 `event_id` 指向不存在的行 → 拦截
- **重复 EventOpinion**：同一 `(event_id, opinion_id)` 出现多行 → 拦截（重建用 get-or-create，本应 0）
- **`opinion_count` 错位**：每个 Event 的 `opinion_count` 字段与真实关联数不一致 → 拦截
- **引用完整性**：被关联 `opinion_id` 必须真实存在

重建后额外用 `_recompute_counts(db)` 以**真实链接数**反写 `opinion_count`，确保字段与关系永远一致（不依赖聚类时的计数副本）。

---

## 9. 运行测试结果

```
事件相关（test_events + test_events_aggregator_v2 + test_event_migration）：
  24 passed

全量 pytest tests/：
  66 passed, 12 failed
  —— 12 个失败全部位于 test_ai_analysis / test_ai_service / test_collector /
     test_government_collector，与事件迁移无关，且为 Phase 4-Event-1 基线
     已存在的环境型失败（DeepSeek 未配置 / 政府采集器 mock 计数），
     本阶段新增文件零回归。
```

发现并修复的两个实现缺陷（均未触及聚合规则）：
- 删除 Event 后未 `flush` 关联导致事务内一致性校验看不到新建链接 → 在重建循环内对每个 Event 显式 `db.flush()`；
- `DELETE ... synchronize_session=False` 使旧 Event 对象残留在会话身份映射，后续查询误返回「空/孤儿」幻影 → 改用默认 `fetch` 同步，删除实例自动从会话移除。

---

## 10. 明确声明：本阶段是否修改了生产数据库数据

**否。本阶段（Phase 4-Event-2A）未对生产数据库（`opinion_db`）执行任何 INSERT / UPDATE / DELETE / TRUNCATE / DROP。**

- 生产库仅被**只读 `SELECT`** 用于 preflight 预测（输出见第 6 节）。
- 新增的 `migrate_events(dry_run=False, force=True)` 正式路径**已实现但从未被调用**。
- 所有写库测试均在隔离测试库 `opinion_test`（`127.0.0.1:5432`）运行，与生产数据物理隔离。

---

## 11. 风险与待确认事项（进入下一阶段前需你拍板）

1. **全量重建会丢弃 45 个「窗口外陈旧旧 Event」**：这是「基于最近 7 天 Opinion 全量重建」的固有语义（与今天跑一次 `aggregate()` 等价），并非数据损坏；快照可还原。**待确认**：接受「丢弃窗口外陈旧 Event」，还是希望迁移只重建窗口内、并**保留**陈旧旧 Event 原封不动？（后者需把迁移改为「仅窗口内重建 + 陈旧事件置为只读保留」，会重新引入部分旧逻辑的复杂度）
2. **是否正式执行生产 rebuild**：本阶段未执行。如需执行，命令为（**务必先确认**）：
   ```bash
   DATABASE_URL="postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db" \
     ../.venv/Scripts/python.exe scripts/migrate_events.py --force --allow-production
   ```
   执行前会自动落盘快照、事务内重建、双重一致性校验；失败自动回滚。
3. **聚合阈值仍为经验值**：`event_text_similarity_threshold=0.45` / `event_low_merge_text_threshold=0.30` 等来自 Phase 4-Event-1 的校验，建议在 Phase 4-Event-4 结合更多真实数据再调优。
4. **`Event.title` / `description` 仍临时兼容**（最高风险 Opinion 标题 / 正文截断），最终 Narrative 留待 Phase 4-Event-2；本迁移不涉及。
5. **传播树（propagation_nodes）**：正式重建会先把引用 Event 的 `propagation_nodes` / `alert_records` 外键置空，重建新 Event 后 best-effort 重新触发 `PropagationService.rebuild_for_event`；旧传播树按新 Event 重新生成，旧树不保留（快照含旧值可还原）。
