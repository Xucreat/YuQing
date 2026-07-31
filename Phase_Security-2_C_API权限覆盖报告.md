# Phase Security-2-C：后端 API 权限覆盖报告

- 生成时间：2026-07-31
- 扫描方式：加载 `app.main:app` 后遍历 `route.dependant` 依赖树（含 router 级 `dependencies=`），**未执行任何业务逻辑**
- 扫描范围：`backend/app/api/` 全部路由

> 本报告由只读审计脚本自动生成，全过程未修改任何代码、数据库记录或权限数据。
> 数据来源：生产库 `opinion_db@127.0.0.1:5432`（仅 SELECT）+ FastAPI 路由内省 + 前端源码静态扫描。

> **扫描方法学说明（避免误判）**：
> 1. `require_permission(code)` 返回的是**闭包**，`code` 存放在 `__closure__[i].cell_contents` 而非参数默认值，需专门提取；
> 2. router 级 `dependencies=[...]` 由 FastAPI 在 `include_router` 时合并进 `route.dependant`，若用 `get_dependant(call=endpoint)` 重新推导会**丢失**这些依赖（`bocha` / `anspire` 曾因此被误判为未保护）。
> 本报告采用遍历真实 `route.dependant` 的方式，结果已与源码逐一核对。

---

## 一、总览

| 指标 | 数量 | 占比 |
|---|---|---|
| 路由总数 | 103 | 100% |
| 写操作路由（POST/PUT/PATCH/DELETE） | 49 | 47.6% |
| 读操作路由（GET） | 54 | 52.4% |

### 按防护类型分布

| 防护类型 | 写路由 | 读路由 | 合计 |
|---|---|---|---|
| `require_admin` | 10 | 2 | 12 |
| `require_permission` | 36 | 24 | 60 |
| `仅登录态` | 2 | 26 | 28 |
| `无（公开）` | 1 | 2 | 3 |
| **合计** | **49** | **54** | **103** |

### 关键结论

- 写操作路由 **49** 个，其中 **46** 个（93.9%）具备 `require_permission` 或 `require_admin`；
- 未达标写路由 **3** 个：`POST /api/login`（公开登录，设计如此）、`POST /api/logout`（登出自身，无风险）、**`POST /api/propagation/rebuild/{event_id}`（⛔ 真实缺口，SEC2-01）**；
- 读操作路由中 **26** 个仅要求登录态，未强制 `:read` 权限（SEC2-02）。

---

## 二、写操作路由清单（49 条）

| 方法 | 路径 | 防护类型 | 权限码 | 判定 |
|---|---|---|---|---|
| POST | `/api/admin/bocha/leads/{lead_id}/confirm` | require_admin | — | ✅ 合规 |
| POST | `/api/admin/bocha/leads/{lead_id}/promote` | require_admin | — | ✅ 合规 |
| POST | `/api/admin/bocha/leads/{lead_id}/reject` | require_admin | — | ✅ 合规 |
| POST | `/api/admin/bocha/search` | require_admin | — | ✅ 合规 |
| POST | `/api/admin/data-sources` | require_admin | — | ✅ 合规 |
| POST | `/api/admin/data-sources/test` | require_admin | — | ✅ 合规 |
| PATCH | `/api/admin/data-sources/{ds_id}` | require_admin | — | ✅ 合规 |
| POST | `/api/alerts/evaluate` | require_permission | `alerts:write` | ✅ 合规 |
| PUT | `/api/alerts/records/{record_id}/handle` | require_permission | `alerts:write` | ✅ 合规 |
| POST | `/api/alerts/rules` | require_permission | `alerts:write` | ✅ 合规 |
| DELETE | `/api/alerts/rules/{rule_id}` | require_permission | `alerts:write` | ✅ 合规 |
| PUT | `/api/alerts/rules/{rule_id}` | require_permission | `alerts:write` | ✅ 合规 |
| POST | `/api/analyze/{opinion_id}` | require_permission | `ai:analyze` | ✅ 合规 |
| POST | `/api/anspire/leads` | require_permission | `ai:search` | ✅ 合规 |
| POST | `/api/anspire/search` | require_permission | `ai:search` | ✅ 合规 |
| POST | `/api/bocha/ai-leads` | require_permission | `ai:search` | ✅ 合规 |
| POST | `/api/bocha/ai-search` | require_permission | `ai:search` | ✅ 合规 |
| POST | `/api/bocha/leads` | require_permission | `ai:search` | ✅ 合规 |
| POST | `/api/bocha/search` | require_permission | `ai:search` | ✅ 合规 |
| POST | `/api/collector/run` | require_admin | — | ✅ 合规 |
| POST | `/api/events/aggregate` | require_permission | `events:write` | ✅ 合规 |
| DELETE | `/api/events/{event_id}` | require_permission | `events:write` | ✅ 合规 |
| POST | `/api/events/{event_id}/actions` | require_permission | `events:write` | ✅ 合规 |
| PATCH | `/api/events/{event_id}/status` | require_permission | `events:write` | ✅ 合规 |
| POST | `/api/keywords` | require_permission | `keywords:write` | ✅ 合规 |
| DELETE | `/api/keywords/{keyword_id}` | require_permission | `keywords:write` | ✅ 合规 |
| PUT | `/api/keywords/{keyword_id}` | require_permission | `keywords:write` | ✅ 合规 |
| POST | `/api/login` | 无（公开） | — | ✅ 公开端点（设计如此） |
| POST | `/api/logout` | 仅登录态 | — | ⛔ **HIGH** |
| POST | `/api/opinions` | require_permission | `opinions:write` | ✅ 合规 |
| DELETE | `/api/opinions/batch` | require_admin | — | ✅ 合规 |
| PATCH | `/api/opinions/batch` | require_permission | `opinions:write` | ✅ 合规 |
| DELETE | `/api/opinions/{opinion_id}` | require_admin | — | ✅ 合规 |
| PATCH | `/api/opinions/{opinion_id}` | require_permission | `opinions:write` | ✅ 合规 |
| POST | `/api/propagation/rebuild/{event_id}` | 仅登录态 | — | ⛔ **HIGH** |
| POST | `/api/reports/export` | require_permission | `reports:export` | ✅ 合规 |
| POST | `/api/reports/generate` | require_permission | `reports:export` | ✅ 合规 |
| POST | `/api/reports/templates` | require_permission | `reports:manage` | ✅ 合规 |
| DELETE | `/api/reports/templates/{template_id}` | require_permission | `reports:manage` | ✅ 合规 |
| PUT | `/api/reports/templates/{template_id}` | require_permission | `reports:manage` | ✅ 合规 |
| POST | `/api/roles` | require_permission | `roles:write` | ✅ 合规 |
| DELETE | `/api/roles/{role_id}` | require_permission | `roles:delete` | ✅ 合规 |
| PUT | `/api/roles/{role_id}` | require_permission | `roles:write` | ✅ 合规 |
| POST | `/api/users` | require_permission | `users:write` | ✅ 合规 |
| DELETE | `/api/users/{user_id}` | require_permission | `users:write` | ✅ 合规 |
| PUT | `/api/users/{user_id}` | require_permission | `users:write` | ✅ 合规 |
| POST | `/api/users/{user_id}/activate` | require_permission | `users:activate` | ✅ 合规 |
| POST | `/api/users/{user_id}/deactivate` | require_permission | `users:activate` | ✅ 合规 |
| POST | `/api/users/{user_id}/reset-password` | require_permission | `users:write` | ✅ 合规 |

---

## 三、读操作路由清单（54 条）

| 路径 | 防护类型 | 权限码 | 判定 |
|---|---|---|---|
| `/_debug_static` | 无（公开） | — | ✅ 公开端点（设计如此） |
| `/api/admin/bocha/leads` | require_admin | — | ✅ 合规 |
| `/api/admin/data-sources` | require_permission | `sources:read` | ✅ 合规 |
| `/api/admin/data-sources/collection-logs` | require_permission | `sources:read` | ✅ 合规 |
| `/api/admin/data-sources/collection-logs/{batch_key}/runs` | require_permission | `sources:read` | ✅ 合规 |
| `/api/admin/data-sources/quality` | require_permission | `sources:read` | ✅ 合规 |
| `/api/admin/data-sources/{ds_id}/runs` | require_permission | `sources:read` | ✅ 合规 |
| `/api/admin/regions` | require_admin | — | ✅ 合规 |
| `/api/alerts/records` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/alerts/rules` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/alerts/unread` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/anspire/leads` | require_permission | `ai:search` | ✅ 合规 |
| `/api/anspire/options` | require_permission | `ai:search` | ✅ 合规 |
| `/api/anspire/sessions` | require_permission | `ai:search` | ✅ 合规 |
| `/api/auth/me` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/bocha/ai-search/options` | require_permission | `ai:search` | ✅ 合规 |
| `/api/bocha/leads` | require_permission | `ai:search` | ✅ 合规 |
| `/api/bocha/sessions` | require_permission | `ai:search` | ✅ 合规 |
| `/api/collector/status` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/alert-stats` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/alerts` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/hot-keywords` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/kpi-trends` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/recent` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/region-children` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/risk-distribution` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/dashboard/stats` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/events` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/events/{event_id}` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/events/{event_id}/opinions` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/events/{event_id}/situation` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/keywords` | require_permission | `keywords:read` | ✅ 合规 |
| `/api/keywords/categories` | require_permission | `keywords:read` | ✅ 合规 |
| `/api/login-logs` | require_permission | `login_logs:read` | ✅ 合规 |
| `/api/operation-logs` | require_permission | `audit_logs:read` | ✅ 合规 |
| `/api/opinions` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/opinions/sources` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/opinions/{opinion_id}` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/opinions/{opinion_id}/original` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/permissions` | require_permission | `permissions:read` | ✅ 合规 |
| `/api/propagation/events` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/propagation/graph/{event_id}` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/reports/modules` | require_permission | `reports:read` | ✅ 合规 |
| `/api/reports/overview` | require_permission | `reports:read` | ✅ 合规 |
| `/api/reports/overview/pdf` | require_permission | `reports:export` | ✅ 合规 |
| `/api/reports/templates` | require_permission | `reports:export` | ✅ 合规 |
| `/api/roles` | require_permission | `roles:read` | ✅ 合规 |
| `/api/roles/{role_id}` | require_permission | `roles:read` | ✅ 合规 |
| `/api/sources/history` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/sources/status` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/tasks/{task_id}` | 仅登录态 | — | ⚠️ MEDIUM |
| `/api/users` | require_permission | `users:read` | ✅ 合规 |
| `/api/users/{user_id}` | require_permission | `users:read` | ✅ 合规 |
| `/health` | 无（公开） | — | ✅ 公开端点（设计如此） |

---

## 四、问题清单

### ⛔ HIGH — SEC2-01

| 方法 | 路径 | 当前防护 | 应有防护 |
|---|---|---|---|
| POST | `/api/propagation/rebuild/{event_id}` | `Depends(get_current_user)` | `require_permission('events:write')` 或 `require_admin` |

该接口执行「删除旧传播节点 + 重新计算传播链」，是明确的写操作，但未做任何权限校验。

### ⚠️ MEDIUM — SEC2-02

26 个 GET 路由仅要求登录态。典型：

| 路径 | 已定义但未使用的权限 |
|---|---|
| `/api/events` | `events:read` |
| `/api/events/{event_id}` | `events:read` |
| `/api/opinions` | `opinions:read` |
| `/api/opinions/{opinion_id}` | `opinions:read` |
| `/api/alerts/rules` | `alerts:read` |
| `/api/alerts/records` | `alerts:read` |
| `/api/dashboard/*` | `dashboard:read` |
| `/api/propagation/graph/{event_id}` | `propagation:read` |
| `/api/collector/status` | `collectors:read` |
| `/api/sources/status` | `sources:read` |

> 这些权限码在 `permissions` 表与前端路由 `meta.permission` 中均已使用，但**服务端不校验**。当前三角色读权限差异小，实际暴露有限；一旦引入“受限读”角色，模型即失效。

---

## 五、阶段结论

1. 共扫描 **103** 条路由，写操作保护率 **46/49 = 93.9%**。
2. 唯一真实写操作缺口：`POST /api/propagation/rebuild/{event_id}`（SEC2-01，HIGH）。
3. `bocha` / `anspire` 经复核由 router 级 `require_permission('ai:search')` 保护，**不是缺口**。
4. `reset-password`、`activate`、`deactivate` 均由 `users:write` / `users:activate` 保护，**不是缺口**。
5. 读操作服务端未强制 `:read`（SEC2-02，MEDIUM）。
6. 本阶段**未做任何修改**。
