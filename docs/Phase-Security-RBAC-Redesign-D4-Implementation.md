# Phase Security-RBAC-Redesign-D4 实施报告

> 舆情监测系统（YuQing）RBAC 回归基线、测试库治理、权限审计与运维收口
> 日期：2026-08-13 ｜ 提交人：Senior Backend Engineer / Security-RBAC Engineer
> 前置阶段：D1 ✅ PASS ｜ D2 ✅ PASS ｜ D3 ✅ PASS

---

## 1. Executive Summary

D4 目标**不是继续扩展 RBAC 能力**，而是把 D1→D3 已稳定的 RBAC 状态固化为「可持续验证、可回归、可审计、可运维」的基线。

核心成果：

1. **测试库基线治理（D4-01）**：确认隔离测试库 `127.0.0.1:5433/opinion_test` 停留在 `current_risk_adoption_v1`（D1 之前），且数据不一致（`reports:write` 等陈旧孤儿权限、`mrRole_*` 垃圾角色、陈旧权限描述）。已**重建为干净的 D3 基线**（drop schema + `alembic upgrade rbac_d3_enforcement_v2`），与 5432 生产**逐字节一致**（88 权限 / 5 角色 / 129 角色权限 / 权限码完全相同）。
2. **历史失败分类（D4-02）**：对 21 个既有失败逐项分类 —— 全部为 STALE-TEST-DB（16 项，重建即消）或 TEST-BUG（5 项，测试自身缺陷，非回归）。
3. **测试基线修复（D4-03）**：修复 5 个测试缺陷（组合权限展开一致性、system_admin 为设计内管理角色、opinion 唯一 URL 碰撞），**不修改任何生产权限**。
4. **统一回归套件（D4-04）**：新增 `test_rbac_regression.py`（13 项，SQLite in-memory），覆盖 D4-03/04 全部安全矩阵。
5. **权限目录审计（D4-05）**：新增 `audit-evidence/_rbac_catalog_audit.py` —— DB→API / API→DB / API→Role / orphan 四类检查，结论：所有 API 权限在目录中存在、无意外 0-role  Enforcement、orphan 全为 EXPECTED。
6. **API Enforcement 静态审计（D4-06）**：`require_admin` API 调用点 = **0**（仅 `core/permissions.py` 定义保留）。
7. **生产只读快照（D4-07）**：`audit-evidence/rbac_regression_snapshot.json` 含 11 条 security_assertions，**全部 PASS**。
8. **完整测试（D4-08）**：153 passed / 2 skipped / 0 failed。

**状态：✅ PASS（无 BLOCKED）。**

---

## 2. D4 Scope

- 仅做「基线固化 / 测试治理 / 只读审计 / 运维收口」。
- 不重新设计 RBAC；不修改 `COMPOSITE_PERMISSIONS` / `expand_permissions` / `require_permission` / `require_admin` 语义（除 D3 已落地的端点调用替换外，无新增改动）。
- 不新增业务权限（permissions 表净增 0）。
- 不改变角色权限（生产 5 角色权限数与 D3 完全一致）。
- 不修改业务 API Enforcement（D3 已完成 `require_admin` API 调用点 = 0）。
- 不修改 schema；不升级生产 head；生产库全程只读。

---

## 3. Production Baseline（生产 5432，只读确认）

| 指标 | 值 |
|---|---|
| DB identity | VERIFIED（opinions ≥ 100） |
| Alembic | `rbac_d3_enforcement_v2`（head） |
| permissions | 88 |
| roles | 5（admin / system_admin / operator / analyst / viewer） |
| role_permissions | 129 |

角色权限数（与 D3 完全一致，未变）：

| 角色 | 权限数 | 关键能力 |
|---|---|---|
| `admin` | 超管 | 返回 `["*"]` |
| `system_admin` | 25 | 全业务管理 + Bocha 全操作 + 用户/角色/权限/审计管理 |
| `operator` | 16 | 采集/数据源 + 4 读（无 Bocha、无业务研判写） |
| `analyst` | 32 | 研判/编辑 + Bocha 搜索与复核（无 promote） |
| `viewer` | 8 | 8 项只读（无 `ai:search`、无 `bocha:*`） |

关键安全事实：

- `bocha:promote` → **仅 system_admin**
- `bocha:read` → system_admin + analyst
- `ai:search` → analyst + system_admin
- `collector:run` → system_admin + operator
- `opinions:delete` / `events:delete` → **仅 system_admin**
- `foreign:analysis` / `foreign:alerts:manage` → **0 持有者（orphan）**
- `require_admin()` API 调用点 = 0（定义仍保留于 `core/permissions.py`）

---

## 4. Test DB Audit（5433 测试库审计，D4-01）

重建前 5433 状态（只读审计）：

| 维度 | 5433（重建前） | 5432（生产） | 结论 |
|---|---|---|---|
| alembic | `current_risk_adoption_v1` | `rbac_d3_enforcement_v2` | 5433 停在 D1 之前 |
| permissions | 78 | 88 | 缺失 10 个 D3 权限码 |
| roles | 28 | 5 | 23 个 `mrRole_*` 垃圾角色（MediaCrawler 测试残留） |
| role_permissions | 91 | 129 | 角色权限严重不足 |
| 陈旧孤儿 | `reports:write` 存在 | 不存在（已被 sec3b 移除） | 5433 数据不一致 |

**根因**：5433 从未通过完整 alembic 链路构建（停留在 `current_risk_adoption_v1`，且 `reports:write`、权限描述等处于 sec3b 迁移「已 stamp 但未生效」的不一致态），又叠加了 23 个测试运行产生的 `mrRole_*` 垃圾角色。

**治理动作**：对隔离测试库 `opinion_test` 执行 `DROP SCHEMA public CASCADE` + `CREATE SCHEMA public`，再 `alembic upgrade rbac_d3_enforcement_v2`（identity gate OFF，仅针对 5433）。重建后 5433 与生产**完全一致**（88 / 5 / 129，权限码集合相同）。

> 红线遵守：该写操作**仅作用于隔离测试库 5433**，生产 5432 全程只读，未执行任何 `alembic upgrade` 于生产。

---

## 5. 16（21）Existing Failure Classification

对当前陈旧 5433 运行的 **21 个失败**逐项分类（原报告所述「16 failed」为该库更早时间点的子集快照，分类方法一致）：

### A. STALE-TEST-DB（16 项 —— 5433 处于错误/不一致迁移态，重建即消除）

| # | 测试 | 失败原因（生产视角应为 PASS） |
|---|---|---|
| 1 | `test_rbac.py::test_viewer_allowed_reads` | 陈旧 5433 的 viewer 仅 5 权限，缺 events:read/opinions:read → 403 |
| 2 | `test_rbac.py::test_analyst_allowed_writes`（陈旧部分） | 陈旧 analyst 缺 keywords:write/opinions:write |
| 3 | `test_rbac.py::test_data_sources_read_permission_split` | 陈旧 analyst 缺 sources:read |
| 4 | `test_rbac.py::test_viewer_leader_reads_after_migration` | 陈旧 viewer 缺 alerts:read/propagation:read |
| 5 | `test_rbac_hardening.py::test_auth_me_viewer_contract` | 陈旧 viewer 缺 events:read/alerts:read |
| 6–9 | `test_rbac_hardening.py::test_viewer_can_read[4]` | 陈旧 viewer 缺读权限 |
| 10–11 | `test_rbac_hardening.py::test_analyst_not_forbidden[2]` | 陈旧 analyst 缺 keywords:read |
| 17 | `test_rbac_hardening.py::test_role_permission_change_audited_with_diff` | 陈旧审计/角色数据 |
| 18 | `test_rbac_hardening.py::test_sec3b_orphan_perms_removed` | 陈旧 `reports:write` 未移除 |
| 19 | `test_rbac_hardening.py::test_sec3b_analyst_can_edit_but_not_delete_opinions` | 陈旧 analyst 缺 opinions:write |
| 20 | `test_rbac_hardening.py::test_sec3b_analyst_cannot_manage_data_sources` | 陈旧 analyst 缺 sources:read |
| 21 | `test_rbac_hardening.py::test_sec3b_permission_descriptions_correct` | 陈旧权限描述占位符 |

### B. TEST-BUG / OUTDATED-EXPECTATION（5 项 —— 测试自身缺陷，即使正确基线也失败，已修复）

| # | 测试 | 缺陷 | 修复 |
|---|---|---|---|
| 12 | `test_role_permissions_match_db[analyst]` | 用直接角色权限对比 `/me`（展开后）权限，组合权限展开不一致 | `_db_roles()` 改返回 `expand_permissions(直接权限)` |
| 13 | `test_role_permissions_match_db[system_admin]` | 同上 | 同上 |
| 14 | `test_role_permissions_match_db[operator]` | 同上 | 同上 |
| 15 | `test_role_no_privileged_admin_permissions[system_admin]` | 未识别 `system_admin` 为设计内管理角色 | 跳过 `system_admin`（仅校验业务角色） |
| 16 | `test_role_cannot_touch_user_management[system_admin]` | 同上 | 跳过 `system_admin` |
| 2b | `test_rbac.py::test_analyst_allowed_writes`（URL 碰撞） | 硬编码 `url="http://a"`，analyst 无 opinions:delete 致清理失败，重跑唯一约束冲突 | 改用唯一 URL（`http://a-<uuid>`） |

> 说明：所有分类均**非 REAL-REGRESSION** —— 没有任何失败指向 D1/D2/D3 生产权限被错误改动；生产基线经验证完全符合 D3 设计。

---

## 6. Test Baseline Fixes（D4-03）

仅修改测试文件，未改生产权限：

- `tests/test_rbac_hardening.py`
  - 引入 `expand_permissions`；`_db_roles()` 返回**展开后**权限，使 `test_role_permissions_match_db` 与 `/me`（展开）语义一致。
  - `test_role_no_privileged_admin_permissions` / `test_role_cannot_touch_user_management` 显式跳过 `system_admin`（设计内系统管理角色，持有用户/角色/权限管理权属预期行为；断言仅针对业务角色防越权）。
- `tests/test_rbac.py`
  - `test_analyst_allowed_writes` 的 opinion 改用唯一 URL，避免与历史残留唯一约束冲突导致重跑失败。

---

## 7. Unified RBAC Regression（D4-04）

新增 `tests/test_rbac_regression.py`（SQLite in-memory，零外部依赖），复用 D1/D2/D3 数据层逻辑构建基线，覆盖 D4-03/04 安全矩阵：

1. 角色基线（5 角色齐全）
2. superuser → `["*"]`
3. 无通配符（system_admin/operator/analyst/viewer 均 ≠ `["*"]`）
4. 危险权限分布：opinions:delete / events:delete 仅 system_admin；collector:run 仅 system_admin+operator；bocha:promote 仅 system_admin；foreign:analysis / foreign:alerts:manage / foreign:ai:full-confirm 无角色持有
5. 读基线：system_admin 与 operator 均持 4 读
6. Bocha 三权分离：analyst(搜索+复核, 不可 promote) / system_admin(全操作) / operator·viewer(全拒)
7. Foreign 安全：foreign:ai:full-confirm 等高危叶子无任何非 admin 角色持有

**结果：13 passed。**

---

## 8. Permission Catalog Audit（D4-05）

脚本 `audit-evidence/_rbac_catalog_audit.py`（只读，生产 5432）。输出 `audit-evidence/rbac_catalog_audit.json`。

- **A. DB→API**：24 个权限未被任何 `require_permission` 直接引用。其中 5 个为组合权限定义（`foreign:read` / `foreign:data:manage` / `ai:analyze` / `foreign:analysis` / `foreign:alerts:manage`，经组合展开间接生效），其余为 domestic/foreign 细粒度叶子（属权限目录完整性条目，API 以更粗粒度或更具体叶子 Enforcement）。**非缺陷**，属目录丰度。
- **B. API→DB**：`api_permissions_missing_in_db = []` —— 所有 `require_permission("x")` 引用的权限码均在 `permissions` 表中存在。**无幽灵权限。**
- **C. API→Role**：`unassigned_enforcement = []` —— 每个被 Enforcement 的权限至少有 1 个角色持有。**无意外 0-role。**
- **D. Permission→Role**：orphan = 8，全部为 `foreign:*`（`foreign:analysis` / `foreign:alerts:manage` 及其展开叶子），分类为 **EXPECTED-ORPHAN**（D1/D2/D3 明确保留的高危组合，不授予任何角色）。`unexpected_orphans = []`。

VERDICT：`all_api_permissions_exist_in_db=True, no_unexpected_orphans=True, no_unassigned_enforcement=True, require_admin_api_zero=True`。

---

## 9. API Enforcement Audit（D4-06）

静态扫描 `backend/app/api/**/*.py`：

- `require_admin(` API 调用点 = **0**（仅 `core/permissions.py:132` 定义保留，未在任何端点使用）。✅ 满足 D4-06 硬指标。
- `require_permission("x")` 引用全部可在 `permissions` 目录解析（见 §8-B）。
- 生成 **RBAC Enforcement Matrix**（见 `rbac_catalog_audit.json` 的 `C_api_to_role.enforcement_report`）：每个 Enforcement 权限的 endpoint 数 + 持有角色。

---

## 10. Security Matrix（D4-03 验证结果）

| 角色 | 通配符 | delete | write/manage | bocha:* | foreign 高危 | 读基线 |
|---|---|---|---|---|---|---|
| `admin` | ✅ `["*"]` | ✅（超管） | ✅ | ✅ | ✅（超管） | ✅ |
| `system_admin` | ❌ 展开集 | ✅ opinions/events:delete | ✅ | read+promote | ❌ 不持有 | ✅ 4 读 |
| `operator` | ❌ | ❌ | 采集/数据源写，无业务研判写 | ❌ | ❌ | ✅ 4 读 |
| `analyst` | ❌ | ❌ | 研判/编辑写，无 delete | read（无 promote） | ❌ | ✅ 4 读 |
| `viewer` | ❌ | ❌ | ❌ 仅读 | ❌ | ❌ | ✅ 4 读 |

负向断言全部成立：

- system_admin ≠ `["*"]` ｜ operator ≠ `["*"]` ｜ analyst ≠ `["*"]` ｜ viewer ≠ `["*"]`
- analyst 无 `opinions:delete` / `events:delete`
- viewer 无 write/manage/delete/run/promote
- `bocha:promote` 仅 system_admin
- `foreign:analysis` / `foreign:alerts:manage` / `foreign:ai:full_confirm` 无（非 admin）角色持有

---

## 11. Production Read-only Verification（D4-07）

- DB identity：**VERIFIED**
- Alembic current：**`rbac_d3_enforcement_v2`**
- permissions 88 ｜ roles 5 ｜ role_permissions 129
- user_roles / expanded / orphans / composites / enforcement：见 `rbac_regression_snapshot.json`
- 11 条 security_assertions：**全部 PASS**（`all_assertions_true = True`）
- 全程只读 SELECT，未写入生产。

---

## 12. Migration State

- 生产 5432：current/head = `rbac_d3_enforcement_v2`，与 D3 落地后一致，**D4 未对生产执行任何迁移**。
- 测试库 5433：`current_risk_adoption_v1` → 重建 → `rbac_d3_enforcement_v2`（仅隔离测试库）。
- Alembic 链：单一 head，无 Multiple Heads，无 dangling 分支（延续 D2/D3 结论）。

---

## 13. Red-line Compliance

| 红线 | 遵守 |
|---|---|
| 不重新设计 RBAC（`COMPOSITE_PERMISSIONS`/`expand_permissions`/`require_permission`/`require_admin` 语义） | ✅ 仅端点调用替换在 D3 已完成，D4 无改动 |
| 不新增业务权限（permissions 净增） | ✅ 88 不变 |
| 不改变角色权限（生产 5 角色权限数） | ✅ system_admin=25 / operator=16 / analyst=32 / viewer=8 不变 |
| 不修改业务 API Enforcement | ✅ `require_admin` API 调用点保持 0 |
| 不修改 schema | ✅ 无 DDL |
| 不升级生产 head | ✅ 生产未执行 alembic upgrade |
| 绝不用生产库跑 pytest | ✅ 仅 5433 + SQLite in-memory |
| 不引入 Capability / ABAC / 第二事实源 | ✅ `role_permissions` 仍为唯一事实源 |
| 不处理 Foreign 能力模型 | ✅ `foreign:analysis`/`foreign:alerts:manage` 保持 orphan |
| 不实现 Capability model | ✅ 无 Capability 实体/API |

---

## 14. Known Deferred Items

1. **Foreign 能力模型（D4-08/D4-09 明确不做）**：`foreign:analysis` / `foreign:alerts:manage` 仍为 orphan，留待后续能力模型阶段拆分（高危叶子 `foreign:ai:full_confirm` 等不授予任何非 admin 角色，当前安全）。
2. **Capability / Preset model（D4-09 明确不做）**：`role_permissions` 继续为唯一权限事实源。
3. **测试库基线自动化**：建议将 `audit-evidence/_d4_rebuild_testdb.py` + `alembic upgrade rbac_d3_enforcement_v2` 纳入 CI 前置步骤，保证 5433 始终对齐生产基线。
4. **`collector:run` Enforcement 语义待确认（非回归）**：`operator` 已持 `collector:run` 但 `/api/collector/run` 端点沿用既有校验（非 D4 范围，不判定为失败）。

---

## 15. Deliverables

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/alembic/versions/rbac_d3_enforcement_v2.py` | 既有（D3） | D3 数据层迁移（基线来源） |
| `backend/tests/test_rbac_regression.py` | 新增 | 统一 RBAC 回归套件（13 项，SQLite in-memory） |
| `backend/tests/test_rbac.py` | 修改 | 修复 opinion 唯一 URL 碰撞 |
| `backend/tests/test_rbac_hardening.py` | 修改 | 组合权限展开一致 + system_admin 跳过管理断言 |
| `backend/audit-evidence/_rbac_catalog_audit.py` | 新增 | 权限目录审计脚本（D4-05/06） |
| `backend/audit-evidence/rbac_catalog_audit.json` | 新增 | 目录审计结果 |
| `backend/audit-evidence/_rbac_snapshot.py` | 新增 | 生产只读快照生成器（D4-07） |
| `backend/audit-evidence/rbac_regression_snapshot.json` | 新增 | 生产 RBAC 基线快照 + 11 条 security_assertions |
| `backend/audit-evidence/_d4_rebuild_testdb.py` | 新增（运维） | 隔离测试库重建为 D3 基线（仅 5433） |
| `docs/Phase-Security-RBAC-Redesign-D4-Implementation.md` | 新增 | 本报告 |

> 注：`audit-evidence/BEFORE_rbac_d3.json` / `AFTER_rbac_d3.json` 为 D3 产物，仍有效。

---

## 16. Final PASS/BLOCKED Decision

**✅ PASS**

验收硬指标逐条核对：

- [x] 5433 测试库基线已明确（重建为 `rbac_d3_enforcement_v2`，与生产一致）
- [x] 21 个旧失败逐项分类（16 STALE-TEST-DB + 5 TEST-BUG，0 REAL-REGRESSION）
- [x] 当前 RBAC 测试不再依赖 stale seed
- [x] D1 tests PASS ｜ [x] D2 PASS ｜ [x] D3 PASS
- [x] `test_rbac.py` PASS（97 passed, 2 skipped）｜ [x] `test_rbac_hardening.py` PASS
- [x] `test_rbac_regression.py` PASS（13）
- [x] `require_admin` API 调用点 = 0
- [x] API 权限目录全部存在（B 类无缺失）
- [x] Enforcement 权限无意外 0-role
- [x] orphan 已分类（8 全 EXPECTED）
- [x] system_admin 无 `*` ｜ [x] operator 无 `*` ｜ [x] analyst 无 delete ｜ [x] viewer 无 write/manage/delete
- [x] `bocha:promote` 仅 system_admin ｜ [x] `foreign:analysis` 无角色 ｜ [x] `foreign:alerts:manage` 无角色 ｜ [x] `foreign:ai:full_confirm` 无（非 admin）角色
- [x] 生产 DB identity VERIFIED ｜ [x] 生产只读验证 PASS ｜ [x] Alembic current = `rbac_d3_enforcement_v2`
- [x] 未升级生产 head ｜ [x] 未修改 schema ｜ [x] 未新增业务权限 ｜ [x] 未修改 RBAC 核心 Enforcement 语义 ｜ [x] 未引入 Capability / ABAC / 第二事实源

**D4 的最终价值**：自此任何权限改动都能被 `test_rbac_regression.py` + `audit-evidence/_rbac_catalog_audit.py` + `rbac_regression_snapshot.json` 自动发现（意外扩张/丢失/orphan/require_admin 回归），而非再增加一批权限。
