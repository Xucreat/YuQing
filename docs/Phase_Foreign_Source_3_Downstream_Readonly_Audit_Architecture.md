# Phase Foreign-Source-3 Downstream Readonly Audit and Architecture

审计日期：2026-08-07  
审计范围：当前工作区 `C:\Users\Administrator\Desktop\YQ`  
审计性质：只读审计与独立架构设计  
实施状态：本阶段未修改业务代码、数据库结构、数据库数据或配置

## 1. 执行边界与证据

本阶段执行了以下只读检查：

- `git status --short`
- 阅读 Phase 0、Phase 1、Phase 1.1、Phase 2 报告
- 阅读当前外网模型、采集器、采集服务、API、路由、前端工作台和 `foreign_source_1` migration
- 阅读当前国内 Risk、AI、Event、Alert、Dashboard、Propagation、API、模型和前端组件
- 使用隔离测试数据库 `opinion_test`（localhost:5433）执行 SELECT 级数据库结构和状态检查
- 检查 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`FOREIGN_HTTP_PROXY`、`FOREIGN_HTTPS_PROXY`

代理环境变量均未配置。本阶段未连接代理、境外采集节点或真实外网来源。

当前工作区在审计开始前已经存在大量修改、未跟踪报告、临时文件和备份目录，包括外网链路相关源码修改。本阶段没有撤销、覆盖、整理或删除任何已有内容。新增文件仅为本报告。

一次未带测试数据库环境变量的 `alembic current` 读取命令解析到了应用默认数据库目标；该命令只读，没有执行升级、降级或写入。后续数据库证据以隔离测试数据库为准。

## 2. 当前实现真实摘要

### 2.1 国内链路

```text
domestic collectors
  -> CollectorService
  -> opinions
  -> RuleFallbackProvider / AIService / RiskEngine
  -> events + event_opinions
  -> AlertService + alert_records
  -> DashboardService / report / propagation / ChinaMap / domestic hotwords
  -> domestic API and domestic UI
```

关键事实：

1. `Opinion.region_id` 是非空外键，指向 `regions.id`，是国内采集、事件和 Dashboard 的基础假设。
2. `EventOpinion.opinion_id` 外键指向 `opinions.id`，不能关联 `foreign_opinions`。
3. `AlertRecord.opinion_id` 外键指向 `opinions.id`，`AlertService` 直接查询 `Opinion`、`AlertRule` 和国内 `keywords`。
4. `DashboardService` 的总量、风险量、趋势、来源、区域、热词、最近舆情和告警统计均查询国内表。
5. `ChinaMap.vue` 消费 `/api/dashboard` 的国内区域统计和本地中国行政区 GeoJSON，并通过 `region-children` 下钻。
6. 国内 `/api/opinions` 只查询 `Opinion`，详情、原文、编辑和删除也都是国内 Opinion 语义。
7. 国内 `/api/events`、`/api/alerts`、`/api/dashboard` 没有外网业务表的查询入口。

### 2.2 外网基础链路

```text
foreign data_sources (is_foreign=true, collector=foreign_rss)
  -> ForeignRSSCollector
  -> ForeignCollectionService
  -> foreign_opinions
  -> /api/foreign/*
  -> /foreign?tab=opinions|keywords|sources|runs
```

关键事实：

1. 外网采集器从 `foreign_keywords` 读取已启用关键词，不读取国内 `keywords`。
2. 外网采集器忽略国内 CollectorService 传入的国内关键词参数。
3. 外网数据只创建 `ForeignOpinion`，没有创建 `Opinion` 的调用路径。
4. 外网采集创建 `CollectorRun(scope="foreign")`，并记录 `proxy_used`。
5. 外网采集服务当前不调用 RiskEngine、EventAggregator、AlertService、Dashboard、地图或热词服务。
6. 正文抓取是可选增强；失败时保留 RSS 标题、摘要或 RSS 内容。
7. 三个默认外网数据源使用 `foreign_rss`，且在隔离测试数据库中均为 `enabled=false`、`schedule_enabled=false`。
8. `ForeignOpinion` 没有 `region_id`，也没有国内地域、国内采集模式或国内事件外键。

## 3. UI 入口现状

Phase 1.1 的入口对齐已经落地，当前不是复制国外 CRUD，而是跳转到现有 `/foreign` 工作台：

| 国内页面 | 入口 | 目标 |
|---|---|---|
| `Opinions.vue` | 国内舆情 / 国外舆情 | `/foreign?tab=opinions` |
| `Keywords.vue` | 国内关键词 / 外网关键词 | `/foreign?tab=keywords` |
| `Sources.vue` | 国内数据源 / 外网数据源 | `/foreign?tab=sources` |
| `AppLayout.vue` | 外网舆情、外网采集日志 | `/foreign`、`/foreign?tab=runs` |

`ForeignWorkspace.vue` 通过 `tab` 查询参数切换 opinions、keywords、sources、runs 区域，并继续调用：

- `/api/foreign/keywords`
- `/api/foreign/sources`
- `/api/foreign/opinions`
- `/api/foreign/collection-runs`
- `/api/foreign/collect`

国内页面默认仍调用国内接口。`CollectionLog.vue` 本身仍是国内采集日志页面；外网日志通过 `/foreign?tab=runs` 展示。这个现状符合“保留 `/foreign`、补齐入口、不复制查询逻辑”的要求。

## 4. 数据库只读审计

### 4.1 表结构与关系

| 对象 | 实际情况 | 隔离判断 |
|---|---|---|
| `foreign_keywords` | `id`、`word`、`category`、`is_enabled`、`created_at`、`updated_at`；`word` 有独立唯一约束和索引 | 与国内 `keywords` 物理隔离 |
| `foreign_opinions` | 来源、快照、标题、摘要、正文、URL、发布时间、采集时间、命中词 JSON、内容 hash、重复指针、创建时间 | 不依赖 `Opinion.region_id` |
| `foreign_opinions.source_id` | `data_sources.id`，`ON DELETE SET NULL` | 删除数据源后历史行仍可展示 |
| `foreign_opinions.url` | 非空字段，存在有效值唯一索引 | 支持 URL 去重 |
| `foreign_opinions.content_hash` | 普通索引 | 支持内容去重 |
| `foreign_opinions.duplicate_of_id` | 当前无自引用外键、无专用索引 | 可记录重复来源，但后续应补约束/索引设计 |
| `collector_runs.scope` | 非空，默认 `domestic`，有索引 | 国内/外网运行日志可按 scope 隔离 |
| `collector_runs.proxy_used` | 非空 Boolean，默认 `false` | 可记录是否实际使用代理 |
| `opinions` | `region_id` 非空外键到 `regions` | 国内专用 |
| `event_opinions` | `event_id -> events.id`、`opinion_id -> opinions.id` | 无法关联外网 |
| `alert_records` | `opinion_id -> opinions.id`、`event_id -> events.id` | 无法关联外网 |

未发现引用 `foreign_opinions` 的视图，也未发现外网表到 `opinions`、`events`、`event_opinions` 或 `alert_records` 的外键。

### 4.2 测试数据库状态

隔离测试数据库的只读快照：

- `opinions`：4 行
- `foreign_opinions`：0 行
- `foreign_keywords`：3 行，内容为 `中国`、`Chinese`、`China`
- 国内 `keywords`：44 行
- `collector_runs`：国内 8 行，外网 0 行
- 外网运行中的任务：0 行
- 三个外网数据源：`enabled=false`、`schedule_enabled=false`
- 三个外网源均带 `is_foreign=true`，采集类路径包含 `foreign_rss`

本阶段没有向上述数据库写入数据。

### 4.3 Migration

`backend/alembic/versions/foreign_source_1.py` 的实际作用：

- 在 `collector_runs` 新增 `scope`、`proxy_used`
- 新建 `foreign_keywords`
- 新建 `foreign_opinions`
- 插入三条外网关键词
- 插入三个默认禁用、默认不调度的外网 RSS 数据源
- 不修改历史国内表数据

隔离测试数据库显示 `foreign_source_1` 为当前 head，外网表和新增列均存在。未来若继续迁移，应保持新增式策略，不在生产库执行 downgrade。

## 5. 国内下游调用关系审计

### 5.1 风险与情感分析

国内采集和分析使用两类实现：

1. `RuleFallbackProvider`：
   - 使用内置中文风险/敏感/情感词集合；
   - 允许外部注入关键词，但默认不是从 `foreign_keywords` 读取；
   - 生成 `sentiment`、`risk_score`、命中关键词等国内 Opinion 字段。
2. `RiskEngine`：
   - 使用 `severity_keywords`、`ALL_HARM_KEYWORDS`、中文事件状态词；
   - 计算 severity、event state、resolution flag、risk category 和最终风险分；
   - 结果当前写回 `Opinion.risk_score`、`severity_score`、`event_state`、`risk_factors`、`risk_model_version`、`risk_category`。

结论：

- 当前模型没有明确的英文词表、跨语言分词、语言检测或中英文混合归一化流程。
- 英文内容若没有命中中文规则，通常会落到 neutral 和基础风险分；这不是英文内容安全，而是规则覆盖不足。
- `RiskEngine` 的字符串计算部分是纯函数，理论上可以复用为底层算法原语；不能直接复用其服务边界、数据库写回或国内词表。
- `backend/app/api/analysis.py` 直接 `db.get(Opinion, opinion_id)`，调用 AI 后写回 `Opinion.ai_*`，不能用于 `ForeignOpinion`。
- 现有 AI prompt 和输出契约围绕国内 `Opinion` 字段设计；没有 `region_id` 本身不会影响一个纯文本函数，但直接接入现有 API 会因模型和写回目标不匹配而失败。

推荐：

- 新建 `ForeignRiskService` 和 `foreign_risk_results`。
- 可复用 `RiskEngine` 的无副作用打分原语，但必须注入独立的中英文规则集和独立模型版本。
- 需要语言识别或显式 `language` 字段；英文、中文、混合文本使用不同规则策略。
- 需要独立 AI prompt，至少明确原文语言、来源、摘要/正文边界和不确定性。
- 外网分析结果不得写回 `Opinion` 或 `ForeignOpinion` 的国内风险字段。

建议表：

```text
foreign_risk_results
  id
  foreign_opinion_id FK foreign_opinions.id
  risk_score
  risk_level
  sentiment
  risk_category
  matched_terms JSONB
  language
  model_version
  analysis_status
  analyzed_at
  error_message
  created_at
  updated_at
```

至少应有 `foreign_opinion_id + model_version` 唯一约束或等价幂等键，并为 `analysis_status`、`analyzed_at` 建索引。

### 5.2 事件聚合

国内事件聚合的输入和关系是：

```text
opinions (analysis_status=completed)
  -> EventAggregator
  -> events
  -> event_opinions
  -> propagation / event detail / alerts / dashboard
```

实际规则：

- 事件候选取时间窗口内的 `Opinion`；
- `_merge_condition` 强制要求相同 `Opinion.region_id` 和时间接近；
- 使用标题加正文的字符 n-gram 相似度；
- 使用 `Opinion.keywords`、`ai_keywords` 和内置中文通用词；
- 事件风险、主题、热度和标题从国内 Opinion 计算；
- 自动聚合可在采集后触发，并可能进一步重建传播链；
- 事件 API 详情还会反查国内 Opinion 和 `AlertRecord`。

这些规则不适合直接用于外网：

- `foreign_opinions` 没有 `region_id`；
- 字符 n-gram 对英文形态变化、跨语言同义表达和中文网稿件的表现不可直接假定；
- 主题词、风险词和事件状态存在中文语义假设；
- 标题格式没有强制翻译，但叙事 fallback 含中文固定文案，不能作为外网统一标题策略；
- 国内事件和告警存在连锁关系，直接复用会破坏隔离。

推荐：

- 新建 `ForeignEventService`，第一期只生成“事件候选”，不自动合并为正式事件。
- 新建 `foreign_events` 和 `foreign_event_opinions`，外键只指向 `foreign_opinions` 和 `foreign_events`。
- 首期禁止中文网与英文稿件自动跨语言聚合；跨 Fox、Guardian、纽约时报中文网的同语言候选可在后续人工确认机制下评估。
- 事件正式形成前需要人工确认或明确的运营审批；候选状态不应进入国内事件 API。
- 外网事件统计、传播分析和后续告警只能查询 `foreign_*` 表。

建议表：

```text
foreign_events
  id
  title
  title_original_language
  summary
  language_set JSONB
  topic_category
  heat_score
  trend
  status                # candidate / confirmed / rejected / closed
  first_time
  last_time
  source_count
  opinion_count
  created_at
  updated_at

foreign_event_opinions
  id
  foreign_event_id FK foreign_events.id
  foreign_opinion_id FK foreign_opinions.id
  similarity_score
  match_reason JSONB
  created_at
  UNIQUE(foreign_event_id, foreign_opinion_id)
```

### 5.3 告警

当前告警实现：

- 规则存储在 `alert_rules`；
- `AlertService.evaluate()` 查询启用的 `AlertRule` 和 `Opinion`；
- 规则可按风险阈值、关键词、来源、风险级别筛选；
- 未显式配置关键词时，复用国内 `keywords`；
- 结果写入 `alert_records`，并可通过 `EventOpinion` 反链到国内事件；
- `/api/alerts/*` 没有 foreign scope 参数；
- 当前代码没有发现真正的通用外发通知发送器；主要是告警记录、查询和人工处置。

因此，外网数据如果进入 `opinions` 或公共告警表，会有误触发风险。外网告警不能直接复用国内告警查询或 `AlertService.evaluate()`。

推荐独立对象：

```text
foreign_alert_rules
  id
  name
  rule_type              # keyword / risk_threshold / event_heat / source_health
  rule_config JSONB
  enabled                # default false
  require_manual_confirm # default true
  cooldown_seconds
  created_at
  updated_at

foreign_alerts
  id
  rule_id FK foreign_alert_rules.id
  foreign_opinion_id FK foreign_opinions.id nullable
  foreign_event_id FK foreign_events.id nullable
  source_key
  risk_level
  trigger_reason JSONB
  dedupe_key
  status
  created_at
  handled_at

foreign_notification_records
  id
  foreign_alert_id FK foreign_alerts.id
  channel
  delivery_status
  provider_message_id
  sent_at
  error_message
```

首期建议只支持关键词命中和来源异常；风险阈值需等 3A 的结果稳定后再开启，事件热度需等 3B 人工确认后再开启。外网告警默认关闭，通知默认需要人工确认，采用 `dedupe_key + cooldown + per-source rate limit` 防止重复告警和告警风暴。若复用通知发送器，必须通过显式 `scope="foreign"` 和独立模板调用，不能复用国内告警查询。

## 6. Dashboard、热词和地图审计

### 6.1 Dashboard

`DashboardService` 直接读取：

- `opinions` 总量、时间趋势、情感、来源和风险；
- `events` 事件数量；
- `alert_records` 告警统计；
- `regions` 和 `Opinion.region_id` 区域统计；
- 国内 `keywords` 的真实提及频次；
- `Opinion.keywords`、`risk_category`、`event_state` 等国内派生字段。

当前接口包括 `/api/dashboard/stats`、`/recent`、`/alerts`、`/hot-keywords`、`/alert-stats`、`/region-children`。这些接口应继续保持国内语义，不应增加“把 foreign_opinions 合并统计”的隐式分支。

推荐新增：

- `GET /api/foreign/dashboard/summary`
- `GET /api/foreign/dashboard/trends`
- `GET /api/foreign/dashboard/sources`
- `GET /api/foreign/dashboard/risks`（3A 后）
- `GET /api/foreign/hotwords`

外网 Dashboard 只能查询 `foreign_opinions` 和未来 `foreign_*` 表，不能加入国内 Dashboard 的总数、趋势、风险、事件或告警总数。

### 6.2 热词

国内热词由 Dashboard 服务基于国内 `keywords` 和 `Opinion.title/content` 统计。它不是 `foreign_opinions.matched_keywords` 的直接替代。

外网热词建议分两层：

1. 3D 首期只做原文词频、来源分布、时间趋势和可解释的停用词过滤。
2. 中文翻译归一化、词形还原、实体归并和跨语言主题词在有语言模型与人工评估后再做。

首期 `中国`、`Chinese`、`China` 只作为外网筛选/采集关键词，不作为热词归一化规则。英文大小写可以统一，单复数和词形变化应使用可配置 tokenizer/lemmatizer，并保留原词以便审计。外网热词不能写入国内 `keywords`，也不能进入国内 Dashboard 的 `hot_keywords`。

可以先采用按请求实时计算或短时缓存，规模稳定后再考虑：

```text
foreign_hotword_stats
  id
  bucket_start
  token
  normalized_token
  language
  source_key
  count
  created_at
  UNIQUE(bucket_start, normalized_token, language, source_key)
```

### 6.3 地图与地域视图

当前地图是中国行政区地图：

- 数据来自 Dashboard 的 `regions` / `region_detail`；
- 查询依赖 `Opinion.region_id` 和 `regions`；
- 前端加载中国省级 GeoJSON，并按省名请求市县下钻。

外网内容没有国内 `region_id`，不能被标为河北、全国或任意中国行政区。外网“地域”还需要先定义是：

- 新闻来源国家；
- 媒体所在地；
- 舆论发生地；
- 内容涉及国家/地区。

这些语义不能混为一个字段。建议：

- Phase 3E 前暂缓地图；
- 首选“来源分布”或“媒体分布”视图，而不是复用中国行政区地图；
- 后续若需要内容涉及地域，单独建立抽取结果和置信度，不写入 `regions` 或 `Opinion.region_id`。

## 7. 国内/国外对照表

| 层次 | 国内 | 外网当前 | 外网目标 |
|---|---|---|---|
| 采集 | 国内 CollectorService/专用采集器 | ForeignRSSCollector | 保持独立 ForeignCollector |
| 关键词 | `keywords` | `foreign_keywords` | 独立外网词表、语言字段 |
| 原始意见 | `opinions` | `foreign_opinions` | 保持物理隔离 |
| 风险 | Opinion 风险字段、RiskEngine | 尚未接入 | `ForeignRiskService` + `foreign_risk_results` |
| 事件 | `events` + `event_opinions` | 尚未接入 | `foreign_events` + `foreign_event_opinions` |
| 告警 | `alert_rules` + `alert_records` | 尚未接入 | `foreign_alert_rules` + `foreign_alerts` |
| 日志 | `collector_runs(scope=domestic)` | `collector_runs(scope=foreign)` | 统一表、强制 scope |
| Dashboard | `/api/dashboard/*`，国内表 | `/api/foreign/*` 工作台，无下游统计 | `/api/foreign/dashboard/*` |
| 热词 | 国内 Dashboard/keywords | 尚未接入 | `/api/foreign/hotwords` |
| 地图 | 中国行政区、`regions` | 不适用 | 来源/媒体/议题分布，独立视图 |
| UI | 国内舆情、关键词、数据源、日志页 | `/foreign?tab=...` | 独立外网工作台和下游页面 |

## 8. 推荐目标架构

```text
domestic collectors
  -> opinions
  -> domestic risk
  -> domestic events
  -> domestic alerts / dashboard / map / hotwords

foreign collectors
  -> foreign_opinions
  -> ForeignRiskService
  -> foreign_risk_results
  -> ForeignEventService
  -> foreign_events / foreign_event_opinions
  -> ForeignAlertService
  -> foreign_alerts / foreign_notification_records
  -> foreign dashboard / foreign hotwords / foreign source distribution
```

### 8.1 服务边界

- `ForeignCollectionService`：只负责外网抓取、关键词匹配、去重、`ForeignOpinion` 和 foreign scope 日志。
- `ForeignRiskService`：只消费 `ForeignOpinion`，写 `foreign_risk_results`。
- `ForeignEventService`：只消费外网意见和外网风险结果，先生成候选，人工确认后形成外网事件。
- `ForeignAlertService`：只消费外网结果，写外网告警和通知记录。
- `ForeignDashboardService`：只查询外网业务表和外网统计结果。
- `ForeignHotwordService`：只消费外网意见，保留原文词与归一化词的双轨结果。
- `ForeignSourceDistributionService`：只消费来源元数据和明确的外网地域抽取结果。

### 8.2 可复用基础设施

允许复用：

- HTTP/RSS/XML 解析基础设施；
- 代理配置读取机制，但仅使用外网专用环境变量；
- 任务执行、权限校验、审计日志和 `collector_runs`；
- 通知传输底层，但调用时必须显式传入 foreign scope；
- 通用分页、错误处理和前端布局组件。

不允许复用：

- `Opinion` 作为外网业务表；
- `Opinion.region_id` 作为外网归属；
- 国内 `keywords` 作为外网词表；
- 国内 `RiskEngine` 的默认中文词库；
- 国内 `EventAggregator`、`AlertService`、`DashboardService` 的查询入口；
- 中国行政区地图作为外网地域表达。

### 8.3 权限、任务、日志和指标

建议新增权限前缀：

- `foreign:keywords:read/write`
- `foreign:sources:read/write`
- `foreign:opinions:read`
- `foreign:collect:execute`
- `foreign:risk:read/write`
- `foreign:events:read/write`
- `foreign:alerts:read/write`
- `foreign:dashboard:read`

外网任务应使用独立任务名和队列/锁命名空间，例如 `foreign-collector`、`foreign-risk`，不得进入国内采集任务列表。公共 `collector_runs` 必须强制写入 scope，所有外网查询显式 `scope="foreign"`，所有国内默认查询显式 `scope="domestic"`。

指标至少按 `scope`、`source_key`、`collector_name` 维度分开：

- 请求成功率、RSS 解析失败率；
- 条目数、命中数、新增数、URL/content hash 去重数；
- 风险分析成功率；
- 事件候选数和人工确认数；
- 告警创建数、通知发送数和抑制数。

## 9. 未来数据库设计建议

保留当前基础表：

- `data_sources`：复用，外网源使用 `config_json.is_foreign=true`；
- `collector_runs`：复用，强制 `scope`；
- `foreign_keywords`、`foreign_opinions`：继续独立。

建议新增：

1. `foreign_risk_results`
2. `foreign_events`
3. `foreign_event_opinions`
4. `foreign_alert_rules`
5. `foreign_alerts`
6. `foreign_notification_records`
7. 可选 `foreign_hotword_stats`
8. 可选 `foreign_geo_mentions` 或 `foreign_source_locations`

所有外网表都应满足：

- 外键只指向 `foreign_*` 表或明确的公共元数据表；
- 不向国内 `opinions`、`events`、`alert_records` 写外网关系；
- 有唯一/幂等键；
- 有保留期、状态和错误字段；
- 删除源后通过 snapshot 字段保留历史展示能力。

## 10. 推荐 API 设计

### 风险分析

- `GET /api/foreign/risk-results`
- `GET /api/foreign/opinions/{id}/risk`
- `POST /api/foreign/opinions/{id}/analyze`

`POST` 只能写 `foreign_risk_results`，不能返回或更新 `Opinion`。

### 事件

- `GET /api/foreign/events/candidates`
- `POST /api/foreign/events/candidates/{id}/confirm`
- `POST /api/foreign/events/candidates/{id}/reject`
- `GET /api/foreign/events`
- `GET /api/foreign/events/{id}`

首期禁止把候选事件接入国内 `/api/events`。

### 告警

- `GET/POST/PATCH /api/foreign/alerts/rules`
- `POST /api/foreign/alerts/evaluate`
- `GET /api/foreign/alerts`
- `POST /api/foreign/alerts/{id}/ack`
- `GET /api/foreign/notifications`

所有规则和记录只能查询外网表，默认关闭。

### Dashboard、热词、来源分布

- `GET /api/foreign/dashboard/summary`
- `GET /api/foreign/dashboard/trends`
- `GET /api/foreign/dashboard/sources`
- `GET /api/foreign/hotwords`
- `GET /api/foreign/source-distribution`

查询函数应使用独立 repository/service，不在国内查询函数上增加隐式表切换。

## 11. 数据隔离验证清单

实施后每次发布必须验证：

- 国内 registry 排除 `config_json.is_foreign=true`；
- 国内 registry 排除 class path 含 `foreign_rss`，即使配置错误地写成 `is_foreign=false`；
- 国内 scheduler 不触发外网源；
- 外网采集只写 `foreign_opinions`；
- 外网采集不创建 `Opinion`；
- 外网采集不调用 RiskEngine、Event、Alert、Dashboard、地图、热词生产服务；
- 国内 `/api/opinions` 不返回外网行；
- 外网 `/api/foreign/opinions` 不返回国内行；
- 国内日志默认 `scope=domestic`；
- 外网日志只返回 `scope=foreign`；
- 国内 `keywords` 和 `foreign_keywords` 读写路径完全分离；
- 外网代理配置不进入国内 HTTP session；
- 外网事件、风险、告警和统计表没有国内外键；
- 国内 Dashboard、地图、热词、事件、告警回归测试结果不变；
- 生产三个外网源仍为禁用且不调度；
- 无外网任务处于 running。

当前只读证据已经确认：外网基础链路的表、API 和 collector registry 排除逻辑存在，隔离测试数据库中没有外网意见残留，三个源保持禁用；但下游 scope 设计尚未实施，不能将未来表或 API 视为已存在。

## 12. 后续实施阶段

### Phase Foreign-Source-3A：外网风险与情感分析

- 目标：建立英文、中文和混合文本的可解释风险/情感结果。
- 新增表：`foreign_risk_results`，必要时 `foreign_analysis_runs`。
- API：`/api/foreign/risk-results`、外网单条分析 API。
- 服务：`ForeignRiskService`、语言识别和规则词表 provider。
- 前端：外网详情页风险和情感只读区域。
- 公共基础设施：复用纯文本算法、AI provider、权限、审计和任务框架；不复用国内写回。
- 迁移：需要新增式 migration。
- 国内影响：应为零；国内 RiskEngine、Opinion 字段和 API 不变。
- 测试：中英文、混合文本、无命中、失败重试、幂等、国内回归。
- 回滚：停用外网分析任务/API，保留或按版本清理外网结果；不回滚国内表。
- 开启条件：规则词表、英文模型能力、阈值和人工复核方案获确认。

### Phase Foreign-Source-3B：外网事件候选与人工确认

- 目标：生成可解释候选，不自动形成跨语言正式事件。
- 新增表：`foreign_events`、`foreign_event_opinions`。
- API：候选列表、确认、驳回、详情。
- 服务：`ForeignEventService`、同语言相似度和候选解释器。
- 前端：外网工作台事件区域或独立外网事件页。
- 公共基础设施：复用分页、权限、审计和锁；不复用 `EventAggregator` 写入国内表。
- 迁移：需要新增式 migration。
- 国内影响：应为零。
- 测试：跨来源同语言、重复候选、人工确认、中文/英文隔离、国内事件回归。
- 回滚：停用候选任务，保留审计记录；不删除国内事件。
- 开启条件：3A 结果可用，业务确认事件定义、时间窗口和跨来源规则。

### Phase Foreign-Source-3C：外网告警规则与告警记录

- 目标：在默认关闭和人工确认前提下建立外网告警。
- 新增表：`foreign_alert_rules`、`foreign_alerts`、`foreign_notification_records`。
- API：规则 CRUD、评估、告警列表、确认/处置和通知记录。
- 服务：`ForeignAlertService`、去重/冷却器、通知 adapter。
- 前端：外网告警区域，不能复用国内告警列表数据。
- 公共基础设施：可复用通知发送器、权限、审计和任务调度，但显式传递 foreign scope。
- 迁移：需要新增式 migration。
- 国内影响：应为零。
- 测试：关键词、风险阈值、来源异常、冷却、幂等、发送失败、国内告警回归。
- 回滚：关闭外网规则和通知，停止评估任务；不改国内 alert 表。
- 开启条件：3A/3B 稳定，阈值、通知渠道、值班人和人工确认流程获批准。

### Phase Foreign-Source-3D：外网 Dashboard 与热词

- 目标：提供外网趋势、来源、风险摘要和原文热词。
- 新增表：可选 `foreign_hotword_stats`、统计运行表。
- API：`/api/foreign/dashboard/*`、`/api/foreign/hotwords`。
- 服务：`ForeignDashboardService`、`ForeignHotwordService`。
- 前端：`/foreign` 增加独立 dashboard/hotwords 区域。
- 公共基础设施：复用图表组件、分页、缓存和权限；不复用国内 Dashboard 查询。
- 迁移：实时查询可不迁移；物化统计需要新增式 migration。
- 国内影响：应为零，国内 Dashboard 契约不变。
- 测试：scope 查询、语言和来源分布、时间窗口、热词归一化、空数据和权限。
- 回滚：隐藏外网入口或停用 API，统计表可保留。
- 开启条件：3A 风险字段稳定，热词口径和翻译策略获确认。

### Phase Foreign-Source-3E：外网来源分布/舆论地域视图

- 目标：提供来源国家、媒体位置、语言和涉华议题分布。
- 新增表：可选 `foreign_source_locations`、`foreign_geo_mentions`。
- API：`/api/foreign/source-distribution`，必要时外网专题视图 API。
- 服务：`ForeignSourceDistributionService`，后续再评估内容地域抽取。
- 前端：外网来源分布视图；不进入中国行政区地图。
- 公共基础设施：复用图表、地图渲染基础设施，但使用新的数据契约和地图资源。
- 迁移：只有落库抽取结果时需要迁移。
- 国内影响：应为零。
- 测试：来源国家、媒体所在地、内容涉及地域三者区分，低置信度和未知值。
- 回滚：停用抽取/视图，保留原文和来源快照。
- 开启条件：业务明确“地域”含义，数据源元数据完整，误导风险可接受。

## 13. 当前不能直接实施的事项

在没有新增授权和业务确认前，不应直接：

- 把外网 Opinion 传给现有 `RiskEngine` 并写回国内字段；
- 把外网 Opinion 传给 `EventAggregator`；
- 把外网数据送入 `AlertService.evaluate()`；
- 让国内 Dashboard、热词或 ChinaMap 读取 `foreign_opinions`；
- 把中文网和英文稿件自动聚合到一个事件；
- 以河北、全国或中国行政区表达外网地域；
- 复用 `AlertRule`、`AlertRecord` 存储外网告警；
- 在没有通知去重和人工确认机制时启用外网告警；
- 在没有明确外网权限模型时向现有权限代码添加模糊的 scope 分支。

## 14. 开放问题与业务确认

1. 外网风险分值是否沿用 0-100，但采用独立阈值和独立等级名称？
2. 英文情感是否需要三分类，还是增加 mixed/uncertain？
3. 中文网与英文稿件是否永久禁止自动跨语言聚合，还是仅首期禁止？
4. “涉华事件”中的地域究竟表示来源地、媒体地、舆论发生地还是内容涉及地？
5. 外网事件是否必须人工确认后才可进入 Dashboard 和告警？
6. 外网告警允许哪些通知渠道，通知是否必须人工确认？
7. 外网结果和正文的保留期限、版权限制和全文展示范围是什么？
8. 是否允许使用第三方翻译/语言模型，数据是否可以发送到外部服务？
9. 外网指标是否需要单独的审计报表和导出权限？
10. 生产启用前是否需要境外节点，若需要，节点认证、数据回传签名和网络出口由谁负责？

## 15. Go / No-Go 结论

### 当前阶段结论：GO FOR DESIGN ONLY

可以进入 3A 的详细设计评审，理由是：

- 外网基础采集、去重、存储、API、UI 和日志已经具备独立边界；
- `foreign_opinions` 与国内 Opinion/Event/Alert 物理关系已隔离；
- 国内 registry 已识别并排除 `is_foreign=true` 和 `foreign_rss`；
- 隔离测试数据库中没有外网意见残留，生产外网源未启用。

### 当前实施结论：NO-GO FOR DOWNSTREAM ENABLEMENT

暂不允许直接实施或开启外网风险、事件、告警、Dashboard、热词或地图，原因是：

- 现有国内 RiskEngine、EventAggregator、AlertService、DashboardService 和 ChinaMap 均有国内表或中文/行政区假设；
- 外网下游独立表、服务、API、权限和任务边界尚未实现；
- 外网语言、风险阈值、跨语言事件和地域语义仍需业务确认；
- 当前公共告警表和国内下游 API 没有可接受的 foreign scope 契约。

## 16. 最终确认

- 没有修改 Python、TypeScript、Vue、SQL、Alembic 或配置文件。
- 没有修改数据库结构或数据库数据。
- 没有启用三个生产外网数据源。
- 没有启动自动调度或触发现有采集任务。
- 没有写入 `foreign_opinions`。
- 没有写入 `opinions`。
- 没有调用风险、事件、告警、Dashboard、地图或热词生产链路。
- 没有使用代理或境外采集节点。
- 本阶段只新增了本审计设计报告。
