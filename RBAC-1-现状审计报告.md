# Phase RBAC-1 现状审计报告

> **审计原则**：未修改任何代码。以「源码 + 数据库实际状态」为唯一事实来源，连库做了只读查询、对 RBAC 模块做了语法编译检查、对前端做了只读探索。
> **审计时间**：2026-07-23
> **结论先行**：后端 RBAC 代码（模型 / 校验 / API / 服务 / 迁移）已**基本写完**，但**数据库迁移 `rbac10001` 尚未应用**（DB 仍停在 `kwlex01`）。前端 RBAC 管理界面**大量缺失**。因此当前系统处于「代码已就位、库未落地、前端缺页面」的半成品状态。

---

## 0. 已验证的关键事实（数据库只读核查）

| 检查项 | 实际结果 |
|---|---|
| `alembic_version` | **`kwlex01`**（HEAD 仍是 kwlex01，**不是** rbac10001） |
| `permissions` 表 | **不存在**（UndefinedTable） |
| `role_permissions` / `user_roles` | **不存在** |
| `user_login_logs` / `user_operation_logs` | **不存在** |
| `users` 表列 | 仅 `id,username,password_hash,role,created_at,is_active,last_login`（**缺** `is_superuser,display_name,email,last_login_ip,updated_at`） |
| `roles` 表 | 存在，但仍是 `p2_rbac` 旧结构（`id,name,display_name,permissions(JSONB),created_at`），**未规范化**（无 `code/is_system/is_enabled/updated_at`） |
| `users` 行数 | 1（仅 admin） |
| `roles` 行数 | 3（admin / analyst / viewer，来自 p2_rbac 种子） |
| 后端进程 | `/health` 返回 `ok`（进程在线） |
| RBAC 模块编译 | `py_compile` 全部通过（user/role/permission/audit/permissions/security/dependencies/users/auth/schemas/audit_service） |

> ⚠️ **重要推论**：当前后端若以磁盘上的新代码运行，登录会访问 `users.is_superuser` 列（不存在）→ 500。也就是说「代码与库schema不一致」是必须解决的首要矛盾，解决方式就是应用迁移 `rbac10001`。

---

## 1. 当前用户认证实现

- **机制**：JWT（HS256，无状态），`Authorization: Bearer <token>`。密钥来自 `.env`（`secret_key`，默认值 `change-me-in-production`，需生产替换）。Token 有效期 1440 分钟。
- **登录 API**：`POST /api/login`（`app/api/auth.py`）
  - 校验用户名 → bcrypt 校验密码 → 更新 `last_login`/`last_login_ip` → 签发 JWT（`sub=user.id`，附带冗余 `role` 声明）→ **写入登录日志** → 返回 `{access_token, token_type, role, permissions}`。
- **当前用户注入 / 获取**：`get_current_user`（`app/core/dependencies.py`）
  - Bearer 解析 → `decode_access_token` → 按 `sub` 查 `User` → **校验 `is_active`**：停用用户即使持有合法 JWT 也立即返回 **401**。
  - 这是「停用用户后旧 Token 立即失效」的实现依据（每次请求都回查 `users` 表，权限不在 Token 内，而是每次从 DB 计算）。
- **登出**：`POST /api/logout`，无状态 JWT 仅前端丢弃 + 写一条 `logout` 登录日志。
- **认证覆盖**：所有业务 router（`opinions/keywords/events/alerts/reports/dashboard/users`）均在 router 级挂 `Depends(get_current_user)`，即**全量需认证**。写操作再叠加 `require_permission`。

---

## 2. 当前用户模型（`app/models/user.py`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | |
| `username` | str(64) unique | 登录名 |
| `password_hash` | str(255) | **bcrypt**（无明文） |
| `role` | str(32) | **主角色**（字符串，对应 `roles.name`）；保留以最小兼容 |
| `is_active` | bool | 启用/停用 |
| `is_superuser` | bool | **超级管理员**（与 `role=='admin'` 等价） |
| `display_name` | str(64) nullable | 显示名 |
| `email` | str(128) nullable | 邮箱 |
| `last_login` | datetime nullable | 最后登录时间 |
| `last_login_ip` | str(64) nullable | 最后登录 IP |
| `created_at` / `updated_at` | datetime | 时间戳 |
| `roles` | M2M | 附加角色（经 `user_roles`），与主角色构成「一个或多个角色」 |

> 注意：`is_superuser/display_name/email/last_login_ip/updated_at` 在**模型里已定义**，但**数据库尚未加列**（迁移未应用）。`init_db.py` 创建 admin 时只写 `username/password_hash/role='admin'`，靠 `role=='admin'` 仍被判定为超管，兼容。

---

## 3. 当前权限实现（`app/core/permissions.py`）

完整链路：**User → Role(s) → Permission**（经 `role_permissions` 关联表，权威来源；替代旧的 `roles.permissions` JSONB）。

- `is_superuser_user(user)` = `user.is_superuser or user.role == 'admin'` —— 两种超管等价。
- `get_user_permissions(user, db)`：
  - 超管返回 `["*"]`；
  - 普通用户 = 主角色（`user.role`）+ 附加角色（`user.roles`）的**权限并集**，仅计入 `is_enabled` 的角色。
- `require_permission(perm)`：依赖工厂；超管放行；否则权限集含 `perm` 则放行，否则 **403**。
- `require_admin`：仅超管。
- **权限码格式沿用 `resource:action`**（如 `keywords:write`），与历史一致，行为不回归。

---

## 4. 当前已有权限列表（`rbac10001` 迁移种子 `_PERMISSIONS`，共 **26** 个）

```
users:read  users:write  users:activate
roles:read  roles:write  roles:delete
permissions:read
keywords:read  keywords:write  keywords:delete
opinions:read  opinions:write
events:read  events:write
alerts:read  alerts:write
collectors:read  collectors:write
sources:read  sources:write
propagation:read
dashboard:read
reports:read  reports:write
audit_logs:read  login_logs:read
```

- 业务中已用 `require_permission` 的接口（与种子一致，无悬空权限码）：`users:*`、`roles:*`、`permissions:read`、`login_logs:read`、`audit_logs:read`、`opinions:write`、`reports:read`、`alerts:write`、`events:write`、`keywords:write`。
- 历史权限码 `keywords:write` 等**保持不变**，向后兼容。

---

## 5. 当前日志能力

- **登录日志**：`LoginLog`（`user_login_logs`）模型完整，字段 `id, user_id(nullable), username, login_at, ip_address, user_agent, status(success|failed|logout), failure_reason`。`auth.py` 已在登录成功/失败（含用户名不存在的 `user_not_found`、密码错、已停用）/登出时写入。**但表尚未建**。
- **操作审计日志**：`OperationLog`（`user_operation_logs`）模型 + `audit_service.log_operation`。记录 `operator_user_id`、`operator_username_snapshot`（改名/删除后仍可读）、`action`、`resource_type`、`resource_id`、`target_user_id`、`request_method/path`、`ip`、`ua`、`result`、`error_message`、`details_json`。**已在 `users.py` 对关键操作显式调用**：CREATE / UPDATE / DELETE / ENABLE / DISABLE / PASSWORD_RESET / ROLE_CREATE / ROLE_UPDATE / ROLE_DELETE。**表尚未建**。
- **审计方式**：采用**显式 `log_operation`（业务动作级）**，而非 request middleware。更贴合「谁 / 对什么 / 做了什么 / 结果」原则；未对 GET 批量刷日志（符合范围控制）。
- **异常日志**：无专门审计表，依赖后端 stdout。
- **数据库审计字段**：各业务表有 `created_at/updated_at`（既有迁移），但非统一操作审计。

---

## 6. 当前前端权限控制（Vue3 + Element Plus + Pinia + Vue Router）

**已具备（雏形）**
- `views/Users.vue`：用户增删改 + 角色下拉（写死 `admin/analyst/viewer`）+ 启用状态；调用真实 `/api/users`。
- `composables/usePermission.ts`：`can(perm)` 封装（`role==='admin'` 放行；否则比对 `authStore.permissions` 或 `*'`）。
- `stores/index.ts`（`useAuthStore`）：登录已接收并持久化 `token/role/permissions/username` 到 localStorage。
- `Dashboard.vue`：已用 `v-if="can('reports:read')"` 控制「导出报告」按钮（**唯一一处权限码落地的按钮**）。

**缺失（RBAC 改造重点）**
1. **路由守卫只判断 `token` 是否存在**（`router.beforeEach`），**不按角色/权限拦截**任何路由；任何登录用户都能直访 `/users` 等业务页（仅靠后端 403 兜底）。
2. **侧边栏菜单完全静态**（`components/AppLayout.vue`）：7 个写死 `router-link`，无权限显隐；且 `/users` 页面**根本没有菜单入口**。
3. **无角色管理页**（仅有 `types/index.ts` 的 `RoleItem` 类型，无 UI）；角色下拉写死三值。
4. **无任何日志/审计页**（登录日志、操作日志均不存在）。
5. **无统一管理页 CRUD 骨架**：`Users.vue` 用手写 `<table>` + 自定义 `.modal`，与 `Sources.vue`/`DataManage.vue` 的 `el-table`/`el-dialog` 风格不一致。
6. **无全局 401 拦截器**：token 过期时前端静默空屏（既有已知建议，待拍板）。

- **UI 风格**：Element Plus + Apple 风 `styles/theme.css`（`--el-color-primary:#0071e3`，圆角/胶囊/airy 卡片）。新增页面应沿用此风格。

---

## 7. 可直接复用的代码（重大）

**后端 ≈ 90% 已就绪，零重写**：
- 模型：`user.py` / `role.py` / `permission.py`（`Permission` + `role_permissions` + `user_roles`）/ `audit.py`（`LoginLog` + `OperationLog`）。
- 校验：`core/permissions.py`（`is_superuser_user` / `get_user_permissions` / `require_permission` / `require_admin`）。
- API：`api/users.py`（用户 CRUD + 启用停用 + 重置密码 + 角色 CRUD + 权限分配 + 权限目录 + 登录/操作日志列表，全部按 `resource:action` 权限门控）。
- 认证：`api/auth.py`（登录/登出/登录日志）。
- 服务/工具：`services/audit_service.py`（`log_login` / `log_operation`）、`core/security.py`（bcrypt + JWT）、`core/dependencies.py`（`get_current_user` + 停用即 401）、`schemas/user.py`（全部出入参）。
- **迁移已写好**：`alembic/versions/rbac10001.py`（`users` 加列；`roles` 规范化；新建 6 张表；**幂等**种子 26 权限；把旧 JSONB 权限迁移进 `role_permissions`；标记系统角色与超管）。
- **引导**：`scripts/init_db.py` 已建 admin（`role='admin'`）+ 区域/数据源/关键词种子。

**前端 ≈ 30% 已就绪**：`Users.vue`、usePermission、authStore、theme.css、AppLayout 框架、`RoleItem` 类型。

---

## 8. 必须新增 / 补齐的能力

1. **【关键】应用数据库迁移 `rbac10001`**（DB 当前停在 kwlex01，新表/新列/权限种子全部缺失）。这是让现有代码跑起来的唯一前提。
2. **后端测试**：RBAC 测试当前 **0 个**（现有 14 个测试均非 RBAC）。需补：用户（创建/重名/停用/启用/停用后无法登录/重置密码/角色分配）、角色（增删改/系统角色保护/权限分配）、权限（多角色合并/无权限 403/超管绕过/`keywords:write` 不回归）、安全（最后超管保护/普通用户不可看审计/不可改角色权限）、日志（登录成功/失败/用户创建/停用/启用/角色变更/密码重置均有记录）。
3. **前端页面**：
   - `Roles.vue`（角色 CRUD + 权限分配，按资源分组展示；复用 `RoleItem` + `el-table`/`el-dialog` 统一风格）；
   - `LoginLogs.vue` / `OperationLogs.vue`（筛选 + 分页）；
   - `Users.vue` 补**菜单入口**、改用 `el-table` 风格统一、详情抽屉展示「角色 / 权限来源 / 登录历史 / 操作历史」；
   - `AppLayout.vue` 侧边栏按 `authStore.permissions` 动态显隐菜单；
   - `router.beforeEach` 按 `meta.roles/permissions` 拦截。
4. **前端 API 封装**：`/api/roles`、`/api/permissions`、`/api/login-logs`、`/api/operation-logs`（后端已就绪）。
5. **可选增强（建议）**：新增「系统管理员」角色（可管用户/角色、可看日志，但非全超管），更贴合建议的 4 默认角色；当前仅有 `admin/analyst/viewer`，日志查看能力目前只落在 `admin`（超管）上。
6. **可选健壮性**：前端全局 401 → `/login` 拦截器（既有建议）。

---

## 9. 与目标方案的差异

| 目标方案要求 | 当前实现状态 | 差异/处理 |
|---|---|---|
| User → Role → Permission 完整链路 | ✅ 已实现（role_permissions 关联） | 一致 |
| `roles` 表 `code/is_system/is_enabled/description/updated_at` | ✅ 迁移会加 | 一致 |
| `permissions` 表 `resource:action` + `group` | ✅ 已实现（group 用于前端分组） | 一致 |
| 超级管理员 `is_superuser` + 最后超管保护 | ✅ 已实现（`_superuser_count`/`_active_superuser_count` 多处校验） | 一致 |
| 不能删除当前登录用户 / 不能删被使用角色 / 系统角色不可删不可停用 | ✅ 已实现 | 一致 |
| 停用用户立即失效 | ✅ 已实现（`get_current_user` 查 `is_active`） | 一致 |
| 审计日志只读、普通用户不可删 | ✅ 已实现（无删除接口） | 一致 |
| 默认 4 角色（超管/系统管理员/分析员/只读） | ⚠️ 仅 3（admin/analyst/viewer），**无独立系统管理员** | 建议补 `system_admin` 角色；非阻塞（admin 兼日志查看） |
| 用户管理 / 角色管理 / 登录日志 / 操作日志 **前端页面** | ❌ 大部分缺失 | **主要工作量** |
| 后端 RBAC 测试 | ❌ 0 个 | **需补** |
| 读接口仅鉴权不鉴权（既有设计） | ⚠️ 业务读接口仅 `get_current_user` | 属范围外，不改；新 RBAC 接口已正确门控 |

---

## 10. 最小合理改造方案（实施阶段，待授权）

### 10.1 数据库迁移（需明确授权，遵循任务书 #20）
- **动作**：`alembic upgrade head`（应用 `rbac10001`）。
- **效果**：自动加 `users` 列、规范化 `roles`、建 `permissions/role_permissions/user_roles/user_login_logs/user_operation_logs`、**幂等**种子 26 权限、把旧 JSONB 权限迁移进 `role_permissions`、标记系统角色（`admin/analyst/viewer`）与超管（`role='admin'` → `is_superuser=true`）。
- **顺序**：先 `alembic upgrade head`，再 `python scripts/init_db.py`（其 `create_all` 为幂等安全网，只补 admin/业务种子，不会与迁移冲突）。
- **影响范围**：仅新增列/表与种子数据；不改任何业务表数据；既有 `admin` 用户权限不丢失（仍为超管）。
- **回滚策略**：`alembic downgrade kwlex01`（迁移已提供对称 downgrade）。
- **验证方案**：连库确认 `permissions`=26 行、`roles` 有 `code/is_system/updated_at`、`users.is_superuser=true`（admin）、用 `admin/admin123` 登录返回 `permissions` 非空；调用 `/api/users`、`/api/roles`、`/api/login-logs` 返回 200。
- ⚠️ 生产库写入前须先获明确授权。

### 10.2 后端测试（不触库结构风险，可先写）
- 新增 `backend/tests/test_rbac.py`，覆盖任务书第十九章全部清单；`conftest` 已支持 `COLLECTOR_TYPE=mock` 注入，用测试库运行，区分「本次新增 / 既有缺陷 / 环境问题」。

### 10.3 前端（按第 6/8 节补齐）
- 新建 `Roles.vue`、`LoginLogs.vue`、`OperationLogs.vue`；
- `Users.vue` 接入真实接口 + 补菜单入口 + 详情抽屉（角色/权限来源/登录历史/操作历史）+ 风格统一为 `el-table`；
- `AppLayout.vue` 侧边栏按 `permissions` 动态显隐；`router/index.ts` 加 `meta.roles/permissions` 并在 `beforeEach` 拦截；
- 复用 `theme.css` 与 `el-*` 组件，保持 Apple 风一致性。

### 10.4 安全边界原则
- **后端为真正安全边界**（所有写操作 + 新 RBAC 接口均有 `require_permission`）；前端仅做 UI 优化（隐藏按钮/菜单/拦截路由），不依赖前端控权。

### 10.5 不破坏既有能力
- 现有 `keywords/opinions/events/alerts/reports` 权限码保持不变；
- `admin` 用户兼容（`role='admin'` ⇒ 超管），登录不失败、权限不丢失；
- 旧 JWT 机制不变（每次鉴权回查 `is_active`）；
- 不改动与本任务无关的业务逻辑。

---

## 审计结论

当前项目**不是从零开始**，而是已经拥有一套写好的 RBAC 后端骨架（模型/校验/API/服务/迁移）与雏形前端。最大的真实缺口是：**① 数据库迁移 `rbac10001` 尚未执行**（导致库与代码不一致）；**② 前端 RBAC 管理页面与路由/菜单权限缺失**；**③ 后端 RBAC 测试为零**。

按「正确性 > 安全性 > 兼容性 > 可审计性 > 可扩展性 > 功能数量」的优先级，最小合理改造 = **应用迁移 + 补前端页面 + 补测试**，即可得到一个真正可用的企业级第一版 RBAC 系统，且完全复用现有代码、不破坏任何既有功能。

**下一步**：请确认是否授权执行数据库迁移 `alembic upgrade head`（及后续前端/测试实现）。生产库写入前我将先给出迁移计划+影响+回滚+验证方案待你批准。
