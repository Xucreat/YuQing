# Risk Model V2 Phase 2-A.1 实施前审计报告

> 模式：**Audit（只读）** → Design → Implement → Test → Report
> 本报告仅做第一阶段只读审计，未修改任何代码、数据库、迁移或服务。
> 审计基准：生产已上线 Phase 2-A（`opinion_db` @ `p8phase2a01`，uvicorn 8000/8011 运行中）。

---

## 0. 审计约束确认

本阶段严格遵守：

- ✅ 不接 DeepSeek 自动分析、不新增任何 LLM 调用
- ✅ 不修改采集链路、不修改 `RuleFallbackProvider` 公式、不修改 `RiskEngine` 评分规则、不修改 Severity 权重体系
- ✅ 不重算历史数据、不进入 Phase 2-B
- ✅ 仅"记录计算依据"，不改变当前评分结果

---

## 1. 当前 Phase 2-A 代码状态

| 组件 | 文件 | 状态 | 本次是否触及 |
|---|---|---|---|
| 规则评分 | `app/services/ai/fallback.py` | 纯规则 `BASE_RISK+Σ10×weight` | ❌ 不改 |
| 风险精炼 | `app/services/risk_engine.py` | 纯函数，返回 `RiskRefinement` | ✅ 仅增 `risk_factors` 解释字段（评分不变） |
| 采集写回 | `app/collectors/service.py:381-394` | `ai.analyze` → `risk_engine.refine` → 写回 3 字段 | ✅ 仅增写 `risk_factors`/`risk_model_version` |
| 告警生成 | `app/services/alert_service.py:84-120` | 纯规则派生 critical + `trigger_reason` 文本 | ✅ 仅增强 critical 文本（逻辑不变） |
| AI 研判 | `api/analysis.py`（DeepSeek） | 用户手动触发，写 `ai_*` 字段 | ❌ 完全隔离 |

**结论**：Phase 2-A 链路已是"0 token 自动风险 + 独立 AI 研判"，Phase 2-A.1 仅做"可解释/可追踪"的附加记录，不触碰评分内核与 AI 链路。

---

## 2. opinions 表结构（当前生产 `p8phase2a01`）

来源：`app/models/opinion.py`

```
id, title, content, source, url, publish_time, region_id,
risk_score, sentiment, summary, keywords, search_vector, created_at,
analysis_status, analysis_time, analysis_suggestion,            # AI 生命周期
ai_summary, ai_sentiment, ai_risk_score, ai_keywords,
ai_analysis_status, ai_analysis_time, ai_analysis_suggestion,   # DeepSeek 报告
severity_score,        # Phase 2-A 新增（Integer, default 0）
event_state,           # Phase 2-A 新增（String, default 'occurred'）
resolution_flag        # Phase 2-A 新增（Boolean, default false）
```

**缺失（本次新增目标）**：
- `risk_factors`（JSONB，建议 nullable=True → 历史=NULL）
- `risk_model_version`（VARCHAR，建议 default `'risk-v2.0'`）

> ⚠️ 重要发现：即便已上线的 `severity_score/event_state/resolution_flag` 也**未出现在 API 响应 `OpinionOut`**（`app/schemas/opinion.py:33-58`），即前端目前**完全无法展示**任何 Phase 2-A 字段。

---

## 3. AlertRecord 结构（当前生产）

来源：`app/models/alert.py`

```
id, rule_id, rule_name, risk_level, opinion_id, opinion_title,
event_id, event_title, trigger_reason (Text, 可为空), handled, created_at
```

- `trigger_reason` 为 `Text`，**无需迁移**，仅增强其文本内容。
- `risk_level` 含 `CheckConstraint IN ('low','medium','high','critical')`，critical 档已合法，Phase 2-A.1 不新增等级。

---

## 4. RiskEngine 输出链路（当前）

`app/services/risk_engine.py`：

- `class RiskRefinement`（dataclass, `:93-100`）：
  `severity_score / event_state / resolution_flag / final_risk_score`
- `RiskEngine.refine(title, content, sentiment)`（`:139-181`）：
  1. Severity 累加真实危害词权重（`:148-152`）→ **此处可同时收集命中词**
  2. EventState 单枚举（`:155`）
  3. StateFactor / SentimentAdj / SeverityFloor（`:156-168`）
  4. 返回 `RiskRefinement`（`:176-181`）

**扩展点**：
- `RiskRefinement` 增加字段 `risk_factors: dict`（不增评分逻辑）
- `refine()` 在 `:148-152` 的 Severity 循环中**并行收集命中词** → 生成 `risk_factors` 解释字典
- 全程纯函数、无 DB、无 LLM，满足约束

**向后兼容**：现有 `refine()` 调用方（`collectors/service.py`）读取 `final_risk_score/severity_score/event_state/resolution_flag` 不变；新增字段为附加返回值，不破坏既有测试与调用。

---

## 5. 前端风险解释展示能力（审计）

来源：`frontend/src/components/OpinionDetailModal.vue`（系统研判报告卡，`:47-77`）

当前"系统研判报告"卡已展示：
- 风险评分 `risk_score`、级别、情感、摘要、关键词、分析时间、`analysis_suggestion`

**缺失**：
- 全前端 `src` grep `severity_score|event_state|resolution_flag|risk_factors|risk_model_version` → **0 匹配**
- `frontend/src/types` 中 `Opinion` 类型**未含**任何 Phase 2-A 字段
- 后端 `OpinionOut` 未回传上述字段 → 即使前端想显示也无数据源

**结论**：前端结构**适合**扩展（"系统研判报告"卡位于右侧上部，天然是风险依据展示位），但当前**不具备**展示能力——需配套：①后端 `OpinionOut` 增加字段；②前端 `Opinion` 类型 + 模板增加"风险依据"区块。**不强行修改**：本审计仅给出设计建议，实施阶段按确认执行。

---

## 6. 适合扩展的位置（落点清单）

| # | 位置 | 改动 | 风险 |
|---|---|---|---|
| E1 | `risk_engine.py:93-100` | `RiskRefinement` 增 `risk_factors: dict` | 低（附加字段） |
| E2 | `risk_engine.py:148-152` | Severity 循环并行收集命中词 → 构造 `risk_factors` | 低（不改 sum） |
| E3 | `risk_engine.py` 顶部 | 增加常量 `RISK_MODEL_VERSION = "risk-v2.0"` | 低 |
| E4 | `collectors/service.py:382-394` | `refine()` 后写 `opinion.risk_factors` + `opinion.risk_model_version` | 低 |
| E5 | `models/opinion.py:64-76` + `:6` | 增 `risk_factors`(JSONB) + `risk_model_version`(String) | 低（ADD COLUMN） |
| E6 | `schemas/opinion.py:33-58` | `OpinionOut` 增 `risk_factors`、`risk_model_version`（及同步补 `severity_score/event_state/resolution_flag` 以便前端完整展示） | 低 |
| E7 | `alert_service.py:84-120` | critical 时增强 `trigger_reason`（含 severity_score、factors、event_state）；对 `risk_factors` 为 None 时降级 | 低 |
| E8 | `alembic/versions/p9_phase2a1_risk_explainability.py` | 新增迁移，`down_revision="p8phase2a01"`，ADD COLUMN + downgrade | 低 |
| E9 | 前端 `OpinionDetailModal.vue` + `types` | 系统研判报告卡增"风险依据"展示 | 低（UI 层，可选项） |

**迁移链确认（实测，非假设）**：
- 线性链 head = `p8phase2a01`（`p7evtuniq01 → p8phase2a01`）
- 新迁移 `down_revision` 必须为 `p8phase2a01`（**不是** `kwlex01`/`rbac10001` 等其他分支）

---

## 7. 架构约束再验证（0-token / AI 隔离不受影响）

- `RiskEngine` 仍纯函数、无 DB/无 LLM → 自动链路 **0 token** 不变
- `risk_factors` 是 `refine()` 的内部派生字典，不触发任何网络/LLM
- `AlertService` 读取 `opinion.risk_factors`（存储字段），仍**不依赖** `ai_*` 字段 → AI 隔离不变
- `AIAnalysisResult` 不扩展 → DeepSeek 路径不受影响
- 评分公式、Severity 权重、采集链路一律不动

---

## 8. 设计建议（供实施参考，待确认）

### 8.1 risk_factors 结构（JSONB）

与任务目标一致：

```json
{
  "severity": [
    { "keyword": "爆炸", "score": 90 },
    { "keyword": "伤亡", "score": 90 }
  ],
  "event_state": "occurred",
  "resolution": false,
  "adjustments": [
    { "type": "severity_floor", "reason": "重大危害事件" }
  ]
}
```

- `severity`：仅列命中真实危害词（含权重），与评分 sum 同口径但**只记录不改分**
- `event_state`：单枚举状态值
- `resolution`：= `resolution_flag`
- `adjustments`：记录触发护栏（如 `severity_floor`），便于未来复算与审计

### 8.2 risk_model_version

- 常量 `RISK_MODEL_VERSION = "risk-v2.0"`（置于 `risk_engine.py`，便于与评分逻辑同文件演进）
- 采集写回时写入 `opinion.risk_model_version = RISK_MODEL_VERSION`
- 历史数据由迁移 `server_default='risk-v2.0'` 兜底，不重算

### 8.3 trigger_reason 增强（critical）

保持原有 `trigger_parts` 机制，仅在 `derived_level=="critical" and severity_score>=70` 分支追加：

```
critical: severity_score=100, factors=[爆炸,伤亡], event_state=occurred
```

- 从 `opinion.risk_factors["severity"]` 提取关键词（None 时退化为仅显示 severity_score）
- 不改变告警生成逻辑，仅增强文本

### 8.4 前端设计建议（不强行修改，供确认）

在 `OpinionDetailModal.vue` "系统研判报告"卡（`sys-card`）内、`report-keywords` 下方新增"风险依据"区块：

```
风险依据：  爆炸 +90   伤亡 +90
事件状态：  发生中
模型版本：  risk-v2.0
```

前置条件：后端 `OpinionOut` 须返回 `risk_factors / risk_model_version / severity_score / event_state`（E6）。前端 `Opinion` 类型同步补充字段。

> 若确认阶段希望最小化前端改动，可只加 `risk_factors`/`risk_model_version` 两字段到 schema，前端展示留作后续；但 `severity_score/event_state` 一并补出能让"风险依据"展示更完整，建议一并加入。

---

## 9. 测试落点（供实施参考）

新增 `tests/test_risk_explainability.py`，覆盖任务 5 项：

1. 爆炸伤亡 → `risk_factors.severity` 含 `爆炸`+`伤亡`，`severity_score` 仍 `100`（评分不变）
2. 普通投诉 → `risk_factors.severity` 为空（无真实危害词）
3. 防灾事件（"政府开展防灾演练"）→ `risk_factors.event_state` 存在（=prevent），且**不产生 critical**
4. 采集写回后 `risk_model_version == "risk-v2.0"`
5. 向后兼容：旧数据 `risk_factors=NULL` / `risk_model_version=NULL` 时 `AlertService.evaluate` 不报错

> 复用 Phase 2-A 的测试 DB 约定：conftest 默认 `:5433/opinion_test` 不可达，实际 `:5432/opinion_test`；运行时以 `DATABASE_URL` 覆盖 + `DB_IDENTITY_CHECK=off`。

---

## 10. 风险再评估

| 风险 | 等级 | 说明 / 缓解 |
|---|---|---|
| 迁移误连生产 | 低 | 实施前必跑 `db_identity_check.py`；迁移仅对测试库先验证再上生产 |
| `risk_factors` 为 NULL 时告警报错 | 低 | `alert_service` 对 None 显式降级（测试 #5 覆盖） |
| 前端无数据源 | 中 | `OpinionOut` 须同步加字段（E6），否则前端展示为空 |
| 评分被无意改变 | 极低 | `refine()` 仅"收集"命中词，sum 逻辑分毫不动；测试 #1 断言 `severity_score` 不变 |

---

## 11. 审计边界声明

- 本报告基于**只读**检查：读取 `risk_engine.py` / `opinion.py` / `alert.py` / `alert_service.py` / `collectors/service.py` / `schemas/opinion.py` / `OpinionDetailModal.vue` / 迁移链，未执行任何写入。
- 未连接生产库执行查询，未运行迁移，未部署服务。
- 所有"设计建议 / 落点清单"为**待确认**方案，实施阶段需用户确认后执行。

---

*审计完成。请确认是否按 §6 落点清单（E1–E9）进入 Design→Implement 阶段。*
