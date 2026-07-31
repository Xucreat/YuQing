# 采集幂等性加固 · Phase 7 收口报告

> 收口日期：2026-07-24
> 收口性质：**纯文档归档，零代码改动**（遵守"禁止新增代码"）
> 关联阶段：只读排查 → 实施加固 → 安全审计 → 生产准备 → 生产实施 → 最终验收 → **收口（本阶段）**

---

## 0. 收口说明

本阶段仅做归档与文档更新，不新增任何功能代码、不修改生产库数据、不触发迁移。
全部加固代码与数据清理已在"生产实施"与"最终验收"阶段完成并验证通过，本报告负责：
1. 生成**最终变更清单**并逐项标记涉及文件；
2. 更新项目架构文档（`docs/architecture.md`）；
3. 输出**当前系统可靠性基线**；
4. 列出**后续技术债**，供下一阶段排期。

---

## 1. Phase 7 阶段回顾与定位

| 子阶段 | 产出 | 状态 |
| --- | --- | --- |
| 根因只读排查 | 双调度器（多后端实例）+ url 无约束 | ✅ |
| 实施加固 | scheduler 单例锁 + 两个 DB 约束 + 清理 SQL | ✅ |
| 安全审计 | 发现 propagation_nodes 自引用 NO ACTION 阻断缺陷并修正 | ✅ |
| 生产准备 | 清理 SQL 增加 0.5/0.6 步骤 + 测试库演练 ALL PASS | ✅ |
| 生产实施 | 备份→清理COMMIT→迁移→rebuild→单例验证 | ✅ 零异常零回滚 |
| 最终验收 | 24h 数据质量/调度/一致性全达标，评级 A- | ✅ |
| **收口（本次）** | 变更清单+架构文档+可靠性基线+技术债归档 | **进行中** |

**约束遵守（全程）**：未改业务代码（service/common/采集器）、未引入 Redis/ES/MQ、未碰未验证数据、生产清理在单事务内验证全 0 后才 COMMIT。

---

## 2. 最终变更清单（含文件标记）

图例：`[MODIFIED]` 修改既有文件 ｜ `[NEW]` 新增文件 ｜ `[DATA]` 数据/脚本（一次性）

| # | 文件 | 标记 | 关键改动 | 作用 | 验证 |
| --- | --- | --- | --- | --- | --- |
| 1 | `backend/app/core/scheduler.py` | `[MODIFIED]` | 新增 `SCHEDULER_ADVISORY_LOCK_KEY`(L23–28)、`_try_acquire_scheduler_lock()`(L59–81)、`_release_scheduler_lock()`(L84–103)；`start_scheduler` 加锁判断(L114–119)、`stop_scheduler` 释放锁(L130) | 跨进程 scheduler 单例，从根上杜绝"定时采集触发两次→同文章重复入库" | pg_locks 恰 1 持有者；:8011 日志确认跳过；10:30 起单批 |
| 2 | `backend/app/models/opinion.py` | `[MODIFIED]` | `__table_args__` 新增 `Index("ix_opinions_url_unique","url",unique=True,postgresql_where=text("url<>''"))`(L92–96) | url 部分唯一索引（空串允许多条），DB 层兜底阻挡同 url 重复舆情 | 索引在生产库存在 |
| 3 | `backend/app/models/event_opinion.py` | `[MODIFIED]` | `__table_args__` 新增 `UniqueConstraint("event_id","opinion_id",name="uq_event_opinions_event_opinion")`(L20–26) | 事件-舆情关联唯一，阻挡字面重复行导致传播树失真 | 约束在生产库存在 |
| 4 | `backend/alembic/versions/p7_event_opinions_unique.py` | `[NEW]` | `revision="p7evtuniq01"`, `down_revision="p6urluniq01"`；`upgrade` 建 `uq_event_opinions_event_opinion`，`downgrade` 删除 | 将事件关联唯一约束纳入版本化迁移，可回滚 | `alembic upgrade head` 成功，current=p7evtuniq01 |
| 5 | `backend/cleanup_duplicate_opinions.sql` | `[DATA]` | 事务内清理脚本；步骤 0.5（删前并回 event 关联防丢失）、0.6（置空自引用 parent_id）、严格删除顺序 | 一次性清理存量重复数据，清理前全部 SELECT 验证 | 测试库演练 ALL PASS；生产执行 COMMIT，删冗余舆情 34 / event_opinions 63+10 / propagation_nodes 61 / alert_records 5 |

**涉及文件统计**：核心代码改动 3 个（scheduler / opinion / event_opinion），新增迁移 1 个，一次性脚本 1 个。
**业务代码零改动**：`collectors/service.py`、`ai_service.py`、`aggregator.py`、`common.py` 均未触碰。

---

## 3. 当前系统可靠性基线

> 评级：**A-（生产可靠，附观察期）**。唯一扣分：加固代码 10:14 上线，加固后完整观察窗口仍需积累（每整半点一个调度点，约 48 点/24h）。

### 3.1 数据质量基线
- `opinions.url` 精确重复：**0 组**（全库 966 条 + 近 24h 新增 297 条内均为 0）
- `event_opinions` 字面重复：**0 行**
- 舆情总量：**966**（1000 − 34 冗余，账目吻合）

### 3.2 调度基线
- 单实例运行：pg_locks 中 advisory lock **恰好 1 个持有者**（:8000 实例）
- 批次唯一性：10:30（锁生效后首个触发点）起**每整半点仅 1 批**，旧双触发（每点 2 批）已消失
- 非 success 运行：24h 内仅 1 条 failed（2026-07-23 11:00 邯郸源，加固前历史事件，已自愈）

### 3.3 数据一致性基线（7 项全 0）
悬空 `parent_id`、4 类孤儿引用（propagation_nodes/event_opinions×2/alert_records）、空事件、跨事件父引用均为 0。

### 3.4 约束与版本基线
- `ix_opinions_url_unique`（部分唯一索引）✅ 在位
- `uq_event_opinions_event_opinion`（唯一约束）✅ 在位
- `alembic_version` = `p7evtuniq01`（head）

---

## 4. 后续技术债清单

| 优先级 | 技术债 | 影响 | 建议处置 |
| --- | --- | --- | --- |
| 中 | `:8011` 冗余后端实例仍在运行 | 资源浪费；虽已被单例锁抑制双触发，但仍持连接 | 择机 `taskkill` 关停，改为**单实例部署**（容器/进程编排层保证 1 副本） |
| 低 | 采集层 url 冲突 `IntegrityError` 未捕获 | 约束生效后因并发/竞态可能抛异常导致单条入库失败 | 观察日志；必要时在 `CollectorService` 捕获 `IntegrityError` 按"已存在"跳过（**下一阶段评估，本期未做**） |
| 低 | url 精确匹配不拦截参数/大小写变体 | 极少数站点同文章带 `?id=1` 与无参视为不同 url | 政府网站源实测 0 例；暂缓 url 归一化，先观察 |
| 低 | 锁会话闪断的理论双调度窗口 | advisory lock 随会话释放瞬间，若恰逢触发点存在极小竞态 | 单实例部署后自然消除；必要时加 `pg_advisory_lock` + 启动幂等检查 |
| 低 | 清理脚本未纳入运维手册 | 后续若再出现重复，缺标准化处置 SOP | 将 `cleanup_duplicate_opinions.sql` 执行纪律写入运维文档/Runbook |
| 低 | 事件传播树 `rebuild_for_event` 无自动化 | 当前依赖人工在清理后触发 | 评估监听清理事件自动 rebuild，或纳入定时维护任务 |

---

## 5. 归档结论与回滚预案

### 归档结论
Phase 7「采集幂等性加固」**正式收口**。采集重复（同数据源同文章）与双触发（多实例）两大根因已被纵深防御消除：
- **预防层**：url 部分唯一索引 + 事件关联唯一约束（DB 层硬约束）；
- **调度层**：PG advisory lock 跨进程单例（根因治理）；
- **存量层**：一次性事务化清理 + rebuild 传播树（已执行、已验证）。

系统已进入**可靠性基线 A-**，可安全进入下一阶段开发。

### 回滚预案（如需）
1. **未 COMMIT 场景**：`ROLLBACK`（本次生产已 COMMIT，不适用）。
2. **已 COMMIT 数据回滚**：`pg_restore` 还原 `backup/opinion_db_pre_cleanup_20260724_103142.dump`。
3. **约束回滚**：`alembic downgrade p6urluniq01`（撤销 p7 事件关联唯一约束）。
4. **单例锁回滚**：删除 `scheduler.py` 中 `_try_acquire_scheduler_lock` 调用（回到进程内 `if scheduler is not None` 防护，不推荐）。

### 关键产物存档
- 生产实施报告：`采集幂等性加固_生产实施报告.md`
- 最终验收报告：`采集幂等性加固_Phase最终验收报告.md`
- 本收口报告：`采集幂等性加固_Phase7_收口报告.md`
- 数据库备份：`backup/opinion_db_pre_cleanup_20260724_103142.dump`（建议保留 ≥ 7 天）

---
*Phase 7 收口完成。后续开发可在当前 A- 基线上推进，技术债按上表优先级排期。*
