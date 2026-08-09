# Phase Foreign-Source-3A 外网风险与情感分析设计评审

审计日期：2026-08-07  
工作区：`C:\Users\Administrator\Desktop\YQ`  
阶段性质：设计评审与只读审计  
本阶段状态：未实施代码、未新增迁移、未调用外部 AI、未执行外网采集

## 1. 执行边界

本阶段只允许读取代码、模型、API、前端、测试和数据库状态，并新增本报告。已执行：

- `git status --short`
- `alembic current`
- Phase 0、Phase 1、Phase 1.1、Phase 2 和 Phase 3 审计材料阅读
- 外网基础链路、国内 Risk/AI 实现和相关测试阅读
- 应用默认数据库的 SELECT 级状态检查
- 代理环境变量存在性检查，不输出任何连接串或密钥

未执行：

- 未修改 Python、TypeScript、Vue、SQL、Alembic 或配置文件
- 未修改数据库结构或数据
- 未启用、停用或切换外网数据源
- 未启动自动调度或采集任务
- 未调用外部 AI、RiskEngine 生产链路、Event、Alert、Dashboard、地图或热词
- 未写入 `foreign_opinions` 或 `opinions`
- 未撤销、覆盖、删除或整理工作区已有修改和未跟踪文件

## 2. 前置检查结果

### 2.1 工作区

`git status --short` 显示工作区在本阶段开始前已经存在外网链路源码修改、测试文件、Phase 报告、备份目录和临时文件。本阶段没有改变这些既有状态。

### 2.2 Migration

`alembic current` 返回：

```text
foreign_source_1 (head)
```

命令只读取当前版本。应用安全检查显示其目标为本地默认数据库，包含既有国内数据；本阶段没有执行 upgrade、downgrade 或任何 DDL。

### 2.3 当前数据库状态

本次只读快照显示：

- `opinions`：1697 条
- `foreign_opinions`：1 条
- `foreign_keywords`：`中国`、`Chinese`、`China`
- `collector_runs`：
  - `domestic/failed`：66
  - `domestic/success`：11207
  - `foreign/success`：3
- `foreign scope` 运行中任务：0
- 外网数据源：
  - `foreign_fox_news`：`enabled=true`、`schedule_enabled=false`
  - `foreign_guardian`：`enabled=true`、`schedule_enabled=false`
  - `foreign_nyt_chinese`：`enabled=false`、`schedule_enabled=false`

当前唯一外网意见快照来自 The Guardian，命中关键词为 `China`。上述启用状态、运行日志和意见记录均为审计前既有数据库状态；本阶段没有修改它们。

这是与 Phase 1/1.1/2 报告中“所有外网源默认禁用、无外网意见残留”的重要偏差。由于本阶段禁止改库，不能在此处自行修复。该偏差必须在进入 3A Implementation 前由具备权限的运维/业务人员单独核实并按既定变更流程处理。

### 2.4 代理状态

以下变量均未配置：

- `HTTP_PROXY`
- `HTTPS_PROXY`
- `ALL_PROXY`
- `FOREIGN_HTTP_PROXY`
- `FOREIGN_HTTPS_PROXY`

本阶段未使用代理或境外采集节点。

## 3. 当前外网分析边界

当前真实链路是：

```text
ForeignRSSCollector
  -> ForeignCollectionService
  -> foreign_opinions
  -> /api/foreign/opinions
  -> /foreign?tab=opinions
```

`ForeignCollectionService`：

- 只读取 `foreign_keywords`
- 只筛选 `config_json.is_foreign=true` 的数据源
- 创建 `CollectorRun(scope="foreign")`
- 只创建 `ForeignOpinion`
- 通过 URL 和内容 hash 去重
- 不调用 `RiskEngine`
- 不调用 `AIService`、`DeepSeekProvider` 或外部 AI
- 不调用事件、告警、Dashboard、地图或热词服务

当前 `ForeignOpinion` 只有采集和展示字段，没有风险、情感、语言、置信度、模型版本或分析状态字段。当前 `/api/foreign/*` 也没有风险分析 API；`ForeignWorkspace.vue` 只有 opinions、keywords、sources、runs 四个区域，没有 risk tab。

结论：外网风险与情感分析尚未实施，当前没有“采集后自动分析”的隐式路径。

## 4. 国内 RiskEngine 审计

### 4.1 输入字段

`RiskEngine.refine(title, content, sentiment)` 的输入是：

- 标题字符串
- 正文字符串
- 已由 `RuleFallbackProvider` 或其他调用方生成的情感值

该类本身不访问数据库，不接收 `Opinion` ORM 对象，也不需要 `region_id`。但它的输出语义是为国内 `Opinion` 写回设计的：

- `severity_score`
- `event_state`
- `resolution_flag`
- `final_risk_score`
- `risk_factors`
- `risk_category`

采集服务随后将这些结果写入 `Opinion` 字段，并记录 `risk_model_version`。

### 4.2 国内评分公式

当前实现可概括为：

```text
text = title + "\n" + content
severity = min(sum(severity_weight for matched real-harm terms), 100)
state_factor = {
  occurred: 1.00,
  notice:   0.85,
  deploy:   0.70,
  prevent:  0.55,
  resolved: 0.35
}
severity_adj = min(severity * state_factor, 100)
positive_adjustment = min(0.25 * (100 - severity), 25) if sentiment == positive else 0
severity_floor = 70 if severity >= 70 else 50 if severity >= 50 else 0
final_risk_score = clamp(
  max(severity_adj - positive_adjustment, severity_floor, 20),
  0,
  100
)
```

国内风险等级的主要映射为：

- `risk_score >= 70`：high
- `40 <= risk_score < 70`：medium
- `< 40`：low
- `severity_score >= 70` 时，AlertService 可进一步派生 critical

Dashboard 的高风险累计口径也是 `risk_score >= 70`。这些阈值属于国内现行语义，外网不能未经评审直接沿用。

### 4.3 国内词表来源

风险和情感词来自多个国内实现层：

1. `RiskEngine.DEFAULT_SEVERITY_KEYWORDS`
   - 内置中文真实危害词和严重度权重
   - 由 `risk_terms.py` 中学校危害、执法危害等集合扩展
2. `risk_terms.py`
   - `ALL_HARM_KEYWORDS`
   - `matches_harm_keyword`
   - `is_actual_harm_hit`
   - 中文上下文和预防语境判断
3. `RuleFallbackProvider.DEFAULT_KEYWORDS`
   - 中文敏感词与权重
   - 无命中时默认风险分为 20
4. `NEGATIVE_SENTIMENT`
   - 中文事故、伤亡、冲突、腐败等词
5. `POSITIVE_SENTIMENT`
   - 中文解决、改善、进展、表扬等词
6. 运行时可注入的国内 `keywords`
   - 由国内关键词服务提供
   - 不是 `foreign_keywords`

外网关键词 `中国`、`Chinese`、`China` 只是采集命中词，不是风险词表，不能直接拿来充当外网风险规则。

### 4.4 RuleFallbackProvider 行为

`RuleFallbackProvider`：

- 构造参数为空或空列表时使用内置国内 `DEFAULT_KEYWORDS`
- 对文本做字面命中
- 计算：
  - `risk_score = min(20 + 10 * sum(hit weights), 100)`
  - 无命中时风险分 20
- 负面命中和正面命中分别统计
- 负面多于正面为 negative，正面多于负面为 positive，相等为 neutral
- 没有足够命中时返回 neutral
- 返回类型为 `AIAnalysisResult`
- 默认没有 `unknown` 情感值

对英文内容的实际风险是：英文事故、暴力、制裁、冲突、外交或政策语义通常不会命中中文词表，容易得到风险分 20 和 neutral。该行为不能作为外网安全默认值。

### 4.5 国内字段下游消费

国内风险字段被以下链路直接或间接消费：

- `AlertService`：读取 `Opinion.risk_score`、`severity_score`、`sentiment`、`risk_factors`、`keywords`
- `EventAggregator`：读取 `Opinion.risk_score`、`keywords`、`ai_keywords`、标题、正文、时间和 `region_id`
- `EventRiskService`：从关联 `Opinion.risk_score` 派生事件风险
- `DashboardService`：读取风险分、情感、风险类别、事件状态并统计
- 国内事件 API：返回事件风险等级和关联国内 Opinion
- 国内舆情 API/UI：返回 `Opinion` 风险字段
- Alert UI：展示国内 `AlertRecord`

因此，外网风险结果不能写入 `Opinion`，也不能只通过“加一个 foreign 标记”混入这些查询。

## 5. 国内 AI 审计

### 5.1 Service 和 Provider

当前 AI 结构为：

```text
AIService
  -> DeepSeekProvider when configured
  -> RuleFallbackProvider when not configured or provider fails
```

`AIService.analyze(title, content)` 会构造：

```text
标题：{title}
正文：{content}
```

然后优先调用 DeepSeek，否则调用中文规则 fallback。

`DeepSeekProvider`：

- 使用 OpenAI SDK 兼容调用
- 配置来自 settings：
  - API key
  - base URL
  - model
  - timeout
  - max retries
- 当前默认 timeout 为 30 秒
- 当前默认 max retries 为 2
- 使用结构化 JSON 返回
- 使用 Pydantic `AIAnalysisResult` 校验
- 会去除 Markdown code fence
- 未配置、网络失败、JSON 解析失败或 schema 校验失败时抛出异常

当前 AI prompt 明确要求中文摘要、中文建议和三分类情感，不能直接作为外网 prompt。

### 5.2 AI 是否绑定 Opinion

`backend/app/api/analysis.py` 的 `POST /api/analyze/{opinion_id}`：

1. 通过 `db.get(Opinion, opinion_id)` 获取国内 Opinion
2. 将 `Opinion.ai_analysis_status` 置为 processing
3. 直接实例化 `DeepSeekProvider`
4. 失败时将 `Opinion.ai_analysis_status` 置为 failed 并返回 500
5. 成功时写回：
   - `Opinion.ai_summary`
   - `Opinion.ai_sentiment`
   - `Opinion.ai_risk_score`
   - `Opinion.ai_keywords`
   - `Opinion.ai_analysis_suggestion`
   - `Opinion.ai_analysis_status`
   - `Opinion.ai_analysis_time`

该接口不是通用文本分析接口，不能接收 `foreign_opinion_id`，也不能用于外网结果。

### 5.3 国内分析的空值、超长和失败

当前国内代码没有为外网场景提供统一的：

- 空标题/空摘要/空正文策略
- 最大输入长度或 token budget
- 内容快照
- 分析结果版本幂等键
- 同文多版本分析
- 外部 AI 原始响应审计

采集服务的国内分析失败会保留 Opinion，并将分析状态标为 failed；手动 AI API 失败也保留状态。但当前 `Opinion` 只有一组 AI 结果字段，不能完整保留同一文章的多个模型版本。

## 6. 外网风险结果模型评审

### 6.1 `foreign_opinions` 当前字段是否足够

当前字段足够作为分析输入的原文来源：

- `title`
- `summary`
- `content`
- `url`
- `published_at`
- `collected_at`
- `matched_keywords`
- `content_hash`
- `source_key`
- `source_name_snapshot`

但不足以承载风险/情感结果，因为缺少：

- 分析状态
- 分析语言和语言置信度
- 风险分和等级
- 情感和情感置信度
- 风险类别
- 命中风险词
- 解释
- 分析器、模型和版本
- 分析时间
- 错误信息
- 结果是否当前版本

建议不修改 `foreign_opinions`，新增独立结果表。

### 6.2 推荐 `foreign_risk_results`

建议字段：

```text
foreign_risk_results
  id
  foreign_opinion_id FK foreign_opinions.id
  content_hash
  risk_score nullable
  risk_level
  sentiment
  sentiment_confidence nullable
  risk_category
  matched_terms JSONB
  explanation
  language
  language_confidence nullable
  analyzer_type
  model_name nullable
  model_version
  analysis_status
  error_message nullable
  analyzed_at nullable
  created_at
  updated_at
```

建议的约束与索引：

- `foreign_opinion_id` 必须有外键，删除文章时采用明确的级联或保留审计策略；
- `content_hash` 复制保存，表示分析时实际使用的文章版本；
- `analysis_status` 使用 `pending/processing/completed/failed/skipped`；
- `risk_level` 允许 `low/medium/high/unknown`；
- `sentiment` 允许 `positive/neutral/negative/unknown`；
- `foreign_opinion_id`、`analysis_status`、`analyzed_at`、`model_version` 建索引；
- 结果表不建立到 `opinions`、`events`、`event_opinions` 或 `alert_records` 的外键。

### 6.3 是否唯一 `foreign_opinion_id`

不建议单独对 `foreign_opinion_id` 做唯一约束。

原因：

- 规则模型和 AI 模型可能同时存在；
- 模型升级后需要重新分析；
- 同一文章可能有中文规则版、英文规则版和人工复核版；
- 失败记录需要保留，不能覆盖成功历史；
- 需要审计“哪一版结果曾经生效”。

推荐使用：

```text
UNIQUE(
  foreign_opinion_id,
  analyzer_type,
  model_name,
  model_version,
  content_hash
)
```

其中：

- `analyzer_type` 示例：`rule`、`ai`、`human_review`
- `model_name` 规则分析可以为 `foreign-rule-engine`
- `model_version` 负责版本升级
- `content_hash` 防止文章正文变化后错误复用旧结果

### 6.4 是否需要 `current_result`

建议保留历史分析行，并增加当前结果标识，而不是覆盖历史：

```text
is_current boolean
```

数据库层应使用“每篇文章最多一个当前结果”的部分唯一索引，或者独立的 `foreign_opinion_analysis_state` 指针表。推荐优先采用指针表，避免不同分析器并行写入时的竞争：

```text
foreign_opinion_analysis_state
  foreign_opinion_id PK/FK
  current_result_id FK foreign_risk_results.id
  current_model_version
  updated_at
```

如果首期不想新增该表，也可以使用 `is_current`，但必须在事务中先取消旧 current，再设置新 current。

### 6.5 是否保存原始模型输出

不建议把完整原始模型响应放在普通结果表中，原因是：

- 可能包含原文复述或敏感内容；
- 容易造成存储和版权扩散；
- 不利于权限隔离。

建议默认只保存结构化结果和 `explanation`。若业务需要可追溯原始响应，应新增受限的审计存储，至少：

- 只允许特权角色读取；
- 脱敏并限制长度；
- 与结果版本绑定；
- 记录保留期和删除策略；
- 不将原文或模型响应输出到普通外网意见列表。

## 7. 是否新增 `foreign_risk_terms`

建议新增，不使用 `keywords`、`foreign_keywords` 或国内 sensitive 词表承载风险词。

推荐字段：

```text
foreign_risk_terms
  id
  term
  language
  category
  weight
  severity
  is_enabled
  source
  version
  created_at
  updated_at
```

推荐约束：

```text
UNIQUE(term, language, version)
```

建议含义：

- `foreign_keywords`：采集入口关键词，只负责 OR 过滤
- `foreign_risk_terms`：分析词库，负责风险分类和严重度
- `keywords`：国内监测词，不得被外网分析读取

中英文词表应分开维护。混合文本允许两个语言词表同时命中，但每个命中项必须记录 language、category、weight 和上下文判定结果。词表版本必须进入 `model_version` 或单独的 `term_set_version`，保证可重算和回溯。

## 8. 风险分析方案比较

### 方案 A：独立规则引擎

优点：

- 可解释、可重复、成本和延迟可控；
- 不依赖外部 AI；
- 易于 fixture 测试；
- 适合先建立英文、中英混合的基础能力。

缺点：

- 需要维护中英文风险词库、否定词和语境规则；
- 对隐含语义、讽刺和复杂外交文本能力有限。

### 方案 B：独立 AI 分析

优点：

- 对中文、英文和混合文本覆盖较好；
- 可输出解释、主题和不确定性；
- 不需要大量手写词典。

缺点：

- 成本、延迟、超时、限流和供应商风险更高；
- 结果稳定性和可解释性需要评估；
- 需要处理原文外发、隐私、版权和敏感内容；
- 不能默认自动调用。

### 方案 C：规则优先，AI 可选复核

建议采用方案 C：

```text
foreign_opinions
  -> language detection
  -> independent rule analysis
  -> foreign_risk_results
  -> optional manual AI review
  -> new versioned foreign_risk_results
```

推荐原因：

- 先让系统具备稳定、低成本、可回归的基础结果；
- AI 只在人工触发或明确满足条件时执行；
- 规则结果和 AI 结果并存，不互相覆盖；
- 可在没有外部 AI 配置时正常展示；
- 不影响国内分析；
- 便于后续比较规则和 AI 结果差异。

## 9. 推荐分析契约

### 9.1 语言

建议至少支持：

- `zh`
- `en`
- `mixed`
- `unknown`

语言识别放在 `ForeignRiskService` 的输入归一化层，而不是写进国内 `AIService`。识别结果应保存 `language` 和 `language_confidence`。

建议：

- 中文网稿件默认走中文规则集，但仍进行检测；
- Fox News、Guardian 默认走英文规则集；
- 标题英文、摘要中文或正文混合时标记 `mixed`；
- 语言置信度不足时不强行归类。

### 9.2 风险

建议风险结果与情感结果解耦：

- 风险分描述潜在危害、升级性和涉华安全语义；
- 情感描述文本态度；
- sentiment 不自动降低 risk_score；
- 第一版不复用国内 `positive` 风险折减逻辑；
- 规则未命中不代表低风险。

默认值建议：

- 可识别且规则完成，但无风险命中：`risk_score=20` 或业务确认后的外网基线，`risk_level=low`，并标记 `matched_terms=[]`；
- 无法识别语言、内容为空或内容过短：`risk_score=NULL`，`risk_level=unknown`，`analysis_status=skipped` 或 `completed` 加明确原因；
- 分析失败：`risk_score=NULL`，`risk_level=unknown`，`analysis_status=failed`；
- 不允许用 `risk_score=0` 伪装成低风险，除非业务明确 0 的语义。

国内 20 分基线不应直接视为外网已批准的基线，需要业务确认。

### 9.3 情感

统一外网输出契约：

- `positive`
- `neutral`
- `negative`
- `unknown`

建议新增 `sentiment_confidence`。无法识别语言、文本太短、标题只有来源模板或规则冲突时返回 `unknown`，而不是强行 neutral。

规则和 AI 优先级建议：

1. 规则分析先生成可解释结果；
2. 人工触发 AI 时，AI 结果作为新的 analyzer/version；
3. AI 失败保留规则结果，不覆盖；
4. 人工复核可以产生 `human_review` 版本；
5. 当前结果指针由显式策略更新，不因 AI 请求成功自动覆盖生产展示结果。

### 9.4 空内容和超短内容

建议：

- 标题、摘要、正文合并前各自保留来源字段；
- 如果三者均为空：`skipped`；
- 如果有效文本低于业务设定的最小长度：`unknown/skipped`，并记录 `insufficient_content`；
- 优先使用 `content`，缺失时退回 `summary`，再退回 `title`；
- 不因为正文抓取失败而拒绝对 RSS 摘要做规则分析；
- 建立最大字符数和 token budget，超长时按标题、摘要、正文顺序截断，并保存输入 hash；
- 截断必须进入 explanation 或 audit metadata。

## 10. 外网风险 API 设计

本阶段只设计，不实现。所有接口保持 `/api/foreign/*` 命名空间。

### 10.1 只读接口

```text
GET /api/foreign/risk
GET /api/foreign/risk/{foreign_opinion_id}
GET /api/foreign/risk/summary
```

建议查询参数：

- `page`、`size`
- `source`
- `language`
- `risk_level`
- `sentiment`
- `analysis_status`
- `model_version`
- `date_from`、`date_to`
- `q`

默认只读权限：

- `foreign:risk:read`

查询必须只 join：

- `foreign_risk_results`
- `foreign_opinions`
- 必要时 `data_sources` 元数据

不能调用国内 Opinion 查询函数，也不能通过外键或 union 返回 `opinions`。

### 10.2 手动分析接口

```text
POST /api/foreign/risk/{foreign_opinion_id}/analyze
POST /api/foreign/risk/batch
```

建议权限：

- 规则分析：`foreign:risk:analyze`
- AI 分析：`foreign:risk:ai`
- 管理/批量操作：`foreign:risk:batch`

建议行为：

- 默认不自动调用 AI；
- 单条手动分析默认只运行规则分析；
- AI 必须显式传 `analyzer_type=ai` 或使用单独权限；
- batch 最大 50 条，后续按压测调整；
- batch 必须返回逐条状态，不因单条失败导致全部失败；
- 已有相同 `foreign_opinion_id + analyzer + model + content_hash` 的 completed 结果时幂等返回；
- processing 状态存在时拒绝重复任务或返回已有任务 ID；
- 不接收国内 `opinion_id`；
- 不允许客户端传入或覆盖 `region_id`、国内关键词或国内风险结果。

失败返回建议：

```json
{
  "foreign_opinion_id": 1,
  "analysis_status": "failed",
  "risk_level": "unknown",
  "error_code": "ANALYSIS_TIMEOUT",
  "error_message": "redacted message",
  "model_version": "..."
}
```

错误信息不得包含 API key、代理密码或完整外部连接串。

### 10.3 是否允许自动分析

3A 首期不允许自动 AI 分析。规则分析可以在明确的外网分析任务中自动运行，但必须：

- 使用独立 task/lock 命名空间；
- 不由国内 CollectorService 触发；
- 不在国内 scheduler 中注册；
- 可通过 feature flag 或配置开关整体关闭；
- 写入独立 `foreign_analysis_runs` 或等价审计记录；
- 不进入国内 `collector_runs` 的 domestic 统计。

## 11. 是否新增 `foreign_analysis_runs`

建议新增，不复用 `collector_runs` 作为分析运行表。

理由：

- `collector_runs` 语义是采集，字段围绕 RSS/来源抓取统计；
- 风险分析需要模型、版本、分析器、输入数量、成功/失败/跳过数量和成本；
- 手动 AI 分析和规则批处理不是采集任务；
- 复用同一表容易让 domestic collection log 混入分析任务，或使 scope 语义变得模糊。

建议字段：

```text
foreign_analysis_runs
  id
  run_key
  scope                  # fixed foreign
  trigger_type           # manual / batch / scheduled-rule-only
  analyzer_type
  model_name
  model_version
  input_count
  completed_count
  skipped_count
  failed_count
  started_at
  ended_at
  status
  proxy_used
  external_ai_used
  error_message
  created_at
```

该表只记录分析作业，不替代 `foreign_risk_results`，也不进入国内采集日志。

## 12. 前端设计评审

建议保留现有 `/foreign` 工作台，并增加：

```text
/foreign?tab=risk
```

风险区域展示：

- 风险等级
- 风险分
- 情感倾向
- 情感置信度
- 风险类别
- 命中风险词
- 分析状态
- 分析时间
- 分析器类型
- 模型名称和版本
- 内容 hash
- 原文详情入口
- 手动触发分析
- 失败提示和重试入口

前端行为约束：

1. `Opinions.vue` 国内页面不改查询、分页、详情和接口。
2. 国内风险页面不显示 `foreign_risk_results`。
3. 外网风险区域不显示国内 `Opinion` 或国内 Dashboard 数据。
4. 不调用 `/api/dashboard/*`。
5. 不在页面加载时自动调用 AI。
6. loading、empty、processing、failed、unknown 状态必须分开。
7. 手动 AI 按钮必须显示权限不足或未配置提示。
8. 规则分析和 AI 分析结果不能在同一个字段中静默覆盖。
9. 原文展示遵循现有外网版权和全文限制，不因分析增加全文暴露范围。
10. 本阶段不修改 Vue 文件。

## 13. 隔离与安全验证清单

3A Implementation 交付前必须逐项验证：

1. 分析输入唯一来自 `foreign_opinions`。
2. 任何外网分析查询都不读取 `opinions`。
3. 任何外网分析写入都不更新 `Opinion`。
4. 国内 `RiskEngine` 不被外网服务调用。
5. 若复用 `RiskEngine` 纯函数，必须显式传入外网词表和外网模型版本，禁止读取国内默认词表。
6. 外网分析结果不进入国内 `events`、`event_opinions`。
7. 外网分析结果不进入国内 `alert_rules`、`alert_records`。
8. 外网分析结果不进入国内 Dashboard、地图或热词。
9. 外网风险 API 只返回 `foreign_risk_results` 关联的外网意见。
10. API 不接受或解释国内 `opinion_id`。
11. 外网 AI 调用默认关闭。
12. 原文发送外部 AI 前必须有显式配置开关、权限、审计和数据脱敏策略。
13. 外网代理配置只从 `FOREIGN_*` 环境变量或安全配置读取，不影响国内 HTTP session。
14. 规则分析和 AI 分析均保存 `model_version`、`content_hash` 和状态。
15. 同文重复分析按版本幂等，不覆盖历史结果。
16. 分析失败保留失败记录，并保留原文展示能力。
17. batch 有最大数量、超时、限流和逐条错误隔离。
18. 所有分析操作可由审计日志追溯到用户、任务、模型和版本。
19. 当前 foreign source enabled 状态在实施前被单独核实。
20. 生产库不得通过本阶段报告或自动 migration 启用任何来源。

## 14. 推荐实现阶段

### Phase Foreign-Source-3A-Implementation

目标：

- 只实现独立规则风险与情感基础链路；
- 建立 `foreign_risk_results`；
- 建立 `ForeignRiskService`；
- 不自动调用外部 AI；
- 不连接事件、告警、Dashboard、地图或热词。

数据库变化：

- 新增 `foreign_risk_results`
- 推荐新增 `foreign_opinion_analysis_state`
- 若启用批处理审计，则新增 `foreign_analysis_runs`
- 新增 `foreign_risk_terms`

API 变化：

- `GET /api/foreign/risk`
- `GET /api/foreign/risk/{foreign_opinion_id}`
- `GET /api/foreign/risk/summary`
- `POST /api/foreign/risk/{foreign_opinion_id}/analyze`
- `POST /api/foreign/risk/batch`

服务变化：

- `ForeignRiskService`
- `ForeignRiskTermService`
- `ForeignLanguageService` 或等价语言检测组件
- 独立 repository/query functions

UI 变化：

- `/foreign?tab=risk`
- 只显示规则结果
- 不显示 AI 手动按钮，或显示明确的未启用状态

测试要求：

- 中文、英文、中英混合和未知语言；
- 风险词命中、非风险采集关键词命中、无命中；
- 空、短、超长内容；
- 标题/摘要/正文回退；
- 结果幂等；
- 同文不同版本；
- 分析失败保留；
- API 双向隔离；
- 国内 Risk/Opinion/Dashboard/Event/Alert 回归。

回滚方式：

- 停止外网规则任务；
- 隐藏风险 tab 和 API；
- 保留或按版本清理 `foreign_*` 结果；
- 不回滚、不更新、不删除国内表。

生产开启条件：

- 外网 source 状态已按变更流程复核；
- 3A migration 在临时数据库验证；
- 外网词表版本和风险阈值获业务确认；
- 外网权限和审计动作完成；
- 国内回归通过；
- 无 foreign scheduler 意外注册。

国内影响：

- 设计上应为零；
- 禁止修改国内 `RiskEngine`、AI prompt、Opinion schema、国内 API、国内 UI 或国内词表。

### Phase Foreign-Source-3A-AI

目标：

- 在规则结果稳定后，增加人工触发的独立 AI 复核；
- 保留规则结果，不覆盖；
- 建立 AI 成本、延迟、失败和审计统计。

数据库变化：

- 复用 `foreign_risk_results` 的多版本设计；
- 如需要，新增受限的 `foreign_ai_audit_records`；
- 不修改 `opinions` 或国内 AI 字段。

API 变化：

- `POST /api/foreign/risk/{foreign_opinion_id}/analyze` 增加显式 `analyzer_type=ai`
- 或新增 `POST /api/foreign/risk/{foreign_opinion_id}/ai-review`
- 新增模型版本筛选和结果比较接口，可选

服务变化：

- 独立 `ForeignAIService`
- 独立 prompt、输出 schema 和内容截断器
- 独立 timeout、retry、rate limit 和成本计量
- 外部服务适配器与配置开关

UI 变化：

- 外网风险页增加手动 AI 复核按钮；
- 显示权限、模型版本、分析状态、失败原因和当前结果来源；
- 页面加载不自动触发。

测试要求：

- mock AI，不访问真实外部服务；
- JSON fence、schema 错误、超时、限流、重试；
- AI 失败不覆盖规则结果；
- 同一文章同一版本幂等；
- 多版本并存和 current pointer；
- 原文外发开关关闭时绝不调用；
- API 权限和审计；
- 国内 AI 调用次数和 Opinion 字段回归不变。

回滚方式：

- 关闭外部 AI feature flag；
- 保留规则结果作为 current；
- 停止 AI 任务和手动入口；
- 不删除国内 AI 结果。

生产开启条件：

- 数据外发、版权、隐私和合规审批完成；
- AI provider、模型、成本上限、超时和限流确定；
- 手动权限和审计可追溯；
- 规则与 AI 差异有人工评估；
- 明确没有默认自动 AI 调用。

国内影响：

- 应为零；
- 外网 prompt、provider、结果表和 API 必须独立。

## 15. Go / No-Go

### 15.1 当前是否可以直接实施外网风险分析

**NO-GO。**

原因：

1. 当前应用默认数据库中 Fox News 和 The Guardian 已是 `enabled=true`，与“默认禁用”的验收基线不一致；
2. 当前数据库已有 1 条 `foreign_opinions` 和 3 条 foreign collection success 日志，说明外网链路曾经写入过数据；
3. 该状态未由本阶段修改，且本阶段禁止擅自修复；
4. 外网风险结果表、词表、分析任务表、API 和权限尚未实现；
5. 国内 Risk/AI 语义不能直接承载外网分析。

### 15.2 推荐规则还是 AI

**推荐方案 C：规则优先，AI 可选人工复核。**

先实现独立规则分析，再在明确的数据外发、费用和权限条件下加入人工 AI 复核。

### 15.3 是否允许自动风险分析

- 规则分析：未来可以在独立外网任务中受控自动运行，但不由国内采集器或国内 scheduler 触发。
- 外部 AI：3A 首期禁止自动调用；后续只允许显式 feature flag、权限和审计后人工触发。

### 15.4 是否允许手动 AI 分析

设计上可以允许，但必须等 3A-AI 条件满足后开放：

- `foreign:risk:ai` 权限；
- 内容外发开关；
- provider/model 配置；
- 超时、重试、限流和成本上限；
- 失败不影响规则结果；
- 审计记录完整。

### 15.5 是否需要 `foreign_risk_terms`

**需要。**

采集关键词与风险词语义不同，不能复用 `foreign_keywords`、国内 `keywords` 或国内 sensitive 词表。

### 15.6 是否需要 `foreign_analysis_runs`

**建议需要。**

风险分析不是采集，不能把分析运行混入 `collector_runs`。`collector_runs` 继续只记录 collection scope；`foreign_analysis_runs` 记录风险分析任务。

### 15.7 外网风险是否进入事件和告警

**当前不允许。**

未来必须等独立 `foreign_events`、`foreign_alerts` 和对应服务完成，并通过单独阶段的业务确认与隔离测试。

### 15.8 是否可以进入 3A Implementation

**暂不可以直接进入。**

进入前必须完成：

1. 由授权人员核实并处理当前两个外网源 `enabled=true` 的状态；
2. 确认现有 1 条 `foreign_opinions` 和 3 条 foreign logs 的来源、留存和测试/生产归属；
3. 确认风险分基线、等级阈值、`unknown` 语义和情感标签契约；
4. 确认中英文风险词库的负责人、版本和审核流程；
5. 确认是否允许正文/摘要发送给外部 AI；
6. 确认外部 AI provider、费用、超时、限流、审计和数据留存策略；
7. 在独立临时数据库完成 migration、规则分析和 API 隔离测试；
8. 验证国内 RiskEngine、AI、Opinion、Event、Alert、Dashboard 和热词回归；
9. 确认风险结果不会进入国内事件、告警或统计链路；
10. 获得新的实施授权。

## 16. 最终确认

- 未修改代码。
- 未修改配置。
- 未修改数据库结构。
- 未修改数据库数据。
- 未启用或停用外网源；但只读快照发现 Fox News、The Guardian 当前已为 `enabled=true`，这是实施阻断项。
- 未启用自动调度；当前三源均为 `schedule_enabled=false`，且无 running 外网任务。
- 未调用外部 AI。
- 未写入 `foreign_opinions`。
- 未写入 `opinions`。
- 未调用风险、事件、告警、Dashboard、地图或热词生产链路。
- 未使用代理或境外采集节点。
- 只新增了本设计评审报告。
