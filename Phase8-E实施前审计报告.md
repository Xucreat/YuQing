# Phase 8-E 舆情运营批量操作优化 — 实施前审计报告

> 阶段：第一阶段（只读审计）。本报告未进行任何代码/文件修改，仅做现状核对与方案设计。
> 审计时间：2026-07-30 18:02
> 待用户确认后，方进入第二阶段（功能实施）。

---

## 一、当前实现情况

### 1.1 前端（舆情列表）

| 检查项 | 结论 |
|---|---|
| 列表是否支持行选择 | ❌ 否。表格为**原生 `<table>`，非 `el-table`**，无内置多选列。 |
| 表格结构 | `Opinions.vue`：11 列表格 `table.tbl`（`table-layout:fixed; min-width:1540px`），外裹 `.tbl-scroll`（`overflow-x:auto`）。整行 `<tr @click="openDetail(row.id)">`（打开详情弹窗）。 |
| 情感修改入口 | ✅ 仅 `opinions:write` 角色可见。第 7 列情感单元格内 `el-popover`（trigger=manual）+ 竖向三胶囊（正面/中性/负面），点击单元格 `@click.stop` 拦截行点击。单条修改已上线（`chooseSentiment` → `PATCH /opinions/{id}`）。 |
| 删除入口 | ❌ 前端**无任何删除 UI**（单条/批量均无）。 |
| API 调用方式 | `frontend/src/api/index.ts`：axios 实例 `api`（`baseURL=/api`，10s 超时）。鉴权由请求拦截器注入 `Bearer` token；响应拦截器统一处理 401 登出。支持 `api.get/post/patch/delete`。 |

**分页逻辑**：`page/size/total/maxPage/pages`；翻页直接 `page=...; loadData()`。
**筛选逻辑**：`filters` reactive（source/content_type/relevance/risk_level[情感]/level/date/keyword），`loadData()` 组装查询参数；情感筛选键为 `risk_level`（注意：UI 显示"情感"但后端参数名 `risk_level`，属历史命名，本期**不改动**）。

### 1.2 后端

| 检查项 | 结论 |
|---|---|
| `PATCH /api/opinions/{id}` | ✅ 已实现（`update_opinion`）。仅接受 `sentiment`（positive/negative/neutral），非法 400；与原值相同幂等返回、不写审计；变更经 `audit_write` 记 `OPINION_SENTIMENT_UPDATE`（details 含 old/new）；权限 `require_permission("opinions:write")`。 |
| `DELETE /api/opinions/{id}` | ✅ 已实现（`delete_opinion`）。权限 `require_permission("opinions:write")`；含完整级联清理；**⚠️ 当前不写审计日志**。 |
| 级联清理逻辑 | 已在 `delete_opinion` 内联实现：<br>① `EventOpinion` 中该 opinion 的关联行删除（解绑事件）；<br>② `AlertRecord.opinion_id` 置 `NULL`（预警保留、解除关联）；<br>③ `PropagationNode` 先将其作为父节点的 `parent_id` 置空，再删除自身（删除传播链节点，避免 FK 冲突）。 |
| 权限要求 | 查看 `opinions:read`（仅校验登录）；修改情感 `opinions:write`；**删除当前为 `opinions:write`**（analyst+admin 均可）。任务要求删除收紧为 **`admin`**。 |
| 审计写入方式 | `services/audit_service.py` 的 `audit_write(db, action, operator, request, resource_type, resource_id, details)` 上下文管理器：业务在 `with` 块内 commit；成功记 `result=success`、失败回滚并记 `result=failed`（与业务同会话，不丢审计、不掩盖异常）。 |

**权限判定权威**：`core/permissions.py`
- `is_superuser_user(user)` = `user.is_superuser` 或 `user.role == "admin"`。
- `require_admin` 依赖：仅 `is_superuser_user` 通过，否则 403。
- 前端 `usePermission`：`isSuperuser` 计算属性（`auth.isSuperuser || role==='admin'`）与后端等价；`hasPermission(p)` 对超管恒真。**删除门禁前端用 `isSuperuser` 最贴切**（可排除仅持 `opinions:write` 的 analyst）。

---

## 二、修改文件列表（第二阶段将改动）

### 后端
1. `backend/app/api/opinions.py`
   - 新增 `PATCH /api/opinions/batch`（`OpinionBatchUpdate`）：循环逐条复用单条情感校验 + `audit_write(OPINION_SENTIMENT_UPDATE)`。
   - 新增 `DELETE /api/opinions/batch`（`OpinionBatchDelete`）：循环调用公共删除函数。
   - 抽离 `_delete_opinion(db, opinion_id, request, operator)` 公共函数，单条 `DELETE /{id}` 与批量 `DELETE /batch` 统一调用（保证级联清理行为一致）。
   - 单条 `DELETE /{id}` 与批量删除权限由 `opinions:write` → **`require_admin`**（收紧）。
   - 单条删除 + 批量删除均补 `audit_write(action="OPINION_DELETE", ...)`。
2. `backend/app/schemas/opinion.py`
   - 新增 `OpinionBatchUpdate`：`ids: List[int]`、`sentiment: str`（校验取值）。
   - 新增 `OpinionBatchDelete`：`ids: List[int]`。

### 前端
3. `frontend/src/views/Opinions.vue`
   - 新增「选择」列：表头全选 `<input type=checkbox>`（含半选 indeterminate 态）+ 每行勾选框；均 `@click.stop` 防误触详情。
   - 新增批量操作栏（选中数 > 0 时显示）：`已选择 N 条` + `修改情感 ▾`（popover 三胶囊）+ `删除` + `取消选择`。
   - 每行新增「删除」按钮（`@click.stop` + `ElMessageBox.confirm` 二次确认）。
   - 新增状态：`selectedIds: Set<number>`、`isAllSelected/isIndeterminate` 计算属性。
   - 权限门禁：`canEditOpinion`（现有，`opinions:write`）控制情感编辑/批量情感；新增 `canDelete = isSuperuser` 控制删除按钮与批量删除。选择列仅在 `canEditOpinion || canDelete` 时渲染。
   - 调用：`api.patch('/opinions/batch', {ids, sentiment})`、`api.delete('/opinions/batch', {data:{ids}})`。
   - 交互后处理：批量情感 → 乐观更新选中行 + 刷新列表 + 清空选择 + **保持当前分页**；删除（单/批）→ 成功后刷新，若当前页清空且 `page>1` 则 `page--`。

> 不改动：`types/index.ts`（选中态用本地 Set 即可，无需改类型）、`utils/opinion.ts`、风险模型、情感算法、事件/传播逻辑、调度、权限模型设计。

---

## 三、API 变化建议

| 方法 | 路径 | 权限 | 请求 | 响应 | 说明 |
|---|---|---|---|---|---|
| PATCH | `/api/opinions/batch`（新增） | `opinions:write` | `{ids:[int], sentiment:str}` | `{updated:int, skipped:int, failed:int, failed_ids:[int]}` | 逐条校验+审计；与原值相同计 skipped；不存在/异常计 failed。 |
| DELETE | `/api/opinions/batch`（新增） | `admin` | `{ids:[int]}` | `{deleted:int, not_found:int}` | 公共删除函数循环；不存在计 not_found。 |
| DELETE | `/api/opinions/{id}`（**权限收紧**） | `opinions:write` → **`admin`** | — | 现状 | 行为不变，仅权限收紧。 |

> ⚠️ 权限变更提示：现有单条删除对 analyst 可用；按任务「删除：admin」收紧后，**analyst 将无法删除（含原本能删的单条）**，仅 admin/超管可删。这是预期行为，但属破坏性权限变更，请在确认时一并认可。

---

## 四、风险点

1. **权限收紧副作用**：删除改 `require_admin` 后 analyst 删除能力被收回（符合任务要求，但需用户明确认可）。
2. **整行 click 误触**：勾选框、行内删除、批量按钮必须 `@click.stop`，否则打开详情弹窗。已在实施要点中强制。
3. **批量规模**：建议单次批量 `ids` 上限（如 ≤ 200），超出返回 400，避免长事务/超时；前端可分页选择规避。
4. **级联影响放大**：删除会解绑事件、置空预警、删传播节点，连带改变事件风险聚合与驾驶舱统计。此行为与现有单条删除一致（非新增风险），但批量放大影响面，需在报告中标注。
5. **审计写入量**：批量情感逐条审计（多行 `OPINION_SENTIMENT_UPDATE`）；批量删除记**单条汇总** `OPINION_DELETE`（details 含 count + id 列表）；单条删除记单条 `OPINION_DELETE`（details 含 id + title）。符合任务审计要求。
6. **删除后分页**：最后一页数据删空时须 `page--` 并刷新，否则显示空白页。
7. **全选范围**：建议 v1 仅「当前页全选」（简单、可预期），不做跨页全局选中集；如需跨页选中待后续确认。
8. **表格宽度**：新增 ~60px 选择列，`min-width` 1540 → 1600，表头/单元格补 `width:60px`。
9. **前端 `risk_level` 命名**：UI 情感筛选后端参数名 `risk_level` 属历史命名，本期不改动，避免引入无关回归。

---

## 五、实施方案（第二阶段概要，待确认后执行）

**后端**
1. `schemas/opinion.py` 加 `OpinionBatchUpdate` / `OpinionBatchDelete`。
2. `api/opinions.py`：
   - 抽 `_delete_opinion(db, opinion_id, request, operator)`（含现有级联清理 + 单条 `OPINION_DELETE` 审计）。
   - 改 `delete_opinion` 调用 `_delete_opinion` 并改 `require_admin`。
   - 加 `update_opinion_batch`（PATCH /batch，逐条审计）、`delete_opinion_batch`（DELETE /batch，循环 `_delete_opinion`，汇总审计）。
3. 重启 uvicorn 加载新路由。

**前端**
4. `Opinions.vue`：选择列 + 全选/半选 + 批量操作栏 + 行内删除 + 二次确认 + 乐观更新/刷新/分页回退。
5. `vite build` + `python backend/_d.py` 部署。

**测试**
6. 后端（requests 端到端）：单条情感/批量情感/单条删除/批量删除/无权限(analyst)删除 403/关联数据清理正确。
7. 前端：全选/取消/半选、操作栏显示、删除确认、分页保持、末页自动回退。

**最终交付**
8. 生成《Phase 8-E 舆情运营批量操作优化实施报告》（含修改文件清单、API 变化、数据库变化=无、权限变化、审计变化、测试结果、已知限制）。

---

## 六、待确认事项（请回复后进入第二阶段）

- [ ] 确认删除权限收紧为 `admin`（analyst 不可删）符合预期。
- [ ] 确认批量 `ids` 上限（建议 200）。
- [ ] 确认全选范围为「当前页」（v1）。
- [ ] 确认审计策略：批量情感逐条、批量删除汇总一行、单条删除各一行。
- [ ] 确认无误后回复「实施」或「按推荐实现」。
