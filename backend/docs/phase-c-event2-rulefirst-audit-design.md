# Phase C / Event-2 Narrative：Rule-first + 按需 LLM 改造 —— 审计与设计

> 阶段：Step 1 审计 + Step 2 复杂度路由设计（阈值已由 84 个真实 Event 只读验证）
> 当前状态：**尚未改动任何项目代码**；仅运行只读 SELECT 分析。
> 最终判定（写回）：**待 Step 7 汇报后由用户显式授权**。

---

## 一、当前实现审计结论（Step 1）

### 1.1 涉及文件

| 文件 | 角色 | 本次是否需要改 |
|---|---|---|
| `app/services/event/narrative.py` | 上下文构建 / 规则 fallback / 编排器 / backfill 运行器 | **需改**（核心） |
| `scripts/backfill_event_narrative.py` | CLI（默认 dry-run） | **需改**（扩展路由报告 + 质量统计） |
| `app/services/ai/providers/deepseek.py` | 唯一 LLM 路径 `generate_event_narrative` | **不改**（沿用；402/超时/解析异常已正确上抛） |
| `app/schemas/event_narrative.py` | `EventNarrative(title, description)` | **不改**（已是 LLM 输出载体） |
| `app/models/event.py` / `opinion.py` / `event_opinion.py` | 数据模型 | **不改**（标题/描述复用既有 `String(512)`/`Text`） |
| `app/services/event/aggregator.py` | 聚类（`_cosine_ngram` 等） | **不改**（仅**复用** `_cosine_ngram` 纯函数做标题相似度） |
| `app/core/config.py` | DeepSeek 配置 | **不改** |
| `tests/test_event_narrative.py` | 14 项测试 | **需改**（适配新路由状态枚举 + 新增路由/质量用例） |
| `docs/phase-c-event2-audit-and-contract.md` | 上一阶段契约 | **不改**（本文件为其补充） |

### 1.2 当前编排逻辑（改造前）

`generate_event_narrative(ctx, llm_callable)`：
- **默认调用 LLM**（即便单成员事件也调）；
- 任何异常（超时/解析/校验/空/类型错）→ 降级 `rule_fallback_narrative`；
- 仅 fallback 自身失败（无成员）→ `failed`。

问题（与本次目标冲突）：
- 单成员 / 高度相似双成员等简单事件**也消耗 LLM token**；
- 无复杂度前置判断（`if len(opinions) > 1: call_llm()` 思路）；
- 生产 Preview 已证实：84 个事件**全部尝试 LLM**，因 DeepSeek 402 全部 fallback —— 80 次本不必要的调用。

### 1.3 现有 fallback 可复用性

`rule_fallback_narrative` 已具备**确定性规则生成**能力，是 Rule-first 的良好基座：

- **单成员分支**（→ 对应 Layer 1 RULE_SIMPLE）：
  - 标题取真实 `title`（或 `{risk}风险舆情` 兜底）；
  - 描述取真实 `summary`（**非 content 前 200 字**），无 summary 时脱敏模板。
  - ✅ 已满足「不粗暴用 content 前 200 字」「保持事实不变」。
- **多成员分支**（→ 对应 Layer 2 RULE_TEMPLATE）：
  - 标题：`{一条具体 Opinion 标题}等N条相关舆情聚集`（如「河北多举措推进基础教育扩优提质等2条相关舆情聚集」）；组合超 `TITLE_SOFT_MAX(80)` 时对该具体标题用省略号截断（如「河北多举措推进基础…等2条相关舆情聚集」）；不再使用旧的「关于{kw}的聚集舆情（N条）」或「N条相关舆情聚集（risk风险）」形式；
  - 描述：时间跨度 + 风险等级 + 来源平台 + 关键词 + 首条标题锚点；
  - ✅ 纯事实拼装，无虚构、无模板腔夸张。

**结论**：现有两个分支可直接拆为 `generate_simple_rule()` 与 `generate_template_rule()`，无需重写叙事文本逻辑；统一质量检查作为独立函数叠加。

### 1.4 现有 Preview / backfill 流程

- `backfill(..., dry_run=True, write=False)` 默认只读 SELECT + `db.rollback()`，**零写库**（已验证幂等、单事件失败隔离、关联表零改动）。
- 报告字段已有：`status/fallback_reason/member_count/elapsed_ms/current_title/current_description`。
- **需扩展**：`complexity_score`、`route`、`llm_called`、`llm_status`、`token_usage`、`fallback_route`、质量标记 `quality_flags`、以及聚合 `estimated_tokens_saved`。

### 1.5 幂等性 / 写回安全性（确认无需新机制）

- 写回仅 `ev.title=...; ev.description=...`，关联表零改动（测试 12/14 已覆盖）；
- 规则生成字节级确定 → 重复执行结果一致；
- 现有 `title≤120 / description≤500` 硬截断已就位。

### 1.6 风险点

| 风险 | 说明 | 缓解 |
|---|---|---|
| 关键词字段噪声 | 真实数据 `keywords` 几乎全空，仅 16 通用词 → 不能用于主题差异信号 | 改用**标题文本相似度**（复用 `_cosine_ngram`） |
| 路由误把「重复转载」当复杂 | 同一文章多源转载（184/185/186/200）标题高度一致 | 标题高相似 → `topic=0`，不进 LLM |
| 路由误把「按大词聚拢的无关新闻」当简单 | 182/189 等被 `河北` 等宽词聚拢、标题各异 | 标题低相似 + 多成员 → 进 LLM |
| LLM 状态枚举变更 | 旧 `success/fallback` 被测试引用 | 改为 `rule_simple/rule_template/llm_success/llm_fallback` 并更新测试 |
| 0 余额环境 | DeepSeek 402 / 未配置 key → 失败 | LLM_REQUIRED 失败可靠 fallback 到规则；Preview 如实标记 `llm_fallback` |

---

## 二、复杂度路由设计（Step 2，阈值经真实数据验证）

### 2.1 特征（全部可解释、可测试、不依赖 LLM/随机）

| 特征 | 取值规则 |
|---|---|
| `member` 成员数 | 1→0，2→1，3→2，4→3，≥5→4 |
| `source` 来源数 | 1→0，2→2，≥3→3 |
| `time` 时间跨度 | <1天→0，1~3天→1，≥3天→2 |
| `risk` 风险差 | max−min risk_score <20→0，<40→1，≥40→2 |
| `sentiment` 情感差 | 1种→0，2种→1，3种→2 |
| `topic` 主题差异（**标题相似度**，非关键词） | 平均两两标题相似 ≥0.6→0，≥0.30→1，<0.30→2 |

> `topic` 复用 `app.services.event.aggregator._cosine_ngram`（字符 2-gram 余弦，已测试纯函数）。
> 之所以用标题而非关键词：真实数据中 `opinions.keywords` 绝大多数为空或仅含 16 通用词，关键词重叠无法区分主题。

`complexity_score = member + source + time + risk + sentiment + topic`

### 2.2 路由决策

```
if member_count == 1:
    route = RULE_SIMPLE        # 单成员事件永不调用 LLM
elif complexity_score >= LLM_THRESHOLD:
    route = LLM_REQUIRED
else:
    route = RULE_TEMPLATE
```

**选定 `LLM_THRESHOLD = 5`**（理由见下）。

### 2.3 真实 84 Event 路由分布（只读验证）

| 阈值 | RULE_SIMPLE | RULE_TEMPLATE | LLM_REQUIRED | LLM 调用占比 | 节省 |
|---|---|---|---|---|---|
| 5 | 59 | 21 | **4** | 4.8% | **95.2%** |
| 6 | 59 | 23 | 2 | 2.4% | 97.6% |
| 7 | 59 | 24 | 1 | 1.2% | 98.8% |

**选 5**：4 个 LLM 事件（131/182/189/197）均为真实复杂/多主题/多源/情感或风险混合，符合「规则模板会明显生硬」的判定；其余 80 个事件用规则即可稳定产出，避免 80 次无意义 LLM 调用。

> 注：84 个 Event 中 59 个为单成员（占 70%），这是「Rule-first 节省显著」的硬数据基础。

### 2.4 路由结果枚举

- `RULE_SIMPLE`：单成员 → `generate_simple_rule`，`llm_called=False`
- `RULE_TEMPLATE`：中等 → `generate_template_rule`，`llm_called=False`
- `LLM_REQUIRED`：复杂 → 调用 LLM
  - 成功 → `status=llm_success`，`llm_called=True`，`llm_status=success`
  - 失败（402/超时/解析/空/类型错）→ `status=llm_fallback`，`llm_called=True`，`llm_status=failed`，`fallback_route=RULE_TEMPLATE`，并如实记录 `fallback_reason`

### 2.5 统一质量检查（规则与 LLM 同标准）

`check_narrative_quality(title, description) -> list[str]` 覆盖：
- 非空；长度合理（title≤120 / desc≤500，已由截断兜底）；
- 无 URL 泄露；无 JSON 残片（```json / `{` 结构）；
- 无 Prompt 泄漏（「作为AI」「作为人工智能」「AI助手」等元话语）；
- 无未替换模板变量（`{...}` / `{{...}}`）；
- 无虚构事实风险标记（如检测到「引发广泛关注」「舆论持续发酵」等空洞夸张表述 → `possible_fabrication`）。

LLM 生成额外约束（Prompt 已含）：仅基于提供事实、禁外部知识/推测/夸张、固定 JSON 结构。

---

## 三、最小改动清单（待 Step 3 执行）

1. `narrative.py`
   - 新增 `ComplexityRoute` 枚举、`classify_complexity(ctx) -> (route, score, detail)`（复用 `_cosine_ngram`）。
   - 拆分 `rule_fallback_narrative` → `generate_simple_rule()` + `generate_template_rule()`（逻辑平移，叙述文本基本不变）。
   - 新增 `check_narrative_quality()`。
   - 改造 `generate_event_narrative`：先路由；RULE_* 直接规则生成（不调 LLM）；LLM_REQUIRED 调 LLM，失败 fallback；结果含 `route/complexity_score/llm_called/llm_status/token_usage/fallback_route/quality_flags`。
   - 扩展 `NarrativeResult` 与 `BackfillReport` 字段（聚合 `rule_simple/rule_template/llm_success/llm_fallback/estimated_tokens_saved`）。
2. `backfill_event_narrative.py`：报告扩展上述字段；新增 `--no-llm` 预览开关（默认仍尝试真实 LLM，0 余额下可靠 fallback）；控制台与 MD/JSON 输出路由与成本统计。
3. `tests/test_event_narrative.py`：更新状态枚举；新增路由/质量用例（见 Step 6 要求）。

**明确不动**：Model / DB schema / API / 前端 / 聚合算法 / `event_singleton_min_risk` / 7 天窗口 / 传播树 / 告警重链 / `DeepSeekProvider` 主路径。
