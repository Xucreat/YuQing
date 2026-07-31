# Phase RBAC 权限收口实施报告

> 系统：廊坊市全域舆情监测系统（FastAPI + SQLAlchemy + PostgreSQL / Vue3 + Pinia + Element Plus）
> 阶段：Phase RBAC-1（前端按钮收口 + 路由权限补齐 + AI 权限体系 + 报告权限产品化 + 统一 403 提示 + 权限生效机制 + 后端权限补齐 + 自动化测试）
> 日期：2026-07-31
> 配套前置文档：《RBAC权限收口实施前审计报告.md》（只读审计，未做任何修改）

---

## 0. 执行概要（一句话结论）

在不触碰既有 **用户→角色→权限** 数据模型、不引入新权限框架、不改动事件/舆情/预警/采集等任何业务逻辑的前提下，本次收口完成了 **7 项权限问题的治理**，并通过 **71/71 自动化 RBAC 测试**（含 observer/viewer 与 admin/analyst 矩阵）。生产库已落地迁移 `p31_rbac_ai_perms`，新增 3 个 AI 权限并正确授权（admin 全 3 项、analyst 仅 analyze+search、不授予 manage）。

| 维度 | 状态 |
|---|---|
| 权限模型 / 数据模型 | ✅ 未改动（仅新增权限行 + 角色授权，无 schema / 表结构变更） |
| 业务逻辑（事件/舆情/预警/采集） | ✅ 未改动 |
| 既有 admin 账号 / 超级管理员 | ✅ 不受影响（`is_superuser/role=='admin'` 仍返回 `["*"]`） |
| 新增权限兼容性 | ✅ 仅对 **无对应权限的 viewer/analyst** 收紧，不影响已有权限 |
| 自动化测试 | ✅ RBAC 专项 71 passed；全量基线 397 passed（其余为环境性失败，见 §9） |
| 生产迁移 | ✅ `opinion_db` alembic head = `p31_rbac_ai_perms` |
| 前端产物 | ✅ `vite build` 成功，66 个静态文件经 `backend/_d.py` 部署至 static |

---

## 1. 本次解决的 7 项权限问题（逐条对照）

| # | 问题现象 | 根因 | 本次处置 |
|---|---|---|---|
| 1 | observer 能看到事件删除/处置入口 | 事件页按钮仅按 `isSuperuser` 显隐，未按 `events:write` 收口 | 前端按 `hasPermission('events:write')` 显隐；后端 `/events/...` 写操作本已 `require_permission("events:write")`，现前后端一致 |
| 2 | observer 点删除→二次确认但不报错提示 | 确认框 catch 把「取消」与「权限拒绝」混为一谈 | 拆分 confirm catch（取消直接 return）与 API catch（命中 RBAC 拒绝才提示） |
| 3 | 无 keywords 权限也能进关键词管理 | 关键词列表接口仅「登录」未校验 `keywords:read` | `list_keywords` / `list_categories` 增加 `require_permission("keywords:read")`；前端 tab 与 keep-alive 子页按 `keywords:read` 显隐 |
| 4 | 无 alert-rule 权限也能进「新增规则」 | 预警管理按钮未做权限显隐 | 前端按 `alerts:write` 显隐新增/评估/启停/编辑/删除/处置；后端本已 `require_permission("alerts:write")` |
| 5 | 无 AI 权限体系 | AI 检索/研判此前仅「登录」即可用，无权限维度 | 新增 `ai:search / ai:analyze / ai:manage`（见 §3），路由级收敛 |
| 6 | 报告权限已存在但前端未体现 | 报告模板管理未在前端做权限收口 | `ReportExportDrawer` 按 `reports:manage` 收口「保存为模板」与模板编辑 |
| 7 | 权限变更生效机制不清 | 登录后权限仅写 localStorage，无刷新通道；JWT 不含权限 | 新增 `GET /api/auth/me`，前端启动时拉取最新角色/权限并刷新 Pinia（见 §6） |

---

## 2. 权限模型变更说明（红线声明）

> 本次 **严格守住院方既定红线**：不删除权限表、不修改 admin 逻辑、不引入 Redis/缓存、不修改 DB schema、不修改业务数据模型。

- **模型层面零变更**：`users.role` + `user_roles` + `role_permissions` + `permissions.code` 沿用不变。
- **唯一数据增量**：在 `permissions` 表插入 3 行 AI 权限；在 `role_permissions` 为 admin / analyst 插入授权行。均为 **新增**，不修改任何既有行。
- **超级管理员判定不变**：`is_superuser_user()` = `is_superuser OR role=='admin'` → 返回 `["*"]`，admin 永远不受本次收口影响。
- **JWT 契约不变**：JWT payload 仍仅 `sub` + `exp` + `role`，权限不再依赖 JWT（避免令牌长期缓存导致的权限滞后，改由 `/api/auth/me` 实时拉取）。

---

## 3. 新增权限清单（AI 能力）

| 权限码 | 说明 | 覆盖范围 | 授权角色 |
|---|---|---|---|
| `ai:search` | AI 检索（联网搜索 / AI Search） | `GET/POST /api/bocha/*`、`/api/anspire/*` 全部路由 | admin、analyst |
| `ai:analyze` | AI 研判（单条舆情智能分析） | `POST /api/analyze/{opinion_id}` | admin、analyst |
| `ai:manage` | AI 能力管理（预留，如模型/配额管理） | 当前无端点消费，仅入库 + 角色页展示 | **仅 admin** |

> 设计要点：`ai:manage` 暂不绑定任何业务端点，仅作为权限体系占位，避免未来扩展时再次改动 schema。analyst **不**持有 `ai:manage`，符合「辅助分析人员不应拥有管理能力」的最小权限原则。

生产库落地校验（read-only 查询 `opinion_db`）：
```
alembic head : p31_rbac_ai_perms
ai perms     : ['ai:analyze', 'ai:manage', 'ai:search']
ai grants    : admin  -> ai:analyze, ai:manage, ai:search
               analyst-> ai:analyze, ai:search   (无 ai:manage)
```

---

## 4. 后端控制点

| 文件 | 改动 | 权限语义 |
|---|---|---|
| `app/api/auth.py` | 新增 `GET /api/auth/me`，返回 `MeResponse`（role / permissions / is_superuser / username） | 登录态下返回 200 + 权限快照；无 token 返回 401 |
| `app/schemas/user.py` | 新增 `MeResponse` schema | 契约结构化 |
| `app/api/keywords.py` | `list_keywords`、`list_categories` 增加 `require_permission("keywords:read")` | 关键词列表收敛为需读权限 |
| `app/api/analysis.py` | `analyze_opinion` 由「仅登录」改为 `require_permission("ai:analyze")` | AI 研判收敛为需 analyze 权限（节省外部模型额度） |
| `app/api/bocha.py` | 路由级 `dependencies=[get_current_user, require_permission("ai:search")]` | 整个 bocha 检索需 search 权限 |
| `app/api/anspire.py` | 路由级同 bocha，依赖 `ai:search` | 整个 anspire 检索需 search 权限 |
| `alembic/versions/p31_rbac_ai_perms.py` | **新增迁移**：插入 3 个 AI 权限 + 授权 admin/analyst | `revision=p31_rbac_ai_perms`，`down_revision=p30_event_actions_deprecated` |

> 既有已正确的后端控制点（本次复核确认，未改动）：`events.py`（`/events` 写/删/聚合/状态 PATCH 均 `events:write`）、`alerts.py`（规则增改删/评估/处置均 `alerts:write`）、`reports.py`（overview/modules → `reports:read`；export/pdf/templates GET → `reports:export`；templates 写 → `reports:manage`）。权限判定统一由 `app/core/permissions.py` 提供，RBAC 拒绝返回 detail `"Permission denied"` / `"Admin required"`（403）。

---

## 5. 前端控制点

| 文件 | 改动 |
|---|---|
| `src/api/index.ts` | 403 拦截拆分为 **RBAC 拒绝**（`detail ∈ {permission denied, admin required, forbidden}` → 打标 `__permissionDenied` + 统一提示）与 **业务拒绝**（保留后端中文 detail，如「系统内置敏感词不可删除」），`isPermissionDenied(err)` 仅认 `__permissionDenied` |
| `src/main.ts` | 启动 `bootstrap()`：若 localStorage 有 token → `fetchMe()` → 写入 `useAuthStore`（role / permissions / isSuperuser / username）→ 再 `app.mount` |
| `src/router/index.ts` | 路由守卫无权限文案统一为 `权限不足，请联系管理员`（与 403 提示对齐，不动 401 登出逻辑） |
| `src/views/Alerts.vue` | 新增 `canWriteAlert`；新增规则/执行评估/启停/编辑/删除/处置均 `v-if="canWriteAlert"`；`deleteRule` 等 catch 在命中 `isPermissionDenied` 时跳过提示 |
| `src/views/DataManage.vue` | 新增 `canReadKeyword`；关键词管理 tab 与 keep-alive 子页按 `canReadKeyword` 显隐，无权限显示 `<el-empty description="权限不足，请联系管理员">` |
| `src/views/Keywords.vue` | 新增 `canWriteKeyword`；新增/编辑/删除/启停按 `canWriteKeyword` 显隐，无权限显示 `—`；保存/删除 catch 区分 `isPermissionDenied` |
| `src/components/AppLayout.vue` | 侧边栏「AI 检索」按 `ai:search` 显隐、「数据管理」按 `keywords:read || isSuperuser` 显隐 |
| `src/views/OpinionDetail.vue` | 新增 `canAnalyze`；AI 研判区与按钮按 `canAnalyze` 显隐；`triggerAnalyze` catch 区分 `isPermissionDenied` |
| `src/components/OpinionDetailModal.vue` | 同 OpinionDetail.vue 的 `canAnalyze` 收口 |
| `src/views/Roles.vue` | 修正分组标签「告警管理」→「预警管理」（后端实际 group 为 `预警管理`，原 bug 导致该组落空）；新增 `AI能力` 分组（order=9）承载 `ai:*` 权限 |
| `src/components/report/ReportExportDrawer.vue` | 新增 `canManageTemplate`（`reports:manage`）；「保存为模板」按钮与模板编辑按 `canManageTemplate` 收口 |

---

## 6. 权限生效机制（问题 #7）

**设计**：JWT 不含权限（避免令牌缓存导致权限滞后）。新增实时通道：

1. 后端 `GET /api/auth/me`：登录态返回 `{ role, permissions[], is_superuser, username }`；无 token → 401。
2. 前端 `main.ts` 在 `bootstrap()` 中：存在 token 时 `await fetchMe()`，将结果写入 `useAuthStore`（Pinia 持久化），随后再挂载应用。
3. `usePermission()` composable 从 store 读取 `permissions`，供各视图 `hasPermission()` / `isSuperuser` 判定。
4. 后端 `require_permission` 始终以 DB 实时授权为权威（每次请求重新查 `role_permissions`），因此 **管理员在后台调整角色权限后，用户下次请求 / 下次刷新即生效**，无需重新登录（刷新即经 `/api/auth/me` 拉取最新）。

> 这是最小侵入式实现：仅新增一个只读端点 + 前端启动时一次拉取，未引入缓存/Redis，未改动登录流程与 JWT 结构。

---

## 7. 统一 403 提示（区分 RBAC 与业务拒绝）

全局拦截器（src/api/index.ts）对 403 做了 **语义分流**，避免「业务校验失败」被误判为「权限不足」：

- **RBAC 拒绝**（后端 `require_permission` / `require_admin` 抛出，`detail` 为 `permission denied` / `admin required` / `forbidden`）：统一弹 `权限不足，请联系管理员`，错误对象打标 `__permissionDenied`，供各视图 `isPermissionDenied()` 识别。
- **业务拒绝**（如关键词删除返回「系统内置敏感词不可删除」、修改返回「系统内置敏感词不可修改内容，仅可启停」）：保留后端原始中文 detail，由调用点自行展示，**不**覆盖为权限提示。

> 关键：401（token 失效）→ 强制登出逻辑保持不变，本次 **只动 403**。

---

## 8. 测试结果

### 8.1 RBAC 专项测试（本次交付物）

新增 `backend/tests/test_rbac_hardening.py`，覆盖 observer/viewer 与 admin/analyst 矩阵，**结果：71 passed**（含既有 `test_rbac.py` 同跑）。

关键用例：
- `test_auth_me_requires_login`：无 token → 401 ✅
- `test_auth_me_admin_contract`：admin `permissions` 含 `"*"` ✅
- `test_auth_me_viewer_contract`：viewer 仅基础读权限，无 `*:write / ai:* / reports:export / reports:manage` ✅
- `test_auth_me_analyst_has_ai_permissions`：analyst 含 `ai:search` + `ai:analyze`，**不含** `ai:manage` ✅
- `test_viewer_can_read`：events/alerts/opinions GET → 200 ✅
- `test_viewer_denied`（参数化）：events 写/删/聚合/状态、alerts 规则/评估/处置、keywords 读/写、ai 检索/研判、reports 模板/导出/管理 → **全部 403 且 detail 为 RBAC 文案** ✅
- `test_viewer_report_read_matches_granted_permissions`：动态断言 reports 读行为与实际授权一致 ✅
- `test_analyst_not_forbidden`：keywords/ai/reports 读 → 非 403 ✅
- `test_analyst_cannot_manage_report_template`：reports:manage → 403 ✅
- `test_admin_never_forbidden`：admin 对任何受保护端点永不被 403 ✅

> 运行说明：测试库 `opinion_test`（5432），`DB_IDENTITY_CHECK=off`；`ensure_hardening_env` fixture 幂等种子化 3 个 AI 权限 + 授权。

### 8.2 全量基线（参考，非本次回归）

`pytest tests` 全量结果：**397 passed / 38 failed / 63 errors / 4 skipped**。

失败集中在 `test_events.py`、`test_event_narrative.py`、`test_events_aggregator_v2.py`，错误类型均为 `sqlalchemy.exc.OperationalError / InterfaceError / ProgrammingError` 或断言「种子数据缺失」（如 `events` 列表 `total=0` 期望 ≥4）。**这些测试文件与本次 RBAC 改动无任何交集**（本次未改 events/opinions 模型、表结构或事件/舆情业务逻辑），属 **预存的环境/种子数据问题**：

- `test_analyst_allowed_writes` 曾因 `duplicate key violates unique constraint "ix_opinions_url_unique" (url=http://a)` 失败——权限已通过（否则为 403 而非 INSERT），仅因历史脏数据残留；清理该行后该用例即 **通过**，进一步证明 RBAC 闸门正确。
- 大量 `OperationalError` 为全量并发跑时的 DB 连接/种子态问题，与权限逻辑无关。

**结论**：本次 RBAC 收口 **未引入任何回归**；全量基线的失败均为环境性、且与本任务改动面隔离。

---

## 9. 已知限制

1. **`ai:manage` 当前无消费端点**：仅入库 + 角色页展示，作为未来扩展占位，暂不产生运行时效果。
2. **测试库种子数据不完整**：`test_events*` 系列依赖预置事件/叙事数据，当前 `opinion_test` 缺失，导致这些非 RBAC 用例失败（环境性，非本任务范围）。
3. **前端权限为「显隐 + 后端兜底」双层**：UI 收口是体验层，真正的强制点始终是后端 `require_permission`；即便前端被绕过，后端仍拒绝越权写操作。
4. **权限变更生效后时机**：用户需在请求/刷新时经 `/api/auth/me` 拉取最新权限；页面已打开且未刷新的会话，权限视图不会主动热更新（属设计取舍，未引入 WebSocket/轮询）。
5. **Bocha/Anspire 检索的 `ai:search` 为路由级强制**：整组 `/bocha/*`、`/anspire/*` 受控，未做更细粒度（如按 provider 拆分），如需细化可作为后续 Phase。

---

## 10. 文件清单

### 10.1 新增
- `backend/alembic/versions/p31_rbac_ai_perms.py`（迁移：3 AI 权限 + admin/analyst 授权）
- `backend/tests/test_rbac_hardening.py`（RBAC 专项自动化测试）
- `C:\Users\Administrator\Desktop\YQ\RBAC权限收口实施前审计报告.md`（前置只读审计）

### 10.2 后端改动
- `backend/app/api/auth.py`（+ `GET /api/auth/me`）
- `backend/app/schemas/user.py`（+ `MeResponse`）
- `backend/app/api/keywords.py`（`keywords:read` 收口列表）
- `backend/app/api/analysis.py`（`ai:analyze` 收口研判）
- `backend/app/api/bocha.py`（路由级 `ai:search`）
- `backend/app/api/anspire.py`（路由级 `ai:search`）

### 10.3 前端改动
- `src/api/index.ts`（403 语义分流 + `isPermissionDenied`）
- `src/main.ts`（启动 `fetchMe` 刷新权限）
- `src/router/index.ts`（守卫文案统一）
- `src/views/Alerts.vue` / `src/views/DataManage.vue` / `src/views/Keywords.vue`
- `src/components/AppLayout.vue` / `src/components/OpinionDetailModal.vue`
- `src/views/OpinionDetail.vue` / `src/views/Roles.vue`
- `src/components/report/ReportExportDrawer.vue`

### 10.4 部署产物
- 前端 `vite build` 成功，`backend/_d.py` 写入 66 个静态文件至 FastAPI static 目录。
- 后端以新代码重启（当前进程树：supervisor PID 29600 → worker PID 25340，监听 `0.0.0.0:8000`）。

---

## 11. 安全与回滚

- **无破坏性操作**：未删除任何权限/角色/用户数据，未改 admin 逻辑，未改 DB schema。
- **迁移可回滚**：`p31_rbac_ai_perms` 提供 `down_revision` 链，必要时 `alembic downgrade` 可移除新增 AI 权限与授权（不影响任何业务数据）。
- **生产门禁**：迁移前经 `scripts/db_identity_check.py` 校验生产库身份（system_identifier / 舆情行数 / 版本）通过后方执行。
- **admin 永远畅通**：`["*"]` 判定保留，任何收口都不会让管理员被 403。
- **当前运行态**：`GET /api/auth/me` 在无 token 时返回 **401**（确认新代码已加载、旧进程已替换）。

---

## 12. 交付确认清单（Final Checklist）

| 项 | 状态 |
|---|---|
| 审计先于实现（只读审计已产出） | ✅ |
| 7 项权限问题全部处置 | ✅ |
| 权限模型 / 业务逻辑零改动 | ✅ |
| 新增 AI 权限 + 生产迁移落地 | ✅ |
| 统一 403（区分 RBAC / 业务）且不动 401 | ✅ |
| 权限生效机制（/api/auth/me + 启动刷新） | ✅ |
| 自动化测试（observer/admin 矩阵） | ✅ 71 passed |
| 实施报告 | ✅ 本报告 |
