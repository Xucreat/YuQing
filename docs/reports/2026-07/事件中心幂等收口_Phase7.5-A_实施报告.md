# 事件中心幂等收口 · Phase 7.5-A 实施报告
## 事件聚合并发保护（advisory lock）

> 阶段性质：Phase 7.5-A 仅做「聚合入口并发保护」，不执行任何历史数据清理、不新增数据库字段、不修改聚合逻辑。
> 日期：2026-07-24　实施人：WorkBuddy　范围：生产代码 + 单测（测试库 `:5432/opinion_test`）

---

### 一、修改文件清单

| 文件 | 标记 | 改动 |
|---|---|---|
| `backend/app/services/event/aggregator.py` | `[MODIFIED]` | `EVENT_AGGREGATE_LOCK_KEY` 模块常量（L60-63）；`aggregate()` 入口加 advisory lock 包裹（L266 起，约 +38 行）。聚合逻辑 `_aggregate_full` / `_aggregate_incremental` **零改动**。 |
| `backend/app/core/advisory_lock.py` | `[NEW]` | 通用 PG 会话级 advisory lock 助手：`make_lock_key(seed)`（sha1→64位键）、`try_acquire_advisory_lock`、`release_advisory_lock`。集中封装 scheduler 锁与聚合锁共用的底层原语。 |
| `backend/tests/test_aggregate_advisory_lock.py` | `[NEW]` | 4 个测试：锁互斥、释放后可重入、持锁时 skip、空闲时正常执行。 |

**未改动**：`Event` / `EventOpinion` Model、`app/api/events.py`（手动聚合入口）、`app/core/scheduler.py`（仅复用其「思想」，未复制其长锁）、采集器、任何迁移、任何数据库字段。

---

### 二、设计要点（对照需求）

1. **仅修改聚合入口**：锁加在 `EventAggregator.aggregate()` 入口，自动聚合（`auto_aggregate_after_collect`）与手动聚合（`_run_aggregate_task` → `/api/events/aggregate`）都经此入口，故**两者行为一致**。
2. **复用 scheduler 锁思想，不是复制长锁**：采用与 scheduler 完全相同的机制（PG 会话级 `pg_try_advisory_lock` + sha1 派生稳定键），但语义为**「每次聚合调用的短锁」**——用独立连接持有、调用结束即释放；而非 scheduler 的「进程级长锁」。底层原语抽到 `app/core/advisory_lock.py` 共用。
3. **不新增数据库字段**：锁为纯运行时 advisory lock，无表结构/DDL 变更。
4. **不修改聚合逻辑**：仅用 `try/finally` 把原有 dispatch 包裹，内部 `_aggregate_full` / `_aggregate_incremental` 一行未动。
5. **自动/手动行为一致**：两者在「未获锁」时都返回 `{"skipped": True, "reason": "another aggregation in progress"}`；调用方（采集后自动聚合 / 后台任务轮询）对该结果透明。
6. **锁获取异常 → 保守放行**：`pg_try_advisory_lock` 抛异常（如 DB 短暂不可用）时设 `acquired=True` 放行本次聚合，避免聚合静默丢失；正常并发由 `acquired=False → skipped` 处理。

---

### 三、关键实现决策与踩坑

**踩坑：advisory lock 经 SQLAlchemy 连接池残留（已修复）**
- 初版把锁加在 `aggregate()` 的 `db` 会话上。验证发现：合跑回归时 `test_risk_level_mapping` 报 `KeyError: 'created'`——即 `aggregate()` 误返回 `{"skipped": True}`。根因：会话级 advisory lock 随 `db.close()` 归还连接池后**不会自动释放**，被后续测试复用的连接「误持锁」，导致后续 `aggregate()` 误判为并发冲突而 skip。
- **修复**：锁改由**独立连接**持有（`engine.connect()`），在 `finally` 中显式 `pg_advisory_unlock` 并 `conn.close()`。锁随连接关闭释放，绝不污染聚合用的 `db` 会话连接池。这与 scheduler 用 `engine.connect()` 持锁的范式一致。
- 互斥性不受影响：advisory lock 按 **key** 全局互斥，与持有它的连接无关；并发聚合各自用独立连接抢同一 key，仍严格串行。

**验证手段**：用独立连接持锁后，原「持锁 skip」测试仍成立（holder 用任意连接持有 key，aggregate 用自身连接抢同一 key 失败→skip），证明跨连接互斥正确。

---

### 四、风险分析

| 风险 | 等级 | 说明 / 缓解 |
|---|---|---|
| 锁未释放导致聚合被长期跳过 | 低 | `finally` 中显式 `pg_advisory_unlock` + `conn.close()` 双重保险；连接关闭时 PG 自动回收会话级锁。 |
| DB 抖动时误跳过聚合 | 低 | 锁获取异常已设为「放行」；正常并发才 skip。被跳过的增量聚合由下一周期自动聚合兜底（与现有幂等设计一致）。 |
| 长事务持有锁阻塞并发聚合 | 低 | 锁仅在单次 `aggregate()` 调用期间持有（含 commit + 传播重建），典型秒级；不会跨调度周期。 |
| 多个后端实例同时聚合 | 已消除 | advisory lock 跨进程全局互斥，:8000 与 :8011 实例也串行；与 Phase 7 scheduler 锁叠加更稳。 |
| 前端手动聚合「skip」体验 | 低（建议） | 被 skip 时任务结果为 `{"skipped": true}`；建议后续前端提示「聚合进行中，已合并到正在运行的任务」（不改本次逻辑）。 |
| 生产生效需重启后端 | 中 | 当前运行中的 uvicorn 仍是旧 aggregator 代码，**新锁尚未生效**。需重启加载新代码（见第六节）。 |

---

### 五、测试结果（测试库 `:5432/opinion_test`，`DB_IDENTITY_CHECK=off`）

**新增测试（`tests/test_aggregate_advisory_lock.py`）：4 passed**
- `test_advisory_lock_mutual_exclusion` —— 两会话不可同时持锁
- `test_advisory_lock_reacquire_after_release` —— 释放后可重入
- `test_aggregate_skips_when_lock_held` —— 持锁时 `aggregate()` 返回 skipped（dry_run 只读）
- `test_aggregate_runs_when_lock_free` —— 空闲时正常执行返回统计

**回归（`test_events_aggregator_v2.py` + `test_events.py` 合跑）：19 passed，3 failed**
- 3 个失败为**基线既有失败**（在无本改动的基线中同样失败）：`test_api_contract_unchanged`、`test_same_keyword_one_event`、`test_api_aggregate`——属环境/种子数据相关，**与本次并发保护无关，不在 Phase 7.5-A 范围**。
- `test_risk_level_mapping` 在修复连接池残留后**合跑恢复通过**（此前因池残留误 skip 而失败），证明锁残留问题已闭环。
- `test_api_list_pagination` 在基线为偶发 ERROR（数据相关），本次合跑通过，非本次引入。

**结论**：本改动**未引入任何新失败**；既有的 3 个失败与本次无关，建议单独排期修复（不在本阶段）。

---

### 六、是否可进入历史重复清理阶段（Phase 7.5-B）

**可以进入，但建议先完成一项运维动作**：

1. ✅ 并发防护已在代码层落地并测试通过：Phase 7 scheduler 锁（杜绝双触发）+ 本阶段聚合入口锁（杜绝并发双物化）形成双层防护，重复事件的根因（并发双物化）已被代码关闭。
2. ⚠️ **生产生效前置**：当前运行中的 uvicorn 仍加载旧 `aggregator.py`，新锁尚未在生产生效。在跑 Phase 7.5-B 历史合并脚本之前，**应先重启后端加载新代码**（用既有安全重启流程：定位 :8000 uvicorn PID → `taskkill /F /PID` → `run_in_background` 启动），使防护实时生效；否则合并期间若发生「手动 + 自动」并发聚合，旧代码仍可能双物化。
3. 可选：关停冗余 `:8011` 实例（Phase 7 已确认其 scheduler 被跳过，但单实例部署可进一步消除一切竞态）。

**进入 Phase 7.5-B 的条件**：后端已重载新代码（新锁生效）后，即可执行《事件中心重复事件审计报告》中的中期方案——事务化合并 43 组 A 类重复事件（keep=传播节点最多→告警最多→最小 id），零舆情丢失，提交后 `rebuild_for_event`。

---

### 七、部署生效步骤（建议，待确认后执行）

```
1. 定位 :8000 uvicorn PID：netstat -ano | findstr :8000
2. 强杀旧进程：taskkill /F /PID <pid>
3. 后台启动新代码：backend/.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
4. 验证：日志出现聚合调用；可选 pg_locks 观察聚合锁仅持有于聚合运行期。
```
（不自动执行，待你确认是否现在重启生产后端。）
