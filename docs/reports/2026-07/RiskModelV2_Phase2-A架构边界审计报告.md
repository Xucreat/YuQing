# Risk Model V2 Phase 2-A 架构边界审计报告

> 审计性质：**只读**（未改代码 / 未改数据库 / 未执行迁移 / 未部署服务）
> 审计目标：确认生产风险链路满足
> 「采集风险识别不依赖大模型，AI 仅用于用户主动触发的事件研判」
> 审计时间：2026-07-24（基于已上线生产代码）

---

## 一、结论速览

| 审计项 | 结论 |
|---|---|
| 自动风险链路（采集→告警）是否 0 token | ✅ **是**，纯规则 + 纯函数，全程无 LLM |
| AI 研判链路是否与告警生成隔离 | ✅ **完全隔离**（字段/控制/评级三向隔离） |
| 定时采集 / 手动采集是否都过 RiskEngine | ✅ **都过**（共用 `_process_collector`） |
| 是否存在架构耦合需修正 | ❌ **无耦合，无需修正** |

**最终判定：生产链路已天然满足约束，无需任何最小修正。**

---

## 二、A. 当前真实调用链图

```
═══════════════════════════════════════════════════════════════════════════
 链路①：自动风险链路（采集 → 舆情 → 风险精炼 → 告警）  ★ 0 token ★
═══════════════════════════════════════════════════════════════════════════
 [定时 cron]  scheduler._run_collector_job()
      │
      ▼
 CollectorService.collect_and_analyze(db)            # 顺序（定时）
      │
 [手动]      scheduler/collector.py  POST /api/collector/run
      │   → CollectorService.collect_and_analyze_concurrent(...)   # 并发（手动）
      │
      └─► 两者都调用 ► _process_collector(db, collector, ...)
                              │
                              ├─► RuleFallbackProvider.analyze(text)   ★纯规则，无网络★
                              │       （BASE_RISK=20 + Σ10×weight，字符串匹配）
                              │
                              ├─► RiskEngine.refine(title, content, sentiment)  ★纯函数★
                              │       （severity/event_state/resolution_flag/final_risk_score）
                              │
                              └─► Opinion 写库
                                       risk_score / severity_score / event_state / resolution_flag
                                       / sentiment / summary / keywords （系统研判报告字段）

 [旁路·事件聚合]  auto_aggregate_after_collect(...)   ★纯 Python 2-gram 余弦★
      （读取 ai_keywords 仅作"高区分度信号"，不调 LLM；与告警无直接关系）

 [定时 cron]  scheduler._run_alert_eval_job()
      │
      ▼
 AlertService.evaluate(db)                            ★纯规则，无 LLM★
      │  — 读 opinion.risk_score / severity_score / sentiment / keywords / title / content
      │  — _map_risk_level(risk_score) → low/medium/high
      │  — severity_score ≥ 70 → critical（Phase 2-A）
      │  — positive 且无危害词 → 降级 low（Phase 1）
      ▼
 AlertRecord（risk_level 由风险分派生，与 AI 无关）

═══════════════════════════════════════════════════════════════════════════
 链路②：AI 研判链路（用户主动触发，独立）  ★ 仅此处有 DeepSeek ★
═══════════════════════════════════════════════════════════════════════════
 [用户手动]  POST /api/analyze/{opinion_id}   （Bearer JWT 保护）
      │
      ▼
 api/analysis.py  → DeepSeekProvider().analyze(text)   ★ 唯一 LLM 调用点① ★
      │
      └─► 仅写 ai_* 字段（ai_summary/ai_sentiment/ai_risk_score/ai_keywords/...）
          **不覆盖** 系统研判报告字段；**不调用** AlertService；**不触发**告警

 [事件叙事]  generate_event_narrative(ctx)   ★ 唯一 LLM 调用点②（按需路由）★
      （services/event/narrative.py：rule-first，仅复杂事件调 DeepSeek）
      → 写 event 叙事文本；与 AlertRecord 生成无数据流交叉
```

**关键边界事实：**
- 自动链路（①）引用的 AI 组件**只有 `RuleFallbackProvider`**，且该组件内部**从不实例化 / 调用 `DeepSeekProvider`**。
- 自动链路引用 `RiskEngine`、`_map_risk_level`、`get_monitoring_keywords` —— 全部为纯函数 / 纯查询，无 IO 外部调用。
- `DeepSeekProvider` 仅被 `api/analysis.py` 与 `event/narrative.py` 直接引用，二者**均不在自动风险链路中**。

---

## 三、B. 自动风险链路是否 0 token

**结论：是。0 token、0 LLM 调用、0 AIService 依赖。**

证据链（逐项核对源码）：

1. **`RuleFallbackProvider.analyze`（`services/ai/fallback.py`）**
   - 全函数仅做 `word in text` 字符串匹配 + 累加 `BASE_RISK + Σ(10×weight)`。
   - import 仅 `app.schemas.ai.AIAnalysisResult` 与 `app.services.ai.providers.base.BaseAIProvider`。
   - `base.py` 为**纯抽象基类**（仅 `ABC` + `@abstractmethod`），无 openai / requests / httpx 依赖。
   - → 无任何网络出口，无 token 消耗。

2. **`RiskEngine.refine`（`services/risk_engine.py`）**
   - 纯函数：`__init__` 仅注入词典，`refine` 仅做算术与状态判定。
   - 不 import 任何 DB / LLM / 网络模块。
   - → 零 IO。

3. **`AlertService.evaluate`（`services/alert_service.py`）**
   - 全部 import：`keyword_service.get_monitoring_keywords`、`event.aggregator._map_risk_level`（纯函数）、ORM 模型。
   - 函数体 = DB 读取 + 阈值算术 + 写 `AlertRecord`。无 LLM。

4. **`collectors/service.py` 装配隔离**
   - 第 45 行 `from app.services.ai.fallback import RuleFallbackProvider`。
   - **从未** import 或实例化 `AIService` 或 `DeepSeekProvider`。
   - → 自动采集路径连 DeepSeek 客户端都不会被构造，自然不可能产生 token。

5. **全局 grep 交叉验证**
   - `chat.completions.create` / `OpenAI` / `DeepSeek` 调用点**仅**出现在：
     - `services/ai/providers/deepseek.py`（定义）
     - `app/api/analysis.py`（手动触发）
     - `app/services/event/narrative.py`（事件叙事）
   - 以上**均不在** Collector → Opinion → RiskEngine → AlertService 链路内。

---

## 四、C. AI 研判链路是否完全隔离

**结论：是，三向隔离（字段隔离 / 控制隔离 / 评级隔离）。**

1. **字段隔离（数据不交叉）**
   - AI 路径（`api/analysis.py`）只写 `ai_*`（ai_summary / ai_sentiment / ai_risk_score / ai_keywords / ai_analysis_suggestion / ai_analysis_status / ai_analysis_time）。
   - `AlertService.evaluate` 读取的字段为 `risk_score / severity_score / sentiment / keywords / title / content` —— **完全不读任何 `ai_*` 字段**。
   - 两链路对同一 `Opinion` 行写入不同列，互不影响。

2. **控制隔离（触发不联动）**
   - `api/analysis.py` 成功后只 `db.commit()` 并返回 `OpinionOut`；**不调用** `AlertService.evaluate`、不调用 `auto_aggregate_after_collect`。
   - DeepSeek 失败（`except Exception`）仅置 `ai_analysis_status='failed'` 并返 500，**系统研判报告与告警完全不受影响**。

3. **评级隔离**
   - `AlertRecord.risk_level` 由 `opinion.risk_score` / `opinion.severity_score` 派生（Phase 1 + Phase 2-A），与 `ai_risk_score` 无任何关系。
   - `RiskEngine` 仅在自动链路被引用，AI 路径不 import 它 → 风险精炼逻辑不被 AI 路径污染。

4. **事件叙事隔离**
   - `event/narrative.py` 的 DeepSeek 调用产出事件叙事文本，仅供事件详情展示；`AlertService.sync_alert_events` 仅按 `opinion_id` 成员关系链接 alert↔event，不消费叙事内容。
   - 叙事的 LLM 路由为 **rule-first + 复杂度阈值**：简单事件（单/中等成员）永远不调 LLM；仅复杂事件按需调用，且失败可靠 fallback（绝不伪造）。这进一步收窄了 token 面。

---

## 五、D. 架构耦合与最小修正方案

**结论：未发现架构耦合，设计已天然满足约束，无需任何修正（无代码改动）。**

为长期稳健性，仅给出 3 条**非强制护栏建议**（均为"守住现状"，不要求立即改代码）：

| # | 护栏 | 风险若被破坏 | 当前状态 |
|---|---|---|---|
| 1 | `collectors/service.py` 必须**持续只用 `RuleFallbackProvider`**，禁止改为 `AIService.analyze()`（后者会按配置自动选 DeepSeek） | 自动采集链路将获得 LLM 依赖，违反 0-token | ✅ 已固化（文件头注释 + 直连 RuleFallbackProvider） |
| 2 | 事件聚合（`auto_aggregate_after_collect`）的 `ai_keywords` 仅作"已触发才存在的信号"，不得改为"聚合时自动补调 DeepSeek 抽取" | 聚合旁路突破 0-token | ✅ 当前仅读字段、不调 LLM |
| 3 | 明确 `AIService`（`services/ai/service.py`）为遗留抽象：当前**无任何调用方**（collector 用 RuleFallbackProvider、analysis 用 DeepSeekProvider 直连），非自动链路组件 | 未来误接进采集主路径 | ✅ 现状安全，建议加注释标注"非自动链路使用" |

> 说明：第 3 条中的 `AIService` 经 grep 确认无生产调用方，是潜在混淆点而非运行风险；标注即可，不必删除（避免误伤）。

---

## 六、审计边界声明

- 本次为**纯只读**审计：
  - 未修改任何 `.py` 源码；
  - 未连接生产库执行写操作（仅通过 db_identity_check 确认环境，未跑迁移）；
  - 未部署 / 重启任何服务。
- 核对依据：生产已上线代码（`collectors/service.py`、`ai/fallback.py`、`risk_engine.py`、`alert_service.py`、`api/analysis.py`、`event/narrative.py`、`event/aggregator.py`、`core/scheduler.py`、`api/alerts.py` 及全局 grep）。

---

## 七、回答用户四个检查点

1. **自动采集路径（定时 + 手动）是否都过 RiskEngine？**
   → 是。定时走 `collect_and_analyze`、手动走 `collect_and_analyze_concurrent`，二者**共用** `_process_collector`，均在第 382 行调用 `RiskEngine.refine()` 写回新字段。

2. **事件详情 AI 研判路径是否独立、不影响告警？**
   → 是。`api/analysis.py` 只写 `ai_*` 字段，不调用 `AlertService`，不触发告警；`AlertService` 不读 `ai_*` 字段。

3. **自动风险链路是否 0 token？**
   → 是。详见第三节 5 项证据。

4. **AI 研判链路是否完全隔离？**
   → 是。详见第四节三向隔离。

**综合：架构边界达标，不需修正。**
