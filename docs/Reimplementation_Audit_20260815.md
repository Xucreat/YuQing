# 重新实现前只读审计报告（Reimplementation Audit）

- 审计时间：2026-08-15 17:59 (+0800)
- 审计性质：**只读审计（Phase 0）**，不实施任何功能
- 工作区：`C:\Users\Administrator\Desktop\YQ`
- 结论：**AUDIT_COMPLETE**

---

## 1. 审计范围

| 编号 | 范围 | 覆盖情况 |
|---|---|---|
| 一 | 工作区真实状态（目录/分支/HEAD/提交/status/diff/未跟踪/目录结构/static） | 已完成 |
| 二 | 历史依据文档（15-A / 15-B / 15-C / 实施计划_4阶段 / 改造方案 / 外网界面需求整理） | 已完成 |
| 三 | A 国内风险展示口径 | 已完成 |
| 四 | B 批量 AI 研判与预览 | 已完成 |
| 五 | C 国内与外网预警处置 | 已完成 |
| 六 | D 预警表格与备注 | 已完成 |
| 七 | E 15-C 数据库设计（只读 SELECT） | 已完成 |
| 八 | F 测试现状 | 已完成 |

本阶段严格遵守只读约束，实际执行的写操作**仅有本报告文件的创建**。

---

## 2. 当前分支、HEAD、工作区状态

| 项 | 值 |
|---|---|
| 当前目录 | `/c/Users/Administrator/Desktop/YQ` |
| 当前分支 | `codex/recover-frontend-20260814` |
| 当前 HEAD | `9afe7de35ed01969eaa139355464ac9e37241b27` |
| main | `e56d3d61`（ahead of origin/main 1） |
| 工作区统计 | `39 M`（已修改跟踪文件） + `143 ??`（未跟踪） + **0 D** |

### 最近 10 个提交

```
9afe7de3 feat(前端): 外网事件子页面搬入事件中心并保留处置/删除入口   <- HEAD, 2026-08-15 17:21
7cc8b6a1 Phase 6A: repair foreign alert confirmed_event rule stale 'confirmed' status
f427115b feat: wire foreign event row actions
67f87a0e Phase 4B-Backend: add DELETE /api/foreign/events/{id} (foreign:events:write)
ee1050c9 Phase 4A: Events table and foreign situation wiring
73464cf1 Phase 3: add foreign event situation endpoint
29291a9b 完成阶段2：重建 ForeignEventDetail.vue 并补充 /foreign/event/:id 路由
d71a05a4 Phase2-A: 统一外网事件状态契约(对齐国内7状态枚举)
1e0130b4 Phase1: 抽取统一事件处置弹窗 EventDispositionDialog
3f42235e 修复：RSS 新建数据源测试弹窗误显示「0 个链接」
```

### HEAD 差异说明（必须记录，不自行切换）

| 来源 | 记录的 HEAD | 与当前是否一致 |
|---|---|---|
| 当前工作区实测 | `9afe7de3` | — |
| `docs/Phase_System_Readonly_Audit_20260814.md`（上次审计） | `7cc8b6a1` | **不一致（当前领先 1 个提交）** |
| 工作记忆（.workbuddy/memory） | `7cc8b6a1` | **不一致** |

**差异原因已查明（非异常）**：`9afe7de3` 由用户 `xhl` 于 2026-08-15 17:21:12 提交，内容为
`frontend/src/views/foreign/ForeignEventsView.vue`（新增）+ `frontend/src/views/Events.vue`（修改）
+ `backend/app/static/index.html` + **1374 个 `backend/app/static/assets/` 文件**。

这解释了上次审计记录的「1301 个 D（已删除）」现已归零：那批删除是构建产物差异，已随本次提交落地。
**本次审计未做任何 Git 写操作，HEAD 保持 `9afe7de3` 不变。**

### 2026-08-13 回退事件的 reflog 证据（只读）

```
756cc8cd HEAD@{2026-08-14 15:23:26}: reset: moving to HEAD
756cc8cd HEAD@{2026-08-13 17:11:17}: reset: moving to HEAD      <- 用户所述 17:00 左右回退
756cc8cd HEAD@{2026-08-13 17:07:07}: commit: feat: 完善外网AI人工复核闭环与驾驶舱外网嵌入
```

`756cc8cd` 是 `frontend/src/views/Alerts.vue` 的**最后一次提交**。当前 `Alerts.vue` 工作区状态为
「未修改」（`git status --porcelain` 输出为空），即 **Alerts.vue 现在等于 `756cc8cd` 的版本**，
2026-08-13 17:07 之后针对该文件的全部修改均已不存在。

---

## 3. 未提交修改与未跟踪文件清单

### 3.1 已修改跟踪文件（39 M，去除构建产物后的源码级清单）

```
Foreign_RSS_Source_Recommendations.md
backend/app/api/alerts.py
backend/app/api/foreign.py
backend/app/api/foreign_alerts.py
backend/app/api/opinions.py
backend/app/api/propagation.py
backend/app/api/users.py
backend/app/collectors/mediacrawler_runner.py
backend/app/core/permissions.py
backend/app/models/event.py
backend/app/models/event_action.py
backend/app/models/foreign_alert.py
backend/app/schemas/event.py
backend/app/services/foreign_alert_service.py
backend/app/services/foreign_visualization_service.py
backend/scripts/run_mediacrawler_real_verify.py
backend/tests/conftest.py
backend/tests/test_alert_operation.py            <- 文件已损坏（见 F 节）
backend/tests/test_foreign_source_3b.py
backend/tests/test_foreign_source_3b_remediation.py
backend/tests/test_foreign_source_5a_5e.py
backend/tests/test_foreign_source_5g_remediation.py
backend/tests/test_media_crawler_1b.py
backend/tests/test_rbac.py
backend/tests/test_rbac_hardening.py
frontend/package.json / package-lock.json
frontend/src/views/AiSearch.vue
frontend/src/views/Dashboard.vue
frontend/src/views/ForeignWorkspace.vue
frontend/src/views/Opinions.vue                  <- 仅权限常量改名 4 行
docs/phase-responsive-1-screenshots/*.png (7)
```

`frontend/src/views/Opinions.vue` 的全部未提交改动仅为权限常量重命名：
`domestic:ai:review:complete` → `ai:review:complete`，`domestic:ai:review:read` → `ai:review:read`。

### 3.2 ⚠️ 未跟踪的**核心源码**（BLOCKING 级风险）

以下 22 个后端文件与 5 个前端文件承载了国内 AI 复核链路、current_risk 采纳链路、RBAC D 系列与
15-C 数据库迁移，**全部从未进入任何 Git 提交**：

```
# Alembic 迁移（10 个，含 15-C）
backend/alembic/versions/current_risk_adoption_v1.py
backend/alembic/versions/domestic_ai_review_chain.py
backend/alembic/versions/foreign_alert_disposition_status.py     <- 15-C 迁移
backend/alembic/versions/p33_event_archived_merge_split.py
backend/alembic/versions/p34_foreign_event_status_unify.py
backend/alembic/versions/rbac_d1_role_directory_governance.py
backend/alembic/versions/rbac_d2_enforcement_v1.py
backend/alembic/versions/rbac_d3_enforcement_v2.py
backend/alembic/versions/review_decision_complete_v2.py
backend/alembic/versions/review_substates_and_complete_perm_v1.py

# 模型（5 个）
backend/app/models/domestic_ai_alert_candidate.py
backend/app/models/domestic_ai_batch_run.py
backend/app/models/domestic_ai_result.py
backend/app/models/domestic_manual_review.py
backend/app/models/foreign_ai_alert_candidate.py

# 服务（6 个）
backend/app/services/current_risk.py                  <- 当前风险采纳核心
backend/app/services/domestic_ai_service.py
backend/app/services/domestic_manual_review_service.py
backend/app/services/event/management.py
backend/app/services/foreign_event_situation.py
backend/app/services/foreign_manual_review_service.py

# 核心（1 个）
backend/app/core/rbac_d1.py

# 前端（5 个）
frontend/src/components/BatchAIModal.vue
frontend/src/components/EventAnalysisStats.vue
frontend/src/composables/useCockpitScope.ts
frontend/src/styles/events-layout-fix.css
frontend/src/views/foreign/useForeignOpinion.ts
```

**风险**：Alembic 版本链 `foreign_alert_disposition_v1 → p34 → d6_ai_review_consolidation` 中的
`foreign_alert_disposition_status.py`、`p33`、`p34` 三个文件均未提交。数据库已应用到 `d6`，
若在其他环境重建库，链路会断裂。

### 3.3 其他未跟踪项（备份/临时，仅登记不处理）

- 备份目录：`backend/app/static.bak.*`（6 个）、`backend/app/static.pre_frontend_recovery_20260814/`、
  `_static_trash_20260724_1749/`、`frontend/dist*/`（14 份）
- 编译产物孤岛：`_chk.js`（80213 字节，2026-08-14 15:12，15-C 版 Alerts.vue 的编译产物）
- 损坏备份：`backend/app/services/current_risk.py.corrupt-20260814`
- 本会话遗留临时脚本：`_mem_append.js`、`_mem_append2.js`（上次会话删除未生效，无害）
- 历史文档：`实施计划_4阶段_预警与展示口径优化.md`、`改造方案_预警与展示口径优化.md`、
  `外网舆情界面_待修改需求整理.md`、`docs/Phase_Foreign-Alert-Status-15-{A,B,C}*.md`

---

## 4. 当前真实代码结构

### 4.1 前端

```
frontend/src/{api,components,composables,layouts,router,stores,styles,types,utils,views}
frontend/src/views/            25 个 .vue（Alerts.vue / Opinions.vue / ForeignWorkspace.vue / Events.vue ...）
frontend/src/views/foreign/    ForeignAIReviewView / ForeignCollectionLogView / ForeignEventsView
                               / ForeignKeywordsView / ForeignOpinionDetailModal / ForeignOpinionListView
                               / ForeignSourcesView / foreign-ui.css / foreignSourceStatus{,.test}.ts
                               / useForeignOpinion.ts
```

### 4.2 后端

```
backend/app/{api,collectors,constants,core,db,models,schemas,services,static,utils}
backend/app/api/          24 个模块（alerts / foreign / foreign_alerts / foreign_events
                          / domestic_ai_analysis / opinions ...）
backend/app/services/     预警与 AI 相关：alert_service / current_risk / domestic_ai_service
                          / domestic_manual_review_service / foreign_ai_service
                          / foreign_alert_admission_service / foreign_alert_service
                          / foreign_effective_risk / foreign_manual_review_service
                          / foreign_risk_service / risk_engine / risk_terms
backend/alembic/versions/  含 10 个未跟踪迁移
```

### 4.3 backend/app/static 编译产物

| 项 | 值 |
|---|---|
| 是否存在 | 存在 |
| assets 文件数 | **164** |
| index.html 引用 | `assets/index-CL6LKzp8.js` + `assets/index-ByK17bbq.css` |
| Git 状态 | **已全部提交**（`git status backend/app/static/` 输出为空） |
| Alerts chunk | 6 个（`Alerts-7ycVuI_u/Bxly08Ac/CL0lT3it/DY0fnATz/JXUS-Dst/czLYJv3G.js`） |
| 6 个 chunk 的 `disposition_status` 计数 | **全部为 0** |

结论：**当前部署产物与当前源码同源，均为不含 disposition 的版本**。产物与源码之间无偏差。

---

## 5. 历史需求与当前实现的差异矩阵

结论取值：`已完成` / `部分完成` / `当前缺失` / `已回退` / `无法确认`

| # | 历史需求 | 当前源码实现 | 数据库 | 结论 |
|---|---|---|---|---|
| 1 | 国内列表读取 `current_risk_score`/`current_risk_source` | `Opinions.vue` 列表用 `row.risk_score`；`current_risk` 全文件计数 **0** | 4 列齐备 | **当前缺失** |
| 2 | 仅「已研判且采用 AI 展示」显示 AI 分与 AI 标识 | 无任何 AI/规则标识渲染 | — | **当前缺失** |
| 3 | 未研判舆情保持规则分原样 | 天然满足（全部显示 `risk_score`） | — | 已完成（副作用） |
| 4 | 不给所有行强加 AI/规则徽标 | 无徽标 | — | 已完成 |
| 5 | 不做全局展示口径切换 | 无全局开关；`localStorage` 仅存 `domestic-ai-active-run` | — | 已完成 |
| 6 | 后端 `display_risk` 不被改动 | `serialize_alert` 无 display_risk 改动 | — | 已完成 |
| 7 | 国内批量「保留规则风险」 | 批量下拉**无** `keep_rule`（单行有） | — | **当前缺失** |
| 8 | 外网批量「采用 AI 展示」 | `ForeignAIReviewView.vue` L14 有 | — | 已完成 |
| 9 | 外网批量逐条容错、不整批回滚 | `foreign.py` L1913-1943 savepoint 逐条 + `failed[]` | — | 已完成 |
| 10 | 国内批量逐条容错 | `domestic_ai_analysis.py` L779-800 **整批 rollback + 409** | — | **当前缺失** |
| 11 | 预览不调用 AI | 国内/外网预览均无 AI 调用 | — | 已完成 |
| 12 | 预览不创建正式预警 | `evaluate(dry_run=True)` L372 跳过建 alert | — | 已完成 |
| 13 | 预览仅统计已有结果 | 外网预览额外调用 `rebuild_candidates(commit=True)` 与 `evaluate(dry_run)`，写入 run 记录 | — | **部分完成** |
| 14 | 候选按 `opinion_id` 去重 | 国内 `count(distinct opinion_id)`；外网 `matched: set[int]` | — | 已完成 |
| 15 | 国内预览不再硬编码 0 | `_preview_domestic_alert_count` 真实统计 | — | 已完成 |
| 16 | AI 只生成候选、不直接触发正式预警 | 边界保持（评论与代码一致） | — | 已完成 |
| 17 | 国内处置 5 态 + 备注写入 | `PUT /alerts/records/{id}/handle` 写 `status`/`handled`/`handle_note` | — | 已完成 |
| 18 | 国内备注可被列表读取 | API 输出 `handle_note`；**表格无备注列** | — | **部分完成** |
| 19 | 删除国内禁止流转约束 | `_FORBIDDEN_DOMESTIC_TRANSITIONS` **仍在**（L89-98，409 拒绝） | — | **当前缺失（需删除）** |
| 20 | 外网 `status` 保持生命周期语义 | CHECK 5 态 `triggered/acknowledged/resolved/suppressed/failed` | 一致 | 已完成 |
| 21 | 外网 `disposition_status` 五态 | **模型层有**（L46-50、L79-81）；服务/API/前端**全无** | 列+CHECK+索引齐备 | **部分完成** |
| 22 | `set_disposition()` | `foreign_alert_service.py` 计数 **0** | — | **当前缺失** |
| 23 | 外网处置 API 支持 disposition 参数 | `foreign_alerts.py` 21 个端点无一个含 disposition | — | **当前缺失** |
| 24 | 外网处置备注单独保存 | **无 `disposition_note` 列**（模型与 DB 均无） | 无该列 | **当前缺失** |
| 25 | 外网 disposition 审计 | `foreign_alert_disposition_actions` 表存在但**无任何代码引用** | 表存在（8 列） | **部分完成** |
| 26 | `ignored` 与 `false_positive` 语义区分 | DB CHECK 已区分；无代码消费 | 已区分 | **部分完成** |
| 27 | `false_positive` 不被 `suppressed` 替代 | 无映射代码（尚未实现） | — | 无法确认（待实现时保证） |
| 28 | 外网默认隐藏误报 + 隐藏误报开关 | 国内有（`hideFalsePositive=true` + `exclude_status`）；**外网无** | — | **当前缺失** |
| 29 | 外网删除生命周期状态筛选项 | `Alerts.vue` L58 生命周期 5 选项**仍在** | — | **当前缺失** |
| 30 | 外网操作列只保留「处置」 | 当前 5 个按钮：详情/处置历史/确认/解决/抑制 | — | **当前缺失** |
| 31 | 外网来源筛选 `source_name_snapshot` 精确匹配 | `foreign_alerts.py` L210 `== source` | — | 已完成（现状确认） |
| 32 | 15-C 前端（Alerts.vue 双状态） | 源码=`756cc8cd` 旧版；仅 `_chk.js` 存编译产物 | — | **已回退** |
| 33 | 15-C 测试 38 用例 | `test_foreign_alert_disposition.py` 二进制损坏，Git 无副本 | — | **当前缺失** |
| 34 | ①B 历史预警快照回填 | — | — | **SKIPPED BY USER DECISION** |

---

## 6. 国内风险展示口径审计结论（A）

### 后端：链路完整 ✅

| 层 | 证据 | 状态 |
|---|---|---|
| 模型 | `models/opinion.py` L66-78：`current_risk_source` / `current_risk_score` / `current_risk_level` / `current_risk_updated_at`；L150-155 CHECK（source ∈ rule,ai；level ∈ low,medium,high,unknown） | 完成 |
| Schema | `schemas/opinion.py` L61-65 `OpinionOut` 含全部 4 字段 + `current_ai_result_id` | 完成 |
| 列表 API | `api/opinions.py` L48-52 `_current_risk_score_expression()` = `CASE WHEN current_risk_updated_at IS NOT NULL THEN current_risk_score ELSE risk_score END` | 完成 |
| 采纳服务 | `services/current_risk.py`（153 行）含 `adopt_domestic_rule` / `adopt_domestic_ai` / `apply_review_decision` / `sync_domestic_rule_if_not_ai_adopted` | 完成（**未提交**） |
| 决策落地 | `domestic_ai_analysis.py` L681-697：`keep_rule`/`use_ai_display` → `apply_review_decision(...)` | 完成 |

**重要发现**：`_current_risk_score_expression()` 当前**仅用于 `risk_min`/`risk_max` 筛选**（L100-104），
不参与响应字段构造。但由于 `OpinionOut` 声明了 4 个 `current_risk_*` 字段且 ORM 有对应属性，
**列表响应实际已携带 `current_risk_source` 与 `current_risk_score`**。

### 前端：链路断裂 ❌

| 检查项 | 结果 |
|---|---|
| `Opinions.vue` 中 `current_risk` 出现次数 | **0** |
| 列表风险等级列（L196） | `levelPill(row.risk_score)` / `levelText(row.risk_score)` |
| 列表风险分列（L199） | `riskColor(row.risk_score)` / `{{ row.risk_score }}` |
| `types/index.ts` 的 `Opinion` 接口 | **未声明** `current_risk_source` / `current_risk_score`（仅 3 处 `linked_opinion_current_risk?: CurrentRisk`，用于事件/预警） |
| AI / 规则徽标 | 不存在（既无正确实现，也无错误滥加） |
| 全局展示口径切换 | 不存在 ✅ 符合要求 |
| `localStorage` 使用 | 仅 `domestic-ai-active-run`（批量任务 run_id，L429/778/798/841），与展示口径无关 ✅ |
| 后端 `display_risk` 是否被改 | 未改 ✅ |

**结论**：后端已就绪并已输出字段，**唯一缺口在前端消费层**（`types/index.ts` 未声明 + `Opinions.vue` 未使用）。
「采用 AI 展示」后国内列表仍显示规则分。Phase 1 的工作量集中在前端，属**低风险改动**。

---

## 7. 批量 AI 研判审计结论（B）

### 国内

| 检查项 | 证据 | 结论 |
|---|---|---|
| 单行决策含 `keep_rule` | `Opinions.vue` L289-291（采用 AI 展示 / 保留规则风险 / 完成复核） | 已完成 |
| **批量决策含 `keep_rule`** | L241-246 仅有 `use_ai_display` / `confirm_event_change` / `confirm_alert_change` / `reject_change` / `confirm_event_all` / `reject_all` | **当前缺失** |
| 后端支持 `keep_rule` 批量 | `decide_reviews_batch` 透传 `payload.decision`，后端**已支持** | 后端就绪 |
| 逐条容错 | L779-800：`request.state.batch_mode=True` → 循环 → 统一 `db.commit()`；异常 `db.rollback()` + 409「批量人工复核已整体回滚」 | **整批回滚，无逐条容错** |

### 外网

| 检查项 | 证据 | 结论 |
|---|---|---|
| 批量「采用 AI 展示」 | `ForeignAIReviewView.vue` L14「确认选中采用 AI 展示」 | 已完成 |
| 单行 `use_ai_display` / `keep_rule` | L56-57 | 已完成 |
| **逐条容错** | `foreign.py` L1913-1943：`display_only={"use_ai_display","keep_rule"}`，每条 `db.begin_nested()` savepoint；失败回滚至 savepoint 并记入 `failed[]` 后 `continue`；正式决策（confirm/reject/complete）保持整批原子性 | **已完成（实现质量高）** |
| 返回结构 | `{items, total, failed, transaction}` | 已完成 |

**结论**：外网的逐条容错实现是当前代码库中的正确范式；**国内应对齐外网**（Phase 3）。

---

## 8. AI 预览是否调用 AI 的结论

| 检查项 | 国内 `_batch_preview` | 外网 `_foreign_ai_batch_preview` |
|---|---|---|
| 是否调用 AI 模型 | **不调用**（仅 SELECT `DomesticAIResult`） | **不调用**（仅 `resolve_one()` 取 rule_risk） |
| 是否创建正式预警 | **不创建** | **不创建**（`evaluate` L372 `if dry_run:` 跳过建 alert） |
| 是否仅统计已有结果 | 是（`status=='completed'` + 已启用规则阈值） | 部分：`possible_alert_count` 由 `_preview_foreign_candidate_count` 纯只读统计；但流程内**额外调用**了两个带副作用的服务 |
| 按 `opinion_id` 去重 | `count(distinct DomesticAIResult.opinion_id)` ✅ | `matched: set[int]`，规则命中与 AI 命中共用同一 set ✅ |
| 国内是否仍硬编码 0 | **否**，`_preview_domestic_alert_count` 已真实统计（异常时才回退 0） | — |
| 外网是否用错误数据源 | — | 主口径已改为 `_preview_foreign_candidate_count`（规则风险 + AI 分双路，正确）；`evaluate` 结果仅作异常兜底 |

### ⚠️ 外网预览的写库副作用（NON-BLOCKING，但需在 Phase 2 处理）

`api/foreign.py` L1364-1372：

```python
ForeignEventService().rebuild_candidates(
    db, user_id=None, dry_run=True, opinion_ids=[...], commit=True
)
```

- `foreign_event_service.py` L635 `if not dry_run:` → dry_run 下不写候选实体 ✅
- 但 L655 `run.status = "dry_run"`、L657-658 `if commit: db.commit()` → **写入并提交一条 run 审计记录**

`api/foreign.py` L1377-1382：

```python
alert_run = ForeignAlertService.evaluate(db, user_id=None, dry_run=True, max_items=200, opinion_ids=[...])
```

- `foreign_alert_service.py` L290 `run_type="dry_run"` → **写入一条 `foreign_alert_runs` 记录**

**影响**：预览会污染 run 审计表，并在请求中途 `commit()` 提交请求级事务（打断调用方的事务边界）。
不违反「不创建正式预警」与「不调用 AI」两条硬边界，但违反「仅统计已有结果」的最小副作用原则。
`possible_event_count` 依赖 `rebuild_candidates`，Phase 2 需改为纯只读统计后才能移除该调用。

---

## 9. 国内预警处置审计结论（C-1）

| 检查项 | 证据 | 结论 |
|---|---|---|
| `status` 实际允许值 | `api/alerts.py` L79 `_ALLOWED_ALERT_STATUSES = {pending, processing, resolved, ignored, false_positive}` | 5 态完整 |
| 处置接口 | L240 `PUT /alerts/records/{record_id}/handle`，body `{status, note}`；无 body 时兼容为 `{status:"resolved", note:""}` | 已完成 |
| 弹窗状态选项与中文文案 | `Alerts.vue` L87：待处理 / 处理中 / 已解决 / 已忽略 / 误报 | 已完成（**作为国内外统一文案基准**） |
| 备注字段写入位置 | L287 `rec.status`/`rec.handled = new_status in _RESOLVED_STATES`/`rec.handle_note = req.note or ""` | 已完成 |
| 备注能否被列表读取 | `_alert_record_payload` L43 输出 `handle_note` → API 已返回 | 后端完成 |
| 备注是否在列表展示 | 国内表格 9 列**无备注列**（仅弹窗回填 L148 `handleForm.note = row.handle_note`） | **当前缺失** |
| **禁止流转约束** | L89-98 `_FORBIDDEN_DOMESTIC_TRANSITIONS`：`(pending→false_positive)`、`(pending→ignored)`、`(resolved→ignored)`、`(resolved→false_positive)`、`(ignored→resolved)`、`(false_positive→resolved)`；L264-270 命中即 **409** | **与最新要求冲突，必须删除** |
| 列表列定义完整性 | 序号 / 触发规则 / 正式记录风险 / 关联舆情当前风险 / 关联舆情 / 触发原因 / 处置状态 / 触发时间 / 操作（处置）= 9 列 | 缺备注列 |
| 隐藏误报 | L54 `el-switch v-model="hideFalsePositive"`（L111 默认 `true`）→ L130 `params.exclude_status='false_positive'` → 后端 L204-217 校验并过滤 | **已完成（外网应复用此范式）** |
| `alert_records.status` 语义 | 未被改动 | 符合要求 |

---

## 10. 外网预警处置审计结论（C-2）

| 检查项 | 证据 | 结论 |
|---|---|---|
| `foreign_alerts.status` 是否仍为生命周期 | 模型 L20-21 CHECK `triggered/acknowledged/resolved/suppressed/failed`；DB 实测一致 | **是，语义正确** |
| `disposition_status` 是否存在 | 模型 L46-50 CHECK + L79-81 `Mapped[str]` + L50 索引；DB 实测存在 | **模型与 DB 存在** |
| 五态是否完整 | `pending / processing / resolved / ignored / false_positive` | 完整 |
| 处置 API 当前参数 | `POST /{id}/acknowledge`、`POST /{id}/resolve`、`POST /{id}/suppress`（各自独立端点，仅 note） | 仅旧 lifecycle 动作 |
| 是否有统一 handle 端点 | **无** `PUT /foreign/alerts/{id}/handle` | **当前缺失** |
| 是否支持旧 status 参数兼容 | 列表 `status` 参数存在并校验 5 态生命周期（L203-206） | 存在（应改造） |
| `set_disposition()` | `foreign_alert_service.py` 中计数 **0** | **当前缺失** |
| 非法状态流转限制 | `transition()` 存在（lifecycle 层）；**无 disposition 流转矩阵** | 符合「不新增禁止流转」 |
| `ignored` / `false_positive` 区分 | DB CHECK 已列为独立值；无代码消费 | 结构已具备 |
| `false_positive` 是否被 `suppressed` 替代 | 尚无 disposition 代码，不存在错误映射 | 待实现时保证 |
| 处置备注是否单独保存 | **无 `disposition_note` 列**（模型、DB 双重确认缺失）；仅 `foreign_alert_disposition_actions.note` | **当前缺失** |
| disposition 审计 | 表存在（`id/foreign_alert_id/previous_disposition/new_disposition/note/actor_id/created_at/metadata`），**零代码引用** | **部分完成** |
| 默认隐藏误报 | **无**（外网筛选无该开关） | **当前缺失** |
| 是否已删除生命周期状态筛选 | **未删**，`Alerts.vue` L58 仍有 5 个 lifecycle 选项 | **当前缺失** |
| 来源筛选实现 | `foreign_alerts.py` L210 `ForeignAlert.source_name_snapshot == source`（精确匹配）；前端 L60 文本输入 | **仍为精确匹配** |
| 操作列 | 详情 / 处置历史 / 确认 / 解决 / 抑制 = **5 个按钮** | **当前缺失（应只留「处置」）** |
| `serialize_alert` 输出 | 34 个字段，**不含** `disposition_status` / `disposition_note` | **当前缺失** |

### `disposition` 关键字在后端的全量分布

```
11 backend/app/models/foreign_alert.py     <- 唯一出现位置
 0 backend/app/services/foreign_alert_service.py
 0 backend/app/api/foreign_alerts.py
 0 backend/app/core/permissions.py
```

`foreign:alerts:false_positive` 权限**已存在**（`permissions.py` L92，位于 `foreign:alerts:manage` 复合包内）。

**结论**：15-C 呈明确的三段式状态——
**数据库层 + 模型层 + 权限层已完成**，**服务层 / API 层 / 前端层 / 测试层全部缺失**。

---

## 11. `disposition_status` 当前状态

| 层 | 状态 | 证据 |
|---|---|---|
| 数据库列 | ✅ 存在 | `character varying`, `NOT NULL`, `DEFAULT 'pending'::character varying` |
| 数据库 CHECK | ✅ 存在 | `ck_foreign_alerts_disposition_status CHECK (disposition_status IN ('pending','processing','resolved','ignored','false_positive'))` |
| 数据库索引 | ✅ 存在 | `ix_foreign_alerts_disposition_status` |
| 审计表 | ✅ 存在 | `foreign_alert_disposition_actions`（8 列，含 `previous_disposition`/`new_disposition`/`note`/`actor_id`/`metadata`） |
| SQLAlchemy 模型 | ✅ 存在 | `models/foreign_alert.py` L46-50 / L79-81 / L124-152 |
| Alembic 迁移 | ⚠️ 存在但**未提交** | `foreign_alert_disposition_status.py`，`revision="foreign_alert_disposition_v1"`，`down_revision="p33_event_archived_merge_split"`，含 add_column + CHECK + index + 回填 UPDATE + create_table |
| 服务层 | ❌ 缺失 | 无 `set_disposition()` |
| API 层 | ❌ 缺失 | 21 个端点均无 disposition |
| 序列化 | ❌ 缺失 | `serialize_alert` 不输出 |
| 前端 | ❌ 缺失 | `Alerts.vue` 无引用 |
| 备注列 `disposition_note` | ❌ 不存在（模型与 DB 均无） | 需新增列或改用 audit 表最新 note |
| 生产数据 | `foreign_alerts` 表当前无待迁移数据（历史数据不恢复，按用户决定） | — |

---

## 12. 外网 lifecycle status 当前状态

| 项 | 值 | 结论 |
|---|---|---|
| CHECK 约束（DB 实测） | `triggered / acknowledged / resolved / suppressed / failed` | 5 态，含 `failed` |
| 模型定义 | `String(16)`, `NOT NULL`, `default/server_default='triggered'` | 一致 |
| 索引 | `ix_foreign_alerts_status` | 存在 |
| 语义 | 生命周期（由评估引擎与 acknowledge/resolve/suppress 驱动） | **保持不变，符合最新要求** |
| 时间戳/操作人字段 | `acknowledged_at/by`、`resolved_at/by`、`suppressed_at/by`、`failure_reason` | 齐备 |
| lifecycle 审计 | `ForeignAlertAction` + `serialize_action`（`previous_status`/`new_status`/`note`） | 已完成，与 disposition 审计表并列 |
| `failed` 是否应禁止人工处置 | **依据**：`failed` 由评估异常写入（`failure_reason` 非空），不代表业务事实，人工处置无意义且会掩盖故障。建议**仅**对 `failed` 保留「不可人工处置」限制，不扩大为状态流转矩阵 | 待用户裁定 |

---

## 13. 备注字段与备注展示链路

| 侧 | 存储 | API 输出 | 列表展示 | 弹窗 | 结论 |
|---|---|---|---|---|---|
| 国内 | `alert_records.handle_note`（`PUT .../handle` 写入） | ✅ `_alert_record_payload` L43 | ❌ 无备注列 | ✅ L87 处置备注 textarea；L148 回填 | **部分完成**（缺列表列） |
| 外网 | ❌ 无 `disposition_note` 列；仅 `foreign_alert_disposition_actions.note`（无代码写入） | ❌ | ❌ | ❌ 无处置弹窗 | **当前缺失** |

**外网备注的两种可选实现（Phase 4 需选定）**：

1. **新增 `foreign_alerts.disposition_note` 列**（需要新 migration）—— 列表读取最简单，与国内 `handle_note` 对称，推荐。
2. **不加列，读取 `foreign_alert_disposition_actions` 最新一条 note** —— 无需 migration，但列表需 lateral join 或额外查询。

**明确要求**：外网备注列必须只显示处置备注文本本身，**不得根据 `disposition_status` 自动生成文案**。

---

## 14. 隐藏误报实现情况

| 侧 | 开关 | 默认值 | 请求参数 | 后端支持 | 结论 |
|---|---|---|---|---|---|
| 国内 | `Alerts.vue` L54 `el-switch v-model="hideFalsePositive"` | `true`（L111） | L130 `exclude_status='false_positive'` | `alerts.py` L192/L204-206 校验 + L216-217 `where status != exclude_status` | **已完成** |
| 外网 | ❌ 无开关 | — | ❌ | ❌ 列表无 disposition 过滤参数 | **当前缺失** |

外网实现应复用国内范式：默认隐藏 `false_positive`，开关关闭时显示全部。
注意 `ignored`（已忽略）**必须始终可见**，不得被隐藏误报开关一并过滤。

---

## 15. 外网筛选项与操作列实现情况

### 当前外网筛选区（`Alerts.vue` L57-62）

| 筛选项 | 当前实现 | 目标 |
|---|---|---|
| 状态（生命周期） | `el-select`：待确认/已确认/已解决/已抑制/失败 → `params.status` | **删除** |
| 严重度 | 低/中/高/紧急 → `params.severity` | 保留 |
| 来源 | `el-input` 文本 → `params.source`（后端精确匹配 `source_name_snapshot`） | 保留（精确匹配现状确认） |
| 日期范围 | `triggered_from`/`triggered_to` | 保留 |
| 处置状态（disposition） | **不存在** | **新增 5 态筛选** |
| 隐藏误报 | **不存在** | **新增开关（默认开）** |

### 当前外网操作列（`Alerts.vue` L69 末列，`min-width="280"`）

| 按钮 | 条件 | 目标 |
|---|---|---|
| 详情 | 无条件 | **删除** |
| 处置历史 | 无条件 | **删除** |
| 确认 | `row.status === 'triggered'` | **删除** |
| 解决 | `status ∈ {triggered, acknowledged}` | **删除** |
| 抑制 | `status ∈ {triggered, acknowledged}` | **删除** |
| **处置** | — | **新增（唯一按钮，打开与国内一致的处置弹窗）** |

### 当前外网表格列（9 列）

`ID / 触发规则 / 正式记录风险 / 关联舆情当前风险 / 关联舆情 / 触发原因 / 处置状态(lifecycle) / 触发时间 / 操作`

目标列结构（与国内对齐）：
`ID / 触发规则 / 正式记录风险 / 关联舆情当前风险 / 关联舆情 / 触发原因 / 生命周期状态(只读展示) / 处置状态(disposition) / 处置备注 / 触发时间 / 操作(处置)`

### 页面健康度检查

| 检查项 | 结果 |
|---|---|
| 游离模板文本 | 未发现 |
| setup 顶层裸语句 | 未发现（L111-112 为正常 `ref`/`reactive` 声明） |
| 未定义变量导致空白 | 未发现；`Alerts.vue` 为 157 行紧凑单行模板风格，语法完整 |
| 国内处置弹窗可否打开 | 可以（L148 `openHandleDialog` → `handleDialogVisible=true`） |
| 外网处置弹窗 | **不存在**（外网走 `handleForeign(row, action)` 直接调用） |
| 备注提交后能否重查显示 | 国内：后端已持久化且 API 已返回，但列表无列 → **不可见**；外网：无链路 |

---

## 16. 数据库 schema 与 migration 差异

### Alembic 版本状态（只读实测）

```
opinion_db (127.0.0.1:5432)
alembic_version 行数 = 1
alembic_version = d6_ai_review_consolidation
```

### 版本链验证

```
foreign_alert_disposition_v1  (foreign_alert_disposition_status.py, down=p33_event_archived_merge_split)
        ↓ 被引用
p34_foreign_event_status_unify (down=foreign_alert_disposition_v1)
        ↓ 被引用
d6_ai_review_consolidation     (down=p34_foreign_event_status_unify)  ← 数据库当前版本
```

**结论：数据库版本是 `foreign_alert_disposition_v1` 的后代，15-C 迁移已正确应用，
migration 与 DB schema 一致，无需任何 upgrade/downgrade。**

### schema 一致性核对

| 对象 | migration 声明 | DB 实测 | 模型声明 | 一致 |
|---|---|---|---|---|
| `foreign_alerts.disposition_status` | add_column, NOT NULL, server_default 'pending' | varchar NOT NULL DEFAULT 'pending' | `Mapped[str]` L79-81 | ✅ |
| `ck_foreign_alerts_disposition_status` | 5 态 CHECK | 5 态 CHECK | L46-48 | ✅ |
| `ix_foreign_alerts_disposition_status` | create_index | 存在 | L50 | ✅ |
| `foreign_alert_disposition_actions` | create_table + 2 CHECK + 2 index | 表存在，8 列 | L124-152 | ✅ |
| `ck_foreign_alerts_status` | — | 5 态含 failed | L19-21 | ✅ |
| `opinions.current_risk_*` | `current_risk_adoption_v1`（未提交） | 已应用 | L66-78 | ✅ |
| `foreign_alerts.disposition_note` | 未定义 | 不存在 | 未定义 | ✅ 一致地缺失 |

### 遗留问题

| 问题 | 级别 |
|---|---|
| 版本链中 `foreign_alert_disposition_status.py`、`p33`、`p34` 等 10 个迁移文件**未提交 Git** | **BLOCKING（数据安全）** |
| 生产 schema 与本地 migration 不一致 | 未发现 |
| 未提交 migration 与 model 不一致 | 未发现 |

---

## 17. 测试现状

### 后端测试（`backend/tests/`）

| 文件 | Git 状态 | 完整性 | 说明 |
|---|---|---|---|
| `test_foreign_alert_disposition.py` | `??` 未跟踪 | **损坏**（NUL=4126 / 26412 字节） | 15-C 声明的 38 用例；Git 全历史无副本，**必须重写** |
| `test_alert_operation.py` | `M` 已修改 | **损坏**（NUL=4114 / 17563 字节） | HEAD 版本完好（274 行 / 11335 字节），可用 `git show HEAD:...` 取出 |
| `test_domestic_ai_manual_review.py` | `??` 未跟踪 | 正常 | 国内 AI 复核 |
| `test_foreign_ai_manual_review.py` | `??` 未跟踪 | 正常 | 外网 AI 复核 |
| `test_foreign_ai_alert_cleanup.py` | 已提交 | 正常 | — |
| `backend/scripts/backfill_alert_snapshots.py` | `??` 未跟踪 | **损坏**（NUL=4092） | 属 ①B 回填脚本 → **SKIPPED BY USER DECISION**，无需修复 |

### 前端测试（`frontend/`）

| 文件 | 说明 |
|---|---|
| `frontend/src/views/foreign/foreignSourceStatus.test.ts` | **唯一**前端测试；与预警/复核无关 |

### 目标行为的测试覆盖

| 目标行为 | 是否有测试 |
|---|---|
| `current_risk_source` / `current_risk_score` 展示口径 | ❌ 无 |
| 批量采用 AI 展示 | 部分（`test_foreign_ai_manual_review.py` 需逐一核对用例） |
| 批量保留规则风险 | ❌ 无 |
| 预览不调用 AI | ❌ 无 |
| 预览不创建正式预警 | ❌ 无 |
| `disposition_status` 五态 | ❌ 测试文件已损坏 |
| `ignored` 与 `false_positive` 区分 | ❌ 无 |
| 备注持久化与列表展示 | 国内部分覆盖（`test_alert_operation.py`，但当前副本损坏） |
| 隐藏误报 | ❌ 无 |
| 国内回归 | `test_alert_operation.py`（损坏，HEAD 可恢复） |

---

## 18. 前端构建与部署现状（只读，未执行构建）

| 项 | 值 |
|---|---|
| `backend/app/static/assets` 文件数 | 164 |
| `index.html` 入口 | `assets/index-CL6LKzp8.js` + `assets/index-ByK17bbq.css` |
| Git 状态 | 已全部提交于 `9afe7de3`（2026-08-15 17:21） |
| Alerts chunk | 6 个，`disposition_status` 计数**全为 0** |
| 与源码是否同源 | **是**（源码 `Alerts.vue` 亦无 disposition） |
| `_chk.js` | 仓库根，80213 字节，未跟踪，为 **15-C 版 Alerts.vue 的编译产物**；依赖 `index-DR_DX6Dt.js`（仅存于 `backend/app/static.pre_frontend_recovery_20260814/assets/`） |
| `frontend/dist*` 备份 | 14 份未跟踪目录 |
| `.vite` 缓存 | 仓库根存在 `.vite/`；`frontend/node_modules/.vite` 需在构建前清理（历史踩坑：不清理会打包出陈旧模块） |

**关于 `_chk.js` 的处置立场**：本次为**重新实现**，不做机械恢复。`_chk.js` 仅可作为
**行为对照参考**（确认 15-C 曾实现的字段名、请求路径、文案），**严禁**作为源码直接还原或反编译落盘。
同时**严禁删除**该文件，它是 15-C 前端行为的唯一存活证据。

---

## 19. 需要重新实现的功能清单

| ID | 功能 | 缺口性质 |
|---|---|---|
| R1 | 国内列表按 `current_risk_source`/`current_risk_score` 展示，仅采用 AI 的行显示 AI 分与 AI 标识 | 前端消费层缺失 |
| R2 | 国内批量复核补「保留规则风险」 | 前端下拉项缺失（后端已支持） |
| R3 | 国内批量复核改为逐条容错（对齐外网 savepoint 范式） | 后端逻辑缺失 |
| R4 | 外网预览移除写库副作用（`rebuild_candidates(commit=True)` / `evaluate(dry_run)`） | 后端副作用清理 |
| R5 | 删除国内 `_FORBIDDEN_DOMESTIC_TRANSITIONS` 禁止流转约束 | 后端约束删除 |
| R6 | 外网 `set_disposition()` 服务 + disposition 审计写入 | 后端服务层缺失 |
| R7 | 外网统一处置 API（`PUT /foreign/alerts/{id}/handle`） + 列表 `disposition_status` / `disposition_filter` 参数 | 后端 API 缺失 |
| R8 | `serialize_alert` 输出 `disposition_status` + 处置备注 | 后端序列化缺失 |
| R9 | 外网处置备注存储（新增 `disposition_note` 列或读 audit 表最新 note） | 需决策，可能涉及 migration |
| R10 | `Alerts.vue` 国内表格新增「处置备注」列 | 前端缺失 |
| R11 | `Alerts.vue` 外网表格重构：双状态列 + 备注列 + 操作列只留「处置」 | 前端缺失 |
| R12 | 外网处置弹窗（复用国内 5 态中文文案） | 前端缺失 |
| R13 | 外网删除生命周期状态筛选项，新增 disposition 筛选 + 隐藏误报开关（默认开） | 前端缺失 |
| R14 | 提交全部未跟踪核心源码与迁移文件到 Git | 工程治理（BLOCKING） |
| R15 | 修复 `test_alert_operation.py`（从 HEAD 取回）、重写 `test_foreign_alert_disposition.py` | 测试缺失 |
| R16 | 补齐目标行为测试（展示口径 / 批量 / 预览 / 五态 / 备注 / 隐藏误报） | 测试缺失 |
| R17 | 构建 + 同步 static + 重启 + 运行验证 | 部署 |
| R18 | 重新采集数据积累 | 运营 |
| — | ①B 历史预警快照回填 | **SKIPPED BY USER DECISION** |

---

## 20. 每项功能对应的文件清单

| ID | 预计修改文件 |
|---|---|
| R1 | `frontend/src/types/index.ts`（`Opinion` 接口加 `current_risk_source`/`current_risk_score`/`current_risk_level`/`current_risk_updated_at`）、`frontend/src/views/Opinions.vue`（L196/L199 风险列） |
| R2 | `frontend/src/views/Opinions.vue`（L241 批量下拉加 `keep_rule`） |
| R3 | `backend/app/api/domestic_ai_analysis.py`（L779-800 `decide_reviews_batch`） |
| R4 | `backend/app/api/foreign.py`（L1343-1408 `_foreign_ai_batch_preview`）；可能需 `backend/app/services/foreign_event_service.py` 增加纯只读计数入口 |
| R5 | `backend/app/api/alerts.py`（删 L89-98 常量 + L263-271 校验） |
| R6 | `backend/app/services/foreign_alert_service.py`（新增 `set_disposition()`，写 `ForeignAlertDispositionAction`） |
| R7 | `backend/app/api/foreign_alerts.py`（新增 handle 端点；L181-232 列表加 `disposition_status`/`disposition_filter`） |
| R8 | `backend/app/services/foreign_alert_service.py`（`serialize_alert` L604-638）、`backend/app/schemas/foreign_alert.py` |
| R9 | 方案 1：新建 `backend/alembic/versions/<new>_foreign_alert_disposition_note.py` + `backend/app/models/foreign_alert.py`；方案 2：仅改 `foreign_alert_service.py` 查询 |
| R10 | `frontend/src/views/Alerts.vue`（L64-66 国内表格） |
| R11 | `frontend/src/views/Alerts.vue`（L68-70 外网表格） |
| R12 | `frontend/src/views/Alerts.vue`（新增外网处置弹窗，参照 L87 国内弹窗） |
| R13 | `frontend/src/views/Alerts.vue`（L57-62 筛选区 + L112 `foreignFilters` + L131 `loadForeignRecords`） |
| R14 | 3.2 节列出的 22 个后端 + 5 个前端文件 |
| R15 | `backend/tests/test_alert_operation.py`、`backend/tests/test_foreign_alert_disposition.py` |
| R16 | `backend/tests/`（新增用例）、可选 `frontend/src/views/__tests__/` |
| R17 | `frontend/dist` → `backend/app/static`（node 脚本同步） |
| R18 | 无代码改动 |

---

## 21. 每项功能的风险等级

| ID | 风险 | 理由 |
|---|---|---|
| R14 | **高** | 涉及 27 个从未提交的核心文件；一旦操作失误将永久丢失国内 AI 复核链路与 15-C 迁移 |
| R9 | **高** | 若选方案 1 需新建 migration 并对数据库执行 DDL，需用户明确批准 |
| R7 | 中 | 新增端点 + 修改列表契约，影响前端调用 |
| R6 | 中 | 新增服务函数并写审计表，需保证 `ignored`/`false_positive` 不被 `suppressed` 替代 |
| R11 | 中 | `Alerts.vue` 为 157 行紧凑单行模板，改动易引入语法错误导致页面空白 |
| R3 | 中 | 事务语义变更（整批→savepoint），需保证正式决策仍原子 |
| R4 | 中 | 移除 `rebuild_candidates` 会改变 `possible_event_count` 来源，需先实现只读统计 |
| R5 | 低 | 纯删除约束，放宽而非收紧 |
| R1 / R2 / R10 / R12 / R13 | 低 | 前端展示层改动，后端契约已就绪 |
| R8 | 低 | 追加输出字段，向后兼容 |
| R15 / R16 | 低 | 仅测试代码 |
| R17 | 中 | 会覆盖当前 164 个已提交产物并中断服务；需清 `.vite` 缓存后构建 |
| R18 | 低 | 运营动作 |

---

## 22. 推荐实施顺序

```
Phase 0  只读审计与需求矩阵                       ← 本报告，已完成
Phase 0.5 ⚠️ 先提交未跟踪核心源码（R14）           ← 强烈建议插入，作为所有后续改动的安全基线
Phase 1  国内风险展示口径（R1）
Phase 2  批量 AI 预览真实化与副作用清理（R4）
Phase 3  国内/外网 AI 批量复核对齐（R2, R3）
Phase 4  外网统一 disposition 后端（R6, R7, R8, R9）+ 删除禁止流转（R5）
Phase 5  Alerts.vue 表格/处置/备注/隐藏误报（R10, R11, R12, R13）
Phase 6  后端与前端测试（R15, R16）
Phase 7  构建、静态部署、重启与运行验证（R17）
Phase 8  重新采集数据积累（R18）
①B      历史预警快照回填                          SKIPPED BY USER DECISION
```

排序依据：先建立 Git 安全基线 → 再做无依赖的前端展示层 → 再清理后端副作用 →
再做后端契约（disposition）→ 前端消费该契约 → 测试 → 部署 → 数据。
R5（删除禁止流转）归入 Phase 4，因其与外网 disposition 的「不新增流转矩阵」原则同属一次口径统一。

---

## 23. 可独立验收与回滚的 Phase 划分

| Phase | 交付物 | 验收方式 | 回滚点 |
|---|---|---|---|
| 0.5 | 一个「保存未提交工作」的提交 | `git status --porcelain \| grep -c "^??"` 显著下降；`git show --stat HEAD` 含 27 个核心文件 | 该提交的父 commit `9afe7de3`；`git revert` 而非 reset |
| 1 | `types/index.ts` + `Opinions.vue` | 采用 AI 展示后列表显示 AI 分并带 AI 标识；未研判行仍显示规则分且无标识 | `git diff` 仅 2 文件，可单文件 checkout 该 2 文件 |
| 2 | `foreign.py` 预览函数 | 调 `POST /foreign/ai-analysis/batch/preview` 前后 `select count(*) from foreign_alert_runs` **不变** | 单文件回滚 |
| 3 | `Opinions.vue` + `domestic_ai_analysis.py` | 批量下拉出现「保留规则风险」；混入一条无 AI 结果的记录后，其余仍成功且返回 `failed[]` | 单文件回滚（2 文件） |
| 4 | `foreign_alert_service.py` + `foreign_alerts.py` + `schemas/foreign_alert.py` + `alerts.py`（+ 可选 migration） | `PUT /foreign/alerts/{id}/handle` 五态均可设置；`ignored` 与 `false_positive` 互不映射；`foreign_alert_disposition_actions` 新增一行；国内 `pending→false_positive` 不再返回 409 | 代码单文件回滚；**若新增 migration，回滚点 = `alembic downgrade d6_ai_review_consolidation`**，需事前 `pg_dump` |
| 5 | `Alerts.vue` | 外网筛选无生命周期项、有 disposition 项与隐藏误报开关（默认开）；操作列仅「处置」；国内外均有处置备注列且显示备注原文；提交备注后刷新可见 | 单文件回滚 |
| 6 | `backend/tests/*` | `pytest backend/tests/test_alert_operation.py backend/tests/test_foreign_alert_disposition.py` 全绿 | 仅测试文件，回滚无风险 |
| 7 | `backend/app/static/*` | `curl http://127.0.0.1:8000/assets/<新 Alerts chunk> \| grep -c disposition_status` > 0；浏览器实测预警页 | 部署前整体备份 `backend/app/static` → `static.bak.<ts>`；回滚即目录还原 |
| 8 | 采集数据 | `select count(*) from foreign_alerts` 增长 | 无需回滚 |

**关键验证纪律（本项目历史踩坑，务必遵守）**：

1. 验证 static 内容**必须用 `curl` 打真实服务**，不可只用 bash 读文件（沙箱 overlay 会返回陈旧层）。
2. `vite build` **前必须** `rm -rf frontend/node_modules/.vite frontend/node_modules/.cache`。
3. 构建 OOM 时用 `node.exe --max-old-space-size=1400 node_modules/vite/bin/vite.js build`，并先停 uvicorn。
4. `dist` → `static` 同步用 node 脚本（`fs.copyFileSync`），不可依赖 bash cp 的可见性。
5. 数据库连接统一用 `127.0.0.1`，**不可用 `localhost`**（PG 仅监听 IPv4）。

---

## 24. BLOCKING 问题

| # | 问题 | 影响 | 需要的决策/动作 |
|---|---|---|---|
| B1 | **27 个核心源码/迁移文件从未提交 Git**（含 `current_risk.py`、5 个 domestic AI 模型、`foreign_manual_review_service.py`、10 个 Alembic 迁移含 15-C） | 任何 `git reset --hard` / `restore` / `clean -fd` / `stash` 将**永久销毁**国内 AI 复核链路与 15-C 迁移；Alembic 版本链在其他环境无法重建 | **请批准 Phase 0.5：先提交这批文件**（仅 `git add` + `git commit`，不改任何内容）。这是后续所有实施的安全前提 |
| B2 | 外网处置备注**无存储位置** | R9 无法在不决策的情况下实施 | 请选择：**方案 1** 新增 `foreign_alerts.disposition_note` 列（需新 migration + DDL，与国内 `handle_note` 对称，推荐）；或**方案 2** 读 `foreign_alert_disposition_actions` 最新 note（无 DDL，查询稍复杂） |
| B3 | `failed` 状态是否禁止人工处置未定 | 影响 R6/R7 的校验实现 | 请裁定：建议**仅**禁止 `failed` 的人工处置（依据：由评估异常写入，`failure_reason` 非空，处置会掩盖故障），且不引入任何状态流转矩阵 |

以上三项均为**决策型**阻塞，不是技术不可行，也不是无法读取工作区。故整体结论仍为 `AUDIT_COMPLETE`。

---

## 25. NON-BLOCKING 问题

| # | 问题 | 建议 |
|---|---|---|
| N1 | 外网预览调用 `rebuild_candidates(commit=True)` 与 `evaluate(dry_run=True)`，写入 run 审计记录并中途提交事务 | Phase 2 改为纯只读统计 |
| N2 | `test_alert_operation.py` 工作区副本损坏（NUL=4114） | Phase 6 用 `git show HEAD:backend/tests/test_alert_operation.py` 取回 |
| N3 | `test_foreign_alert_disposition.py` 损坏且 Git 无副本 | Phase 6 依 15-B 设计文档重写，不从 `_chk.js` 反推 |
| N4 | `backend/scripts/backfill_alert_snapshots.py` 损坏 | 属 ①B，**SKIPPED**，无需修复 |
| N5 | `backend/app/services/current_risk.py.corrupt-20260814` 残留 | 确认 `current_risk.py` 正常后可删（需批准） |
| N6 | 仓库根遗留 `_mem_append.js` / `_mem_append2.js` / `_t_kw.sql` / `_tmp_edit_events.py` / `_events_orig.vue` / `_fw_head*.vue` | 建议列入 `.gitignore` 或统一清理（需批准） |
| N7 | 14 份 `frontend/dist*` + 7 份 `backend/app/static.bak*` 备份目录占用空间 | 保留 `static.pre_frontend_recovery_20260814`（`_chk.js` 依赖），其余可归档（需批准） |
| N8 | 前端仅 1 个测试文件，预警/复核零前端测试 | Phase 6 视投入决定是否补 |
| N9 | 国内 `Opinions.vue` 未提交改动为权限常量改名（`domestic:ai:review:*` → `ai:review:*`） | 与 `Phase D6` 权限合并一致，随 Phase 0.5 一并提交 |
| N10 | 上次审计报告与工作记忆记录的 HEAD 为 `7cc8b6a1`，与当前 `9afe7de3` 不一致 | 已在本报告 §2 记录差异与原因，无需处理 |

---

## 26. 本阶段明确没有做的事情

以下操作在本次审计中**一律未执行**：

- ❌ 未修改任何既有源码文件（前端 `.vue`/`.ts`、后端 `.py` 全部零改动）
- ❌ 未修改数据库：无 `INSERT` / `UPDATE` / `DELETE` / `ALTER` / `CREATE`，仅执行 `SELECT` 与
  `information_schema` / `pg_constraint` 只读查询
- ❌ 未创建或执行任何 Alembic migration（未运行 `upgrade` / `downgrade` / `revision` / `stamp`）
- ❌ 未执行历史数据回填（①B 已标记 SKIPPED BY USER DECISION）
- ❌ 未修改生产数据
- ❌ 未执行前端构建（未运行 `npm run build` / `vite build`）
- ❌ 未同步 `backend/app/static`
- ❌ 未重启后端服务
- ❌ 未执行 `git reset` / `git restore` / `git checkout` / `git clean` / `git stash` / `git rebase`
  （Git 操作仅限 `status` / `log` / `diff` / `show` / `ls-tree` / `rev-parse` / `reflog` / `branch -vv`）
- ❌ 未整体覆盖 `frontend/src` 或 `backend/app/static`
- ❌ 未把 `_chk.js` 或任何旧编译产物作为源码恢复
- ❌ 未删除任何文件（含损坏文件、临时脚本、备份目录）
- ❌ 未实现本报告列出的任何功能（R1–R18 全部处于未实施状态）

本阶段**唯一的写操作**：创建本文件 `docs/Reimplementation_Audit_20260815.md`。

---

## 附录：重新实现需求矩阵

| ID | 功能 | 当前状态 | 目标状态 | 预计修改文件 | 是否涉及数据库 | 是否允许当前阶段实施 |
|----|------|----------|----------|--------------|----------------|----------------------|
| R14 | 提交未跟踪核心源码与迁移 | 27 个文件从未提交 | 全部纳入版本控制 | 见 §3.2 清单 | 否 | 否（待批准，建议最先做） |
| R1 | 国内列表 current_risk 展示口径 | 前端用 `risk_score`，`current_risk` 计数 0 | 读 `current_risk_score`；仅采用 AI 的行显示 AI 分与 AI 标识 | `types/index.ts`, `views/Opinions.vue` | 否 | 否（待批准） |
| R2 | 国内批量「保留规则风险」 | 批量下拉缺 `keep_rule` | 批量下拉含「保留规则风险」 | `views/Opinions.vue` | 否 | 否（待批准） |
| R3 | 国内批量逐条容错 | 整批 rollback + 409 | savepoint 逐条，返回 `failed[]` | `api/domestic_ai_analysis.py` | 否 | 否（待批准） |
| R4 | 外网预览移除写库副作用 | 调 `rebuild_candidates(commit=True)` + `evaluate(dry_run)` | 纯只读统计 | `api/foreign.py`, `services/foreign_event_service.py` | 否（消除写入） | 否（待批准） |
| R5 | 删除国内禁止流转约束 | `_FORBIDDEN_DOMESTIC_TRANSITIONS` 仍在 | 删除，仅保留状态值合法性校验 | `api/alerts.py` | 否 | 否（待批准） |
| R6 | 外网 `set_disposition()` | 计数 0 | 唯一写入口 + 审计写入 | `services/foreign_alert_service.py` | 否（写现有表） | 否（待批准） |
| R7 | 外网统一处置 API | 无 handle 端点、无 disposition 参数 | `PUT /foreign/alerts/{id}/handle` + 列表 disposition 筛选 | `api/foreign_alerts.py` | 否 | 否（待批准） |
| R8 | 序列化输出 disposition | `serialize_alert` 无该字段 | 输出 `disposition_status` + 备注 | `services/foreign_alert_service.py`, `schemas/foreign_alert.py` | 否 | 否（待批准） |
| R9 | 外网处置备注存储 | 无 `disposition_note` 列 | 方案 1 新增列 / 方案 2 读 audit 最新 note | 方案 1：新 migration + `models/foreign_alert.py`；方案 2：仅 service | **方案 1 = 是（DDL）**；方案 2 = 否 | 否（**需用户先选方案**） |
| R10 | 国内表格处置备注列 | 9 列无备注列 | 新增「处置备注」列 | `views/Alerts.vue` | 否 | 否（待批准） |
| R11 | 外网表格重构 | lifecycle 单状态列 + 5 按钮 | 双状态列 + 备注列 + 仅「处置」 | `views/Alerts.vue` | 否 | 否（待批准） |
| R12 | 外网处置弹窗 | 不存在 | 复用国内 5 态中文文案 | `views/Alerts.vue` | 否 | 否（待批准） |
| R13 | 外网筛选项调整 | 有 lifecycle 筛选、无隐藏误报 | 删 lifecycle，加 disposition 筛选 + 隐藏误报（默认开） | `views/Alerts.vue` | 否 | 否（待批准） |
| R15 | 修复/重写测试 | 2 个文件损坏 | 可运行且通过 | `tests/test_alert_operation.py`, `tests/test_foreign_alert_disposition.py` | 否 | 否（待批准） |
| R16 | 补齐行为测试 | 9 项目标行为基本无覆盖 | 关键行为均有用例 | `backend/tests/` | 否 | 否（待批准） |
| R17 | 构建与静态部署 | 当前产物为旧版（同源） | 含新功能的产物上线 | `frontend/dist` → `backend/app/static` | 否 | 否（待批准） |
| R18 | 重新采集数据 | `foreign_alerts` 无数据 | 通过采集积累 | 无 | 是（写业务数据） | 否（待批准） |
| ①B | 历史预警快照回填 | 脚本损坏 | — | — | — | **SKIPPED BY USER DECISION** |

---

## 最终结论

```
AUDIT_COMPLETE
```

本阶段未实现任何功能，已停止，等待下一步实施指令。

**建议的第一个动作**：批准 **Phase 0.5（R14）** —— 仅执行 `git add` + `git commit`，
把 27 个从未提交的核心源码与迁移文件纳入版本控制，为后续所有改动建立可回滚基线。
在此之前进行任何实施，都存在不可恢复的丢失风险。

同时请就 §24 的 **B2（外网备注存储方案）** 与 **B3（`failed` 是否禁止人工处置）** 给出裁定。

