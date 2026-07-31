# RBAC 权限收口实施报告

> 执行日期：2026-07-24｜执行范围：RBAC 权限收口（collector 收敛 + 数据源读分层 + viewer 领导查看 + 前端收口）
> 原则：保持现有 RBAC 架构、不新增角色、不改动表结构、不重构核心逻辑、不改变 JWT 设计、不引入新权限体系。

## 一、执行前只读核验（已执行，先于任何修改）

连生产库 `opinion_db`（身份门禁 VERIFIED：opinions≈1025、alembic head=`p11_phase2b2`），导出三角色当前 `role_permissions`：

| 角色 | 实施前权限数 | 实际内容 |
|---|---|---|
| admin | 0（超管返回 `*`） | — |
| analyst | 13 | alerts/read+write, dashboard, events/read+write, keywords/read+write, opinions/read+write, **propagation:read**, reports/read+write, **sources:read** |
| viewer | 4 | dashboard, events, opinions, reports（**缺 alerts:read、propagation:read**） |

**关键发现**：analyst 在库中**已含** `sources:read` 与 `propagation:read`（与计划里「analyst 增 sources:read」假设不一致）——属现状既成事实。因此本次迁移对 analyst 的两项为**幂等 no-op**，实际净变化仅为 **viewer 补 `alerts:read` + `propagation:read`**。

结论：三角色权限与种子默认值一致，无人工作过，可安全增量执行，不覆盖任何人工调整。

## 二、修改文件清单

| 文件 | 改动 | 类型 |
|---|---|---|
| `backend/app/api/collector.py` | `POST /run` 守卫 `get_current_user` → `require_admin`；`GET /status` 保持登录可读；同步更新 docstring | 代码（守卫） |
| `backend/app/api/admin_data_sources.py` | 4 个读端点 `require_admin` → `require_permission("sources:read")`；3 个写端点保持 `require_admin` | 代码（守卫） |
| `backend/alembic/versions/p12_rbac_roleperms.py` | **新增迁移（纯数据，零 DDL）**：增量 INSERT 三行绑定 | 新增迁移 |
| `frontend/src/components/AppLayout.vue` | 「采集数据」按钮加 `v-if="isSuperuser"`；`usePermission` 解构补 `isSuperuser` | 前端 |
| `frontend/src/router/index.ts` | `/alerts` 路由补 `meta.permission:'alerts:read'`；`/propagation` 路由补 `meta.permission:'propagation:read'` | 前端 |
| `backend/tests/test_rbac.py` | 新增 4 个回归用例（见第五节） | 测试 |

> 未改动：`users/roles/permissions` 管理接口、`collectors:read/write` 权限码（保留在目录中，标记为 reserved/unused）、未新增任何 `trigger/manage` 权限码、未新增角色/表/列。

## 三、权限变化前后对比

| 权限 | admin | analyst 前→后 | viewer 前→后 |
|---|---|---|---|
| alerts:read | ● | ● → ● | **— → ○** |
| propagation:read | ● | ○ → ○ | **— → ○** |
| sources:read | ● | ○ → ○（库中原已存在，无变化） | — → — |
| collectors:* | ● | — → —（接口改 admin） | — → — |
| 其余业务域 | ● | 不变 | 不变 |

**净变化**：viewer +`alerts:read`+`propagation:read`（共 4→6 项）；analyst 无实际变化（两项已存在）。两者均无任何新增写权限。

## 四、后端守卫细节

- `collector.py`：router 级依赖仍 `get_current_user`（保证 `/status` 登录可读）；`run_collector` 端点单独加 `require_admin`。语义：采集=资源消耗型基础设施操作，收敛为 admin-only。
- `admin_data_sources.py` 端点分级：
  - 读（→ `require_permission("sources:read")`）：`GET ""`（列表）、`GET /{id}/runs`、`GET /collection-logs`、`GET /collection-logs/{batch_key}/runs`
  - 写（→ 保持 `require_admin`）：`POST /test`、`POST ""`、`PATCH /{id}`
  - 效果：analyst 现可查看数据源状态/采集日志（持 `sources:read`）；viewer 无 `sources:read` → 读接口 403。

## 五、迁移与测试

**迁移 `p12_rbac_roleperms`**（down_revision=`p11_phase2b2`）：
- 使用 `INSERT ... WHERE NOT EXISTS` 幂等写入，重复执行安全；不 DELETE/UPDATE 既有绑定，绝不覆盖人工调整。
- 已应用至 **生产库 `opinion_db`**（head 现为 `p12_rbac_roleperms`）与 **测试库 `opinion_test`**（带 `DB_IDENTITY_CHECK=off`）。
- `downgrade` 按 `(role, permission)` 精确删除本次新增 3 行，不影响其他绑定。

**测试**（隔离库 `opinion_test`，护栏：指向生产 `opinion_db` 时整模块跳过）：

```
13 passed, 92 warnings in 13.31s
```
新增 4 例均通过：
- `test_collector_run_requires_admin`：未认证 401；admin 200（返回 task_id）；analyst/viewer 403（采集收敛）。
- `test_collector_status_login_only`：viewer 登录可读 200（低风险只读保持）。
- `test_data_sources_read_permission_split`：admin 200；analyst（持 sources:read）200；viewer 403。
- `test_viewer_leader_reads_after_migration`：viewer 登录 permissions 含 `alerts:read`+`propagation:read`；读接口 200。

## 六、运行时验证（生产服务器实拉）

- `POST /api/collector/run` 无 token → **401**；admin token → **200**（可触发）。
- `GET /api/collector/status` 无 token → **401**（登录校验）。
- admin `GET /api/admin/data-sources` → **200**（sources:read 分层对超管无影响）。
- 前端已重新 `vite build` 并经 `backend/_d.py` 部署至 `backend/app/static`（index.html 已更新，assets 全新 50 文件）。

## 七、保留 / 未做项（按确认要求）

1. `collectors:read` / `collectors:write` 权限码**保留在目录中、不删除、不新增 trigger/manage 权限码**，当前为 reserved/unused（无任何接口接该守卫，无运行时「管理」接口需保护，符合最小改动）。
2. 未新增角色、未改表结构、未改 JWT、未重构 RBAC 核心。
3. `GET /collector/status` 维持登录可读（低风险只读，符合确认结论）。

## 八、风险与回滚

- 回滚：`alembic downgrade -1`（撤销 p12 三行绑定）；代码改动可 `git revert` 对应文件；`/run` 如确需放宽，将 `require_admin` 改回 `get_current_user` 即可。
- 已知副作用：非超管在前端点「采集数据」将看不到按钮（已加 `v-if="isSuperuser"`），不再产生无效 403。
- 静态资源：`backend/app/static` 下存在历史多次构建遗留的 `assets.old-*` / `assets.bak_*` 孤儿目录（旧哈希，index.html 已不引用）。建议后续一次性清理（非功能问题，本回合未删除以遵守删除安全门限）。

## 九、后续建议

1. 清理 `backend/app/static` 下的孤儿 `assets.old-*` / `assets.bak_*` 目录，回收磁盘。
2. 若未来出现「运行时修改调度/采集配置」的管理 API，再按本次设计新增 `collectors:manage` 并配套 `collectors:trigger` 专接 `/run`，届时再评估拆分（当前不必要）。
