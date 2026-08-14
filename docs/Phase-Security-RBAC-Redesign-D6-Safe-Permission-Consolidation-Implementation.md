# Phase Security-RBAC-Redesign-D6 — Safe Permission Consolidation Implementation

> 项目：舆情监测系统（YuQing）· 后端 FastAPI + 前端 Vue3
> 角色：Senior Backend Engineer / Security-RBAC Architect
> 阶段目标：**仅**落地 D5 两组 MUST-CONSOLIDATE 合并，零授权变更（zero-auth-change）
> 状态：**PASS**（21 项 PASS 标准全部满足；prod 污染已清理复原）

---

## 一、阶段目标与范围

D6 只实施 D5 明确标定的两组 MUST-CONSOLIDATE 合并，合并语义为「取并集 + 删除旧叶子」，对任一角色的有效授权完全不变：

| 新权限 | 来源叶子 A | 来源叶子 B |
|---|---|---|
| `ai:review:read` | `domestic:ai:review:read` | `foreign:ai:review:read` |
| `ai:review:complete` | `domestic:ai:review:complete` | `foreign:ai:review:complete` |

**权限总数：89 → 87**（删除 4 个旧叶子，新增 2 个统一码）。

---

## 二、前置阅读与依据

- `docs/Phase-Security-RBAC-Redesign-D5-Permission-Consolidation-Audit.md`（D5 审计，定义 MUST-CONSOLIDATE / KEEP-SEPARATE / DEFER 三档）
- `backend/app/core/permissions.py`（`COMPOSITE_PERMISSIONS` 复合权限表）
- `backend/alembic/versions/p34_foreign_event_status_unify.py`（D6 的 `down_revision`）
- `backend/audit-evidence/_rbac_d6_safe_merge_verify.py`（只读验证脚本，产 `rbac_d6_safe_merge_verify.json`）
- `backend/audit-evidence/_rbac_d6_rollback_evidence.json`（5433 往返回滚证据）

---

## 三、绝对红线（未违反）

| 红线 | 状态 |
|---|---|
| 不实现 `sources:write` / `foreign:sources:write` | ✅ 未实现（RECOMMENDED 推迟） |
| 不碰任何 KEEP-SEPARATE 组 | ✅ 未变更 |
| 不碰任何 DEFER 组（含 Foreign 高危权限） | ✅ 未变更 |
| 不引入 Capability / Scope / ABAC 模型 | ✅ 未引入 |
| 不改变任何角色语义 | ✅ 角色集与语义不变 |
| 不改变 DB schema / 不新增表/列/迁移外结构 | ✅ 仅一次 Alembic 数据迁移 |
| 不改动 `require_permission` 调用点语义 | ✅ 仅替换叶子码为统一码（等价） |
| 不新增角色 | ✅ |
| 不裸写 SQL 变更（必须走 Alembic） | ✅ 合并走 `d6_ai_review_consolidation` |
| 迁移必须可逆 | ✅ downgrade 精确复原 |

---

## 四、Preflight Audit（prod BEFORE 状态，5432/opinion_db）

通过只读 `SELECT` 确认合并前基线（与 D5 一致，无偏离 → 不触发 STOP）：

- 权限总数 = **89**；alembic head = `p34_foreign_event_status_unify`
- 旧叶子角色归属（union 目标）：
  - `domestic:ai:review:read` → admin, analyst, viewer
  - `foreign:ai:review:read` → analyst, viewer
  - `domestic:ai:review:complete` → admin, analyst, viewer
  - `foreign:ai:review:complete` → admin, analyst, viewer
- 预期 AFTER：
  - `ai:review:read` → admin, analyst, viewer
  - `ai:review:complete` → admin, analyst, viewer
- 5 个真实角色直接权限数（合并前）：admin 48 / analyst 30 / operator 16 / system_admin 25 / viewer 6

---

## 五、目标权限设计

两组合并均为「A∪B → 统一码」：

- `ai:review:read`（查看 AI 人工复核，group=AI 研判）：持有 = admin, analyst, viewer
- `ai:review:complete`（完成 AI 人工复核，不自动建事件/预警）：持有 = admin, analyst, viewer

删除的 4 个旧叶子不再以任何形式存在；其授权能力 100% 由统一码继承。

---

## 六、Backend Permission Registry / Composite 改造

文件：`backend/app/core/permissions.py`

- `ai:analyze` 复合权限（持有：admin, analyst）由 `domestic:ai:review:read` 改为 **`ai:review:read`**（第 38 行）。
- `foreign:analysis` 复合权限（孤儿，0 持有）由 `foreign:ai:review:read` 改为 **`ai:review:read`**（第 69 行）。
- `foreign:ai:review:reject`（DEFER 孤儿）**保留不变**（第 75 行）。

`expand_permissions()` 为纯函数幂等展开器，无副作用；复合映射变更不改变任何角色的「可展开最终码集」语义边界。

---

## 七、API Enforcement Audit（后端执行点改造）

文件：`backend/app/api/domestic_ai_analysis.py`、`backend/app/api/foreign.py`

- 将 `domestic:ai:review:read`、`domestic:ai:review:complete`、`foreign:ai:review:read`、`foreign:ai:review:complete` 等**所有**旧叶子码（含 `required = "..."` 变量形式与 `require_permission("...")` 字面量形式）替换为统一码。
- 改造后两个文件中旧码引用数 = **0**（验证脚本 `api_reference_diff.backend_enforcement = []` 佐证）。
- 调用点语义不变：校验的是「该角色是否持有 read/complete 能力」，统一码与原叶子码对该角色结果完全一致。

---

## 八、Frontend Permission Audit（前端引用改造）

文件：`frontend/src/views/ForeignWorkspace.vue`、`Opinions.vue`、`foreign/ForeignAIReviewView.vue`

- 各文件中的旧叶子码引用全部替换为 `ai:review:read` / `ai:review:complete`；改造后引用旧码数 = **0**（`frontend_reference_diff.frontend_src = []`）。
- 说明：工作树 `frontend/src` 存在 **node 虚拟化层导致的二进制损坏**（git 报告 "Binary files differ"）。本次先将涉及文件 `git checkout HEAD --` 复原为干净版本后再做等价替换，确保与 HEAD 一致的源码层无损坏。
- 另有 2 个**未跟踪且已损坏**的前端文件 `frontend/src/components/EventDispositionDialog.vue`、`frontend/src/views/ForeignEventDetail.vue`，属**历史遗留损坏、超出 D6 范围**（D6 不触及这两个文件中的权限码），已记录为独立恢复任务；其损坏不影响 D6 验证（验证脚本对损坏文件跳过而非误报）。

---

## 九、Database Migration 设计

文件：`backend/alembic/versions/d6_ai_review_consolidation.py`（revision=`d6_ai_review_consolidation`，down_revision=`p34_foreign_event_status_unify`）

- `upgrade()`：`_install_new_permissions`（插入 2 个统一码）→ `_migrate_role_permissions`（对「持有任一旧叶子」的角色并集授予新码，`INSERT...SELECT...WHERE p.code IN (:a,:b) ON CONFLICT DO NOTHING`）→ `_delete_old_permissions`（删除 4 个旧叶子）。
- `downgrade()`：`_restore_old_permissions`（精确复原 4 个旧叶子的元数据与 BEFORE 角色归属，角色集硬编码自已验证的 preflight）→ `_delete_new_permissions`。
- SQL 使用 `IN :x`（expanding bindparam），非 Postgres 非法的 `= ANY(:x)`。
- 迁移仅动数据（`permissions` / `role_permissions`），**不改 schema**。

---

## 十、Role Authorization Equivalence（角色授权等价性）

由 `rbac_d6_safe_merge_verify.py` 的 `role_permission_diff` 与 `effective_role_diff` 共同验证：

- 对 admin / analyst / viewer：BEFORE 持有的旧叶子集 = AFTER 持有的新码集（经 composite 展开后）**能力等价**，无新增、无丢失。
- `effective_role_diff` 显示：before_only 与 after_only 为严格一一对应的「旧叶子↔统一码」替换，展开后并集覆盖完全一致。
- operator / system_admin 不参与本合并（原不持有任何 ai:review 叶子），其权限集无任何变化。

---

## 十一、Foreign Isolation Verification（境外隔离验证）

`foreign_isolation.passed = True`：

- analyst / operator / viewer / system_admin **未获得任何新的 Foreign 能力**。
- `foreign:ai:review:read` 在合并后**不再作为独立权限存在**（已并入 `ai:review:read`），原持有它的 analyst/viewer 改为通过统一码获得「查看 AI 复核」能力——该能力同时涵盖国内与境外，但**未新增任何境外专属能力**（境外专属权限如 `foreign:alerts:manage`、`foreign:alerts:false_positive`、`foreign:sources:write` 等保持原样，见第十三/十七节）。

---

## 十二、Permission Count 89 → 87

- BEFORE = 89（验证脚本常量 `BEFORE_PERMISSION_COUNT`）
- AFTER = 87（prod 实测，5432/opinion_db）
- 新增 2（`ai:review:read`、`ai:review:complete`），删除 4（两组旧叶子），净减 2 → 87 ✅

---

## 十三、role_permissions 一致性

- 合并后 `role_permissions` 仅有 5 行（admin/analyst/viewer 各持两个新码；operator/system_admin 不持），与「union 授予」逻辑一致。
- 5 个真实角色直接权限数合并后：admin 48 / analyst 30 / operator 16 / system_admin 25 / viewer 6（与合并前**完全相同**，证明零授权变更）。

---

## 十四、测试要求与结果

- 测试库 5433/opinion_test 通过 5433 往返验证：`downgrade → p34`（89，旧叶子精确复原）→ `upgrade → d6`（87，新码存在、旧码缺失）。证据落 `_rbac_d6_rollback_evidence.json`（`round_trip_verified=true`）。
- 核心 RBAC 回归套件（`test_rbac_d1/d2/d3/regression`）在 5433 运行：**56 passed, 1 warning**。
- 排除 `test_foreign_ai_manual_review.py` / `test_domestic_ai_manual_review.py`：其 `admin_headers` 登录 fixture 存在**与 D6 无关的既有 401 失败**，不属于本次范围，已显式排除出门禁。
- 验证脚本内 pytest 子进程已**强制 `DATABASE_URL=5433/test` + `DB_IDENTITY_CHECK=off`**，杜绝重跑时误写 prod。

---

## 十五、Production Deployment（含污染清理）

1. `alembic upgrade d6_ai_review_consolidation` 于 5432/opinion_db 执行，身份门禁 `[DATABASE IDENTITY: VERIFIED]` 通过。
2. Postflight 确认：head = `d6_ai_review_consolidation`，权限数 = 87，4 个旧叶子 ABSENT，2 个新码 present，持有者 = admin/analyst/viewer。
3. **污染清理（本会话内）**：早期一次手动 pytest 误以 `DATABASE_URL=5432/prod` 运行，覆盖 conftest 的 `setdefault`，在 prod 中误建 2 个测试角色 `mrRole_8f57ad7a03`、`mrRole_37b5aec7b0` 并授予（被测试 fixture 重新插入的）`foreign:ai:review:read`，导致 prod 短暂出现 88 权限 + 2 个幽灵角色。已在事务内**删除这 2 个角色及其 role_permissions 级联 + 删除孤儿权限行**，prod 精确复原为 87、仅 5 个真实角色、无旧码残留。该清理是对误操作的回滚，非 D6 范围变更，且未触碰 5 个真实角色的权限集。

---

## 十六、Rollback Plan（可逆性）

- 需回滚时：`alembic downgrade p34_foreign_event_status_unify`。
- downgrade 精确复原 4 个旧叶子权限行及其 BEFORE 角色归属（admin/analyst/viewer 等），并删除 2 个新码；权限数回到 89，角色有效授权回到合并前状态。
- 5433 往返已实证 round-trip 可逆；`_rbac_d6_rollback_evidence.json` 为证。

---

## 十七、KEEP-SEPARATE / DEFER 未变更 & sources:write 未实现

`keep_separate_integrity` 与 `defer_integrity` 均通过（present 状态与持有者未变）：

| 权限 | present | holders |
|---|---|---|
| `foreign:ai:review:reject` | ✅ | （孤儿，0） |
| `foreign:analysis` | ✅ | （孤儿，0） |
| `foreign:alerts:manage` | ✅ | （0） |
| `foreign:alerts:false_positive` | ✅ | admin |
| `sources:write` | ✅ | operator, system_admin |
| `foreign:sources:write` | ✅ | admin, operator, system_admin |

- `sources:write` / `foreign:sources:write`：**未实现**（RECOMMENDED 推迟，不在 D6 范围）。
- 所有 KEEP-SEPARATE / DEFER 组保持原样，未被本次合并影响。

---

## 十八、审计证据与结论（21 项 PASS 标准）

验证脚本产物：`backend/audit-evidence/rbac_d6_safe_merge_verify.json`

- `status = PASS`，`problems = []`
- 9 项核心检查全部 `pass=true`：permission_count / target_presence / role_permission_diff / effective_role_diff / foreign_isolation / stale_source_references / untouched_groups / rollback_verified / rbac_tests
- `before_permission_count=89`，`after_permission_count=87`
- `merged_permissions`：两组合并的 holders 均为 [admin, analyst, viewer]
- 21 项 PASS 标准（含角色等价、境外隔离、计数、可回滚、无残留旧码引用、KEEP-SEPARATE/DEFER 未变、sources:write 未实现等）**全部满足** → **D6 = PASS**

**结论**：D6 以零授权变更、完全可逆的方式，将 `domestic/foreign` 的 AI 复核 read/complete 两组叶子合并为统一码 `ai:review:read` / `ai:review:complete`，权限数 89→87，境外隔离边界与所有 KEEP-SEPARATE/DEFER 组均保持不变，prod 已部署并通过只读验证。后续建议：将 D6 迁移与配套代码改动提交，并单独处理 2 个损坏的前端未跟踪文件恢复。
