# Phase Security-RBAC-Redesign-D5
# Permission Catalog Consolidation Audit（权限目录归并审计）

> 舆情监测系统（YuQing）｜ 纯只读审计阶段 ｜ 日期：2026-08-14
> 前置阶段：D1 ✅ PASS ｜ D2 ✅ PASS ｜ D3 ✅ PASS ｜ D4 ✅ PASS
> 执行人：Senior Backend Engineer / Security-RBAC Architect

---

## 1. Executive Summary

D5 是**纯只读审计**，目标不是修改 RBAC，而是判断当前 88→**89** 个权限中，
因「国内 / 外网」业务域拆分而产生的**过细、重复、语义重叠**权限，
并给出「应该怎么归并」的设计建议（不执行归并）。

**最关键发现**：

1. **基线漂移（Baseline Drift）**：D4 文档记录生产为 `permissions=88 / alembic=rbac_d3_enforcement_v2`，
   但**当前生产实际为 `permissions=89 / alembic=p34_foreign_event_status_unify`**。原因是 D4 之后生产落地了 `foreign_alert_disposition_v1`（Phase 15-C1，新增 `foreign:alerts:false_positive`，仅授予 admin）
   与 `p34_foreign_event_status_unify`（统一事件状态枚举，不改权限）。审计**针对实时生产**执行，结果有效；
   建议事后刷新 D4 基线文档。此漂移不影响 D4 的 PASS 结论（D4 在其时点正确）。
2. **真实架构与 D5 示例假设不同**：外网（foreign）能力当前几乎全部为 **admin-only 或孤立（0 业务角色持有）**；
   国内（domestic）能力 + 无前缀核心能力才授予 analyst/operator。这是**刻意的授权边界**，不是简单的命名重复。
3. **`require_admin` API 调用点 = 0**（与 D4 一致），API Enforcement 全部可在权限目录解析。
4. **归并结论**：19 个候选归并组中 —— **MUST-CONSOLIDATE=2、RECOMMENDED=1、KEEP-SEPARATE=11、DEFER=5**。绝大多数为 KEEP-SEPARATE，因合并会扩大业务角色至外网域（BLOCKED-BY-SCOPE-DIFFERENCE）。

**状态：✅ PASS（审计完整；基线漂移已记录，非阻断）。**

---

## 2. Scope / Red Lines

**范围**：读取源码 / 生产库（SELECT）/ 迁移 / 测试 / 前端权限配置；执行静态扫描；
生成只读审计脚本（`_rbac_consolidation_audit.py`）与 JSON/Markdown 报告。

**红线（全部遵守，零违反）**：

- ❌ 禁止修改生产库 / 5432 权限 / role_permissions / permissions / roles / users
- ❌ 禁止新增 / 删除 / 修改 Alembic migration（未执行 upgrade/downgrade）
- ❌ 禁止修改 `COMPOSITE_PERMISSIONS` / `expand_permissions` / `require_permission` / `require_admin`
- ❌ 禁止修改任何业务 API Enforcement / Collector / Scheduler / AI / Foreign 逻辑 / 前端权限逻辑
- ❌ 禁止在本阶段实施任何权限归并（仅建议）
- ❌ 禁止引入 Capability / ABAC / Scope engine

---

## 3. D1-D4 Baseline（含漂移校正）

| 维度 | D4 文档记录 | 当前生产实测（D5 审计目标） |
|---|---|---|
| Alembic | `rbac_d3_enforcement_v2` | `p34_foreign_event_status_unify` |
| permissions | 88 | **89** |
| roles | 5 | 5（admin/system_admin/operator/analyst/viewer） |
| 新增权限 | — | `foreign:alerts:false_positive`（admin-only，Phase 15-C1） |
| role_permissions | 129（D4 时） | 需以实时库为准（见 §4） |
| require_admin API 站点 | 0 | **0**（D5 重扫确认） |

> D4 安全矩阵（system_admin=25/operator=16/analyst=32/viewer=8/admin=["*"]）在 D5 实测中仍成立，
> 因新增的 `foreign:alerts:false_positive` 仅授予 admin（超管），不改变任何非超管角色权限数。

---

## 4. Current Permission Catalog

生产 5432 实测共 **89** 个权限，完整目录如下（按 code 排序）。
`domain` 列：core=无前缀核心能力；domestic=国内；foreign=外网。

| # | code | domain | resource | action | group | roles |
|---|---|---|---|---|---|---|
| 1 | `ai:analyze` | core | ai | analyze | AI能力 | admin, analyst |
| 2 | `ai:manage` | core | ai | manage | AI能力 | admin |
| 3 | `ai:search` | core | ai | search | AI能力 | admin, analyst, system_admin |
| 4 | `alerts:read` | core | alerts | read | 预警管理 | analyst, operator, system_admin, viewer |
| 5 | `alerts:write` | core | alerts | write | 预警管理 | analyst |
| 6 | `audit_logs:read` | core | audit_logs | read | 审计 | system_admin |
| 7 | `bocha:promote` | core | bocha | promote | Bocha | system_admin |
| 8 | `bocha:read` | core | bocha | read | Bocha | analyst, system_admin |
| 9 | `collector:run` | core | collector | run | 采集 | operator, system_admin |
| 10 | `domestic:ai:analyze` | domestic | domestic | ai_analyze | 国内 AI | admin, analyst |
| 11 | `domestic:ai:batch:cancel` | domestic | domestic | batch_cancel | 国内 AI | admin, analyst |
| 12 | `domestic:ai:batch:read` | domestic | domestic | batch_read | 国内 AI | admin, analyst |
| 13 | `domestic:ai:full-confirm` | domestic | domestic | full_confirm | 国内 AI | admin, analyst |
| 14 | `domestic:ai:review:complete` | domestic | domestic | review_complete | 国内 AI | admin, analyst, viewer |
| 15 | `domestic:ai:review:read` | domestic | domestic | review_read | 国内 AI | admin, analyst, viewer |
| 16 | `domestic:ai:review:reject` | domestic | domestic | review_reject | 国内 AI | admin, analyst |
| 17 | `domestic:alerts:review:confirm` | domestic | domestic | alert_review_confirm | 国内 AI | admin, analyst |
| 18 | `domestic:alerts:review:read` | domestic | domestic | alert_review_read | 国内 AI | admin, analyst |
| 19 | `domestic:events:review:confirm` | domestic | domestic | event_review_confirm | 国内 AI | admin, analyst |
| 20 | `domestic:events:review:read` | domestic | domestic | event_review_read | 国内 AI | admin, analyst |
| 21 | `events:delete` | core | events | delete | 事件 | system_admin |
| 22 | `events:read` | core | events | read | 事件管理 | analyst, operator, system_admin, viewer |
| 23 | `events:write` | core | events | write | 事件管理 | analyst |
| 24 | `foreign:ai:analyze` | foreign | foreign | analyze | Foreign sources | admin |
| 25 | `foreign:ai:batch:cancel` | foreign | foreign | batch_cancel | 外网 AI | analyst, operator |
| 26 | `foreign:ai:batch:read` | foreign | foreign | batch_read | 外网 AI | analyst, operator |
| 27 | `foreign:ai:full-confirm` | foreign | foreign | full_confirm | 外网 AI | (none/orphan) |
| 28 | `foreign:ai:review:complete` | foreign | foreign | review_complete | 外网 AI | admin, analyst, viewer |
| 29 | `foreign:ai:review:read` | foreign | foreign | review_read | 外网 AI | analyst, viewer |
| 30 | `foreign:ai:review:reject` | foreign | foreign | review_reject | 外网 AI | (none/orphan) |
| 31 | `foreign:alerts:acknowledge` | foreign | foreign | acknowledge | Foreign alerts | admin |
| 32 | `foreign:alerts:ai-admit` | foreign | foreign | ai-admit | Foreign sources | admin |
| 33 | `foreign:alerts:enable` | foreign | foreign | enable | Foreign alerts | admin |
| 34 | `foreign:alerts:evaluate` | foreign | foreign | evaluate | Foreign alerts | admin |
| 35 | `foreign:alerts:false_positive` | foreign | foreign | false_positive | Foreign alerts | admin |
| 36 | `foreign:alerts:manage` | foreign | foreign | manage | Foreign combined | (none/orphan) |
| 37 | `foreign:alerts:read` | foreign | foreign | read | Foreign alerts | admin |
| 38 | `foreign:alerts:resolve` | foreign | foreign | resolve | Foreign alerts | admin |
| 39 | `foreign:alerts:review:confirm` | foreign | foreign | alert_review_confirm | 外网 AI | (none/orphan) |
| 40 | `foreign:alerts:review:read` | foreign | foreign | alert_review_read | 外网 AI | (none/orphan) |
| 41 | `foreign:alerts:rules:read` | foreign | foreign | rules:read | Foreign alerts | admin |
| 42 | `foreign:alerts:rules:write` | foreign | foreign | rules:write | Foreign alerts | admin |
| 43 | `foreign:alerts:suppress` | foreign | foreign | suppress | Foreign alerts | admin |
| 44 | `foreign:analysis` | foreign | foreign | analysis | Foreign combined | (none/orphan) |
| 45 | `foreign:data:manage` | foreign | foreign | manage | Foreign combined | operator, system_admin |
| 46 | `foreign:events:auto-aggregate` | foreign | foreign | auto-aggregate | Foreign sources | admin |
| 47 | `foreign:events:candidates:read` | foreign | foreign | events:candidates:read | Foreign events | admin |
| 48 | `foreign:events:confirm` | foreign | foreign | events:confirm | Foreign events | admin |
| 49 | `foreign:events:merge` | foreign | foreign | events:merge | Foreign events | admin |
| 50 | `foreign:events:read` | foreign | foreign | events:read | Foreign events | admin |
| 51 | `foreign:events:rebuild` | foreign | foreign | events:rebuild | Foreign events | admin |
| 52 | `foreign:events:review:confirm` | foreign | foreign | event_review_confirm | 外网 AI | (none/orphan) |
| 53 | `foreign:events:review:read` | foreign | foreign | event_review_read | 外网 AI | (none/orphan) |
| 54 | `foreign:events:split` | foreign | foreign | events:split | Foreign events | admin |
| 55 | `foreign:events:status` | foreign | foreign | events:status | Foreign events | admin |
| 56 | `foreign:events:write` | foreign | foreign | write | Foreign sources | admin |
| 57 | `foreign:keywords:read` | foreign | foreign | read | Foreign sources | admin |
| 58 | `foreign:keywords:write` | foreign | foreign | write | Foreign sources | admin |
| 59 | `foreign:opinions:read` | foreign | foreign | read | Foreign sources | admin |
| 60 | `foreign:read` | foreign | foreign | read | Foreign combined | analyst |
| 61 | `foreign:risk:ai` | foreign | foreign | risk:ai | 外网风险 | admin |
| 62 | `foreign:risk:analyze` | foreign | foreign | risk:analyze | 外网风险 | admin |
| 63 | `foreign:risk:batch` | foreign | foreign | risk:batch | 外网风险 | admin |
| 64 | `foreign:risk:read` | foreign | foreign | risk:read | 外网风险 | admin |
| 65 | `foreign:risk:terms:read` | foreign | foreign | risk:terms:read | 外网风险 | admin |
| 66 | `foreign:sources:collect` | foreign | foreign | collect | Foreign sources | admin, operator |
| 67 | `foreign:sources:collect_all` | foreign | foreign | collect_all | Foreign sources | admin |
| 68 | `foreign:sources:read` | foreign | foreign | read | Foreign sources | admin, operator, system_admin |
| 69 | `foreign:sources:test` | foreign | foreign | test | Foreign sources | admin, operator, system_admin |
| 70 | `foreign:sources:write` | foreign | foreign | write | Foreign sources | admin, operator, system_admin |
| 71 | `keywords:read` | core | keywords | read | 关键词管理 | analyst, operator |
| 72 | `keywords:write` | core | keywords | write | 关键词管理 | analyst, operator |
| 73 | `login_logs:read` | core | login_logs | read | 审计 | system_admin |
| 74 | `opinions:delete` | core | opinions | delete | 舆情 | system_admin |
| 75 | `opinions:read` | core | opinions | read | 舆情管理 | analyst, operator, system_admin, viewer |
| 76 | `opinions:write` | core | opinions | write | 舆情管理 | analyst |
| 77 | `permissions:read` | core | permissions | read | 权限管理 | system_admin |
| 78 | `propagation:read` | core | propagation | read | 传播溯源 | analyst, operator, system_admin, viewer |
| 79 | `reports:export` | core | reports | export | 报告 | analyst |
| 80 | `reports:manage` | core | reports | manage | 报告 | admin, analyst |
| 81 | `reports:read` | core | reports | read | 报告 | analyst |
| 82 | `roles:delete` | core | roles | delete | 角色管理 | system_admin |
| 83 | `roles:read` | core | roles | read | 角色管理 | system_admin |
| 84 | `roles:write` | core | roles | write | 角色管理 | system_admin |
| 85 | `sources:read` | core | sources | read | 数据源 | analyst, operator, system_admin |
| 86 | `sources:write` | core | sources | write | 数据源 | operator, system_admin |
| 87 | `users:activate` | core | users | activate | 用户管理 | system_admin |
| 88 | `users:read` | core | users | read | 用户管理 | system_admin |
| 89 | `users:write` | core | users | write | 用户管理 | system_admin |

---

## 5. Domestic / Foreign Permission Inventory

domestic/foreign 域权限共 **58** 个，分布：

- `domestic:` = **11**
- `foreign:` = **47**

| code | domain | base(去域前缀) | resource | action | roles |
|---|---|---|---|---|---|
| `domestic:ai:analyze` | domestic | `ai:analyze` | domestic | ai_analyze | admin, analyst |
| `domestic:ai:batch:cancel` | domestic | `ai:batch:cancel` | domestic | batch_cancel | admin, analyst |
| `domestic:ai:batch:read` | domestic | `ai:batch:read` | domestic | batch_read | admin, analyst |
| `domestic:ai:full-confirm` | domestic | `ai:full-confirm` | domestic | full_confirm | admin, analyst |
| `domestic:ai:review:complete` | domestic | `ai:review:complete` | domestic | review_complete | admin, analyst, viewer |
| `domestic:ai:review:read` | domestic | `ai:review:read` | domestic | review_read | admin, analyst, viewer |
| `domestic:ai:review:reject` | domestic | `ai:review:reject` | domestic | review_reject | admin, analyst |
| `domestic:alerts:review:confirm` | domestic | `alerts:review:confirm` | domestic | alert_review_confirm | admin, analyst |
| `domestic:alerts:review:read` | domestic | `alerts:review:read` | domestic | alert_review_read | admin, analyst |
| `domestic:events:review:confirm` | domestic | `events:review:confirm` | domestic | event_review_confirm | admin, analyst |
| `domestic:events:review:read` | domestic | `events:review:read` | domestic | event_review_read | admin, analyst |
| `foreign:ai:analyze` | foreign | `ai:analyze` | foreign | analyze | admin |
| `foreign:ai:batch:cancel` | foreign | `ai:batch:cancel` | foreign | batch_cancel | analyst, operator |
| `foreign:ai:batch:read` | foreign | `ai:batch:read` | foreign | batch_read | analyst, operator |
| `foreign:ai:full-confirm` | foreign | `ai:full-confirm` | foreign | full_confirm | (none/orphan) |
| `foreign:ai:review:complete` | foreign | `ai:review:complete` | foreign | review_complete | admin, analyst, viewer |
| `foreign:ai:review:read` | foreign | `ai:review:read` | foreign | review_read | analyst, viewer |
| `foreign:ai:review:reject` | foreign | `ai:review:reject` | foreign | review_reject | (none/orphan) |
| `foreign:alerts:acknowledge` | foreign | `alerts:acknowledge` | foreign | acknowledge | admin |
| `foreign:alerts:ai-admit` | foreign | `alerts:ai-admit` | foreign | ai-admit | admin |
| `foreign:alerts:enable` | foreign | `alerts:enable` | foreign | enable | admin |
| `foreign:alerts:evaluate` | foreign | `alerts:evaluate` | foreign | evaluate | admin |
| `foreign:alerts:false_positive` | foreign | `alerts:false_positive` | foreign | false_positive | admin |
| `foreign:alerts:manage` | foreign | `alerts:manage` | foreign | manage | (none/orphan) |
| `foreign:alerts:read` | foreign | `alerts:read` | foreign | read | admin |
| `foreign:alerts:resolve` | foreign | `alerts:resolve` | foreign | resolve | admin |
| `foreign:alerts:review:confirm` | foreign | `alerts:review:confirm` | foreign | alert_review_confirm | (none/orphan) |
| `foreign:alerts:review:read` | foreign | `alerts:review:read` | foreign | alert_review_read | (none/orphan) |
| `foreign:alerts:rules:read` | foreign | `alerts:rules:read` | foreign | rules:read | admin |
| `foreign:alerts:rules:write` | foreign | `alerts:rules:write` | foreign | rules:write | admin |
| `foreign:alerts:suppress` | foreign | `alerts:suppress` | foreign | suppress | admin |
| `foreign:analysis` | foreign | `analysis` | foreign | analysis | (none/orphan) |
| `foreign:data:manage` | foreign | `data:manage` | foreign | manage | operator, system_admin |
| `foreign:events:auto-aggregate` | foreign | `events:auto-aggregate` | foreign | auto-aggregate | admin |
| `foreign:events:candidates:read` | foreign | `events:candidates:read` | foreign | events:candidates:read | admin |
| `foreign:events:confirm` | foreign | `events:confirm` | foreign | events:confirm | admin |
| `foreign:events:merge` | foreign | `events:merge` | foreign | events:merge | admin |
| `foreign:events:read` | foreign | `events:read` | foreign | events:read | admin |
| `foreign:events:rebuild` | foreign | `events:rebuild` | foreign | events:rebuild | admin |
| `foreign:events:review:confirm` | foreign | `events:review:confirm` | foreign | event_review_confirm | (none/orphan) |
| `foreign:events:review:read` | foreign | `events:review:read` | foreign | event_review_read | (none/orphan) |
| `foreign:events:split` | foreign | `events:split` | foreign | events:split | admin |
| `foreign:events:status` | foreign | `events:status` | foreign | events:status | admin |
| `foreign:events:write` | foreign | `events:write` | foreign | write | admin |
| `foreign:keywords:read` | foreign | `keywords:read` | foreign | read | admin |
| `foreign:keywords:write` | foreign | `keywords:write` | foreign | write | admin |
| `foreign:opinions:read` | foreign | `opinions:read` | foreign | read | admin |
| `foreign:read` | foreign | `read` | foreign | read | analyst |
| `foreign:risk:ai` | foreign | `risk:ai` | foreign | risk:ai | admin |
| `foreign:risk:analyze` | foreign | `risk:analyze` | foreign | risk:analyze | admin |
| `foreign:risk:batch` | foreign | `risk:batch` | foreign | risk:batch | admin |
| `foreign:risk:read` | foreign | `risk:read` | foreign | risk:read | admin |
| `foreign:risk:terms:read` | foreign | `risk:terms:read` | foreign | risk:terms:read | admin |
| `foreign:sources:collect` | foreign | `sources:collect` | foreign | collect | admin, operator |
| `foreign:sources:collect_all` | foreign | `sources:collect_all` | foreign | collect_all | admin |
| `foreign:sources:read` | foreign | `sources:read` | foreign | read | admin, operator, system_admin |
| `foreign:sources:test` | foreign | `sources:test` | foreign | test | admin, operator, system_admin |
| `foreign:sources:write` | foreign | `sources:write` | foreign | write | admin, operator, system_admin |

**观察**：11 个 `domestic:` 权限均有对应 `foreign:` 叶子（构成候选归并组）；
47 个 `foreign:` 权限中，多数无国内对应（外网专属能力，或高危复合叶子），自成 Foreign 能力域。

---

## 6. Permission → API Enforcement Matrix

静态扫描 `backend/app/api/**/*.py` 的 `require_permission("x")`，映射到方法+路径。
`require_admin(` API 站点 = **0**。下列仅列出候选归并组的 Enforcement 情况：

| base | 成员权限 | endpoint 数 | 直接 Enforcement 端点 |
|---|---|---|---|
| `ai:analyze` | `ai:analyze`, `domestic:ai:analyze`, `foreign:ai:analyze` | 7 | ? ?; POST /ai-analysis/batch; POST /ai-analysis/batch/preview; POST /batch; POST /batch/preview; POST /batch/{run_id}/retry-failed; POST /opinions/{opinion_id}/ai-analyze |
| `ai:batch:cancel` | `domestic:ai:batch:cancel`, `foreign:ai:batch:cancel` | 2 | POST /ai-analysis/batch/{run_id}/cancel; POST /batch/{run_id}/cancel |
| `ai:batch:read` | `domestic:ai:batch:read`, `foreign:ai:batch:read` | 4 | GET /ai-analysis/batch/{run_id}; GET /ai-analysis/batches; GET /batch/{run_id}; GET /batches |
| `ai:full-confirm` | `domestic:ai:full-confirm`, `foreign:ai:full-confirm` | 0 | (无直接引用) |
| `ai:review:complete` | `domestic:ai:review:complete`, `foreign:ai:review:complete` | 0 | (无直接引用) |
| `ai:review:read` | `domestic:ai:review:read`, `foreign:ai:review:read` | 1 | GET /results/{opinion_id} |
| `ai:review:reject` | `domestic:ai:review:reject`, `foreign:ai:review:reject` | 0 | (无直接引用) |
| `alerts:read` | `alerts:read`, `foreign:alerts:read` | 8 | GET /alert-auto-evaluation/status; GET /alert-runs; GET /records; GET /rules; GET /unread; GET /{alert_id}; GET /{alert_id}/actions |
| `alerts:review:confirm` | `domestic:alerts:review:confirm`, `foreign:alerts:review:confirm` | 0 | (无直接引用) |
| `alerts:review:read` | `domestic:alerts:review:read`, `foreign:alerts:review:read` | 0 | (无直接引用) |
| `events:read` | `events:read`, `foreign:events:read` | 11 | ? ?; GET /auto-aggregate/status; GET /event-actions; GET /event-runs; GET /{event_id}; GET /{event_id}/opinions |
| `events:review:confirm` | `domestic:events:review:confirm`, `foreign:events:review:confirm` | 0 | (无直接引用) |
| `events:review:read` | `domestic:events:review:read`, `foreign:events:review:read` | 0 | (无直接引用) |
| `events:write` | `events:write`, `foreign:events:write` | 7 | ? ?; POST /rebuild/{event_id}; POST /{event_id}/actions |
| `keywords:read` | `foreign:keywords:read`, `keywords:read` | 4 | ? ?; GET /categories; GET /keywords; GET /keywords/categories |
| `keywords:write` | `foreign:keywords:write`, `keywords:write` | 9 | ? ?; DELETE /keywords/{keyword_id}; DELETE /{keyword_id}; PATCH /keywords/{keyword_id}; POST /keywords; POST /keywords/bulk-status; POST /opinions/rescore; PUT /batch-toggle; PUT /{keyword_id} |
| `opinions:read` | `foreign:opinions:read`, `opinions:read` | 9 | ? ?; GET /opinions; GET /opinions/sources; GET /opinions/{opinion_id}; GET /opinions/{opinion_id}/detail; GET /opinions/{opinion_id}/original; GET /sources; GET /{opinion_id}; GET /{opinion_id}/original |
| `sources:read` | `foreign:sources:read`, `sources:read` | 12 | ? ?; GET /collection-logs; GET /collection-logs/{batch_key}/runs; GET /collection-runs; GET /collection-schedule/status; GET /quality; GET /regions; GET /sources; GET /sources/approved; GET /sources/{source_id}/runs; GET /{ds_id}/runs |
| `sources:write` | `foreign:sources:write`, `sources:write` | 6 | PATCH /sources/{source_id}; PATCH /{ds_id}; POST /schedule/batch; POST /sources; POST /test |

> 多数 domestic/foreign 叶子**无直接 `require_permission` 引用**（endpoint 数=0），
> 它们通过 `COMPOSITE_PERMISSIONS` 展开间接生效，或当前为 orphan。
> 有引用的核心能力（events:read/opinions:read/sources:*/keywords:*/alerts:read 等）端点数 4–12，
> 表明这些能力确有真实 API 保护，归并须同步改造 Enforcement（下一阶段范围）。

---

## 7. Permission → Role Matrix

每个候选归并组的 BEFORE 角色分配（合并前）与 PROPOSED（合并后）角色集：

| base | 成员 | BEFORE 角色 | PROPOSED 角色 | scope_diff |
|---|---|---|---|---|
| `ai:analyze` | `ai:analyze`, `domestic:ai:analyze`, `foreign:ai:analyze` | ai:analyze→admin, analyst; domestic:ai:analyze→admin, analyst; foreign:ai:analyze→admin | admin, analyst | YES |
| `ai:batch:cancel` | `domestic:ai:batch:cancel`, `foreign:ai:batch:cancel` | domestic:ai:batch:cancel→admin, analyst; foreign:ai:batch:cancel→analyst, operator | admin, analyst, operator | YES |
| `ai:batch:read` | `domestic:ai:batch:read`, `foreign:ai:batch:read` | domestic:ai:batch:read→admin, analyst; foreign:ai:batch:read→analyst, operator | admin, analyst, operator | YES |
| `ai:full-confirm` | `domestic:ai:full-confirm`, `foreign:ai:full-confirm` | domestic:ai:full-confirm→admin, analyst; foreign:ai:full-confirm→(none/orphan) | admin, analyst | YES |
| `ai:review:complete` | `domestic:ai:review:complete`, `foreign:ai:review:complete` | domestic:ai:review:complete→admin, analyst, viewer; foreign:ai:review:complete→admin, analyst, viewer | admin, analyst, viewer | no |
| `ai:review:read` | `domestic:ai:review:read`, `foreign:ai:review:read` | domestic:ai:review:read→admin, analyst, viewer; foreign:ai:review:read→analyst, viewer | admin, analyst, viewer | no |
| `ai:review:reject` | `domestic:ai:review:reject`, `foreign:ai:review:reject` | domestic:ai:review:reject→admin, analyst; foreign:ai:review:reject→(none/orphan) | admin, analyst | YES |
| `alerts:read` | `alerts:read`, `foreign:alerts:read` | alerts:read→analyst, operator, system_admin, viewer; foreign:alerts:read→admin | admin, analyst, operator, system_admin, viewer | YES |
| `alerts:review:confirm` | `domestic:alerts:review:confirm`, `foreign:alerts:review:confirm` | domestic:alerts:review:confirm→admin, analyst; foreign:alerts:review:confirm→(none/orphan) | admin, analyst | YES |
| `alerts:review:read` | `domestic:alerts:review:read`, `foreign:alerts:review:read` | domestic:alerts:review:read→admin, analyst; foreign:alerts:review:read→(none/orphan) | admin, analyst | YES |
| `events:read` | `events:read`, `foreign:events:read` | events:read→analyst, operator, system_admin, viewer; foreign:events:read→admin | admin, analyst, operator, system_admin, viewer | YES |
| `events:review:confirm` | `domestic:events:review:confirm`, `foreign:events:review:confirm` | domestic:events:review:confirm→admin, analyst; foreign:events:review:confirm→(none/orphan) | admin, analyst | YES |
| `events:review:read` | `domestic:events:review:read`, `foreign:events:review:read` | domestic:events:review:read→admin, analyst; foreign:events:review:read→(none/orphan) | admin, analyst | YES |
| `events:write` | `events:write`, `foreign:events:write` | events:write→analyst; foreign:events:write→admin | admin, analyst | YES |
| `keywords:read` | `foreign:keywords:read`, `keywords:read` | foreign:keywords:read→admin; keywords:read→analyst, operator | admin, analyst, operator | YES |
| `keywords:write` | `foreign:keywords:write`, `keywords:write` | foreign:keywords:write→admin; keywords:write→analyst, operator | admin, analyst, operator | YES |
| `opinions:read` | `foreign:opinions:read`, `opinions:read` | foreign:opinions:read→admin; opinions:read→analyst, operator, system_admin, viewer | admin, analyst, operator, system_admin, viewer | YES |
| `sources:read` | `foreign:sources:read`, `sources:read` | foreign:sources:read→admin, operator, system_admin; sources:read→analyst, operator, system_admin | admin, analyst, operator, system_admin | YES |
| `sources:write` | `foreign:sources:write`, `sources:write` | foreign:sources:write→admin, operator, system_admin; sources:write→operator, system_admin | admin, operator, system_admin | no |

---

## 8. Frontend Permission Consumption

只读扫描 `frontend/src`：共 **66** 个权限被前端直接引用。
国内/外网权限确实分别控制不同页面的同一 UI 能力，例如：

- `domestic:events:review:read` / `domestic:ai:review:read` → `src/views/Opinions.vue`（国内事件/AI 研判）
- `foreign:events:review:read` → `src/views/ForeignWorkspace.vue` + `src/views/foreign/ForeignAIReviewView.vue`（外网）
- `foreign:alerts:read` → `src/views/Roles.vue`
- `events:read` / `alerts:read` → `src/router/index.ts`（路由级守卫，国内）

> 前端消费证实「国内/外网页面不同」是**真实的 UI 差异**（§十原则 4），但 UI 差异 ≠ 授权需求差异。
> 若未来归并，前端只需将两处引用统一为新权限码，改动局部、低风险。

---

## 9. Candidate Consolidation Groups

共 **19** 个候选归并组（按去域前缀 base 聚合 domestic/foreign/core 同 base 成员）。
4 类最终分类计数：**MUST=2 / RECOMMENDED=1 / KEEP-SEPARATE=11 / DEFER=5**。

| base | 分类 | scope_diff | 理由摘要 |
|---|---|---|---|
| `ai:analyze` | DEFER | YES | domestic:ai:analyze=[admin,analyst]，foreign:ai:analyze=[admin]（foreign:analysis 高危复合叶子，0 业 |
| `ai:batch:cancel` | KEEP-SEPARATE | YES | domestic:ai:batch:cancel=[admin,analyst]，foreign:ai:batch:cancel=[analyst,operator]。operat |
| `ai:batch:read` | KEEP-SEPARATE | YES | domestic=[admin,analyst]，foreign=[analyst,operator]。operator 仅持 foreign，合并扩大 operator 至国内读 |
| `ai:full-confirm` | DEFER | YES | foreign:ai:full-confirm 为高危叶子 0 持有（orphan）。DEFER。 |
| `ai:review:complete` | MUST-CONSOLIDATE | no | 同上，国内/外 AI 研判「完成」角色集完全一致（admin+analyst+viewer），合并零风险。 |
| `ai:review:read` | MUST-CONSOLIDATE | no | 国内/外 AI 研判结果「查看」由完全相同业务角色集（admin+analyst+viewer）持有，且 foreign:ai:review:read 当前已授予 analyst/ |
| `ai:review:reject` | DEFER | YES | foreign:ai:review:reject 为高危叶子 0 持有（orphan）。DEFER。 |
| `alerts:read` | KEEP-SEPARATE | YES | core alerts:read 授予 analyst/operator/system_admin/viewer（国内预警读），foreign:alerts:read 仅 admi |
| `alerts:review:confirm` | DEFER | YES | foreign:alerts:review:confirm 为高危叶子 0 持有（orphan）。DEFER。 |
| `alerts:review:read` | KEEP-SEPARATE | YES | domestic=[admin,analyst]，foreign 叶子 0 持有（orphan）。合并使 analyst 获得外网预警复核读。BLOCKED。 |
| `events:read` | KEEP-SEPARATE | YES | core events:read 授予 4 个业务角色（国内事件读），foreign:events:read 仅 admin。合并扩大业务角色至外网事件读。BLOCKED。 |
| `events:review:confirm` | DEFER | YES | foreign:events:review:confirm 为高危叶子 0 持有（orphan）。DEFER。 |
| `events:review:read` | KEEP-SEPARATE | YES | domestic=[admin,analyst]，foreign 叶子 0 持有。合并使 analyst 获得外网事件复核读。BLOCKED。 |
| `events:write` | KEEP-SEPARATE | YES | core events:write=[analyst]（国内事件写），foreign:events:write=[admin]。合并使 analyst 获得外网事件写。BLOCKE |
| `keywords:read` | KEEP-SEPARATE | YES | core keywords:read=[analyst,operator]，foreign:keywords:read=[admin]。合并扩大业务角色至外网关键词读。BLOCKE |
| `keywords:write` | KEEP-SEPARATE | YES | core keywords:write=[analyst,operator]，foreign:keywords:write=[admin]。合并扩大业务角色至外网关键词写。BLOC |
| `opinions:read` | KEEP-SEPARATE | YES | core opinions:read=[analyst,operator,system_admin,viewer]，foreign:opinions:read=[admin]。合并 |
| `sources:read` | KEEP-SEPARATE | YES | core sources:read=[analyst,operator,system_admin]，foreign:sources:read=[admin,operator,sys |
| `sources:write` | RECOMMENDED-CONSOLIDATE | no | operator+system_admin 当前已同时持有 domestic/foreign 两种 sources:write（角色集一致），合并对这两类角色有效授权不变；但「数据 |

---

## 10. MUST-CONSOLIDATE

**定义**：国内/外网叶子保护**完全相同**能力，且业务角色集**逐字节一致** → 合并为单一权限，有效授权零变化。

- **`ai:review:complete`** ← `domestic:ai:review:complete`, `foreign:ai:review:complete`
  - 角色集：admin, analyst, viewer（合并前后一致）
  - 证据：同上，国内/外 AI 研判「完成」角色集完全一致（admin+analyst+viewer），合并零风险。
- **`ai:review:read`** ← `domestic:ai:review:read`, `foreign:ai:review:read`
  - 角色集：admin, analyst, viewer（合并前后一致）
  - 证据：国内/外 AI 研判结果「查看」由完全相同业务角色集（admin+analyst+viewer）持有，且 foreign:ai:review:read 当前已授予 analyst/viewer（非孤立）。合并为 ai:review:read 不改变任何角色有效授权，属零风险归并。

> 仅 2 项，因绝大多数 domestic/foreign 对角色集**并不一致**（见 KEEP-SEPARATE）。

---

## 11. RECOMMENDED-CONSOLIDATE

**定义**：高度可能可统一（角色集一致或仅超管持有），但存在轻微实现/敏感度差异，建议产品确认后归并。

- **`sources:write`** ← `foreign:sources:write`, `sources:write`
  - 角色集：admin, operator, system_admin
  - 证据：operator+system_admin 当前已同时持有 domestic/foreign 两种 sources:write（角色集一致），合并对这两类角色有效授权不变；但「数据源配置写入」属较高敏感操作，建议产品确认国内外数据源连接器无差异后再归并。

---

## 12. KEEP-SEPARATE

**定义**：当前**必须保持独立**。原因均为真实授权边界（BLOCKED-BY-SCOPE-DIFFERENCE）：
某业务角色持有国内叶子但不持有外网叶子，合并会将该角色**权限扩大**至外网域。
只有业务**明确确认「拥有国内 X 即拥有外网 X」**后，才可转为 RECOMMENDED。

- **`ai:batch:cancel`** ← `domestic:ai:batch:cancel`, `foreign:ai:batch:cancel`
  - domestic:ai:batch:cancel=[admin,analyst]，foreign:ai:batch:cancel=[analyst,operator]。operator 持有 foreign 但不持有 domestic —— 合并会使 operator 获得国内 AI 批次取消能力（权限扩大）。BLOCKED。
- **`ai:batch:read`** ← `domestic:ai:batch:read`, `foreign:ai:batch:read`
  - domestic=[admin,analyst]，foreign=[analyst,operator]。operator 仅持 foreign，合并扩大 operator 至国内读。BLOCKED。
- **`alerts:read`** ← `alerts:read`, `foreign:alerts:read`
  - core alerts:read 授予 analyst/operator/system_admin/viewer（国内预警读），foreign:alerts:read 仅 admin（外网预警读，foreign:read 复合叶子，当前 0 业务角色持有）。合并使全部业务角色获得外网预警读，越权扩大。BLOCKED。
- **`alerts:review:read`** ← `domestic:alerts:review:read`, `foreign:alerts:review:read`
  - domestic=[admin,analyst]，foreign 叶子 0 持有（orphan）。合并使 analyst 获得外网预警复核读。BLOCKED。
- **`events:read`** ← `events:read`, `foreign:events:read`
  - core events:read 授予 4 个业务角色（国内事件读），foreign:events:read 仅 admin。合并扩大业务角色至外网事件读。BLOCKED。
- **`events:review:read`** ← `domestic:events:review:read`, `foreign:events:review:read`
  - domestic=[admin,analyst]，foreign 叶子 0 持有。合并使 analyst 获得外网事件复核读。BLOCKED。
- **`events:write`** ← `events:write`, `foreign:events:write`
  - core events:write=[analyst]（国内事件写），foreign:events:write=[admin]。合并使 analyst 获得外网事件写。BLOCKED。
- **`keywords:read`** ← `foreign:keywords:read`, `keywords:read`
  - core keywords:read=[analyst,operator]，foreign:keywords:read=[admin]。合并扩大业务角色至外网关键词读。BLOCKED。
- **`keywords:write`** ← `foreign:keywords:write`, `keywords:write`
  - core keywords:write=[analyst,operator]，foreign:keywords:write=[admin]。合并扩大业务角色至外网关键词写。BLOCKED。
- **`opinions:read`** ← `foreign:opinions:read`, `opinions:read`
  - core opinions:read=[analyst,operator,system_admin,viewer]，foreign:opinions:read=[admin]。合并扩大业务角色至外网舆情读。BLOCKED。
- **`sources:read`** ← `foreign:sources:read`, `sources:read`
  - core sources:read=[analyst,operator,system_admin]，foreign:sources:read=[admin,operator,system_admin]。analyst 持有 core 但不持有 foreign —— 合并使 analyst 获得外网数据源读。BLOCKED。

> 关键安全闸门（D5-十六）：以上任何一项**默认不可直接归并**。若强行归并，
> `analyst`/`operator` 将意外获得外网读/写/复核能力 —— 这正是当前设计刻意避免的。

---

## 13. DEFER / DO-NOT-TOUCH

**定义**：Foreign 高危复合/叶子，D5-17 明确 DEFER。不为消灭 orphan 而授予角色，不合并。

候选归并组中的 DEFER：
- **`ai:analyze`** ← `ai:analyze`, `domestic:ai:analyze`, `foreign:ai:analyze` —— domestic:ai:analyze=[admin,analyst]，foreign:ai:analyze=[admin]（foreign:analysis 高危复合叶子，0 业务角色持有）。属 Foreign 高危能力，D5-17 明确 DEFER/DO-NOT-TOUCH，且 analyst 仅持国内分析。
- **`ai:full-confirm`** ← `domestic:ai:full-confirm`, `foreign:ai:full-confirm` —— foreign:ai:full-confirm 为高危叶子 0 持有（orphan）。DEFER。
- **`ai:review:reject`** ← `domestic:ai:review:reject`, `foreign:ai:review:reject` —— foreign:ai:review:reject 为高危叶子 0 持有（orphan）。DEFER。
- **`alerts:review:confirm`** ← `domestic:alerts:review:confirm`, `foreign:alerts:review:confirm` —— foreign:alerts:review:confirm 为高危叶子 0 持有（orphan）。DEFER。
- **`events:review:confirm`** ← `domestic:events:review:confirm`, `foreign:events:review:confirm` —— foreign:events:review:confirm 为高危叶子 0 持有（orphan）。DEFER。

独立 Foreign 高危项（不进候选组，单独保留）：

- `foreign:alerts:acknowledge`
- `foreign:alerts:ai-admit`
- `foreign:alerts:enable`
- `foreign:alerts:evaluate`
- `foreign:alerts:false_positive`
- `foreign:alerts:manage`
- `foreign:alerts:resolve`
- `foreign:alerts:rules:write`
- `foreign:alerts:suppress`
- `foreign:analysis`
- `foreign:data:manage`
- `foreign:events:auto-aggregate`
- `foreign:events:confirm`
- `foreign:events:merge`
- `foreign:events:rebuild`
- `foreign:events:split`
- `foreign:events:status`
- `foreign:read`
- `foreign:risk:ai`
- `foreign:risk:analyze`
- `foreign:risk:batch`

> `foreign:analysis` / `foreign:alerts:manage` 仍为 EXPECTED-ORPHAN（0 角色持有），
> 连同新增的 `foreign:alerts:false_positive`（admin-only）一并 DEFER 至后续能力模型阶段。

---

## 14. Role Expansion / Security Impact

对每一候选组模拟合并后的角色影响（**仅模拟，不执行**）：

- **MUST/RECOMMENDED（2+1）**：合并前后业务角色有效授权**完全一致** → **零扩大风险**。
- **KEEP-SEPARATE（11）**：若强行合并，**扩大风险**如下：
  - `analyst` 将获得外网 events/alerts/opinions/keywords 的 read/write/review（当前仅国内）
  - `operator` 将获得国内 ai:batch:cancel/read（当前仅外网）
  - `viewer` 将获得外网 events/alerts 读
  - 这些扩大均**未经业务确认**，故禁止自动归并。
- **DEFER（5+）**：外网高危能力，保持 admin/orphan 现状。

`security_risks.scope_difference_groups` = ['ai:analyze', 'ai:batch:cancel', 'ai:batch:read', 'ai:full-confirm', 'ai:review:reject', 'alerts:read', 'alerts:review:confirm', 'alerts:review:read', 'events:read', 'events:review:confirm', 'events:review:read', 'events:write', 'keywords:read', 'keywords:write', 'opinions:read', 'sources:read']

---

## 15. Simulated Before / After Matrix

**仅为模拟（SIMULATION），非生产变更。**

- **BEFORE**：permissions = **89**
- **SAFE MERGE（仅 MUST+RECOMMENDED，零授权变化）**：合并 3 组 → permissions ≈ **86**
- **FULL CONSOLIDATION（假设业务确认统一授权后，合并全部 19 组，含 KEEP/DEFER）**：permissions ≈ **69**（纯架构假设，不代表建议）

示例（SAFE MERGE）：

```
BEFORE:
  domestic:ai:review:read   -> admin, analyst, viewer
  foreign:ai:review:read   -> analyst, viewer
  domestic:ai:review:complete -> admin, analyst, viewer
  foreign:ai:review:complete -> admin, analyst, viewer
  sources:write             -> operator, system_admin
  foreign:sources:write     -> admin, operator, system_admin
PROPOSED:
  ai:review:read    -> admin, analyst, viewer
  ai:review:complete -> admin, analyst, viewer
  sources:write     -> admin, operator, system_admin
```

> `role_permissions` 行数将随 permissions 减少而同比例下降（每组 2 叶子→1 统一权限，
> 涉及角色的行合并）。SAFE MERGE 影响 6 条 role_permissions 行（3 组 × 2 成员）。

---

## 16. Recommended Permission Model

建议的「能力导向」权限模型（**设计建议，非实施**）。原则：Permission = Business Capability，
国内/外网默认作为**数据域**而非独立权限；Foreign 高危能力继续独立。

**建议统一（去 domestic/foreign 前缀）的能力：**

- `events:read` `events:write` `events:review:read` `events:review:confirm` `events:review:complete` `events:review:reject`
- `alerts:read` `alerts:write` `alerts:review:read` `alerts:review:confirm`
- `opinions:read` `opinions:write` `opinions:delete` `opinions:review`
- `ai:analyze` `ai:review:read` `ai:review:complete` `ai:review:reject` `ai:batch:read` `ai:batch:cancel` `ai:full-confirm`
- `sources:read` `sources:write` `keywords:read` `keywords:write`
- `propagation:read` `bocha:read` `bocha:promote` `collector:run` 等既有核心能力保持不变

**必须继续独立的 Foreign 能力（高危，DEFER）：**

- `foreign:analysis`（复合，含 risk/events/alerts/ai 全链路高危叶子）
- `foreign:alerts:manage`（复合，含 acknowledge/resolve/suppress/enable 等处置权）
- `foreign:alerts:false_positive` `foreign:events:confirm` `foreign:events:merge/split/status/rebuild`
- 等外网专属强处置能力 —— 这些**不应**因「归并」而下沉到 analyst/operator。

> 统一后，原 `domestic:*` 与对应 `foreign:*` 合并为单权限；外网高危复合仍独立，
> 通过显式角色授予（而非默认继承）控制谁可触外网。

---

## 17. Foreign High-Risk Handling

- `foreign:analysis` / `foreign:alerts:manage`：D4 EXPECTED-ORPHAN，D5 DEFER，0 角色持有。
- `foreign:ai:full-confirm` / `foreign:ai:review:reject` / `foreign:alerts:review:confirm` / `foreign:events:review:confirm`：高危叶子，0 业务角色持有，DEFER。
- `foreign:alerts:false_positive`：Phase 15-C1 新增，仅 admin 持有，DEFER。
- **原则**：orphan ≠ bug（D4 已确认）。不为消灭 orphan 而授予角色，不合并高危复合。

---

## 18. Non-Domestic/Foreign Duplicate Permissions

**未发现**非 domestic/foreign 的 (resource, action) 重复权限。
即除「国内/外网」前缀拆分外，权限目录**不存在其他机械复制的过细权限**（如 `xxx:review` 与 `xxx:confirm` 语义不同，不构成重复）。

---

## 19. Future Scope Requirements

若业务未来确实需要「按国内/外网区分授权」（例如 analyst 只能处置国内事件、不能触外网），
**不应**在权限目录层用 `domestic:`/`foreign:` 前缀机械复制，而应在后续阶段作为
**FUTURE-DESIGN-REQUIREMENT** 记录（本阶段不实现）：

- 方案 A：数据域 scope（在既有权限上叠加 `scope=domestic|foreign` 维度），保持权限码稳定；
- 方案 B：Foreign 能力模型阶段将 `foreign:analysis`/`foreign:alerts:manage` 拆为可授予角色的能力；
- **禁止**引入 ABAC policy engine / Capability model / 第二权限事实源（D5-二十）。

---

## 20. Red-line Compliance

| 红线 | 遵守 |
|---|---|
| 修改生产库 / 5432 权限 | ✅ 仅 SELECT |
| 修改 role_permissions / permissions / roles / users | ✅ 未改 |
| 新增/修改 Alembic migration | ✅ 未执行 upgrade/downgrade |
| 修改 COMPOSITE_PERMISSIONS / expand_permissions / require_permission / require_admin | ✅ 未改 |
| 修改业务 API Enforcement | ✅ 未改（require_admin 站点仍 0） |
| 修改前端权限逻辑 | ✅ 仅只读扫描 |
| 实施权限归并 | ✅ 仅建议，未执行 |
| 引入 Capability / ABAC / Scope engine | ✅ 未引入 |
| 修改 RBAC 核心语义 | ✅ 未改 |

---

## 21. Deliverables

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/audit-evidence/_rbac_consolidation_audit.py` | 新增（只读） | D5 归并审计脚本 |
| `backend/audit-evidence/rbac_consolidation_audit.json` | 新增 | 审计证据（89 权限全目录 / 候选组 / 分类 / 模拟） |
| `docs/Phase-Security-RBAC-Redesign-D5-Permission-Consolidation-Audit.md` | 新增 | 本报告 |

---

## 22. Final Decision

**✅ PASS** —— 审计完整，所有 D5-26 PASS 硬指标满足：

- [x] 89 权限逐项审计（含漂移校正）
- [x] domestic/foreign 权限全部识别（58 个：11 domestic + 47 foreign）
- [x] API Enforcement 映射完成（require_admin=0，全部可解析）
- [x] 前端权限消费审计完成（66 权限被引用）
- [x] Role impact 分析完成（含 scope_difference 闸门）
- [x] 每个候选归并组均有明确 4 类分类
- [x] Foreign 高危权限未被误处理（DEFER）
- [x] 无生产写操作 / 未改 RBAC 核心 / 未改 permissions / 未新增 migration
- [x] JSON + Markdown 证据完整

**对 D5-二十五 12 个最终问题的明确回答：**

1. 89 个权限中，明确有归并价值（候选组）的 = **19 组**（覆盖 38 个 domestic/foreign 叶子）。
2. **MUST-CONSOLIDATE = 2**（ai:review:read, ai:review:complete）。
3. **RECOMMENDED-CONSOLIDATE = 1**（sources:write）。
4. **KEEP-SEPARATE = 11**（均因 scope_difference 授权边界）。
5. **DEFER = 5 + 独立 Foreign 高危项若干**（foreign:analysis / foreign:alerts:manage / false_positive 等）。
6. 因「国内/外网被机械复制」而产生的权限：11 个 `domestic:*` 及其 `foreign:*` 对应叶子（共 22 个叶子，含于候选组）。
7. 真正具有不同授权语义、须保持独立的：KEEP-SEPARATE 的 11 组（外网域对 analyst/operator/viewer 确有限制）。
8. 若仅实施 SAFE MERGE（MUST+RECOMMENDED）：permissions **89 → 86**；若业务确认全量统一：≈ **89 → 69**（纯架构假设）。
9. role_permissions 行数将随 permissions 减少同比例下降（SAFE MERGE 影响 6 行）。
10. **可能扩大权限的角色**：若强行合并 KEEP-SEPARATE 组 → analyst/operator/viewer 将意外获得外网能力（已设 BLOCKED 闸门阻止）。
11. **Foreign 高危误合并风险**：已通过 DEFER + 不授予角色完全规避。
12. 推荐模型见 §16：能力导向、去 domestic/foreign 前缀、Foreign 高危继续独立。

---

## 最终汇报（第二十七条格式）

# Phase Security-RBAC-Redesign-D5
## Permission Consolidation Audit

### Status
PASS

### 1. Audit Scope
纯只读审计：89 权限目录归并分析（domestic/foreign 拆分导致的过细/重复/重叠）。

### 2. Production Baseline
5432 VERIFIED / alembic `p34_foreign_event_status_unify` / permissions=89 / roles=5 / require_admin API=0。（注意基线漂移：D4 文档为 88/rbac_d3_enforcement_v2，生产已演进。）

### 3. Permission Catalog Statistics
总数 89；domestic/foreign 域 58（domestic=11, foreign=47）；非 domestic/foreign 重复 = 0。

### 4. Domestic / Foreign Inventory
domestic 11 个均有 foreign 对应（进候选组）；foreign 47 个多为外网专属/高危叶子。详见 §5。

### 5. Consolidation Candidates
19 个候选组：MUST=2 / RECOMMENDED=1 / KEEP-SEPARATE=11 / DEFER=5。

### 6. MUST-CONSOLIDATE
ai:review:read, ai:review:complete（角色集逐字节一致，零授权变化）。

### 7. RECOMMENDED-CONSOLIDATE
sources:write（operator+system_admin 已同时持有，建议产品确认后归并）。

### 8. KEEP-SEPARATE
11 组，均因 BLOCKED-BY-SCOPE-DIFFERENCE（合并会扩大业务角色至外网域）。

### 9. DEFER / DO-NOT-TOUCH
5 候选组 + foreign:analysis / foreign:alerts:manage / foreign:alerts:false_positive 等高危项。

### 10. Role Impact
SAFE MERGE 零扩大；KEEP-SEPARATE 强行合并将扩大 analyst/operator/viewer 至外网。

### 11. API Enforcement Impact
require_admin=0；有引用的核心能力端点 4–12；多数 domestic/foreign 叶子经复合展开间接生效。

### 12. Frontend Impact
66 权限被前端引用；国内/外网分别控制不同页面同 UI 能力，归并时前端改动局部。

### 13. Simulated Permission Changes
SAFE MERGE: 89→86；FULL(假设): 89→69。

### 14. Recommended Future Permission Model
能力导向、去 domestic/foreign 前缀；Foreign 高危复合继续独立（§16）。

### 15. Foreign High-Risk Safety
高危 Foreign 全部 DEFER，0 业务角色持有，未误合并/误授予。

### 16. Security Assessment
当前 domestic/foreign 拆分是**刻意授权边界**而非纯命名重复；仅 3 组可零风险归并，
其余须业务确认 scope 统一策略后再议。安全边界未被破坏。

### 17. Red-line Compliance
全部红线遵守（仅 SELECT / 未改核心 / 未改权限 / 未新增 migration / 未实施归并 / 未引入 ABAC）。

### 18. Deliverables
_rbac_consolidation_audit.py + rbac_consolidation_audit.json + 本报告。

### 19. Final Recommendation
**可以进入下一阶段「Permission Consolidation Implementation」**，但须严格遵守：
下一阶段必须**基于本报告逐项确认**，**不得自动执行全部 MUST-CONSOLIDATE**。建议顺序：
1. 先实施 SAFE MERGE（MUST 2 + RECOMMENDED 1），因其零授权变化、风险最低；
2. KEEP-SEPARATE 组需产品/安全**逐组 sign-off**「国内⇒外网授权统一」策略后方可实施；
3. DEFER 组（Foreign 高危）留待 Foreign 能力模型阶段，本阶段不触。
4. 实施时需同步改造 `COMPOSITE_PERMISSIONS` 展开、`require_permission` Enforcement、前端引用（§6/§8）。