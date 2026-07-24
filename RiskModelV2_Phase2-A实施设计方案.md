# Risk Model V2 Phase 2-A 实施设计方案
## （Severity + Event State 风险模型 — 只读设计，未执行修改）

> 本方案基于 **Phase 1.5 运行验证**发现的残余误报而设计，目标根治：
> - 防灾部署类文章包含 事故/灾害 关键词 → 误判高危
> - 宣教类文章包含风险关键词 → 误判高危
> - 正面政策文章因危害词导致高风险 → 误判高危
>
> 设计原则：**增量演进、不推翻现有系统、明确文件位置与数据库影响、明确实施风险**。

---

## 1. 当前评分链路（设计锚点）

| 环节 | 文件:行 | 现状 |
|---|---|---|
| 评分注入 | `app/collectors/service.py:335` | `ai = RuleFallbackProvider(keywords=get_sensitive_keywords(db))` |
| 评分计算 | `app/services/ai/fallback.py:79-84` | `risk_score = BASE_RISK(20) + Σ(10*weight)`，纯加权和 |
| 结果写回 | `app/collectors/service.py:370-377` | `opinion.risk_score = analysis.risk_score` |
| 结果结构 | `app/schemas/ai.py:15` | `AIAnalysisResult(summary, sentiment, risk_score, keywords, suggestion)`，`extra="forbid"` |
| 等级派生 | `app/services/alert_service.py:78` | `derived_level = _map_risk_level(opinion.risk_score)`（≥70 high/≥40 medium/else low） |
| 关键词模型 | `app/models/keyword.py` | `word/weight/category/type('monitoring'\|'sensitive')/source/is_enabled` |
| 舆情模型 | `app/models/opinion.py` | `risk_score/sentiment/keywords/...`（无 severity/state 字段） |

**关键约束**：`AIAnalysisResult` 设了 `extra="forbid"`，新增字段必须显式加入 schema。

---

## 2. Severity 子评分设计

### 2.1 数据来源
- **真实危害指标词权重**：`keywords` 表 `type='sensitive'`（即当前驱动评分的词）新增一列 **`severity_weight`**（int，默认 0）。仅「真实事件信号」词（火灾/爆炸/事故/伤亡/死亡/冲突/上访/谣言/诈骗/腐败/贪污/涉警）赋非零 `severity_weight`；语境词（投诉/舆情/维权/群体）`severity_weight=0`（与 Phase 1 治理一致）。
- **注入方式**：扩展 `get_sensitive_keywords(db)` 返回 `(word, weight, severity_weight)` 三元组，透传至 `RuleFallbackProvider` / 新 Risk Engine。

### 2.2 计算位置（推荐方案 B：独立 Risk Engine）
- **新增** `app/services/risk_engine.py`：`RiskEngine` 类，职责单一——输入 `(title, content, sentiment)`，输出 `severity_score / event_state / resolution_flag / final_risk_score / risk_level`。
- 调用点：`app/collectors/service.py` 在 `ai.analyze(...)` 之后调用 `risk_engine.refine(title, content, analysis)`，用返回值覆盖 `opinion.risk_score` 并写入新字段。
- **为何不直接塞进 fallback.py**：保持 `RuleFallbackProvider`「纯规则、不查库、可单测」的现有约束；Risk Engine 作为编排层叠加 Severity/State 逻辑，符合 Phase 1 已确立的「评分与预警职责分离」原则。

### 2.3 是否需要新增字段
- `keywords` 表：**加 `severity_weight` 列**（int，默认 0）——增量，不改现有 `weight` 语义（过渡期 `weight` 仍可用于兼容旧逻辑，随后可弃用）。
- `opinions` 表：**加 3 列**——`severity_score`(int)、`event_state`(varchar, 枚举)、`resolution_flag`(bool)。
- `AIAnalysisResult` schema：**加 3 字段**（severity_score / event_state / resolution_flag），因 `extra="forbid"` 必须显式声明。
- 均为**加列，无删改、无破坏**。

---

## 3. Event State 设计（发生/预防/部署/通报/已解决）

### 3.1 是否需要 NLP / LLM
**不需要。** Phase 2-A 采用**规则词典过渡**：用状态短语词典做关键词匹配，零 NLP/LLM 依赖，确定性强、可审计、可配置。

> LLM 仅在 Phase 2 后期作为**精度增强**（处理否定句、细粒度状态判别）引入，本阶段不依赖。

### 3.2 状态词典（可配置，建议落地为 `risk_engine.py` 常量或 `keywords` 表 `type='state'`）
| 状态 | 触发短语（示例） | StateFactor |
|---|---|---|
| 发生(occurred) | 发生、出现、造成、致、引发、突发、遇难 | 1.0 |
| 通报(notice) | 通报、公布、发布、回应、表态、致歉 | 0.85 |
| 部署(deploy) | 部署、安排、落实、实施、推进、开展 | 0.70 |
| 预防(prevent) | 防范、预防、演练、预案、排查、整治 | 0.55 |
| 已解决(resolved) | 解决、妥善处理、办结、整改完成、化解、善后、问责到位 | 0.35 |

- 匹配优先级：**已解决 > 预防 > 部署 > 通报 > 发生**（多状态共存时取最"缓和"者，避免过度升级）。
- 默认状态：无状态词命中 → `发生(occurred)`。

### 3.3 是否可以规则过渡
**可以，且推荐。** 词典可配置化后，业务人员可自行增删状态词，无需改代码/重训模型。

---

## 4. Resolution Flag 设计

### 4.1 如何派生
- `resolution_flag = (event_state == '已解决')`，或由「已解决」短语命中直接置真。
- 作为独立布尔字段落库，供研判人员复核与大屏展示。

### 4.2 对风险评分的影响（核心公式）
```
Severity      = min( Σ(severity_weight of hit harm-indicator words), 100 )   # 仅真实危害词
StateFactor   = {occurred:1.0, notice:0.85, deploy:0.70, prevent:0.55, resolved:0.35}
SeverityAdj   = min(Severity * StateFactor, 100)
SentimentAdj  = (sentiment == 'positive') ? min(0.25 * (100 - Severity), 25) : 0
SeverityFloor = Severity >= 70 ? 70 : (Severity >= 50 ? 50 : 0)   # 不可抑制内核
final_score   = clamp( max(SeverityAdj - SentimentAdj, SeverityFloor), 0, 100 )
```

### 4.3 如何避免「重大事故因已处理被降为低风险」
**SeverityFloor 护栏**：当真实危害程度 `Severity ≥ 70`（如含 伤亡/死亡/爆炸），即使 `resolution_flag=True`（已救援整改），`final_score` 不得低于 70 → 仍判 high/critical。
- ✅ 「企业积极开展重大事故救援和整改」：Severity 高（事故/伤亡命中）→ floor 70 → **保留高危**（符合 V2 原则 P1：风险内核不可被情感/状态压制）。
- ✅ 「政府积极回应群众投诉，问题已解决」：Severity=0（无危害词）→ resolved factor 0.35 → **低风险**（误报消除）。

### 4.4 对 Phase 1.5 残余误报的消除验证（逻辑推演）
| Phase 1.5 误报样例 | Severity | EventState | final_score | 结果 |
|---|---|---|---|---|
| 防灾部署类含事故/灾害词 | 中（危害词命中） | 预防(0.55) | 显著下降 | 不再高危 ✓ |
| 宣教类含风险关键词 | 低-中 | 预防/部署 | 下降 | 不再高危 ✓ |
| 正面政策文章含危害词 | 视危害词 | 多为部署/预防 | 下降+positive折减 | 不再高危 ✓ |

---

## 5. 风险等级（risk_level）演进

Phase 1 的 `_map_risk_level` 只有 high/medium/low，**丢失 critical 语义**。Phase 2-A 恢复四档：
```
if Severity >= 70:                          risk_level = "critical"   # 真实重大事件
elif final_score >= 70:                     risk_level = "high"
elif final_score >= 40:                     risk_level = "medium"
else:                                       risk_level = "low"
```
- `alert_service.py` 改为优先用 `opinion.severity_score` 决定 critical 档，再回退 `final_score` 推导其余档——**与 Phase 1 的派生逻辑兼容叠加**，不推翻。

---

## 6. 文件位置与改动清单

| 文件 | 改动类型 | 内容 |
|---|---|---|
| `app/services/risk_engine.py` | **新增** | RiskEngine：Severity/EventState/ResolutionFlag/final_score/risk_level 计算 |
| `app/schemas/ai.py` | 修改 | AIAnalysisResult 加 `severity_score/event_state/resolution_flag` |
| `app/services/ai/fallback.py` | 修改 | 透传 `severity_weight`；或仅返回基础 hits，由 RiskEngine 算 Severity |
| `app/collectors/service.py` | 修改 | analyze 后调用 `risk_engine.refine(...)`，写回 opinion 新字段 |
| `app/services/alert_service.py` | 修改 | risk_level 增加 critical 档（基于 severity_score） |
| `app/models/opinion.py` | 修改 | 加 `severity_score(int)` / `event_state(str)` / `resolution_flag(bool)` |
| `app/models/keyword.py` | 修改 | 加 `severity_weight(int, default 0)` |
| Alembic migration | 新增 | 上述加列（全为 ADD COLUMN，无破坏） |
| （可选）`keywords` 表 `type='state'` | 新增数据 | 状态词典入库，可配置化（也可先用常量） |

---

## 7. 数据库影响

- **仅加列**，无 DROP / ALTER TYPE / 约束破坏：
  - `opinions`: +`severity_score`, +`event_state`, +`resolution_flag`
  - `keywords`: +`severity_weight`
- **历史数据**：存量 `opinions` 需重算（recompute pipeline）回填新字段；可离线批量跑 `RiskEngine.refine` 覆盖写入，不影响线上读。
- **兼容**：新列均有默认值/可空，旧代码读旧字段不受影响；回滚只需撤 migration。

---

## 8. 实施风险

| 风险 | 等级 | 说明 / 缓解 |
|---|---|---|
| 评分口径漂移 | 中 | 新公式改变 risk_score 分布，大屏/历史基线需同步校准 | 干系人确认 `severity_weight` 与 `StateFactor` 标定；先在测试库跑全量回灌对比 |
| 状态词典误判 | 中 | 否定句（"问题**未**解决"）可能误判为已解决 | Phase 2-A 先用简单短语；Phase 2 后期加否定词排除；可审计可配 |
| 多状态共存歧义 | 低 | 一文同时含"发生"与"整改" | 取最缓和状态（已解决>预防>部署>通报>发生），保守不升级 |
| 与 Phase 1 冲突 | 低 | Phase 1 已派生 risk_level + positive 保护 | Phase 2-A 在其上叠加 severity 维度，逻辑兼容，不推翻 |
| 性能 | 低 | 每条舆情多一次规则匹配 | 词典匹配 O(n)，可忽略；与现有 fallback 同量级 |

---

## 9. 与 Phase 1 / Phase 1.5 的衔接

1. **Phase 1 必须先生效**：当前生产未重启 uvicorn，Phase 1 代码未加载（见《Phase 1 收口验证报告》）。Phase 2-A 应在 Phase 1 收口后实施。
2. **Phase 2-A 直接消除 Phase 1.5 残余 FP-1/FP-2**：防灾/宣教/正面政策类含危害词误报，靠 EventState 的 StateFactor 折减 + Severity 仅计真实危害词解决。
3. **演进路径**：Phase 2-A（Severity+State）→ Phase 2-B（关键词三角色拆分 monitoring/risk_factor/trigger）→ Phase 2-C（传播/趋势/来源可信度）→ Phase 3（ML 严重度分类、分析师反馈闭环）。
