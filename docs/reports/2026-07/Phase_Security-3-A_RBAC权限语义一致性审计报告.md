# Phase Security-3-A：RBAC权限语义一致性审计报告

> 审计日期：2026-07-31 | 审计范围：只读（未修改任何代码/数据库/配置）

---

## 1. 执行摘要

| 项目 | 数量 |
|---|---|
| 权限码 (permissions) | 31 |
| 角色 (roles) | 4（含 1 非系统角色 "111"） |
| 授权关系 (role_permissions) | 28 |
| 后端 API 路由 | 107 |
| 前端页面 | 23 views + 7 components |
| 前端路由 | 20 条 |

**审计结论**：发现 **6 项 HIGH / 4 项 MEDIUM / 3 项 LOW** 权限语义不一致问题，其中 5 项为用户测试直接反馈的根因。

---

## 2. 权限资产清单

| 权限码 | 中文名 | resource | action | 分组 | description |
|---|---|---|---|---|---|
| ai:analyze | AI研判 | ai | analyze | AI能力 | 对单条舆情触发 AI 研判分析 |
| ai:manage | AI配置管理 | ai | manage | AI能力 | 管理 AI 服务配置（预留） |
| ai:search | AI检索 | ai | search | AI能力 | 使用 AI 检索（Web/AI/Anspire）并保存线索 |
| events:read | 查看事件 | events | read | 事件管理 | 查看事件中心 |
| events:write | 管理事件 | events | write | 事件管理 | 聚合/编辑事件 |
| propagation:read | 查看传播 | propagation | read | 传播溯源 | 查看传播路径 |
| keywords:delete | 删除关键词 | keywords | delete | 关键词管理 | 删除关键词 |
| keywords:read | 查看关键词 | keywords | read | 关键词管理 | 查看监测/敏感词 |
| keywords:write | 管理关键词 | keywords | write | 关键词管理 | 增删改关键词 |
| audit_logs:read | 查看操作日志 | audit_logs | read | 审计 | 查看操作审计日志 |
| login_logs:read | 查看登录日志 | login_logs | read | 审计 | 查看登录日志 |
| reports:export | 导出报告 | reports | export | 报告 | 导出PDF报告 |
| reports:manage | 管理报告模板 | reports | manage | 报告 | 管理报告模板（保存/编辑/删除） |
| reports:read | 查看报告 | reports | read | 报告 | 查看分析报告 |
| reports:write | 导出报告 | reports | write | 报告 | 导出PDF报告 |
| sources:read | 查看数据源 | sources | read | 数据源 | 查看数据源 |
| sources:write | 管理数据源 | sources | write | 数据源 | 管理数据源 |
| permissions:read | 查看权限 | permissions | read | 权限管理 | 查看权限目录 |
| users:activate | 启用/停用用户 | users | activate | 用户管理 | 启用或停用用户 |
| users:read | 查看用户 | users | read | 用户管理 | 查看用户列表与详情 |
| users:write | 管理用户 | users | write | 用户管理 | 创建/编辑用户 |
| opinions:read | 查看舆情 | opinions | read | 舆情管理 | 查看舆情列表/详情 |
| opinions:write | 管理舆情 | opinions | write | 舆情管理 | 删除/编辑舆情 |
| roles:delete | 删除角色 | roles | delete | 角色管理 | 删除非系统角色 |
| roles:read | 查看角色 | roles | read | 角色管理 | 查看角色列表 |
| roles:write | 管理角色 | roles | write | 角色管理 | 创建/编辑/分配权限 |
| collectors:read | 查看采集 | collectors | read | 采集管理 | 查看采集任务 |
| collectors:write | 管理采集 | collectors | write | 采集管理 | 启停采集任务 |
| alerts:read | 查看预警 | alerts | read | 预警管理 | 查看预警规则与记录 |
| alerts:write | 管理预警 | alerts | write | 预警管理 | 配置/评估预警 |
| dashboard:read | 查看驾驶舱 | dashboard | read | 驾驶舱 | 查看数据总览 |

---

## 3. 权限-角色矩阵

| 权限码 | admin | analyst | viewer | 111 |
|---|---|---|---|---|
| ai:analyze | ✅ | ✅ | ⛔ | ⛔ |
| ai:manage | ✅ | ⛔ | ⛔ | ⛔ |
| ai:search | ✅ | ✅ | ⛔ | ⛔ |
| alerts:read | ✅(短路) | ✅ | ✅ | ⛔ |
| alerts:write | ✅(短路) | ✅ | ⛔ | ⛔ |
| audit_logs:read | ✅(短路) | ⛔ | ⛔ | ⛔ |
| collectors:read | ✅(短路) | ⛔ | ⛔ | ⛔ |
| collectors:write | ✅(短路) | ⛔ | ⛔ | ⛔ |
| dashboard:read | ✅(短路) | ✅ | ✅ | ⛔ |
| events:read | ✅(短路) | ✅ | ✅ | ⛔ |
| events:write | ✅(短路) | ✅ | ⛔ | ⛔ |
| keywords:delete | ✅(短路) | ⛔ | ⛔ | ⛔ |
| keywords:read | ✅(短路) | ✅ | ⛔ | ⛔ |
| keywords:write | ✅(短路) | ✅ | ⛔ | ⛔ |
| login_logs:read | ✅(短路) | ⛔ | ⛔ | ⛔ |
| opinions:read | ✅(短路) | ✅ | ✅ | ✅ |
| opinions:write | ✅(短路) | ✅ | ⛔ | ⛔ |
| permissions:read | ✅(短路) | ⛔ | ⛔ | ⛔ |
| propagation:read | ✅(短路) | ✅ | ✅ | ⛔ |
| reports:export | ✅(短路) | ✅ | ⛔ | ⛔ |
| reports:manage | ✅ | ✅ | ⛔ | ⛔ |
| reports:read | ✅(短路) | ✅ | ⛔ | ⛔ |
| reports:write | ✅(短路) | ✅ | ⛔ | ⛔ |
| roles:delete | ✅(短路) | ⛔ | ⛔ | ⛔ |
| roles:read | ✅(短路) | ⛔ | ⛔ | ⛔ |
| roles:write | ✅(短路) | ⛔ | ⛔ | ⛔ |
| sources:read | ✅(短路) | ✅ | ⛔ | ⛔ |
| sources:write | ✅(短路) | ✅ | ⛔ | ⛔ |
| users:activate | ✅(短路) | ⛔ | ⛔ | ⛔ |
| users:read | ✅(短路) | ⛔ | ⛔ | ⛔ |
| users:write | ✅(短路) | ⛔ | ⛔ | ⛔ |

> admin 在 role_permissions 表仅 4 条授权（ai:analyze/ai:manage/ai:search/reports:manage），其余靠 `is_superuser_user()` 短路返回 `["*"]`。

---

## 4. 权限-API矩阵

### 写接口（47 个业务写接口，100% 权限覆盖）

| API | 方法 | 权限码 |
|---|---|---|
| /api/opinions | POST | opinions:write |
| /api/opinions/batch | PATCH | opinions:write |
| /api/opinions/{id} | PATCH | opinions:write |
| /api/opinions/batch | DELETE | ADMIN |
| /api/opinions/{id} | DELETE | ADMIN |
| /api/keywords | POST | keywords:write |
| /api/keywords/{id} | PUT | keywords:write |
| /api/keywords/{id} | DELETE | **keywords:write**（非 keywords:delete） |
| /api/events/aggregate | POST | events:write |
| /api/events/{id}/status | PATCH | events:write |
| /api/events/{id}/actions | POST | events:write |
| /api/events/{id} | DELETE | events:write |
| /api/alerts/rules | POST | alerts:write |
| /api/alerts/rules/{id} | PUT | alerts:write |
| /api/alerts/rules/{id} | DELETE | alerts:write |
| /api/alerts/evaluate | POST | alerts:write |
| /api/alerts/records/{id}/handle | PUT | alerts:write |
| /api/propagation/rebuild/{id} | POST | events:write |
| /api/analyze/{id} | POST | ai:analyze |
| /api/reports/export | POST | reports:export |
| /api/reports/generate | POST | reports:export |
| /api/reports/templates | POST | reports:manage |
| /api/reports/templates/{id} | PUT | reports:manage |
| /api/reports/templates/{id} | DELETE | reports:manage |
| /api/users | POST | users:write |
| /api/users/{id} | PUT | users:write |
| /api/users/{id} | DELETE | users:write |
| /api/users/{id}/reset-password | POST | users:write |
| /api/users/{id}/activate | POST | users:activate |
| /api/users/{id}/deactivate | POST | users:activate |
| /api/roles | POST | roles:write |
| /api/roles/{id} | PUT | roles:write |
| /api/roles/{id} | DELETE | roles:delete |
| /api/collector/run | POST | ADMIN |
| /api/admin/data-sources | POST | ADMIN |
| /api/admin/data-sources/{id} | PATCH | ADMIN |
| /api/admin/data-sources/test | POST | ADMIN |
| /api/admin/bocha/search | POST | ADMIN |
| /api/admin/bocha/leads/{id}/confirm | POST | ADMIN |
| /api/admin/bocha/leads/{id}/reject | POST | ADMIN |
| /api/admin/bocha/leads/{id}/promote | POST | ADMIN |
| /api/bocha/search | POST | ai:search |
| /api/bocha/ai-search | POST | ai:search |
| /api/bocha/ai-leads | POST | ai:search |
| /api/bocha/leads | POST | ai:search |
| /api/anspire/search | POST | ai:search |
| /api/anspire/leads | POST | ai:search |
| /api/login | POST | 无（鉴权端点） |
| /api/logout | POST | 无（鉴权端点） |

### 读接口（54 个，26 有权限门控，28 仅 LOGIN_ONLY）

| API | 权限码 | 备注 |
|---|---|---|
| /api/dashboard/stats | LOGIN_ONLY | ⛔ dashboard:read 未生效 |
| /api/dashboard/recent | LOGIN_ONLY | ⛔ |
| /api/dashboard/alerts | LOGIN_ONLY | ⛔ |
| /api/dashboard/hot-keywords | LOGIN_ONLY | ⛔ |
| /api/dashboard/region-children | LOGIN_ONLY | ⛔ |
| /api/dashboard/kpi-trends | LOGIN_ONLY | ⛔ |
| /api/dashboard/risk-distribution | LOGIN_ONLY | ⛔ |
| /api/dashboard/alert-stats | LOGIN_ONLY | ⛔ |
| /api/opinions (GET) | LOGIN_ONLY | ⛔ opinions:read 未生效 |
| /api/opinions/sources | LOGIN_ONLY | ⛔ |
| /api/opinions/{id} | LOGIN_ONLY | ⛔ |
| /api/opinions/{id}/original | LOGIN_ONLY | ⛔ |
| /api/events (GET) | LOGIN_ONLY | ⛔ events:read 未生效 |
| /api/events/{id} | LOGIN_ONLY | ⛔ |
| /api/events/{id}/situation | LOGIN_ONLY | ⛔ |
| /api/events/{id}/opinions | LOGIN_ONLY | ⛔ |
| /api/alerts/rules (GET) | LOGIN_ONLY | ⛔ alerts:read 未生效 |
| /api/alerts/unread | LOGIN_ONLY | ⛔ |
| /api/alerts/records | LOGIN_ONLY | ⛔ |
| /api/sources/status | LOGIN_ONLY | ⛔ sources:read 未生效 |
| /api/sources/history | LOGIN_ONLY | ⛔ |
| /api/collector/status | LOGIN_ONLY | ⛔ collectors:read 未生效 |
| /api/keywords (GET) | keywords:read | ✅ |
| /api/keywords/categories | keywords:read | ✅ |
| /api/reports/overview | reports:read | ✅ |
| /api/reports/modules | reports:read | ✅ |
| /api/reports/overview/pdf | reports:export | ✅ |
| /api/reports/templates (GET) | reports:export | ✅（见问题4） |
| /api/users (GET) | users:read | ✅ |
| /api/users/{id} | users:read | ✅ |
| /api/roles (GET) | roles:read | ✅ |
| /api/roles/{id} | roles:read | ✅ |
| /api/permissions | permissions:read | ✅ |
| /api/login-logs | login_logs:read | ✅ |
| /api/operation-logs | audit_logs:read | ✅ |
| /api/admin/data-sources (GET) | sources:read | ✅ |
| /api/admin/data-sources/quality | sources:read | ✅ |
| /api/admin/data-sources/{id}/runs | sources:read | ✅ |
| /api/admin/data-sources/collection-logs | sources:read | ✅ |
| /api/admin/data-sources/collection-logs/{key}/runs | sources:read | ✅ |
| /api/bocha/sessions | ai:search | ✅ |
| /api/bocha/leads (GET) | ai:search | ✅ |
| /api/bocha/ai-search/options | ai:search | ✅ |
| /api/anspire/options | ai:search | ✅ |
| /api/anspire/sessions | ai:search | ✅ |
| /api/anspire/leads (GET) | ai:search | ✅ |
| /api/propagation/events | LOGIN_ONLY | ⛔ propagation:read 未后端生效 |
| /api/propagation/graph/{id} | LOGIN_ONLY | ⛔ |

---

## 5. 权限-页面矩阵

| 权限码 | 页面入口 | 菜单可见性 | 路由 meta.permission | 实际可达性 |
|---|---|---|---|---|
| dashboard:read | /dashboard | 始终可见（无权限门） | **无** | ⛔ analyst/viewer 都可进，但权限码无实际作用 |
| opinions:read | /opinions | 始终可见 | **无** | ⛔ 同上 |
| opinions:write | Opinions.vue 内按钮 | — | — | ✅ 编辑按钮用 hasPermission('opinions:write') |
| events:read | /events | 始终可见 | **events:read** | ✅ 路由守卫生效 |
| events:write | Events.vue 内按钮 | — | — | ✅ 笔记区 v-if="canUpdateEvent" |
| alerts:read | /alerts | 始终可见 | **alerts:read** | ✅ 路由守卫生效 |
| keywords:read | /data (关键词 tab) | hasPermission('keywords:read') || isSuperuser | **keywords:read** | ✅ |
| keywords:write | Keywords.vue 内按钮 | — | — | ✅ v-if="canWriteKeyword" |
| propagation:read | /propagation | 始终可见 | **propagation:read** | ✅ |
| ai:search | /ai-search | hasAiSearchPerm | **ai:search** | ✅ |
| sources:read | /data (数据源 tab) | **isSuperuser**（非 sources:read） | keywords:read（路由级） | ⛔ analyst 有权限但看不到页面 |
| sources:write | /data (数据源 tab) | **isSuperuser** | — | ⛔ analyst 有权限但看不到页面 |
| collectors:read | 无独立页面 | — | — | ⛔ 权限码无前端载体 |
| collectors:write | AppLayout 采集按钮 | **isSuperuser** | — | ⛔ analyst 有权限但无入口 |
| reports:read | Dashboard.vue 报告数据区 | — | — | ✅ 后端 require_permission 生效 |
| reports:export | Dashboard.vue 导出按钮 | — | — | ✅ v-if="can('reports:export')" |
| reports:manage | ReportExportDrawer.vue 模板按钮 | — | — | ✅ canManageTemplate |
| reports:write | 无独立页面 | — | — | ⛔ 冗余，无代码引用 |
| users:read | /system/users | hasSystemPerm | **users:read** | ✅ |
| roles:read | /system/roles | hasSystemPerm | **roles:read** | ✅ |

---

## 6. 权限-按钮矩阵

| 页面 | 按钮 | 权限控制方式 | 使用的权限码 | 状态 |
|---|---|---|---|---|
| Opinions.vue | 批量删除 | **isSuperuser** | — | ⛔ SEC3-01: opinions:write 无法触发删除 |
| Opinions.vue | 编辑/勾选 | hasPermission | opinions:write | ✅ |
| Events.vue | 笔记/操作区 | v-if canUpdateEvent | events:write | ✅ |
| Propagation.vue | 构建传播链 | v-if canRebuild | events:write | ✅ |
| Dashboard.vue | 导出报告按钮 | v-if can | reports:export | ✅ |
| ReportExportDrawer | 保存为模板/删除模板 | canManageTemplate | reports:manage | ✅ |
| Keywords.vue | 新增/编辑/删除 | v-if canWriteKeyword | keywords:write | ✅（含删除） |
| AppLayout.vue | 手动采集 | v-if isSuperuser | — | ⛔ |
| AppLayout.vue | 数据管理菜单 | hasDataPerm | keywords:read || isSuperuser | ⛔ 数据源tab被isSuperuser锁 |
| DataManage.vue | 数据源/日志/博察 tab | v-if isSuperuser | — | ⛔ analyst 有 sources:read/write 但看不到 |

---

## 7. 发现问题列表

### SEC3-01 ⛔ HIGH — opinions:write 与删除按钮语义断裂

**问题**：analyst 拥有 `opinions:write` 权限，DB description 定义为"删除/编辑舆情"，但前端删除按钮用的是 `isSuperuser`，后端删除接口用的是 `require_admin`。**analyst 拥有权限码却无法删除**。

**根因**：
- 前端 `Opinions.vue` L291: `canDelete = computed(() => isSuperuser.value)` — 仅超管可见删除按钮
- 后端 `DELETE /api/opinions/{id}` 和 `DELETE /api/opinions/batch` 使用 `require_admin` — 仅超管可执行
- 权限码 `opinions:write` description = "删除/编辑舆情"，但实际删除被 ADMIN 独占

**影响**：权限码语义与实际能力严重不一致，analyst 配了"管理舆情"却只能编辑、不能删除

**建议**：二选一——
- A（推荐）：**让 opinions:write 涵盖删除**：前端 `canDelete` 改为 `hasPermission('opinions:write')`，后端 DELETE 改为 `require_permission('opinions:write')`
- B：**权限码 description 改为"编辑舆情"，删除仍归 ADMIN**：需要新增 `opinions:delete` 权限码或维持 ADMIN-only，但必须修正 description 不再暗示删除

---

### SEC3-02 ⛔ HIGH — sources:read/write 在前端完全无效

**问题**：analyst 被授予 `sources:read` + `sources:write`，但无法看到数据源页面。

**根因**：
- `AppLayout.vue` L227: `hasDataPerm = hasPermission('keywords:read') || isSuperuser.value` — 数据管理菜单可见性不依赖 sources:read
- `DataManage.vue` L16/26/36: 数据源/日志/博察 tab 全部用 `v-if="isSuperuser"` — 容器级锁死
- `DataManage.vue` L71-72 注释：**"数据源接口后端实际使用 require_admin（即超管专属），与 sources:read/write 种子权限不一致"**
- 后端 `admin_data_sources.py` 写接口（创建/修改/测试）全用 `require_admin`，仅读接口用 `sources:read`

**影响**：analyst 拥有 `sources:read`+`sources:write` 权限码，但前端完全不承认——菜单锁在 isSuperuser、后端写接口锁在 ADMIN。权限码形同虚设。

**建议**：
- A（推荐）：**承认现实，修改权限码语义**——`sources:read` 仅保护 `/api/admin/data-sources` GET 端点（后端已生效），前端 tab 保持 isSuperuser 锁定（因为写操作全是 ADMIN-only，给 analyst 开 tab 看到却不能操作反而体验更差）。从 analyst 角色移除 `sources:write`（无后端写入口对应），`sources:read` 保留但改 description 为"查看数据源运行状态（管理操作限超管）"
- B：**扩展 analyst 能力**——后端数据源写接口改为 `require_permission('sources:write')`、前端 tab 改为 `hasPermission('sources:read')`。但这改变了管理员独占数据源的设计意图，需重新确认业务需求

---

### SEC3-03 ⛔ HIGH — keywords:write 与 keywords:delete 语义重复

**问题**：`keywords:write`（description="增删改关键词"）与 `keywords:delete`（description="删除关键词")职责重叠。

**根因**：
- 后端 `DELETE /api/keywords/{id}` 使用 `keywords:write`（非 keywords:delete）
- 前端 `Keywords.vue` L156: `canWriteKeyword = hasPermission("keywords:write")` — 新增/编辑/删除全部走此码
- **keywords:delete 在后端和前端零引用**——纯孤儿权限
- DB 中 keywords:delete 无任何角色授权（admin 靠短路获得，analyst/viewer 均无）

**影响**：keywords:delete 存在但无效，keywords:write 已涵盖删除功能

**建议**：**废弃 keywords:delete**（从 permissions 表删除或标记 is_enabled=false），description 修正为确认 keywords:write 包含删除

---

### SEC3-04 ⛔ HIGH — reports:write 与 reports:export 语义重复

**问题**：`reports:write`（description="导出PDF报告")与 `reports:export`（description="导出PDF报告")description 完全相同。

**根因**：
- 后端 `/api/reports/export`、`/api/reports/generate`、`/api/reports/overview/pdf`、`/api/reports/templates`(GET) 全用 `reports:export`
- 前端 Dashboard.vue 导出按钮用 `can('reports:export')`；ReportExportDrawer 用 `reports:manage`
- **reports:write 在后端和前端零引用**——纯孤儿权限
- analyst 同时持有 reports:export + reports:write（功能重复授权）

**影响**：两个权限码做同一件事，reports:write 完全冗余

**建议**：**废弃 reports:write**，从 analyst 角色授权中移除

---

### SEC3-05 ⛔ HIGH — reports:read 取消后 API 仍可访问

**问题**：用户反馈取消 `reports:read` 后，前端有警告弹窗但"实际上仍可正常进行后续操作"。

**根因**：
- 前端**无 /reports 路由**（注释明确"报告能力无独立路由（Dashboard 内导出抽屉），由 reports:export / reports:manage 控制按钮"）
- 前端 Dashboard.vue 调用 `/api/dashboard/*` 和 `/api/reports/overview` 等 API——这些 API **无前端路由守卫**
- `reports:read` 保护的是 `/api/reports/overview` 和 `/api/reports/modules`（后端 `require_permission("reports:read")` 生效）
- 用户取消 reports:read → 后端返回 403 → 前端 axios 全局拦截弹警告 → **但 Dashboard 页面本身仍然渲染**（仅数据加载失败）
- 真正的操作入口（导出按钮）由 `reports:export` 保护，不受 reports:read 取消影响

**影响**：reports:read 语义模糊——它保护的是"查看报告数据 API"，而非"查看报告页面入口"

**建议**：
- A：**修正 reports:read description**为"查看报告分析数据（Dashboard 内的 overview/modules API）"，让用户理解取消它只是让 Dashboard 报告数据区空显示，不影响导出功能
- B：**前端在 Dashboard 报告区加容器级 v-if="hasPermission('reports:read')"**——取消后不显示报告数据区域，而非空数据+弹窗

---

### SEC3-06 ⛔ MEDIUM — collectors:read/write 权限码无前端载体

**问题**：`collectors:read`、`collectors:write` 存在于 permissions 表，analyst 无授权但权限码定义了。

**根因**：
- 后端 `/api/collector/status` 仅 LOGIN_ONLY（无 require_permission）
- 后端 `/api/collector/run` 用 `require_admin`（非 collectors:write）
- 前端无独立采集管理页面——采集操作入口是 AppLayout.vue 的手动采集按钮（`v-if="isSuperuser"`）
- 前端 `CollectionLog.vue` 只在 DataManage 的 isSuperuser tab 内显示

**影响**：collectors:read/write 是完全的孤儿权限——后端不引用、前端不引用、无角色持有

**建议**：**废弃 collectors:read 和 collectors:write**，或改后端采集读接口为 `collectors:read`、写接口为 `collectors:write`

---

### SEC3-07 ⛔ MEDIUM — dashboard:read 权限码后端未生效

**问题**：`dashboard:read` 存在于 permissions 表，analyst/viewer 均持有，但后端 Dashboard API 全为 LOGIN_ONLY。

**根因**：
- 8 个 `/api/dashboard/*` 端点均为 `LOGIN_ONLY`（仅 require get_current_user）
- 前端 `/dashboard` 路由 **无 meta.permission**（仅 requiresAuth: true）
- AppLayout 菜单中驾驶舱始终可见（无 visible 条件）
- dashboard:read 在后端和前端**零引用**

**影响**：任何登录用户都能访问驾驶舱——dashboard:read 权限码完全无效

**建议**：
- A（推荐）：**废弃 dashboard:read**——驾驶舱是所有登录用户的基础入口，不应受权限码限制
- B：**让 dashboard:read 生效**——后端加 `require_permission("dashboard:read")`、前端路由加 `meta.permission: 'dashboard:read'`——但这会让 viewer 如果取消此权限就看不到首页

---

### SEC3-08 ⛔ MEDIUM — 28 个 GET 接口仅 LOGIN_ONLY（读权限码未后端生效）

**问题**：opinions:read、events:read、alerts:read、propagation:read、sources:read、collectors:read 等读权限码在后端 GET 接口未强制。

**根因**：Phase Security-2 SEC2-02 已记录此问题（26 个 GET 未强制 :read），当时决定维持现状。当前数量为 28 个（新增 dashboard 8 + propagation 2 + sources 2 + collector 1）。

**影响**：权限码定义了"查看"语义但后端不强制——前端路由守卫是唯一防线，绕过前端可直调 API

**建议**：维持现状（Phase Security-2 已确认），但需在权限码 description 注明"前端路由级控制，后端仅登录态"

---

### SEC3-09 ⛔ LOW — ai:manage 孤儿权限

**问题**：`ai:manage` description="管理 AI 服务配置（预留）"，仅在 admin role_permissions 有授权，后端/前端零引用。

**建议**：保留（预留权限），标记 description 为"预留"

---

### SEC3-10 ⛔ LOW — 角色 "111" 非系统角色 + 0 用户

**问题**：roles 表 id=5 name="111" 非系统角色、enabled=true、0 用户、仅授权 opinions:read。

**建议**：清理或禁用

---

### SEC3-11 ⛔ LOW — reports:export 保护了模板列表 GET

**问题**：`GET /api/reports/templates` 用 `reports:export` 而非 `reports:read`——查看模板列表需要导出权限。

**根因**：模板列表在导出抽屉中选择，逻辑上属于导出流程的一部分，但从权限语义看"查看模板"≠"导出报告"。

**建议**：维持现状（模板选择是导出流程前置步骤），或改为 `reports:read` + `reports:export` 任一即可

---

## 8. 权限治理建议

### A. 必须修复（6 项 HIGH）

| 编号 | 建议 | 修改范围 | 风险 |
|---|---|---|---|
| SEC3-01 | opinions 删除按钮改 hasPermission('opinions:write') 或改 description | 前端 Opinions.vue L291 + 后端 opinions.py DELETE 路由 | 改变删除操作权限归属 |
| SEC3-02 | analyst 移除 sources:write，sources:read 改 description | DB role_permissions + permissions description | 权限码语义修正 |
| SEC3-03 | 废弃 keywords:delete | DB permissions 表 + role_permissions 清理 | 删除孤儿权限 |
| SEC3-04 | 废弃 reports:write | DB permissions 表 + role_permissions 清理 | 删除孤儿权限 |
| SEC3-05 | reports:read description 修正 + 前端容器级 v-if | permissions description + Dashboard.vue | UI 行为变化 |
| SEC3-02-alt | 如果决定开放数据源给 analyst | 后端 admin_data_sources.py + 前端 DataManage.vue + AppLayout.vue | 设计意图变更，需业务确认 |

### B. 建议优化（4 项 MEDIUM）

| 编号 | 建议 |
|---|---|
| SEC3-06 | 废弃 collectors:read/write 或改造后端采集接口 |
| SEC3-07 | 废弃 dashboard:read（驾驶舱为基础入口） |
| SEC3-08 | 读权限码 description 加注"前端路由级控制" |
| SEC3-11 | 模板列表 GET 权限改为 read 或 export 任一即可 |

### C. 保留现状（2 项 LOW）

| 编号 | 说明 |
|---|---|
| SEC3-09 | ai:manage 预留权限，暂不处理 |
| SEC3-10 | 角色 "111" 需人工确认后清理 |

---

## 9. 五项重点问题根因结论

### 问题1：analyst 有 opinions:write 但无删除按钮

**根因**：前端删除按钮用 `isSuperuser` 独占，后端删除接口用 `require_admin` 独占。`opinions:write` 的 description 暗示包含删除，但实际删除被 ADMIN 独占。**这是权限码语义与实际实现不一致**，不是权限配置错误。

### 问题2：analyst 有 sources:read/write 但无法进数据源页面

**根因**：前端 DataManage.vue 数据源 tab 用 `isSuperuser` 锁死（代码注释已承认"后端实际使用 require_admin，与种子权限不一致"）。`sources:read` 在后端 GET 接口生效（analyst 可直调 API 获取数据源列表），但前端页面入口不承认此权限。`sources:write` 在后端零入口（写操作全 ADMIN-only）。**这是权限码定义与业务设计冲突**——业务设计决定数据源管理限超管，但权限码仍分配给了 analyst。

### 问题3：keywords:write 与 keywords:delete 是否重复

**结论**：**完全重复**。keywords:delete 是孤儿权限——后端删除接口用 keywords:write，前端删除按钮用 canWriteKeyword。keywords:delete 在后端/前端零引用、零授权。建议废弃 keywords:delete。

### 问题4：报告4权限是否重复

**结论**：
- `reports:write` 与 `reports:export` description 完全相同（"导出PDF报告"），**reports:write 是孤儿权限**——后端/前端零引用
- `reports:read` 与 `reports:export` 职责不同：read 保护查看数据 API，export 保护导出操作
- `reports:manage` 职责独立：保护模板 CRUD
- **建议废弃 reports:write**

### 问题5：collectors:read/write/dashboard:read 为什么无效

**根因**：
- **collectors:read**：后端 `/api/collector/status` 仅 LOGIN_ONLY（未引用此权限码）；前端无独立页面
- **collectors:write**：后端 `/api/collector/run` 用 require_admin（非此权限码）；前端采集按钮 isSuperuser
- **dashboard:read**：后端 8 个 dashboard API 全 LOGIN_ONLY；前端 /dashboard 路由无 meta.permission
- **三者均为权限码定义了但后端/前端完全不引用**——属于"权限存在但无作用"

---

## 10. 是否建议进入修复阶段

**建议进入 Phase Security-3-B 修复阶段**，优先处理 6 项 HIGH 问题。

修复顺序建议：
1. SEC3-03 + SEC3-04：废弃孤儿权限（keywords:delete、reports:write）——最安全、无功能影响
2. SEC3-01：opinions 删除权限语义对齐——需确认业务意图（analyst 是否应能删除？）
3. SEC3-02：sources 权限码语义修正——需确认业务意图（数据源管理是否应限超管？）
4. SEC3-05：reports:read description 修正 + 前端容器级门控
5. SEC3-06/07：collectors/dashboard 孤儿权限清理

---

> 审计完成。未修改任何代码、数据库、配置。仅生成此报告。
