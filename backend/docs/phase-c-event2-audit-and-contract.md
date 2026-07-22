# Phase C-Event-2：Narrative Backfill — 审计报告 · 生成契约 · 变更说明

> 阶段范围：仅生成事件叙事（title/description），不重新迁移、不改成员归属、不改聚合规则。
> 执行状态：**Phase 1–5 已完成（含生产只读 Preview）；尚未执行生产写回，等待显式授权。**
> 最终判定：**READY FOR PRODUCTION BACKFILL**（见文末）。

---

## 一、Phase 1 代码与模型审计结论

### A. 当前实现状态

| 项 | 现状 |
|---|---|
| **Event Model** | `app/models/event.py` 仅 8 列：`id, title(String512), description(Text), keyword, risk_level(low/medium/high), opinion_count, first_time, last_time`。**无** `risk_score`/`member_count`/`source`/`status` 列（`status` 仅 API 层硬编码 `"active"`）。 |
| **title/description 当前值** | 由 `app/services/event/aggregator.py::_create_event`（L413-431）写入**临时占位**：`title=top.title`（簇内最高风险舆情标题）、`description=(top.content or "")[:200]`（该舆情正文前 200 字）。`migration.py` 重建时沿用同一占位逻辑。代码注释已明确标注「待 Event-2 替换」。 |
| **API 承载** | 列表接口 `GET /events` 已返回 `title`；详情 `GET /events/{id}` 已返回 `title`+`description`。**复用两列即可完整承载 Event-2 叙事，无需改 API contract**。 |
| **现有 LLM 设施** | 唯一路径 = DeepSeek（OpenAI 兼容 SDK）。`DeepSeekProvider.analyze(text)` 返回 `AIAnalysisResult`。原实现**无 timeout、无 max_retries 覆盖、无限流/并发控制、无 logging**；异常一律上抛由 `AIService` 降级。 |
| **可复用 Narrative 能力** | **无**事件级叙事生成器；仅有单条舆情摘要 `AIService.analyze`（输出结构固定，不能直接用于事件级）。 |
| **生产 84 Event 数据可读性** | 经只读统计：59 单成员 / 25 多成员（最多 5）；风险 44 high / 18 medium / 22 low；全部 429 条 Opinion **均有非空 title 与 summary（系统研判摘要）**，可支撑叙事生成。DeepSeek **已配置**（真实调用可用）。 |

### B. Event-2 最小改动方案

1. 复用 `Event.title` / `Event.description`，**不新增 DB 列、不做 schema migration**。
2. 扩展（非新建第二套）现有 `DeepSeekProvider`：抽出通用 `_chat_json(messages, schema)` 调用入口，新增 `generate_event_narrative(context)`；原 `analyze` 改走同一入口（行为不变）。新增 `timeout`/`max_retries` 与 `logging`。
3. 新增 `app/services/event/narrative.py`：
   - `build_context(db, event)`：只读查询 EventOpinion→Opinion，**脱敏**构建上下文（仅用 title/summary/keywords/risk_score/sentiment/source，绝不含 content/url/region_id/作者）。成员按有效时间升序（确定性）。
   - `rule_fallback_narrative(ctx)`：**确定性**规则叙事（单成员用真实标题+摘要；多成员用关键词+风险+来源+时间跨度拼装）。
   - `generate_event_narrative(ctx, llm_callable)`：LLM 优先，任何失败（超时/解析/校验/空/类型错）→ 降级规则叙事并**如实记录** `error_type`/`fallback_reason`；仅当 fallback 自身也失败（如无成员）才标 `failed`。
   - `backfill(...)`：dry-run（默认）/ write 双模式；支持 `event_ids`/`limit`/`min_interval`（限流）/注入 `llm_callable`（测试）；仅 write 模式写回 `title`/`description` 两字段。
4. 新增 `scripts/backfill_event_narrative.py`：CLI，默认 dry-run（只读 SELECT+回滚），仅显式 `--write` 才写库；产出 JSON+MD 审计报告。
5. 新增 `app/schemas/event_narrative.py`：`EventNarrative`（title/description，仅作 LLM 输出载体，不映射到新表列）。

### C. 是否需要数据库 migration

**否。** `title`/`description` 已存在且已被 API 消费，重建时已安全填充占位值。Event-2 仅覆盖写入这两列，零结构变更。

### D. 是否需要 API / 前端改动

**否。** 列表已含 `title`、详情已含 `title`+`description`。审计确认 Event-2 结果可经现有字段正常承载，故不修改 `app/schemas/event.py`、`app/api/events.py` 或前端。

### E. 生产 backfill 风险点与回滚方案

| 风险 | 缓解 / 回滚 |
|---|---|
| 模型虚构事实（幻觉） | 契约硬性约束「仅基于成员事实、禁虚构」；Prompt 脱敏且只投喂成员已存在字段；preview 报告附质量标记（title_too_long/desc_too_short/possible_url_leak）供人工复核。 |
| 限流/超时（DeepSeek 免费档 ~20 RPM） | `min_interval` 默认 3.0s 控速；SDK `max_retries=2` 指数退避；超时即降级规则叙事，不中断批次。 |
| 单事件失败污染批次 | `backfill` 逐事件 try；失败仅该事件标 `fallback`/`failed`，其余继续（测试 11 验证）。 |
| 误写其它表/字段 | write 模式**仅** `ev.title=...; ev.description=...`；`opinion_count/risk_level/keyword/first_time/last_time` 与其它关联表零改动（测试 12/14 验证）。 |
| 写回后需回滚 | 回滚等价「用规则 fallback 或占位值再跑一次 dry→write」；因两字段可重复覆盖、关联表未动，回滚成本低且安全。绝不执行 `DELETE FROM propagation_nodes WHERE event_id IS NULL`。 |
| 幂等性 | 重复执行只覆盖写同一事件的两字段，无新增/重复行；fallback 路径字节级确定性，success 路径覆盖式幂等（无数据损坏）。测试 10 验证。 |

---

## 二、Phase 2 Event-2 Narrative 生成契约

### 输出结构（`EventNarrative`）
```json
{ "title": "事件标题（≤120 字，硬截断）", "description": "事件描述（≤500 字，硬截断）" }
```

### 生成规则
1. **事实边界**：叙事**只**基于该 Event 已确定的 EventOpinion 成员生成；绝不跨事件合并（Prompt 仅投喂本事件成员）。
2. **脱敏输入**：成员事实仅含 `title / summary / keywords / risk_score / sentiment / source(平台名)`；**禁止**把 `content / url / region_id / 作者身份` 送入模型。
3. **单成员 Event**：标题取该舆情真实标题（或「{risk}风险舆情」兜底），描述取该舆情 summary（无则脱敏模板）。
4. **多成员 Event**：标题用「一条具体 Opinion 标题 + 等N条相关舆情聚集」（如「河北多举措推进基础教育扩优提质等2条相关舆情聚集」；组合超 80 字时该具体标题用省略号截断），描述按时间顺序说明发展、风险等级、涉及来源平台、主要关键词，最早一条标题作锚点；不重复罗列、不虚构。
5. **防错误合并**：输入已是被判定同事件的成员，Prompt 明示「不得假设事件外信息」；不调用聚类/合并逻辑。
6. **防虚构**：Prompt 硬性要求「禁止包含未出现于事实的地点/人物/机构/数字/时间」；模型输出经 pydantic 校验 + 非空校验 + 长度截断。
7. **时间/风险/来源/重复处理**：成员按有效时间升序输入；风险取事件 `risk_level`；来源平台去重列举；重复信息合并概括。
8. **模型失败 fallback**：超时/解析错/校验错/空内容/类型错 → 确定性规则叙事，原样记录 `error_type`/`fallback_reason`；不得静默。
9. **长度限制**：title ≤ 120 字、description ≤ 500 字（Prompt 建议 ≤80/≤400，编排器硬截断）。
10. **保留原始值作参考**：dry-run/preview 报告同时给出 `current_title`/`current_description` 与拟议值，便于差异审计；生产写回前不破坏原值。

---

## 三、变更说明（本阶段实际改动）

**新增文件**
- `app/schemas/event_narrative.py` — `EventNarrative` schema（LLM 输出载体，不映射新列）。
- `app/services/event/narrative.py` — 上下文构建、规则 fallback、编排器、backfill 运行器。
- `scripts/backfill_event_narrative.py` — CLI（默认 dry-run，仅 `--write` 写回）。
- `tests/test_event_narrative.py` — 14 项测试，全部通过。
- `docs/phase-c-event2-audit-and-contract.md` — 本文件。

**修改文件**
- `app/core/config.py` — 新增 `deepseek_timeout=30.0`、`deepseek_max_retries=2`（仅影响 DeepSeek 客户端，不改聚合/聚类规则）。
- `app/services/ai/providers/deepseek.py` — 抽出通用 `_chat_json`；新增 `generate_event_narrative`、logging、构造函数 timeout/max_retries；`analyze` 改走同一入口（行为不变，缩小为单一 LLM 调用路径）。

**环境依赖**
- 测试环境补全了缺失的项目依赖 `apscheduler==3.11.3`（被 `app.core.scheduler` 间接引用，conftest 加载 `app.main` 所需；属既有依赖，非本阶段引入）。

---

## 四、本阶段明确未修改的表 / 字段 / 功能

| 类别 | 未修改项 |
|---|---|
| 表 | `opinions`、`event_opinions`、`propagation_nodes`、`alert_records`、`events`（行与结构均未动；仅 `events.title`/`events.description` 两列在**生产写回阶段**会被更新，当前 preview 未写） |
| Event 字段 | `keyword`、`risk_level`、`opinion_count`、`first_time`、`last_time`（写回模式亦不动，测试 14 验证） |
| 聚合/聚类 | `event_singleton_min_risk`、`event_window_days`、`cluster_opinions`、aggregator 成员判定逻辑 |
| 迁移 | 未重新执行 `migrate_events`；未改 `EventOpinion` 成员归属 |
| API / 前端 / Schema contract | `app/schemas/event.py`、`app/api/events.py`、前端均未改 |
| 清理操作 | **未**执行 `DELETE FROM propagation_nodes WHERE event_id IS NULL` 或任何无关清理/汇编 |

---

## 五、生产只读 Preview（Phase 5）

- 对生产 84 个 Event 执行 **dry-run（只读 SELECT + 回滚，零写库）**，调用真实 DeepSeek 生成拟议叙事。
- 产出可审计报告：`backend/_event2_preview/event2_preview.json` 与 `event2_preview.md`。
- 报告字段：`event_id`、`member opinion ids`（经 context 可溯）、`current title/description`、`proposed title/description`、`status`、`fallback_reason`、`member_count`、`elapsed_ms`、质量标记。
- 质量快检：标题过长（>80）、描述过短（<10）、疑似 URL 泄露、生成失败。

---

## 六、最终状态

**READY FOR PRODUCTION BACKFILL**

依据：
1. 审计确认 `title`/`description` 足以承载 Event-2，零 schema migration、零 API 改动。
2. 实现仅改叙事字段，复用既有单一 LLM 路径，含 timeout/retry/logging/限流。
3. 14 项测试全部通过（单/多成员、时间顺序、混合风险、模型成功/超时/非法结构/空内容、fallback、幂等、单事件失败隔离、关联表零改动、dry-run 零写、write 仅改叙事字段）。
4. 现有 33 项 event/AI 测试无回归。
5. 生产只读 Preview 已产出，待人工复核幻觉/空洞/不一致后授权写回。

**下一步**：待用户显式授权后，以
`python scripts/backfill_event_narrative.py --write [--event-ids ...] [--limit ...] [--min-interval ...]`
执行生产写回（默认仍只读；`--write` 为唯一写库开关）。
