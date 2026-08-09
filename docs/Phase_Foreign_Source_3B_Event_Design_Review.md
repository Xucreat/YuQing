# Phase Foreign-Source-3B 外网事件聚合设计评审

评审日期：2026-08-08  
工作区：`C:\Users\Administrator\Desktop\YQ`  
阶段性质：只读审计与独立架构设计，不实施代码、迁移、配置或数据变更

## 1. 执行边界与结论

本阶段只允许读取代码、测试、数据库元数据和数据库现状，并新增本报告。没有运行采集器、调度器、事件聚合、风险分析、AI 或任何外网下游生产任务。

本次评审结论：

- **3B 设计评审：GO**。可以进入下一步独立外网事件链路实施设计。
- **3B 生产实现：CONDITIONAL GO**。必须先在独立测试库/预发布库完成 3A 迁移和回归，不能直接在当前默认业务库实施。
- **当前直接启用外网事件生产链路：NO-GO**。当前默认库仍为 `foreign_source_1`，生产库没有 3A 风险结果表；当前只有 1 条外网舆情样本，不能用于效果评估。
- 推荐采用“规则召回与候选生成 + 保守相似度确认 + 人工确认”的方案，不直接自动生成正式事件。
- 首期禁止中英文跨语言自动聚合；同语言跨来源聚合可以生成候选，但不能仅凭来源或“中国/China/Chinese”监测关键词合并。

## 2. 前置检查结果

### 2.1 工作区

`git status --short` 显示工作区已有大量已修改文件、未跟踪文件、备份目录和临时审计文件。本阶段没有撤销、覆盖、整理或删除其中任何内容。

本阶段唯一新增文件：

`docs/Phase_Foreign_Source_3B_Event_Design_Review.md`

### 2.2 数据库身份与迁移版本

执行 `alembic current` 的安全检查结果：

- 默认数据库：已被项目安全检查识别为本地业务数据库 `opinion_db`
- PostgreSQL 端口：本机业务端口
- 系统标识与预期业务库指纹匹配
- 当前 Alembic revision：`foreign_source_1`
- 当前不是 3A head

本阶段没有执行 upgrade、downgrade、DDL、DML 或任何事务写入。

### 2.3 当前只读数据快照

截至 2026-08-08，只读查询观察到：

| 对象 | 数量/状态 |
|---|---:|
| `opinions` | 1701 |
| `events` | 292 |
| `alert_records` | 37 |
| `foreign_keywords` | 3 |
| `foreign_opinions` | 1 |
| `collector_runs(scope=foreign)` | 3 |
| `collector_runs(scope=domestic)` | 11396 |
| `scope=foreign AND status=running` | 0 |

三个外网数据源当前均为：

- `enabled=false`
- `schedule_enabled=false`
- `class_path=app.collectors.foreign_rss.ForeignRSSCollector`

具体来源为 Fox News、The Guardian、纽约时报中文网。报告中的 1 条 `foreign_opinions` 和 3 条外网采集日志按既有人工灰度样本保留，不删除、不重置、不作为模型或聚合效果评估样本。

### 2.4 外部连接与代理

本阶段未使用代理、境外采集节点、真实 RSS 或外部 AI。当前审计未输出任何密码、Token、代理地址或完整连接串。

## 3. 当前系统真实实现

### 3.1 国内事件链路

当前国内链路实际为：

```text
domestic collectors
  -> CollectorService
  -> opinions
  -> domestic RiskEngine / AI fields
  -> EventAggregator
  -> events + event_opinions
  -> domestic event API/UI
  -> AlertRecord / propagation / Dashboard / map / hotwords
```

核心实现位于：

- `backend/app/models/event.py`
- `backend/app/models/event_opinion.py`
- `backend/app/services/event/aggregator.py`
- `backend/app/services/event/risk_service.py`
- `backend/app/services/event/heat_service.py`
- `backend/app/services/event/situation.py`
- `backend/app/services/event/narrative.py`
- `backend/app/services/propagation_service.py`
- `backend/app/services/alert_service.py`
- `backend/app/api/events.py`
- `backend/app/api/dashboard.py`

国内 `EventAggregator` 的真实输入是 `Opinion`，候选召回和合并判断直接使用：

- `Opinion.region_id`
- `Opinion.publish_time` / `created_at`
- `Opinion.title` / `content`
- `Opinion.keywords`
- `Opinion.ai_keywords`
- `Opinion.risk_score`

当前聚合为区域相同、时间接近、信号或文本相似度满足条件后进行合并。文本相似度使用截断文本的字符 2-gram 余弦式相似度，配置项包括：

- `event_text_similarity_threshold`
- `event_low_merge_text_threshold`
- `event_window_days`
- `event_continuation_days`

国内事件物化后会计算风险、热度、主题和时间范围，并通过 `EventOpinion` 关联国内 `opinions`。事件 API 进一步查询国内 `Opinion`、`Region`、`AlertRecord`、`EventAction` 和传播节点。

### 3.2 国内事件数据库关系

数据库只读元数据确认：

```text
events.region_id          -> regions.id
event_opinions.event_id   -> events.id
event_opinions.opinion_id -> opinions.id
alert_records.event_id    -> events.id
alert_records.opinion_id  -> opinions.id
propagation_nodes.event_id   -> events.id
propagation_nodes.opinion_id -> opinions.id
```

`event_opinions` 的唯一约束为 `(event_id, opinion_id)`。现有事件表没有 scope 字段，也没有外网外键边界。

因此，给 `events` 增加 `is_foreign` 标记不能替代独立外网事件表：现有 API、风险、告警、传播和 Dashboard 查询都会继续按国内模型解释关联数据，极易造成语义和统计污染。

### 3.3 外网基础链路

当前外网基础链路实际为：

```text
ForeignRSSCollector
  -> ForeignCollectionService
  -> foreign_opinions
  -> collector_runs(scope=foreign)
  -> /api/foreign/opinions
  -> /foreign?tab=opinions
```

3A 风险链路已经在测试库实现，但当前默认业务库尚未迁移到 3A：

```text
foreign_opinions
  -> ForeignRiskService
  -> foreign_risk_results
  -> foreign_analysis_runs
  -> /api/foreign/risk/*
  -> /foreign?tab=risk
```

当前生产数据库中没有 `foreign_risk_results`、`foreign_analysis_runs` 或任何 `foreign_*event*` 表。

外网基础模型的隔离特征：

- `ForeignOpinion` 不含 `region_id`
- `ForeignOpinion.source_id` 仅外键到 `data_sources`
- 外网风险表若部署，只关联 `foreign_opinions` 和外网分析运行
- 外网 API 查询 `ForeignOpinion`，不调用国内 `Opinion` 查询函数
- 外网采集不会调用国内 `RiskEngine`、`EventAggregator`、`AlertService`、Dashboard 或热词服务

## 4. 国内与外网事件模型对照

| 维度 | 国内事件 | 推荐外网事件 |
|---|---|---|
| 输入表 | `opinions` | `foreign_opinions` |
| 关联表 | `event_opinions` | `foreign_event_opinions` |
| 区域语义 | `region_id`、中国行政区划 | 不使用国内 `region_id`；媒体国家、涉事地点和来源地域分开建模 |
| 风险字段 | 国内 `Opinion.risk_score` 派生 | 仅消费 `foreign_risk_results`，结果独立 |
| 关键词 | 国内 `keywords` / `ai_keywords` | 监测词 `foreign_keywords` 与事件锚点分离 |
| 语言 | 主要按中文内容和中文主题分类 | `zh`、`en`、`mixed`、`unknown` |
| 事件表 | `events` | `foreign_events` |
| 候选 | 没有独立外网候选表 | 推荐 `foreign_event_candidates` |
| 运行日志 | 国内聚合无独立外网边界 | 推荐 `foreign_event_runs` |
| 告警/统计 | 国内 `AlertRecord`、Dashboard | 本阶段不接入；后续使用 `foreign_*` API 和表 |
| UI | `/events`、`/event/:id` | `/foreign?tab=events` |

## 5. 为什么不能复用国内 EventAggregator

直接复用会造成以下不可接受的耦合：

1. `EventAggregator` 的输入类型是 `Opinion`，不是 `ForeignOpinion`。
2. 合并硬条件使用 `region_id`，外网文章没有该字段，也不能伪造河北或全国归属。
3. 事件风险使用国内 `Opinion.risk_score`，会把外网结果写入或解释成国内风险语义。
4. `EventOpinion` 强制关联 `opinions.id`，无法关联 `foreign_opinions.id`。
5. 事件详情和列表 API 直接返回国内 Opinion，并反查国内告警。
6. 事件热度、传播树、主题和叙事服务均以国内 Opinion/Event 为输入。
7. 国内 Dashboard 直接统计 `opinions`、`events` 和 `AlertRecord`，无法安全接纳外网事件。

结论：可以复用底层字符串归一化、时间窗口、分页、权限、审计、任务锁和数据库基础设施；不得复用国内事件业务服务、国内事件模型、国内关联表或国内事件 API。

## 6. 推荐外网事件目标架构

```text
foreign_opinions
  -> ForeignEventCandidateService
  -> foreign_event_candidates
  -> manual review / conservative confirmation
  -> ForeignEventService
  -> foreign_events + foreign_event_opinions
  -> /api/foreign/events/*
  -> /foreign?tab=events
```

外网风险结果只作为事件候选的可选元数据：

```text
foreign_opinions
  -> ForeignRiskService
  -> foreign_risk_results
  -> ForeignEventCandidateService
```

事件聚合不得在采集流程内自动触发。未来即使允许外网规则聚合自动运行，也必须使用独立任务、独立运行日志和显式 feature flag。

## 7. 推荐数据库设计

本阶段不创建表。以下是后续实现阶段的推荐结构。

### 7.1 `foreign_event_candidates`

推荐新增。原因是候选不是正式业务事件，必须允许被拒绝、重算、合并或替换，而不能污染正式事件表。

建议字段：

- `id`
- `candidate_key`
- `title`
- `summary`
- `language`
- `candidate_status`：`candidate`、`rejected`、`converted`、`superseded`
- `confidence`
- `event_type`
- `risk_level_snapshot`
- `heat_score_snapshot`
- `first_seen_at`
- `last_seen_at`
- `opinion_count`
- `source_count`
- `aggregation_version`
- `evidence_json`
- `created_at`
- `updated_at`
- `reviewed_by`
- `reviewed_at`
- `rejection_reason`

`evidence_json` 用于保存候选生成时的可解释证据，例如标题相似度、内容相似度、实体/锚点交集、时间距离、语言判断、来源多样性和去重摘要。它不是模型原始输出存储。

### 7.2 `foreign_events`

正式事件表只在人工确认后创建或将候选转换为正式事件。建议字段至少包括：

- `id`
- `title`
- `summary`
- `language`
- `event_status`：`confirmed`、`monitoring`、`resolved`、`archived`
- `event_type`
- `risk_level`
- `heat_score`
- `first_seen_at`
- `last_seen_at`
- `opinion_count`
- `source_count`
- `confidence`
- `aggregation_version`
- `origin_candidate_id`
- `canonical_event_id`：合并/重定向时保留
- `created_at`
- `updated_at`
- `confirmed_by`
- `confirmed_at`
- `resolved_at`
- `archived_at`

不建议将国内 `region_id`、`topic_category` 直接复制到外网事件表。未来若要表达地域，应拆分为来源国家、媒体所在地、内容涉事地点和涉及国家/地区等不同字段，不能混成中国行政区划。

### 7.3 `foreign_event_opinions`

建议字段：

- `id`
- `foreign_event_id`，外键只指向 `foreign_events.id`
- `foreign_opinion_id`，外键只指向 `foreign_opinions.id`
- `relation_type`：`primary`、`secondary`、`duplicate`、`manual`
- `similarity_score`
- `matched_terms` JSON/JSONB
- `evidence_json` JSON/JSONB
- `created_at`
- `created_by`

建议唯一约束为 `(foreign_event_id, foreign_opinion_id)`，并增加 `foreign_opinion_id` 索引。

重复 URL 或相同 `content_hash` 的文章不应作为独立事件成员计数。应保留原始采集记录和去重关系，事件只关联规范化后的 canonical 文章；如需审计，可保存 `relation_type=duplicate`，但不计入 `opinion_count` 和 `source_count`。

### 7.4 `foreign_event_runs`

推荐新增，不复用 `collector_runs` 或 `foreign_analysis_runs`：

- `collector_runs` 是采集任务日志
- `foreign_analysis_runs` 是风险/情感分析日志
- 事件聚合需要记录算法版本、候选数、确认数、合并拆分数和失败位置

建议字段：

- `id`
- `scope`，固定为 `foreign`
- `trigger_type`：`manual`、`dry_run`、未来的 `scheduled`
- `aggregation_version`
- `input_count`
- `deduplicated_count`
- `candidate_count`
- `linked_count`
- `created_event_count`
- `updated_event_count`
- `rejected_count`
- `failed_count`
- `status`
- `started_at`
- `finished_at`
- `error_message`
- `created_by`
- `created_at`

### 7.5 `foreign_event_actions`

建议在实现人工确认、合并、拆分时新增。用于保存：

- 候选确认
- 候选拒绝
- 事件合并
- 事件拆分
- 状态变更
- 事件归档/重新激活
- 关联文章手动调整

动作记录必须保存操作人、旧状态、新状态、来源候选/事件、目标事件、原因和时间。

### 7.6 `foreign_event_narratives`

3B 首期不建议引入外部 AI 叙事表。事件标题和摘要可以先使用代表文章标题、模板和可解释统计生成。若后续需要多版本叙事，再单独设计 `foreign_event_narratives`，不得写回国内 `events.title/description`。

## 8. 候选生命周期、合并和拆分

### 8.1 候选状态

推荐候选状态：

```text
candidate -> converted
candidate -> rejected
candidate -> superseded
```

正式事件状态：

```text
confirmed -> monitoring -> resolved -> archived
                         \-> reopened -> monitoring
```

状态名称和 UI 标签应与国内事件页面区分，避免用户误解为国内事件。

### 8.2 权限建议

- 系统自动任务只能生成 `candidate`，不能确认正式事件。
- `foreign:events:read`：读取正式事件和候选。
- `foreign:events:candidates:read`：读取候选证据。
- `foreign:events:confirm`：候选转正式事件。
- `foreign:events:merge`：合并事件。
- `foreign:events:split`：拆分事件。
- `foreign:events:status`：变更状态、归档、重新激活。
- `foreign:events:rebuild`：触发受控重建，建议只授予管理员。

所有人工操作必须进入 `foreign_event_actions` 或等价审计日志，不能只改状态字段。

### 8.3 合并

合并仅允许人工确认或具备专门权限的受控任务执行。合并时：

1. 保留原事件/候选记录，不硬删除。
2. 选择一个 canonical 事件。
3. 其他事件标记为 `superseded` 或设置 `canonical_event_id`。
4. 关联文章在同一事务内去重迁移。
5. 保存合并前后的成员集合、理由和操作人。
6. 不改动国内 `events` 或 `event_opinions`。

### 8.4 拆分

拆分必须生成新的外网事件或候选，并保存：

- 原事件 ID
- 新事件 ID
- 被迁移的文章 ID
- 拆分理由
- 操作人和时间

不能通过删除旧事件成员而不留痕迹的方式实现拆分。

### 8.5 归档和重新激活

- 归档采用软状态，不删除事件或关联文章。
- 新文章命中已归档事件时，首期不得自动重新激活；生成新的候选并提示人工复核。
- 正式事件重新激活必须由 `foreign:events:status` 权限人工操作。
- 数据源删除后，历史事件仍依靠标题、摘要、快照字段和 `foreign_opinions` 关联展示。

## 9. 聚合策略比较

### 9.1 方案 A：纯规则/关键词聚合

输入包括时间窗口、共享关键词、标题相似度、正文相似度和来源交集。

优点：

- 可解释
- 不依赖外部模型
- 容易使用本地 fixture 测试
- 成本和延迟可控

缺点：

- `China`、`Chinese` 和 `中国`只是监测关键词，区分度很低
- 英文改写、同义表达和跨媒体改写容易漏聚或误聚
- 不能仅凭关键词判断同一现实事件

结论：可用于候选召回，不能直接生成正式事件。

### 9.2 方案 B：向量相似度聚合

按英文、中文或多语言模型生成标题/正文向量，再使用相似度阈值聚合。

风险：

- 需要新增模型、缓存、版本、资源和失败处理
- 跨语言相似度可能产生看似合理但不可审计的误聚
- 当前生产库没有足够标注样本支持阈值校准
- 会引入额外外部模型或本地模型运行依赖

结论：不适合 3B 首期直接作为唯一判据；可在 3B-Review 之后作为二次确认器评估。

### 9.3 方案 C：规则候选 + 相似度确认

推荐方案 C：

```text
foreign_opinions
  -> canonical URL/content dedupe
  -> language partition
  -> time-window candidate recall
  -> lexical/entity similarity scoring
  -> low-confidence candidate queue
  -> manual confirmation
  -> foreign_events
```

推荐原因：

- 先保证高精度和可解释性
- 通过候选表保留不确定结果，不污染正式事件
- 可以复用底层时间窗口、字符串归一化、分页和任务锁
- 后续可以把向量模型作为可插拔二次确认器，不改变表和 API 边界

## 10. 推荐聚合算法和首期阈值

以下为实现阶段的建议初始值，必须在有标注数据后校准；本阶段不写入配置。

### 10.1 预处理

1. 只读 `foreign_opinions`。
2. 通过 URL 和 `content_hash` 使用 canonical 文章。
3. 合并 `title + summary + content`，保留原始字段。
4. 语言分区为 `zh`、`en`、`mixed`、`unknown`。
5. 去除 URL、HTML、停用标点和重复空白。
6. 不把 `foreign_keywords` 作为事件主题；它们只用于采集筛选。

### 10.2 候选召回

建议首期：

- 同语言自动召回。
- 默认近事件窗口：72 小时。
- 事件延续窗口：最多 7 天，必须有新的时间接近且高相似证据。
- 自动候选至少包含 2 篇不同 canonical URL 的文章。
- 单篇文章默认不自动物化为候选；人工可创建单篇观察项。
- 同一来源文章可以形成候选，但单一来源候选 confidence 应降低。
- 至少两个不同来源会增加证据强度，但不能替代语义相似度。

### 10.3 配对评分

建议把各项得分保存到 `evidence_json`：

```text
pair_score =
    0.35 * title_similarity
  + 0.25 * content_similarity
  + 0.25 * anchor_overlap
  + 0.15 * time_proximity
```

其中：

- `title_similarity`：英文按词 n-gram，中文按字符 n-gram；大小写归一化。
- `content_similarity`：摘要优先，正文可用时加入截断正文。
- `anchor_overlap`：标题中的组织、人物、地点、数字、事件动作等稳定锚点交集；首期可用可解释的规则抽取，不能把监测关键词直接当实体。
- `time_proximity`：72 小时内线性衰减，超出窗口为 0。

建议初始判定：

- `pair_score >= 0.72` 且至少一个强锚点满足：进入高置信候选。
- `0.55 <= pair_score < 0.72`：进入低置信候选，必须人工确认。
- `< 0.55`：不建立候选关联。

这不是国内事件阈值，也不得直接复用国内 `event_text_similarity_threshold`。

### 10.4 集群和候选置信度

首期使用代表性星型聚类，要求新文章与候选代表文章直接满足判定条件，避免 A-B、B-C 推出 A-C 的链式误聚。

候选置信度建议：

```text
candidate_confidence =
  min(pair_score of accepted member links)
  + source_diversity_bonus
  - language_uncertainty_penalty
  - duplicate_penalty
```

结果限制在 `[0, 1]`。来源多样性只能作为小幅加分；相同来源、正文缺失、语言未知、风险结果失败都应降低置信度。

### 10.5 风险结果的使用

- `foreign_risk_results` 只提供风险等级快照和分析可用性。
- 风险结果不得作为唯一事件合并依据。
- 3A 风险分析失败的文章仍可进入候选召回，但候选必须标记 `risk_analysis_unavailable=true`，并限制自动置信度。
- 仅命中 `中国`、`Chinese` 或 `China` 不得提高事件合并分。
- 生产风险词表为空时，风险等级为 `unknown/low` 的文章仍可以依据内容相似度进入候选。

## 11. 多语言策略

首批来源包含两个英文源和一个中文源，必须把语言作为硬隔离条件之一。

### 11.1 英文文章

Fox News 与 The Guardian 的英文文章只在英文分区内自动召回和聚合。允许跨来源形成英文候选，但要求标题/内容/锚点相似度满足阈值。

### 11.2 中文文章

纽约时报中文网文章只在中文分区内自动召回和聚合。中文标题和摘要不强制翻译为英文，也不强制生成中文之外的事件标题。

### 11.3 中英混合文章

`mixed` 文章首期不自动加入纯中文或纯英文事件。它可以进入 mixed 候选队列，但默认标记为低置信度，必须人工确认。

### 11.4 未知语言

语言无法识别或正文过短时：

- 不自动跨语言聚合
- 可以保留文章展示
- 可进入低置信候选队列，但不得自动确认

### 11.5 翻译和多语言向量

3B 首期不引入自动翻译，也不把翻译结果写回原文或事件主标题。多语言向量和翻译辅助应作为后续可选确认器，必须保存模型/翻译版本和失败状态。

明确结论：

- 中文“ 中国 ”、英文 `China`、`Chinese` 只作为采集监测关键词，不作为事件主题。
- 中英文报道同一现实事件时，首期默认不自动合并。
- 需要跨语言合并时，必须由人工确认，并保存人工依据。

## 12. 单文章多事件、来源交叉和重复处理

### 12.1 一篇文章是否可属于多个事件

数据库关系采用多对多，允许人工复核后把一篇综合报道关联到多个正式事件。但自动候选阶段：

- 每篇 canonical 文章默认只进入一个主候选。
- 发现疑似多事件时标记 `ambiguous_multi_event=true`，进入人工队列。
- 只有人工拆分或人工添加 secondary 关系后，才允许多事件关联。

### 12.2 是否允许跨来源

允许同语言的 Fox News、The Guardian 和纽约时报中文网候选跨来源聚合，但：

- 来源交集不能单独触发合并。
- 至少一个内容/标题/实体锚点证据必须满足阈值。
- 跨来源只用于提高证据质量和 source_count。

### 12.3 同源重复和内容重复

- 相同 URL：只保留 canonical 文章参与事件计数。
- URL 不同但 `content_hash` 相同：只保留一个 canonical 文章计数，其他记录保留去重关系。
- 转载改写：仍按相似度判断，不因来源相同自动合并。

## 13. API 设计

本阶段只设计，不实现接口。

### 13.1 查询接口

```text
GET /api/foreign/events
GET /api/foreign/events/{event_id}
GET /api/foreign/events/{event_id}/opinions
GET /api/foreign/events/candidates
```

列表支持：

- `page`、`size`
- `status`
- `language`
- `source`
- `risk_level`
- `event_type`
- `first_seen_from`、`first_seen_to`
- `last_seen_from`、`last_seen_to`
- `min_confidence`
- `min_opinion_count`
- `q`

正式事件查询只能查询 `foreign_events`、`foreign_event_opinions`、`foreign_opinions`、`foreign_risk_results` 和必要的外网数据源元数据；不得 join `events`、`event_opinions`、`opinions` 或 `AlertRecord`。

### 13.2 人工操作接口

```text
POST /api/foreign/events/{event_id}/confirm
POST /api/foreign/events/{event_id}/reject
POST /api/foreign/events/{event_id}/merge
POST /api/foreign/events/{event_id}/split
POST /api/foreign/events/{event_id}/status
POST /api/foreign/events/rebuild
```

建议：

- `confirm` 只接收候选 ID、标题/摘要人工修订和理由。
- `merge` 必须接收源事件 ID、目标事件 ID、理由和幂等请求 ID。
- `split` 必须接收文章 ID 分组、理由和幂等请求 ID。
- `rebuild` 默认关闭，必须显式传 `dry_run=true` 或由管理员授权执行。
- 所有写接口返回 `foreign_event_actions` 审计 ID。
- 批量重建必须限制最大输入量，并通过 `foreign_event_runs` 追踪。

### 13.3 权限和错误处理

API 应复用现有认证机制，但使用独立 foreign event 权限。错误响应不得包含数据库连接信息、内部堆栈、代理信息或模型密钥。

## 14. 前端设计

保留现有 ForeignWorkspace，并新增：

```text
/foreign?tab=events
```

建议分成两个横向区域：

- 外网事件
- 事件候选

正式事件列表显示：

- 事件标题和摘要
- 状态
- 风险等级
- 热度
- 关联文章数
- 来源数
- 语言
- 置信度
- 首次出现时间
- 最近更新时间

候选列表额外显示：

- 生成方式和 `aggregation_version`
- 标题/内容/锚点/时间评分
- 风险分析可用性
- 同源/跨源信息
- 低置信度原因
- 确认、拒绝、合并、拆分入口

前端约束：

1. 国内 `Events.vue`、`EventDetail.vue` 不修改。
2. 外网事件页面只调用 `/api/foreign/events*`。
3. 不调用国内 `/api/events`、Dashboard、Alerts、地图或热词接口。
4. 候选必须有明确的 `candidate` 或“待人工确认”状态。
5. 处理 `loading`、`empty`、`failed`、`stale` 和重建进行中状态。
6. 事件标题保留原始语言，不强制翻译。
7. 人工操作按钮按 foreign event 权限显示。

## 15. 运行任务和并发边界

未来实现应建立独立的 `ForeignEventCandidateService` 和 `ForeignEventService`：

```text
ForeignEventCandidateService
  -> read foreign_opinions / foreign_risk_results
  -> write foreign_event_candidates / foreign_event_runs

ForeignEventService
  -> read candidates and foreign_opinions
  -> write foreign_events / foreign_event_opinions / foreign_event_actions
```

不允许：

- 在 `ForeignCollectionService` 内调用事件候选生成。
- 在国内 scheduler 中注册外网事件任务。
- 使用国内 `EventAggregator` 的咨询锁名称和业务入口直接处理外网数据。
- 把外网事件运行写入国内 `collector_runs` 的 domestic 统计。

可以复用底层数据库咨询锁和任务管理器，但锁键、任务名称、审计资源类型和统计指标必须能识别 `foreign_event`。

## 16. 隔离验收清单

3B 实现和验收必须逐项断言：

1. `foreign_event_opinions.foreign_opinion_id` 只指向 `foreign_opinions.id`。
2. `foreign_event_opinions` 不存在指向 `event_opinions` 的外键。
3. `foreign_events` 不存在指向 `events` 的外键。
4. 国内 `/api/events` 不返回 `foreign_events`。
5. 外网 `/api/foreign/events*` 不返回 `events`。
6. 外网事件服务不导入或调用国内 `EventAggregator`。
7. 外网事件服务不写入 `events`、`event_opinions`、`opinions` 或 `AlertRecord`。
8. 外网事件候选不触发国内 AlertService。
9. 外网事件统计不进入国内 Dashboard。
10. 外网事件不进入国内热词和地图统计。
11. 国内事件聚合结果和国内事件测试断言保持不变。
12. 外网事件运行只出现在 `foreign_event_runs` 或明确的 foreign scope 记录。
13. 同一 `aggregation_version` 和同一输入快照重复执行是幂等的。
14. 合并、拆分、确认、拒绝和状态变更均有人工审计记录。
15. 来源删除后，事件仍可通过快照和历史外网文章展示。
16. 外网源仍为 `enabled=false`、`schedule_enabled=false`，且没有运行任务。

## 17. 后续实施阶段

### Phase Foreign-Source-3B-Implementation

目标：

- 新增 `foreign_event_candidates`
- 新增 `foreign_events`
- 新增 `foreign_event_opinions`
- 新增 `foreign_event_runs`
- 新增 `foreign_event_actions`
- 实现 `ForeignEventCandidateService` 和 `ForeignEventService`
- 实现只生成候选、不自动确认的 API/UI

迁移：

- 新增式 Alembic migration，基于已确认的 3A head。
- 先在独立测试库验证 upgrade/downgrade。
- 不删除或修改国内表。

API/UI：

- `/api/foreign/events*`
- `/foreign?tab=events`

测试：

- 同语言跨来源候选
- 中英文禁止自动合并
- 低置信度进入候选
- 监测关键词不直接造成事件合并
- URL/content hash 重复处理
- 候选幂等和 aggregation version
- 人工确认、拒绝、合并、拆分审计
- 国内事件 API/服务回归
- 事件双向 API 隔离

回滚：

- 停止外网事件候选任务和入口。
- 在独立测试/预发布环境执行 downgrade。
- 生产回滚只允许按正式变更窗口执行，不能直接删除国内表或国内数据。

开启条件：

- 3A 迁移在预发布通过。
- 外网风险结果版本和 `unknown` 语义已确认。
- 外网事件候选表和外键审计通过。
- 国内事件回归通过。
- 三个外网源仍由人工控制，自动调度关闭。

对国内链路影响：设计上为零，不修改国内事件服务、表、API、UI 或测试断言。

### Phase Foreign-Source-3B-Review

目标：

- 人工确认候选。
- 验证合并、拆分、归档、重开和事件质量。
- 评估同语言跨来源聚合的精度。

不新增自动告警、不接入国内 Dashboard、不接入国内地图或热词。

验收重点：

- 候选到正式事件的状态机。
- 事件成员可追溯。
- 合并/拆分可回滚或通过反向动作恢复。
- 跨语言候选不会被自动确认。
- 事件热度仅在外网页面显示。

开启条件：

- 有足够的人工标注样本，而不是依赖当前 1 条生产样本。
- 业务方明确跨来源和跨语言政策。
- 操作权限、审计和重复告警前置边界完成评审。

### 后续外网告警前置条件

在 3B Review 通过之前，不得设计或启用外网告警。进入外网告警阶段前，必须有：

- 独立 `foreign_alert_rules`、`foreign_alerts` 和通知记录设计。
- 明确外网风险和事件是否允许触发告警。
- 告警去重、冷却、人工确认和通知失败策略。
- 确保国内 `AlertService` 不会读取外网表。

## 18. 已知风险与开放问题

1. 当前生产库只有 1 条外网舆情，不能评估事件聚合效果。
2. 当前默认库仍为 `foreign_source_1`，3A 风险结果表尚未部署。
3. 3A 生产风险词表和风险基线仍需业务确认，不能把风险等级当作可靠事件锚点。
4. 轻量语言识别对短标题、专名和混合内容存在误判风险。
5. 没有人工标注样本前，向量阈值、词法阈值和候选最小文章数都不能视为最终参数。
6. 同一篇综合报道是否允许关联多个正式事件，需要业务确认；本报告建议自动阶段单主候选、人工阶段允许 secondary 关系。
7. 是否允许英文媒体和中文网人工合并同一现实事件，需要业务确认；本报告首期禁止自动跨语言聚合。
8. 外网事件的“地域”尚未被定义为媒体所在地、来源国家、涉事地点或内容涉及国家/地区，不能复用中国行政区地图。
9. 外网事件叙事和翻译尚未设计数据留存、版权和外发边界，3B 首期不接入外部 AI。
10. 当前工作区存在用户既有源码修改和临时文件，实施阶段必须继续按文件级变更授权执行。

## 19. 当前不能直接实施的事项

当前不得直接执行：

- 在默认业务库创建 3B 表。
- 使用国内 `EventAggregator` 处理 `ForeignOpinion`。
- 把外网文章插入 `event_opinions`。
- 通过 `region_id=河北`、全国或其他国内地域表达外网事件。
- 自动确认外网正式事件。
- 自动跨中英文聚合。
- 启用外网事件自动调度。
- 把外网事件接入国内告警、Dashboard、地图或热词。
- 以当前 1 条外网舆情评估模型效果。

## 20. 最终 Go/No-Go

| 事项 | 结论 |
|---|---|
| 完成 3B 只读设计评审 | GO |
| 进入 3B 独立实现设计 | CONDITIONAL GO |
| 当前默认库直接迁移 3B | NO-GO |
| 直接复用国内 EventAggregator | NO-GO |
| 首期自动生成正式事件 | NO-GO |
| 首期生成外网事件候选 | GO，需独立服务和运行日志 |
| 同语言跨来源自动候选 | GO，需保守阈值和人工确认 |
| 中英文自动事件合并 | NO-GO |
| 人工确认、合并、拆分 | GO，需独立权限和审计 |
| 启用外网事件告警 | NO-GO，等待后续阶段 |
| 进入 3B Implementation | 需先满足 3A 预发布迁移、回归和业务确认条件 |

## 21. 本阶段最终确认

- 未修改 Python、TypeScript、Vue、SQL、Alembic 或配置文件。
- 未修改数据库结构或数据库数据。
- 未执行数据库 upgrade/downgrade。
- 未启用 Fox News、The Guardian 或纽约时报中文网。
- 未启用自动调度。
- 未触发真实采集、风险分析、事件聚合、告警、Dashboard、地图、热词或外部 AI。
- 未写入 `foreign_opinions`、`foreign_risk_results`、`opinions`、`events`、`event_opinions` 或国内告警表。
- 当前 1 条外网舆情和 3 条外网采集日志作为既有人工灰度样本保留。
- 3B 只读设计评审报告已完成；正式实现仍需独立测试库/预发布库和业务确认。
