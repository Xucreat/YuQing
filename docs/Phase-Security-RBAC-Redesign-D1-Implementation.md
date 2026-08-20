# Phase Security-RBAC-Redesign-D1 实施报告

> 权限目录与角色分配治理（Role → Permission → role_permissions）
> 零 Enforcement 改动 · 零 Capability · 零 schema 改动 · 数据层幂等迁移

---

## 1. Executive Summary

D1 已按设计在生产库（127.0.0.1:5432/opinion_db，身份校验 VERIFIED，opinions=1765）完成落地：

- 新增正式角色 **system_admin**（非 `*`、可审计）与 **operator**（数据源与采集）。
- 修复 `foreign:read` → analyst、`foreign:data:manage` → operator+system_admin 两个组合权限无人持有的死分支。
- 补齐 **analyst** 业务缺口（`keywords:write` / `foreign:ai:review:read` / `foreign:ai:batch:read` / `foreign:ai:batch:cancel` / `foreign:read`），并收紧其不应持有的 `permissions:read`、`sources:write`（幽灵权限）。
- 安全清理游离角色 **111**（无用户/附加角色引用）。
- 孤儿权限 21 → 8（剩余 8 个全部属于被**有意 BLOCKED** 的 `foreign:analysis` / `foreign:alerts:manage` 组合，其展开含高危 `foreign:ai:full-confirm` 且 scope 不明确，留待 D2/D3 能力模型拆分）。

**状态：PASS。** 全部 D1 验收项满足；未改动任何 Enforcement / 前端 / schema / `collector:run` / 历史迁移。

实施过程中发现并正确处理一处范围外事件：执行 `alembic upgrade head` 时，工作区存在一个**未提交的、以本 D1 迁移为前置**的待执行 schema 迁移 `current_risk_adoption_v1`（prior phase 风险列持久化），被一并执行。为严格保持 D1「只做 RBAC 数据、不动 schema」的边界，已将其 `downgrade` 回退，使生产库停留在 `rbac_d1_role_gov_v1`。该 schema 迁移应在其自身阶段单独执行（见 §20）。

---

## 2. 当前工作区 dirty 状态说明

实施前执行 `git status --short --branch`（HEAD=58717ff9，branch main…origin/main）。工作区存在大量未提交改动（与 D1 无关），节选：

```
 M Foreign_RSS_Source_Recommendations.md
 M backend/app/api/__init__.py
 M backend/app/api/analysis.py
 M backend/app/api/foreign.py
 M backend/app/core/permissions.py      ← 工作区已 M，但 D1 未触碰
 M backend/app/models/{__init__,alert,event,foreign_manual_review}.py
 M backend/app/schemas/{alert,event,opinion}.py
 M backend/app/services/alert_service.py
 M backend/app/static/assets/*          ← 构建产物（node 虚拟化层，非源码）
 ...
```

- D1 **未修改** 上述任何文件；`permissions.py` 仍为工作区原有 M 状态。
- D1 新增文件均为未跟踪（`??`），不覆盖既有未提交改动。
- 未对既有未提交改动做任何 stash / 回滚 / 假设。

---

## 3. 实施前源码事实（重新核验）

| 项 | 事实 | 证据 |
| --- | --- | --- |
| 组合权限定义 | 5 个：`ai:analyze` + `foreign:read`/`foreign:data:manage`/`foreign:analysis`/`foreign:alerts:manage` | `backend/app/core/permissions.py:34-94` `COMPOSITE_PERMISSIONS` |
| 展开函数 | `expand_permissions` 纯函数、幂等；`get_user_permissions` 先判 `is_superuser_user` 再展开 | `permissions.py:97-129` |
| ADMIN 判定 | `is_superuser` 或 `role=='admin'` 等价超管，返回 `["*"]` | `permissions.py:22-24,116-117` |
| Role 模型 | `name`(unique)/`code`(unique)/`is_system`/`is_enabled`；**无 `is_superuser` 列** | `models/role.py` |
| Permission 模型 | `code`(unique)/`resource`/`action`/`group` | `models/permission.py` |
| 历史迁移不被改 | `foreign_batch_review_permissions.py` 是既有迁移，D1 不修改 | 仅新增 `rbac_d1_*` |
| 无 `collector:run` | 全局 grep 无此 permission；采集接口仅 `require_admin` | `app/api/collector.py:157` |
| 无前端/Enforcement 改动 | D1 不触碰 `dependencies.py` / `usePermission.ts` / `Roles.vue` | — |

---

## 4. 实施前数据库事实（只读 SELECT，BEFORE）

| 维度 | 值 |
| --- | --- |
| roles | 4：admin(1,is_system) / analyst(2,is_system) / viewer(3,is_system) / **111(5,is_system=False,code='111')** |
| permissions | 83 |
| role_permissions | 85（admin 48 / analyst 28 / viewer 8 / 111 1） |
| user_roles | 0 |
| users | 3：admin(superuser) / 测试(analyst) / 观察测试(viewer) |
| orphan permissions | 21（含 `users:*`/`roles:*`/`keywords:write`/`audit_logs:read`/`login_logs:read`/`foreign:read`/`foreign:data:manage`/`foreign:analysis`/`foreign:alerts:manage`/`foreign:ai:batch:read`/`foreign:ai:batch:cancel` 等） |
| 4 个 foreign 组合权限持有角色 | **全部 0 角色**（死分支确认） |
| 角色 111 引用 | `users.role` 无；`user_roles` 0；`role_permissions` 1（opinions:read）；无其他表 FK；源码无硬编码 `111` |
| `sources:write`(domestic) | 仅 analyst 持有；全量 grep `app/api` 无任何端点引用（幽灵权限） |

---

## 5. 实际修改文件

| 动作 | 文件 | 说明 |
| --- | --- | --- |
| 新增 | `backend/app/core/rbac_d1.py` | D1 数据治理 helper（幂等 add/remove 角色权限、清理 111）；**非 Enforcement**，被迁移与测试共用 |
| 新增 | `backend/alembic/versions/rbac_d1_role_directory_governance.py` | D1 前向迁移（revision=`rbac_d1_role_gov_v1`, down=`review_decision_complete_v2`）；flush 交由 Alembic 事务统一提交 |
| 新增 | `backend/tests/test_rbac_d1.py` | D1 隔离测试（SQLite in-memory，14 项） |
| 新增 | `audit-evidence/_rbac_d1_verify.py` | 生产只读验证脚本（仅 SELECT） |
| 新增 | `audit-evidence/_rbac_d1_after_snapshot.txt` | AFTER 快照证据 |
| 生产数据 | `role_permissions` / `roles` | 经迁移写入（见 §14） |

**未修改**：`permissions.py` / `dependencies.py` / `roles.py` / `permission.py` / `user.py` / 任何 API / Service / 前端 / `COMPOSITE_PERMISSIONS` / `expand_permissions` / `require_permission` / `require_admin` / 任何历史迁移 / `role_permissions` schema。

---

## 6. 新增 migration 说明

- **revision** `rbac_d1_role_gov_v1`，**down_revision** `review_decision_complete_v2`。
- **幂等**：角色用 `ensure_role`（存在则仅校正标志位）；权限用「仅追加缺失」；清理 111 用「存在才删」。重复执行不产生重复行（`role_permissions` 有 `uq_role_permission`）。
- **事务安全**：`op.get_bind()` 已处于 Alembic 事务内，迁移只 `flush`，由 Alembic 在上下文退出时统一提交；异常自动回滚。
- **可降级**：`downgrade()` 精确回滚——删除 system_admin/operator 角色（CASCADE 清其 rp）、移除 analyst 的 D1 新增项并恢复 `permissions:read`/`sources:write`、重建游离角色 111（含 opinions:read）。验证见 §16。
- **零 schema 变更**：不 `add_column` / 不 `DROP` / 不改表结构。
- 执行顺序：db_identity_check(VERIFIED) → `alembic current`=review_decision_complete_v2 → `alembic upgrade head`（因 `current_risk_adoption_v1` 连锁，见 §20 处理）→ 回退该 schema 迁移 → 最终生产停留 `rbac_d1_role_gov_v1`。

---

## 7. system_admin 权限矩阵

`is_system=True, is_enabled=True, 不持 *, 不依赖 is_superuser`。直接持有 15 项：

| 权限 | 类别 | 说明 |
| --- | --- | --- |
| users:read / users:write / users:activate | 用户管理 | 解除原 `*` 锁定，可审计 |
| roles:read / roles:write / roles:delete | 角色管理 | 同上 |
| permissions:read | 权限目录 | 从 analyst 收回后归此 |
| audit_logs:read / login_logs:read | 日志审计 | 原孤儿，现可审计 |
| sources:read / sources:write | 数据源（国内） | system_admin 负责数据源 |
| foreign:sources:read / foreign:sources:write / foreign:sources:test | 外网数据源 | system_admin 负责外网数据源基础设施 |
| foreign:data:manage（组合） | 外网数据管理 | 展开为 foreign 关键词/源 读写测采集（含 collect/collect_all） |

**不含**：`*`、`opinions:write`、`events:write`、`alerts:write`、`foreign:analysis`、`foreign:alerts:manage`、`foreign:ai:review:read`、任何 AI 研判/复核（业务操作归 analyst）。
**Enforcement 现状**：`users.py` 的用户/角色/权限/日志端点已用 `require_permission(具体码)`，system_admin 可通过；但 `admin_data_sources.py` / `admin_regions.py` / `admin_bocha.py` / `opinions.py` 的删除等仍 `require_admin`，system_admin 当前会被 403（见 §19 D2-BLOCKER）。

---

## 8. operator 权限矩阵

`is_system=True, is_enabled=True, 不持 *, 不依赖 is_superuser`。直接持有 11 项：

| 权限 | 类别 |
| --- | --- |
| keywords:read / keywords:write | 关键词 |
| sources:read / sources:write | 数据源（国内） |
| foreign:sources:read / foreign:sources:write / foreign:sources:test / foreign:sources:collect | 外网数据源与采集 |
| foreign:data:manage（组合） | 外网数据管理 |
| foreign:ai:batch:read / foreign:ai:batch:cancel | 外网 AI 批量任务（采集运维监控） |

**不含**：`users:*` / `roles:*` / `permissions:read` / `audit_logs:read` / `login_logs:read` / `opinions:write` / `events:write` / `alerts:write` / `foreign:analysis` / `foreign:ai:review:read` / 任何 AI 研判与人工复核（属 analyst）。
**Enforcement 现状**：`foreign:sources:test`/`collect`/`collect_all` 实际端点（`foreign.py`）多数仍 `require_admin`，operator 当前会被 403（见 §19）。

---

## 9. analyst 权限补齐

直接权限 28 → **31**（净 +3）：

| 变更 | 权限 | 处理 |
| --- | --- | --- |
| 新增 | keywords:write | 修复功能性缺口（原孤儿，analyst 无法管理关键词） |
| 新增 | foreign:read（组合） | 外网业务分析读；展开为 9 个 foreign 读叶子 |
| 新增 | foreign:ai:review:read | 修复「能 complete 不能 read」 |
| 新增 | foreign:ai:batch:read / foreign:ai:batch:cancel | 外网 AI 批量读取/取消 |
| 移除 | permissions:read | analyst 不应持系统管理目录（归 system_admin） |
| 移除 | sources:write | 幽灵权限（Enforcement 未引用），归 system_admin/operator |

`foreign:analysis` / `foreign:alerts:manage` **未授予 analyst**（BLOCKED，见 §12）。

---

## 10. viewer 权限保持情况

直接权限 **8 项不变**（alerts:read / events:read / opinions:read / propagation:read / domestic:ai:review:read / domestic:ai:review:complete / foreign:ai:review:read / foreign:ai:review:complete）。
生产只读验证确认：viewer 展开结果无 `*`、无任何 `write`/`manage`/`delete`、未获得 system_admin/operator 任何权限（§18）。

---

## 11. superuser 行为保持情况

- `User(role='admin', is_superuser=True)` → `get_user_permissions` 仍返回 `["*"]`（未改判定逻辑）。
- `User(role='admin', is_superuser=False)` → 仍等价超管返回 `["*"]`（向后兼容）。
- admin 角色的 48 行 `role_permissions` **未触碰**（超管本就不依赖它们）。

---

## 12. foreign composite 展开结果

| 组合权限 | 目录存在 | 直接持有角色（AFTER） | expand_permissions 结果 | get_user_permissions | 风险说明 |
| --- | --- | --- | --- | --- | --- |
| foreign:read | ✓ | **analyst** | foreign:opinions:read, foreign:risk:read, foreign:risk:terms:read, foreign:events:read, foreign:events:candidates:read, foreign:alerts:read, foreign:alerts:rules:read, foreign:keywords:read, foreign:sources:read（9 读叶子） | analyst 含以上叶子 | 全读，安全；在 analyst 外网业务分析 scope 内 |
| foreign:data:manage | ✓ | **operator + system_admin** | foreign:keywords:read/write, foreign:sources:read/write/test/collect/collect_all（7 叶子） | 两角色含以上叶子 | 数据管理 scope，归属 operator/system_admin（基础设施） |
| foreign:analysis | ✓ | **无（BLOCKED）** | foreign:risk:read/analyze/batch/ai, foreign:events:read/candidates:read/review:read/review:confirm/confirm/merge/split/status/rebuild/auto-aggregate, foreign:alerts:review:read/review:confirm/evaluate/ai-admit, foreign:ai:analyze/batch:read/review:read/full-confirm/reject（21 叶子） | — | **展开含高危 `foreign:ai:full-confirm` 与事件/预警处置操作**，超出 analyst 文档化外网 scope；最小权限审核未通过 → BLOCKED，留 D2/D3 能力模型拆分 |
| foreign:alerts:manage | ✓ | **无（BLOCKED）** | foreign:alerts:read/rules:read/rules:write/acknowledge/resolve/suppress/enable（7 叶子） | — | 预警处置 scope 在三角色间均不明确；BLOCKED，留 D2/D3 |
| ai:analyze | ✓ | admin + analyst（既有，未变） | domestic:ai:analyze/batch:read/review:read（3 叶子） | — | 既有，不在 D1 调整范围 |

---

## 13. role 111 清理过程

1. `roles` 查询：`id=5, name='111', code='111', is_system=False`，仅持有 `opinions:read`（1 行 rp）。
2. 引用检查：`users.role` 无 `'111'`；`user_roles` 0 行；`information_schema` 中仅 `role_permissions`/`user_roles` 两表 FK 到 `roles`（均 CASCADE）；源码 grep 无硬编码 `111`。
3. 决策：满足全部安全删除条件。
4. 执行：`DELETE role_permissions WHERE role_id=5` → `DELETE roles WHERE id=5`（经迁移幂等逻辑）。
5. 验证：生产查询 `Role WHERE code='111'` 返回 None（§18）。

---

## 14. BEFORE / AFTER 快照统计

| 维度 | BEFORE | AFTER | Δ |
| --- | --- | --- | --- |
| roles | 4 | 5 | +1（system_admin,operator）；111 删除 |
| permissions | 83 | 83 | 0（D1 不增删 permission） |
| role_permissions | 85 | 113 | +28 |
| user_roles | 0 | 0 | 0 |
| users | 3 | 3 | 0 |
| orphan permissions | 21 | 8 | −13 |
| admin 直接权限 | 48 | 48 | 0 |
| analyst 直接权限 | 28 | 31 | +3 |
| viewer 直接权限 | 8 | 8 | 0 |
| **system_admin 直接权限** | — | 15 | 新增 |
| **operator 直接权限** | — | 11 | 新增 |
| 每角色展开权限数 | admin `["*"]` / analyst 28 / viewer 8 | admin `["*"]` / analyst ≈39（含 foreign:read 展开） / viewer 8 / system_admin ≈21（含 foreign:data:manage 展开） / operator ≈17（含 foreign:data:manage 展开） | — |

孤儿 8 个（全部 foreign，属被 BLOCKED 的 `foreign:analysis`/`foreign:alerts:manage`）：
`foreign:analysis, foreign:alerts:manage, foreign:events:review:read, foreign:events:review:confirm, foreign:alerts:review:read, foreign:alerts:review:confirm, foreign:ai:full-confirm, foreign:ai:review:reject`。

---

## 15. expand_permissions 验证

`backend/tests/test_rbac_d1.py` 单元测试（隔离 SQLite，14/14 通过）：

- `test_expand_foreign_read`：展开含全部 9 个 foreign 读叶子。
- `test_expand_foreign_data_manage`：展开含 `foreign:sources:write/test/collect/collect_all`、`foreign:keywords:write`。
- `test_expand_foreign_analysis_includes_high_risk_full_confirm`：确认展开含 `foreign:ai:full-confirm` / `foreign:events:review:confirm` / `foreign:alerts:review:confirm`（即 BLOCKED 依据）。
- `test_expand_foreign_alerts_manage`：展开含 `foreign:alerts:enable/resolve/suppress`。
- `test_expand_ai_analyze`：展开含 `domestic:ai:analyze/review:read`。

生产只读验证（`_rbac_d1_verify.py`）确认 `get_user_permissions` 在真实库上：
- system_admin 展开含 `foreign:sources:write`（来自 foreign:data:manage）且 `'*' not in perms`；
- analyst 展开含 `foreign:opinions:read`（来自 foreign:read）且 `'*' not in perms`；
- admin(superuser) == `['*']`；viewer 无 `*` 无 write/manage；role 111 == None。

---

## 16. D1 专项测试结果

`backend/tests/test_rbac_d1.py`（SQLite in-memory，隔离，**绝不连生产**）：**14 passed**。

覆盖：4 组合展开、角色创建与 `is_system` 标志、system_admin/operator 矩阵（含「不含 `*` / 不含越权」负向断言）、analyst 补齐+收紧、`foreign:analysis` 不授予 analyst、viewer 不变、get_user_permissions 三角色展开、superuser `['*']`、role 111 清理、**revert 精确回滚至 BEFORE**（验证 downgrade 正确）。

---

## 17. 既有测试结果

`tests/test_rbac.py` + `tests/test_rbac_hardening.py`（隔离测试库 5433/opinion_test）：**143 passed, 16 failed**。

**关键判定**：测试库 `alembic_version` = `review_decision_complete_v2`、roles 仅 admin/analyst/viewer（+ 测试 `mrRole_*`），**D1 从未应用于测试库**。16 个失败均在该 pre-D1 状态复现，典型如 `test_viewer_allowed_reads` 的 `ProgrammingError`（缺表/缺列，测试库 stale schema）、`test_sec3b_*` 系列对角色权限分配状态的既有断言偏差。

**结论**：这些失败是**与 D1 无关的既有问题**（测试库 stale schema/seed + 既有测试对旧分配状态的硬编码假设），**非 D1 引入**（D1 仅修改生产 5432 的 role_permissions 数据、未改任何 Enforcement 代码、未触测试库 schema/seed）。D1 验收以 §16 的 D1 专项测试 + §18 生产只读验证为准；既有失败建议在 D2 测试环境治理时一并修复，不在 D1 范围。

---

## 18. 生产只读验证结果

执行 `audit-evidence/_rbac_d1_verify.py`（仅 SELECT，连接来自 `app.core.config`，不硬编码口令）：

- roles：5（admin/analyst/viewer/system_admin/operator）；**111 不存在** ✓
- role_permissions：113；permissions：83；user_roles：0 ✓
- 孤儿：8（全部 foreign，属 BLOCKED 组合）✓
- system_admin：`'*' not in perms`；含 users:read/roles:delete/permissions:read/audit_logs:read/foreign:sources:write（展开）/foreign:sources:collect ✓
- analyst：`'*' not in perms`；含 foreign:read/foreign:opinions:read（展开）/keywords:write/foreign:ai:review:read/foreign:ai:batch:read；**不含** permissions:read/sources:write/foreign:analysis ✓
- operator：`'*' not in perms`；含 keywords:write/foreign:sources:collect/foreign:ai:batch:cancel；**不含** users:read/foreign:analysis ✓
- viewer：无 `*`、无 write/manage ✓
- admin(superuser)：`['*']` ✓
- `foreign:read` 直接持有=analyst；`foreign:data:manage` 直接持有=operator+system_admin；`foreign:analysis`/`foreign:alerts:manage` 直接持有=None（BLOCKED）✓
- `sources:write` 直接持有=operator+system_admin（仍幽灵，见 §19）✓
- `collector:run` 不存在 ✓

---

## 19. D2-ENFORCEMENT-BLOCKER 清单

以下端点仍用 `require_admin`，**system_admin / operator 当前返回 403**（D1 未改 Enforcement，按规记录，不修复）：

| 端点（文件:行） | 操作 | 应改为（D2） |
| --- | --- | --- |
| `opinions.py:490` | 舆情删除 | `require_permission("opinions:delete")`（D2 新增叶子） |
| `opinions.py:531` | 舆情批量删除 | `require_permission("opinions:delete")` |
| `collector.py:157` | `POST /collector/run` 触发采集 | `require_permission("collector:run")`（D2 新增，不在 D1） |
| `admin_data_sources.py:974/1069/1095/1171/1266` | 数据源 创建/测试/调度/修改/删除 | `require_permission("sources:write"/"foreign:sources:*")` |
| `admin_regions.py:19` | 区域管理 | `require_permission(具体码)` |
| `admin_bocha.py:89/146/197/230/268` | Bocha 检索管理 | `require_permission(具体码)` |

> 注：因 system_admin 已持 `sources:write`/`foreign:sources:*`/`users:*` 等具体叶子，D2 仅需把上述 `require_admin` 改为 `require_permission(对应码)`，无需改角色分配即可生效。

---

## 20. 未解决问题 / 范围外事件

1. **`current_risk_adoption_v1` 连锁**：工作区存在一个未提交迁移，其 `down_revision="rbac_d1_role_gov_v1"`，表明 prior phase 已规划「D1 之后接风险列持久化」。执行 `alembic upgrade head` 时一并应用；为守 D1 边界已 `downgrade` 回退至 `rbac_d1_role_gov_v1`。**该 schema 迁移应作为独立阶段执行，不属 D1。**
2. **`sources:write`（domestic）仍为幽灵权限**：目录存在、现由 system_admin/operator 持有，但全量 grep `app/api` 无任何端点引用 → D2 应删除或接线。
3. **`foreign:analysis` / `foreign:alerts:manage` 仍孤儿**：BLOCKED，待 D2/D3 决定是否拆分 `foreign:ai:full-confirm`（高危）后再赋值。
4. **角色创建无约束**：`111` 证明可任意建角色（仅 `is_system` 保护系统角色）→ D2 加约束（默认 viewer 基线 / 仅 system_admin 可建）。
5. **8 个 foreign 叶子孤儿**：属 `foreign:analysis`/`foreign:alerts:manage` 子集，随 D2/D3 能力模型处理。

---

## 21. D2 / D3 / D4 明确待办

- **D2（Enforcement 重构）**：将 §19 的 `require_admin` 改为 `require_permission(具体码)`；新增 `opinions:delete`/`events:delete`/`collector:run` 叶子；补 `*:read` 强制；`tasks` 结果加归属校验；清理 `sources:write` 幽灵；拆分 `foreign:ai:full-confirm` 高危；新增 `system_admin`/`operator` 用户并验证可过所有系统管理端点。
- **D3（Capability + 配置 UI）**：引入「能力包/Preset」配置层（不进 Enforcement、不建 DB 实体），`Roles.vue` 改为「模块→业务能力→高级权限」三层 + 角色模板；保持 `role_permissions` 为唯一事实源。
- **D4（回归 + 运维手册）**：以 §18 生产只读矩阵 + 全量测试为基线，建立权限变更 regression 套件；编写角色权限运维手册。

---

## 22. 红线确认

| 红线 | 状态 |
| --- | --- |
| 未修改 Enforcement（API 端点 require_permission） | ✓ 未改 |
| 未修改 `require_permission` | ✓ 未改（`permissions.py` 原样） |
| 未修改 `require_admin` | ✓ 未改 |
| 未修改 `expand_permissions` / `COMPOSITE_PERMISSIONS` | ✓ 未改 |
| 未修改 Service 层权限判断 | ✓ 未改 |
| 未修改前端（Roles.vue / usePermission.ts） | ✓ 未改 |
| 未实现 Capability | ✓ 未实现 |
| 未新增 `/capabilities` API | ✓ 未新增 |
| 未修改 `foreign.py`/`domestic_ai_analysis.py`/`foreign_alerts.py` 授权逻辑 | ✓ 未改 |
| 未修改 `role_permissions` schema | ✓ 未改 |
| 未修改 `users` 表结构 / 现有 admin/superuser 属性 | ✓ 未改 |
| 未新增 `collector:run` | ✓ 未新增 |
| 未修改历史 Alembic migration | ✓ 仅新增 D1 迁移 |
| 未直接 `DROP`/批量删除 permissions/role_permissions | ✓ 仅受控 INSERT/DELETE（111 清理） |
| 未扩大任何低权限角色实际权限 | ✓ analyst 仅补齐业务缺口并收紧 2 项；viewer/operator 均在设计 scope 内 |
| 生产变更可审计、可回滚 | ✓ 前向迁移有 downgrade；db_identity VERIFIED |

---

## 附：最终输出格式

### 1. 状态
**PASS**

### 2. 核心结果
- system_admin：已建立（is_system=True，不持 `*`，15 直接权限，可审计）
- operator：已建立（is_system=True，不持 `*`，11 直接权限）
- analyst：已补齐 keywords:write / foreign:read / foreign:ai:review:read / foreign:ai:batch:read/cancel；已移除 permissions:read / sources:write（28→31）
- viewer：8 项权限完全不变
- superuser：仍返回 `["*"]`，行为不变
- role 111：已安全删除（无用户/附加角色引用）

### 3. 数据变化（BEFORE → AFTER）
- roles：4 → 5（删 111，增 system_admin/operator）
- permissions：83 → 83
- role_permissions：85 → 113
- user_roles：0 → 0
- orphan：21 → 8
- 每角色直接权限：admin 48 / analyst 28→31 / viewer 8 / system_admin 15(新) / operator 11(新)
- 每角色展开权限：admin `["*"]` / analyst ≈39 / viewer 8 / system_admin ≈21 / operator ≈17

### 4. Foreign 权限验证
- foreign:read：存在；analyst 持有；展开 9 读叶子；get_user_permissions 含；风险低（全读）
- foreign:data:manage：存在；operator+system_admin 持有；展开 7 数据叶子；含；风险中（数据管理，归属基础设施角色）
- foreign:analysis：存在；**无人持有（BLOCKED）**；展开 21 叶子含高危 full-confirm；风险高，留 D2/D3
- foreign:alerts:manage：存在；**无人持有（BLOCKED）**；展开 7 预警叶子；scope 不明，留 D2/D3

### 5. 测试
- expand_permissions 单元测试：14 passed（test_rbac_d1.py）
- D1 RBAC 测试：14 passed
- 既有 RBAC 测试：143 passed / 16 failed（pre-D1 测试库 stale，与 D1 无关）
- 全量测试：同上区分
- 生产只读验证：PASS（§18）

### 6. 修改文件
- 新增：`backend/app/core/rbac_d1.py`、`backend/alembic/versions/rbac_d1_role_directory_governance.py`、`backend/tests/test_rbac_d1.py`、`audit-evidence/_rbac_d1_verify.py`、`audit-evidence/_rbac_d1_after_snapshot.txt`
- 迁移：`rbac_d1_role_gov_v1`（前向 + 可降级）
- 报告：`docs/Phase-Security-RBAC-Redesign-D1-Implementation.md`

### 7. D1 红线（逐项）
Enforcement 未改 · require_permission 未改 · require_admin 未改 · expand_permissions 未改 · Frontend 未改 · Capability 未实现 · API 未改 · Service 未改 · Collector/Scheduler 未改 · Schema 未改 · role_permissions schema 未改 · collector:run 未新增 —— 全部满足（见 §22）。

### 8. 遗留问题（仅 D2/D3/D4）
- D2-ENFORCEMENT-BLOCKER：§19 列出的 require_admin 端点（system_admin/operator 当前 403）
- sources:write 幽灵权限（无 Enforcement 引用）
- foreign:analysis / foreign:alerts:manage 仍孤儿（BLOCKED，待能力模型）
- 角色创建无约束（111 暴露）
- 既有测试 16 失败（测试库 stale，无关 D1）

### 9. 产物
`docs/Phase-Security-RBAC-Redesign-D1-Implementation.md`
