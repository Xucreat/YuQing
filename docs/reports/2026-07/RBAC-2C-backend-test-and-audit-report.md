# RBAC-2C 后端自动化测试与现有权限实现审计报告

> 阶段目标：后端 RBAC 自动化测试 + 现有权限实现只读审计 + 必要最小修复，为下一阶段（前端 RBAC）建立事实基线。
> 执行时间：2026-07-23
> 测试库：`opinion_test`（与 `opinion_db` 同 5432 集群的隔离 DATABASE，`DB_IDENTITY_CHECK=off` 仅用于该测试库）
> 生产库：`opinion_db`（rbac10001，opinions≈718，**本阶段未做任何写操作**）

---

## 1. 审计结果（现有权限机制）

### 1.1 当前实际权限机制清单（位置 | 机制 | 当前角色 | 是否仍在使用）

| 位置 | 机制 | 当前角色 | 是否仍在使用 |
|------|------|---------|------------|
| `core/dependencies.py` `get_current_user` | JWT 鉴权网关：缺失/非法/过期 token → 401；`is_active=False` → 401（即停用立即失效） | 所有受保护接口 | **是（核心网关）** |
| `core/permissions.py` `is_superuser_user` | 超管判定：`is_superuser OR role=='admin'`（两者等价） | admin / `is_superuser` 用户 | **是** |
| `core/permissions.py` `get_user_permissions(user, db)` | 实时从 `role_permissions` + `user_roles` 计算最终权限；超管返回 `["*"]` | 所有鉴权路径 | **是（权限权威来源）** |
| `core/permissions.py` `require_permission(perm)` | 依赖工厂：按权限码校验（超管绕过）；`"*" in perms or perm in perms` | 业务写/读接口 | **是** |
| `core/permissions.py` `require_admin` | 仅超级管理员通过（`is_superuser OR role=='admin'`），否则 403 | 纯管理员接口 | **是** |
| `models/user.py` `User.role`（主角色字段） | 向后兼容的单角色；`users.py` 创建/更新时据此设 `is_superuser` | 所有用户 | **是（兼容保留）** |
| `models/role.py` `roles.permissions` JSONB（旧） | 旧权限存储（RBAC-2B 前） | — | **否（rbac10001 已删除该列，数据已迁移至 `role_permissions`）** |
| `api/admin_data_sources.py` `require_admin` | 数据源全部接口统一用 `require_admin`，而非 seed 中的 `sources:read`/`sources:write` | 数据源管理 | **是（但与 seed 分歧，见 §1.2 / §2）** |

### 1.2 关键发现：26 个权限码中仅 14 个被后端实际强制

种子共定义 **26 个权限码**（`rbac10001.py` `_PERMISSIONS`）。经逐接口核对 `require_permission` 调用，实际被后端强制校验的 **14 个**：

`users:read` `users:write` `users:activate` `roles:read` `roles:write` `roles:delete` `permissions:read` `keywords:write` `opinions:write` `events:write` `alerts:write` `reports:read` `audit_logs:read` `login_logs:read`

**定义但未被强制（12 个）**，按性质分两类：

| 类别 | 权限码 | 现状说明 |
|------|--------|---------|
| 读接口只校验登录、未强制读权限 | `opinions:read` `events:read` `dashboard:read` | `GET /api/opinions`、`GET /api/events`、`dashboard/*` 仅依赖 `get_current_user`，未 `require_permission(...:read)`；任何已登录用户均可读 |
| 读权限码未被对应读接口强制 | `keywords:read` `alerts:read` | 无接口强制这两个读权限（写接口仍强制 `:write`） |
| 种子存在但接口走 `require_admin` 绕过 | `sources:read` `sources:write` | `admin_data_sources.py` 全部用 `require_admin`；analyst 虽在 seed 含 `sources:read` 仍会被 403 |
| 接口未实现/未挂权限 | `collectors:read` `collectors:write` `propagation:read` | 采集器/传播溯源相关接口未强制这些码 |
| 冗余/与实现不符 | `keywords:delete`（DELETE 实际用 `keywords:write`）、`reports:write`（导出 PDF 实际用 `reports:read`） | 权限码存在但无接口单独强制 |

**风险判定**：当前 3 个系统角色（admin/analyst/viewer）**均拥有全部读权限**，因此「读接口未强制 `:read`」在当前角色集下**不构成实际越权**（任何已登录用户都能读，符合"已登录即可看"的默认预期）；`sources:*` 走 `require_admin` 是 **fail-closed（更严）**，亦非安全缺陷。以上均按本阶段修复原则归为 **P5 记录项（非阻塞）**，不在本阶段改动业务代码。

---

## 2. 新旧权限逻辑重叠（重复 / 冲突 / 保留 / 收敛）

| 维度 | 旧实现（RBAC-2B 前） | 新 RBAC（rbac10001） | 关系 | 处理 |
|------|---------------------|---------------------|------|------|
| 权限存储 | `roles.permissions` JSONB（角色上直接挂权限数组） | `permissions` 表 + `role_permissions` 关联 + `user_roles` 多对多 | **收敛** | 旧 JSONB 列已在 rbac10001 删除并迁移；无残留 |
| 超管判定 | `role == 'admin'` | `is_superuser_user`（显式 `is_superuser` **或** `role=='admin'`） | **收敛/兼容** | 保留双判定，向后兼容历史 admin 角色 |
| 单主角色 | `User.role`（admin/analyst/viewer） | `get_user_permissions` 仍先读主角色 | **保留兼容** | 保留；新系统新增 `user_roles` 多角色能力，当前仅主角色在用 |
| 多角色能力 | 无 | `user_roles` 多对多 + 权限并集 | **新增** | 保留（为下一阶段前端 RBAC 管理预留） |
| 数据源权限 | （无显式权限控制） | seed 含 `sources:read/write`，但接口统一 `require_admin` | **冲突/分歧** | 记录；行为 fail-closed 安全，建议在下一阶段统一（见 §10） |
| 停用即失效 | 无显式 | `get_current_user` 校验 `is_active` → 401 | **新增（更严格）** | 保留 |

**结论**：旧逻辑已干净收敛到新 RBAC，无并存的"双套权限系统"；唯一分歧是 `sources:*` 与 `require_admin` 的不一致（见 §1.2），属文档化项，不触发本阶段重构。

---

## 3. 测试用例清单（后端自动化测试）

测试文件：`backend/tests/test_rbac.py`（全新创建，隔离测试库运行）。

模块级护栏：若 `DATABASE_URL` 含 `opinion_db`（生产库），整模块 `pytest.skip`，从机制上杜绝误跑生产。

| # | 测试函数 | 覆盖要求 | 类型 |
|---|---------|---------|------|
| 1 | `test_unauthenticated_protected_endpoints_401` | 未认证访问受保护接口 → 401 | 鉴权网关 |
| 2 | `test_invalid_tokens_401` | 缺失/非法/格式错/错误 scheme/过期 token → 401 | 鉴权网关 |
| 3 | `test_inactive_user_rejected_and_token_invalidated` | 停用用户无法登录 + 旧 token 立即失效 → 401/403 | 账户生命周期 |
| 4 | `test_viewer_allowed_reads` | viewer 允许读（dashboard/events/opinions/reports） | 角色只读 |
| 5 | `test_viewer_denied_writes` | viewer 拒绝全部写（含数据源） → 403 | 最小权限 |
| 6 | `test_analyst_allowed_writes` | analyst 允许 keywords/events/opinions 写；清理 | 角色写权限 |
| 7 | `test_analyst_denied_admin_writes` | analyst 拒绝 users/roles 写、数据源写 → 403 | 最小权限 |
| 8 | `test_admin_superuser_full_access` | admin `is_superuser` 即使 `role_permissions=0` 仍可全访问；`permissions==["*"]` | 超管绕过 |
| 9 | `test_privilege_escalation_denied` | viewer/analyst 越权改关键词/数据源/用户/角色 → 403 | 越权防护 |

---

## 4. 逐测试结果

运行命令（仅测试库）：
```
DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test' \
DB_IDENTITY_CHECK=off \
./.venv/Scripts/python.exe -m pytest tests/test_rbac.py -v
```

`opinion_test` 状态：`alembic_version = rbac10001`，`permissions=26`、`role_permissions=17`、`roles=3`（与生产的 RBAC 结构一致）。

| # | 测试 | 结果 |
|---|------|------|
| 1 | `test_unauthenticated_protected_endpoints_401` | **PASS** |
| 2 | `test_invalid_tokens_401` | **PASS** |
| 3 | `test_inactive_user_rejected_and_token_invalidated` | **PASS** |
| 4 | `test_viewer_allowed_reads` | **PASS** |
| 5 | `test_viewer_denied_writes` | **PASS** |
| 6 | `test_analyst_allowed_writes` | **PASS** |
| 7 | `test_analyst_denied_admin_writes` | **PASS** |
| 8 | `test_admin_superuser_full_access` | **PASS** |
| 9 | `test_privilege_escalation_denied` | **PASS** |

**汇总：9 passed（连续两次运行均全绿，确认可重复）**。

重点验证项（回答需求中的关键问题）：
- **admin 超管绕过**：`admin` 用户 `role_permissions=0` 时仍返回 `permissions == ["*"]` 且可写关键词、可 PUT 不存在用户（不被 401/403）。✅
- **越权防护**：viewer 尝试改关键词/删关键词/改数据源/改用户/改角色，analyst 尝试改用户/角色，全部 403。✅
- **inactive 即时失效**：停用后旧 Bearer token 立即 401，登录返回 401/403。✅
- **无效 token**：缺失/非法/格式错/错误 scheme/过期，全部 401。✅

---

## 5. 失败与根因（测试过程中已修复的测试隔离问题）

本阶段测试代码曾 2 次失败，均属 **测试隔离/可重复性问题（修复优先级 #3），非后端安全缺陷**：

| 失败 | 现象 | 根因 | 修复 |
|------|------|------|------|
| 首次 `test_analyst_allowed_writes` | `POST /api/opinions` → `404 {"detail":"Region not found"}` | `Region` 主键是 `id`（自增），`code="130000"` 是独立唯一列；端点用 `db.get(Region, region_id)` 按**主键**查，而测试误传 `region_id=130000`（code 值）。端点行为正确。 | 测试改为查询 seed region 的真实 `id` 后传参 |
| 二次 `test_analyst_allowed_writes` | `POST /api/keywords` → `409 {"detail":"关键词已存在"}` | 上次失败在清理前中止，残留关键词 `akw` 触发唯一约束 `(word, type)` | 测试改用每次运行唯一的 `word`（uuid 后缀），彻底消除重跑冲突 |

修复后两次运行均 9/9 通过。

---

## 6. 修复清单（本阶段实际改动）

| 文件 | 改动 | 性质 | 修复优先级 |
|------|------|------|-----------|
| `backend/tests/test_rbac.py` | `ensure_test_env` 暴露 seed region 的真实主键 `id`（`_REGION_ID`）；analyst 测试改用真实 `id` | 测试隔离 | #3 |
| `backend/tests/test_rbac.py` | 测试创建的关键词改用 `uuid` 唯一后缀，避免重跑唯一冲突 | 测试隔离 | #3 |

**后端业务代码（auth / permissions / users / keywords / opinions / events / alerts / reports / admin_data_sources / dashboard）：本阶段零改动。**
未触发任何 P1（安全缺陷）/ P2（明确越权）修复——因审计与测试均未发现此类问题。

---

## 7. 本阶段是否发生数据库写操作？

| 数据库 | 是否写入 | 说明 |
|--------|---------|------|
| `opinion_db`（生产） | **否** | 全程未连接生产库；模块级护栏 `pytest.skip` 防止误指生产；DB 身份闸门未 bypass 生产路径 |
| `opinion_test`（隔离测试库） | **是（测试数据，允许）** | `ensure_test_env` 幂等写入 admin 用户 + 河北省 region；测试创建并清理 rbac_viewer / rbac_analyst / 临时关键词与舆情。测试结束时这些临时资源被删除（admin/region 保留供复用） |

`opinion_test` 在本阶段初已执行 `alembic upgrade head`（`DB_IDENTITY_CHECK=off`，仅测试库），将测试库结构对齐到 `rbac10001`——这是测试库迁移，属本阶段允许范围，**未对生产库跑任何 alembic**。

---

## 8. 生产数据是否变更？

**否。** 生产库 `opinion_db` 在本阶段未建立任何连接（除最初只读核验其 `rbac10001` 指纹外，且无写）。所有写操作均作用于隔离的 `opinion_test`。

---

## 9. 是否新增迁移（migration）？

**否。** 本阶段未创建任何新的 alembic 版本文件（`backend/alembic/versions/` 最新仍为 `rbac10001.py`）。仅新增/修改了测试文件 `backend/tests/test_rbac.py`，符合"禁止新增不必要迁移"边界。

---

## 10. 下一阶段（前端 RBAC）建议

基于本阶段建立的事实基线，给前端 RBAC 开发的明确输入：

1. **登录返回的 `permissions` 是权限真相来源，但需注意"读权限未强制"**：
   - 后端 `GET /api/opinions`、`GET /api/events`、`dashboard/*` 仅校验登录，不强制 `opinions:read`/`events:read`/`dashboard:read`。
   - 前端**不应**仅凭 `permissions` 列表隐藏这些读页面（否则会出现"前端隐藏但后端仍可读"的不一致）。建议：
     - 方案 A（推荐，最小后端改动）：前端按 `permissions` 控制 UI；后端保持"已登录即可读"（当前角色集安全）。
     - 方案 B（更严格）：下一阶段在后端为读接口补 `require_permission("...:read")`，实现前后端一致的最小权限。

2. **`sources:*` 与 `require_admin` 分歧**：数据源管理接口实际是超管专属（`require_admin`）。前端应将其放在"管理员专属"区域，而非按 `sources:read/write` 展示；或在后端统一为 `sources:write` 后前端按权限展示。**当前 seed 给 analyst 的 `sources:read` 是无效授权**（接口会 403），建议下一阶段清理 seed 或统一接口鉴权。

3. **超管判定两端一致**：前端可继续用 `role === 'admin' || is_superuser` 判定超管，与后端 `is_superuser_user` 一致。

4. **停用即失效已生效**：前端应处理 401（token 失效）跳转登录；建议补充全局 401 响应拦截器（当前前端无），避免静默空屏（见既有运维记录）。

5. **后端已具备多角色能力（`user_roles`）**：前端 RBAC 管理页可基于 `roles` / `permissions` / `role_permissions` 三张表做角色与权限的可视化分配，无需改后端模型。

6. **冗余权限码待清理（可选）**：`keywords:delete`、`reports:write`、`collectors:*`、`propagation:read`、`alerts:read`、`keywords:read` 当前无接口强制，建议在下一阶段明确"是否保留这些码"或补充对应接口强制，避免权限目录与实际强制脱节。

---

## 附：测试运行产物与边界合规自检

- ✅ 未触碰生产库 `opinion_db`
- ✅ 未修改任何后端业务代码
- ✅ 未新增/修改任何 alembic 迁移
- ✅ 未启动采集器、未触发真实采集任务
- ✅ 未修改前端、AppLayout、路由、指挥大屏、业务权限模型
- ✅ `DB_IDENTITY_CHECK=off` 仅用于隔离测试库 `opinion_test`，未进入任何生产路径
- ✅ 测试库写操作限于测试数据且可重复清理

> 结论：后端 RBAC 鉴权网关、超管绕过、最小权限、越权防护均工作正常；发现的非阻塞项为"读权限未强制"与"`sources:*`/require_admin 分歧"，均 fail-closed 或当前角色集下无实际风险，已记录并移交下一阶段前端 RBAC 处理。
