# Phase Security-2-E：权限链路一致性报告

- 生成时间：2026-07-31
- 分析链路：**角色 → 权限 → 后端 API → 前端入口**

> 本报告由只读审计脚本自动生成，全过程未修改任何代码、数据库记录或权限数据。
> 数据来源：生产库 `opinion_db@127.0.0.1:5432`（仅 SELECT）+ FastAPI 路由内省 + 前端源码静态扫描。

---

## 一、四类不一致检查总览

| # | 不一致类型 | 命中数 | 最高等级 |
|---|---|---|---|
| 1 | 孤儿权限（定义了但无角色持有） | 13 | MEDIUM |
| 2a | 前端强制、后端未强制（读权限） | 5 | MEDIUM |
| 2b | 前后端均未引用（真·死权限） | 6 | LOW |
| 3 | 前端有入口但后端无保护 | 1 | **HIGH** |
| 4 | 后端有保护但前端未隐藏入口 | 0 | — |

---

## 二、类型 1：孤儿权限（13 项）

定义于 `permissions` 表，但 `role_permissions` 中无任何角色持有，仅超管短路可用。

| 权限码 | 后端是否使用 | 前端是否使用 | 结论 |
|---|---|---|---|
| `audit_logs:read` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `collectors:read` | ✗ 未使用 | ✗ 未使用 | 仅超管可用，职责无法下放 |
| `collectors:write` | ✗ 未使用 | ✗ 未使用 | 仅超管可用，职责无法下放 |
| `keywords:delete` | ✗ 未使用 | ✗ 未使用 | 仅超管可用，职责无法下放 |
| `login_logs:read` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `permissions:read` | ✅ 使用 | ✗ 未使用 | 仅超管可用，职责无法下放 |
| `roles:delete` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `roles:read` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `roles:write` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `sources:write` | ✗ 未使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `users:activate` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `users:read` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |
| `users:write` | ✅ 使用 | ✅ 使用 | 仅超管可用，职责无法下放 |

**影响**：用户管理、角色管理、审计日志、采集管理、数据源写入这五类职责，目前**只能由超管执行**，无法授予任何非超管角色（SEC2-04）。

---

## 三、类型 2：后端未引用的权限码（11 项，需细分）

### 3.1 类型 2a：前端强制、后端未强制（5 项，MEDIUM）

这些权限在前端路由 `meta.permission` 中生效，但后端对应 GET 接口只校验登录态 —— 绕过前端即失效。

| 权限码 | 名称 | 授予角色 | 前端使用位置 | 后端对应接口 |
|---|---|---|---|---|
| `alerts:read` | 查看预警 | analyst、viewer | 路由 `/alerts` | `GET /api/alerts/rules`、`/api/alerts/records`（仅登录态） |
| `dashboard:read` | 查看驾驶舱 | analyst、viewer | （仅角色授权，无路由门槛） | `GET /api/dashboard/*`（仅登录态） |
| `events:read` | 查看事件 | analyst、viewer | 路由 `/events`、`/event/:id` | `GET /api/events`、`/api/events/{id}`（仅登录态） |
| `opinions:read` | 查看舆情 | analyst、viewer | （仅角色授权，无路由门槛） | `GET /api/opinions`、`/api/opinions/{id}`（仅登录态） |
| `propagation:read` | 查看传播 | analyst、viewer | 路由 `/propagation` | `GET /api/propagation/graph/{id}`（仅登录态） |

> 归属风险 **SEC2-02**。

### 3.2 类型 2b：前后端均未引用（6 项，LOW）

| 权限码 | 名称 | 授予角色 | 实际由谁承担 | 归属 |
|---|---|---|---|---|
| `ai:manage` | AI配置管理 | admin | 无（规划预留） | SEC2-08 |
| `collectors:read` | 查看采集 | （无） | `sources:read` + `require_admin` | SEC2-08 |
| `collectors:write` | 管理采集 | （无） | `require_admin`（`POST /api/collector/run`） | SEC2-08 |
| `keywords:delete` | 删除关键词 | （无） | `keywords:write` | SEC2-08 |
| `reports:write` | 导出报告 | analyst | `reports:export`（语义完全重复） | SEC2-06 |
| `sources:write` | 管理数据源 | （无） | `require_admin`（数据源增改） | SEC2-08 |

> 这 6 项在角色管理界面可被勾选，但勾选后**不产生任何实际效果**，易误导管理员。

---

## 四、类型 3：前端有入口但后端无保护（⛔ HIGH）

| 前端入口 | 前端门槛 | 调用接口 | 后端防护 | 判定 |
|---|---|---|---|---|
| `Propagation.vue` L40「构建传播链」 | 页面 `propagation:read`（viewer 持有）；按钮**无门控** | `POST /api/propagation/rebuild/{event_id}` | 仅 `get_current_user` | ⛔ **SEC2-01** |

完整越权链路：
```
viewer → /propagation（propagation:read 放行）→ 点击「构建传播链」
      → POST /api/propagation/rebuild/{id} → 无权限校验 → 重算 propagation_nodes（写入成功）
```

---

## 五、类型 4：后端有保护但前端未隐藏入口

**命中 0 项。** 逐项复核结论：

| 后端受保护接口 | 前端入口 | 前端是否隐藏 |
|---|---|---|
| `require_admin` 数据源写入 | `Sources.vue` | ✅ 容器 `v-if="isSuperuser"` |
| `require_admin` AI 线索审核 | `BochaLeadReview.vue` | ✅ 容器 `v-if="isSuperuser"` |
| `require_admin` 手动采集 | `AppLayout.vue` L95 | ✅ `v-if="isSuperuser"` |
| `require_admin` 舆情批量删除 | `Opinions.vue` L87 | ⚠️ `disabled` 而非隐藏（SEC2-07，LOW） |
| `users:write` / `users:activate` | `Users.vue` | ✅ `v-if="canWrite/canActivate"` |
| `roles:write` / `roles:delete` | `Roles.vue` | ✅ `v-if="canWrite/canDelete"` |
| `alerts:write` | `Alerts.vue` | ✅ `v-if="canWriteAlert"` |
| `events:write` | `Events.vue` / `EventDetail.vue` | ✅ `v-if="canUpdateEvent"` |
| `keywords:write` | `Keywords.vue` | ✅ `v-if/v-else` 分支 |
| `ai:search` | AI 检索三页 | ✅ 路由 `meta.permission` |
| `ai:analyze` | 舆情详情/弹窗 | ✅ `v-if="canAnalyze"` |
| `audit_logs:read` / `login_logs:read` | `SystemAdmin.vue` / `Users.vue` | ✅ 页签级门控 |

---

## 六、链路一致性矩阵（按权限码）

| 权限码 | 已授予角色 | 后端使用 | 前端使用 | 一致性 |
|---|---|---|---|---|
| `ai:analyze` | admin、analyst | ✅ | ✅ | ✅ 一致 |
| `ai:manage` | admin | ✗ | ✗ | ⚠️ 死权限 |
| `ai:search` | admin、analyst | ✅ | ✅ | ✅ 一致 |
| `alerts:read` | analyst、viewer | ✗ | ✅ | ⚠️ 仅前端强制 |
| `alerts:write` | analyst | ✅ | ✅ | ✅ 一致 |
| `audit_logs:read` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |
| `collectors:read` | **（无）** | ✗ | ✗ | ⚠️ 死权限 |
| `collectors:write` | **（无）** | ✗ | ✗ | ⚠️ 死权限 |
| `dashboard:read` | analyst、viewer | ✗ | ✗ | ⚠️ 仅前端强制 |
| `events:read` | analyst、viewer | ✗ | ✅ | ⚠️ 仅前端强制 |
| `events:write` | analyst | ✅ | ✅ | ✅ 一致 |
| `keywords:delete` | **（无）** | ✗ | ✗ | ⚠️ 死权限 |
| `keywords:read` | analyst | ✅ | ✅ | ✅ 一致 |
| `keywords:write` | analyst | ✅ | ✅ | ✅ 一致 |
| `login_logs:read` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |
| `opinions:read` | analyst、viewer | ✗ | ✗ | ⚠️ 仅前端强制 |
| `opinions:write` | analyst | ✅ | ✅ | ✅ 一致 |
| `permissions:read` | **（无）** | ✅ | ✗ | ⚠️ 孤儿权限 |
| `propagation:read` | analyst、viewer | ✗ | ✅ | ⚠️ 仅前端强制 |
| `reports:export` | analyst | ✅ | ✗ | ✅ 一致 |
| `reports:manage` | admin | ✅ | ✗ | ✅ 一致 |
| `reports:read` | analyst | ✅ | ✗ | ✅ 一致 |
| `reports:write` | analyst | ✗ | ✗ | ⚠️ 死权限 |
| `roles:delete` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |
| `roles:read` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |
| `roles:write` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |
| `sources:read` | analyst | ✅ | ✗ | ✅ 一致 |
| `sources:write` | **（无）** | ✗ | ✅ | ⚠️ 死权限 |
| `users:activate` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |
| `users:read` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |
| `users:write` | **（无）** | ✅ | ✅ | ⚠️ 孤儿权限 |

> `admin` 列未计入「已授予角色」，因其权限来自超管短路而非数据授权（SEC2-03）。

---

## 七、阶段结论

1. **1 项 HIGH**：前端有入口、后端无保护 —— 传播链重建（SEC2-01）。
2. **0 项**「后端有保护但前端未隐藏」，管理员入口隐藏工作完整。
3. **13 项孤儿权限**导致管理职责无法下放（SEC2-04）。
4. **5 项读权限仅前端强制**：`alerts:read`、`dashboard:read`、`events:read`、`opinions:read`、`propagation:read`（SEC2-02）。
5. **6 项真·死权限**：`ai:manage`、`collectors:read`、`collectors:write`、`keywords:delete`、`sources:write`（SEC2-08）与 `reports:write`（SEC2-06）。
6. 本阶段**未做任何修改**。
