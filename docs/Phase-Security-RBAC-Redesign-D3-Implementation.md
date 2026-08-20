# Phase Security-RBAC-Redesign-D3 实施报告

> 舆情监测系统（YuQing）RBAC 收口 · Bocha 细粒度授权 · *:read 一致化 · system role 保护
> 日期：2026-08-13 ｜ 提交人：Senior Backend Engineer / Security-RBAC Engineer

---

## 1. 状态（Status）

**✅ PASS（无 BLOCKED）**

所有 D3 目标达成，生产迁移已落地（identity-verified），隔离测试、D1/D2 回归全绿，
红线零违反。D3 仅做「权限目录 + 角色权限分配」数据治理与端点 Enforcement 注入，
未触碰任何 Enforcement 语义、schema、角色表、Capability、ABAC 或 Collector/Scheduler/AI 逻辑。

---

## 2. 核心结果（Core Results）

| 项目 | 结果 |
|---|---|
| D3-01 Bocha 治理 | `admin_bocha.py` 5 个端点全部由 `require_admin` 改为细粒度 `require_permission`；`promote` 仅 `system_admin` 可操作，且 **未** 映射 `ai:search` |
| D3-02 *:read Enforcement | `opinions/events/alerts/propagation` 共 14 个 GET 端点补齐 `require_permission("<res>:read")`；`system_admin`/`operator` 显式授予 4 读权限（不扩张低权限角色） |
| D3-03 Foreign 高危 composite | `foreign:analysis` / `foreign:alerts:manage` 保持 **orphan**（无角色持有），其高危叶子（foreign:ai:full-confirm 等）**未**授予 analyst；状态即安全 |
| D3-04 权限组合设计 | search ≠ create-Opinion：`ai:search`（搜索）/ `bocha:read`（查看复核）/ `bocha:promote`（提升，高危）三权分离 |
| D3-05 Roles.vue 治理 | 经审计判定无需后端外改动；`role_permissions` 仍为唯一事实来源，Capability 仅 UI 预设层（未引入新实体） |
| D3-13/14 系统角色保护 | `update_role` 新增系统角色修改守卫；角色创建安全模型已就绪（D1 已强制 `is_system=False` + 唯一 code） |
| D3-06 Alembic 迁移链 | 链完整、单一 head，无需 merge；新增 `rbac_d3_enforcement_v2` 链式挂接 `rbac_d2_enforcement_v1` |
| 生产迁移 | `alembic upgrade rbac_d3_enforcement_v2`（identity gate ON）→ 成功，`current = rbac_d3_enforcement_v2 (head)` |
| 回归 | D1(28) + D2(28) 全绿；D3 新增 15 项全绿 |

**关键回归防护**：生产 `system_admin` 原先**不持有** `ai:search`，若只把 `search_bocha` 改为
`require_permission("ai:search")` 会将其锁死在 Bocha 搜索之外。D3 迁移显式将 `ai:search` 授予
`system_admin`，实现「system_admin 可完整操作」且不构成对 analyst/viewer 的扩张。

---

## 3. 执行前审计摘要（Pre-execution Audit）

- **git status / diff**：确认仅 7 个后端源文件 + 1 个迁移文件为 D3 工作区改动；前端 `static` 变更为既有无关构建产物，未纳入本次范围。
- **代码审计**：`core/permissions.py`（`require_permission` / `require_admin` / `expand_permissions` / `COMPOSITE_PERMISSIONS` 语义未变）、`admin_bocha.py`、`opinions/events/alerts/propagation/users.py`、`models/*`、`Roles.vue` / `usePermission.ts` 全部只读审阅。
- **Alembic 链审计**：
  - `alembic heads` = 单一 head `rbac_d3_enforcement_v2`（D3 落地后）。
  - 落地前 `current = rbac_d2_enforcement_v1`；链 `…review_decision_complete_v2 → rbac_d1_role_gov_v1 → current_risk_adoption_v1 → rbac_d2_enforcement_v1`，**无 dangling 分支、无 Multiple Heads**（D2 报告 §10 的告警经核实不成立）。
- **生产只读基线（127.0.0.1:5432/opinion_db）**：
  - `system_admin`：18 权限，**无** `ai:search`、无 4 读、`bocha:*` 不存在；
  - `operator`：12 权限，**无** 4 读；
  - `analyst`：31 权限，**有** `ai:search` + 4 读；
  - `viewer`：8 只读；
  - `bocha:read` / `bocha:promote` 在生产**尚不存在**（perm_exists=0）。

---

## 4. Permission 变化（Permission Changes）

新增 2 个权限（D3 真正新增）：

| code | name | resource | action | group | 说明 |
|---|---|---|---|---|---|
| `bocha:read` | Bocha 线索查看 | bocha | read | Bocha | 查看搜索会话、线索列表、确认/拒绝（**不含**提升为舆情） |
| `bocha:promote` | Bocha 线索提升为舆情 | bocha | promote | Bocha | 将线索创建为正式 Opinion（高危写，仅 `system_admin`） |

既有 4 读权限仅「确保存在」（D3 前已存在并被 analyst/viewer 持有），不在 downgrade 中删除。

**生产计数**：`permissions` 86 → **88**（+2）；`role_permissions` 117 → **129**（+12）。

---

## 5. 角色权限矩阵（Role Permission Matrix，迁移后）

| 角色 | 权限数 | 相对 BEFORE 新增 | 关键能力 |
|---|---|---|---|
| `system_admin` | 25 | `ai:search`, `opinions:read`, `events:read`, `alerts:read`, `propagation:read`, `bocha:read`, `bocha:promote` | 全业务管理 + Bocha 全操作（含 promote） |
| `operator` | 16 | `opinions:read`, `events:read`, `alerts:read`, `propagation:read` | 采集/数据源 + 4 读（**无** Bocha、无业务研判写） |
| `analyst` | 32 | `bocha:read` | 研判/编辑 + Bocha 搜索与复核（**无** promote） |
| `viewer` | 8 | （无变更） | 8 项只读（**无** `ai:search`、无 `bocha:*`） |

> `foreign:analysis` / `foreign:alerts:manage` 在两表中均为 **0 持有者（orphan）**。

---

## 6. Bocha 逐端点（D3-01 / D3-04）

| 端点（admin_bocha.py） | 行 | 改造前 | 改造后 | 语义 |
|---|---|---|---|---|
| `search_bocha` | 89 | `require_admin` | `require_permission("ai:search")` | 搜索/检索 |
| `list_bocha_leads` | 146 | `require_admin` | `require_permission("bocha:read")` | 查看线索列表 |
| `confirm_bocha_lead` | 197 | `require_admin` | `require_permission("bocha:read")` | 确认线索 |
| `reject_bocha_lead` | 230 | `require_admin` | `require_permission("bocha:read")` | 拒绝线索 |
| `promote_bocha_lead` | 268 | `require_admin` | `require_permission("bocha:promote")` | 提升为舆情（**仅 system_admin**） |

用户侧 `bocha.py` 路由器（line 39）早已 `require_permission("ai:search")` 保护，与本次一致。
**关键约束满足**：`promote` 经 `bocha:promote` 而非 `ai:search`，故「搜索 ≡ 提升」不成立；
`analyst` 可搜索/复核但**不能** promote。

---

## 7. *:read 逐模块（D3-02）

| 模块 | 文件 | 注入端点数 | 依赖权限 | 受影响角色补齐 |
|---|---|---|---|---|
| 舆情 | `opinions.py` | 4（list/list_sources/get_original/get） | `opinions:read` | system_admin、operator 新增 |
| 事件 | `events.py` | 5（list/hot_topic/get_situation/get_opinions/get） | `events:read` | system_admin、operator 新增 |
| 预警 | `alerts.py` | 3（list_rules/unread/list_records） | `alerts:read` | system_admin、operator 新增 |
| 传播 | `propagation.py` | 2（list_events/get_graph） | `propagation:read` | system_admin、operator 新增 |

**设计原则**：仅把「此前靠 router 级 `get_current_user`（任意已登录可读）」的 GET 端点
显式化为角色级 `require_permission`；4 读权限授予 system_admin/operator 是将其**既有读能力显式化**，
**绝不**向 analyst/viewer 追加任何写能力。

---

## 8. Foreign 权限治理（D3-03）

- `foreign:analysis`（21 叶子，含 `foreign:ai:full-confirm` / `foreign:ai:review:reject` / `foreign:events:review:confirm` / `foreign:alerts:review:confirm` 等高危）与 `foreign:alerts:manage`（7 叶子）**保持 orphan**：
  - 未在任何角色的 `role_permissions` 中赋值；
  - 其叶子权限在 foreign 各端点上仍按既有细粒度 `require_permission` 独立校验（analyst 仅持有 `foreign:read` 展开后的读能力，不持有上述高危叶子）。
- 决策：维持现状 = 安全。**不修改** `COMPOSITE_PERMISSIONS`（红线默认 BLOCKED），避免误授高危能力给低权限角色。

---

## 9. Alembic 迁移链（D3-06）

- 新增迁移：`rbac_d3_enforcement_v2`
  - `revision = "rbac_d3_enforcement_v2"`，`down_revision = "rbac_d2_enforcement_v1"`；
  - 复用 D2 既定模式：`op.get_bind()` + `Session` + `_ensure_permissions` / `_grant_roles`，幂等，Alembic 事务内自动提交；
  - `downgrade` 仅移除本迁移新增/关联的 `role_permissions`，并仅在无其它引用时删除 `bocha:read` / `bocha:promote`。
- 链完整性：`heads` 单一；未 merge、未改历史迁移、未强制 `upgrade head`。
- identity gate：`alembic/env.py:42 assert_identity_for_migration()` 在生产执行前返回 `DATABASE IDENTITY: VERIFIED`。

---

## 10. 测试（Tests）

| 套件 | 范围 | 结果 |
|---|---|---|
| `tests/test_rbac_d3.py`（新增，隔离 SQLite） | 15 项：Bocha 三权分离、*:read 按角色、Foreign orphan、提升防护、系统角色守卫、superuser `["*"] | **15 passed** |
| `tests/test_rbac_d1.py` + `tests/test_rbac_d2.py`（回归） | D1/D2 矩阵与 Enforcement | **28 passed** |

测试隔离：全部使用 `sqlite://` in-memory，**绝不连接** 生产 5432 / 测试 5433。

**关于 `tests/test_rbac.py` / `tests/test_rbac_hardening.py` 的分类**：
- 二者为 Phase RBAC-1/2、RBAC-2C 的**既有/环境依赖**测试；
- 仅面向隔离库 `opinion_test`，且模块级护栏在 `DATABASE_URL` 命中 `opinion_db` 时整体 `skip`；
- 需独立的、已播种的测试库（schema 可能与当前生产不完全一致），**非 D3 引入的失败**；
- 结论：属 pre-existing/environmental，不在本次 D3 验收范围内，未对其执行生产写入。

---

## 11. 修改文件清单（Modified Files）

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `backend/app/api/admin_bocha.py` | 修改 | 5 端点 `require_admin` → 细粒度 `require_permission`；移除 `require_admin` 引用 |
| `backend/app/api/opinions.py` | 修改 | 4 GET 端点加 `opinions:read` |
| `backend/app/api/events.py` | 修改 | 5 GET 端点 `get_current_user` → `events:read` |
| `backend/app/api/alerts.py` | 修改 | 3 GET 端点 `get_current_user` → `alerts:read` |
| `backend/app/api/propagation.py` | 修改 | 2 GET 端点 `get_current_user` → `propagation:read` |
| `backend/app/api/users.py` | 修改 | `update_role` 加系统角色修改守卫（line 515） |
| `backend/alembic/versions/rbac_d3_enforcement_v2.py` | 新增 | D3 数据层迁移（权限 + 角色绑定） |
| `backend/tests/test_rbac_d3.py` | 新增 | D3 隔离测试（15 项） |
| `docs/Phase-Security-RBAC-Redesign-D3-Implementation.md` | 新增 | 本实施报告 |

> 注：前端 `app/static/assets/*` 的 M 状态为既有构建产物，非本次 D3 改动，未纳入。

---

## 12. D3 红线遵守（Red-line Compliance）

| 红线 | 遵守情况 |
|---|---|
| 不修改 `require_permission`/`require_admin`/`expand_permissions`/`COMPOSITE_PERMISSIONS` 语义 | ✅ 仅移除端点对 `require_admin` 的调用；`require_admin` 定义保留未动 |
| 不修改 `COMPOSITE_PERMISSIONS`（默认 BLOCKED） | ✅ `foreign:analysis`/`foreign:alerts:manage` 维持不变 |
| 不引入 Capability DB 实体 / 第二权限事实源 | ✅ `role_permissions` 仍为唯一事实来源 |
| 不改动 schema / `role_permissions` 表结构 / `users` / `roles` | ✅ 迁移仅 INSERT 权限与关联行 |
| 不引入 ABAC / data_scope | ✅ |
| 不改动 Collector / Scheduler / AI 逻辑 | ✅ |
| 不扩张 analyst / viewer | ✅ analyst 仅 +`bocha:read`；viewer 0 变更 |
| Bocha promote **不**映射 `ai:search` | ✅ 用独立 `bocha:promote` |
| 不向 analyst 授予 `foreign:analysis` / `foreign:alerts:manage` | ✅ 二者保持 orphan |
| 不修改/删除历史迁移 | ✅ 仅新增 `rbac_d3_enforcement_v2` |
| 不强制 `alembic upgrade head` | ✅ 仅 `upgrade rbac_d3_enforcement_v2`（identity-verified） |
| 不自动变更用户/角色 | ✅ |

---

## 13. 遗留问题与产物（Open Issues & Deliverables）

### 遗留 / 已知限制
1. **`foreign:analysis` / `foreign:alerts:manage` orphan**：为 D1 已 BLOCKED 项，留待后续能力模型拆分阶段处置；当前安全状态可接受。
2. **`tests/test_rbac.py` / `test_rbac_hardening.py`**：依赖独立测试库 `opinion_test`（需预播种），非本次执行对象；建议在下一阶段统一测试库基线后纳入 CI。
3. **`Roles.vue` / `usePermission.ts`**：经审计无需后端外改动；其权限目录不过滤调用者已授权集合，依赖后端系统角色守卫兜底（已补强）。如需前端 UX 收敛可另立任务。

### 产物（Deliverables）
- 迁移：`backend/alembic/versions/rbac_d3_enforcement_v2.py`
- 后端 Enforcement 改造：6 个 API 文件（见 §11）
- 测试：`backend/tests/test_rbac_d3.py`（15 项，全绿）+ D1/D2 回归（28 项，全绿）
- 生产验证快照：`audit-evidence/BEFORE_rbac_d3.json`、`audit-evidence/AFTER_rbac_d3.json`
- 本报告：`docs/Phase-Security-RBAC-Redesign-D3-Implementation.md`

### 生产验证结论
- `permissions` 86 → 88（+2）；`role_permissions` 117 → 129（+12）
- `system_admin` 25 / `operator` 16 / `analyst` 32 / `viewer` 8（viewer 不变）
- `bocha:promote` 仅 `system_admin` 持有；`bocha:read` 由 `system_admin` + `analyst` 持有
- `foreign:analysis` / `foreign:alerts:manage` 持有者 = 0
- 残存 `require_admin` 端点调用 = 0（仅 `core/permissions.py` 定义保留）
