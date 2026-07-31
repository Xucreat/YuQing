# 大厂关键词历史污染数据治理 · Phase X-History-1A 实施报告

> 阶段定位：Phase X-History-0 只读审计通过后的**历史数据治理实施**（仅标记、不删除）。
> 执行前置：DB 身份门禁 VERIFIED（opinions=932，≥100）；生产库 `opinion_db` @ `127.0.0.1:5432`。
> 红线遵守：**未删除任何 opinion / event / event_opinions / propagation_nodes**；完整历史可追溯（原 region_id 保留）。
> 本阶段**未修改 Dashboard 查询逻辑**（收口留 Phase X-History-1B）。

---

## 1. 修改文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/alembic/versions/p29_history_geo_filtered.py` | 新增迁移 | `opinions` 加 `geo_filtered` BOOLEAN nullable；`events.ck_events_status` 约束扩展加入 `'deprecated'`。`down_revision = p29_report_templates`（与既有并行 p29 线性化，避免多 head）。 |
| `backend/app/models/opinion.py` | 修改 | 新增 `geo_filtered: Optional[bool]` 字段（nullable, default=False），含治理语义注释。 |
| `backend/app/models/event.py` | 修改 | `ck_events_status` CheckConstraint 合法值扩展为 `('active','verifying','processing','resolved','closed','deprecated')`。 |
| `backend/_history1a_seed.py` | 新增（治理脚本） | oracle 驱动：推导 73 噪声意见 + 12 幻影事件，执行 UPDATE 标记。幂等、零删除。 |
| `backend/_history1a_rollback.sql` | 新增（回滚脚本） | 撤销治理的 SQL（不自动执行，安全留存）。 |
| `backend/_history1a_result.json` | 新增（artifact） | 噪声/真实/幻影事件 id 清单 + before/after 统计。 |

> 说明：`p29_report_templates` 是与本任务无关的既有迁移（同样以 `p28_anspire_provider` 为父），形成双 head；本迁移通过 `down_revision` 链式接在其后，使全链单一 head=`p29_history_geo_filtered`。**未改动该既有迁移**。

---

## 2. 数据变更统计（基于 _audit_dachang_backtest.json oracle）

### 2.1 opinions.geo_filtered（仅标记）
- **73 条噪声意见** → `geo_filtered = TRUE`（22 条原错标大厂区 id=1、51 条原错标廊坊市 id=12）。
- **49 条真实意见** → 保持 `NULL`（未被标记）。校验：`真实意见被误标记数 = 0`，`真实意见 geo_filtered=NULL 数 = 49` ✅

### 2.2 events.status（仅标记，复用既有字段）
- **12 个 100% 噪声幻影事件** → `status = 'deprecated'`（原均为 `active`）。
  - 事件 id：`397,400,405,409,449,466,468,547,550,551,562,563`
- 全部由程序重新推导并与 History-0 交叉验证（期望 12，实得 12）。

### 2.3 级联对象（按用户要求**保留，未删除**）
| 对象 | 行数 | 状态 |
|---|---|---|
| `event_opinions`（12 幻影事件关联） | 30 | 保留 ✅ |
| `propagation_nodes`（12 幻影事件关联） | 30 | 保留 ✅ |
| `alert_records` | 0 关联 | 无影响（噪声/幻影事件本就 0 预警） |

---

## 3. Before / After 数量

| 指标 | Before | After | 说明 |
|---|---|---|---|
| opinions.geo_filtered=TRUE | 0 | **73** | 噪声标记 |
| events.status='deprecated' | 0 | **12** | 幻影事件标记 |
| 真实意见(geo_filtered=NULL) | 49 | 49 | 不变 ✅ |
| event_opinions 总数 | 不变 | 不变 | 零删除 ✅ |
| propagation_nodes 总数 | 不变 | 不变 | 零删除 ✅ |
| 大厂区(id=1) 舆情总数 | 44 | 44 | 数据未删；**逻辑去噪后 = 22**（44−22 噪声） |
| 廊坊市(id=12) 舆情总数 | 740 | 740 | 数据未删；**逻辑去噪后 = 689**（740−51 噪声） |

> 注：本阶段仅打标记，物理行数不变；上表「去噪后」为 Phase X-History-1B 接入 Dashboard 排除条件（`WHERE geo_filtered IS NOT TRUE`）后预期的统计口径。

---

## 4. 回滚方案

**原则**：本阶段未删除任何数据，回滚即为两行反向 UPDATE，安全可逆。

```sql
-- 文件：backend/_history1a_rollback.sql（已生成，需手动确认后执行）
BEGIN;
UPDATE opinions SET geo_filtered = NULL
  WHERE id = ANY(ARRAY[1252,1253,...,2171]);   -- 73 个噪声 id
UPDATE events SET status = 'active'
  WHERE id = ANY(ARRAY[397,400,405,409,449,466,468,547,550,551,562,563]);
COMMIT;
```

**约束回滚注意**（仅当需回退 p29 迁移时）：
- 直接 `alembic downgrade` 会先尝试把 `ck_events_status` 重建为不含 `'deprecated'` 的旧约束，若仍有 `deprecated` 行将**失败**。
- 正确顺序：先执行上面的数据回滚（events 恢复 `active`）→ 再 `alembic downgrade -1`（p29），此时旧约束重建不与残留数据冲突。
- 若只想撤销数据标记而保留 `geo_filtered` 列/约束，仅执行上面 SQL 的 UPDATE 部分即可。

---

## 5. 风险与后续

### 5.1 已知边界（非阻塞，建议 1B 一并处理）
- `app/api/events.py` 的 `EVENT_STATUS_LABELS` / `NEXT_EVENT_STATUS` 字典**未含 `'deprecated'`**。本阶段未改 API（属 Dashboard 收口范畴外）。影响：管理员若在 UI 手动对某 deprecated 事件改状态时，该端点读 `EVENT_STATUS_LABELS[old_status]` 会 KeyError。建议 Phase X-History-1B 顺带补 `'deprecated': '已废弃'` 标签与合理流转规则，使系统自洽。
- 当前运行实例（uvicorn PID 9940）加载的是 1A 之前的 ORM 模型，本阶段 schema 为**纯加法**（新增可空列 + 约束扩展），不影响运行时；但建议进入 1B 改 Dashboard 查询前**重启 uvicorn** 以加载含 `geo_filtered` 的新模型。

### 5.2 验收基线（移交 1B）
- 大厂区按地域统计：去噪后 **22**（原 44）。
- 廊坊市按地域统计：去噪后 **689**（原 740）。
- 12 个 deprecated 事件应在事件列表中默认排除（或显式标注「已废弃」）。

### 5.3 完整性校验（已执行，全绿）
```
真实意见被误标记数 = 0
真实意见 geo_filtered=NULL 数 = 49
幻影事件 deprecated 数 = 12
幻影事件 event_opinions 保留 = 30
幻影事件 propagation_nodes 保留 = 30
alembic_version = p29_history_geo_filtered
ck_events_status 含 'deprecated' = True
opinions.geo_filtered 列存在(nullable boolean) = True
```

---

## 6. 结论
Phase X-History-1A 已按需求完成：**73 条噪声意见标记 `geo_filtered=true`、12 个幻影事件标记 `deprecated`**；**零删除、完整可追溯**（原 region_id 全部保留）。治理效果待 Phase X-History-1B 在 Dashboard 查询中接入 `geo_filtered` 排除条件后正式收口显现。
