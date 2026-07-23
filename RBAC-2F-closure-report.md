# Phase RBAC-2F 关闭报告：RBAC 初始需求闭环与企业级审计体验补齐

> **阶段定位**：RBAC-2B（迁移）/2C（后端测试+审计）/2D（前端闭环）/2E（浏览器验收）之后，对照《RBAC-1-现状审计报告.md》第 8、9 节做只读差异审计，确认仍有 4 项最初明确要求未实现。本阶段**仅补齐这 4 项**，不重新设计、不扩展权限模型。
> **执行纪律**：先只读审计 → 最小实施 → 构建/测试/浏览器验收 → 关闭。未扩大范围。
> **日期**：2026-07-23

---

## 1. 阶段目标

补齐 RBAC-1 最初明确要求但尚未实现的 4 项前端能力，使 RBAC-1 → RBAC-2F 真正完成需求闭环：

1. 新增登录日志查看页 `LoginLogs.vue`
2. 新增操作日志查看页 `OperationLogs.vue`
3. 为 `Users.vue` 增加用户详情抽屉（基本/角色/权限来源/登录历史/操作历史）
4. 将 `Users.vue` 统一为既有 `el-table` / `el-dialog` 风格

除此之外不主动扩展范围。

---

## 2. 初始缺口（来自 RBAC-1 审计，本阶段前仍缺失）

| # | 最初要求（RBAC-1 §8.3） | 阶段前状态 |
|---|---|---|
| 1 | 登录日志查看页 `LoginLogs.vue` | 后端 `/api/login-logs` 已就绪；前端无页面/路由/菜单 |
| 2 | 操作日志查看页 `OperationLogs.vue` | 后端 `/api/operation-logs` 已就绪；前端无页面/路由/菜单 |
| 3 | `Users.vue` 用户详情抽屉（角色/权限来源/登录历史/操作历史） | 仅有列表+增删改，无抽屉，点击行无反应 |
| 4 | `Users.vue` 统一 `el-table` 风格 | 仍是手写 `<table class="tbl">` + 自定义 `.modal` |

---

## 3. 实际修改文件

**仅前端，零后端改动：**

| 文件 | 动作 | 说明 |
|---|---|---|
| `frontend/src/views/LoginLogs.vue` | 新增 | 登录日志页 |
| `frontend/src/views/OperationLogs.vue` | 新增 | 操作日志页 |
| `frontend/src/views/Users.vue` | 重构 | `el-table` 化 + `el-drawer` 详情 + `el-dialog` 表单 |
| `frontend/src/router/index.ts` | 编辑 | 新增 `/login-logs`、`/operation-logs` 路由（含 `permission` meta） |
| `frontend/src/components/AppLayout.vue` | 编辑 | 新增「登录日志」「操作日志」菜单项（`hasPermission` 门控） |

> 未新增任何后端文件、迁移、库字段、权限码；未修改 `require_permission` / `require_admin` / `get_user_permissions` / `is_superuser_user` / `user_roles` / `role_permissions` / `permissions` / `roles`。

---

## 4. LoginLogs 实现

- **路由** `/login-logs`：`requiresAuth: true` + `permission: 'login_logs:read'`；无权限直访被 `router.beforeEach` 拦截回退 `/dashboard` 并提示「无权限访问该页面」。
- **菜单**：`AppLayout.vue` 中 `v-if="hasPermission('login_logs:read')"` 显示「登录日志」，未使用 `role==='admin'` 硬编码。
- **页面**：复用既有 `el-card.table-card` + `<el-table stripe>` + `<el-pagination background layout="total,prev,pager,next">` + `el-tag` + `el-button link`，与 `Alerts.vue` 风格一致。
- **字段（全部为后端真实返回，无伪造）**：用户名、登录时间、IP 地址、登录结果（`el-tag`：成功/失败/退出）、失败原因、用户代理/设备。
- **分页**：真实后端分页（`page`/`size`/`total`），`size` 默认 20。
- **筛选**：后端支持的 `username`、`status` 过滤已实现。

---

## 5. OperationLogs 实现

- **路由** `/operation-logs`：`requiresAuth: true` + `permission: 'audit_logs:read'`；无权限行为与 LoginLogs 一致。
- **菜单**：`v-if="hasPermission('audit_logs:read')"`，不硬编码 `role`/`isSuperuser`。
- **页面**：同样 `el-table` 风格。
- **字段（后端真实返回）**：操作人、操作类型（`el-tag`）、资源类型、资源 ID、操作结果（成功/失败）、操作时间、IP 地址、详情（`details_json`）。
- **分页**：真实后端分页。
- **筛选**：后端已支持的 `operator`、`action`、`result` 过滤已实现。

---

## 6. Users 详情抽屉实现

- **交互**：点击行内「详情」按钮（或双击行）打开 `el-drawer`；含加载态、空态、错误态；关闭（`@closed`）清理 `currentUser`/历史数据，再次打开重新拉取。
- **五区块（均基于真实 API 返回）**：
  - **A. 基本信息**：`username` / `display_name` / 主角色 / `is_active` / `is_superuser` / `last_login` / `last_login_ip` / `created_at`（来自列表 `UserOut`）。
  - **B. 角色信息**：主角色 + 关联角色（`user.roles`），并从 `GET /api/roles`（`roles:read`，带 403 降级）映射出 `code` / 是否系统角色。
  - **C. 权限来源**：超管显示「通配 `["*"]」说明；非超管按角色展示各角色直接授予的权限码，并展示「当前最终生效权限（后端计算）」= `user.permissions`。**完全复用后端 `get_user_permissions` 计算结果，未自行实现聚合逻辑**。
  - **D. 登录历史**：复用 `GET /api/login-logs?username=...`（后端 `username` 过滤）。
  - **E. 操作历史**：复用 `GET /api/operation-logs?target_user_id=...`（后端 `target_user_id` 过滤）。
- **权限隔离**（详见第 9 节）：D/E 两区仅在持有对应权限时才发起请求并渲染表格，否则显示「无权限查看…」提示。

---

## 7. Users el-table 风格统一

- 将原手写 `<table class="tbl">` + 自定义 `.modal` 重构为 `<el-card class="table-card">` + `<el-table stripe>` + `<el-pagination>` + `el-tag` + `el-button link`，与 `Alerts.vue`/`Sources.vue` 既有管理页风格一致。
- **新增/编辑**改用 `el-dialog`（沿用既有 `.apple-dialog` 全局样式）+ `el-form`/`el-form-item`。
- **保留能力（表现层重构，权限语义不变）**：搜索、角色筛选、分页、新增、编辑、启用、停用、删除、自我保护（不能操作自己）、`admin` 保护（不能删除内置管理员）、权限门禁、二次确认（`ElMessageBox`）、401 统一处理（失效跳登录清态）、403 不登出（仅提示）。
- 真实分页：`page`/`size` 默认 10，`el-pagination` 驱动。

---

## 8. 权限矩阵

| 功能 | 所需权限码 | 门控位置 |
|---|---|---|
| 登录日志菜单/页面 | `login_logs:read` | `AppLayout` `v-if` + 路由 `meta.permission` |
| 操作日志菜单/页面 | `audit_logs:read` | 同上 |
| 用户管理页 + 详情抽屉（基本/角色/权限来源） | `users:read` | 路由 `meta.permission` |
| 详情抽屉·登录历史区 | `login_logs:read` | 抽屉内独立 `canLoginLogs` 判断，无则显示无权限 |
| 详情抽屉·操作历史区 | `audit_logs:read` | 抽屉内独立 `canOpLogs` 判断，无则显示无权限 |
| 新增/编辑用户 | `users:write` | `canWrite` |
| 启用/停用用户 | `users:activate` | `canActivate` |
| 删除用户 | `users:write` | `canWrite` |

> 详情抽屉沿用 `users:read`；日志数据仍受各自 `login_logs:read` / `audit_logs:read` 限制，不因打开详情而绕过。

---

## 9. 日志权限隔离验证（重点）

构造隔离测试用户 `logtester`：自定义角色仅含 `users:read`（无 `login_logs:read` / `audit_logs:read`）。

实测（真实浏览器，Playwright + 系统 Chrome）：
- `logtester` 可进入 `/users`、可打开用户详情抽屉，基本信息/角色/权限来源区块正常显示；
- 登录历史区显示「**无权限查看登录日志**」、操作历史区显示「**无权限查看操作日志**」；
- 抽屉内历史 `el-table` 数量为 **0**（未加载真实日志数据），证明详情抽屉**没有绕过日志权限**拿到数据。

对照：拥有全部权限的 `admin` 打开同一抽屉时，登录/操作历史均正常加载（非 denied）。

结论：用户详情抽屉不能绕过日志权限，满足第 8 节要求。

---

## 10. Admin 验收（生产 :8000，只读验收）

| 检查 | 结果 |
|---|---|
| 登录日志/操作日志/用户管理/角色权限 菜单均显示 | ✅ |
| 登录日志页加载（`el-table`，20 行，分页正常） | ✅ |
| 操作日志页加载（`el-table`，3 行） | ✅ |
| 用户页使用 `el-table` | ✅ |
| 详情抽屉打开，A/B/C/D/E 五区块齐全 | ✅ |
| 权限来源区展示「最终生效权限（后端计算）」 | ✅ |
| admin 登录/操作历史正常加载（未被拒绝） | ✅ |
| 控制台错误 | **无（[]）** |

> 生产环境仅做只读验收，未通过生产 UI 创建/删除/停用任何用户。

---

## 11. Viewer / Analyst 验收（隔离 :8001）

| 检查 | Viewer | Analyst |
|---|---|---|
| 登录日志/操作日志/用户管理 菜单隐藏 | ✅ | ✅ |
| 直访 `/login-logs`（或 `/operation-logs`）→ 重定向 `/dashboard` + 「无权限」提示 | ✅ | ✅ |
| 越权 API 调用返回 403 | ✅（403） | ✅ |
| 403 **不触发全局登出**（token 保留） | ✅ | ✅ |

---

## 12. 构建结果

- 命令：`cd frontend && NODE_OPTIONS=--max-old-space-size=1400 npx vite build`
- 结果：**成功**（2320 modules transformed，无 TS/构建错误；仅良性警告）。
- 新产出 chunk：`LoginLogs-*.js/.css`、`OperationLogs-*.js/.css`、`Users-*.js/.css`。
- 已通过 `backend/_d.py` 同步 `dist` → `backend/app/static`（52 文件写入），生产 `:8000` 经 SPA 中间件即时提供新 `index.html` 与懒加载 chunk。

---

## 13. RBAC-2C 回归结果

- 命令（隔离测试库）：`DATABASE_URL='...5432/opinion_test' DB_IDENTITY_CHECK=off pytest tests/test_rbac.py`
- 结果：**9 passed**（与 RBAC-2C 一致）。
- 本阶段未改动任何后端代码，回归确认无回退。

---

## 14. 浏览器验收结果

- 工具：Playwright（backend venv）+ 系统 Chrome（headless）。
- 覆盖率：Admin（prod 只读）、Viewer、Analyst、Logtester（权限隔离）四类会话。
- 结论：全部通过（详见第 10/11/9 节）。关键项：4 菜单显隐正确、两日志页与用户页 `el-table` 正常、详情抽屉五区块完整、日志权限隔离未被绕过、403 不登出、零控制台错误。
- 验收脚本与产物保留于 `C:/Users/Administrator/AppData/Local/Temp/rbac2f/`（`browser_accept.py`、`browser_out.json`）。

---

## 15. 是否修改后端业务逻辑

**否。** 后端零改动；仅复用既有 `/api/login-logs`、`/api/operation-logs`、`/api/users`、`/api/roles` 接口。

## 16. 是否修改数据库

**否。** 无迁移、无 schema 改动、无库字段改动；生产库仅承受 admin 登录与只读页面验收。

## 17. 是否新增迁移

**否。** 未新增任何 Alembic 迁移。

## 18. 是否污染生产数据

**否。** 生产 `:8000` 仅做只读验收，未创建/删除/停用/修改任何用户或角色。隔离测试库 `opinion_test` 中临时创建的 `rbac_viewer`(46)、`rbac_analyst`(47)、`logtester`(48) 用户及自定义角色 `logtester`(4) 已全部删除并复查（登录均返回 401），测试后端 `:8001` 已关停。

---

## 19. 未实现项

下列属「可选增强 / 后续架构演进」，**不在本阶段范围**，亦非 RBAC-1 必须项：

- 新增「系统管理员」第 4 默认角色（`system_admin`）——RBAC-1 §9 明确标注非阻塞（可选）。
- 读权限模型重构、sources 权限统一、多角色前端增强、审计日志高级检索、RBAC 权限模型重构——均为后续演进，非初始需求缺口。
- 操作日志页未接入时间范围（`start`/`end`）筛选与操作日志 `details_json` 结构化展示——后端已支持 `start/end`，前端仅实现了 `operator/action/result`，时间范围筛选留作后续增强（不影响「查看操作日志」核心需求）。

> 除上列可选/后续项外，**RBAC-1 最初明确的 4 项未完成功能已全部实现**。

---

## 20. 最终结论

> **RBAC-2F 完成。**

- ✅ RBAC-1 最初明确的 4 项未完成功能全部补齐：`LoginLogs.vue`、`OperationLogs.vue`、`Users.vue` 详情抽屉、`Users.vue` `el-table` 风格统一。
- ✅ 登录日志页、操作日志页可用；用户详情抽屉可用（五区块 + 日志权限隔离）。
- ✅ 日志权限未被详情抽屉绕过（仅持 `users:read` 的用户看不到真实日志）。
- ✅ `npx vite build` 成功，无 TS/构建错误。
- ✅ RBAC-2C 后端测试 **9/9** 回归通过。
- ✅ 真实浏览器验收（Admin/Viewer/Analyst/Logtester）全部通过，零控制台错误。
- ✅ 未修改后端业务逻辑、未修改数据库、未新增迁移、生产数据零污染。

**按阶段停止条件，RBAC-2F 达成，立即停止，不自动进入 RBAC-3 或其他功能开发。**
