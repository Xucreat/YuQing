# Phase Foreign-Source-3D Dashboard、热词与地图设计评审

## 1. 评审结论摘要

本阶段仅完成只读审计和独立架构设计，没有实施代码、配置、数据库迁移或数据库写入。

推荐结论：

- 外网 Dashboard 可以进入隔离测试实现设计，但不能直接在生产库实现或启用。
- 外网热词可以进入隔离测试实现设计，首期采用中英文分开、规则可解释的统计。
- 外网地图暂缓，不复用国内中国行政区地图；首期实现来源媒体、来源国家元数据、语言和时间分布。
- 外网可视化必须只经过 `/api/foreign/*`，不得通过国内 Dashboard API 增加隐式过滤。
- 首期直接查询现有 `foreign_*` 表，不新增快照表；手动重建需要独立的 `foreign_visualization_runs` 或等价审计结构。
- 当前默认库仍为 `foreign_source_1`，3A、3B、3C 表尚未在默认库应用。因此当前只能批准隔离环境中的后续实现，不能批准生产启用。

## 2. 审计边界和环境证据

### 2.1 执行的只读检查

- `git status --short`
- 根目录执行 `alembic current`：因仓库根目录没有 `alembic.ini`，命令返回找不到配置文件。
- 在实际 Alembic 目录执行 `alembic -c alembic.ini current`。
- 使用当前 `.env` 的数据库连接执行只读 SQL 快照。
- 使用 `rg`、源码阅读和静态路由检查。

实际 Alembic 命令输出确认：

```text
DATABASE_URL: 127.0.0.1:5432/opinion_db
Database: opinion_db
Alembic version: foreign_source_1
DATABASE IDENTITY: VERIFIED
```

### 2.2 默认库只读快照

| 对象 | 数量/状态 |
|---|---:|
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `foreign_opinions` | 3 |
| `foreign_risk_results` | 不存在，3A 未迁移 |
| `foreign_events` | 不存在，3B 未迁移 |
| `foreign_alerts` | 不存在，3C 未迁移 |
| `foreign_event_runs` | 不存在，3B 未迁移 |
| 外网 `collector_runs` 状态为 `running` | 0 |

外网数据源快照：

| source key | `enabled` | `schedule_enabled` |
|---|---:|---:|
| `foreign_fox_news` | false | false |
| `foreign_guardian` | false | false |
| `foreign_nyt_chinese` | false | false |

本阶段没有执行 upgrade、downgrade、INSERT、UPDATE、DELETE、TRUNCATE、采集、AI、代理连接或通知发送。工作区已有修改、未跟踪文件、备份和临时目录均保留；本报告是本阶段唯一新增或更新的文件。

## 3. 当前国内实现审计

### 3.1 Dashboard 统计

实际实现位于 `backend/app/services/dashboard_service.py` 和 `backend/app/api/dashboard.py`：

- `total`、`today`、`high_risk` 直接统计国内 `opinions`，并按 `geo_filtered` 过滤。
- `event_count` 统计国内 `events`，排除 `status='deprecated'`。
- 趋势按国内 `Opinion.created_at` 的日期统计，情感和来源也来自国内 `opinions`。
- `regions` 使用 `Opinion.region_id` 聚合，再按 `regions.code` 回卷到省级。
- 兼容字段 `keywords` 来自 `Opinion.keywords`；指挥大屏 `hot_keywords` 从国内 `keywords` 表匹配 `opinions.title/content`。
- 服务使用进程内缓存，缓存键包括天数和统计类型，不具备外网 scope 语义。

国内 API 包括 `/api/dashboard/stats`、`/recent`、`/alerts`、`/hot-keywords`、`/region-children`、`/kpi-trends`、`/risk-distribution` 和 `/alert-stats`。这些接口保持国内语义，不应添加 foreign 分支。

### 3.2 国内事件和告警

- `events` 通过 `event_opinions` 关联国内 `opinions`；`event_opinions.opinion_id` 是国内 `opinions.id` 外键。
- 国内事件 API 会反查 `Opinion`、`Region` 和 `AlertRecord`，并提供按 `region_id`、风险、热度和时间筛选。
- 国内 `AlertService` 读取 `Opinion`、国内 `AlertRule` 及国内关键词语义，写入 `alert_records`。
- 国内告警统计由 `alert_records` 提供，状态为 `pending`、`processing`、`resolved`、`ignored`、`false_positive`。
- 国内事件、告警和 Dashboard 之间已有业务联动；外网统计不得复用这些服务或表。

### 3.3 国内地图真实语义

`ChinaMap.vue` 是中国行政区 choropleth：

- 使用本地中国省级 GeoJSON，地图名称为 `china`，下钻使用省级 adcode 和省级 GeoJSON。
- 服务端的 `regions` 依赖 `Opinion.region_id -> regions.id`。
- `/api/dashboard/region-children` 按中国省名、行政区划 code 和市县层级返回下钻数据。
- 来源地、文章涉及地和舆情发生地在国内语义中由 `region_id` 近似承载；这不是外网新闻媒体所在国的通用表达。

因此，外网文章没有国内 `region_id` 时，不能默认为河北、全国或任一中国行政区，也不能把来源媒体所在地当作舆情发生地。

## 4. 当前外网实现审计

### 4.1 外网输入和风险链路

当前代码已形成如下边界：

```text
foreign data_sources(is_foreign=true)
  -> ForeignRSSCollector / ForeignCollectionService
  -> foreign_opinions
  -> ForeignRiskService + foreign_risk_terms
  -> foreign_analysis_runs + foreign_risk_results
  -> ForeignEventService
  -> foreign_event_candidates / foreign_events / foreign_event_opinions
  -> ForeignAlertService
  -> foreign_alert_rules / foreign_alerts / foreign_alert_runs
```

- `ForeignOpinion` 有 `source_key`、`source_name_snapshot`、标题、摘要、正文、URL、发布时间、采集时间、匹配监测词和 `content_hash`，没有国内 `region_id`。
- `ForeignRiskService` 只读取 `ForeignOpinion`、`ForeignRiskTerm`，规则评分默认基线为 20，风险阈值为 40/70；采集监测词不直接当作风险词。
- 外网风险结果有 `language`、`risk_score`、`risk_level`、`risk_category`、`analysis_status`、当前版本和安全错误摘要。
- `ForeignEventService` 按同语言、时间窗口和词法相似度产生候选；candidate 与 confirmed 分离，候选不进入国内事件。
- `ForeignEvent`、`ForeignEventOpinion` 和 `ForeignEventAction` 的外键只指向外网事件、外网文章和用户。
- `ForeignAlertService` 只导入外网文章、风险、事件、规则和告警模型；评估是显式调用，未接入采集调度，也不调用国内 `AlertService`。
- `ForeignAlert` 保存规则快照、消息快照、来源快照、风险快照、去重键和状态；`ForeignAlertAction` 独立保存外网处置审计。

外网 API 已有 `/api/foreign/opinions`、`/risk`、`/events*`、`/alerts*`、`/alert-rules`、`/alert-runs` 等入口。当前 `ForeignWorkspace.vue` 已有 opinions、risk、events、alerts、keywords、sources、runs 七个 tab，但没有 dashboard、hotwords 或 map tab。

### 4.2 当前生产状态和实现前提

工作区内已有 3A/3B/3C 模型、服务、API 和 Alembic 文件属于未应用到默认库的后续实现。默认库仍为 `foreign_source_1`，所以当前生产库不能被当作已经具备 3D 输入表的验证环境。3D 实现和验收必须先使用独立测试数据库或 fixture，并继续保留已有外网文章及采集日志。

## 5. 外网 Dashboard 独立架构

### 5.1 数据边界

首期 Dashboard 的唯一业务数据源为：

- `foreign_opinions`
- 当前版本且已完成的 `foreign_risk_results`
- `foreign_events`
- `foreign_event_opinions`
- `foreign_alerts`
- `foreign_event_runs`、`foreign_analysis_runs`、`foreign_alert_runs` 的外网运行状态

不读取 `opinions`、国内 `events`、`event_opinions`、`alert_records`、`keywords`、`regions` 或国内 Dashboard 统计。共享的 `collector_runs` 即使带 `scope='foreign'`，也不纳入 Dashboard 业务 KPI；它继续由外网采集日志 API 按 scope 展示，避免跨 scope 聚合。

### 5.2 API 设计

建议新增独立路由：

| API | 口径 |
|---|---|
| `GET /api/foreign/dashboard/summary` | 外网文章、已完成风险、事件和外网告警总览 |
| `GET /api/foreign/dashboard/trends` | 按 UTC 日期边界和显示时区返回文章、风险、事件、告警趋势 |
| `GET /api/foreign/dashboard/sources` | 来源快照、source_key、文章数、事件数、风险数 |
| `GET /api/foreign/dashboard/languages` | `zh`、`en`、`mixed`、`unknown` 分布 |
| `GET /api/foreign/dashboard/risk` | 风险等级、类别、分析状态及未完成/失败数量 |
| `GET /api/foreign/dashboard/events` | candidate、confirmed、monitoring、resolved、archived 的分布 |

所有接口都应要求现有认证，并新增或明确 `foreign:dashboard:read` 权限。参数统一使用 `days=1..90` 或明确的 ISO8601 `from/to`，服务端转换为 UTC；返回 `data_as_of`、`timezone`、`window_start`、`window_end` 和 `incomplete` 元数据。

### 5.3 统计口径

- 采集量：按 `foreign_opinions` 实际落库文章数；去重文章不重复计入新增量。
- 新增量：按 `collected_at`，发布时间仅用于事件首末时间和内容分析时间展示。
- 去重量：只展示已有外网采集运行记录提供的去重计数，不从文章总量反推。
- 风险：`is_current=true` 且 `analysis_status='completed'` 才进入正式风险分布；`pending/processing/failed/skipped` 单独展示。
- 事件：candidate 只能进入候选卡片；confirmed、monitoring、resolved、archived 分开计数，不把 archived 偷换成 active。
- 告警：`triggered`、`acknowledged`、`resolved`、`suppressed`、`failed` 分开计数，失败运行与业务告警失败分开显示。
- 空数据返回稳定的空结构；未完成风险和失败运行显示为处理中/失败，不折算为低风险或零告警。
- 默认展示窗口内已完成风险结果和人工确认事件，同时提供“包含未完成/失败”的只读筛选，避免误解数据完整性。

### 5.4 性能策略

首期使用限定窗口的直接查询，复用已有外网表索引，并补充评审后的外网索引：`foreign_opinions.collected_at`、`foreign_opinions.source_key`、风险结果的 `language/risk_level/risk_category` 组合索引，以及事件和告警的状态+时间组合索引。索引变更只能在 3D 实现的独立迁移中评审。

不在首期新增物化视图或跨国内表缓存。进程内缓存不能作为统计正确性的来源；若缓存存在，键必须包含 scope、窗口、时区、筛选条件和统计版本。

当文章量、窗口查询 p95 或并发超过业务阈值时，再引入 `foreign_dashboard_snapshots` 和 `foreign_visualization_runs`。快照必须包含统计版本、窗口、筛选条件、生成时间、结果 JSON 和安全错误摘要，且只保存 foreign 数据。

## 6. 外网热词独立架构

### 6.1 API 和输入

建议新增：

- `GET /api/foreign/hotwords`
- `GET /api/foreign/hotwords/trends`
- `GET /api/foreign/hotwords/sources`

首期输入优先级：`foreign_opinions.title`、`summary`、`content`；已确认外网事件标题可作为独立的“事件主题词”视图，不与文章词频直接混合。`foreign_risk_results.matched_terms` 和 `foreign_alerts` 的条件只作为可选的风险词视图，不能伪装成自然热词。

`中国`、`Chinese`、`China` 是采集/筛选监测词，不应直接成为热词结果。外网统计不得读取国内 `keywords`，也不得把 `foreign_keywords` 自动解释成风险词。

### 6.2 语言和归一化规则

- `zh`、`en` 分开统计；`mixed` 单独统计或默认排除在双语主榜之外；`unknown` 只进入质量统计。
- 英文使用 Unicode `casefold`、标点和空白归一化，首期不强制词形还原；如增加 stemming，必须记录 tokenizer/version。
- 中文首期使用明确版本的分词器和停用词表；没有可靠分词时宁可返回字符 n-gram 质量较低状态，不把中英文翻译后强行合并。
- 停用词、监测词、国家名、人名和机构名要分成不同词典。人名和机构名需要实体识别置信度，不能仅因字符串出现就当作稳定实体。
- 热词结果保存 `language`、词典版本、统计窗口、来源筛选、计数和趋势。首期不强制持久化快照，实时结果必须带 `data_as_of`。
- 允许人工排除词，但排除规则必须属于 foreign scope，具有版本和审计记录；不得复用国内敏感词表。

### 6.3 质量和失败

无文章、无可分词内容和 mixed/unknown 占比过高时，API 返回 `empty` 或 `incomplete` 标志，不生成确定性热词。分词或统计失败写入 `foreign_visualization_runs` 的安全摘要；不会修改文章、风险、事件或告警表。

## 7. 外网地图和来源分布

### 7.1 现有国内地图不适用的原因

国内地图依赖 `region_id`、`regions` 表、中国行政区 GeoJSON 和中国省市下钻接口。`ForeignOpinion` 没有 `region_id`，而来源媒体所在国、文章涉及国、事件发生国和读者舆论地域也不是同一字段。直接复用会造成错误的确定性结论。

禁止：

- 将所有外网数据标成河北或全国。
- 使用国内 `region_id` 代替外网地域。
- 把 Fox News、The Guardian 等媒体所在地当作文章讨论事件发生地。
- 在没有实体识别和人工确认时显示精确的事件地图。

### 7.2 方案比较和推荐

| 方案 | 评估 |
|---|---|
| A 来源国家/媒体分布 | 可解释、数据易得；需要受控的来源元数据，不能从名称猜国家 |
| B 舆论涉及地域 | 需要实体识别和人工确认，误判及跨语言歧义高 |
| C 中国议题的海外来源分布 | 适合首期业务问题，但仍应区分来源国家与议题涉及地 |
| D 暂缓地图 | 风险最低，首期做来源、语言、时间趋势 |

推荐 `D + A/C`：首期把“来源分布”做成外网视图，按 `source_key`、`source_name_snapshot`、受控来源国家元数据、语言和时间趋势展示；不做行政区地图。来源国家字段必须来自审核过的数据源配置或独立来源元数据，不能从 URL/TLD 自动推断为事件地域。

若未来确实需要“涉及地域”，应新增独立的 `foreign_topic_regions` 或等价事实表，保存实体、标准化名称、国家/地区代码、置信度、识别版本、人工确认状态和证据片段。该表不能引用国内 `regions.id`，并且低置信度只能显示“未知/待确认”。

## 8. UI 设计

### 8.1 ForeignWorkspace 入口

当前 `/foreign` 没有 `dashboard`、`hotwords`、`map` tab。3D 实现阶段建议增加：

- `/foreign?tab=dashboard`：外网总览、风险、事件、告警和来源概况。
- `/foreign?tab=hotwords`：中英文热词、趋势、来源筛选和词典质量状态。
- `/foreign?tab=source-distribution`：来源媒体/国家元数据/语言/时间趋势；不称作地理事件地图。

若产品必须保留 `/foreign?tab=map`，该 tab 首期只能展示“地图暂缓”和来源分布替代视图，不能绘制中国行政区地图或作事件地域结论。

所有外网页面只调用 `/api/foreign/*`。国内 `Dashboard.vue`、`Alerts.vue`、`Events.vue` 和 `ChinaMap.vue` 不修改。

### 8.2 展示状态

每个 tab 应明确展示数据窗口、显示时区、`data_as_of` 和统计版本，并区分：

- `loading`：请求进行中；
- `empty`：窗口内没有可用 foreign 数据；
- `processing`：风险、事件或统计运行尚未完成；
- `failed`：运行失败，显示安全错误摘要和失败时间；
- `disabled`：外网可视化或自动重建未启用；
- `completed`：统计窗口和数据更新时间明确。

候选事件、已确认事件、风险未完成和告警失败不能在 UI 中显示为空白或被折算为成功数据。无权限用户收到稳定 403，前端隐藏管理/重建入口，但后端权限仍是安全边界。

## 9. 权限和审计设计

建议权限：

- `foreign:dashboard:read`
- `foreign:hotwords:read`
- `foreign:source-distribution:read`
- `foreign:visualization:export`
- `foreign:visualization:rebuild`
- `foreign:visualization:manage`（词典/排除规则等配置）

普通外网读用户只能查询统计；导出和重建分离。手动 rebuild 只能由管理员或明确的 `foreign:visualization:rebuild` 权限调用，必须限制窗口、数量、并发和超时。每次 rebuild 记录调用人、开始/结束时间、窗口、统计版本、处理数、成功数、失败数和安全错误摘要。

推荐新增 `foreign_visualization_runs`，统一承载 Dashboard、hotword 和 source-distribution 的手动/重建运行日志；也可以在实现阶段拆成 `foreign_dashboard_runs`、`foreign_hotword_runs`，但不能复用国内运行或审计表作为业务结果表。查询 API 不应创建运行记录；刷新只触发缓存失效，不应默默写生产数据。

## 10. 数据模型、快照和重算

### 10.1 首期

首期不新增 `foreign_hotword_snapshots` 或 `foreign_dashboard_snapshots`，直接对有索引的 `foreign_*` 表进行窗口查询。外网已有事件、告警、分析运行日志作为状态来源；不会把统计写入国内 Dashboard 统计表。

### 10.2 规模增长后

只有出现以下任一情况才考虑快照：跨进程缓存不一致、同一窗口查询 p95 超出业务 SLA、导出需要稳定历史结果、或数据规模使词频扫描不可接受。快照模型至少保存 `scope='foreign'`、`calculation_version`、`window_start/end`、`timezone`、筛选 JSON、结果 JSON、生成时间和状态。

快照重建应幂等：同一版本+窗口+筛选可以覆盖同一 foreign 快照或生成带版本的新快照；失败记录 run，不删除源数据。来源删除后历史快照保留来源名称快照并标记 `source_removed`，不能悄悄重算为零。

### 10.3 索引和隔离性能验证

3D 实现前应在独立测试库评估执行计划，并确认查询只扫描 `foreign_*`。首期重点检查 `collected_at`、`published_at`、`source_key`、风险状态/语言/类别、事件状态/语言/时间、告警状态/触发时间和关联表外键索引。性能测试必须包含空数据、单语言、mixed、多个来源、窗口边界和失败运行。

## 11. 未来实施阶段

### Phase Foreign-Source-3D-Implementation

1. 在从 `foreign_source_3c_remediation` 派生的独立测试数据库应用必要迁移；不触碰 `opinion_db`。
2. 建立 `ForeignDashboardService`、`ForeignHotwordService` 和 `ForeignSourceDistributionService`，服务层禁止导入国内 Dashboard、Alert、Event、Keyword、Region 服务。
3. 增加 `/api/foreign/dashboard/*`、`/api/foreign/hotwords*` 和来源分布 API，统一认证、分页、窗口、时区和安全错误结构。
4. 在 ForeignWorkspace 增加 dashboard、hotwords、source-distribution 入口；不改国内页面。
5. 首期只读统计和手动查询；默认不自动重建、不启用生产源、不发送通知。
6. 若实现 rebuild，再增加 `foreign_visualization_runs`；快照表留到性能证据出现后。
7. 回滚只允许在临时库验证 migration downgrade；生产启用前必须有独立审批和验收报告。

### Phase Foreign-Source-3D-Acceptance

使用本地 fixture/mock 验收：

- Dashboard 的文章、风险、事件、告警数量和趋势口径；
- 风险未完成/失败和事件 candidate/confirmed/archive 状态；
- 中英文热词隔离、监测词排除、停用词和 mixed/unknown 处理；
- 来源分布不把来源地误报为事件发生地；
- 空、处理中、失败、无权限和更新时间展示；
- API 只返回 foreign 数据，页面网络请求只命中 `/api/foreign/*`；
- 外网统计前后国内 `opinions/events/event_opinions/alert_records` 快照不变；
- 失败重建可恢复、重复重建幂等、性能执行计划不扫描国内表；
- upgrade/downgrade/upgrade 往返只在临时库执行。

通过后仍需单独审批外网源、调度、风险、事件和告警的生产启用；3D 验收本身不授权自动化或生产灰度。

## 12. 国内/国外隔离验证清单

实现阶段必须逐项提供证据：

1. Dashboard 服务的 SQL/ORM 不出现 `opinions`、`events`、`event_opinions`、`alert_records`、`keywords`、`regions`。
2. 热词服务只读取 `foreign_opinions` 和明确批准的外网风险/事件快照，不读取国内 `keywords`。
3. 来源分布不读取国内 `region_id`、行政区或中国 GeoJSON。
4. 外网 API 不调用国内 Dashboard、Events、Alerts、Keywords、Map API。
5. 外网统计不写国内 Dashboard 统计表，不创建国内事件或告警。
6. `foreign_events` 不进入国内事件统计，`foreign_alerts` 不进入国内告警统计。
7. 外网 Dashboard、热词和来源分布失败时国内数据快照不变。
8. API 响应中不存在国内对象 ID、国内文章、国内事件或国内告警。
9. 统计查询和重建有 `foreign` scope、权限和审计记录。
10. 自动调度关闭时不会自动触发外网统计、事件或告警评估。
11. 外部 RSS、AI、代理和通知调用计数为 0。
12. 生产数据库 Alembic 仍保持原 revision，未执行迁移、写入或回滚。

## 13. 已知风险和开放问题

- 默认库当前只有 `foreign_opinions`，3A/3B/3C 后续表不存在；必须先完成并验收前置阶段的独立迁移，不能在默认库补迁移。
- `ForeignOpinion` 当前没有持久化语言字段，语言统计首期需要依赖当前风险结果；未分析文章只能进入 unknown/incomplete，不能猜测语言。
- 来源国家元数据尚未在外网文章模型中形成受控字段；必须先确定数据源元数据契约，禁止从媒体名称猜测事件地域。
- 中文分词、英文词形变化、实体识别和中英翻译归一化会显著影响热词质量；首期不做强制翻译聚合。
- 现有进程内缓存不能解决多实例一致性；在没有快照/run 设计前，不应提供声称“历史稳定”的导出。
- 现有调度器包含国内 `AlertService` 自动评估逻辑；未来实现必须证明外网统计、事件、告警评估没有注册到该任务，并单独审计生产配置。
- 共享 `collector_runs` 带有 `scope`，但为满足外网 Dashboard 只读 `foreign_*` 的硬边界，本设计不把它混入 Dashboard KPI；运行日志仍通过外网专用查询入口展示。
- 外网数据源被删除时，source snapshot、事件和统计历史的保留策略尚未完成业务确认。

## 14. Go/No-Go

| 问题 | 结论 |
|---|---|
| 当前可否直接实现外网 Dashboard | 生产：No-Go；隔离环境：有前置条件后 Go |
| 当前可否直接实现外网热词 | 生产：No-Go；隔离环境：有前置条件后 Go |
| 当前可否直接实现外网地图 | No-Go |
| 首期是否暂缓地图 | 是 |
| 推荐替代方案 | 来源媒体/来源国家受控元数据、语言分布和时间趋势 |
| 首期是否需要统计快照表 | 不需要，先直接查 foreign 表 |
| 是否需要 `hotword_runs` | 直接查询阶段不需要；手动重建阶段需要 `foreign_visualization_runs` 或等价结构 |
| 是否允许直接查询 `foreign_*` | 允许，但必须有窗口、索引、权限和只读边界 |
| 当前是否进入 3D 实现 | 仅允许隔离测试实现；不允许生产实现/启用 |
| 是否允许进入生产灰度 | 通过 3D 实施和验收、完成数据源元数据与权限确认，并经独立生产审批后才可评估 |

进入实现前需要业务确认：默认时间窗口和展示时区、风险/事件/告警的统计口径、来源国家元数据来源、mixed/unknown 的展示策略、热词停用词和人工排除权限、是否需要稳定导出、快照保留期、以及外网可视化与自动调度的长期开关策略。

## 15. 本阶段最终声明

- 未修改 Python、TypeScript、Vue、SQL、Alembic 或配置文件。
- 未修改数据库结构或数据库数据。
- 未启用外网源，三个外网源仍为 disabled，`schedule_enabled=false`。
- 未启用自动调度、自动风险、自动事件或自动告警。
- 未执行真实采集，未访问真实 RSS、外部 AI、代理或境外节点。
- 未发送任何通知。
- 未修改国内 Dashboard、地图、热词、事件、告警或风险行为。
- 未删除用户已有的外网文章、风险结果、事件、告警或采集日志。
- 本阶段只新增/更新本设计评审报告。
- 结论：允许进入 `Phase Foreign-Source-3D-Implementation` 的隔离设计实现准备；不允许生产启用，也不允许把外网统计接入国内链路。
