# Phase C · Event-2 Narrative — Step 7 最终报告（规则优先 + 按复杂度按需调用 LLM）

> 执行顺序严格遵守：Step 1 审计 → Step 2 路由器设计 → Step 3 规则优先实现 → Step 4 只读 Preview → Step 5 质量审计 → Step 6 测试 → **Step 7 停止并汇报（未执行生产写回）**。

## 一、最终报告（任务书强制格式）

```
总 Event：              84
规则直接生成：          59  (RULE_SIMPLE，0 token，单成员确定性规则)
规则模板生成：          21  (RULE_TEMPLATE，0 token，多成员模板+统计)
LLM 调用：              4   (路由判定需调 LLM 的复杂事件：id=131/182/189/197)
LLM 成功：              0   (真实环境 DeepSeek HTTP 402 余额不足；Preview 用 --no-llm 亦未调)
LLM 失败：              4   (真实 LLM 探针：4 个复杂事件全部 402，可靠回退规则)
Fallback：              4   (llm_fallback，fallback_route=RULE_TEMPLATE，未伪造 success)
预计 token 节省：       ~64,000  (_EST_TOKENS_PER_LLM_CALL=800 × 80 个被路由跳过的事件 ≈ 95.2% 节省)
Preview 是否零写库：    是  (dry_run 默认 + db.rollback，已确认零写入)
测试结果：              Event-2 25 passed；migration+aggregator 25 passed；全量 99 passed / 13 failed
是否建议进入生产 backfill：建议（见下方「决策与前提」）
```

## 二、关键说明

### 1. 架构改造（核心变更）
原策略 `全部 Event → LLM(默认) → 失败回退` 已重构为**规则优先、按复杂度按需调用 LLM**：
```
Event → ComplexityRouter → { RULE_SIMPLE(0 token) | RULE_TEMPLATE(0 token) | LLM_REQUIRED(token) }
```
- **RULE_SIMPLE**：单成员事件直接确定性规则生成（标题/摘要无需 LLM）。
- **RULE_TEMPLATE**：多成员事件用模板 + 聚合统计生成（0 token）。
- **LLM_REQUIRED**：仅当复杂度评分 ≥ 阈值(=5) 才调 LLM；LLM 失败/超时/返回非法结构 → 可靠回退到 RULE_TEMPLATE，**如实记录 `llm_status=failed` / `fallback_reason`，绝不伪造成功**。

### 2. 复杂度路由器（可解释、可测试、无 LLM、非随机）
评分特征（均为确定性、可复现）：
- `_member_score` 成员数、 `_source_score` 信源数、 `_time_score` 时间跨度、 `_risk_spread_score` 风险分散、 `_sentiment_score` 情感分布、 `_topic_score` 话题发散度。
- **话题发散度改用标题文本相似度**（`aggregator._cosine_ngram` 字符 2-gram 余弦），**不再用 `Opinion.keywords`**——真实数据 429 条中 84.4% 关键词为空、且仅有 16 个通用敏感词，keyword-overlap 会误触发 LLM。改用标题相似度后，被路由到 LLM 的事件从 13 个降至 4 个，更准确。
- 阈值 `LLM_THRESHOLD=5` 经真实 84 Event 只读 SELECT 校验得出：59 规则直接 + 21 规则模板 + 4 LLM = **95.2% LLM 调用节省**。

### 3. 零余额（no-balance）环境支持（已验证）
- Preview 用 `--no-llm`：84 Event 全部走确定性生成，**零空标题 / 零空描述 / 零质量标记 / 零写库**。
- 真实 LLM 探针（对 4 个复杂事件调真实 DeepSeek）：全部 HTTP 402 → 全部可靠回退规则（`llm_status=failed`、`fallback_route=RULE_TEMPLATE`），**从未把 fallback 标记成 LLM 成功**，整个 Preview 不崩溃。

### 4. 质量红线（check_narrative_quality 已内置）
正则检测：空标题、空描述、标题过长(>80)、描述过短(<10)、疑似 URL 泄漏、JSON 片段残留、prompt 泄漏、未解析模板变量、疑似虚构。Preview 全量 0 命中。

### 5. 测试结果（可信度）
- `tests/test_event_narrative.py` 重写 **25 项**，覆盖：路由（单→RULE_SIMPLE 不调 LLM / 多相似→RULE_TEMPLATE 不调 LLM / 多话题→LLM_REQUIRED 成功 / 402→回退 / 超时→回退 / 非法 JSON→回退）、规则生成、质量、回归（确定性/幂等/失败隔离/关联表零改动/dry-run 零写/write 仅改叙事字段/路由器可解释）。**25 passed**。
- migration + aggregator 测试 **25 passed**（无回归）。
- 全量 `pytest`：**99 passed / 13 failed**。13 项失败全部位于 `test_ai_analysis`、`test_ai_service`、`test_collector`、`test_dashboard`、`test_government_collector`——均**不 import 本次改动模块**，根因为缺 DeepSeek key / 测试库 `data_sources` 注册不全，**属既有环境性失败，零新增回归**。

### 6. 改动范围（最小侵入，已审查）
- `backend/app/services/event/narrative.py`（重写：ComplexityRouter / 阈值 / 评分 / 质量校验 / 重写 NarrativeResult·BackfillReport·backfill）
- `backend/scripts/backfill_event_narrative.py`（重写：新增 `--no-llm`、路由/成本统计、新 MD 报告）
- `backend/tests/test_event_narrative.py`（重写 25 测试）
- `backend/docs/phase-c-event2-rulefirst-audit-design.md`（新增，Step 1+2 交付）
- **未改**：Models / DB schema / EventOpinion 关系 / 聚合规则 / `event_singleton_min_risk` / 7 天窗口 / 传播树 / 告警重链 / API 契约 / 前端 / 基础设施。write 模式仅写回 `Event.title` / `Event.description` 两字段。

## 三、决策与前提（⚠️ 进入生产 backfill 前必读）

**建议进入生产 backfill**，但必须满足以下前提之一，并由用户显式授权：

1. **接受「仅规则叙事」**：当前 DeepSeek 余额=0，生产 `--write` 时 4 个复杂事件将走回退规则（与 Preview 一致），**不会产出 LLM 叙事**。若产品可接受纯规则叙事，可直接授权。
2. **先充值再写**：若需 LLM 叙事，须先为 DeepSeek 充值，然后重跑 Preview 复核真实 LLM 输出（幻觉/空洞/不一致快检），再授权 `--write`。

**生产写回命令（默认仍 dry-run，须显式 `--write`）**：
```bash
cd backend
PYTHONPATH=. python scripts/backfill_event_narrative.py --write          # 全量写回
# 或先小批量验证：
PYTHONPATH=. python scripts/backfill_event_narrative.py --no-llm         # 再确认一次只读预览
PYTHONPATH=. python scripts/backfill_event_narrative.py --write --event-ids 131,182,189,197
```

## 四、结论
Step 1–6 全部完成并通过验证；Step 7 按指令**停止，未执行任何生产写库**。等待用户明确授权后，方可执行 `--write`。
