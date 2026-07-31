# Phase Security-2-D：前端权限覆盖报告

- 生成时间：2026-07-31
- 扫描范围：`frontend/src/router/index.ts`、`frontend/src/views/*.vue`（23 个）、`frontend/src/components/*.vue`（7 个）
- 扫描方式：静态源码解析 + 逐项人工复核

> 本报告由只读审计脚本自动生成，全过程未修改任何代码、数据库记录或权限数据。
> 数据来源：生产库 `opinion_db@127.0.0.1:5432`（仅 SELECT）+ FastAPI 路由内省 + 前端源码静态扫描。

> **说明**：前端权限控制属于 **UX 层**，真正的安全边界在后端。本报告的判定标准是「管理员级入口是否对无权限用户隐藏」，而非「是否可被绕过」（前端一定可被绕过）。

> **扫描注记**：`Users.vue` 曾在原生工具下读取为乱码（虚拟化 FS 造成，特征字节 `88 7d 1c`），改用 Node 读取后确认为正常 405 行源码，门控完整。

---

## 一、路由级权限门槛

路由守卫位于 `router/index.ts` `beforeEach`：未登录 → `/login`；`canAccessRoute(to.meta)` 不通过 → `ElMessage.warning('权限不足，请联系管理员')` 并重定向 `/dashboard`。

| 路由 | 视图 | `meta.permission` | 判定 |
|---|---|---|---|
| `/dashboard` | Dashboard | — | ✅ 通用页面（登录即可） |
| `/opinions` | Opinions | — | ✅ 通用页面（登录即可） |
| `/opinion/:id` | OpinionDetail | — | ✅ 通用页面（登录即可） |
| `/ai-search` | AiSearch | `ai:search` | ✅ 已设门槛 |
| `/ai-search/web` | WebSearch | `ai:search` | ✅ 已设门槛 |
| `/ai-search/ai` | AiSearchPanel | `ai:search` | ✅ 已设门槛 |
| `/ai-search/anspire` | AnspireSearch | `ai:search` | ✅ 已设门槛 |
| `/events` | Events | `events:read` | ✅ 已设门槛 |
| `/event/:id` | EventDetail | `events:read` | ✅ 已设门槛 |
| `/alerts` | Alerts | `alerts:read` | ✅ 已设门槛 |
| `/data` | DataManage | `keywords:read` | ✅ 已设门槛 |
| `/propagation` | Propagation | `propagation:read` | ✅ 已设门槛 |
| `/system → users` | Users | `users:read` | ✅ 已设门槛 |
| `/system → roles` | Roles | `roles:read` | ✅ 已设门槛 |
| `/system → login-logs` | LoginLogs | `login_logs:read` | ✅ 已设门槛 |
| `/system → operation-logs` | OperationLogs | `audit_logs:read` | ✅ 已设门槛 |
| `/command-screen` | CommandScreen | — | ✅ 通用页面（登录即可） |

> `/keywords`、`/sources`、`/users`、`/roles`、`/login-logs`、`/operation-logs` 为 redirect 别名，最终落到已设门槛的 `/data` 与 `/system` 子路由，无绕过路径。

---

## 二、页面内操作级权限门控

共扫描到 `@click` 绑定 **138** 处，其中变更类操作 **71** 处。逐项复核结果如下：

| 视图 | 受控操作 | 门控表达式 | 对应权限 | 判定 |
|---|---|---|---|---|
| `Users.vue` | 新增用户 / 编辑 / 删除 | `v-if="canWrite"` | users:write | ✅ 已控 |
| `Users.vue` | 启用 / 停用 | `v-if="canActivate"` | users:activate | ✅ 已控 |
| `Users.vue` | 登录日志页签 | `v-if="canLoginLogs"` | login_logs:read | ✅ 已控 |
| `Users.vue` | 操作日志页签 | `v-if="canOpLogs"` | audit_logs:read | ✅ 已控 |
| `Roles.vue` | 新建角色 | `v-if="canWrite"` | roles:write | ✅ 已控 |
| `Roles.vue` | 编辑权限 / 保存 | `v-if="canWrite && !isAdminRole"` | roles:write | ✅ 已控 |
| `Roles.vue` | 删除角色 | `v-if="canDelete && !r.is_system"` | roles:delete | ✅ 已控 |
| `Alerts.vue` | 新增/编辑/删除规则、手动评估、处置 | `v-if="canWriteAlert"` | alerts:write | ✅ 已控 |
| `Events.vue` | 手动聚合 / 处置 / 删除 / 状态变更 / 备注 | `v-if="canUpdateEvent"` | events:write | ✅ 已控 |
| `EventDetail.vue` | 状态变更 / 添加备注 | `v-if="canUpdateEvent"` | events:write | ✅ 已控 |
| `Keywords.vue` | 新建 / 编辑 / 删除 / 启停 | `v-if="canWriteKeyword"（v-else 分支）` | keywords:write | ✅ 已控 |
| `Opinions.vue` | 批量删除 | `:disabled="!canDelete"` | opinions:write | ⚠️ 仅 disabled（未隐藏） |
| `Opinions.vue` | 编辑舆情 | `v-if="canEditOpinion"` | opinions:write | ✅ 已控 |
| `OpinionDetail.vue / OpinionDetailModal.vue` | AI 研判 | `v-if="canAnalyze && ..."` | ai:analyze | ✅ 已控 |
| `DataManage.vue` | 关键词管理页签 | `v-if="canReadKeyword"` | keywords:read | ✅ 已控 |
| `DataManage.vue` | 数据源管理 / 采集日志 / AI线索审核 页签 | `v-if="isSuperuser"` | （超管短路） | ✅ 容器级已控 |
| `SystemAdmin.vue` | 四个管理页签 | `v-if="canUsers/canRoles/canLoginLogs/canOperationLogs"` | users:read / roles:read / login_logs:read / audit_logs:read | ✅ 已控 |
| `AppLayout.vue` | 系统管理菜单项 | `hasPermission(users:read/roles:read/login_logs:read/audit_logs:read)` | 同左 | ✅ 已控 |
| `AppLayout.vue` | 手动采集入口 | `v-if="isSuperuser"` | （超管短路） | ✅ 已控 |
| `Sources.vue` | 新建采集源 / 配置 / 测试连接 / 保存 | `无按钮级门控` | sources:write（后端 require_admin） | ✅ 由 DataManage 容器 isSuperuser 兜底 |
| `CollectionLog.vue` | 刷新 / 展开 | `无（只读操作）` | - | ✅ 容器级已控 |
| `BochaLeadReview.vue` | 确认 / 驳回 / 提升为舆情 / 批量 | `无按钮级门控` | 后端 require_admin | ✅ 由 DataManage 容器 isSuperuser 兜底 |
| `WebSearch.vue / AnspireSearch.vue / AiSearchPanel.vue` | 搜索 / 保存线索 | `无按钮级门控` | ai:search | ✅ 由路由 meta.permission 兜底 |
| `Propagation.vue` | 构建传播链（handleRebuild） | `**无任何门控**` | 无（后端仅登录态） | ⛔ 缺失 |

---

## 三、问题清单

### ⛔ 缺失 — SEC2-01（前端侧）

| 视图 | 位置 | 操作 | 现状 | 后端防护 |
|---|---|---|---|---|
| `Propagation.vue` | L40 | 「构建传播链」`handleRebuild` | 无 `v-if` / 无 `:disabled` | **无**（仅登录态） |

页面门槛为 `propagation:read`，viewer 持有该权限，因此 viewer 可见并可点击该按钮，且后端不拦截 → 构成完整越权链路。**这是前后端双缺失，属本次审计最高优先级问题。**

### ⚠️ LOW — SEC2-07

| 视图 | 位置 | 操作 | 现状 | 建议 |
|---|---|---|---|---|
| `Opinions.vue` | L87 | 批量「删除」 | `:disabled="!canDelete"`（灰态可见） | 与其它页面统一为 `v-if` 隐藏 |

后端 `/api/opinions/batch` 为 `require_admin`，**无实际越权风险**，仅体验不一致。

### ✅ 经复核不构成问题的项

| 视图 | 初判 | 复核结论 |
|---|---|---|
| `Sources.vue`（新建/配置/测试/保存） | 无按钮级门控 | 仅在 `DataManage.vue` 中以 `v-if="isSuperuser"` 渲染，容器级已控；后端 `require_admin` |
| `CollectionLog.vue` | 无门控 | 同上，容器级 `isSuperuser`；且均为只读操作 |
| `BochaLeadReview.vue`（确认/驳回/提升/批量） | 无按钮级门控 | 同上，容器级 `isSuperuser`；后端全部 `require_admin` |
| `WebSearch.vue` / `AnspireSearch.vue` / `AiSearchPanel.vue` | 无按钮级门控 | 路由 `meta.permission='ai:search'` 已兜底；后端 router 级 `require_permission('ai:search')` |
| `Keywords.vue` L80/81 编辑、删除 | 疑似无门控 | 位于 `v-if="!canWriteKeyword"` 的 `v-else` 分支内，实际已控 |
| `Events.vue` / `EventDetail.vue` 添加备注 | 疑似无门控 | 整个 `.note-editor` 区块由 `v-if="canUpdateEvent"` 包裹，已控 |
| 各类弹窗内「保存/提交」按钮 | 无门控 | 弹窗只能由已门控的入口按钮打开，属间接门控；后端亦有校验 |

---

## 四、阶段结论

1. **路由级**：13 个需要门槛的路由已全部设置 `meta.permission`，守卫逻辑完整，覆盖率 **100%**。
2. **操作级**：所有管理员级入口（用户、角色、日志、数据源、采集、AI 线索审核）均已隐藏，覆盖率 **约 96%**。
3. **唯一缺失**：`Propagation.vue` 「构建传播链」按钮（SEC2-01）。
4. **1 项体验问题**：`Opinions.vue` 批量删除用 `disabled` 而非 `v-if`（SEC2-07，LOW）。
5. 本阶段**未做任何修改**。
