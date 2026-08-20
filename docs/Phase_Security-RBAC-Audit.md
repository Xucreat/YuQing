# 舆情监测系统 权限体系全面审计（Phase Security-RBAC-Audit）

> 审计性质：**READ-ONLY SECURITY / RBAC AUDIT**
> 审计范围：`backend/app`（FastAPI 后端）、`frontend/src`（Vue3 前端）、`backend/alembic`（迁移）、生产只读库 `127.0.0.1:5432/opinion_db`
> 审计约束：未修改任何源码 / 数据库 / 迁移 / 权限数据 / 生产配置。所有数据库访问为 `SELECT` 只读。
> 审计时间：2026-08-13

---

# Executive Decision（执行决策，一页纸）

```
当前权限体系状态：        MAJOR_REFACTOR
是否存在权限过细：        YES  （外网/复核域呈典型权限爆炸）
是否存在 Permission Explosion： YES  （83 个 permission，非 admin 角色仅用 8~28 个，外网域 45 个 permission 中 43 个实际仅 superuser 可用）
是否存在权限冲突：        YES  （删除门禁不一致、analyst 缺 keywords:write、foreign 复核 read/complete 不对称、组合授权死分支）
是否存在前后端不一致：    YES  （前端强制 events:read/alerts:read/propagation:read，后端 domestic 读接口仅校验登录；4 个组合 permission 前端可见但库中无人持有）
是否存在高风险安全问题：  YES  （LOW~MEDIUM：任意已登录用户可读全部 domestic 数据；task 结果无归属校验；组合授权死分支导致外网复核权限仅靠 * 兜底）
是否建议重构：            YES

推荐方案：
  RBAC + 业务能力(Capability) 分层模型（方案 C），保留高风险独立 permission，
  修复"外网组合授权死分支"，清理 21 个孤儿 permission，统一命名，
  并将角色配置 UI 从"83 个 checkbox"改为"模块→业务能力→高级权限"三层。
```

## 若继续"新增功能 → 新增 permission → 新增 checkbox"模式，未来最可能出现的 5 个问题

1. **权限目录失控**：当前 83 个 permission 已出现 21 个孤儿（25%），继续线性增长将很快突破 120+，角色配置界面不可用。
2. **外网域彻底锁死**：外网 45 个 permission 中 43 个仅 superuser（admin）可用，任何非 admin 角色都无法使用外网模块——新增外网功能若继续走"细粒度 permission + 组合授权"模式，会重复当前的死分支（组合 permission `foreign:analysis` 从未被任何角色持有，导致批量授权 SQL 实际插入 0 行）。
3. **隐性越权**：domestic 读接口只校验登录不校验 `*:read`，非 admin 用户（含未来外部/低信任账号）可直接通过 API 读取全量舆情/事件/预警/传播/数据源状态。
4. **角色语义漂移**：`analyst` 名义是"分析员"，却缺失 `keywords:write`（孤儿）、且对 `foreign` 模块几乎无权限、对 domestic 事件却拥有删除权——角色职责与权限严重错配，无法用"角色"表达业务职责。
5. **审计不可信**：组合 permission 与叶子 permission 双层 + superuser `*` 兜底，使得"某角色到底能做什么"无法从 `role_permissions` 表直接得出，权限评审与合规审计失去事实来源。

## 下一阶段应先重构什么？为什么？

**先重构"权限数据模型 / 目录"（含清理孤儿、修复组合授权死分支、统一命名），再规范化后端读权限 enforcement，最后重做前端角色配置 UI。**

理由：前端角色配置 UI 与后端 `require_permission` 都以"permission 目录"为单一事实来源。当前目录本身已损坏（21 孤儿 + 4 个无人持有的组合 permission + 外网授权死分支）。若先做 UI，只是把一套坏数据包装得好看；先做数据模型与后端 enforcement，再让 UI 消费干净的 Capability 分组，才能一次性收敛。

---

# 1. Executive Summary

本次审计对舆情监测系统的 RBAC 体系做了完整、只读、架构级盘点。核心结论：

- **后端写/删/管理类接口的 enforcement 基本健全**（高危动作均有 `require_permission` 或 `require_admin` 兜底），但**读接口的 enforcement 缺失**——domestic 读接口仅校验登录。
- **权限模型已出现明显爆炸（Permission Explosion）**：库内 83 个 permission，但系统实际只有 4 个角色（3 个系统角色 + 1 个游离自定义角色 `'111'`）、3 个用户（1 superuser + 1 analyst + 1 viewer）。非 admin 角色仅用到 8~28 个 permission。
- **外网（foreign）域是重灾区**：45 个 foreign permission 中 **43 个仅 superuser 可用**（admin 通过 `is_superuser/role=='admin' → ["*"]` 兜底），普通角色事实上无法使用外网模块。
- **组合权限机制形同虚设**：4 个组合 permission（`foreign:read` / `foreign:data:manage` / `foreign:analysis` / `foreign:alerts:manage`）**没有任何角色持有**，其设计初衷（用 1 个组合 permission 替代多个叶子 permission 来简化角色配置）完全失效。
- **存在一处结构性死分支**：`foreign_batch_review_permissions.py` 的批量授权 SQL 仅向"已持有 `foreign:analysis` 组合 permission 的角色"授予外网 AI 复核权限，而 `foreign:analysis` 无人持有 → 这 9 个外网 AI 复核 permission **未被任何角色授予**，只能靠 superuser `*` 兜底。
- **前后端读权限语义不一致**：前端路由守卫强制 `events:read`/`alerts:read`/`propagation:read`，后端对应接口仅校验登录；这是"前端更严、后端更松"的收敛缺口。
- **删除门禁强度不一致**：`opinions` 删除 = `require_admin`（superuser 专属），`events` 删除 = `events:write`（任何 analyst 可删）。同为"删除"，门禁强度不同。

---

# 2. Current RBAC Architecture

## 2.1 实际结构（基于源码 + 库事实）

```
User (is_superuser:bool, role:str, roles:M2M)
   │
   ├── 主角色 user.role (字符串，默认 "analyst")
   │      └── 解析为 Role（按 Role.name 查找）
   └── 附加角色 user.roles (user_roles 多对多)
          └── 多个 Role
                 │
                 ▼
            Role.permissions (role_permissions 多对多)
                 │
                 ▼
            Permission (code="resource:action", group, resource, action)
                 │
   ┌─────────────┼──────────────────────────────────────────┐
   ▼             ▼                                          ▼
Frontend      API (FastAPI)                              Service
hasPermission  require_permission(perm)  /  require_admin   inline 判定
(route guard,  (dependencies.py)         (admin 专属接口)    (foreign.py 等)
 v-if, menu)
```

## 2.2 关键事实（不是理论，是代码+库事实）

| 机制 | 是否存在 | 证据 |
|---|---|---|
| ADMIN 特权 / bypass | **存在且彻底** | `permissions.py:22-24,116-117,156-157`：`is_superuser_user` 或 `role=="admin"` → `get_user_permissions` 返回 `["*"]`，`require_permission` 直接放行 |
| 角色继承 | **不存在** | `role.py` 无 parent/层级字段；用户权限 = 主角色 ∪ 附加角色权限并集（`permissions.py:118-129`） |
| Permission 独占 | **不存在** | 任一 permission 可被多角色持有 |
| 资源级 / 行级权限 | **不存在** | 全部为 `resource:action` 操作级；`scope_region_codes` 是数据源采集范围，非用户数据范围（`models/data_source.py:46`） |
| 数据范围(data-range)权限 | **不存在（后端）** | 读接口不按用户/角色过滤地域；任意已登录用户读全量数据 |
| 状态级权限 | 否（api 层无） | 仅业务字段状态流转，无独立 permission |
| 前端按钮权限 | **存在** | `usePermission.ts` 的 `hasPermission` 用于 `v-if` 隐藏按钮 |
| 后端 API 权限 | **存在** | `require_permission` / `require_admin` |
| wildcard `*` | **存在** | 仅 superuser 持有（`permissions.py:116-117`） |
| 组合 permission | **存在但失效** | `COMPOSITE_PERMISSIONS`（`permissions.py:34-94`）+ `expand_permissions`；但 4 个组合码均未被任何角色持有（库实测） |

---

# 3. Database Permission Inventory

## 3.1 角色（4 个）

| id | name | code | is_system | is_enabled | 实际持有 permission 数 | 备注 |
|----|------|------|-----------|-----------|----------------------:|------|
| 1 | admin | admin | true | true | 48（显式，但 * 覆盖全部 83） | superuser，实际无需 role_permissions |
| 2 | analyst | analyst | true | true | 28 | 业务分析角色 |
| 3 | viewer | viewer | true | true | 8 | 只读角色 |
| 5 | 111 | 111 | false | true | 1 (opinions:read) | **游离自定义角色**，疑似测试残留 |

> 用户仅 3 名：admin(superuser=1)、analyst、viewer。无任何 `user_roles` 附加角色绑定（库实测 `USER_ROLES` 为空）。

## 3.2 Permission 总数与分布

- **permission 总数：83**（库实测；迁移累计定义 88，被 `sec3b_perm_semantic.py` 删除 5 个：`keywords:delete`/`collectors:read`/`collectors:write`/`dashboard:read`/`reports:write`）。
- **role 总数：4**；**user 总数：3**。
- **每角色 permission 数**：admin 48（显式）/ analyst 28 / viewer 8 / 111 1。
- **每个 permission 被多少 role 使用**：见 §3.4。
- **只被一个 role 使用的 permission**：见 §3.4（绝大多数为 admin-only）。
- **从未使用（orphan，0 role）的 permission：21 个（25.3%）**，见 §3.5。
- **重复语义 / 高度相似 permission**：见 §7、§14。

## 3.3 Role-Permission 矩阵（库实测，节选自 role_permissions）

完整行 85 条，关键分布如下（✓=该角色持有，`A`=admin via `*`/显式，`-`=不持有）：

| Permission | admin | analyst | viewer | 111 |
|---|:--:|:--:|:--:|:--:|
| opinions:read | ✓ | ✓ | ✓ | ✓ |
| opinions:write | ✓ | ✓ | - | - |
| events:read | ✓ | ✓ | ✓ | - |
| events:write | ✓ | ✓ | - | - |
| alerts:read | ✓ | ✓ | ✓ | - |
| alerts:write | ✓ | ✓ | - | - |
| propagation:read | ✓ | ✓ | ✓ | - |
| keywords:read | ✓ | ✓ | - | - |
| keywords:write | **✗(orphan)** | **✗** | - | - |
| sources:read | ✓ | ✓ | - | - |
| sources:write | ✓ | ✓ | - | - |
| reports:read | ✓ | ✓ | - | - |
| reports:export | ✓ | ✓ | - | - |
| reports:manage | ✓ | ✓ | - | - |
| ai:search | ✓ | ✓ | - | - |
| ai:analyze | ✓ | ✓ | - | - |
| permissions:read | **✗(orphan)** | **✗** | - | - |
| users:read/write/activate | **✗(orphan)** | **✗** | - | - |
| roles:read/write/delete | **✗(orphan)** | **✗** | - | - |
| login_logs:read | **✗(orphan)** | **✗** | - | - |
| audit_logs:read | **✗(orphan)** | **✗** | - | - |
| domestic:ai:*（11 项） | ✓ | ✓(全) | read/complete | - |
| foreign:ai:review:read | ✓ | **✗(缺)** | ✓ | - |
| foreign:ai:review:complete | ✓ | ✓ | ✓ | - |
| foreign:ai:review:reject | **✗(orphan)** | **✗** | - | - |
| foreign:ai:batch:read/cancel | **✗(orphan)** | **✗** | - | - |
| foreign:ai:full-confirm | **✗(orphan)** | **✗** | - | - |
| foreign:events:read/confirm/merge/split/status/rebuild/auto-aggregate | ✓ | **✗** | - | - |
| foreign:events:review:read/confirm | **✗(orphan)** | **✗** | - | - |
| foreign:alerts:*（8 项） | ✓ | **✗** | - | - |
| foreign:alerts:review:read/confirm | **✗(orphan)** | **✗** | - | - |
| foreign:risk:*（5 项） | ✓ | **✗** | - | - |
| foreign:keywords:*/sources:* | ✓ | **✗** | - | - |
| foreign:opinions:read | ✓ | **✗** | - | - |

> 说明：admin 列标记 ✓ 表示"逻辑可达"（含 `*` 兜底）；库内 `role_permissions` 对 admin 显式写入 48 行，但 `*` 使这 48 行对 admin 实际无意义。

## 3.4 每个 permission 被多少 role 使用（库实测，按使用数升序节选）

- **0 个 role（孤儿，21 个）**：见 §3.5。
- **1 个 role（admin-only，多数）**：`foreign:*` 绝大多数、`alerts:write`、`events:write`、`opinions:write`、`keywords:read`、`sources:read/write`、`reports:read/export/manage`、`ai:analyze/search`、`permissions:read` 等。
- **2 个 role（admin+analyst）**：`domestic:ai:*` 多数、`events:read`、`alerts:read`、`propagation:read`、`ai:analyze/search`。
- **3 个 role（admin+analyst+viewer）**：`opinions:read`、`domestic:ai:review:read`、`domestic:ai:review:complete`、`foreign:ai:review:read`、`foreign:ai:review:complete`。

> **关键洞察**：除 `opinions:read` 等少数"全员可读"项外，**几乎没有任何 permission 被 2 个以上非 admin 角色共享**。这说明"角色"之间几乎没有"共性业务能力"，角色不是按"业务能力"划分，而是按"能否绕过 admin"划分。

## 3.5 孤儿 permission 清单（0 role 持有，库实测 21 个）

```
audit_logs:read
foreign:ai:batch:cancel
foreign:ai:batch:read
foreign:ai:full-confirm
foreign:ai:review:reject
foreign:alerts:manage
foreign:alerts:review:confirm
foreign:alerts:review:read
foreign:analysis
foreign:data:manage
foreign:events:review:confirm
foreign:events:review:read
foreign:read
keywords:write
login_logs:read
roles:delete
roles:read
roles:write
users:activate
users:read
users:write
```

分类：
- **admin-only 类（设计上合理但应显式声明）**：`users:*`、`roles:*`、`login_logs:read`、`audit_logs:read`——这些端点（`users.py` 全部）确实应仅 superuser，但把它们定义为"orphan permission"会让角色编辑器出现"勾了也不生效"的死选项。
- **结构性损坏类（必须修复）**：`foreign:read`/`foreign:data:manage`/`foreign:analysis`/`foreign:alerts:manage`（4 个组合 permission，0 角色）、`foreign:ai:batch:*`/`foreign:ai:full-confirm`/`foreign:ai:review:reject`/`foreign:alerts:review:*`/`foreign:events:review:*`（组合授权死分支导致未授予）。
- **功能性缺口类（需决策）**：`keywords:write` 孤儿 → analyst 名义是内容管理角色却无法管理关键词（后端 `keywords.py` 要求 `keywords:write`）。

---

# 4. Backend Authorization Audit

## 4.1 鉴权链路（实际）

```
HTTP Request
   │
   ▼
get_current_user (dependencies.py:28-67)
   │  校验 Bearer JWT → 解码 sub → 查库 → is_active 检查 → 401/403
   ▼
端点依赖 (三选一)：
   A. Depends(get_current_user)             → 仅登录门禁（读接口主流）
   B. Depends(require_permission("x:y"))    → 权限门禁（写/管理接口主流）
   C. Depends(require_admin)                → superuser 专属（高危/系统接口）
   │
   ▼ (部分模块在 Service 层内联判定)
foreign.py / domestic_ai_analysis.py / foreign_alerts.py
   → 函数内联 get_user_permissions + is_superuser_user 判定（非依赖注入）
```

## 4.2 `require_permission` 实现（`permissions.py:139-165`）

- 工厂函数，返回内部 `checker` 依赖。
- 判定：`is_superuser_user(user)` → 放行；否则 `get_user_permissions` 并集 + `expand_permissions` → `"*" in perms or permission in perms` → 放行，否则 `403 Permission denied`。
- **无 `require_role` 函数**（全仓 grep 0 命中）：角色维度仅通过"用户→角色→permission"间接体现。

## 4.3 各模块权限映射（库事实 + 源码）

| 模块 | 读接口门禁 | 写/管理门禁 | 高风险门禁 |
|---|---|---|---|
| opinions | 仅登录（`opinions.py:48/295/323`） | `opinions:write`（`:338/438/553`） | **DELETE = `require_admin`**（`:490/531`） |
| events | 仅登录（`:152/217/236/260/535`） | `events:write`（`:132/349/414`） | **DELETE = `events:write`**（`:449`，analyst 可删） |
| alerts | 仅登录（`:48/101`） | `alerts:write`（`:56/67/80/91`） | - |
| keywords | `keywords:read`（`:106/293`） | `keywords:write`（`:134/177/236/267`） | - |
| reports | `reports:read`（`:66/127`） | `reports:export`（`:77/239/284/310`）、`reports:manage`（`:320/331/341`） | - |
| users/roles/perms | `users:read`/`roles:read`/`permissions:read`/`login_logs:read`/`audit_logs:read`（`users.py`） | `users:write`/`users:activate`/`roles:write`/`roles:delete`（均 orphan→仅 superuser） | 最后 superuser 保护（`:347/417`） |
| sources（管理端） | `sources:read`（`:879` 等） | **`require_admin`**（create/update/test/list_regions：`:974/1069/1095/1171/1266`） | - |
| sources（前端态） | **仅登录**（`:18/81`，无 `sources:read`） | - | - |
| dashboard / propagation / tasks / translate | **仅登录**（无 `*:read`） | propagation rebuild=`events:write` | tasks 结果无归属校验 |
| collector | `GET /status` 仅登录 | **`POST /run` = `require_admin`**（`:157`） | - |
| admin_bocha / admin_regions / admin_data_sources(写) | - | **`require_admin`** | - |
| foreign.* | `foreign:*:read` 系列（强制） | `foreign:*:write`/`foreign:alerts:*` 等（强制） | `foreign:ai:full-confirm`/`foreign:alerts:enable` 内联额外判定 |
| domestic_ai_analysis | `domestic:ai:review:read` | `domestic:ai:*` | `domestic:ai:full-confirm` 内联 |

## 4.4 后端 enforcement 总体评价

- **写/删/管理/系统配置类**：✅ 有清晰后端边界；高危动作（用户/角色/权限/数据源写、采集触发、Bocha）均 `require_admin` 或 `require_permission`。未发现有"完全无门禁的高危写操作"。
- **读类（domestic）**：⚠️ 仅校验登录，无 `*:read` 强制（详见 §15 安全边界审计）。属已知设计差异，但构成真实暴露面。
- **Service 层内联判定**：⚠️ `foreign.py`/`domestic_ai_analysis.py`/`foreign_alerts.py` 的复核决策、规则启用、采集走函数内联，不在路由层可见，缺统一失败审计日志（仅 collect 路径写审计）。建议重构为依赖注入以保持可见性与可审计性。

---

# 5. Frontend Authorization Audit

## 5.1 权限基础设施（前端）

- 唯一入口：`frontend/src/composables/usePermission.ts`（`:14-78`）：`hasPermission` / `hasAnyPermission` / `hasAllPermissions` / `hasModulePermission` / `hasAnyModulePermission` / `can` / `canAccessRoute`。
- `isSuperuser` 判定（`:19`）：`auth.isSuperuser === true || auth.role === 'admin'`，**与后端 `is_superuser_user` 完全对齐**。
- 通配符 `*`：permissions 数组含 `'*'` 即全权限（`:23/29/35/43`）。
- **无 `hasRole`、`v-permission`、`v-role`**：所有 UI 门禁通过 `hasPermission(...)` 在 `v-if` / computed 实现。
- 认证 store：`stores/index.ts` `useAuthStore`（:5-41），`permissions` 来自 `GET /api/auth/me` 实时刷新（main.ts:27-39）。
- 路由守卫：`router/index.ts` `beforeEach`（:161-183）——明确注释"前端体验层，非安全边界"（:169）。
- 菜单过滤：`AppLayout.vue`（:215-245）按 `hasAnyModulePermission` 控制 `/data`、`/ai-search`、`/system` 可见性。

## 5.2 前端引用的全部 permission 字符串（去重，节选）

路由 `meta`：``ai:search``、``events:read``、``alerts:read``、``propagation:read``、模块前缀 `keywords/sources/collectors/foreign/users/roles/login_logs/audit_logs`。
叶子：`opinions:write`、`events:write`、`alerts:write`、`keywords:read`、`sources:read`、`foreign:*`（events/alerts/risk/ai/sources/keywords 全套）、`domestic:ai:*`、`reports:read/export/manage`、`roles:write/delete`、`users:activate`、`ai:search/analyze`、`foreign:data:manage`、`foreign:sources:collect[_all]` 等。

## 5.3 前端权限用途分类

- **页面/模块访问**：路由 `meta.permission` + `meta.module` + 菜单 `visible` 过滤。
- **按钮/操作权限**：`v-if` 隐藏删除/编辑/采集/复核/确认/导出/管理按钮，均与后端 `require_permission` 一一对应。
- **纯 UI 装饰性权限（展开/折叠/排序/刷新/筛选）**：**未发现**。前端没有"仅用于控制 UI 装饰"的 permission——所有 `hasPermission` 命中项都对应真实业务操作。**这是好的设计，不应被误判为"过细"。**

## 5.4 前后端一致性结论

- **命名一致性**：✅ 前后端均使用 `resource:action` 冒分格式，无 `event_manage` vs `event:manage` 类分隔符冲突（任务假设的情形在本系统不存在）。
- **前端孤儿 permission（前端有、后端无）**：✅ 无。前端每个 permission 码都能在后端目录/`require_permission`/组合表中找到。
- **后端孤儿 permission（后端有、前端从不引用）**：⚠️ 较多——`permissions:read`、`dashboard:read`(已删)、`reports:write`(已删)、`keywords:delete`(已删)、`ai:manage`、`foreign:events:write`、`foreign:risk:*`、`domestic:*review:confirm/reject/full-confirm`、`domestic:ai:batch:cancel`、`foreign:opinions:read`、`foreign:keywords:write` 等；以及无 `foreign:` 前缀的遗留 `events:*`/`risk:*` 系列（仅后端旧迁移，前端统一用前缀版）。
- **读权限语义缺口（核心不一致）**：❌ 前端路由强制 `events:read`/`alerts:read`/`propagation:read`，后端 domestic 读接口**仅校验登录**。属"前端更严、后端更松"，是安全收敛重点（见 §9、§15）。
- **组合 permission 可见但无效**：`Roles.vue` 标签字典列出 `foreign:read`/`foreign:data:manage`/`foreign:analysis`/`foreign:alerts:manage`，但库中无人持有 → 角色编辑器里勾选这些项**不产生任何效果**（死选项）。

---

# 6. 权限语义分类（按业务含义，非仅按名称）

| 类别 | 包含的 permission（节选） | 后端是否真成边界 |
|---|---|---|
| **1. 页面/模块访问** | `opinions:read`、`events:read`、`alerts:read`、`propagation:read`、`sources:read`、`reports:read`、`dashboard:read`(已删)、`foreign:*:read`、`foreign:read`(组合) | ⚠️ domestic 读仅登录，未强制 |
| **2. 数据管理** | `opinions:write`、`events:write`、`keywords:read/write`、`sources:read/write`、`reports:read/export/manage`、`foreign:sources:*`、`foreign:keywords:*` | ✅ 基本强制 |
| **3. 业务操作** | `events:confirm/merge/split/status/rebuild/auto-aggregate`、`foreign:alerts:acknowledge/resolve/suppress`、`foreign:ai:full-confirm`、`ai:analyze`、`foreign:risk:analyze/batch/ai` | ✅ 强制 |
| **4. 系统管理** | `users:*`、`roles:*`、`permissions:read`、`login_logs:read`、`audit_logs:read`、`admin_data_sources(require_admin)`、`admin_regions(require_admin)`、`collector:run(require_admin)`、`admin_bocha(require_admin)` | ✅ 强制（多 admin-gated） |
| **5. 高风险** | `users:write/activate`、`roles:write/delete`、`foreign:alerts:enable`、`foreign:ai:full-confirm`、`domestic:ai:full-confirm`、`opinions` DELETE(`require_admin`)、所有 `require_admin` 端点 | ✅ 强制 |
| **6. UI-only** | **无**（前端无纯 UI 装饰 permission） | - |

---

# 7. Permission Granularity Audit（粒度审计，核心）

> 判断标准：不是"细=坏"，而是"同一业务能力是否被拆成多个本应合并的 permission" + "组合授权是否失效导致膨胀"。

| Permission | 当前作用 | 实际业务能力 | 粒度 | 是否合理 | 建议 |
|---|---|---|---|---|---|
| `foreign:events:review:read` | 查看外网事件人工复核 | 外网复核-事件-读 | 过细 | NO | 并入 `foreign:review`（域级 read） |
| `foreign:events:review:confirm` | 确认外网事件人工复核 | 外网复核-事件-确认 | 过细 | NO | 并入 `foreign:review:confirm` |
| `foreign:alerts:review:read` | 查看外网预警人工复核 | 外网复核-预警-读 | 过细 | NO | 并入 `foreign:review` |
| `foreign:alerts:review:confirm` | 确认外网预警人工复核 | 外网复核-预警-确认 | 过细 | NO | 并入 `foreign:review:confirm` |
| `foreign:ai:review:read` | 查看外网 AI 复核 | 外网复核-AI-读 | 过细 | NO | 并入 `foreign:review` |
| `foreign:ai:review:complete` | 完成外网 AI 复核 | 外网复核-AI-完成 | 过细 | NO | 并入 `foreign:review:confirm` |
| `foreign:ai:review:reject` | 驳回外网 AI 结果 | 外网复核-驳回 | 中 | 保留(高风险) | 可并入 `foreign:review`，但 reject 建议保留显式 |
| `foreign:ai:batch:read` / `batch:cancel` | 外网 AI 批量任务查看/取消 | 批量任务 | 过细 | NO | 并入 `foreign:ai:batch` |
| `foreign:ai:full-confirm` | 全量确认外网 AI 结果 | 高危"一键全确认" | 合理(高风险) | YES | **保留独立** |
| `domestic:*` 同构 11 项 | 国内 AI 复核全套 | 国内复核 | 过细 | NO | 同 foreign 收敛为 `domestic:review` 等 |
| `foreign:events:confirm/merge/split/status/rebuild/auto-aggregate` | 外网事件操作 | 事件运营 | 合理(业务操作) | YES(部分) | merge/rebuild 高风险可保留独立；confirm/status 可并入 `foreign:events:manage` |
| `foreign:alerts:acknowledge/resolve/suppress` | 告警处置 | 告警运营 | 合理 | YES | 保留，或并入 `foreign:alerts:manage` |
| `opinions:write` / `events:write` / `alerts:write` | 编辑 | 数据编辑 | 合理 | YES | 保留 |
| `reports:read/export/manage` | 报告 | 报告 | 合理 | YES | 保留 |
| `keywords:read/write` | 关键词 | 关键词 | 合理 | YES | 保留（但需修复 analyst 缺失 write） |
| `users:read/write/activate`、`roles:read/write/delete` | 用户/角色管理 | 系统管理 | 合理(高风险) | YES | 保留（显式声明为 admin-only） |

**粒度结论**：膨胀集中在 **"外网/国内 复核工作流"**——`foreign`/`domestic` × `events`/`alerts`/`ai` × `read`/`confirm`/`complete`/`reject` 的笛卡尔积，叠加"组合 permission 本应简化却失效" → 形成约 30+ 个本可收敛为 3~4 个 Capability 的 permission。

---

# 8. Permission Conflict Audit（权限冲突）

## 8.1 包含关系矛盾

- **`events:write` 隐含删除，但无 `events:delete`**；而 **`opinions` 删除走 `require_admin` 而非 `opinions:write`**。同一"删除"语义，事件可被 analyst 删、舆情只能 superuser 删——强度倒挂，且无统一 `*:delete` 概念。
- **`sources:write` 授予 analyst**（`role_permissions` 实测 analyst 持有），但 `admin_data_sources` 的 create/update/test/list_regions/batch_update_schedule **全部 `require_admin`**（`admin_data_sources.py:974/1069/1095/1171/1266`）。即 `sources:write` 对管理端写接口是**死 permission**（端点不识别它），造成"有这个权限却用不上"的假象。

## 8.2 角色逻辑矛盾

- **analyst 缺失 `keywords:write`（孤儿）**：analyst 持有 `keywords:read` 却无 `keywords:write`，而后端 `keywords.py` 要求 `keywords:write` → analyst **无法管理关键词**（按钮因缺权限隐藏 + 后端 403）。与 analyst "内容/分析角色"职责错配。
- **analyst 缺失 `foreign:ai:review:read` 却持有 `foreign:ai:review:complete`**：analyst 能"完成"外网 AI 复核却无"查看"权限 → 打开复核页即 403，complete 操作不可达。明显 bug。
- **analyst 对 domestic 事件拥有删除权（`events:write` 含删除），对外网事件零权限**：业务上"事件"被按国内外切成两套完全独立的权限域，且外网域对非 admin 几乎全封闭。

## 8.3 高危权限矛盾

- `users:write` / `roles:write` / `roles:delete` 均为 **orphan（0 role）** → 没有任何非 admin 角色能管理用户/角色。这本身"安全"，但意味着"系统管理员"这一职责在当前角色体系里**只能由 superuser 充当**，无法委派给一个"非 * 的管理员角色"。这是角色模型的最大结构缺陷：要么全有（`*`），要么全无。

## 8.4 前后端矛盾（逐项）

| 项 | 前端 | 后端 | 结论 |
|---|---|---|---|
| `events:read` / `alerts:read` / `propagation:read` | 路由守卫强制 | 读接口仅登录 | 前端更严；后端暴露面 |
| `foreign:read` / `foreign:data:manage` / `foreign:analysis` / `foreign:alerts:manage` | Roles.vue 可勾选 | 库内 0 role 持有 | 勾选无效（死选项） |
| `sources:read` | DataManage 用 `hasAnyModulePermission(['sources'])` 控制菜单 | `sources.py:/sources/status` /`/sources/history` 仅登录，无 `sources:read` | 管理端要求 `sources:read`，前端态不要求 → 不一致 |
| `dashboard:read` | 前端不门禁（仅 requiresAuth） | 已删（sec3b） | 残留引用 |

---

# 9. 角色合理性审计（Role Rationality）

## 9.1 Role-Permission Matrix（库实测，业务能力视角）

| 业务能力 Domain | admin | analyst | viewer | 111 |
|---|:--:|:--:|:--:|:--:|
| 舆情查看 | ✓* | ✓ | ✓ | ✓ |
| 舆情编辑 | ✓* | ✓ | - | - |
| 舆情删除 | require_admin | - | - | - |
| 事件查看 | ✓* | ✓ | ✓ | - |
| 事件管理(含删) | ✓* | ✓ | - | - |
| 预警查看 | ✓* | ✓ | ✓ | - |
| 预警管理 | ✓* | ✓ | - | - |
| 传播查看 | ✓* | ✓ | ✓ | - |
| 关键词查看 | ✓* | ✓ | - | - |
| 关键词编辑 | ✓* | **✗(orphan)** | - | - |
| 数据源查看 | ✓* | ✓ | - | - |
| 数据源编辑 | ✓* | ✓(端点admin) | - | - |
| 数据源高危操作 | require_admin | - | - | - |
| 报告查看/导出/模板 | ✓* | ✓/✓/✓ | - | - |
| AI 检索/研判 | ✓* | ✓/✓ | - | - |
| 用户管理 | ✓* | - | - | - |
| 角色管理 | ✓* | - | - | - |
| 权限目录 | ✓* | - | - | - |
| 登录/操作日志 | ✓* | - | - | - |
| 国内 AI 复核 | ✓*(全) | ✓(全) | read/complete | - |
| 外网模块 | ✓*(全) | 仅 review:complete | 仅 review:read/complete | - |

（`✓*` = 经 superuser `*` 或显式持有）

## 9.2 角色问题清单

- **角色过少且职责错配**：只有 admin/analyst/viewer + 1 游离角色。没有"系统管理员""采集员""风控处置员"等中间角色；analyst 既管 domestic 又管不了 foreign、既管事件删除又管不了关键词——职责边界混乱。
- **admin 之外的角色实质上都是"受限分析师"**：analyst 与 viewer 的区别仅在于 analyst 多了写/管理权限，二者都几乎无法触达 foreign 与系统管理。角色之间缺乏"业务模块级"共性。
- **admin 是"全有或全无"的唯一中间层缺失**：无法委派"能管用户但不能删角色""能配数据源但不能碰 AI"等细分管理员。
- **存在游离自定义角色 `111`**（is_system=false，1 permission）——疑似测试残留，说明角色创建在 UI 上未受约束，需清理并加约束。

---

# 10. ADMIN / Superuser Audit

## 10.1 事实

- 定义：`is_superuser_user(user) = user.is_superuser OR user.role == "admin"`（`permissions.py:22-24`）。
- 效果：`get_user_permissions` 直接返回 `["*"]`（`permissions.py:116-117`）；`require_permission` 内 `is_superuser_user` 直接放行（`permissions.py:156-157`）；`require_admin` 同判（`permissions.py:132-136`）。
- `users.py` 创建/更新用户时强制 `is_superuser = (role == "admin")`（`users.py:228/297`），即 `admin` 角色**隐式等价于 superuser**，不可降权（除非同时改 `is_superuser` 与 `role`）。
- "最后 superuser 保护"：`_superuser_count` / `_active_superuser_count`（`users.py:51-60,347,417`）防止误删/停用最后一个 superuser。

## 10.2 问题

1. **admin 的 `role_permissions`（48 行）形同虚设**：`*` 已覆盖全部 83 permission，这 48 行对 admin 不产生任何增量效果，却让"admin 到底有哪些权限"在 `role_permissions` 表中看不出全貌。
2. **"admin" 是硬编码超管**：任何 `role=='admin'` 的用户（即使 `is_superuser=False`）也拥有 `["*"]` → 不可通过撤销 role_permissions 来缩小 admin 权限（代码层无效）。
3. **"系统管理员"无法委派**：由于只有 `*` 能解锁 users/roles/permissions 管理（这些 permission 都是 orphan），不存在"非 * 的管理员角色"。

## 10.3 建议

**保留 superuser 概念，但显式化并引入分层管理员角色**：
- 保留一个 `is_superuser` 应急通道（用于初始部署/灾难恢复），其边界**必须文档化**。
- 新增显式 `system_admin` 角色，持有 `users:*`/`roles:*`/`permissions:read`/`sources:*`/`collectors:*` 等**具体 permission**（而非 `*`），使"系统管理"成为可从 `role_permissions` 审计的实体。
- 在代码注释与运维文档中明确："`role=='admin'` 即 superuser，`*` 兜底；日常运维请用 `system_admin` 角色而非 admin"。

---

# 11. Permission Naming Audit

## 11.1 命名风格（库实测，5 类混用）

1. **双段 `resource:action`**：`opinions:write`、`events:write`、`alerts:write`、`keywords:read`、`reports:read|export|manage`、`users:read|write|activate`、`roles:read|write|delete`、`permissions:read`、`login_logs:read`、`audit_logs:read`、`ai:search`、`ai:analyze`、`sources:read`。
2. **三段 `foreign:` 前缀**：`foreign:events:read`、`foreign:alerts:rules:write`、`foreign:risk:analyze` 等。
3. **三段 `domestic:` 前缀**：`domestic:ai:analyze`、`domestic:events:review:confirm` 等。
4. **组合/分组码（非叶子）**：`foreign:read`、`foreign:data:manage`、`foreign:analysis`、`foreign:alerts:manage`、`ai:analyze`（亦作组合）。
5. **通配 `*`**：superuser。

## 11.2 具体不一致点

- **分隔符混用**：action 段内既用 `:` 又用 `-`。`foreign:events:auto-aggregate`、`foreign:ai:full-confirm`、`foreign:alerts:ai-admit`、`domestic:ai:full-confirm` 用连字符；而 `foreign:events:candidates:read`、`foreign:alerts:rules:write` 用冒号。同一资源下 `read/confirm` 用 `:`、`full-confirm`/`auto-aggregate`/`ai-admit` 用 `-`，维护易错。
- **前缀体系内部重复**：规范码为 `foreign:events:*`；后端旧迁移仍保留无前缀 `events:*`（`events:candidates:read`/`events:confirm`/`events:merge`/`events:split`/`events:status`/`events:rebuild`）与无前缀 `risk:*`。前端统一用前缀版，故前后端交互一致，但**目录存在"同一能力两套码"混淆**。
- **语义迁移遗留**：`reports:write`（rbac10001 定义）已被 `reports:export`/`reports:manage` 取代（p26/p29），`reports:write` 成为已删除孤儿，但 `p26_report_records.py` 注释仍称"保持兼容"——注释与实现已矛盾。
- **`dashboard:read` / `keywords:delete` / `collectors:*`**：被 `sec3b` 删除，但 `p2_rbac.py` 的 analyst/viewer JSONB 仍含 `dashboard:read`/`collectors:*`，`rbac10001` 展开时静默丢弃（reserved 设计），属历史债。

## 11.3 统一规范建议

```
格式：  <domain>:<resource>:<action>    或  <domain>:<action>
action 词表（受控）：read | write | delete | export | manage | confirm | reject | enable | collect | review
规则：
  - action 段一律用冒号分隔，禁止连字符（full-confirm → confirm_all；auto-aggregate → aggregate）
  - 国内外用 domain 前缀 domestic/foreign 统一
  - 删除保留 delete；批量用 batch 前缀（foreign:ai:batch:read）
  - 高风险动作显式命名（confirm_all / enable / delete）
```

---

# 12. Security Boundary Audit（后端安全边界）

> 验证方法：静态分析 + 库实测 permission 授予情况。**未对生产数据做任何写入**。

| 高风险能力 | 前端检查 | 后端 API 检查 | Service 检查 | 越过前端直调 API 是否仍被拦 |
|---|---|---|---|---|
| 用户管理（增删改/启停/改密） | 按钮 `users:activate` 等 | `require_permission(users:*)`（`users.py`） | - | ✅ 拦（orphan→仅 superuser） |
| 角色管理（增删改） | `roles:write/delete` | `require_permission(roles:*)` | 系统角色保护 | ✅ 拦（仅 superuser） |
| 权限目录查看 | - | `permissions:read` | - | ✅ 拦（仅 superuser） |
| 数据源写/测试/调度 | 按钮 | **`require_admin`** | - | ✅ 拦 |
| 采集触发 | 顶栏按钮(isSuperuser) | `require_admin`（`collector.py:157`） | - | ✅ 拦 |
| 关键词管理 | `keywords:write` | `require_permission(keywords:write)` | - | ✅ 拦（analyst 缺 write→403） |
| 删除舆情 | 按钮 | **`require_admin`** | - | ✅ 拦（仅 superuser） |
| 删除事件 | 按钮 | `events:write`（analyst 可） | - | ⚠️ analyst 可删 |
| 导出报告 | 按钮 | `reports:export` | - | ✅ 拦 |
| **读取舆情/事件/预警/传播/大屏/数据源状态** | **路由强制 `*:read`** | **仅登录（无 `*:read`）** | - | ❌ **不拦——任意已登录用户可读全量** |
| **后台任务结果 `GET /tasks/{id}`** | - | 仅登录 | 无归属校验 | ❌ 任意用户可读他人任务结果 |

**结论**：写/管理/系统类边界扎实；**读类边界缺失**是主要安全欠债（MEDIUM）。API 直调场景下，低权限用户（如 viewer）可读取全部 domestic 业务数据。

---

# 13. Permission Explosion Analysis（爆炸量化）

| 指标 | 数值 |
|---|---:|
| permission 总数 | 83 |
| role 总数 | 4（3 系统 + 1 游离） |
| user 总数 | 3 |
| 平均每非 admin 角色 permission 数 | analyst 28 / viewer 8 |
| permission / 业务能力 比 | ≈ 4 : 1（约 20 个业务能力 vs 83 permission） |
| 仅使用一次的 permission 占比 | 多数 foreign:* 仅 admin 持有（占 foreign 域 95%） |
| 高度相似 permission 占比 | 复核工作流笛卡尔积 ≈ 30+ 个可收敛为 ≤5 个 Capability |
| UI-only permission 占比 | 0% |
| 后端真实安全边界 permission 占比 | 写/管/系统 ≈ 40 个有效；其余为 orphan/admin-only 装饰 |
| orphan permission 占比 | **21 / 83 = 25.3%** |
| 组合 permission 实际利用率 | **0 / 4 = 0%** |
| 外网域 permission 中"仅 superuser 可用"占比 | **43 / 45 ≈ 96%** |

**结论：Permission Explosion = YES。** 根因不是"按钮级权限"本身（前端无纯 UI 权限），而是：
1. 外网/国内复核工作流的笛卡尔积式拆分；
2. 组合 permission 机制失效（死分支 + 无人持有）使简化手段归零；
3. admin 的 `*` 兜底让所有细粒度 permission 对 admin 无意义，却仍被创建/维护。

---

# 14. Current Architecture Problems（当前架构问题汇总）

1. **外网域 96% 仅 superuser 可用**——功能交付了，但除 admin 外无人能用（业务价值未释放）。
2. **组合授权死分支**——`foreign_batch_review_permissions.py` 依赖 `foreign:analysis`，而它从未被授予 → 9 个外网 AI 复核 permission 未被任何角色持有。
3. **21 个孤儿 permission（25%）**——含 4 个组合 permission（完全无效）、`keywords:write`（功能性缺口）、admin-only 类（死选项）。
4. **读接口无 `*:read` 强制**——domestic 全量数据对任意已登录用户暴露。
5. **删除门禁倒挂**——舆情删除需 superuser，事件删除 analyst 即可。
6. **analyst 职责错配**——缺 `keywords:write`、缺 `foreign:ai:review:read`、对 domestic 事件却有删除权。
7. **admin 不可降权 + 无中间管理员角色**——系统管理只能由 `*` 充当。
8. **命名不一致**——`-` vs `:`、无前缀遗留码、注释与实现矛盾。
9. **Service 层内联鉴权不可见**——复核/启用/采集判定不在路由层，缺统一审计。
10. **游离角色 `111`**——角色创建未受约束，存在测试残留。
11. **`tasks` 结果无归属校验**——信息隔离缺口。
12. **权限配置 UI 直接暴露 83 个 checkbox**——管理员无法理解业务含义，易漏配（如 analyst 漏 `keywords:write`）。

---

# 15. Candidate RBAC Models（候选模型）

## 方案 A：粗粒度 RBAC（resource × {read, write, manage}）

```
opinions:read / opinions:write / opinions:manage
events:read / events:write / events:manage
...
```
- 优点：极简，permission 数降到 ~30。
- 缺点：丢失"确认/合并/驳回"等需独立审计的高风险动作；`manage` 过大。

## 方案 B：RBAC + 高风险 Action（推荐基础）

在 A 基础上保留少数高风险独立 permission：
```
<domain>:<resource>:read | write | delete
<domain>:<resource>:confirm_all   (高风险"一键全确认")
<domain>:<resource>:enable       (启用规则)
users:manage / roles:manage / permissions:read  (系统管理)
```
- 优点：安全清晰、数量适中（~40）、高风险动作可审计。
- 缺点：外网/国内复核仍需逐域展开。

## 方案 C：RBAC + 业务能力(Capability) 分层（★ 推荐）

```
User → Role → Capability(业务能力分组) → Permission → API/Action
```
- Capability 示例（~12 个，给管理员看的"业务能力"）：
  `舆情查看` `舆情编辑` `舆情删除` `事件运营` `预警处置` `传播溯源` `报告` `关键词` `数据源` `AI研判` `外网运营` `系统管理`。
- 每个 Capability 后端映射到一组 permission（含必要的 `confirm_all`/`enable`/`delete` 高风险项）。
- 组合 permission 机制**修复并真正使用**（Capability 即组合 permission 的落地）。
- 角色配置 UI 只展示 Capability + "高级权限"开关，不直接暴露 83 个叶子 permission。
- 优点：管理员可理解、易配置、数量可控、后端边界清晰、兼容现有 `COMPOSITE_PERMISSIONS` 展开逻辑。
- 缺点：需一次性迁移（旧叶子 permission → Capability 映射）。

---

# 16. Recommended RBAC Architecture（推荐架构）

```
                    ┌──────────────┐
                    │    User      │
                    │(is_superuser)│
                    └──────┬───────┘
                           │  (主角色 user.role + 附加角色 user.roles)
                           ▼
                        Role (扁平, 可多角色并集)
                           │
                    ┌──────▼───────────────────────┐
                    │  Capability (业务能力分组)     │   ← 新增抽象层（即修复后的组合 permission）
                    │  舆情查看/编辑/删除 事件运营    │
                    │  预警处置 传播 报告 关键词      │
                    │  数据源 AI研判 外网运营 系统管理 │
                    └──────┬───────────────────────┘
                           │  (Capability 1:N Permission，复用 expand_permissions)
                           ▼
                      Permission (叶子, resource:action)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           Frontend      API          Service
           Capability    require_     (统一依赖注入,
           门禁 +按钮    permission   禁内联)
```

**是否引入下列机制（基于"简单、稳定、易配置、后端安全边界清晰"原则）：**

| 机制 | 是否引入 | 理由 |
|---|---|---|
| Capability / permission group | **是** | 解决配置 UI 爆炸，复用现有 `COMPOSITE_PERMISSIONS` |
| permission inheritance（组合展开） | **是（修复后）** | 已有 `expand_permissions`，只需让组合码真正被角色持有 |
| role template（角色模板） | **是** | 预置 超级管理员/系统管理员/分析员/采集员/只读，允许少量微调 |
| scope / data-range | **否（本期）** | 当前业务无按地域划分数据可见性的强需求；如需再说 |
| resource / 行级权限 | **否（本期）** | 超出当前规模，避免过度设计 |
| wildcard `*` | **保留仅作 superuser 应急** | 不用于普通角色 |

---

# 17. Recommended Role Model（推荐角色模型）

| 角色 | 说明 | 主要 Capability |
|---|---|---|
| 超级管理员 (superuser, `*` 应急) | 初始/灾难恢复，文档化边界 | 全部 |
| 系统管理员 (system_admin) | 日常运维，非 `*` | 用户管理/角色管理/权限目录/数据源/采集/日志 |
| 分析员 (analyst) | 业务分析+处置 | 舆情查看编辑/事件运营/预警处置/传播/报告/关键词/AI研判/外网运营(读+复核) |
| 采集员 (operator) | 数据源与采集 | 数据源/关键词/采集触发/采集日志 |
| 只读 (viewer) | 只看 | 全部 `:read` Capability |

> 关键改进：**系统管理员不再依赖 `*`**，而是持有具体 permission，可被 `role_permissions` 审计；分析员能真正使用外网模块（修复 foreign 授权死分支后）。

---

# 18. Recommended Permission Model（推荐权限模型）

- 保留现有叶子 permission（`resource:action`），但**统一命名**（见 §11.3）。
- 将 4 个失效组合 permission 替换为 **12 个 Capability**，并真正授予相应角色。
- 高风险独立 permission 保留：`*:delete`、`*:confirm_all`、`*:enable`、`users:manage`、`roles:manage`、`permissions:read`。
- 收敛外网/国内复核笛卡尔积：将 `foreign:events:review:read/confirm`、`foreign:alerts:review:read/confirm`、`foreign:ai:review:read/complete/reject`、`foreign:ai:batch:read/cancel` 等收敛为 `foreign:review`(read+confirm+complete+reject) + `foreign:ai:batch`。
- 清理 21 个孤儿；`keywords:write` 显式授予 analyst/operator。

---

# 19. Recommended Permission Configuration UI（推荐配置 UI）

**不要**直接暴露 83 个 checkbox。改为三层：

```
角色：[ 系统管理员 ▼ ]    （可从"角色模板"新建/克隆）
│
├─ 舆情
│   ☐ 查看舆情   ☐ 编辑舆情   ☐ 删除舆情(高风险)
├─ 事件
│   ☐ 查看事件   ☐ 事件运营(确认/合并/状态)   ☐ 删除事件(高风险)
├─ 预警
│   ☐ 查看预警   ☐ 预警处置(确认/解决/抑制)   ☐ 启用规则(高风险)
├─ 传播 / 报告 / 关键词 / 数据源 / AI研判
│   ...
├─ 外网运营
│   ☐ 外网查看   ☐ 外网复核(确认/驳回)   ☐ 全量确认(高风险)   ☐ 采集
└─ 系统管理
    ☐ 用户管理   ☐ 角色管理   ☐ 权限目录   ☐ 日志
        │
        └─ [高级权限]（默认折叠）：confirm_all / enable / delete 等逐条开关
```

- 顶层用 **Capability（业务能力）** 勾选；底层叶子 permission 由 Capability 自动映射（管理员一般不必看）。
- 提供 **角色模板**（超级管理员/系统管理员/分析员/采集员/只读）一键套用 + 少量微调。
- 每个 Capability 显示"中文业务说明 + 影响的接口数"，避免盲人勾选。
- `foreign:read` 等组合项从"死选项"变为"有效 Capability"。

---

# 20. Old → New Permission Mapping Proposal（旧→新映射，节选）

| 当前 Permission | 建议归属(Capability) | 新 Permission | 是否保留 |
|---|---|---|---|
| `foreign:events:review:read` | 外网运营 | `foreign:review` | 合并 |
| `foreign:events:review:confirm` | 外网运营 | `foreign:review`(confirm) | 合并 |
| `foreign:alerts:review:read/confirm` | 外网运营 | `foreign:review` | 合并 |
| `foreign:ai:review:read/complete/reject` | 外网运营 | `foreign:review` | 合并 |
| `foreign:ai:batch:read/cancel` | 外网运营 | `foreign:ai:batch` | 合并 |
| `foreign:ai:full-confirm` | 外网运营(高风险) | `foreign:confirm_all` | **保留独立** |
| `foreign:analysis`(组合, orphan) | 外网运营 | `foreign:review`+`foreign:ai:batch`+... | 转为 Capability 落地 |
| `foreign:read`(组合, orphan) | 外网运营 | `foreign:review`(read) | 转为 Capability |
| `domestic:ai:review:*` / `domestic:events:review:*` / `domestic:alerts:review:*` | 国内 AI 复核 | `domestic:review` | 合并 |
| `opinions:write` / `events:write` / `alerts:write` | 对应域 | 保留 | 保留 |
| `keywords:write`(orphan) | 关键词 | `keywords:write` | **保留并授予 analyst/operator** |
| `users:read/write/activate`(orphan) | 系统管理 | `users:manage` | 合并+保留 |
| `roles:read/write/delete`(orphan) | 系统管理 | `roles:manage` | 合并+保留 |
| `reports:read/export/manage` | 报告 | 保留 | 保留 |
| `audit_logs:read` / `login_logs:read`(orphan) | 系统管理 | `logs:read` | 合并+保留(显式) |

> 映射后预计：叶子 permission 由 83 → ~45，Capability 12 个；角色配置 UI 只暴露 12 个 Capability + 少量高风险开关。

---

# 21. Migration Risks（迁移风险）

1. **组合授权死分支修复需重跑授权**：修复后需将 Capability 真正写入 `role_permissions`，否则外网仍不可用。
2. **orphan permission 清理风险**：直接 DELETE 权限行会影响 `role_permissions` 外键（已设 CASCADE），但不会丢业务数据；需先在 staging 验证。
3. **`*` 兜底依赖**：若引入 `system_admin` 非 `*` 角色，必须确认所有"系统管理"端点已正确 `require_permission(具体码)` 而非仅 `require_admin`，否则新管理员角色会被卡死。
4. **前端 `/me` 缓存**：权限变更依赖 `main.ts` 刷新；迁移后需提示用户重新登录或前端主动刷新。
5. **命名统一**：旧无前缀 `events:*`/`risk:*` 若删除，需确认无代码/前端残留引用（前端已统一用前缀版，风险低）。
6. **回归测试**：`test_rbac.py` / `test_rbac_hardening.py` 需随模型更新，避免误报。

---

# 22. Recommended Implementation Phases（建议实施阶段）

> 本阶段**不实施**，仅给出顺序。下一阶段确认后再动代码。

- **Phase 1（数据模型/目录治理，先做）**：清理 21 孤儿（含修复 foreign 组合授权死分支，将 `foreign:*` 复核权限真正授予 analyst/viewer/system_admin）；统一命名；修复 `analyst` 缺失 `keywords:write` 与 `foreign:ai:review:read` 不对称。不动 enforcement 逻辑。
- **Phase 2（后端 enforcement 规范化）**：domestic 读接口补 `require_permission("*:read")` 或明确"读=已登录"策略文档；`tasks` 结果加归属校验；Service 层内联判定改为依赖注入 + 统一审计；引入 `system_admin` 非 `*` 角色并验证所有系统管理端点对其开放。
- **Phase 3（Capability 抽象 + 配置 UI）**：落地 12 个 Capability（复用 `COMPOSITE_PERMISSIONS`/`expand_permissions`）；角色配置 UI 改为"模块→业务能力→高级权限"三层 + 角色模板；清理游离角色 `111`。
- **Phase 4（回归与文档）**：更新 `test_rbac*`，编写《RBAC 运维手册》明确 superuser 边界、角色职责、命名规范。

---

# 23. Final Decision / Recommendation（最终结论）

## 1. 当前权限体系是否已经过细？
**PARTIALLY（YES 于外网/复核域，NO 于按钮级）**。前端无纯 UI 装饰 permission（这点不坏）；但外网/国内复核工作流的笛卡尔积拆分 + 组合授权失效，造成约 30+ 个可收敛的过细 permission。

## 2. 是否存在 Permission Explosion？
**YES。** 83 个 permission、25% 孤儿、组合 permission 利用率 0%、外网域 96% 仅 superuser 可用。

## 3. 是否存在角色设计问题？
**YES。** 角色过少且职责错配；admin 不可降权、无中间管理员角色；analyst 缺 `keywords:write` 与 `foreign:ai:review:read`；存在游离角色 `111`。

## 4. 是否存在权限冲突？
**YES。** 删除门禁倒挂（舆情 require_admin vs 事件 events:write）；`sources:write` 授予 analyst 但端点 `require_admin` 使其失效；analyst 可 complete 外网复核却无 read；组合授权死分支导致 9 个 foreign 复核 permission 未被任何角色持有。

## 5. 是否存在前后端权限不一致？
**YES。** 前端强制 `events:read`/`alerts:read`/`propagation:read`，后端 domestic 读仅登录；4 个组合 permission 前端可勾选但库内 0 持有（死选项）；`sources:read` 管理端要求、前端态不要求。

## 6. 是否存在安全漏洞？
**按等级：**
- **MEDIUM**：任意已登录用户可读全部 domestic 业务数据（读接口无 `*:read` 强制）；`tasks` 结果无归属校验。
- **LOW**：组合授权死分支使外网复核权限仅靠 `*` 兜底（admin 降级即失效）；admin `role_permissions` 形同虚设导致权限不可审计；命名不一致增加误配风险；游离角色 `111` 暴露角色创建无约束。
- **无 CRITICAL/HIGH**：未发现"完全无门禁的高危写操作"；写/删/系统管理均有后端边界。

## 推荐新架构
**方案 C：RBAC + 业务能力(Capability) 分层**，保留高风险独立 permission，修复并真正启用组合/Capability 机制，角色配置 UI 改为三层 + 角色模板。

## 下一步顺序
**先治理权限数据模型/目录（Phase 1）→ 再规范化后端读 enforcement（Phase 2）→ 最后重做 Capability 抽象与配置 UI（Phase 3）**。原因：UI 与后端都以 permission 目录为单一事实来源，目录先干净，UI 重构才有意义。

---

## 证据索引（文件:行号）

- 后端鉴权核心：`backend/app/core/permissions.py:22-24,34-94,110-129,132-165`
- 认证依赖：`backend/app/core/dependencies.py:28-67`
- 角色/权限/用户模型：`backend/app/models/role.py:11-36`、`permission.py:30-90`、`user.py:12-42`
- admin 删除门禁：`backend/app/api/opinions.py:490,531`；事件删除 `events.py:449`（`events:write`）
- 系统管理全 admin-gated：`backend/app/api/users.py:183-604`、`admin_data_sources.py:974-1266`、`collector.py:157`、`admin_bocha.py`、`admin_regions.py`
- 组合授权死分支：`backend/alembic/versions/foreign_batch_review_permissions.py:41-54`（依赖 `foreign:analysis`，该码 0 角色持有）
- 组合展开表：`backend/app/core/permissions.py:34-94`；4 组合码无人持有（库实测）
- 前端唯一入口：`frontend/src/composables/usePermission.ts:14-78`；路由守卫 `router/index.ts:161-183`；菜单 `AppLayout.vue:215-245`；角色标签字典 `Roles.vue:187-209`
- 库实测数据：本审计 `audit-evidence/_rbac_readonly_audit.py` 输出（roles=4, permissions=83, role_permissions=85, orphan=21, combined-assigned=0）

> 本报告全部基于只读检查与生产只读库 `SELECT`，未对任何源码、数据库、迁移、权限数据或生产配置做修改。
