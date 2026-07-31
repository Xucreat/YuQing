# 事件中心幂等收口 · Phase 7.5 设计方案（企业级 · 仅设计）

> 生成时间：2026-07-24 11:23（GMT+8）
> 模式：**仅设计，未修改任何代码 / 未执行任何 DDL/DML/迁移**。本文为修复设计方案，落地需另立实施阶段。
> 前置依据：《事件中心重复事件审计报告》（Phase 7 后续 · 只读）—— 43 组重复事件全部为 A 类（完全重复），根因为历史多实例双触发 + 聚合增量路径无并发串行化。

---

## 0. 设计目标与原则

| 维度 | 目标 |
|---|---|
| 防再生 | 杜绝新增重复事件（并发物化、双触发） |
| 清存量 | 合并 43 组历史重复事件，**零舆情/告警/传播信息丢失** |
| 幂等化 | 事件级具备可识别的确定性键，支撑去重与未来扩展 |
| 在线安全 | 不加表锁、不中断采集/API、可回滚、可失败恢复 |
| 最小侵入 | 复用既有 scheduler 锁范式，不引入 Redis / MQ 等新依赖 |

---

## 1. EventAggregator 聚合入口 advisory lock 方案

### 1.1 最佳加锁位置

**结论：在 `aggregate()` 调用链的最外会话处加锁，且锁必须取在与「候选召回 + 提交」同一连接上。**

代码事实（已读）：
- `auto_aggregate_after_collect(session_factory)`（`aggregator.py:682`）入口 `db = session_factory()`（L695），全程用该 `db` 会话做候选召回（L376-385）、物化（L462-479）、提交（L492），`finally` 中 `db.close()`（L702）。
- 手动聚合入口 `api/events.py:_run_aggregate_task`（L44）同样 `db = session_factory()`（L47），经 `start_task` 后台执行。

因此加锁点应选在 **`auto_aggregate_after_collect` 拿到 `db` 之后、开始召回之前**，并在其 `finally` 中释放；手动路径 `_run_aggregate_task` 同样在拿到 `db` 后加锁。两层共享一个锁 key，即"任何聚合（自动/手动）在任一时刻全局唯一执行"。

```python
# 设计示意（非落地代码）
def auto_aggregate_after_collect(session_factory):
    db = session_factory()
    try:
        if not try_advisory_lock(db, EVENT_AGGREGATE_LOCK_KEY):
            logger.info("聚合被跳过：其他聚合正在进行（advisory lock 未获取）")
            return {"skipped": True, "reason": "locked"}
        return EventAggregator().aggregate(db, incremental=True)
    ...
    finally:
        release_advisory_lock(db, EVENT_AGGREGATE_LOCK_KEY)  # 幂等，未持锁也安全
        db.close()
```

### 1.2 与 scheduler.py 锁机制复用方式

`scheduler.py` 已有成熟范式（`L23-28` 密钥派生、`L59-103` 取/释放）。**但二者语义不同，不能直接复用 `_try_acquire_scheduler_lock`**：
- scheduler 锁是**进程级单例长锁**（持有至进程退出，`_scheduler_lock_conn` 为模块级全局连接）。
- 聚合锁是**调用级短锁**（仅持有一次 `aggregate()` 期间），需随会话释放。

**推荐复用方式：抽取通用助手 `app/core/advisory_lock.py`**，让 scheduler 与 aggregator 共用同一套底层原语：

```python
# app/core/advisory_lock.py（设计）
import hashlib
from sqlalchemy import text
from sqlalchemy.orm import Session

def make_lock_key(seed: str) -> int:
    return int.from_bytes(hashlib.sha1(seed.encode()).digest()[:8], "big") & 0x7FFFFFFFFFFFFFFF

def try_advisory_lock(db: Session, key: int) -> bool:
    return bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}).scalar())

def release_advisory_lock(db: Session, key: int) -> None:
    db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
    db.commit()
```

聚合锁 key：`make_lock_key("opinion-platform-event-aggregate")`（与 scheduler 的 `opinion-platform-scheduler-singleton` 不同 key，互不干扰）。可选：将 `scheduler.py` 的取/释放重构为调用本助手（保持行为不变）。

### 1.3 是否影响手动聚合

- **行为变化**：并发的两次手动聚合（或手动与自动重叠）中，后到者**跳过而非阻塞**，返回 `{"skipped": true}`。
- **数据正确性**：无影响。聚合幂等——被跳过的那次本要处理的未关联舆情，会在下一次自动聚合（采集后触发）或下次手动聚合中被处理；增量路径仅处理未关联舆情，不会遗漏。
- **用户体验（需配套小改）**：`api/events.py` 的聚合任务结果应区分 `skipped` 与 `done`，前端提示"聚合已在执行，稍后查看"，而非报错。这是唯一需要的 API 层配套改动。
- **结论**：影响可控，且对正常串行使用（绝大多数场景）完全透明。

### 1.4 是否影响性能

- advisory lock 是 PG **会话级轻量锁**，无表锁、无行锁竞争开销；取/释为两条极快 SQL。
- 锁仅在单次 `aggregate()` 期间持有：增量聚合为秒级（仅未关联舆情），全量 rebuild 较长但**极少触发**（显式开启）。
- 因采用 **skip-if-not-acquired**（不阻塞等待），不会造成请求排队。
- **结论**：性能影响可忽略。

---

## 2. 事件级幂等设计（event_hash）

### 2.1 字段方案

`events` 表新增 **`dedup_key VARCHAR(64)`（可空）**，存放该事件在「创建时刻」所代表舆情簇的确定性签名。

> 设计要点：`dedup_key` 是**创建时刻签名，而非持续维护的事件身份**。它在 INSERT 时计算并冻结，用于拦截"同一簇被并发物化两次"的竞态；后续舆情挂载不改变该值（详见 2.5 权衡）。

### 2.2 hash 生成规则

在 `_create_event`（`aggregator.py:597`）物化前计算，输入为本次待物化簇的**全部成员 Opinion 的 url**（url 已是 Phase 7 强制唯一的业务主键，`opinions.url` 有 `ix_opinions_url_unique`）：

```python
# 设计示意
def _compute_dedup_key(cluster: list[Opinion]) -> str:
    urls = sorted({o.url.strip() for o in cluster if o.url})
    if not urls:
        # 极端兜底：用代表舆情 id，避免空 key 触发唯一索引误拦
        return hashlib.sha1(("oid:" + str(sorted(o.id for o in cluster)[0])).encode()).hexdigest()
    return hashlib.sha1("|".join(urls).encode()).hexdigest()  # 64 hex
```

- 单成员事件：key = sha1(该 opinion.url)。
- 多成员事件：key = sha1(排序后所有成员 url 以 `|` 拼接)。
- 归一化仅做 `.strip()`，**不做大小写/参数归一化**（与 Phase 7 决策一致，避免误并）。

### 2.3 唯一索引设计

```sql
CREATE UNIQUE INDEX uq_events_dedup_key
  ON events (dedup_key)
  WHERE dedup_key IS NOT NULL;   -- 部分唯一索引，空值不约束
```

- 部分索引：仅对已有 key 的事件强制唯一，兼容历史未回填/边界空值。
- **必须在合并 43 组重复事件 + 回填 key 之后**才创建（否则旧重复事件会触发唯一冲突）。

### 2.4 与现有模型兼容性

- `Event`（`models/event.py`）当前无 `dedup_key`/`created_at`，新增可空列**向后兼容**：旧代码不写该列，新代码写；读路径不受影响。
- `EventOpinion`（`models/event_opinion.py:20-27`）已有 `(event_id, opinion_id)` 唯一约束，与新增列无冲突。
- 查询层（`api/events.py` 列表）在**硬合并**方案下无需改动（重复事件已物理删除）；若采用软合并（见 3.4）则需加 `status <> 'merged'` 过滤。
- 前端无需改动（事件标题/结构不变）。

### 2.5 冲突处理（幂等创建）

`_create_event` 在写入 `dedup_key` 后若触发唯一冲突（IntegrityError），应**回退为"挂载到既存事件"**而非抛错：

```python
# 设计示意
try:
    event = _insert_event(db, cluster, dedup_key)
except IntegrityError:
    db.rollback()  # 仅回滚本次插入
    existing = db.query(Event).filter(Event.dedup_key == dedup_key).first()
    # 把本簇舆情挂到 existing（等价于并发时另一进程已建好的事件）
    EventAggregator()._link_all(db, existing.id, cluster)
    return existing
```

这正是把并发竞态转化为"后到者挂载到先到者"，实现事件级幂等。

---

## 3. 历史 43 组重复事件合并方案（零数据丢失设计）

### 3.1 前置约束（来自审计报告）

- 43 组全部 A 类：keep 与 redundant 的 `opinions` 集合**镜像一致**，url 指纹相同。
- 43 冗余事件承载：`event_opinions` 63 行、`propagation_nodes` 63 行、`alert_records` 0 行（3 条告警均在 keep 侧）。
- `events` 仅被 `event_opinions` / `propagation_nodes` / `alert_records` 三表以 `NO ACTION` 引用（无 CASCADE）。

### 3.2 保留事件选择规则（keep 规则）

每组保留**子表信息最丰富**者，确定性 tie-break：

```
keep = argmax over group events of (propagation_nodes_count, alert_records_count, -event_id)
# 即：传播节点最多 → 否则告警最多 → 否则取最小 id
```

审计报告实测：keep 与 redundant 在 `propagation_nodes` 上常打平（如均 63），故最终以 `alert_records`（keep 侧有 3）与最小 id 决出，结果确定、可复现。

### 3.3 迁移步骤（事务内，验证后提交）

> 以下为合并脚本逻辑设计；执行须遵循 Phase 7 纪律：先 `pg_dump` 备份、DELETE 前 SELECT 验证、不在未验证时删数据。

```
BEGIN;
FOR 每组 (K = keep_id, R = redundant_ids[]):
  -- 0. 预校验（保险）：R 的每个 opinion 必须已在 K 上关联
  ASSERT: 对 r in R, set(opinions of r) ⊆ set(opinions of K)

  -- 1. event_opinions：直接删冗余行（opinions 已由 K 自己的行关联，零丢失）
  DELETE FROM event_opinions WHERE event_id = ANY(R);

  -- 2. propagation_nodes：删冗余事件树（派生数据，后续重建）
  DELETE FROM propagation_nodes WHERE event_id = ANY(R);

  -- 3. alert_records：重定向到 keep（本批 0 行，保留通用性）
  UPDATE alert_records SET event_id = K WHERE event_id = ANY(R);

  -- 4. 删冗余事件（子表已清空，FK 不阻断）
  DELETE FROM events WHERE id = ANY(R);

-- 验证（任一非 0 则 ROLLBACK）
SELECT count(*) FROM (SELECT title,count(*) FROM events GROUP BY title HAVING count(*)>1) t;  -- 期望 0
SELECT count(*) FROM propagation_nodes c
  WHERE c.parent_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM propagation_nodes p WHERE p.id=c.parent_id);  -- 期望 0
SELECT count(*) FROM opinions;        -- 期望 966（不变）
SELECT count(*) FROM alert_records;   -- 期望不变（3）
COMMIT;   -- 验证通过才提交
```

**提交后重建传播树**（与 Phase 7 一致，rebuild 失败不影响已提交合并）：

```
FOR K in keep_ids:
    PropagationService.rebuild_for_event(db, K)   # 由 K 的 opinions 重建唯一干净树
```

### 3.4 不删数据替代方案（严格零删除 · 软合并）

若要求"绝对不 DELETE 任何行"，采用软合并：

- `events` 新增 `status VARCHAR(16) DEFAULT 'active'` 与 `superseded_by INTEGER`（FK→events.id）。
- 对冗余事件：`UPDATE events SET status='merged', superseded_by=K WHERE id=ANY(R)`，**不删行**。
- 子表（event_opinions/propagation_nodes/alert_records）仍重定向到 K（同上 3.3 步骤 1-3）。
- **配套必改**：所有事件列表查询加 `WHERE status <> 'merged'`（或 `superseded_by IS NULL`），前端/统计/传播树入口均须过滤。
- 代价：保留 43 个空壳事件 + 查询层改动面较大 → **默认不推荐**，仅在合规强约束"零删除"时采用。

### 3.5 各子表策略小结

| 子表 | 硬合并策略 | 数据丢失风险 |
|---|---|---|
| `event_opinions` | 删冗余行（opinions 已挂在 K） | 无（K 侧行保留） |
| `propagation_nodes` | 删冗余树 + `rebuild_for_event(K)` | 无（派生数据，可重建） |
| `alert_records` | `UPDATE event_id=K` | 无（本批 0 行，通用保留） |
| `events` | 删冗余行 | 无（信息已并入 K） |

---

## 4. 数据库迁移方案（Alembic）

### 4.1 变更范围

合并 43 事件**不是迁移**，是一次性受控数据修复脚本（同 Phase 7 cleanup SQL 地位）。Alembic 仅承载 schema 演进：

- **p8 `add_event_dedup_fields`**：
  - `events.dedup_key VARCHAR(64) NULL`；
  - （若采用软合并）`events.status VARCHAR(16) DEFAULT 'active'`、`events.superseded_by INTEGER` FK→events(id)；
  - **不在本迁移建唯一索引**（避免旧重复数据阻塞）。
- **数据修复**：执行 3.3 合并脚本（事务）+ rebuild。
- **回填**：对合并后全部 events 计算并写入 `dedup_key`（仅 `WHERE dedup_key IS NULL`）。
- **p9 `add_event_dedup_unique`**：
  - `CREATE UNIQUE INDEX CONCURRENTLY uq_events_dedup_key ON events(dedup_key) WHERE dedup_key IS NOT NULL`；
  - 须在建索引前预校验 `SELECT dedup_key,count(*) FROM events WHERE dedup_key IS NOT NULL GROUP BY dedup_key HAVING count(*)>1` 为 0。

### 4.2 回滚策略

| 层级 | 回滚 |
|---|---|
| p9 索引 | `DROP INDEX CONCURRENTLY uq_events_dedup_key`（downgrade） |
| p8 字段 | `DROP COLUMN dedup_key`（及 status/superseded_by）；PG12+ 在线、低风险 |
| 数据修复 | `pg_restore` 从合并前 `pg_dump` 备份；或合并脚本自身事务 `ROLLBACK`（验证失败即回滚，原子） |
| 回填 | 重跑幂等（仅更新 `IS NULL`） |

### 4.3 失败恢复方案

- **合并事务失败**：自动 `ROLLBACK`，库状态不变；重跑脚本（已合并组消失，脚本需跳过已不存在的冗余 id，幂等）。
- **rebuild 单事件失败**：`PropagationService.rebuild_for_event` 已在 `try/except ValueError` 中隔离（见 `aggregator.py:498-504` 模式），单事件失败不致命，可单独重试。
- **回填失败**：重跑（仅 `WHERE dedup_key IS NULL`），幂等。
- **唯一索引创建失败**（发现重复 key）：暂停，查 `GROUP BY dedup_key HAVING count>1` 定位遗漏合并的组，回到 3.3 补合并后再建索引。
- **全程兜底**：合并前 `pg_dump` 全库备份，任何不可逆步骤前均有可恢复点。

---

## 5. 风险评估

### 5.1 聚合锁风险
- **锁未释放（异常路径）**：缓解 = `try/finally` 中 `release_advisory_lock` + `db.close()`（连接关闭 PG 自动回收）；本助手 release 对未持锁安全。
- **skip 导致手动聚合被吞**：缓解 = 下一次自动聚合兜底处理未关联舆情（增量幂等）；前端区分 `skipped` 提示，不报错误。
- **与 scheduler 锁 key 冲突**：缓解 = 两个 key 由不同 seed 派生，物理隔离。

### 5.2 唯一约束风险
- **误拦正常新事件（哈希碰撞）**：64 hex SHA1 覆盖成员 url 全集，碰撞需"完全相同文章集合"，概率可忽略；即便发生，2.5 回退逻辑也会挂载而非失败。
- **回填顺序错误**：缓解 = 必须先合并再去重键/建唯一索引（4.1 顺序硬约束）。
- **key 冻结后不随成员增长更新**：设计取舍——key 仅为"创建时刻竞态"防御，成员后续增长不重算，避免与"仅部分重叠的不同事件"误撞；真正的持续去重由锁 + 软/硬合并兜底。已在 2.1/2.5 明示。

### 5.3 历史合并风险
- **keep 选错丢告警**：缓解 = keep 规则优先 `alert_records` 最多（3 条全在 keep 侧实测），且预校验 alert 总数合并前后不变。
- **rebuild 失败残留重复节点**：缓解 = rebuild 在提交后单独跑，失败可重试；最终复验 `dangling parent = 0`。
- **FK NO ACTION 阻断删除**：缓解 = 严格按"先迁子表、后删 events"顺序（3.3）。

### 5.4 对线上功能影响
- 采集主流程不受影响（聚合异常安全，`auto_aggregate_after_collect` 捕获所有异常）。
- 事件中心列表：硬合并后重复消失，无查询改动；软合并需加过滤（3.4）。
- 调度/预警/传播树/告警推送：无契约变化。
- `ADD COLUMN` 与 `CREATE INDEX CONCURRENTLY` 均为 PG 在线操作，**无停机**。

---

## 6. Phase 7.5 实施建议顺序

| 序 | 动作 | 类型 | 阻断依赖 | 在线安全 |
|---|---|---|---|---|
| 1 | 新增 `app/core/advisory_lock.py` 通用助手；在 `auto_aggregate_after_collect` 与手动聚合入口加聚合锁（skip-if-not-acquired） | 代码 | 无（独立） | ✅ 立即防再生 |
| 2 | `_create_event` 计算 `dedup_key` + 唯一冲突回退挂载（2.5） | 代码 | 无（列不存在时降级 no-op） | ✅ |
| 3 | `pg_dump` 全库备份 → 事务合并 43 组（3.3）→ 验证 → 提交 → rebuild 43 保留事件 | 数据修复 | 依赖 1（锁已防新重复，合并期安全） | ✅ 事务原子 |
| 4 | Alembic p8：加 `events.dedup_key`（及可选软合并字段） | 迁移 | 无 | ✅ 在线 |
| 5 | 回填 `dedup_key`（仅 `IS NULL`） | 数据 | 依赖 3 完成 | ✅ 幂等 |
| 6 | Alembic p9：`CREATE UNIQUE INDEX CONCURRENTLY uq_events_dedup_key`（预校验无重复 key） | 迁移 | 依赖 3+5 | ✅ 在线 |
| 7 | 关停 `:8011` 冗余后端实例 | 运维 | 无 | ✅ |
| 8 | （可选）软合并 `superseded_by` + 查询过滤（仅当合规要求零删除） | 代码+迁移 | 依赖 3 | ⚠ 需改查询层 |
| 9 | 验收：复跑审计查询（重复组=0、scheduler 单实例、聚合锁持有者唯一） | 验证 | 全部 | — |

**优先即做**：1 → 3（先锁住再生、再清存量）；2/4/5/6 为纵深防御，可紧随；7 收口多实例隐患；8 按需。

---

## 7. 结论

Phase 7.5 以"**锁防再生 + 合并清存量 + 键做幂等**"三层递进：
1. **聚合 advisory lock**（复用 scheduler 范式、新增通用助手）从根上消除并发双物化，零性能/体验代价；
2. **事务化合并 43 组**（keep 规则确定、子表迁移零丢失、rebuild 去重）彻底消除存量重复；
3. **`dedup_key` + 部分唯一索引 + 冲突回退**形成事件级幂等闭环，使任何未来并发/重试都安全。

全程在线安全、可回滚、可失败恢复，未引入新基础设施依赖。本方案为**设计稿**，落地须另立实施阶段并严格遵循 Phase 7 已确立的备份/验证/事务纪律。
