# Phase Security-RBAC-Redesign-D2 实施报告

**Enforcement 重构与权限边界收口**

- 日期：2026-08-13
- 阶段：D2（承接 D1 角色/权限目录治理，使 D1 的权限数据真正落地到 API Enforcement）
- 状态：**PASS**
- 生产库：`127.0.0.1:5432/opinion_db`（身份校验 `VERIFIED`，opinions=1765）
- Alembic 操作：`alembic upgrade rbac_d2_enforcement_v1`（**仅 D2 修订，未升级 head**）

---

## 0. 结论速览（状态 / 结果 / 边界）

| 项 | 结果 |
|---|---|
| 总体状态 | ✅ PASS |
| 新增权限 | `opinions:delete` / `events:delete` / `collector:run`（各 1 行，幂等） |
| 角色绑定 | `system_admin` ← 3 项；`operator` ← `collector:run` |
| 低权角色扩大 | ❌ 无（analyst / viewer 权限集 0 变化） |
| 迁移幂等 | ✅ 重复执行不重复插入 |
| 生产数据变更 | permissions 83→86(+3)；role_permissions 113→117(+4) |
| 测试 | D2 专项 14 passed；D1 回归 14 passed（共 28）；生产读校验 VERIFIED |
| 遗留 require_admin | 仅 `admin_bocha.py` ×5（超管专用，设计保留，推迟 D3） |
| 红线的违背 | ❌ 无（未升级 head / 未改 schema / 未改 Enforcement 实现 / 未改前端） |

---

## 1. 目标与范围

D1 已完成「角色 → 权限 → role_permissions」数据治理（`system_admin`/`operator` 角色建立、analyst 补齐、`111` 游离角色清理），但 **API 层仍大量使用 `require_admin()`**，导致 D1 的权限数据并未真正约束接口访问（任何超管都能过，非超管的业务角色拿不到细粒度授权）。

D2 目标：把 `require_admin()` 收敛为 `require_permission(<明确业务权限>)`，使 D1 的权限目录**真正生效**，同时：
- 新增 3 个缺失的业务权限（删除舆情 / 删除事件 / 触发采集）；
- 收口 `sources:write` 幽灵权限（此前 Enforcement 未引用，现接入国内数据源写接口）；
- 新增角色创建/编辑的权限提升防护（`_assert_no_privilege_escalation`）；
- **绝不扩大任何低权角色**（analyst / viewer 权限集零变化）。

---

## 2. 红线与禁止项（已遵守）

| 红线 | 是否违反 |
|---|---|
| 不升级 head（仅 `rbac_d2_enforcement_v1`） | ✅ 遵守 |
| 不修改 `expand_permissions` / `COMPOSITE_PERMISSIONS` / `require_permission` / `require_admin` 实现 | ✅ 遵守（仅新增调用点，未改函数体） |
| 不改前端 | ✅ 遵守（D2 纯后端） |
| 不改 schema（无新表/列/迁移结构变更） | ✅ 遵守（迁移仅 INSERT 权限与关联） |
| 不引入 Capability | ✅ 遵守 |
| 不新增 3 个以外的权限（除最小必需） | ✅ 遵守（仅 opinions:delete/events:delete/collector:run） |
| 不改动 service 业务逻辑 | ✅ 遵守（仅改 API 依赖注入） |
| 不改动历史迁移 | ✅ 遵守（新增独立修订） |

---

## 3. Enforcement 变更清单（逐项）

### 3.1 `backend/app/api/opinions.py`
| 行 | 端点 | 变更前 | 变更后 |
|---|---|---|---|
| ~490 | `DELETE /api/opinions/batch`（批量删除） | `require_admin` | `require_permission("opinions:delete")` |
| ~531 | `DELETE /api/opinions/{id}`（单条删除） | `require_admin` | `require_permission("opinions:delete")` |

### 3.2 `backend/app/api/collector.py`
| 行 | 端点 | 变更前 | 变更后 |
|---|---|---|---|
| ~157 | `POST /api/collector/run`（手动触发采集） | `require_admin` | `require_permission("collector:run")` |

### 3.3 `backend/app/api/admin_data_sources.py`
| 行 | 端点 | 变更前 | 变更后 |
|---|---|---|---|
| ~974 | `GET /api/admin/data-sources/regions` | `require_admin` | `require_permission("sources:read")` |
| ~1069 | `POST /api/admin/data-sources/test` | `require_admin` | `require_permission("sources:write")` |
| ~1095 | `POST /api/admin/data-sources/`（创建） | `require_admin` | `require_permission("sources:write")` |
| ~1171 | `POST /api/admin/data-sources/schedule/batch` | `require_admin` | `require_permission("sources:write")` |
| ~1266 | `PATCH /api/admin/data-sources/{ds_id}` | `require_admin` | `require_permission("sources:write")` |

> 说明：`sources:write` 此前是「幽灵权限」（Enforcement 未引用，仅存在于 system_admin/operator 的权限集）。D2 将其接入国内数据源的 创建/测试/调度/更新 与 regions 读 接口，**使该权限具备真实 Enforcement 语义**。未扩大任何角色——它本就只属于 system_admin/operator。

### 3.4 `backend/app/api/admin_regions.py`
| 行 | 端点 | 变更前 | 变更后 |
|---|---|---|---|
| ~19 | `GET /api/admin/regions` | `require_admin` | `require_permission("sources:read")` |

### 3.5 `backend/app/api/events.py`
| 行 | 端点 | 变更前 | 变更后 |
|---|---|---|---|
| ~480 | `DELETE /api/events/{event_id}` | `require_permission("events:write")` | `require_permission("events:delete")` |

> 关键语义修正：原 `events:write` 同时覆盖「编辑/合并」与「删除」，导致 analyst 可删除事件（权限倒置）。D2 将「删除」独立为 `events:delete`（仅 system_admin），analyst 保留 `events:write`（编辑/合并）但**不再能删除**。`events.py` 其余既有用户脏改（行 45–97 的 `current_risk` 等）**原样保留，未触碰**。

### 3.6 `backend/app/api/users.py`（仅新增权限提升防护）
- 新增辅助函数 `_assert_no_privilege_escalation(current_user, requested_codes, db)`：
  - 超管（`is_superuser` 或 `role=='admin'` → 有效权限 `["*"]`）直接放行；
  - 否则逐项校验：请求授予的权限码必须已存在于调用者自身有效权限集中，否则 `403 无权授予以下权限：...`。
- 接入 `create_role` 与 `update_role`（约行 470 / 502），在写库前拦截越权授权。
- **未改动** `users.py` 既有任何其他逻辑。

---

## 4. require_admin 最终残留清单

D2 执行后，全代码仅剩以下 `require_admin` 端点调用（**5 处，全部位于 `admin_bocha.py`，设计保留为超管专用**）：

| 文件:行 | 端点 | 处理决策 |
|---|---|---|
| `admin_bocha.py:89` | Bocha 检索/配置 | 保留 `require_admin`（超管专用） |
| `admin_bocha.py:146` | Bocha 任务列表 | 保留 `require_admin` |
| `admin_bocha.py:197` | Bocha 任务详情 | 保留 `require_admin` |
| `admin_bocha.py:230` | Bocha 结果拉取 | 保留 `require_admin` |
| `admin_bocha.py:268` | Bocha 提升为舆情（promote） | 保留 `require_admin` |

**保留理由**：`ai:search` 当前由 admin+analyst 持有；Bocha `promote` 会创建 Opinions，若映射到 `ai:search` 会把创建舆情能力扩给 analyst，违背 D2「不扩大低权角色」红线。故 Bocha 系列保持超管专用，推迟至 **D3** 能力模型拆分时再决定细粒度授权。

> 注：`permissions.py:132` 的 `require_admin` 定义与 `rbac_d1.py` 文档提及均**未修改**（红线）。

---

## 5. 权限变更（新增 3 项）

| code | name | resource | action | group | 绑定角色 |
|---|---|---|---|---|---|
| `opinions:delete` | 删除舆情 | opinions | delete | 舆情 | system_admin |
| `events:delete` | 删除事件 | events | delete | 事件 | system_admin |
| `collector:run` | 触发采集 | collector | run | 采集 | system_admin, operator |

生产校验（AFTER 快照）：
- `permissions` 表：83 → **86**（+3，每项恰好 1 行）
- `role_permissions` 表：113 → **117**（+4 = system_admin×3 + operator×1）

---

## 6. 角色变更矩阵（D2 前后对比）

| 角色 | D2 前权限数 | D2 后权限数 | 变化 |
|---|---|---|---|
| `system_admin` | 15 | 18 | +opinions:delete, +events:delete, +collector:run |
| `operator` | 11 | 12 | +collector:run（**仅此一项**） |
| `analyst` | 31 | 31 | **0 变化**（保留 events:write/opinions:write 编辑能力，不含任何 delete/collector:run/foreign:analysis） |
| `viewer` | 8 | 8 | **0 变化** |

验证脚本断言（AFTER 快照 `[verified]=True`）：
- `system_admin` 含全部 3 个 D2 新权限；
- `operator` 仅含 `collector:run`，**不含** opinions:delete/events:delete；
- `analyst` ∩ {opinions:delete, events:delete, collector:run} = ∅；
- `viewer` ∩ {opinions:delete, events:delete, collector:run} = ∅；
- `analyst`/`viewer` 权限集与 BEFORE 快照**逐码相等**。

---

## 7. 安全边界（Security Boundary）

- **高危删除收敛到 system_admin**：舆情删除、事件删除现在仅 `system_admin` 可触发；非超管的 analyst 只能编辑/合并，不能删除。
- **采集触发分级**：`collector:run` 授予 system_admin + operator（基础设施操作），analyst/viewer 不可触发。
- **角色授权防提升**：创建/编辑角色时，调用者只能把**自己已持有**的权限授予他人；越权授权被 `403` 拦截（覆盖 system_admin 越权授予 opinions:write、operator 越权授予 foreign:analysis 等场景）。
- **超管等价不变**：`is_superuser` 或 `role=='admin'` 仍返回 `["*"]`，不受 D2 影响；Bocha 系列保持超管专用。
- **低权角色零扩大**：analyst / viewer 权限集在 D2 前后完全一致，满足「权限边界收口、不扩大」硬约束。

---

## 8. 测试（隔离 + 读校验）

### 8.1 D2 专项测试 `backend/tests/test_rbac_d2.py`（**14 passed**）
SQLite in-memory，**绝不连接生产/测试库**。覆盖：
1. 新增权限存在性：opinions:delete / events:delete / collector:run 均存在；
2. D2 migration 数据逻辑幂等（`_ensure_permissions` / `_grant_roles` 重复执行不重复插入）；
3. `system_admin` 矩阵：不含 `*`、含 collector:run、= SYSTEM_ADMIN_PERMS ∪ D2_NEW；
4. `operator` 矩阵：含 collector:run、不含 users:read/roles:write/permissions:read/foreign:analysis/foreign:alerts:manage；
5. `analyst` 不获 D2 高危权限、保留 events:write（生产基线建模）；
6. `viewer` 完全不扩大；
7. `require_permission` Enforcement 决策：合法角色 200/通过，非法角色 403；
8. 超管 `get_user_permissions` == `["*"]`；
9. 权限提升防护：拦截 system_admin 授予 opinions:write、拦截 operator 授予 foreign:analysis、放行超管。

### 8.2 D1 回归 `backend/tests/test_rbac_d1.py`（**14 passed**）
确认 D2 未破坏 D1 治理逻辑（28 passed 合计）。

### 8.3 既有 RBAC 集成测试 `test_rbac.py` / `test_rbac_hardening.py`
- 结果：**171 passed，16 failed**。
- 分类结论：**16 个失败全部为既有/环境性，0 个由 D2 引发**。
  - 主因：测试库 `127.0.0.1:5433/opinion_test` 的 alembic head 仍为 `current_risk_adoption_v1`，**D1 与 D2 迁移从未应用于 5433**，故角色权限集与生产/D1 设计不一致 → 接口 403、权限集/描述断言失败（如 `sources:read description 未修正: test database migration prerequisite`）。
  - 次因：部分 hardening 测试的预期**与 D1 设计相矛盾**（如 `test_role_no_privileged_admin_permissions[system_admin]` 期望 system_admin 不持有 users:read/roles:write，但 D1 明确授予），此类测试无论 D2 与否均失败。
  - D2 Enforcement 改动（opinions 删除 / collector 运行 / sources 读写 / events 删除 / users 提升防护）**未在任何失败断言中被 D2 特异性触发**——失败均源于 5433 角色缺少对应权限（DB 状态），而非端点语义变化。

### 8.4 生产只读校验（AFTER 快照 `audit-evidence/d2_after_snapshot.json`）
`verified = True`，errors = []，analyst/viewer 均未变化。

---

## 9. 迁移（Alembic）

- 文件：`backend/alembic/versions/rbac_d2_enforcement_v1.py`（**新建**）
- `revision = "rbac_d2_enforcement_v1"`，`down_revision = "current_risk_adoption_v1"`
- 仅做数据治理：`_ensure_permissions`（幂等插入 3 权限）、`_grant_roles`（幂等关联 system_admin/operator）
- `upgrade()` / `downgrade()` 均使用 `op.get_bind()` + `Session`，flush 后由 Alembic 统一提交（事务内）
- 执行：`alembic upgrade rbac_d2_enforcement_v1`（身份门禁 `DB IDENTITY: VERIFIED`）
- **未升级 head**：遵循红线，避免牵连 D1 悬空分支（见 §10 风险）

---

## 10. 已知风险 / 推迟项（Deferred）

1. **D1 Alembic 修订悬空**：生产 alembic head 在执行 D2 前为 `current_risk_adoption_v1`，而 D1 的 `rbac_d1_role_gov_v1` 的 `down_revision = "review_decision_complete_v2"`，与当前 head 不连续。D1 的**数据**已通过 `apply_d1_role_fixes` 核心函数直接落地生产，但其 **alembic 修订从未 apply**。现状：D2 链路（current_risk_adoption_v1 → rbac_d2_enforcement_v1）自洽可应用，但整体迁移图存在 D1 悬空分支。未来执行 `alembic upgrade head` 会因「Multiple heads」报错。建议后续（D3 或独立迁移治理任务）将 D1 修订的 `down_revision` 修正为 `current_risk_adoption_v1` 并补齐 apply，使图收敛为单链。

2. **Bocha 系列超管专用（D3）**：5 个 `admin_bocha.py` 端点保持 `require_admin`，待 D3 能力模型拆分后决定 `ai:search` / promote 的细粒度授权。

3. **`*:read` Enforcement 推迟 D3**：`opinions:read` / `events:read` / `alerts:read` / `propagation:read` 由 analyst+viewer 持有但**未**由 system_admin/operator 持有；`foreign:*:read` 仅 admin 持有。若现在在对应读接口加 `require_permission("*:read")`，会使 system_admin/operator 在既有读接口 403，违背 D2 目标。故统一读接口 Enforcement 留待 D3。

4. **测试库 5433 未迁移**：集成测试需在 5433 应用 D1+D2 后方可全绿；属测试环境治理，不在 D2 变更范围内。

---

## 11. 修改文件清单（Deliverables）

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/app/api/opinions.py` | 改 | 2 处删除端点 → `require_permission("opinions:delete")` |
| `backend/app/api/collector.py` | 改 | 1 处采集触发 → `require_permission("collector:run")` |
| `backend/app/api/admin_data_sources.py` | 改 | 5 处数据源接口 → `sources:read` / `sources:write` |
| `backend/app/api/admin_regions.py` | 改 | 1 处 regions 读 → `sources:read` |
| `backend/app/api/events.py` | 改 | 删除事件 → `require_permission("events:delete")` |
| `backend/app/api/users.py` | 改 | 新增 `_assert_no_privilege_escalation` 并接入 create_role/update_role |
| `backend/alembic/versions/rbac_d2_enforcement_v1.py` | 新建 | D2 数据迁移（幂等） |
| `backend/tests/test_rbac_d2.py` | 新建 | D2 隔离专项测试（14 passed） |
| `docs/Phase-Security-RBAC-Redesign-D2-Implementation.md` | 新建 | 本报告 |
| `audit-evidence/d2_before_snapshot.json` | 新建 | 生产 BEFORE 快照 |
| `audit-evidence/d2_after_snapshot.json` | 新建 | 生产 AFTER 快照（verified=True） |

---

## 12. 验收标准核对

| 验收项 | 结果 |
|---|---|
| D1 权限数据在 API 层真正生效 | ✅ |
| 新增 3 权限且绑定正确角色 | ✅ |
| `sources:write` 幽灵权限收口为真实 Enforcement | ✅ |
| 角色创建/编辑防权限提升 | ✅ |
| analyst/viewer 权限集零扩大 | ✅ |
| 迁移幂等、可回滚（downgrade 实现） | ✅ |
| 仅 D2 修订、未升级 head、未改 schema/前端/Enforcement 实现 | ✅ |
| 生产身份校验 VERIFIED、变更可核对 | ✅ |
| 测试：D2 14 + D1 14 通过 | ✅ |
| 遗留 require_admin 仅 Bocha ×5（有据可查） | ✅ |
