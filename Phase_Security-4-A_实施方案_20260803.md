# Phase Security-4-A 实施方案（前端权限门禁重构）

> 生成时间：2026-08-03
> 状态：**设计稿 / 待确认**。本文档仅描述方案，**未修改任何代码、未执行 Git 恢复或文件重写**。
> 背景：基于「系统管理-角色权限」四个现象的根因分析，重构前端页面/菜单门禁，使其与「模块权限」语义一致。

---

## 0. 约束遵守确认（按你的 5 条要求）

| 要求 | 本方案如何满足 |
|---|---|
| ① 不新增权限码 | 仅使用既有前缀 `users/roles/keywords/sources/collectors/login_logs/audit_logs`，不引入任何 `:*_new` 码 |
| ② 不修改数据库 | 全部改动在前端路由/菜单/组件层；后端、迁移、SQL 一律不动 |
| ③ 不改变现有角色权限数据 | 仅放宽门禁**语义**（从单 `:read` 放宽为模块任意权限）；不增删任何 `role_permissions` 绑定 |
| ④ 不处理 opinions 删除权限 | 原问题 1（管理舆情删除）**移出本阶段范围**；`Opinions.vue` 的 `canDelete=isSuperuser` 维持原状 |
| ⑤ permissions:read 不强行映射角色页面 | `permissions:read` 保持仅后端 `GET /permissions` 接口使用，不接到任何前端页面/菜单门禁 |

---

## 1. 只读核对结论（已执行，未改动）

### 1.1 DataManage.vue 的 Git 恢复检查（要求 D）

| 提交 | blob 哈希 | 首字节 | 判定 |
|---|---|---|---|
| **479ee542（HEAD，当前工作树）** | `625aba58…` | `88 7d 1c 7f` | **损坏**（与工作树一致，损坏已提交） |
| 3043b3bb | `5677c085…` | `3c 74 65 6d`(`<tem`) | ✅ 干净 |
| 08cb1609 | `e0b16d5a…` | `3c 74 65 6d` | ✅ 干净 |
| 0feb9a15 | `1e5f1fb4…` | `88 7d 1c 29` | ❌ 损坏 |
| f8f38ad5 | `f5909b1e…` | `3c 74 65 6d` | ✅ 干净 |

**结论：**
- 工作树损坏（`88 7d 1c`）且哈希与 `HEAD` 完全相同 → 损坏版本**已提交进 Git**，不是工作树意外。
- Git 历史**存在干净版本**（3043b3bb / 08cb1609 / f8f38ad5），但均早于当前 `HEAD`；`HEAD` 之后的 `0feb9a15`、`479ee542` 两个提交均为损坏。
- 当前「预期源码」仅能通过 node 虚拟化层以 stdout 形式读到（本次只读提取，未落盘），磁盘与 `HEAD` blob 中均无干净副本。
- 因此恢复路径只有两条，且各有代价：
  - **R1 `git checkout 3043b3bb -- .../DataManage.vue`**：可得干净文件，但可能**丢失** `0feb9a15→479ee542` 之间对该文件的合法编辑。
  - **R2 node 管道提取当前预期源码再写回**：精确恢复当前预期内容，但属于「修复/重写」，违反本次「禁止重新生成」。
- **对方案的影响**：外层 `/data` 路由门禁（§4.1）不依赖 `DataManage.vue`，可独立实施；内层 tab 门禁+默认 tab（§4.2）必须在该文件恢复为可读后才可实施。本设计阶段只给出 §4.2 的编辑清单，**不执行恢复/重写**。

### 1.2 当前 DataManage.vue 的 tab 结构（node 只读提取，未修改）

```
keywords     关键词管理       v-if="tab==='keywords' && canReadKeyword"
sources      数据源管理       v-if="tab==='sources' && canReadSource"
logs         采集日志         v-if="tab==='logs'    && canReadSource"   ← 复用 sources:read
bocha-leads  AI线索审核       v-if="tab==='bocha-leads' && isSuperuser" ← 仅超管
初始 tab 取路由 query.tab（支持 /data?tab=sources 直达），默认 keywords
```

### 1.3 权限码前缀核验

- 目录中确认存在的资源前缀：`users / roles / keywords / sources / collectors / login_logs / audit_logs`。
  - 注：`collectors:read`、`collectors:write` 在目录中为 **reserved（保留未用）**，无默认角色绑定——前缀可用作门禁，只是默认无人持有。
- **无 `bocha:*` 独立读码**：`bocha-leads` 当前为 `isSuperuser` 专属，故维持不变（不新增权限即满足要求①）。

---

## 2. 设计 C：通用 `hasModulePermission(resourcePrefix)`（核心能力）

**文件**：`frontend/src/composables/usePermission.ts`

新增两个方法，并利用既有 `isSuperuser` / `*` 短路：

```ts
// 模块权限：命中 `prefix` 或 `prefix:*` 任一即视为拥有该模块权限
function hasModulePermission(prefix: string): boolean {
  if (isSuperuser.value) return true
  const perms = auth.permissions || []
  return perms.includes('*') || perms.includes(prefix) || perms.some(p => p.startsWith(prefix + ':'))
}

// 多模块：任一命中即放行（用于 /data 需 keywords|sources|collectors 任一）
function hasAnyModulePermission(prefixes: string[]): boolean {
  if (isSuperuser.value) return true
  return prefixes.some(p => hasModulePermission(p))
}
```

扩展 `canAccessRoute` 识别 `meta.module`（string | string[]），优先级置于 `meta.permission` 之前，保持原有 `meta.permission/permissions/permissionAny` 向后兼容：

```ts
function canAccessRoute(meta: Record<string, any> | undefined): boolean {
  if (!meta) return true
  if (meta.module) {
    const mods = Array.isArray(meta.module) ? meta.module : [meta.module]
    return hasAnyModulePermission(mods)
  }
  if (meta.permission) return hasPermission(meta.permission as string)
  if (Array.isArray(meta.permissions)) {
    return meta.permissionAny ? hasAnyPermission(meta.permissions) : hasAllPermissions(meta.permissions)
  }
  return true
}
```

> 设计要点：**不在任何地方硬编码 `users:read` 之类的具体码**，只传资源前缀；新增资源模块时只需在路由 `meta.module` 填前缀，无需改判断逻辑。

---

## 3. 设计 A：用户管理 / 角色管理模块门禁

### 3.1 `router/index.ts`
- `/system/users` 子路由：`meta.permission: 'users:read'` → 改为 `meta.module: 'users'`
- `/system/roles` 子路由：`meta.permission: 'roles:read'` → 改为 `meta.module: 'roles'`
- `/system/login-logs`：`meta.module: 'login_logs'`
- `/system/operation-logs`：`meta.module: 'audit_logs'`
- `/system` 的 `redirect` 函数（现用 `hasPermission('users:read')` 等）改为 `hasModulePermission('users') → 'roles' → 'login_logs' → 'audit_logs'`，无则回退 `/dashboard`。

### 3.2 `frontend/src/views/SystemAdmin.vue`
- `canUsers / canRoles / canLoginLogs / canOperationLogs` 改为 `hasModulePermission('users' | 'roles' | 'login_logs' | 'audit_logs')`；`firstPermitted` 与 `hasAny` 同步。
- 效果：角色只要拥有 `users:write / users:activate / users:delete` 等**任一** `users:*` 权限，即可看到「用户管理」tab 并进入 `/system/users`（即使未勾 `users:read`）。

### 3.3 `AppLayout.vue`
- `hasSystemPerm`（现 `:219-222`，硬编码 4 个 `:read`）改为：
  `hasAnyModulePermission(['users', 'roles', 'login_logs', 'audit_logs'])`

---

## 4. 设计 B：数据管理门禁

### 4.1 外层 `/data` 路由 + 菜单（不依赖 DataManage.vue，可立即实施）
- `router/index.ts` 的 `/data`：`meta.permission: 'keywords:read'` → 改为 `meta.module: ['keywords', 'sources', 'collectors']`（三者任一即可进）。
- 同步删除/改写 `/data` 上方旧注释（"整页门槛取 keywords:read"、"页内数据源/采集日志/AI线索审核仍受 isSuperuser 控制" 等已过时表述）。
- `AppLayout.vue` 的 `hasDataPerm`（现 `:227`，`keywords:read || isSuperuser`）改为：
  `hasAnyModulePermission(['keywords', 'sources', 'collectors'])`。
- 效果：角色仅持有 `sources:read`（无 `keywords:read`）也能进入 `/data` 整页，不再因缺关键词权限而整页消失。

### 4.2 内层 tab 门禁 + 默认 tab（依赖 DataManage.vue 恢复，编辑清单如下）
> 前提：先按 §1.1 的恢复决策把 `DataManage.vue` 恢复为可读（R1 或 R2），再实施本小节。本方案不在此执行恢复。

在 `DataManage.vue` 内：
1. 引入 `usePermission`，定义**单一数据源** `TAB_DEFS`（顺序即默认优先级）：
   ```ts
   const TAB_DEFS = [
     { key: 'keywords',    perm: 'keywords:read' },   // 关键词管理
     { key: 'sources',     perm: 'sources:read' },    // 数据源管理
     { key: 'logs',        perm: 'sources:read' },    // 采集日志（沿用现有复用 sources:read）
     { key: 'bocha-leads', perm: null, superuserOnly: true }, // AI线索审核（无独立读码，维持超管）
   ] as const
   ```
2. `canViewTab(key)`：有 `perm` 则 `hasPermission(perm)`；`superuserOnly` 则 `isSuperuser`。
3. 各 `<*View v-if="tab===key && canViewTab(key)">` 改为统一按 `canViewTab` 判定（删除原 `canReadKeyword/canReadSource/isSuperuser` 散落判断）。
4. **默认 tab 自动选择**：进入时若 `route.query.tab` 缺省或不被 `canViewTab` 允许，则 `router.replace({ query: { tab: 首个 canViewTab 为真的 TAB_DEFS.key } })`。
   - 例：角色仅 `sources:read` → 进 `/data` 自动落到 `sources` tab，且 `keywords`/`logs`(sources 可见)/`bocha-leads`(超管) 中 keywords 不显示、bocha-leads 不显示。
5. 移除对 `isSuperuser` 的硬依赖判断（仅保留 bocha-leads 的 `superuserOnly` 例外）。

---

## 5. 明确不改动项（scope guard）

- ❌ 不新增 / 删除任何权限码（`collectors:*` 仅作为已存在的 reserved 前缀使用）。
- ❌ 不改后端：包括 `users.py`、`opinions.py`、`admin_data_sources.py` 等接口的 `require_permission` 鉴权；`permissions:read` 维持仅后端 `GET /permissions` 使用。
- ❌ 不改任何 `role_permissions` / 角色权限绑定数据。
- ❌ 不处理 `opinions` 删除（`Opinions.vue` 的 `canDelete` 维持 `isSuperuser`）。
- ❌ 不强行把 `permissions:read` 映射到角色页面（问题 2 的原「映射」修复已移出）。
- ❌ 不执行 `DataManage.vue` 的 Git 恢复 / 重写（违反本次「禁止重新生成」；仅给出 §4.2 编辑清单待授权）。

---

## 6. 实施步骤（执行阶段，待你授权后按序进行）

1. `usePermission.ts`：加 `hasModulePermission` / `hasAnyModulePermission` + `canAccessRoute` 支持 `meta.module`。
2. `router/index.ts`：`/system/*` 与 `/data` 的 `meta` 改写 + `/system` redirect + 注释更新。
3. `AppLayout.vue`：`hasSystemPerm` / `hasDataPerm` 改写。
4. `SystemAdmin.vue`：tab 可见性改用 module 判定。
5. **[依赖恢复]** `DataManage.vue`：先恢复为可读（见 §8 决策），再做 §4.2 tab 门禁 + 默认 tab。
6. 构建前端（`node --max-old-space-size=1400 ... vite build`）→ 部署静态 → 重启 uvicorn → 验证。

---

## 7. 验收标准

- 角色仅持有 `users:write`（无 `users:read`）→ 可进入 `/system/users` 且「用户管理」tab 可见。
- 角色仅持有 `roles:assign`（无 `roles:read`）→ 可进入 `/system/roles`。
- 角色仅持有 `sources:read`（无 `keywords:read`）→ 可进入 `/data` 整页，默认选中「数据源管理」tab；「关键词管理」tab 不显示。
- 角色仅持有 `keywords:read` → 进入 `/data` 默认「关键词管理」tab。
- 超管全部可见、行为不变。
- **数据库 `role_permissions` 行数迁移前后零变动**（门禁仅改判断逻辑）。
- `permissions:read` 不影响任何前端页面/菜单可见性（维持原状）。

---

## 8. DataManage.vue 恢复决策（需你拍板，影响 §4.2 是否可执行）

- **R1** `git checkout 3043b3bb -- frontend/src/views/DataManage.vue`：干净，但可能落后 `0feb9a15/479ee542` 的编辑。
- **R2** node 管道提取当前预期源码写回：精确，但属「重写」，需你明确豁免本次「禁止重新生成」。
- **R3** 本阶段仅完成 §2 / §3 / §4.1，§4.2 暂缓至文件恢复授权后再做（推荐：先交付不依赖该文件的改进，降低风险）。

> 请就 R1 / R2 / R3 给出选择；确认后我再进入「实施步骤」逐文件改动并附构建/重启验证。
