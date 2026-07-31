# Phase 8-E 舆情运营批量操作优化 · 实施报告

> 生成时间：2026-07-30  
> 阶段：第二阶段（功能实施 + 端到端验收）  
> 状态：✅ 已上线，23/23 项端到端测试全部通过

---

## 一、需求回顾与确认事项

需求：① 舆情列表支持全选/勾选，批量修改情感；② 支持删除舆情列表中的舆情。

实施前已与管理员确认四项边界，本阶段严格按确认事项落地：

| # | 确认事项 | 落地结果 |
|---|---------|---------|
| 1 | 删除权限收紧 | `DELETE /api/opinions/{id}` 与新增 `DELETE /api/opinions/batch` 均改为 **admin** 权限，analyst 不再具备删除权限 |
| 2 | 批量数量上限 | 批量 ids 上限 **200**，超过返回 **400** 参数错误（单条/批量情感、单条/批量删除均生效） |
| 3 | 全选范围 | V1 仅支持**当前页全选**，不做跨页全局选择 |
| 4 | 审计策略 | 批量情感：逐条 `OPINION_SENTIMENT_UPDATE`；单条删除：单条 `OPINION_DELETE`；批量删除：一条**汇总** `OPINION_DELETE`（details 保存数量与 ID 列表） |

---

## 二、修改文件清单

### 后端（2 个文件，最小范围）
| 文件 | 改动 |
|------|------|
| `backend/app/api/opinions.py` | ① 新增公共函数 `_delete_opinion(...)`（级联清理 + 可选审计）；② 新增 `PATCH /batch`、`DELETE /batch`；③ 重写 `DELETE /{opinion_id}`（改 admin 权限）；④ 路由顺序修正（`/batch` 定义于 `/{opinion_id}` 之前） |
| `backend/app/schemas/opinion.py` | 新增 `OpinionBatchUpdate`（ids, sentiment）、`OpinionBatchDelete`（ids） |

### 前端（1 个文件 + 重新构建部署）
| 文件 | 改动 |
|------|------|
| `frontend/src/views/Opinions.vue` | ① 表头/行首增加「选择列」checkbox（`@click.stop` 防整行 `openDetail` 误触）；② 批量操作栏（已选 N 条 / 修改情感 popover / 删除 / 取消选择）；③ 行末「删除」按钮（仅 `canDelete` 可见）；④ `colCount` 动态；⑤ `loadData` 删空末页自动 `page--` 回退 |
| `backend/app/static/...`（构建产物） | `vite build` 成功 → `python backend/_d.py` 部署 42 个文件，含 `Opinions-BndpuuaF.js`（已验证含 batch 全部逻辑） |

> 注：前端为纯静态资源，由 uvicorn 直读 `backend/app/static`；后端改动须重启 uvicorn 生效（已重启）。

---

## 三、API 变化

### 新增 `PATCH /api/opinions/batch` — 批量修改情感
- 权限：`opinions:write`（analyst / admin 均可）
- 请求体：`{ "ids": [int], "sentiment": "positive|negative|neutral" }`
- 校验：ids 去重；>200 返回 400；sentiment 非法返回 400
- 返回：`{ "updated": int, "skipped": int, "failed": int, "failed_ids": [int] }`
  - 与原值相同计 `skipped`；记录不存在计 `failed`；逐一写入 `OPINION_SENTIMENT_UPDATE` 审计

### 新增 `DELETE /api/opinions/batch` — 批量删除
- 权限：`require_admin`（admin 或 is_superuser）
- 请求体：`{ "ids": [int] }`
- 校验：ids 去重；>200 返回 400
- 行为：循环复用 `_delete_opinion(audit=False)` 做级联清理，**统一提交一次**，并写一条**汇总** `OPINION_DELETE` 审计
- 返回：`{ "deleted": int, "not_found": int }`

### 修改 `DELETE /api/opinions/{opinion_id}` — 单条删除（权限收紧）
- 权限：由原先 `opinions:write` 改为 **`require_admin`**
- 行为：调用 `_delete_opinion(audit=True)`，写单条 `OPINION_DELETE` 审计（details 含 `id` + `title`）
- 返回：`{ "detail": "Opinion deleted", "id": int }`；不存在返回 404

> 既有 `PATCH /api/opinions/{id}`（单条情感校正，上一阶段已上线）保持不变，权限 `opinions:write`。

### 路由顺序要点
`/batch` 必须定义在 `/{opinion_id}` **之前**，否则路径参数会把 `batch` 当作 `{opinion_id}` 捕获，导致批量接口失效。已确认顺序正确。

---

## 四、数据库变化

**✅ 无数据库结构变化，无新增表/字段，无迁移脚本。**

删除走**级联 bulk delete**（`synchronize_session=False`，绕开 ORM 多对多对象删除），关联数据处理策略：

| 关联表 | 处理方式 |
|--------|---------|
| `event_opinions`（事件-舆情多对多） | 解绑（删除关联行），不删除事件 |
| `alert_records` | 保留预警，仅 `opinion_id` 置 NULL |
| `bocha_leads`（博查线索） | 保留线索，仅 `opinion_id` 置 NULL |
| `propagation_nodes`（传播链） | 先将其子节点 `parent_id` 置 NULL，再删除自身节点 |

舆情主表行删除同样用 bulk delete，避免触发 ORM 多对多级联 `StaleDataError`。

---

## 五、权限变化

| 操作 | 权限 | 说明 |
|------|------|------|
| 批量修改情感 `PATCH /batch` | `opinions:write` | analyst / admin 均可 |
| 单条修改情感 `PATCH /{id}` | `opinions:write` | analyst / admin 均可（上阶段） |
| 单条删除 `DELETE /{id}` | **admin** | ⛔ analyst 改判 403 |
| 批量删除 `DELETE /batch` | **admin** | ⛔ analyst 改判 403 |

前端 `canDelete = computed(() => isSuperuser.value)`，与后端 `require_admin`（`is_superuser` 或 `role=='admin'`）一致；无删除权限时选择列/删除按钮不渲染。

---

## 六、审计变化

| 操作 | 审计动作 | details 内容 |
|------|---------|-------------|
| 批量情感（逐条） | `OPINION_SENTIMENT_UPDATE` | `{ field, old, new }` |
| 单条删除 | `OPINION_DELETE` | `{ id, title }` |
| 批量删除（汇总一条） | `OPINION_DELETE` | `{ count, ids, not_found }` |

审计统一写入 `user_operation_logs`，复用既有 `audit_write` / `log_operation` 机制，与登录等现有写操作同套体系。

---

## 七、测试结果（端到端，23/23 PASS）

### 验证方法（生产库零风险）
破坏性删除测试**不直接跑生产库**。采用隔离克隆法：
1. `CREATE DATABASE opinion_phase8e_test TEMPLATE opinion_db`（克隆生产 16MB / 894 条舆情 / 345 条事件关联，秒级完成；前提是先停生产 uvicorn 使 opinion_db 无活跃连接）；
2. 另起独立 uvicorn 于 **8001**，指向克隆库（`DB_IDENTITY_CHECK=off`）；
3. 跑完整用例（删除的 3 条舆情仅落在克隆库）；
4. 测试后 `DROP DATABASE opinion_phase8e_test` 销毁克隆。

> 未采用「升级 opinion_test 后测试」：经核查 `opinion_test` 的 `opinions` 表缺 `relevance_score` 列，且 fresh `alembic upgrade head` 在 `alert_records` 的 ALTER 处报 `UndefinedTable` 失败，无法承载带 Opinion 查询的测试。隔离克隆法更干净、更贴近真实数据。

### 用例结果
| 分组 | 用例 | 结果 |
|------|------|------|
| A 批量情感 | A1 接口 200 / A2 返回字段齐全 / A3 DB 已更新 / A4 审计行写入 | ✅ 4/4 |
| B 单条删除+级联 | B1 接口 200 / B2 舆情已删 / B3 事件关联已解绑 / B4 预警 opinion_id 置空 / B5 传播节点已清理 / B6 单条删除审计 | ✅ 6/6 |
| C 批量删除 | C1 接口 200 / C2 返回字段齐全 / C3 舆情已删 / C4 汇总审计含 count+ids | ✅ 4/4 |
| D 权限 | D1 单条删除 analyst 403 / D2 批量删除 analyst 403 / D3 批量情感 analyst 200 | ✅ 3/3 |
| E 上限 | E1 批量情感 >200 → 400 / E2 批量删除 >200 → 400 | ✅ 2/2 |
| F 校验 | F1 非法 sentiment → 400 | ✅ 1/1 |
| — | **合计** | **✅ 23/23** |

---

## 八、实施中修复的关键缺陷

测试阶段发现并修复了**单条删除「返回 200 但未真正删除、且无审计」**的缺陷（B2/B3/B5/B6 原 FAIL）：
- 根因：`Opinion.events` 是多对多关系，`db.delete(opinion)` 触发 ORM 关联表级联删除，与手动清理冲突抛出 `StaleDataError`，被 `audit_write` 的 `else` 分支静默吞掉（业务未提交、审计回滚）。
- 修复：将「删除舆情主表行」也改为 `db.query(Opinion).where(...).delete(synchronize_session=False)`，全程 bulk delete 绕开 ORM 多对多级联；批量删除（含事件关联舆情）一并修复。

---

## 九、红线遵守声明

- ✅ 未修改风险模型 / 情感算法
- ✅ 未修改事件聚合逻辑
- ✅ 未修改传播逻辑
- ✅ 未修改数据库结构（无迁移）
- ✅ 未引入新依赖
- ✅ 生产库零写入 / 零删除（验收全程在隔离克隆上进行）

---

## 十、已知限制（V1 范围）

1. **全选仅当前页**：不支持跨页全局选择；如需全局批量，后续版本再评估。
2. **批量上限 200 条**：单次批量操作 ids 上限 200，超限返回 400。
3. **删除仅 admin**：analyst 无删除权限（按确认事项收紧）。
4. **关联保留策略**：删除舆情时，相关预警（alert_records）与博查线索（bocha_leads）仅解绑不删除，传播链子节点父引用置空；事件（event）实体保留。
5. **软删除未做**：当前为物理删除，删除后不可恢复（符合「删除舆情」语义；如需回收站机制另行设计）。
