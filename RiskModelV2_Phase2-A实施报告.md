# Risk Model V2 Phase 2-A 实施报告

>

---

## 一、修改文件清单

### 1. 新增：`backend/app/services/risk_engine.py`（核心新增组件）

独立风险精炼层（Risk Engine），**纯函数、无数据库访问、无数据库写入**。

- `BASE_RISK = 20` 底座保留。
- `DEFAULT_SEVERITY_KEYWORDS`：内置真实危害词 → 严重度权重 fallback（火灾80/爆炸90/伤亡90/死亡90/事故60/冲突50/上访50/谣言45/诈骗50/腐败50/贪污50/涉警55）。**语境词（投诉/舆情/维权/群体）不入表**。
- `RiskRefinement` 独立结果对象（severity_score / event_state / resolution_flag / final_risk_score），**不进入 `AIAnalysisResult`**（`extra="forbid"` 不受影响，DeepSeek 路径安全）。
- 单枚举 `Event State`：`occurred / notice / deploy / prevent / resolved`，多状态共存取最缓和；`resolution_flag = (state=='resolved')`。
- `Severity Floor`：`severity>=70 → 保底70`，`>=50 → 保底50`，保证重大事件不因正面/已处理降级。
- 构造器对注入词表与 DEFAULT 做**合并**（注入项覆盖同名默认，未注入项保留默认）。

### 2. 修改：`backend/app/services/keyword_service.py`

新增 `get_severity_keywords(db)`：以 `DEFAULT_SEVERITY_KEYWORDS` 为底座，用 `keywords` 表 `type='sensitive'` 且启用的 `severity_weight` **覆盖**（DB 优先）。

- **关键修正（测试中发现并修复的真实 Bug）**：原合并逻辑 `if word and sw is not None` 会用 DB 中 `severity_weight=0`（新建列默认值、从未播种）把全部默认严重度清零，导致 Severity 恒为 0。已改为 **仅当 `sw` 为真（>0）才覆盖**，使未配置的词沿用默认权重，feature 开箱即用。

### 3. 修改：`backend/app/collectors/service.py`

- 顶部新增 `from app.services.risk_engine import RiskEngine`。
- `_process_collector` 内：`ai = RuleFallbackProvider(...)` 旁注入 `risk_engine = RiskEngine(severity_keywords=get_severity_keywords(db))`。
- 在 `analysis = ai.analyze(...)` 之后、opinion 字段写回之前，调用 `risk_engine.refine(title, content, sentiment)` 并写回 `risk_score(=final)` / `severity_score` / `event_state` / `resolution_flag`。
- 手动与定时采集共用该路径 → 一处插入全覆盖。

### 4. 修改：`backend/app/services/alert_service.py`

- `AlertService.evaluate` 在 Phase 1 派生逻辑之后新增 **critical 派生**：`severity_score >= 70` 时 `derived_level = "critical"`。
- 保留 Phase 1 的 `risk_score → 等级` 派生与正面误报保护；历史 `severity_score` 为 NULL/0 的旧数据不触发 critical（向后兼容）。

### 5. 修改：`backend/app/models/opinion.py`

新增 3 列（均 `ADD COLUMN`，带 server_default，不删不改既有字段）：

- `severity_score Integer NOT NULL default 0`
- `event_state String(16) NOT NULL default 'occurred'` + CheckConstraint `event_state IN (5态)`
- `resolution_flag Boolean NOT NULL default false`

### 6. 修改：`backend/app/models/keyword.py`

新增 `severity_weight Integer NOT NULL default 0`（与既有 `weight` 职责分离、并行存在）。

### 7. 新增迁移：`backend/alembic/versions/p8_phase2a_risk_engine.py`

`down_revision = 'p7evtuniq01'`。全部 `ADD COLUMN` + 一个 `event_state` CheckConstraint；含完整 `downgrade`。**未重算历史数据**。

### 8. 新增/扩展测试

- `backend/tests/test_risk_engine.py`（新增 16 例）
- `backend/tests/test_phase2a_collector_writeback.py`（新增 2 例，驱动真实 `collect_and_analyze` 路径）
- `backend/tests/test_phase1_risk_model.py`（扩展 3 例：critical 恢复 ×2、老数据兼容 ×1）

---

## 二、Migration 执行结果

身份门禁：`db_identity_check.py` 此前确认生产 `system_identifier=7663057120701798896` = VERIFIED。本次测试库迁移以 `DB_IDENTITY_CHECK=off` 显式关闭门禁（已知安全场景），生产库未触碰。

---

## 三、测试结果

### 1. 本次新增/扩展测试（目标回归集，全部通过）

- `test_risk_engine.py`：16 passed
- `test_phase2a_collector_writeback.py`：2 passed（验证采集写回 severity_score/event_state/resolution_flag/risk_score）
- 扩展 Phase 1 测试：3 passed（critical 恢复、正面+危害词仍 critical、老数据 severity_score=0 不误判 critical）

**Phase 2-A 目标回归集：26 passed, 0 failed。**

### 2. 全量测试（回归基线对比）

- 含 Phase 2-A：`153 passed, 14 failed, 10 errors`
- 去除 Phase 2-A（git stash 仅暂存本阶段文件后重跑）：`127 passed, 14 failed, 10 errors`
- 差值 = **+26 passed**，失败/错误集**完全一致** → **Phase 2-A 零回归**。

14 failed + 10 errors 为**既有问题**（与本次无关），典型根因：

- `test_ai_analysis.py`：DeepSeek API 402 `Insufficient Balance`（需有效额度/网络）。
- `test_government_collector.py`：`GovernmentCollector` 无 `_get` 属性（用例与当前实现漂移）。
- `test_events*.py`：事件聚合 API 返回异步 task（`created` 不在同步响应），属已有断言偏差。
- `test_dashboard.py`（10 errors）：teardown 时 `opinions` 被 `event_opinions` 外键引用导致删除失败（测试隔离/清理既有问题）。
- `test_keyword_lexicon.py`：关键词词表预期集与实际（Phase 1 治理后）漂移。

>

---

## 四、风险说明

1. **DB 严重度列默认值陷阱（已在测试中拦截并修复）**：新建 `severity_weight` 列默认 0 且从未播种，原合并逻辑会把内置默认全部清零，使 Severity 恒为 0、feature 形同虚设。修复后仅正权重覆盖默认。
2. **生产迁移尚未执行**：新列仅存在于测试库；生产库若直接跑旧采集器不会出错（模型/ORM 向后兼容），但 `severity_score` 等为空/`0`，critical 档与 Severity 维度在生产不生效，直至生产迁移完成。
3. **历史 opinions 未重算**：本阶段明确不重算。`severity_score=0` 的旧数据经 `AlertService` 不会产生 critical（设计内向后兼容），但也不具备 Severity 维度；历史风险研判复盘需待后续独立的重算写操作。
4. **critical 档语义收紧**：critical 现在仅当真实危害严重度 ≥70 才出现，解决了 Phase 1 无法产出 critical 的问题，但也意味着旧的高分但非真实危害事件（如纯语境词堆叠）不会升级为 critical——符合预期。
5. **并发/采集影响**：RiskEngine 为纯函数、无 IO，写回在既有分析写回临界区内，对采集吞吐无额外 DB 往返；仅增加内存计算，开销可忽略。

---

## 五、下一步建议

1. **Phase D 收口（待确认）**：用户确认后，在生产库执行 `DB_IDENTITY_CHECK` 通过后 `alembic upgrade head`（建议在低峰期，ADD COLUMN 对 PostgreSQL 为大表 `ALTER TABLE ... ADD COLUMN ... DEFAULT` 仅在 12+ 带 `DEFAULT` 时可快速完成，本环境 PG16 无锁表风险），随后**重启 uvicorn**（8000/8011）使新代码与列生效。
2. **可选：历史 opinions 重算**：作为独立写操作（dry-run 优先 + 身份门禁），用 `RiskEngine.refine` 回填存量 `severity_score/event_state/resolution_flag` 并重算 `risk_score`，使历史告警等级与新模型一致。
3. **可选：severity_weight 入库（业务标定）**：若需对个别危害词微调严重度，经 `keywords` 表 `severity_weight` 配置（当前 0 表示沿用默认）；建议在管理员界面暴露该字段。
4. **监控**：上线后观察 `severity_score`、`event_state` 分布与 critical 告警量，确认防灾/宣教类事件误报下降、重大真实事件 critical 恢复符合预期。
