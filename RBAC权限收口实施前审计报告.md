# RBAC 权限收口 · 实施前只读审计报告

- 审计时间：2026-07-31
- 审计范围：`backend/app/core`、`backend/app/api`、`backend/app/models`、`backend/app/schemas`、`backend/alembic`、`frontend/src/{router,stores,composables,api,views,components}`
- 审计性质：**只读**（未修改任何代码、配置、数据库）
- 生产库快照：`opinion_db @127.0.0.1:5432`，alembic head = `p30_event_actions_deprecated`

---

## 一、当前权限模型（结论：结构完整，无需改造）

### 1.1 数据模型

| 表 | 说明 | 关键列 |
|---|---|---|
| `users` | 用户 | `role`（主角色，字符串）、`is_superuser`、`is_active` |
| `roles` | 角色 | `code`、`name`、`is_system`、`is_enabled` |
| `permissions` | **权限目录（定义源）** | `code`(唯一)、`name`、`resource`、`action`、`group`、`description` |
| `role_permissions` | 角色→权限（多对多） | CASCADE |
| `user_roles` | 用户→附加角色（多对多） | CASCADE |

判定链路：`User.role`（主角色）+ `user_roles`（附加角色）→ `role_permissions` → `permissions.code`。
`backend/app/core/permissions.py` 中：

- `is_superuser_user(user)` = `user.is_superuser or user.role == 'admin'`
- `get_user_permissions()`：超管返回 `["*"]`，否则取所有已启用角色的权限并集
- `require_permission(code)`：超管直通；否则要求 `code ∈ perms`，失败 **403 `Permission denied`**
- `require_admin()`：非超管 **403 `Admin required`**

> ✅ 模型健全，本次收口**不改表结构、不改判定算法**，只做「补权限码 + 补挂载点 + 前端收口」。

### 1.2 当前权限码清单（生产库实测 28 条）

| 分组(group) | 权限码 | 名称 |
|---|---|---|
| 舆情管理 | `opinions:read` / `opinions:write` | 查看舆情 / 管理舆情 |
| 事件管理 | `events:read` / `events:write` | 查看事件 / 管理事件 |
| 关键词管理 | `keywords:read` / `keywords:write` / `keywords:delete` | 查看 / 管理 / 删除关键词 |
| 预警管理 | `alerts:read` / `alerts:write` | 查看预警 / 管理预警 |
| 报告 | `reports:read` / `reports:write` / `reports:export` / `reports:manage` | 查看 / (遗留) / 导出 / 管理模板 |
| 数据源 | `sources:read` / `sources:write` | 查看 / 管理数据源 |
| 采集管理 | `collectors:read` / `collectors:write` | 查看 / 管理采集 |
| 传播溯源 | `propagation:read` | 查看传播 |
| 驾驶舱 | `dashboard:read` | 查看数据总览 |
| 用户管理 | `users:read` / `users:write` / `users:activate` | — |
| 角色管理 | `roles:read` / `roles:write` / `roles:delete` | — |
| 权限管理 | `permissions:read` | 查看权限目录 |
| 审计 | `audit_logs:read` / `login_logs:read` | — |

**❌ 不存在任何 `ai:*` 权限码**（全后端 grep 确认）。

### 1.3 当前角色授权（生产库实测）

| 角色 | 权限 | 备注 |
|---|---|---|
| `admin` (id=1) | `role_permissions` 仅含 `reports:manage` | 但 admin 用户 `is_superuser=true` → 实际 `["*"]` 全权限 |
| `analyst` (id=2) | `alerts:read/write`、`dashboard:read`、`events:read/write`、`keywords:read/write`、`opinions:read/write`、`propagation:read`、`reports:read/write/export`、`sources:read`（14 项） | — |
| `viewer` (id=3) | `alerts:read`、`dashboard:read`、`events:read`、`opinions:read`、`propagation:read`（5 项） | **无 keywords:read、无 reports:read** |

用户：`admin`(admin/超管)、`测试`(analyst)、`观察测试`(viewer)。

---

## 二、后端接口权限覆盖审计

### 2.1 已正确挂载 `require_permission` 的接口（保持不变）

| 模块 | 接口 | 权限 |
|---|---|---|
| events | `POST /events/aggregate`、`PATCH /events/{id}/status`、`POST /events/{id}/actions`、`DELETE /events/{id}` | `events:write` |
| alerts | `POST/PUT/DELETE /alerts/rules*`、`POST /alerts/evaluate`、`PUT /alerts/records/{id}/handle` | `alerts:write` |
| keywords | `POST /keywords`、`PUT /keywords/{id}`、`DELETE /keywords/{id}` | `keywords:write` |
| opinions | `POST /opinions`、`PATCH /opinions/batch`、`PATCH /opinions/{id}` | `opinions:write`；删除为 `require_admin` |
| reports | `/overview`、`/modules` → `reports:read`；`/overview/pdf`、`/export`、`/generate`、`GET /templates` → `reports:export`；`POST/PUT/DELETE /templates` → `reports:manage` |
| users/roles | 全量 `users:*` / `roles:*` / `permissions:read` / `audit_logs:read` / `login_logs:read` |
| data-sources | `GET` 系列 → `sources:read`；写操作 → `require_admin` |
| collector | `POST /collector/run` → `require_admin` |

### 2.2 ⚠️ 仅登录校验、无权限校验的接口（问题面）

| 模块 | 接口 | 现状 | 风险 |
|---|---|---|---|
| **keywords** | `GET /keywords`、`GET /keywords/categories` | 仅 `get_current_user` | **P1**：viewer 无 `keywords:read` 仍可读取全部监测词/敏感词 |
| **analysis(AI)** | `POST /analyze/{opinion_id}` | 仅 `get_current_user` | **P1**：任意登录用户可消耗 DeepSeek 额度 |
| **bocha(AI检索)** | `/bocha/*`（web-search、ai-search、sessions、leads 等 8 个） | 仅 `get_current_user` | **P1**：任意登录用户可调用外部付费检索 |
| **anspire(AI检索)** | `/anspire/*`（5 个） | 仅 `get_current_user` | **P1**：同上 |
| dashboard | `/dashboard/*`（9 个） | 仅登录 | P3：与 `dashboard:read` 授权范围一致，暂不改 |
| opinions | `GET` 列表/详情/原文/sources | 仅登录 | P3：全角色均持 `opinions:read` |
| events | `GET` 列表/详情/关联/actions | 仅登录 | P3：全角色均持 `events:read` |
| alerts | `GET /rules`、`/records`、`/unread` | 仅登录 | P3 |
| propagation | 3 个接口 | 仅登录 | P3 |
| sources / tasks / collector status | 只读状态 | 仅登录 | P3（低风险） |

> 结论：**必须补齐** keywords 读接口与全部 AI 接口；其余读接口本次维持现状（避免触碰业务流程，且现有角色均已授予对应读权限）。

### 2.3 权限码一致性缺陷

1. `reports:write`（rbac10001 种子，"导出报告"）**已无任何接口引用**，实际导出用 `reports:export` —— 遗留冗余码，造成"报告权限界限不清"。
2. 前端 `Roles.vue` 的 `GROUP_LABEL` 写的是 `告警管理`，而数据库 group 实际是 `预警管理` → 该分组**未命中中文标签映射**，排序落到兜底 99 位。

---

## 三、前端权限审计

### 3.1 权限缓存与生效机制

| 环节 | 实现 | 文件 |
|---|---|---|
| 权限来源 | `POST /api/login` 响应体 `permissions[]` + `is_superuser` | `backend/app/api/auth.py:72-86` |
| 写入 | `authStore.setPermissions()` → `localStorage.permissions` | `views/Login.vue:74` |
| 读取 | `usePermission()` 只读 pinia/localStorage 缓存 | `composables/usePermission.ts` |
| 刷新 | **不存在**。全站仅 Login.vue 一处调用 `setPermissions` | grep 确认 |
| JWT 载荷 | 仅 `sub` + `exp` + `role`，**不含权限数组** | `core/security.py` |

**结论（回答"权限修改后何时生效"）**：权限只在登录瞬间计算并缓存；**F5 刷新不会更新权限**。用户感知到的"有时刷新就生效"实为：token 过期 → 任意 API 返回 401 → `api/index.ts:34` 拦截器强制登出 → 重新登录 → 拿到新权限。即**只有重登生效**。

### 3.2 路由 `meta.permission` 覆盖情况

| 路由 | meta.permission | 评价 |
|---|---|---|
| `/dashboard` | 无 | 可接受 |
| `/opinions`、`/opinion/:id` | 无 | 可接受 |
| `/events`、`/event/:id` | **无** | ⚠️ 需补 `events:read` |
| `/alerts` | `alerts:read` | ✅ |
| `/data`（含关键词） | **无** | ⚠️ 需补 `keywords:read` |
| `/ai-search`、`/ai-search/{web,ai,anspire}` | **无** | ⚠️ 需补 `ai:search` |
| `/propagation` | `propagation:read` | ✅ |
| `/system/*` | `users:read`/`roles:read`/`login_logs:read`/`audit_logs:read` | ✅ |
| `/command-screen` | 无（仅 fullscreen layout） | 本次不动 |

守卫逻辑 `router/index.ts:160-166`：无权限 → `ElMessage.warning('无权限访问该页面')` + 跳 `/dashboard`（**不会白屏**，已符合要求）。

### 3.3 按钮级门禁审计

| 位置 | 控件 | 现状 | 判定 |
|---|---|---|---|
| `Events.vue:152` | 「处置」按钮 | **无任何权限判断** | ❌ 必改 |
| `Events.vue:153` | 「删除」🗑 | **无任何权限判断** | ❌ 必改 |
| `Events.vue:430-442` | `handleDelete` | `catch { /* cancelled or error */ }` **空捕获** → 403 被静默吞掉，用户以为删成功 | ❌ 必改 |
| `Events.vue:190` | 弹窗内状态变更区 | `v-if="canUpdateEvent"`(`events:write`) | ✅ 已有 |
| `Alerts.vue:6` | 「新增规则」 | 无门禁 | ❌ 必改 |
| `Alerts.vue:30/31` | 「编辑」「删除」 | 无门禁 | ❌ 必改 |
| `Alerts.vue:8` | 「执行评估」 | 无门禁（后端 `alerts:write`） | ❌ 必改 |
| `Alerts.vue:25` | 规则启停开关 | 无门禁 | ❌ 必改 |
| `DataManage.vue:5-13` | 「关键词管理」tab | **始终可见**，且为默认 tab | ❌ 必改 |
| `Keywords.vue:26/71/77/78` | 新增/启停/编辑/删除 | **无门禁** | ❌ 必改 |
| `AppLayout.vue:236` | 侧边栏「AI检索」 | 无 `visible` | ❌ 必改 |
| `AppLayout.vue:242` | 侧边栏「数据管理」 | 无 `visible` | ❌ 必改 |
| `OpinionDetail.vue:91` / `OpinionDetailModal.vue:167` | 「触发 AI 分析」 | 无门禁 | ❌ 必改 |
| `Dashboard.vue:63` | 报告导出 | `v-if="can('reports:export')"` | ✅ 已有 |
| `Opinions.vue` | 编辑/删除 | `opinions:write` / `isSuperuser` | ✅ 已有 |
| `Roles.vue` / `SystemAdmin.vue` / `AppLayout` 系统菜单 | — | 已有门禁 | ✅ |

### 3.4 403 处理审计

`frontend/src/api/index.ts` 响应拦截器**只处理 401**（清 token + 强制跳登录）；**403 无任何统一处理**，完全依赖各调用点自行 `catch`。实测：

- `Alerts.vue` 保存规则失败 → 有 `ElMessage.error`（提示是后端 detail 英文 `Permission denied`）
- `Events.vue` 删除失败 → **空 catch，零提示**（用户核心痛点）

---

## 四、问题 → 处置映射（实施依据）

| # | 用户反馈问题 | 根因 | 处置方案 |
|---|---|---|---|
| 1 | 观察者可见事件处置/删除入口 | `Events.vue` 按钮无 `v-if` | 挂 `events:write` |
| 2 | 删除有确认框但失败无提示 | `catch {}` 空捕获 + 无 403 拦截 | 明确 catch + 全局 403 提示 |
| 3 | 无关键词权限可进关键词管理 | `/data` 无 meta、tab 无门禁、后端读接口无权限 | 路由 meta + tab 门禁 + 后端 `keywords:read` |
| 4 | 无预警写权限可进新增规则 | `Alerts.vue` 按钮无门禁 | 挂 `alerts:write` |
| 5 | 无 AI 权限体系 | 权限目录缺 `ai:*`，AI 接口仅登录 | 新增 3 个权限码 + 前后端挂载 |
| 6 | 报告权限界限不清 | `reports:write` 冗余；`reports:read`/`manage` 无 UI 绑定；分组无中文说明 | 权限页中文说明 + 前端入口映射 |
| 7 | 权限生效机制不明 | 权限仅登录时写 localStorage，无刷新通道 | 新增 `GET /api/auth/me` + 启动时刷新 |

---

## 五、实施边界确认（与约束逐条对照）

| 约束 | 遵守方式 |
|---|---|
| 不大规模重构 | 仅增量：1 个迁移、1 个新端点、若干 `Depends` 与 `v-if` |
| 保留 用户→角色→权限 模型 | 不改 `permissions.py` 判定算法，不改表结构 |
| 不引入新权限框架 | 复用 `require_permission` / `usePermission` |
| 不改业务逻辑 | 事件/舆情/预警/采集的 service 层零改动 |
| 兼容已有角色 | 新增 `ai:*` 授予 admin(超管天然全权) 与 analyst；viewer 补 `keywords:read`（只读，不扩权）；不撤销任何已有授权 |
| 不影响管理员 | `is_superuser_user` 短路逻辑不变，admin 恒 `["*"]` |
| 禁止项 | 不删权限表、不改管理员逻辑、不引 Redis/缓存服务、不改业务数据模型 |

---

## 六、待实施清单（预告）

**后端**
1. 新增迁移 `p31_rbac_ai_perms`：插入 `ai:search` / `ai:analyze` / `ai:manage`（group=`AI能力`），授予 `analyst`；给 `viewer` 补 `keywords:read`、`reports:read`。
2. `keywords.py`：`GET ""` 与 `GET /categories` 挂 `keywords:read`。
3. `analysis.py`：`POST /analyze/{id}` 挂 `ai:analyze`。
4. `bocha.py` / `anspire.py`：检索类接口挂 `ai:search`。
5. `auth.py`：新增 `GET /api/auth/me`。
6. `schemas/user.py`：新增 `MeResponse`。

**前端**
7. `api/index.ts`：新增 403 统一提示（不动 401）。
8. `router/index.ts`：`/events`+`events:read`、`/data`+`keywords:read`、`/ai-search*`+`ai:search`。
9. `Events.vue`：处置/删除按钮门禁 + 删除失败明确提示。
10. `Alerts.vue`：新增/编辑/删除/评估/启停挂 `alerts:write`。
11. `Keywords.vue`：写操作挂 `keywords:write`。
12. `DataManage.vue`：关键词 tab 挂 `keywords:read`。
13. `AppLayout.vue`：AI检索/数据管理菜单项 `visible` 绑定。
14. `OpinionDetail.vue` / `OpinionDetailModal.vue`：AI 分析按钮挂 `ai:analyze`。
15. `Roles.vue`：修 `告警管理`→`预警管理`，新增 `AI能力` 分组，补权限中文说明。
16. `main.ts` / `App.vue`：启动时若有 token 则调 `/auth/me` 刷新权限缓存。

**测试**
17. `tests/test_rbac_hardening.py`：observer/admin 权限矩阵 + `/auth/me` 契约。

---

*本报告为只读审计产物，未对生产库、代码或配置作任何变更。*
