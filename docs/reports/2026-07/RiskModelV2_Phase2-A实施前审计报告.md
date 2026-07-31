# Risk Model V2 Phase 2-A 实施前审计报告

> **性质**：只读实施审计。本报告**不修改代码、不修改数据库、不执行迁移、不部署服务**。
> 目标：基于已收口的 Phase 1 生产状态，确认 Phase 2-A 的最佳落点与工程化风险，供决策后实施。
> 审计时间：2026-07-24　审计范围：`backend/` 当前工作树（Phase 1 已生产收口）。

---

## 0. 审计结论速览

| 项 | 结论 |
|---|---|
| Phase 1 生产状态 | ✅ 已收口（uvicorn 2026-07-24 10:14 重启，新代码生效；`derived_level + 正面保护` 在线） |
| Phase 2-A 最佳插入点 | ✅ **唯一、低风险点**：`backend/app/collectors/service.py` 第 370–377 行 `analysis = ai.analyze(...)` 之后，写回 `opinion` 之前 |
| 新增字段兼容性 | ✅ 全部为 `ADD COLUMN`（opinions 3 列、keywords 1 列），无删改、无约束破坏 |
| 方案需修正的关键点 | ⚠️ **4 处**（详见 §4），最关键：设计文档把字段塞进 `AIAnalysisResult` 会**击穿 `extra="forbid"` 与 DeepSeek 路径**，必须改为 RiskEngine 独立返回对象 |
| 测试体系缺口 | ⚠️ 需新增 1 个 RiskEngine 单元测试文件 + 1 个采集写回归测试 + critical 档回归 |
| 历史数据风险 | ⚠️ 中风险：新公式改变 `risk_score` 分布，存量舆情需**离线重算**（独立写操作，不在本次只读范围内） |
| 是否可立即实施 | ✅ 在完成 §4 修正后可直接实施；重算作为后续独立步骤 |

---

## 1. 当前风险链路核查（确认插入点）

逐环节定位当前实现（Phase 1 收口后）：

| 环节 | 位置 | 现状（已确认） |
|---|---|---|
| **Opinion 生成** | `app/collectors/service.py:345-355` | `Opinion(risk_score=0, sentiment="neutral", analysis_status="pending")` 先落库保证失败不丢 |
| **评分注入** | `app/collectors/service.py:335` | `ai = RuleFallbackProvider(keywords=get_sensitive_keywords(db))` —— 仅注入 `(word, weight)` |
| **risk_score 计算** | `app/services/ai/fallback.py:79-84` | `risk_score = BASE_RISK(20) + Σ(10*weight)`，纯加权和；`analyze()` 返回 `AIAnalysisResult` |
| **结果写回** | `app/collectors/service.py:370-377` | `analysis = ai.analyze(...)`；`opinion.risk_score = analysis.risk_score`；`opinion.keywords/sentiment/...` 写回 |
| **等级派生** | `app/services/alert_service.py:78` | `derived_level = _map_risk_level(opinion.risk_score)`（≥70 high / ≥40 medium / else low） |
| **正面保护** | `app/services/alert_service.py:83-91` | `positive` 且无 `HARM_INDICATOR_KEYWORDS` 命中 → `high/critical` 降级 `low`（命中危害词保留） |
| **AlertRecord 生成** | `app/services/alert_service.py:103-115` | 写入 `risk_level=derived_level`，`alert_records.risk_level` 已含 `critical` 档（CheckConstraint 已支持） |

**插入点确认**：Phase 2-A 的 Severity/EventState/ResolutionFlag 计算，应插入在 `service.py:370` `analysis = ai.analyze(...)` 与 `service.py:375` `opinion.risk_score = analysis.risk_score` **之间**，覆盖 `risk_score` 并写入 3 个新字段。此处：
- 已拿到 `opinion.title / opinion.content / analysis.sentiment`；
- 仍在单条写回的锁内（`:380` `with self._write_lock`），无并发竞争；
- 手动采集（并发 `collect_and_analyze_concurrent`）与定时 cron（`collect_and_analyze` 顺序）**共用同一写回路径** → 一次插入覆盖全部采集来源；
- 不影响 `fetch / 去重 / 提交` 结构，纯增量。

**明确不在 Phase 2-A 范围**：DeepSeek 手动「触发 AI 分析」路径（`ai_risk_score / ai_sentiment`，`opinion.py:50-60`）**不驱动预警**（AlertService 只用 `opinion.risk_score`），故不在本次改动链路内，避免扩大面。

---

## 2. 数据库现状核查（确认兼容方案）

### 2.1 `opinions` 表（`app/models/opinion.py`）
- 现有相关列：`risk_score(int)`、`sentiment(str)`、`keywords(text)`、`analysis_status` 等。
- **缺失**：`severity_score`、`event_state`、`resolution_flag` —— 均需 `ADD COLUMN`：
  - `severity_score INTEGER DEFAULT 0`（可空，旧行=0 或 NULL）
  - `event_state VARCHAR(16) DEFAULT 'occurred'`（可空；建议 NOT NULL DEFAULT 'occurred' 以省去回填）
  - `resolution_flag BOOLEAN DEFAULT FALSE`
- 兼容性：新列均有默认值/可空，**旧代码读旧字段不受影响**，回滚只需 `DROP COLUMN`（对应 migration `downgrade`）。

### 2.2 `keywords` 表（`app/models/keyword.py`）
- 现有：`word / weight / category / type('monitoring'|'sensitive') / source / is_enabled`。
- **缺失**：`severity_weight INTEGER DEFAULT 0` —— `ADD COLUMN`，增量。
- 关键语义分离（已在 Phase 1 确立）：`weight` 仍驱动 `RuleFallbackProvider` 的 `risk_score`；`severity_weight` 仅由 RiskEngine 用于 Severity 子评分。**两条权重并行但职责不同**，过渡期不冲突。
- ⚠️ **风险点**：`get_sensitive_keywords()` 当前返回 `(word, weight)`（`keyword_service.py:60-83`），且**数据库无启用敏感词时回退内置 `DEFAULT_KEYWORDS`**（无 `severity_weight`）。Phase 2-A 必须新增 `get_severity_keywords()` 或在 RiskEngine 内置 `DEFAULT_SEVERITY_KEYWORDS` 常量，否则「无 DB / fallback」路径下 Severity 恒为 0，行为失真（详见 §4.2）。

### 2.3 `alert_records` 关联
- `AlertRecord`（`app/models/alert.py:27-46`）含 `rule_id / opinion_id / risk_level / trigger_reason`。
- `risk_level` CheckConstraint 已含 `critical`（`alert.py:42-45`）→ **critical 档可直接落库，无需改表**。
- 新增的 opinions 字段**不需要** alert_records 增加关联列；预警等级逻辑改为读取 `opinion.severity_score` 决定 critical 档即可。

### 2.4 `AIAnalysisResult` Schema（`app/schemas/ai.py:15-28`）
- `model_config = {"extra": "forbid"}` —— **这是设计文档方案的一个雷区**（详见 §4.1）。

---

## 3. 现有测试体系核查（确认需新增的回归测试）

### 3.1 现状
- `backend/tests/test_phase1_risk_model.py`：6 个用例，覆盖 Phase 1（关键词治理 / 等级派生 / 正面保护 / 规则等级不复制）。
- 夹具：`seeded_region_id`（conftest.py:51，返回种子区域 131028 id）。
- 门禁：`conftest.py:19` 设 `DB_IDENTITY_CHECK=off`（测试库非生产 cluster，关闭身份门禁）。
- ⚠️ **已知坑**（来自 Phase 1 实施经验）：conftest 写 `:5433/opinion_test`，但本机实际测试库在 **`:5432/opinion_test`**。跑测试须 `DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test DB_IDENTITY_CHECK=off pytest ...`。

### 3.2 需新增的 Phase 2-A 回归测试
| 测试文件 | 用例 | 验证点 |
|---|---|---|
| `tests/test_risk_engine.py`（**新增**） | `test_severity_only_harm_words` | Severity 仅计危害指标词；语境词（投诉/舆情/维权/群体）权重=0 不计入 |
| 同上 | `test_state_factor_mapping` | 5 状态 StateFactor 正确（occurred=1.0/notice=0.85/deploy=0.70/prevent=0.55/resolved=0.35） |
| 同上 | `test_multi_state_picks_most_mitigated` | 多状态共存取最缓和（resolved>prevent>deploy>notice>occurred） |
| 同上 | `test_resolution_flag_from_resolved` | `event_state=='resolved'` → `resolution_flag=True` |
| 同上 | `test_sentiment_adj_positive` | positive 且无危害词 → SentimentAdj 折减 |
| 同上 | `test_severity_floor_guard` | Severity≥70（伤亡/死亡/爆炸）→ floor 70，已解决也不低于 70（重大事故仍 critical/high） |
| 同上 | `test_final_score_replaces_risk_score` | 防灾部署含事故/灾害词 → final 显著低于旧公式，不再 high |
| `tests/test_phase2a_collector_writeback.py`（**新增**） | `test_refine_written_on_collect` | 采集写回后 `opinion.severity_score/event_state/resolution_flag/final_risk_score` 正确落库 |
| `tests/test_phase1_risk_model.py`（**追加**） | `test_critical_from_severity_score` | 构造 `severity_score≥70` 舆情 → AlertRecord.risk_level=='critical'（验证 critical 档回归） |
| 同上 | `test_null_severity_score_backward_safe` | `severity_score` 为 NULL/0 的旧舆情 → 不产生 critical，等级仍由 risk_score 派生（向后兼容） |

---

## 4. 工程化评估（重点检查项 + 对设计文档的修正建议）

### 4.1 ⚠️ `AIAnalysisResult.extra="forbid"` 会击穿 DeepSeek 路径 —— **必须修正**
设计文档 §2.3 / §6 建议把 `severity_score / event_state / resolution_flag` 加进 `AIAnalysisResult`。
**问题**：该 Schema 设了 `extra="forbid"`（`ai.py:28`），且有两个构造方：
- `RuleFallbackProvider.analyze`（`fallback.py:123`）—— 可改，补 3 字段即可；
- `DeepSeekProvider.analyze`（`deepseek.py:167-178`）—— 结果由 **LLM JSON** 经 `schema.model_validate(data)` 校验（`deepseek.py:104`）。

若把 3 字段设为**必填**，DeepSeek 返回的 JSON 不含这些字段 → `ValidationError` → 上抛 → AIService 被迫降级到 RuleFallbackProvider，**DeepSeek 路径永久失效**，且每次调用都报错刷日志。
**修正方案（推荐）**：**保持 `AIAnalysisResult` 完全不变**。新增 `app/services/risk_engine.py`，其 `refine()` 返回**独立结果对象**（如 `RiskRefinement`  dataclass / pydantic），由 collector 直接写 `opinion.*`。这样：
- 零 schema 漂移，`extra="forbid"` 与 DeepSeek 路径不受影响；
- RiskEngine 仍是纯函数、可单测，符合 Phase 1 已确立的「评分与预警职责分离」。

### 4.2 ⚠️ `severity_weight` 的 fallback 缺位 —— **必须修正**
设计文档把 `severity_weight` 当 `keywords` 表新列，但：
- `get_sensitive_keywords()` 在无启用敏感词时回退 `DEFAULT_KEYWORDS`（`keyword_service.py:77-79`），该内置表**没有 `severity_weight`**；
- 若 RiskEngine 直接读 DB `severity_weight` 而 DB 未播种，Severity 恒为 0 → 全部舆情降到极低分，误杀真实风险。
**修正方案（推荐）**：在 `risk_engine.py` 内置 `DEFAULT_SEVERITY_KEYWORDS: Dict[str, int]`（与 `HARM_INDICATOR_KEYWORDS` 对齐的 12 个危害词 → 严重度，如 伤亡/死亡/爆炸=80~90，事故/冲突/上访=40~60，谣言/诈骗/腐败/贪污/涉警=40~60）。`get_severity_keywords(db)` 优先读 DB `severity_weight`，空/未配置时回退内置常量，保证「无 DB / 测试 / 演示」路径行为确定。DB 播种作为可选增强，不在强制路径。

### 4.3 Event State：单枚举 vs 多状态 —— **推荐单枚举**
设计文档 §3 已给出 5 状态（发生/通报/部署/预防/已解决）与优先级取最缓和。
**评估结论：采用单枚举（`event_state VARCHAR`，一个值）**，理由：
- 业务规则是「多状态共存取最缓和」→ 本质是一个**派生出的单一状态**，不是可独立为真的多个布尔；
- 多独立布尔（如 `is_occurred/is_prevent/is_resolved`）会引入「状态互斥/优先级裁决」的额外复杂度与不一致风险；
- 单枚举可审计、可配置（词典）、落库简单、前端展示直观。
- 仅保留 `resolution_flag` 作为从 `resolved` 派生的独立布尔（供研判复核与大屏），不与枚举冗余冲突。

### 4.4 RiskEngine 职责边界
**原则（与现有约束一致）**：
- RiskEngine = **纯函数/无 DB 访问**，severity 词典与 `severity_weight` 经构造参数注入（与 `RuleFallbackProvider.__init__(keywords=...)` 同构）；
- RiskEngine **不替换** `RuleFallbackProvider`，而是其后的「编排/精炼层」：`analysis = ai.analyze(...)` → `refine = risk_engine.refine(title, content, analysis.sentiment)`；
- **不把 Severity 逻辑写进 AlertService** —— AlertService 保持「从 opinion 字段派生等级」的薄职责；critical 档仅新增一行 `if opinion.severity_score >= 70: critical`（向后兼容：`severity_score` 为 NULL/0 时不触发）；
- 不触碰 aggregator（`event/aggregator.py`）：事件聚合仍用 `opinion.risk_score`（=refine 后的 final），无需改。

### 4.5 是否影响现有采集流程
- **影响范围极小**：仅在 `service.py:370-377` 插入一次 `risk_engine.refine()` + 3 列写回；不改 `fetch / 去重 / 提交 / 失败隔离`（`service.py:356-390` 的 try/except 与 `_write_lock` 全部保留）。
- 性能：词典匹配 O(n)（与现有 fallback 同量级），每条舆情多一次规则匹配，可忽略。
- 手动/定时采集共用路径 → 全覆盖。
- DeepSeek 手动触发路径（`ai_*`）不受影响（§1 已界定）。

### 4.6 ⚠️ 历史数据兼容风险（中风险，需独立后续步骤）
- 新列可空/有默认值 → **迁移本身零破坏**；但若**不重算存量**，会出现分数分布分裂：
  - 旧舆情：`risk_score` 由旧公式算出（无 Severity/State 折减），可能偏高；
  - 新舆情：`risk_score` 经 refine 折减，偏低。
  - 后果：`alert_rules.risk_threshold`、`EventAggregator._representative/_recompute_event`（用 `max(risk_score)`）会在「旧高 / 新低」混合数据上表现不一致，大屏基线漂移。
- **修正/缓解（推荐）**：
  1. **先部署 refine（新行生效）**，不强制重算 → Phase 2-A 即可上线且向后安全（旧行 `severity_score`=0/NULL，`AlertService` 不产 critical，等级仍由旧 `risk_score` 派生，零回归）；
  2. **重算作为独立写操作**后续执行：离线脚本遍历存量 `opinions`，用 `RiskEngine.refine(title, content, sentiment)` 回写 3 字段 + 重算 `final_risk_score`；**必须先 dry-run 对比分布，且经 `db_identity_check` 门禁**（迁移/写库前强制，见 `alembic/env.py:7,42` 与 `db_identity_check.py`）。本次审计**不执行**重算。
- 另建议：考虑给 `final_score` 设**最小基线**（如保留 `BASE_RISK=20` 或 `max(...,20)`），避免「无危害词文章」score 直接跌到 0（当前最低 20），否则事件代表选择/大屏可能出现全 0 簇。属标定项，交干系人确认。

### 4.7 其他一致性检查
- `OpinionOut`（`schemas/opinion.py:33-58`）：若要在前端展示新字段，需显式加 `severity_score/event_state/resolution_flag`；否则 API 静默丢弃（不报错）。前端展示**非本次必改项**，列为可选跟进。
- `AlertRecord.trigger_reason`：建议在 critical 档触发时追加说明（如「真实危害严重度≥70，保留高危」），提升可解释性（非必须）。

---

## 5. 修正后的实施落点清单（供确认后执行）

| 文件 | 改动 | 备注 |
|---|---|---|
| `app/services/risk_engine.py` | **新增** | `RiskEngine` 纯函数 + `RiskRefinement` 结果对象 + `DEFAULT_SEVERITY_KEYWORDS` 常量 + 5 状态词典（内置，可配置） |
| `app/services/keyword_service.py` | 修改 | 新增 `get_severity_keywords(db)`（回退内置常量） |
| `app/collectors/service.py` | 修改 | `:335` 注入 `RiskEngine(get_severity_keywords(db))`；`:370-377` 插入 `refine()` 并写回 `opinion.severity_score/event_state/resolution_flag/risk_score` |
| `app/services/alert_service.py` | 修改 | 仅追加 critical 档：`if opinion.severity_score and opinion.severity_score >= 70: critical`（向后兼容 NULL/0） |
| `app/models/opinion.py` | 修改 | +`severity_score` / +`event_state` / +`resolution_flag`（含 CheckConstraint：`event_state IN (5态)`） |
| `app/models/keyword.py` | 修改 | +`severity_weight INTEGER DEFAULT 0` |
| Alembic migration | 新增 | 上述加列（全 `ADD COLUMN`，含 `downgrade` 撤列）；走 `assert_identity_for_migration` 门禁 |
| `app/schemas/ai.py` | **不改动** | 保持 `extra="forbid"` 与 DeepSeek 路径（关键修正） |
| `tests/test_risk_engine.py` | **新增** | §3.2 单元用例 |
| `tests/test_phase2a_collector_writeback.py` | **新增** | 采集写回集成用例 |
| `tests/test_phase1_risk_model.py` | 修改 | 追加 critical 档 + 向后兼容 2 用例 |
| （可选）`keywords` 表 `severity_weight` 播种 | 数据 | 12 危害词标定 severity_weight（增强，非强制） |
| （后续独立写操作）存量重算脚本 | 新增 | dry-run 优先 + 身份门禁，不在本次范围 |

---

## 6. 实施风险再评估（更新设计文档 §8）

| 风险 | 等级 | 缓解（修正后） |
|---|---|---|
| Schema 漂移击穿 DeepSeek | **高→已消解** | §4.1：不改动 `AIAnalysisResult` |
| Severity fallback 缺位致全 0 | **高→已消解** | §4.2：内置 `DEFAULT_SEVERITY_KEYWORDS` 常量 |
| 评分口径漂移 / 大屏基线 | 中 | §4.6：先部署 refine，重算作为独立 dry-run 步骤 |
| 状态词典误判（否定句） | 中 | 维持 Phase 2-A 简单短语；Phase 2 后期加否定词排除 |
| 多状态共存歧义 | 低 | 单枚举 + 取最缓和（§4.3） |
| 与 Phase 1 冲突 | 低 | 在其上叠加 severity 维度，逻辑兼容 |
| 性能 | 低 | O(n) 词典匹配，可忽略 |
| 历史数据分裂 | 中 | §4.6 重算独立步骤 + 身份门禁 |

---

## 7. 审计边界声明
- 本报告所有结论基于**只读**检查：`Read` 源码、`Glob` 文件树、阅读既有设计/迁移文档；**未执行**任何 `INSERT/UPDATE/ALTER`、未运行 `alembic upgrade`、未重启/部署服务、未改动工作树。
- 确认 Phase 1 生产收口状态来源于既有《Phase1_FinalCloseReport》，本次未重新验证生产运行实例。
- 待您确认后，方可按 §5 落点清单进入实施（Craft 模式），并先跑 `db_identity_check.py` 验证目标库身份。
