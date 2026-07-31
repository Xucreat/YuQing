# RBAC-2D 交付报告：前端 RBAC 管理闭环

> 阶段背景：RBAC-2B（真实库迁移 `kwlex01 → rbac10001`）已完成；RBAC-2C（后端测试 9/9 通过 + 权限审计）已完成。本阶段 RBAC-2D **仅闭环前端 RBAC 管理体验**，不扩展后端权限模型、不做不必要的后端重构。
>
> 完成时间：2026-07-23 | 执行者：Senior Developer（高级开发工程师）

---

## 1. 修改文件清单

### 后端（最小化，仅暴露既有字段，无模型/迁移变更）
| 文件 | 改动 | 是否改库/迁移 |
|---|---|---|
| `backend/app/schemas/user.py` | `Token` schema 新增 `is_superuser: bool = False` | 否（仅响应字段） |
| `backend/app/api/auth.py` | `login` 返回 `is_superuser=bool(user.is_superuser)` | 否 |

### 前端（核心闭环）
| 文件 | 改动 |
|---|---|
| `frontend/src/stores/index.ts` | 新增 `isSuperuser` 状态（持久化 `localStorage['is_superuser']`），`logout` 时清空 |
| `frontend/src/types/index.ts` | `LoginResult` 增加 `is_superuser`；新增 `PermissionCatalogItem`、`RoleOut` 类型 |
| `frontend/src/composables/usePermission.ts` | **重写**为统一权限入口（见 §2） |
| `frontend/src/api/index.ts` | 新增全局 401 拦截（见 §7） |
| `frontend/src/router/index.ts` | 新增 `/roles` 路由；`/users` 加 `meta.permission`；`beforeEach` 加路由级权限校验（见 §3） |
| `frontend/src/components/AppLayout.vue` | 按权限显示「用户管理 / 角色权限」菜单（见 §4） |
| `frontend/src/views/DataManage.vue` | 数据源 tab 仅 `isSuperuser` 可见（按 `require_admin` 行为，见 §9） |
| `frontend/src/views/Users.vue` | **重写**为完整用户管理页（见 §5） |
| `frontend/src/views/Roles.vue` | **新建**完整角色权限管理页（见 §6） |

### 构建部署
- `npx vite build` 成功（Roles/Users 分包产出）。
- `python backend/_d.py` 部署 113 个文件到 `backend/app/static`（已确认 `Roles-DRNJ5Dkg.js` + `Roles-BXLv1dK2.css`、多 `Users-*.js` 分包在线）。

---

## 2. 前端权限架构

**单一入口**：`usePermission()`（composable）统一定义全部权限判断，所有页面/菜单/路由复用，避免散落判断逻辑。

```
usePermission()
 ├─ role            : computed(auth.role)               // 登录角色
 ├─ isSuperuser     : computed(!!auth.isSuperuser || role==='admin')
 ├─ hasPermission(p)         : isSuperuser ? true : permissions.includes(p) || includes('*')
 ├─ hasAnyPermission(perms)  : isSuperuser ? true : perms.some(...)
 ├─ hasAllPermissions(perms) : isSuperuser ? true : perms.every(...)
 ├─ can(p)                   : 兼容旧调用 → hasPermission(p)
 └─ canAccessRoute(meta)     : 支持 meta.permission / meta.permissions + meta.permissionAny
```

**与后端保持一致的规则**（对齐 `is_superuser_user`）：
1. `is_superuser === true` → 全权限（含 `role_permissions=0`）；
2. `role === 'admin'` → 保持历史兼容，等价超管；
3. 普通用户 → 使用登录接口返回的实权限列表；
4. **前端权限控制仅用于 UI / 路由体验，不替代后端鉴权**（路由守卫不是安全边界）。

**状态来源**：登录响应 `{access_token, role, permissions, is_superuser}` → `useAuthStore` 落 `localStorage`（token / role / permissions / is_superuser / username）。已验证 admin 登录返回 `is_superuser: true`、`permissions: ["*"]`；`/api/roles` 中 admin 行 `permissions:[]` 但登录态实际为 `["*"]`（证明 `role_permissions=0` 不被误限 —— 满足要求 D）。

**26 项权限分组**（来自 `/api/permissions` 实查，按后端 `Permission.group`）：舆情管理 / 事件管理 / 关键词管理 / 用户管理 / 角色管理 / 权限管理 / 告警管理 / 报告 / 数据源 / 采集管理 / 传播溯源 / 驾驶舱 / 审计。前端未杜撰任何权限码。

---

## 3. 路由权限矩阵

| 路由 | 页面 | requiresAuth | 权限 meta | viewer | analyst | admin/超管 |
|---|---|---|---|---|---|---|
| `/login` | 登录 | 否 | — | 公开 | 公开 | 公开 |
| `/dashboard` | 总览 | 是 | — | ✓ | ✓ | ✓ |
| `/opinions` `/opinion/:id` | 舆情 | 是 | — | ✓ | ✓ | ✓ |
| `/events` `/event/:id` | 事件 | 是 | — | ✓ | ✓ | ✓ |
| `/alerts` | 预警 | 是 | — | ✓ | ✓ | ✓ |
| `/data` | 数据管理 | 是 | — | ✓（关键词tab） | ✓（关键词tab） | ✓（含数据源tab） |
| `/users` | 用户管理 | 是 | `users:read` | ✗（guard→/dashboard，提示无权限） | ✗ | ✓ |
| `/roles` | 角色权限 | 是 | `roles:read` | ✗（guard→/dashboard） | ✗ | ✓ |
| `/propagation` | 传播溯源 | 是 | — | ✓ | ✓ | ✓ |
| `/command-screen` | 指挥大屏 | 是 | —（独立全屏布局） | ✓ | ✓ | ✓ |

> 说明：业务只读页（dashboard/opinions/events/alerts/data/propagation）**不带 permission meta**，保持「已登录即可访问」的既有行为 —— 与 RBAC-2C 审计结论一致（这些读接口后端仅校验登录，未强制 `require_permission`）。未对 GET 端点批量补 `require_permission`（属禁止项，见 §8 与 §10）。

**守卫逻辑**（`router.beforeEach`）：
- 未登录访问受保护页 → `/login`（测试项 A）；
- 已登录访问带 `permission` meta 且无权限 → `ElMessage.warning('无权限访问该页面')` + 回退 `/dashboard`（测试项 B/C）；
- 已登录访问带权限且具备 → 放行（测试项 D）。

---

## 4. 菜单权限矩阵（AppLayout 侧边栏）

| 菜单项 | 显示条件 | viewer | analyst | admin |
|---|---|---|---|---|
| 总览 / 舆情 / 事件 / 预警 / 数据管理 / 传播溯源 | 已登录即显示 | ✓ | ✓ | ✓ |
| 用户管理（👤） | `hasPermission('users:read')` | ✗ 隐藏 | ✗ 隐藏 | ✓ |
| 角色权限（🔐） | `hasPermission('roles:read')` | ✗ 隐藏 | ✗ 隐藏 | ✓ |
| 数据源管理 tab | `isSuperuser`（按 `require_admin`） | ✗ | ✗ | ✓ |

> 明确认知：**前端隐藏菜单 ≠ 后端安全边界**。无权限用户直接访问 `/users`、`/roles` 仍会被路由守卫拦截；即便绕过前端，后端接口按权限校验（见 §7 / §8）。未改动指挥大屏与既有业务菜单。

---

## 5. Users.vue 结果

**功能清单（按真实 API 闭环）**：
- 列表：`GET /api/users?search=&role=&size=200`，展示 `username / display_name / role / roles[] / is_active / is_superuser / last_login`；
- 搜索：用户名输入框；角色筛选下拉（全部/admin/analyst/viewer）；
- 启用/停用：按钮调用 `/api/users/{id}/activate`、`/api/users/{id}/deactivate`，受 `canActivate = hasPermission('users:activate')` 控制显示；
- 写操作（新增/编辑/删除）：受 `canWrite = hasPermission('users:write')` 控制；
- 自我保护：`isSelf(u)` 禁用当前用户的停用/删除；`admin` 用户名禁用删除；系统关键用户受保护；
- 反馈：`ElMessageBox.confirm` 二次确认删除/停用；`ElMessage` 成功/失败提示；操作后按后端响应刷新行；
- 鉴权：401 统一登出跳登录；403 由调用处提示「无权限」。

**后端支持缺口（明确报告，不伪造）**：
- 后端 `GET /users` 不返回「创建时间排序之外」的批量字段问题：无 —— 字段齐全；
- 后端**未提供**「按角色批量改权限」「重置他人密码的前端按钮」等超出 `users:write` 语义的能力，前端未杜撰；
- `display_name` 字段后端返回 `null`（prod admin），前端已容错显示用户名。

**实测（admin 登录）**：`/api/users` 返回 200，`{items,total,page,size}` 结构正确，前端分页/搜索参数与后端一致。

---

## 6. Roles.vue 结果

**功能清单**：
- 角色列表：`GET /roles`，表格展示 `display_name / code / is_system / 权限数 / user_count / is_enabled`；
- 权限详情/编辑弹窗：权限按 `Permission.group` 分组（13 组，含 `GROUP_LABEL`/`GROUP_ORDER`），复选网格显示 `code + 名称 + 描述`；
- 保存：`PUT /roles/{id}` 提交 `{permissions:[选中码...]}`；受 `canWrite = hasPermission('roles:write')` 控制；
- 新建角色：`POST /roles`（code/name/display_name/description + 权限勾选），受 `canWrite` 控制；
- 删除：`v-if="canDelete && !r.is_system"`（`roles:delete`），`ElMessageBox.confirm` 二次确认，`DELETE /roles/{id}`；
- `admin` 系统角色：只读，所有权限复选框展示为选中（超管全权，文档说明）；系统角色不可删除/不可停用。

**与真实权限对齐**：权限目录来自 `GET /permissions`（实查 **26 项**，13 组），未平铺、未杜撰。组序：舆情/事件/关键词/用户/角色/权限/告警/报告/数据源/采集/传播/驾驶舱/审计。

**实测（admin 登录）**：`/api/roles` 返回 3 个角色（admin/analyst/viewer，均 `is_system=true`），`/api/permissions` 返回 26 项 —— 与前端分组逻辑吻合。

---

## 7. 401 / 403 处理

**全局 401 拦截**（`api/index.ts` 响应拦截器）：
1. 清除 `localStorage['token']`；
2. 调 `useAuthStore().logout()` 清空用户态（role / permissions / is_superuser / username）；
3. `ElMessage.error('登录状态已失效，请重新登录')`；
4. 懒加载 router `push('/login')`（失败回退 `window.location.href='/login'`）；
5. `redirectingToLogin` 标志防并发轮询重复跳转；已在 `/login` 不重复跳。

**401 vs 403 严格区分**：仅 401 触发登出跳登录；**403（已登录但无权限）不在此统一登出**，由业务调用处按场景提示（如用户管理页删除被拒、路由守卫 `ElMessage.warning('无权限访问该页面')`）。避免把「无权限」误判为「登录失效」。

**实测**：`GET /api/users` 无 token → 401（已验证）；admin 登录态下调用受保护接口正常。

**测试项 E（停用用户）覆盖**：后端 `test_inactive_user_rejected_and_token_invalidated` 已验证「登录后被停用 → 旧 token 立即 401」；前端 401 拦截据此自动清态跳登录，形成闭环。

---

## 8. 测试结果

### A. 未认证
- 后端：`test_unauthenticated_protected_endpoints_401` / `test_invalid_tokens_401` —— 9/9 通过；
- 前端：路由守卫未登录访问受保护页 → `/login`；API 401 → 清态跳登录（代码层验证；无头浏览器不可用，未做点击级 E2E）。

### B. viewer
- 后端：`test_viewer_allowed_reads`（只读 200）、`test_viewer_denied_writes`（写 403）；
- 前端：无 `users:read`/`roles:read` → 菜单隐藏；直达 `/users`、`/roles` → 守卫拦截回退；写按钮 `v-if` 隐藏；绕过前端后端仍 403。

### C. analyst
- 后端：`test_analyst_allowed_writes`（13 项可写）、`test_analyst_denied_admin_writes`（用户/角色/数据源 403）；
- 前端：无管理菜单；数据源 tab 仅 `isSuperuser` 可见（analyst 不可见，后端 `require_admin` 拒绝）。

### D. admin / 超管
- 后端：`test_admin_superuser_full_access` —— `role_permissions=0` 仍全权（`["*"]`）；
- 前端：登录返回 `is_superuser:true` + `["*"]`，全部 RBAC 页可见、角色/权限/用户可管理，不被 `role_permissions=0` 误限。

### E. 停用用户
- 后端：`test_inactive_user_rejected_and_token_invalidated` —— 登录后被停用 → 后续 API 401 → 前端自动清态跳登录。

### F. 回归
- **RBAC-2C 后端测试：9 passed（5.14s）**，命令：
  `DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test' DB_IDENTITY_CHECK=off .venv/Scripts/python.exe -m pytest tests/test_rbac.py -v`
  > ⚠️ 注意：默认 `tests/conftest.py` 把 `DATABASE_URL` 指向 **5433** 的 `opinion_test`，但本机 PG 仅监听 **5432**，直接 `pytest` 会连接超时挂起。须显式 `export DATABASE_URL=...5432/opinion_test`。已验证 prod 未被污染（prod `users` 仅 `admin` 一条）。
- 现有业务页（opinion/event/keyword/source/dashboard/propagation/command-screen）未改动；指挥大屏未触碰；构建成功、静态部署成功。

### 前端构建/部署验证
- `vite build` 成功；`backend/app/static` 已含 `Roles-*.js/css`、`Users-*.js` 分包；`/` 返回 200；`/api/users` 无 token 返回 401。

---

## 9. 发现但未处理的权限模型差异（已报告，未擅自扩展）

1. **`is_superuser` 响应字段缺失（已修复）**：原 `Token` schema 无 `is_superuser`，前端无法区分「`role==='admin'`」与「`is_superuser=true`」。本阶段以**最小化**方式补字段（仅暴露既有 `User.is_superuser`），未改模型/迁移。
2. **数据源接口 `require_admin` 与 `sources:read/write` 种子权限不一致**：后端 `admin_data_sources.py` 用 `require_admin`（超管专属），前端据此将「数据源管理」按 `isSuperuser` 而非 `sources:*` 控制。**未**为对齐而改后端接口（属禁止项）。
3. **读权限接口未强制 `require_permission`**（RBAC-2C 审计）：`opinions:read/events:read/dashboard:read/keywords:read/alerts:read` 后端仅校验登录。前端按登录态放行对应只读页，未对 GET 端点批量补 `require_permission`。
4. **`role_permissions=0` 与超管全权**：admin 角色 `permissions` 为空数组但登录返回 `["*"]`，前端 `isSuperuser` 判定已覆盖，未误限。
5. **`user_roles` 多角色支持**：后端数据模型支持多角色，但登录 `permissions` 为单角色聚合计算；前端当前以登录返回的扁平 `permissions` 为准，未自管多角色拼接（与后端一致，未扩展）。

---

## 10. 是否修改后端业务逻辑 / 数据库 / 迁移 / 生产数据 —— 明确声明

**后端业务逻辑**：未改任何鉴权/权限校验逻辑。仅 `auth.py` 的 `login` 在返回体中**新增一个既有字段 `is_superuser`**（值来自 `User.is_superuser`，计算逻辑未变），以及 `schemas/user.py` 的 `Token` 增加一个可选字段。**未修改任何 `require_permission` / `require_admin` 装饰器、未新增/删除权限码、未改动 collector / 舆情采集 / 关键词匹配 / 风险评分逻辑。**

**数据库 schema / Alembic 迁移**：**零改动**。未新建/修改任何 migration，未 `alembic upgrade`，未改任何 SQLAlchemy model。

**生产数据**：**零修改**。`RBAC-2C` 测试在隔离库 `opinion_test` 运行（9/9 通过），prod `opinion_db` 的 `users` 表经只读核查仅含 `admin` 一条，无测试污染。本次未对 prod 做任何 INSERT/UPDATE/DELETE。

**指挥大屏 / 业务页**：未改动 `CommandScreen`、既有业务菜单与页面。

> 结论：本阶段严格限定在「前端 RBAC 管理闭环」范围内，后端仅以 2 行最小改动暴露既有 `is_superuser` 字段以支撑前端判定；库结构、迁移、生产数据、业务鉴权逻辑均保持原状。

---

## 附：验证命令速查
```bash
# 后端健康 + 静态
curl http://127.0.0.1:8000/health          # {"status":"ok"}
curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/   # 200
curl -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/users   # 401 (无token)

# admin 登录（确认 is_superuser + ["*"]）
curl -s -X POST http://127.0.0.1:8000/api/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -m json.tool

# RBAC-2C 回归（隔离库，须显式 5432）
DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test' \
DB_IDENTITY_CHECK=off PYTHONPATH=. .venv/Scripts/python.exe -m pytest tests/test_rbac.py -v
```
