# Phase Foreign-Source-3C
# 外网告警链路只读审计与独立架构设计

## 1. 阶段边界与审计结论

本阶段是只读审计和设计评审，不实施代码。审计期间未修改 Python、TypeScript、Vue、SQL、Alembic、配置、数据库结构或数据库数据；未启用外网来源、自动调度、外网事件自动聚合或任何告警通知；未访问真实 RSS、外部 AI、代理或境外采集节点。

**当前结论：外网告警实现为 NO-GO，进入 3C Implementation 设计准备为 CONDITIONAL GO。** 当前国内告警链路与外网风险/事件基础链路已具备清晰的物理表边界，但尚不存在可供外网告警直接使用的表、服务、API、权限和通知 scope。下一阶段必须新建 `foreign_*` 告警模型，并在独立预发布库中完成迁移和隔离验证后才能实现。

## 2. 前置检查与环境状态

执行了：

```text
git status --short
alembic current
```

工作区存在用户既有源码修改、未跟踪文件、备份和临时文件。它们全部保留，未执行 `git reset`、`git checkout`、清理或整理。当前目标报告此前不存在，本文件是本阶段唯一新增文件。

### 2.1 默认数据库

`alembic current` 的数据库身份检查结果：

| 项目 | 结果 |
|---|---|
| 数据库 | `opinion_db` |
| Alembic revision | `foreign_source_1` |
| 3A/3B 外网下游表 | 默认库不存在 |
| `opinions` | 1702 条 |
| `events` | 292 条 |
| `event_opinions` | 567 条 |
| `alert_rules` | 2 条 |
| `alert_records` | 37 条 |
| `foreign_opinions` | 3 条 |
| `foreign_risk_results` | 不存在 |
| `foreign_events` | 不存在 |

默认库不是本阶段可写的临时库，因此没有执行迁移、插入、更新、删除、truncate 或 downgrade。默认库的 3 条外网舆情和 3 条 foreign 采集日志视为已有人工样本/审计数据，未删除。数量与早期报告中的历史测试库快照不同，属于当前环境事实，不在本阶段修复。

### 2.2 外网来源、调度和代理

默认库中三个外网来源的只读状态如下：

| source key | 名称 | enabled | schedule_enabled |
|---|---|---:|---:|
| `foreign_fox_news` | Fox News | false | false |
| `foreign_guardian` | The Guardian | false | false |
| `foreign_nyt_chinese` | 纽约时报中文网 | false | false |

`collector_runs` 中 scope/status 统计为 `foreign/success=3`，`foreign` 且 `running` 或 `processing` 为 0。没有发现运行中的外网采集任务；本阶段没有触发采集。以下环境变量均未设置，检查时没有输出其值：

```text
HTTP_PROXY=UNSET
HTTPS_PROXY=UNSET
ALL_PROXY=UNSET
FOREIGN_HTTP_PROXY=UNSET
FOREIGN_HTTPS_PROXY=UNSET
```

需要特别区分：应用配置的 `alert_eval_enabled=true` 是既有国内告警定时评估开关，当前 scheduler 的 `_run_alert_eval_job()` 只调用国内 `AlertService`，不代表外网告警已启用。3C 不修改该国内配置或任务。

### 2.3 已知国内基线失败

此前聚焦国内回归为 `54 passed, 5 failed`。报告及后续实施必须保留这些基线，不得修改断言或业务代码：

| 测试 | 分类 |
|---|---|
| `test_event_orm_persist` | 历史断言与当前 `Event.status` 模型不一致 |
| `test_same_keyword_one_event` | 历史事件标题选择语义与当前实现不一致 |
| `test_api_aggregate` | 历史测试期望同步聚合，当前 API 返回异步 `task_id` |
| `test_api_list_pagination` | 依赖上述历史同步聚合行为 |
| `test_4_viewer_forbidden` | 测试库缺少 `viewer` 角色 fixture |

本阶段未重新执行会产生写入的评估动作，也未掩盖这些失败。进入实现时应先单独确认它们不是新的外网改造回归。

## 3. 当前国内告警链路真实实现

### 3.1 调用关系

```text
国内 scheduler / POST /api/alerts/evaluate
    -> AlertService.evaluate(db)
    -> enabled alert_rules
    -> Opinion 查询
    -> AlertRecord 写入 alert_records
    -> AlertService.sync_alert_events(db)
    -> event_opinions 查询
    -> Event / event_opinions 关联
    -> 国内 Alerts API 与前端轮询
```

`backend/app/services/alert_service.py` 中 `AlertService.evaluate()` 直接查询 `Opinion`，使用 `Opinion.risk_score`、`title`、`content`、`keywords`、`source` 和国内 `get_monitoring_keywords()`。它可以按风险阈值、关键词和来源筛选，然后写 `AlertRecord`。`sync_alert_events()` 再通过国内 `EventOpinion` 查找并回写 `AlertRecord.event_id/event_title`。

`backend/app/core/scheduler.py` 以 `alert_eval_enabled` 控制定时执行 `AlertService.evaluate()` 和 `sync_alert_events()`。因此未来任何外网评估调用都不能挂入这个国内 job，也不能把外网结果写进现有模型以“自然复用”。

### 3.2 国内数据模型和 API 边界

`AlertRule` 位于 `alert_rules`，字段是国内语义的 `risk_threshold`、文本 `keywords`、`sources`、固定 `risk_level` 和 `enabled`。`AlertRecord` 位于 `alert_records`，其外键为：

```text
alert_records.rule_id    -> alert_rules.id
alert_records.opinion_id -> opinions.id
alert_records.event_id   -> events.id
alert_records.handled_by -> users.id
```

该表没有 `scope`，不适合保存外网告警。国内 API 位于 `/api/alerts/*`，包括 rules、evaluate、unread、records 和 handle。`frontend/src/views/Alerts.vue` 与 `frontend/src/composables/useAlertNotifier.ts` 使用该命名空间；通知器轮询 `/api/alerts/unread`，因此外网告警不能写入该表或复用该 unread 接口，否则会污染国内红点和 Toast。

当前代码中未发现独立的邮件、短信、企业微信、钉钉或其他外部通知发送器。可复用的现有能力主要是认证、权限、`audit_write`、数据库事务和前端站内展示基础设施。

## 4. 当前外网风险与事件链路

当前设计上的外网链路为：

```text
foreign_opinions
    -> ForeignRiskService
    -> foreign_risk_results / foreign_analysis_runs
    -> ForeignEventService
    -> foreign_event_candidates
    -> foreign_events / foreign_event_opinions / foreign_event_runs / foreign_event_actions
    -> /api/foreign/risk/*, /api/foreign/events/*
    -> /foreign?tab=risk|events
```

默认 `opinion_db` 仍停留在 `foreign_source_1`，所以以上 3A/3B 表在默认库不能作为现状数据表使用；它们只存在于独立测试/预发布实现上下文。`ForeignOpinion` 不含国内 `region_id`。3A 风险结果只以 `foreign_opinion_id` 关联 `foreign_opinions`；3B 事件关联只使用 `foreign_events` 与 `foreign_opinions`，不使用国内 `events` 或 `event_opinions`。

外网事件 API 位于独立的 `/api/foreign/events*` 路径，工作台 `/foreign?tab=events` 目前只调用 foreign events、foreign event-runs 和 candidate 接口。工作台没有 alerts tab，告警只能作为后续设计入口，不能假定已存在。

## 5. 国内/国外对照表

| 能力 | 国内现状 | 外网现状 | 3C 建议 |
|---|---|---|---|
| 文章 | `opinions` | `foreign_opinions` | 保持两表隔离 |
| 风险 | `Opinion` 字段 + 国内 `RiskEngine` | `foreign_risk_results` | 只读 foreign risk result |
| 事件 | `events` + `event_opinions` | `foreign_events` + `foreign_event_opinions` | 只读 foreign event |
| 告警规则 | `alert_rules` | 不存在 | 新建 `foreign_alert_rules` |
| 告警记录 | `alert_records`，外键指向国内表 | 不存在 | 新建 `foreign_alerts` |
| 运行审计 | 国内 scheduler 日志/审计 | `foreign_event_runs` 等已有外网运行审计 | 新建 `foreign_alert_runs` |
| 通知 | 国内 `/alerts/unread` 轮询和 Toast | 不存在 | 新建 foreign unread，首期仅站内 |
| API | `/api/alerts/*` | `/api/foreign/risk/*`, `/api/foreign/events/*` | `/api/foreign/alerts/*` |
| UI | `/alerts` | `/foreign?tab=risk|events` | `/foreign?tab=alerts` |

## 6. 外网告警输入边界与状态语义

外网告警评估服务的业务输入限定为：

```text
foreign_opinions
foreign_risk_results
foreign_events
foreign_event_opinions
foreign_event_runs
```

若实现来源异常规则，必须由业务确认是否允许额外读取 `collector_runs` 的 `scope='foreign'` 行；这不是 `foreign_event_runs` 的替代字段。无论是否批准，都禁止读取 domestic scope、国内 `opinions`、国内 `events`、国内 `alerts`、国内 `keywords`、国内 sensitive 词表和国内 Dashboard 聚合。

建议准入规则：

| 输入状态 | 首期处理 |
|---|---|
| 风险分析 `completed` | 可按显式风险规则评估 |
| 风险分析 `pending/processing` | 不触发依赖风险结果的正式告警，保留待评估 |
| 风险分析 `failed` | 默认禁止风险告警，记录评估跳过原因 |
| 事件 `candidate` | 不触发正式告警，可进入候选/待复核计数 |
| 事件 `confirmed` | 可作为事件规则输入 |
| 事件 `monitoring` | 可作为持续监测输入 |
| 事件 `resolved` | 默认抑制新告警，除非明确升级或重新激活 |
| 事件 `archived` | 默认不触发，人工重新激活后才可评估 |
| 事件 `rejected` | 不得触发或自动恢复 |

首期允许基于风险等级、风险分阈值、风险类别、已确认/监控事件、事件热度/文章数、经过组合的关键词和来源异常设计规则。单独命中“中国”、`Chinese` 或 `China` 不得触发高风险告警；监测关键词、风险词、事件主题词必须保持不同来源和不同语义。单篇文章可以触发，但必须同时满足明确的风险/事件条件。

## 7. 推荐独立数据模型

### 7.1 `foreign_alert_rules`

推荐新增表，至少包含：

| 字段 | 设计 |
|---|---|
| `id` | 主键 |
| `name`, `description` | 规则展示和说明 |
| `is_enabled` | 默认 `false` |
| `rule_type` | `risk_score`、`risk_level`、`risk_category`、`confirmed_event`、`keyword_combo`、`source_health` |
| `conditions` | JSONB，保存结构化条件、组合方式、版本 |
| `severity` | `low/medium/high/critical` |
| `cooldown_seconds` | 非负冷却窗口 |
| `deduplication_key` | 模板或规则级默认键 |
| `created_by`, `updated_by` | `users` 外键，可空置为历史快照 |
| `created_at`, `updated_at` | UTC 时间 |

建议增加 `rule_version`、`last_triggered_at`、`disabled_reason` 和唯一的规则命名空间。规则变更不能改写历史告警使用的快照。

### 7.2 `foreign_alerts`

必须完全新建，不能把外网告警保存到国内 `alert_records`。推荐字段：

| 字段 | 设计 |
|---|---|
| `id` | 主键 |
| `rule_id` | 关联 `foreign_alert_rules`，规则删除时保留告警并置空或禁止删除 |
| `foreign_opinion_id` | 可空，关联外网文章 |
| `foreign_event_id` | 可空，关联外网事件 |
| `foreign_risk_result_id` | 可空，关联外网风险结果 |
| `severity`, `status` | 告警严重度和 `pending/acknowledged/resolved/suppressed/failed` |
| `title`, `message` | 告警快照，不依赖原文当前可用 |
| `matched_conditions` | JSONB，保存命中条件快照 |
| `deduplication_key` | 唯一/索引候选键 |
| `rule_snapshot` | JSONB，保存规则版本和关键配置快照 |
| `source_snapshot`, `opinion_snapshot`, `event_snapshot` | 关联对象删除或改名后的展示快照 |
| `triggered_at`, `acknowledged_at`, `resolved_at` | 状态时间 |
| `acknowledged_by`, `resolved_by` | `users` 外键，可空 |
| `suppressed_at`, `suppressed_by`, `failure_reason` | 抑制和失败留痕 |
| `created_at`, `updated_at` | UTC 时间 |

三种关联都应为可空，并通过 `CHECK` 保证至少有一个业务输入关联；外键只能指向对应 `foreign_*` 表。删除文章/事件/风险结果时，历史告警不能消失，应保留快照并将外键置空或使用受控保留策略。规则删除也不能破坏历史告警。

### 7.3 `foreign_alert_runs`

推荐新增独立运行审计表：`id`、`run_type`、`scope='foreign'`、`trigger_type`、`rule_version`、`started_at`、`finished_at`、`processed_count`、`triggered_count`、`deduplicated_count`、`failed_count`、`status`、`error_message`、`created_by`、`created_at`。仅允许人工评估或受控 dry-run；自动评估默认关闭。错误摘要必须脱敏并限制长度。

### 7.4 `foreign_notification_records` 与操作审计

首期不发送外部通知，因此可以暂不建通知表。进入外部通知阶段前新增 `foreign_notification_records`，记录 `foreign_alert_id`、`channel`、`scope='foreign'`、状态、重试次数、最后错误摘要、时间和消息快照。告警确认、解决、抑制、规则启停和人工评估建议新增 `foreign_alert_actions`；若复用通用审计表，必须有不可歧义的 `foreign` resource/scope，不能使用国内告警资源类型伪装。

### 7.5 迁移与回滚

3C Implementation 应从当前实际 head 创建迁移，不能在默认 `opinion_db` 上执行。独立预发布库必须按以下顺序验证：upgrade -> 检查表/索引/FK/check -> fixture dry-run -> downgrade -> 再 upgrade。downgrade 只能删除本阶段新增的 `foreign_alert_*` 表，并在确认无需保留的临时数据后执行；生产库禁止 downgrade。国内任何表不得被修改，外网历史样本也不得被迁移脚本清空。

## 8. 首期规则设计

### 8.1 条件组合

`conditions` 使用显式 AST/JSONB 结构，根节点必须声明 `all` 或 `any`。首期支持有限层级的 AND/OR，不支持任意 SQL 表达式和复杂否定条件。风险分与事件热度可以混合，但只有在规则配置中明确声明并全部满足时才成立，不能隐式把两个指标相加。

推荐首期规则：

1. 已完成分析且 `risk_score >= threshold`，同时可选限定 `risk_level` 或 `risk_category`。
2. `foreign_event.event_status in ('confirmed','monitoring')` 且 `heat_score` 或 `opinion_count` 达到阈值。
3. 监测关键词命中 + 独立风险词命中 + 风险/事件条件之一。
4. 来源异常：连续 foreign 采集失败、RSS 解析失败或超过无数据窗口。该规则与内容风险告警分开，读取来源异常输入前必须完成 `collector_runs(scope='foreign')` 的业务确认。

默认关闭所有规则，特别是来源异常、外部通知和批量自动评估。没有完成风险分析、风险分析失败或事件未确认时，不因文章存在或监测关键词命中而生成正式告警。

## 9. 去重、冷却与告警风暴控制

建议同时保存稳定去重键和规则版本：

```text
article: {foreign_opinion_id}:{content_hash}:{rule_id}:{rule_version}
event:   {foreign_event_id}:{rule_id}:{rule_version}
source:  {source_key}:{failure_class}:{time_bucket}:{rule_version}
```

规则评估应先在事务内锁定同键未过冷却的记录，再创建一条告警；重复采集、重复评估和重复请求均不得生成重复告警。单事件多篇文章默认合并为事件级一条告警，并把新增命中文章记录在 `matched_conditions` 或后续关联表中。升级应使用独立 `deduplication_key`，仅风险等级或事件热度跨阈值升级时触发。

来源恢复不得重放故障期间每个失败，最多生成一条恢复/汇总记录。内容风险和来源故障使用不同规则类型、严重度和冷却窗口。`acknowledged`、`resolved`、`suppressed` 状态只影响处置和再触发策略，不删除历史；规则禁用后不再新建告警，但既有告警保留。

## 10. 通知渠道设计

当前实现只有国内站内告警：后端 `alert_records`，前端 `/api/alerts/unread` 轮询以及 `AlertToastHost.vue` Toast/红点。未发现邮件、短信、企业微信、钉钉等独立发送器。

3C 首期建议只生成外网站内告警记录，不发送任何外部通知：

- 外网页面使用独立 `/api/foreign/alerts/unread`，不能复用国内 `/api/alerts/unread`。
- 外部通知开关默认关闭，且需要单独权限、配置和人工确认。
- 通知发送器若未来复用，只复用底层传输能力，调用参数必须包含 `scope='foreign'`、`foreign_alert_id` 和独立模板；国内 notifier 不得查询 foreign 表。
- 发送失败写入 `foreign_notification_records`，可重试次数有限，错误信息只保存安全摘要。
- 消息体使用 `title/message` 和来源/事件快照；不得包含 Token、密码、代理地址中的敏感信息。中英文双语模板应作为业务确认项，不在首期假定。

## 11. API 设计

设计但本阶段不实现：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/foreign/alerts` | 分页、排序、按状态/严重度/规则/来源/时间筛选 |
| GET | `/api/foreign/alerts/{id}` | 外网告警详情及安全快照 |
| GET | `/api/foreign/alert-rules` | 规则列表，默认展示启停状态 |
| POST | `/api/foreign/alert-rules` | 创建 disabled 规则 |
| PATCH | `/api/foreign/alert-rules/{id}` | 修改规则并递增版本 |
| POST | `/api/foreign/alerts/{id}/acknowledge` | 确认处置 |
| POST | `/api/foreign/alerts/{id}/resolve` | 解决处置 |
| POST | `/api/foreign/alerts/{id}/suppress` | 抑制告警 |
| POST | `/api/foreign/alerts/evaluate` | 受控手动评估或 dry-run |
| GET | `/api/foreign/alert-runs` | 运行审计 |
| GET | `/api/foreign/alerts/unread` | 外网独立未读计数 |

所有路由继承当前认证机制，但权限码必须独立，例如：

```text
foreign:alerts:read
foreign:alerts:rules:read
foreign:alerts:rules:write
foreign:alerts:enable
foreign:alerts:evaluate
foreign:alerts:acknowledge
foreign:alerts:resolve
foreign:alerts:suppress
```

规则启停、手动评估、处置和抑制均需要专门权限。手动评估默认关闭，管理员调用时必须限制最大文章/事件数量、记录 run 和操作者，并且不得触发采集、风险分析、事件聚合、国内告警、Dashboard、地图或热词。查询接口只能 join `foreign_*` 表，不能返回国内 `events`、`alert_records` 或 `opinions`。错误响应使用稳定错误码和脱敏摘要，不返回 SQL、堆栈、密钥或连接串。

## 12. 前端设计评审

后续在 `frontend/src/views/ForeignWorkspace.vue` 增加 `/foreign?tab=alerts` 设计入口；本阶段不修改该文件。页面只请求 `/api/foreign/alerts*`，不请求国内 Alerts、Dashboard 或 Events API。

建议页面分为：

- 外网告警默认关闭状态条，明确显示“规则未启用/外部通知未启用”。
- 未处理、已确认、已解决、已抑制和失败筛选。
- 告警标题、严重度、规则、风险分/等级、关联外网文章、关联外网事件、触发时间、去重键、冷却剩余时间、通知状态。
- 有权限用户的确认、解决、抑制和规则管理入口；无权限用户只读。
- loading、empty、processing、completed、failed、disabled 视觉状态分离；评估 run 失败必须显示失败时间和安全错误摘要，不得降级成空列表或普通 pending。

## 13. 权限、审计和任务边界

外网告警规则和动作必须进入独立资源命名空间。每次创建、修改、启停、评估、确认、解决、抑制、重试都应记录操作者、请求 ID、前后状态、规则版本、对象 ID、时间和原因。公共认证、RBAC middleware、审计基础设施可以复用，但 resource type、scope 和返回数据必须是 foreign。

外网告警服务 `ForeignAlertService` 的唯一输入是外网表；它不得调用国内 `AlertService`、`RiskEngine`、`EventAggregator`、`DashboardService` 或通知器的国内查询入口。外网任务独立于 collector scheduler、国内 alert scheduler 和外网风险/事件自动触发。首期只允许显式人工 `dry_run/evaluate`，不增加定时 job。

## 14. 国内/国外隔离验证清单

3C Implementation 和 Acceptance 必须在独立测试/预发布库完成以下断言：

1. `foreign_alert_rules`、`foreign_alerts`、`foreign_alert_runs` 的外键只指向对应 `foreign_*` 表和 `users`。
2. `foreign_alerts` 不写入 `alert_records`、`opinions`、`events` 或 `event_opinions`。
3. `/api/foreign/alerts*` 不返回国内告警、事件或舆情；`/api/alerts/*` 不返回外网告警。
4. 外网规则只读 `foreign_risk_terms` 和外网输入，不读国内 `keywords` 或 sensitive 词表。
5. 外网评估不修改 `Opinion`、国内风险结果、国内事件、告警、Dashboard、地图或热词数据。
6. candidate/rejected/archived 不会在无明确策略时触发正式告警；confirmed/monitoring 才可作为事件输入。
7. 未完成或失败风险分析不会触发依赖风险结果的告警。
8. disabled 规则和自动评估关闭时不创建告警。
9. 同一文章、事件和来源异常在冷却窗口内幂等去重；升级、恢复和失败均可追溯。
10. 国内 `alert_eval` 定时任务继续只访问国内表，且其行为和测试断言不变。
11. 外网通知使用独立 unread 和 scope；首期外部通知调用数为 0。

## 15. 后续实施阶段

### Phase Foreign-Source-3C-Implementation

**目标**：新建三张核心表和独立 `ForeignAlertService`，默认规则全部关闭，首期只生成站内外网告警记录。

**数据库**：新增 `foreign_alert_rules`、`foreign_alerts`、`foreign_alert_runs`；可按通知启用时间新增 `foreign_notification_records`。迁移从真实当前 head 开始，只在独立预发布库 upgrade/downgrade 往返验证。

**服务/API/UI**：新增 `ForeignAlertService`、`/api/foreign/alerts*` 和工作台 alerts tab；认证、RBAC、分页、审计可复用，查询和业务表不能复用国内告警边界。

**测试**：覆盖风险分/等级、confirmed 事件、候选抑制、关键词组合、来源异常输入、失败状态、幂等、冷却、权限、API 双向隔离、国内告警聚焦回归和前端构建。全部使用 local fixture/mock。

**回滚**：停止 foreign evaluate 入口和任务，禁用规则；预发布库按迁移逆序 downgrade。生产启用前不得对默认库执行 downgrade。国内代码、表和数据不应有变更。

**开启条件**：业务确认规则语义、来源异常是否读取 `collector_runs(scope='foreign')`、权限矩阵、快照保留和预发布迁移往返通过；三源仍 disabled 且 schedule disabled。

### Phase Foreign-Source-3C-Acceptance

**目标**：在独立库验证规则命中、风险/事件准入、去重、冷却、确认/解决/抑制和错误恢复。

**范围**：只使用 fixture；不访问 RSS、AI、代理或境外节点；不发送真实通知。验证 `foreign_alerts` 与国内 `alert_records` 的双向隔离和国内数据快照不变。

**回滚与开启条件**：清理仅由验收创建的临时告警/运行/动作数据，保留用户已有外网样本；接受所有隔离、权限、幂等、通知失败和迁移往返断言后，才可提交生产启用评审。生产启用仍需单独批准，不能由验收自动开启。

## 16. 已知风险与开放问题

1. 默认库仍为 `foreign_source_1`，没有 3A/3B 表，不能直接在其上实现或验证外网告警。
2. 设计要求列出的 `foreign_event_runs` 是事件聚合运行表，来源采集失败实际位于 `collector_runs(scope='foreign')`；来源异常告警的输入边界需业务确认。
3. `AlertRecord` 没有 scope 且硬关联国内表，复用会造成国内通知和统计污染。
4. 当前 `alert_eval_enabled=true` 的国内定时任务必须保持国内语义；实现阶段需增加防误调用测试。
5. 外网风险结果可能为 `unknown`、`pending` 或 `failed`，风险阈值规则需要明确空值和失败策略。
6. 事件确认后多文章告警是文章级还是事件级、事件恢复/升级条件、resolved/archived 重新激活规则需要业务确认。
7. 首期通知是否中英文双语、告警消息是否需要翻译和外部通知渠道的合规边界尚未确认。
8. 规则否定条件、复杂嵌套组合、来源恢复通知和升级通知不应在首期无评审扩展。
9. 只有少量人工外网样本，不能用于估计告警准确率、阈值、冷却时间或告警量。
10. 国内已有 5 条基线失败必须在外网告警实现前完成独立分类，不得借本阶段修改或掩盖。

## 17. Go/No-Go

| 问题 | 结论 |
|---|---|
| 当前是否可以直接实现外网告警 | NO-GO；默认库未部署 3A/3B，且外网表/服务/API 不存在 |
| 首期推荐规则 | 已完成风险结果阈值/等级/类别；confirmed/monitoring 事件热度或文章数；受控关键词组合；来源异常待确认 |
| candidate 是否触发 | NO-GO；只进入候选或待复核统计 |
| 是否必须确认事件后触发事件告警 | 是；首期只允许 `confirmed` 或 `monitoring` |
| 是否默认自动评估 | 否；只允许有权限人工 dry-run/evaluate |
| 是否默认发送外部通知 | 否 |
| 首期是否只做站内告警 | 是 |
| 是否需要 `foreign_alert_rules` | 是 |
| 是否需要 `foreign_alerts` | 是 |
| 是否需要 `foreign_alert_runs` | 是 |
| 是否可复用通知底层能力 | 可评估，但必须显式传入 foreign scope；不能复用国内查询和 unread |
| 当前是否可进入 3C Implementation | CONDITIONAL GO；完成开放问题确认和独立预发布迁移设计后 |

进入实现前必须确认：外网规则条件和阈值、风险失败/unknown 策略、来源异常日志输入、事件级/文章级告警粒度、去重和冷却、恢复和升级、权限码、快照留存期限、通知渠道及双语要求。未完成这些确认，不得创建生产规则、开启自动评估或发送通知。

## 18. 本阶段最终确认

- 未修改代码：是。
- 未修改配置：是。
- 未修改数据库结构：是。
- 未修改数据库数据：是。
- 未启用外网源：是；三个来源均 `enabled=false`。
- 未启用外网自动调度：是；三个来源均 `schedule_enabled=false`，无运行中 foreign collector。
- 未发送真实告警：是。
- 未调用外部 AI：是。
- 未调用真实 RSS：是。
- 未使用代理或境外采集节点：是；五个代理环境变量均未设置。
- 未删除用户已有 `foreign_opinions` 或采集日志：是。
- 只新增本审计设计报告：是。
