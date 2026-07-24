# Risk Model V2 · Phase 2-B.1「告警处置闭环」实施前审计报告

> 模式：**Audit（只读）→ Design → 等待确认 → Implement**
> 本轮仅审计与设计，**未修改任何代码 / 数据库 / 迁移 / 前端 / 服务**。
> 生成时间：2026-07-24 · alembic head 已核实 = `p9phase2a101 (head)`

---

## 0. 结论速览

| 问题 | 结论 |
|---|---|
| **Phase 2-B.1 是否可以实施？** | ✅ **可以**。无阻断性问题，方案为纯附加式扩展。 |
| 是否影响 **0 token 自动风险链路**？ | ❌ 不影响（评分/等级/critical 逻辑一行不改；handle 是人工 API） |
| 是否影响 **AI 隔离**？ | ❌ 不影响（全程无 LLM/DeepSeek/AIService） |
| 是否影响 **RiskEngine 评分**？ | ❌ 不影响（RiskEngine 完全不在改动面内） |
| 是否影响 **历史风险数据**？ | ❌ 不影响（迁移仅 UPDATE `alert_records.status`，绝不触碰 `opinions`） |

> 未发现需要推翻设计的问题。以下为完整证据链与实施设计，**等待确认后再进入 Implement**。

---

## A. AlertRecord 当前实现审计

### A.1 当前模型结构（`models/alert.py`，实测）

`AlertRecord` 现有 **11 个字段**：

| 字段 | 类型 | 约束/默认 | 说明 |
|---|---|---|---|
| id | Integer | PK | |
| rule_id | Integer | **FK alert_rules.id**, index, not null | 触发规则 |
| rule_name | String(256) | not null | 规则名快照 |
| risk_level | String(32) | not null, **CheckConstraint** `IN (low,medium,high,critical)` | 派生等级 |
| opinion_id | Integer | **FK opinions.id**, index, **nullable** | 关联舆情 |
| opinion_title | String(512) | not null, default "" | 舆情标题快照 |
| event_id | Integer | **FK events.id**, index, **nullable** | 关联事件 |
| event_title | String(512) | not null, default "" | 事件标题快照 |
| **trigger_reason** | **Text** | not null, default "" | 触发原因（Phase 2-A.1 已增强 critical 文案） |
| **handled** | **Boolean** | **not null, default False** | 处理标记（当前仅 True/False） |
| created_at | DateTime | not null, default utcnow | |

- **关系确认**：仅有 3 个 **FK 列**（rule_id / opinion_id / event_id），**均未声明 ORM `relationship()`**（纯外键列）。**与 User 无任何关联**（当前处置不记录处理人）。
- **handled**：`Boolean, nullable=False, default=False`（Python 侧 default，无 server_default）。
- **trigger_reason**：`Text, nullable=False, default=""`。

### A.2 Phase 2-B.1 需要新增字段（设计，尚未实施）

| 新字段 | 类型 | 约束/默认 | 用途 |
|---|---|---|---|
| **status** | String(32) | not null, **server_default `'pending'`**, CheckConstraint `IN (pending,processing,resolved,ignored,false_positive)` | 处置状态机 |
| **handled_by** | Integer | **FK users.id**, nullable=True | 处理人（历史/系统为 NULL） |
| **handled_at** | DateTime | nullable=True | 处理时间 |
| **handle_note** | Text | nullable=True | 处置备注 |

### A.3 字段冲突风险

**无冲突**：
- 4 个新字段名与现有 11 字段无重名。
- 新 CheckConstraint 名 `ck_alert_records_status` 与既有 `ck_alert_records_risk_level` 不冲突。
- **`handled` 布尔列保留**（不删除）：现有 `GET /records?handled=` 过滤、`AlertRecordOut.handled`、前端"已处理/未处理"标签均依赖它。设计采用**双写**：处置时 `status` 与 `handled` 同步（`status ∈ {resolved,ignored,false_positive}` → `handled=True`），保证旧消费方零回归。

---

## B. AlertService 告警创建流程审计

### B.1 创建流程（`services/alert_service.py::evaluate`，实测）

- 遍历启用规则 → 按 `risk_threshold`/关键词/来源筛 `Opinion` → 去重（`rule_id + opinion_id` 已存在则跳过）→ 构造 `AlertRecord`。
- **字段来源**：`risk_level = _map_risk_level(opinion.risk_score)`（Phase 1 派生），`severity_score>=70 → critical`（Phase 2-A），正面误报保护（Phase 1），`trigger_reason` 拼装（含 Phase 2-A.1 critical 因子文案）。
- **构造时显式写** `handled=False`（line 137）。
- **是否依赖 handled**：评估逻辑**不读取** `handled`（去重键是 `rule_id+opinion_id`，与 handled 无关）。
- **是否存在自动更新 handled 的逻辑**：**无**。全仓仅 `PUT /handle` 一处把 `handled=True`，`evaluate` 从不回改。

### B.2 新增 status/handled_by/handled_at/handle_note 是否影响 `evaluate`

- 4 个新字段中，创建阶段只涉及 **status**；`handled_by/handled_at/handle_note` 是**处置阶段**才写，创建时保持 NULL。
- **status 初值**由 DB `server_default='pending'` 提供 → `evaluate` 的 `AlertRecord(...)` 构造**可零改动**；为可读性建议附加一行 `status="pending"`（**纯字段赋值，无任何逻辑分支**）。

### B.3 明确回答：「告警产生逻辑是否完全无需修改」

> **风险计算与等级判定逻辑（评分、_map_risk_level、severity≥70 critical、正面保护、trigger_reason 拼装）完全无需修改，一行不动。**
> 唯一可选变化是在 `AlertRecord(...)` 构造处附加 `status="pending"` 一行（或依赖 server_default 实现字面零改动）。两种方式均**不触碰任何评分/等级分支**。

---

## C. Alert API `handle` 调用链审计

### C.1 当前 `PUT /alerts/records/{id}/handle`（`api/alerts.py:126-134`，实测）

```
router: PUT /records/{record_id}/handle
  ├─ 依赖：require_permission("alerts:write")  ← 已有权限校验 ✅
  ├─ 参数：仅路径 record_id，无 body ✅
  ├─ 逻辑：rec.handled = True; db.commit(); db.refresh(rec)
  ├─ 响应：AlertRecordOut ✅
  ├─ 用户上下文：_u 已注入但被丢弃（未记录处理人）⚠️
  └─ audit_write：❌ 未调用
```

| 检查项 | 现状 |
|---|---|
| 请求参数 | 仅路径 `record_id`，**无请求体** |
| 响应结构 | `AlertRecordOut` |
| 权限校验 | ✅ 已有 `alerts:write` |
| 用户身份上下文 | ⚠️ 注入 `_u` 但未使用 → **处理人未落库** |
| audit_write | ❌ **缺失** |

### C.2 为什么 handle 没有 audit_write

同文件规则 CRUD（create/update/delete_rule）**全部**用 `audit_write` 包裹（CREATE/UPDATE/DELETE），**唯独 handle 例外**。判定：handle 是早期一键置位接口，写于审计标准化之前，属**审计覆盖遗漏**（非有意豁免）。Phase 2-B.1 应补齐。

### C.3 升级设计（向后兼容）

- 新增可选请求体（Pydantic）：`AlertHandleRequest { status: str = "resolved", note: str = "" }`。
- **旧调用兼容**：前端/脚本仍以**无 body** 调用 → FastAPI 用默认值 `status="resolved", note=""`，等价于旧 `handled=True` 行为；同步 `handled=True`、`handled_at=now`、`handled_by=当前用户`。→ **旧 API 无 body 调用仍 100% 兼容**。
- 状态机：`pending → processing → resolved / ignored / false_positive`（接口只校验目标值合法，不强制流转顺序，避免破坏简单场景）。
- 签名改造：`_u` → `current_user: User = Depends(require_permission("alerts:write"))`，并注入 `request: Request` 供审计。

---

## D. RBAC 与审计系统兼容检查

### D.1 handled_by 直接 FK users.id — ✅ 可行

`users` 表存在、`id` 为 PK。`handled_by = Integer + ForeignKey("users.id", nullable=True)` 可行；历史/系统写入为 NULL。**不建**声明反向 relationship（避免 User 模型改动），仅列级 FK。

### D.2 处置接口权限方案 — **推荐复用 `alerts:write`（不新增）**

- 权限目录（`rbac10001.py::_PERMISSIONS`）已含 `alerts:read` / **`alerts:write`**；**无 `alerts:handle`、无 `alerts:update`**。
- handle 语义上是「对预警的写操作」，与 `alerts:write` 一致。
- **推荐：复用 `alerts:write`**（当前 handle 已用它，零迁移、零角色重分配、零回归）。
- 若新增 `alerts:handle`：需 ①迁移插 permissions 行 ②给 admin/analyst 分配 role_permissions ③改 checker——**增加迁移面与回归风险，收益低**。**不推荐**。

### D.3 audit_log 记录方案 — ✅ 复用现有 `audit_write`

`OperationLog` 字段齐全（operator/action/resource_type/resource_id/details_json/result…）。设计：

```
action        = "HANDLE_ALERT"
resource_type = "alert_record"
resource_id   = str(record_id)
details       = { "alert_id": id, "old_status": <旧值>, "new_status": <新值>, "note": <备注> }
```

用 `with audit_write(db, action="HANDLE_ALERT", operator=current_user, request=request, resource_type="alert_record", resource_id=str(id), details={...}):` 包裹（与规则 CRUD 完全同构，失败自动回滚+记 failed）。

---

## E. 数据迁移风险审计

### E.1 迁移设计

- 文件：`p10_phase2b1_alert_operation.py`
- **down_revision = `p9phase2a101`** ✅（已核实当前唯一 head）
- upgrade：
  1. `ADD COLUMN status String(32) NOT NULL server_default 'pending'`
  2. `ADD COLUMN handled_by Integer NULL` + `FK alert_records.handled_by → users.id`
  3. `ADD COLUMN handled_at DateTime NULL`
  4. `ADD COLUMN handle_note Text NULL`
  5. `CREATE CHECK ck_alert_records_status IN (pending,processing,resolved,ignored,false_positive)`
  6. **数据回填 UPDATE**（见 E.2）
- downgrade：反向 drop constraint + 4 列。

### E.2 历史数据策略（回填 UPDATE）

| 旧值 | 新 status |
|---|---|
| `handled = True` | `'resolved'` |
| `handled = False / NULL` | `'pending'`（server_default 已覆盖，UPDATE 可省） |

实际只需一条：`UPDATE alert_records SET status='resolved' WHERE handled = true;`
- `handled_by / handled_at` 回填保持 **NULL**（诚实：历史无处理人/处理时刻数据，不臆造 created_at 冒充处理时间）。

### E.3 重点确认：该 UPDATE 是否安全

> ✅ **安全**。
> - 该 UPDATE **只写 `alert_records.status` 一列**，条件基于同表 `handled` 布尔，**完全不涉及 `opinions` 表**（风险数据零触碰，满足"禁止修改任何 opinion 风险数据"）。
> - `alert_records` 量级小（数十~数百行），单语句瞬时完成，无锁风险。
> - 幂等：status 有 server_default，重复执行结果一致。

---

## F. 前端 `Alerts.vue` 审计（本轮只读，改造留待 Implement）

### F.1 当前实现（实测）

- 「预警记录」Tab 表格列：序号 / 触发规则 / 预警等级 / 关联舆情 / 关联事件 / 触发原因 / **状态(handled 标签)** / 触发时间 / **操作(「标记处理」按钮)**。
- 过滤：`recFilterRisk`(等级) + `recFilterHandled`(bool 未处理/已处理)。
- 处置：`handleRecord()` → `api.put('/alerts/records/{id}/handle')`（**无 body**）→ 本地置 `rec.handled=true`。

### F.2 增量改造范围（不重构）

| 改动点 | 内容 |
|---|---|
| 状态列 | 由 handled 布尔标签升级为 5 态标签（pending/processing/resolved/ignored/false_positive） |
| 处置弹窗 | 新增 `el-dialog`：状态 `el-select` + 备注 `el-input textarea` |
| 处置调用 | `handleRecord` 改为打开弹窗 → PUT `{status, note}` |
| 类型 | `types` 的 `AlertRecord` 增 status/handled_by/handled_at/handle_note；新增 `AlertHandleRequest` |
| 兼容 | 保留 handled 标签逻辑或以 status 映射；`recFilterHandled` 可保留 |

- **结论**：组件为单文件、函数清晰，**适合增量修改，无需重构**。
- ⚠️ 本轮审计**未改前端**（遵守禁令）；上表为 Implement 阶段设计。

---

## G. 测试影响审计与测试计划

### G.1 现有测试盘点

- `test_rbac.py`：已有 `admin_headers` / `viewer_user` / `analyst_user` 夹具（`_make_user` 按 role 建号）。**viewer 仅读权限**，可直接用于"普通用户无权限"。
- `test_phase6_hardening.py`：已有 `audit_write` 成功/失败 + CRUD 审计断言范式（`OperationLog.filter(action=..., resource_type=..., resource_id=...)`）。
- **无 `test_alerts.py`**（告警 API 目前无专测）。
- 评分回归护栏：`test_risk_engine.py` / `test_phase1_risk_model.py` / `test_risk_explainability.py`。

### G.2 新增测试文件：`tests/test_alert_operation.py`

| # | 用例 | 断言 |
|---|---|---|
| 1 | 新告警默认状态 | `evaluate` 生成记录 `status == 'pending'` |
| 2 | 旧 API 无 body | `PUT /handle`（无 body）→ `status=='resolved'` 且 `handled==True` |
| 3 | 管理员处置带 body | `{status:'processing', note:'...'}` → `handled_by==uid`、`handled_at` 非空、`handle_note` 落库 |
| 4 | 普通用户无权限 | viewer 调用 `PUT /handle` → **403** |
| 5 | 审计记录 | 处置后 `OperationLog` 存在 `action='HANDLE_ALERT', resource_type='alert_record', resource_id=id`，details 含 old/new_status |
| 6 | evaluate 不变式 | 处置改造后，`evaluate` 的评分/risk_level/critical 派生与基线**逐字节一致**（复用现有风险用例断言） |

### G.3 执行计划

- 先测试库（`:5432/opinion_test`，`DB_IDENTITY_CHECK=off`，先 `alembic upgrade head` 到 p10）跑新增 + 相关回归。
- 再全量回归，对比**当前基线 163 passed / 14 failed / 11 errors**，记录新增失败与基线差异（预期新增 0 失败）。

---

## H. 影响文件清单（Implement 阶段，供确认）

| 文件 | 变更类型 | 内容 |
|---|---|---|
| `backend/app/models/alert.py` | 改 | AlertRecord +4 列 + CheckConstraint |
| `backend/app/schemas/alert.py` | 改 | `AlertRecordOut` +4 字段；新增 `AlertHandleRequest` |
| `backend/app/api/alerts.py` | 改 | `handle_record` 接 body + audit_write + handled_by/at/note；双写 handled |
| `backend/app/services/alert_service.py` | 改（极小） | `AlertRecord(...)` 附加 `status="pending"`（可选，**评分逻辑不动**） |
| `backend/alembic/versions/p10_phase2b1_alert_operation.py` | 新增 | down=p9phase2a101，+4 列 + 约束 + 回填 UPDATE |
| `backend/tests/test_alert_operation.py` | 新增 | 6 用例 |
| `frontend/src/views/Alerts.vue` + `types` | 改 | 状态列 + 处置弹窗（增量，不重构） |

> **RiskEngine / RuleFallbackProvider / collectors 采集链 / AIService / opinions 表：均不在改动面内。**

---

## I. 风险评估

| 风险 | 等级 | 缓解 |
|---|---|---|
| 删除/改动 `handled` 破坏旧过滤与前端 | 中 | **保留 handled 列**，处置时与 status 双写同步 |
| 回填 UPDATE 误伤风险数据 | 低 | UPDATE 只写 `alert_records.status`，SQL 层面不含 opinions |
| 多会话并行：模型列落盘↔生产迁移窗口期 UndefinedColumn | 中 | **改模型后立即完成生产迁移**（Phase 2-A.1 已踩坑，见项目记忆） |
| CheckConstraint 拒绝历史非法值 | 低 | 回填先行，且历史仅 True/False→合法值 |
| handled_at 用 created_at 冒充处理时间 | 低 | **不冒充**，历史回填保持 NULL |
| 新增权限带来的角色重分配回归 | 低 | **复用 alerts:write，不新增权限** |

---

## J. 最终回答

1. **Phase 2-B.1 是否可以实施？** → ✅ **可以实施**。纯附加式扩展，无阻断问题；`handled` 保留双写、复用 `alerts:write`、迁移只碰 alert_records。

2. **实施是否会影响：**
   - **0 token 自动风险链路？** → ❌ 不影响。评分/等级/critical/trigger_reason 逻辑一行不改；handle 为人工触发 API，采集链仍 `RuleFallbackProvider + RiskEngine` 纯规则。
   - **AI 隔离？** → ❌ 不影响。改动面无任何 LLM/DeepSeek/AIService 引用。
   - **RiskEngine 评分？** → ❌ 不影响。RiskEngine 完全不在改动面内。
   - **历史风险数据？** → ❌ 不影响。迁移仅 `UPDATE alert_records.status`，绝不触碰 `opinions`。

> **审计未发现需要推翻或修改设计的问题。等待确认后进入 Implement（Design 已在本报告内定稿）。**
