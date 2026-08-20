# YuQing 系统只读审计报告

审计时间：2026-08-14
审计模式：只读（未修改任何文件、数据库、Git 状态、运行中服务）
审计范围：Git 与工作区 / 前端源码与构建产物 / 外网舆情 / 预警与 AI 复核 / 后端与数据库

---

## 0. 审计基线

| 项 | 值 |
| --- | --- |
| 分支 | `codex/recover-frontend-20260814` |
| HEAD | `7cc8b6a1` Phase 6A: repair foreign alert confirmed_event rule stale 'confirmed' status |
| main | `e56d3d61` |
| origin/main | `052bc034`（HEAD 领先 10 个提交，落后 0） |
| 工作区 | 41 个 M（已修改）、1301 个 D（已删除）、292 个 ??（未跟踪） |
| 服务 | 127.0.0.1:8000 LISTENING（pid 44900, uvicorn） |
| 数据库 | 5432 = opinion_db（开发库，pgdata）；5433 = opinion_test（测试库） |
| Alembic | `d6_ai_review_consolidation`（opinion_db 与 opinion_test 一致） |

### 0.1 关键取证方法说明

- **构建产物 mtime 不可用作时间证据**：沙箱 overlay 导致 `backend/app/static/**` 全部文件 mtime = 会话启动时间。本审计改用**内容指纹（md5）+ 引用链**（index.html → 入口 chunk → 页面 chunk）判定同源。
- **源码损坏检测**：使用 Node `fs` 直读扫描 NUL 字节（`Read` 工具会把损坏文件误判为二进制而拒读）。

---

## 1. 重大发现（先看这 5 条）

### 发现 1：Phase 15-C 从未进入任何 Git 提交

```
git log -S "disposition_status" --all   →  空
git log -S "set_disposition"    --all   →  空
git rev-list --all -- frontend/src/views/Alerts.vue（40 个提交，逐个 grep disposition_status）→ 全部 = 0
```

**结论：15-C 的全部改动（前端 + 后端）在 Git 全历史、所有分支中均不存在。** 15-C 只以「工作区未提交状态」存在过，因此任何 `git checkout` / `git restore` **都无法恢复 15-C**，反而会彻底覆盖残存痕迹。

### 发现 2：Alerts.vue 已被回退为 HEAD 旧版

`git status` 中 **`frontend/src/views/Alerts.vue` 不在 41 个 M 清单内** → 当前源码与 HEAD 完全一致 = 15-C 之前的旧版。交叉验证：

| 检查项 | 当前 Alerts.vue（157 行） |
| --- | --- |
| `disposition` 出现次数 | **0** |
| 外网侧操作列 | 仅 `acknowledge` / `resolve` / `suppress` 三动作 + `row.status` 生命周期 |
| 外网侧处置备注列 | 无 |
| 外网侧隐藏误报 | 无（仅国内侧有 `hideFalsePositive`） |
| 国内侧处置弹窗 | 有（5 态 + 处置备注，`PUT /alerts/records/{id}/handle`） |

### 发现 3：`_chk.js` 是 15-C 前端唯一存活证据

仓库根目录 `_chk.js`（未跟踪，1664 行 / 80213 字节）**是 15-C 版 Alerts.vue 的完整编译产物**，含全部 15-C 特征：

- `disposition_status`、`disposition_filter`、`disposition_note`
- 外网双状态处置列（lifecycle + disposition 并列）
- 外网处置备注列
- `PUT /foreign/alerts/{id}/handle` 调用
- 「前往外网人工复核中心」跳转

其依赖的入口 chunk `index-DR_DX6Dt.js` 仅存在于 `backend/app/static.pre_frontend_recovery_20260814/assets/`。

**该文件是重建 15-C 前端源码的唯一依据，属最高保护级别，严禁删除或覆盖。**

### 发现 4：当前部署产物与 HEAD 产物完全不同源

- 1301 个 D（已删除）**全部**位于 `backend/app/static/assets/`，无一个源码文件被删除。
- 当前 `backend/app/static/assets/` = 164 个文件（未跟踪的新产物）。
- HEAD 版 `static/index.html` 引用 `index-DGuAMy22.js`；当前 `static/index.html` 引用 `index-CL6LKzp8.js`。
- HEAD 提交内含 **64 个** Alerts chunk，但**不含** 15-C 报告声明的 `Alerts-C4xvxUQa.js` / `index-Dx3ovtSD.js`。
- 当前部署的 6 个 Alerts chunk **全部 md5 不同且 `disposition_status` 计数均为 0** → 当前线上跑的是旧版预警页。

**推论：HEAD 提交的 static 是一个完整、干净、可用 `git checkout` 一键恢复的回滚点**，但恢复会覆盖当前 164 个新产物，必须先备份。

### 发现 5：15-C 后端呈「三段式缺失」

| 层 | 文件 | Git 状态 | 15-C 特征 | 判定 |
| --- | --- | --- | --- | --- |
| 迁移 | `backend/alembic/versions/foreign_alert_disposition_status.py` | `??` | `revision="foreign_alert_disposition_v1"`, `down_revision="p33_event_archived_merge_split"` | 存在（未跟踪） |
| 模型 | `backend/app/models/foreign_alert.py` | `M` | 第 47-50 行 `ck_foreign_alerts_disposition_status`；第 77-79 行 `disposition_status`；第 125-151 行 `foreign_alert_disposition_actions` 表 | **完成** |
| 权限 | `backend/app/core/permissions.py` | `M` | 第 46-93 行含 `foreign:alerts:false_positive`（在 `foreign:alerts:manage` 复合内） | **完成** |
| 服务 | `backend/app/services/foreign_alert_service.py` | `M` | **无 `set_disposition`**；`serialize_alert`（第 604 行）输出**无** `disposition_status` / `disposition_note` | **缺失** |
| API | `backend/app/api/foreign_alerts.py` | `M` | 21 个端点中**无任何 disposition 端点**，无 `PUT /{id}/handle`，仅 acknowledge/resolve/suppress | **缺失** |
| 测试 | `backend/tests/test_foreign_alert_disposition.py` | `??` | **文件损坏**（26412 字节，NUL=4126，非文本） | **损毁** |

> 注：服务层与 API 层文件虽标记为 `M`，但其 `M` 来自其他阶段的改动，15-C 部分已被回退。

---

## 2. 结论矩阵

| 功能/需求 | 当前源码 | 当前构建 | Git/备份证据 | 数据库状态 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 外网舆情 `/foreign` 路由 + 导航 | ✅ `router/index.ts` 第 29-35 行定义 `/foreign`；`AppLayout.vue` 第 96/241/263-273/291/301 行含外网导航 | ✅ 引用链含 `ForeignWorkspace-TmRpbyD8.js` | ✅ 756cc8cd 目标已在 HEAD 内 | 不涉及 | **已完成** |
| 外网 7 个子页面 | ✅ `views/foreign/` 齐备（AIReview / CollectionLog / Events / Keywords / OpinionDetailModal / OpinionList / Sources + useForeignOpinion.ts） | ✅ 各 chunk 存在 | ✅ 已提交 | `foreign_opinions`=154 | **已完成** |
| 外网工作台三 Tab | ✅ `ForeignWorkspace.vue` tabs=[dashboard/opinions/events]，opinions 内嵌 ai-review 子页 | ✅ | ✅ 已提交 | — | **已完成** |
| 数据管理外网二级切换 | ✅ `DataManage.vue` 第 48-140 行内嵌 ForeignKeywords/Sources/CollectionLog View | ✅ | ✅ 已提交 | — | **已完成** |
| 国内 AI 复核「采用AI展示 / 保留规则风险」 | ✅ `Opinions.vue` 采用AI=2 / 保留规则=1 / review-view=2；`services/current_risk.py`（153 行）含 adopt_domestic_ai / sync_domestic_rule_if_not_ai_adopted / apply_review_decision | ✅ `Opinions-CIcokEmL.js` | ✅ 已提交 | `opinions.current_risk_source/score/level/updated_at` 列存在 | **已完成** |
| 外网 AI 复核「采用AI展示 / 保留规则风险」 | ✅ `ForeignWorkspace.vue` 第 416-417 / 1126-1128 行含 use_ai_display / keep_rule；`current_risk.py` 含 adopt_foreign_ai / sync_foreign_rule_if_not_ai_adopted | ✅ | ✅ 已提交 | `foreign_ai_results` 存在 | **已完成** |
| `current_risk_source` / `current_risk_score` **列表展示** | ❌ `Opinions.vue`：current_risk_source=0 / current_risk_score=0 / displayRiskScore=0 / domestic-risk-source=0；`types/index.ts` 的 Opinion 接口**无** current_risk_* 字段（仅 `CurrentRisk.source` 用于 linked_opinion_current_risk） | ❌ 产物同源于旧源码 | ⚠️ `schemas/opinion.py` 第 61-65 行 OpinionOut **已声明** current_risk_source/score/level/updated_at（默认 "rule"）；但 `api/opinions.py` 第 31-152 行列表 payload **不输出** current_risk_source | ✅ DB 列存在，`_current_risk_score_expression`（第 48-50 行）已在用 | **当前缺失**（链路三段断裂：DB✅ → schema✅ → API❌ → 前端types❌ → 前端展示❌） |
| 国内预警处置（5 态） | ✅ `Alerts.vue` 第 53/87/148/149 行：状态下拉 5 态 + 处置弹窗 + `PUT /alerts/records/{id}/handle` | ✅ | ✅ 已提交 | `alert_records`=**0 行** | **已完成**（无数据可验） |
| 国内处置备注 | ✅ `Alerts.vue` 第 87 行 `handleForm.note` textarea；第 148 行回填 `row.handle_note` | ✅ | ✅ 已提交 | — | **已完成** |
| 国内隐藏误报 | ✅ `Alerts.vue` 第 54 行 `hideFalsePositive` el-switch | ✅ | ✅ 已提交 | — | **已完成** |
| 国内禁止流转约束 | ⚠️ `api/alerts.py` 第 89-98 行 `_FORBIDDEN_DOMESTIC_TRANSITIONS` 仍在（禁 pending→ignored/false_positive、resolved→ignored/false_positive、ignored→resolved、false_positive→resolved） | ⚠️ | ✅ 已提交 | — | **无法确认**（与「去除禁止流转」需求相矛盾，需用户裁定） |
| 批量 AI 分析预览真实数量 | ✅ `api/domestic_ai_analysis.py` 第 216 行 `_preview_domestic_alert_count`；第 279 行 `possible_alert_count=` 调用 | ✅ | ✅ 已提交 | — | **已完成** |
| **15-C 外网双状态模型（DB/模型/权限）** | ✅ `models/foreign_alert.py` 第 47-50 / 77-79 / 125-151 行；`permissions.py` 第 46-93 行含 false_positive | — | ⚠️ 仅工作区 `M`，**从未提交** | ✅ `foreign_alerts.disposition_status` 列存在 + `foreign_alert_disposition_actions` 表存在 + CHECK 约束存在 | **部分完成** |
| **15-C 外网统一处置（服务/API）** | ❌ `foreign_alert_service.py` 无 `set_disposition`，`serialize_alert` 无 disposition 字段；`foreign_alerts.py` 21 端点无 disposition 端点 | ❌ | ❌ 全历史 `git log -S set_disposition` = 空 | 表/列已就绪但**无任何代码写入** | **已回退** |
| **15-C 外网处置前端（Alerts.vue）** | ❌ 源码 = HEAD 旧版（disposition=0，Alerts.vue 不在 M 清单） | ❌ 6 个 Alerts chunk 全部 disposition_status=0 | ⚠️ **仅 `_chk.js`** 存 15-C 完整编译产物（依赖 `index-DR_DX6Dt.js`，仅存于 `static.pre_frontend_recovery_20260814/`） | — | **已回退** |
| 15-C 外网处置备注 / 隐藏误报 / disposition_filter | ❌ 源码 0 命中 | ❌ | ⚠️ 仅 `_chk.js` 含 disposition_note / disposition_filter | `disposition_status` 列可承载 | **已回退** |
| 15-C 测试（38 用例） | ❌ `tests/test_foreign_alert_disposition.py` **二进制损坏**（NUL=4126） | — | ❌ 未跟踪且从未提交，Git 无副本 | — | **当前缺失**（不可 Git 恢复，需重建） |
| `tests/test_alert_operation.py` | ❌ 工作区损坏（NUL=4114，17563 字节） | — | ✅ **HEAD 版完好**（274 行 / 11335 字节，Phase 2-B.1 告警处置闭环） | — | **当前缺失**（可 Git 恢复） |
| `scripts/backfill_alert_snapshots.py` | ❌ 损坏（NUL=4092，11071 字节） | — | ❌ 未跟踪，Git 无副本 | — | **当前缺失**（需重建） |
| Alembic 迁移链一致性 | ✅ 迁移文件存在（`foreign_alert_disposition_v1`，down=p33，被 p34 引用） | — | `??` 未跟踪 | ✅ DB=`d6_ai_review_consolidation`（p33 → disposition_v1 → p34 → … → d6，链上已应用） | **已完成** |
| 预警页面数据可见性 | — | — | — | ❌ `alert_records`=0、`foreign_alerts`=0、`foreign_alert_rules`=0、`foreign_alert_disposition_actions`=0 | **无法确认**（页面空白同时受「代码缺失」与「数据为空」双重影响） |

### 2.1 数据库实测行数（只读 `select count(*)`，未做任何迁移或写入）

| 表 | 行数 |
| --- | --- |
| `opinions` | 52 |
| `foreign_opinions` | 154 |
| `alert_rules` | 1 |
| `alert_records` | **0** |
| `foreign_alerts` | **0** |
| `foreign_alert_rules` | **0** |
| `foreign_alert_disposition_actions` | **0** |
| `users` | 5 |

> 重要修正：此前记录中提到的「alert id=14 真实处置记录」在当前 `opinion_db` 中**已不存在**（`alert_records`=0）。该记录或位于测试库、或已被清理，需用户确认，本报告不据此推断。

---

## 3. 必须恢复的文件清单

按恢复难度分三档。

### A 档 — 可从 Git 直接恢复（低风险）

| 文件 | 当前问题 | 恢复来源 |
| --- | --- | --- |
| `backend/tests/test_alert_operation.py` | 工作区损坏（NUL=4114） | `git show HEAD:backend/tests/test_alert_operation.py`（274 行完好） |

### B 档 — 必须从 `_chk.js` 反向重建（中高风险，唯一依据）

| 文件 | 需重建内容 | 依据 |
| --- | --- | --- |
| `frontend/src/views/Alerts.vue` | 外网侧：`disposition_status` 双状态列、`disposition_filter`（all/hide_fp/only_fp，默认 hide_fp）、外网处置备注列、外网处置弹窗、隐藏误报开关、处置历史区分 lifecycle/disposition、`PUT /foreign/alerts/{id}/handle` 调用、`前往外网人工复核中心` 跳转 | `_chk.js`（80213 字节，唯一存活产物）+ `docs/Phase_Foreign-Alert-Status-15-B_Unified_Disposition_Design.md`（40890 字节，设计规范）+ `-15-C_Implementation_Report.md` |
| `frontend/src/types/index.ts` | AlertRecord / ForeignAlert 接口补 `disposition_status`、`disposition_note`；Opinion 接口补 `current_risk_source` / `current_risk_score` / `current_risk_level` / `current_risk_updated_at` | 同上 + `backend/app/schemas/opinion.py` 第 61-65 行 |

### C 档 — 必须按设计文档重写（无任何代码副本）

| 文件 | 需补内容 | 依据 |
| --- | --- | --- |
| `backend/app/services/foreign_alert_service.py` | 新增 `set_disposition()`（唯一处置写入口，内部调 `set_status(commit=False)` 协同同一事务）；`serialize_alert()` 补 `disposition_status` / `disposition_note` 输出 | `-15-B` 设计文档 + `-15-C` 实施报告 |
| `backend/app/api/foreign_alerts.py` | 新增 `PUT /foreign/alerts/{id}/handle`（接收 disposition_status + note）；`list_foreign_alerts` 支持 `disposition_filter`（all/hide_fp/only_fp，默认 hide_fp）与 disposition 精确筛选；false_positive 走 `foreign:alerts:false_positive` 权限 | 同上 |
| `backend/tests/test_foreign_alert_disposition.py` | 38 用例（合法/非法状态组合矩阵、set_disposition 事务、权限、筛选默认值） | `-15-C` 实施报告（声明 38 用例全通过） |
| `backend/scripts/backfill_alert_snapshots.py` | 快照回填脚本 | 需用户确认原始用途，Git 无副本 |
| `backend/app/api/opinions.py` | 列表 payload 输出 `current_risk_source` | `schemas/opinion.py` 已声明，仅需接线 |

### 状态映射规范（重建时必须严格遵守，来自 15-B/15-C）

合法组合（5 对）：`(triggered, pending)` / `(acknowledged, processing)` / `(resolved, resolved)` / `(suppressed, ignored)` / `(suppressed, false_positive)`

非法组合：`triggered+false_positive|ignored`、`resolved+ignored|false_positive`、`suppressed+resolved`、`failed+任意`

disposition → lifecycle 映射：`processing→acknowledged`、`resolved→resolved`、`ignored→suppressed`、`false_positive→suppressed`

⚠️ **`foreign_alert_disposition_actions.action_type` 的 CHECK 只接受 `('acknowledge','resolve','suppress')`** —— 写审计记录时 `action_type` 必须传**动作名**，不可传目标状态值（否则 IntegrityError → 500）。

---

## 4. 不应覆盖的文件清单（最高保护级别）

| 文件/目录 | 原因 |
| --- | --- |
| **`_chk.js`**（仓库根） | 15-C 前端**唯一**存活证据。删除即永久失去 15-C 前端实现细节 |
| `backend/app/static.pre_frontend_recovery_20260814/assets/index-DR_DX6Dt.js` | `_chk.js` 的入口依赖，用于确认 `_chk.js` 的构建上下文 |
| `docs/Phase_Foreign-Alert-Status-15-A_Audit.md`（29236） | 15-C 现状审计基线 |
| `docs/Phase_Foreign-Alert-Status-15-B_Unified_Disposition_Design.md`（40890） | 状态映射与权限的权威规范，C 档重写的唯一依据 |
| `docs/Phase_Foreign-Alert-Status-15-C_Implementation_Report.md`（10502） | 改动清单与验收标准 |
| `backend/alembic/versions/foreign_alert_disposition_status.py` | 未跟踪但 DB 已应用；删除会破坏 p33→p34 迁移链 |
| `backend/app/models/foreign_alert.py` | 工作区含 15-C 模型层，未提交；被覆盖即丢失 |
| `backend/app/core/permissions.py` | 工作区含 `foreign:alerts:false_positive`，未提交 |
| `backend/app/services/current_risk.py`（153 行完好版） | 已有 `current_risk.py.corrupt-20260814` 损坏副本，勿混淆或回退 |
| `backend/app/static/assets/` 当前 164 个文件 | 未跟踪；`git checkout` 会全部抹除，须先备份 |
| 所有 `??` 备份目录 | `static.bak*`（6 个）、`_static_trash_20260724_1749/`、`frontend/dist*/`（多份）、`audit-evidence/`、`_fw_*.vue`、`_events_orig.vue` |

### 🚫 绝对禁止的 Git 操作（会造成不可逆丢失）

```
git checkout .            git restore .           git reset --hard
git clean -fd / -fdx      git stash（含未跟踪时）  git rebase
```

理由：15-C 的模型层/权限层/迁移文件**全部处于未提交状态**，且 `_chk.js` 与全部备份目录为**未跟踪**。上述任一命令都会把系统打回 HEAD（15-C 之前），并**永久删除唯一的 15-C 证据**。

---

## 5. 推荐恢复顺序（含每步验证与回滚点）

原则：**先固化证据 → 再补后端 → 再补前端 → 最后构建部署**。每一步单独可回滚，禁止跨步合并。

### Step 0：证据固化（必须最先做，无风险）

- 操作：把 `_chk.js`、`static.pre_frontend_recovery_20260814/assets/index-DR_DX6Dt.js`、`docs/Phase_Foreign-Alert-Status-15-*.md`、当前 `backend/app/static/`（164 文件）整体复制到 `_recovery_evidence_20260814/`（新目录，不动原件）。
- 验证：`ls _recovery_evidence_20260814/` 逐项存在；`md5sum` 与原件一致。
- 回滚点：仅新增目录，删除该目录即完全回滚。

### Step 1：Git 基线快照（无风险）

- 操作：`git stash list` 确认为空后，**不做 stash**；改为 `git diff > _recovery_evidence_20260814/worktree_20260814.patch` 与 `git status --porcelain > _recovery_evidence_20260814/status_20260814.txt`。
- 验证：patch 文件非空且含 `models/foreign_alert.py`、`core/permissions.py` 的 disposition 相关 diff。
- 回滚点：`git apply -R` 可反向应用该 patch。

### Step 2：恢复 A 档损坏文件（低风险）

- 操作：`git show HEAD:backend/tests/test_alert_operation.py > backend/tests/test_alert_operation.py`（先把损坏版备份到 evidence 目录）。
- 验证：`python -c "compile(open(...).read(),'x','exec')"` 通过；Node NUL 扫描为 0；行数=274。
- 回滚点：evidence 目录中的损坏版原件（虽无价值，仍保留）。

### Step 3：补齐 15-C 服务层（中风险，先测后接）

- 操作：在 `foreign_alert_service.py` 新增 `set_disposition()`，并给 `serialize_alert()` 补 `disposition_status` / `disposition_note`。严格按第 3 节「状态映射规范」实现，`action_type` 只传动作名。
- 验证：`python -c "import app.main"` 无异常；对 5 对合法组合与 4 类非法组合写单测并跑通；`curl` 取 `/foreign/alerts` 列表确认 JSON 出现 `disposition_status`。
- 回滚点：Step 3 开始前对该文件做 `.pre_15c_restore` 副本。

### Step 4：补齐 15-C API 层（中风险）

- 操作：新增 `PUT /foreign/alerts/{id}/handle`；`list_foreign_alerts` 增 `disposition_filter`（默认 `hide_fp`）与 disposition 精确筛选；false_positive 挂 `foreign:alerts:false_positive`。
- 验证：`python -c "import app.routes"`；重启 uvicorn 后 `curl /openapi.json | grep handle`（注意：`/openapi.json` 经 SPA 中间件可能返回 404，属预知行为，应改用 Python 导入 + `curl` 打真实端点验证）；用 5 态逐一 PUT 验证合法/非法返回码。
- 回滚点：该文件 `.pre_15c_restore` 副本。

### Step 5：接通 `current_risk_source` 链路（低风险）

- 操作：`api/opinions.py` 列表 payload 输出 `current_risk_source`（schema 已声明，无需改 schema）；`types/index.ts` 的 Opinion 接口补 4 个字段；`Opinions.vue` 列表按 `row.current_risk_source==='ai'` 显示「AI」标识与 AI 分值，否则显示系统规则分且无标识。
- 验证：`curl /opinions?page=1` JSON 含 `current_risk_source`；前端列表 52 条数据中至少一条显示来源标识。
- 回滚点：三个文件各自 `.pre_restore` 副本。

### Step 6：重建 15-C 前端 Alerts.vue（最高风险）

- 操作：以 `_chk.js` 为唯一依据反向推导，对照 15-B 设计文档逐项补齐外网 disposition 双状态列、备注列、筛选器、处置弹窗、处置历史 lifecycle/disposition 区分。**国内侧代码已完好，禁止改动。**
- 验证：`grep -c disposition frontend/src/views/Alerts.vue` > 0；逐项对照 `_chk.js` 中的 6 个特征点确认无遗漏；`vite build` 无 TS 报错。
- 回滚点：Step 6 前 `cp frontend/src/views/Alerts.vue Alerts.vue.head_version`（= HEAD 旧版，可随时退回）。

### Step 7：构建与部署（高风险，须严守既有踩坑规则）

- 操作顺序（不可省略、不可换序）：
  1. 停止 uvicorn（`Stop-Process -Id <PID> -Force`）
  2. **`rm -rf frontend/node_modules/.vite frontend/node_modules/.cache`**（必须；否则 vite 会用陈旧 transform 缓存产出旧版）
  3. `cd frontend && vite build`（OOM 时用 `node.exe --max-old-space-size=1400 node_modules/vite/bin/vite.js build`）
  4. **用 Node 脚本**（`fs.copyFileSync`）把 dist 同步到 `backend/app/static`（先清旧资源）—— **禁止用 bash cp**，因 node 与 bash 处于不同 overlay 层
  5. `git flush index.html`（按既有流程）
  6. 重启 uvicorn
- 验证（必须用 `curl` 打真实 static，不可信 bash 读文件）：
  - `curl -s http://127.0.0.1:8000/ | grep -o 'assets/index-[A-Za-z0-9_-]*\.js'` 得到**新**入口 hash
  - `curl -s http://127.0.0.1:8000/assets/<新Alerts chunk>.js | grep -c disposition_status` **> 0**
  - 浏览器打开 `/alerts` 外网 Tab，确认双状态列 + 备注列 + 隐藏误报开关出现
- 回滚点：Step 0 已备份的当前 `backend/app/static/`（164 文件）整体覆盖回去即可；另有 HEAD 提交版 static 作为二级回滚点（`git checkout HEAD -- backend/app/static`，但**会抹除未跟踪产物**，仅在一级回滚失败时使用）。

### Step 8：重建测试（低风险）

- 操作：重写 `test_foreign_alert_disposition.py`（38 用例矩阵）；确认 `backfill_alert_snapshots.py` 的用途后重写或删除。
- 验证：`pytest backend/tests/test_foreign_alert_disposition.py -q` 全通过；测试须打测试库 `127.0.0.1:5433/opinion_test`（**URL 必须用 `127.0.0.1` 而非 `localhost`**）。
- 回滚点：损坏原件已在 evidence 目录留存。

---

## 6. 需要您明确批准的操作

以下操作**在本次审计中一律未执行**，需逐项获得您的确认：

| # | 操作 | 风险 | 为何需要批准 |
| --- | --- | --- | --- |
| 1 | 创建 `_recovery_evidence_20260814/` 并复制 `_chk.js` 等证据 | 极低 | 会新增文件（本次严格只读，未创建） |
| 2 | 覆盖 `backend/tests/test_alert_operation.py`（用 HEAD 版替换损坏版） | 低 | 覆盖工作区文件 |
| 3 | 修改 `foreign_alert_service.py` / `foreign_alerts.py`（补 15-C） | 中 | 改动未提交的工作区后端代码 |
| 4 | 修改 `api/opinions.py` + `types/index.ts` + `Opinions.vue`（接通 current_risk_source） | 中 | 涉及国内主列表展示逻辑 |
| 5 | 重写 `frontend/src/views/Alerts.vue`（15-C 前端重建） | **高** | 唯一依据是编译产物反推，存在细节偏差风险 |
| 6 | 执行 `vite build` + 同步 static + 重启 uvicorn | **高** | 会覆盖当前 164 个部署产物并中断服务 |
| 7 | **是否移除 `_FORBIDDEN_DOMESTIC_TRANSITIONS`** | 中 | `api/alerts.py` 第 89-98 行的禁止流转约束与您此前「去除禁止流转」的需求直接冲突。**必须您裁定**：保留约束，还是放开全部流转 |
| 8 | `alert_records`=0 / `foreign_alerts`=0 是否需要造测试数据 | 中 | 预警页空白的一半原因是无数据；是否写入测试数据需您同意（涉及开发库 5432 写操作） |
| 9 | 是否将 15-C 改动提交到 Git | 中 | 当前 15-C 全部未提交；建议恢复完成并验证后单独提交，避免再次丢失 |
| 10 | 是否清理 292 个 `??` 备份（`static.bak*`、`dist*` 等） | 低 | 会释放空间但降低回滚余地；建议恢复全部完成后再议 |

---

## 7. 与历史需求的总体对照

| 阶段/需求 | 结论 |
| --- | --- |
| 756cc8cd 外网舆情 `/foreign` 路由 + 7 子页面 | **已完成** |
| 国内/外网 AI 复核（采用AI展示 / 保留规则风险） | **已完成** |
| 批量 AI 分析预警预览真实数量 | **已完成** |
| 国内预警处置 + 处置备注 + 隐藏误报 | **已完成**（数据为空，功能未经真实数据验证） |
| `current_risk_source` / `current_risk_score` 列表展示 | **当前缺失** |
| 去除国内禁止流转约束 | **无法确认**（约束仍在，需裁定） |
| Phase 15-C 外网统一处置（双状态模型） | **部分完成**：DB/模型/权限/迁移 ✅；服务/API/前端 ❌（已回退）；测试 ❌（损毁） |
| 3 个源码文件完整性 | **当前缺失**：1 个可 Git 恢复，2 个需重建 |

---

## 8. 审计合规声明

本次审计全程只读，具体未执行清单：

- 未创建、修改、删除任何既有文件（本报告为唯一新增产物）
- 未执行任何 `git` 写操作（无 add / commit / checkout / restore / reset / clean / stash / rebase）
- 未执行任何 DB 写操作与 Alembic 迁移（仅 `select count(*)` 与 `select version_num`）
- 未启动、停止、重启任何服务（uvicorn pid 44900 保持原状）
- 未执行 `npm run build` / `vite build`

