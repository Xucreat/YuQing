# Phase8 实施前审计报告

> 审计范围：Phase 8-0 数据源可靠性治理、Phase 8-A 事件态势感知第一阶段  
> 审计方式：当前工作区代码、Alembic 迁移、前端调用、测试和历史提交/设计文档只读核对。  
> 本次动作：仅生成本报告；未修改应用代码、未新增数据库迁移、未执行数据变更。

## 1. 审计结论

当前系统不需要从零建设 Phase 8。已有若干能力在此前 Phase/提交中已经实现，但能力边界与本次目标不同：

| 本次要求 | 当前状态 | 审计判断 |
|---|---|---|
| 采集任务成功/失败记录 | 已实现 | `CollectorRun` 已是持久化运行事实，不重复建设 |
| 连续失败、连续空抓取统计 | 已实现但为只读质量分析 | `/admin/data-sources/quality` 和 `Sources.vue` 已展示；尚未形成源级健康状态 |
| 数据源测试采集 | 已实现 | `POST /admin/data-sources/test` 已存在，管理员权限；不重复新增同义接口 |
| `DataSource.last_run_at/last_status/last_error` | 字段已存在但未形成可靠写回链路 | 属于历史 Phase 3 运行态缓存设计，当前不能作为健康事实 |
| Token 失效标准化 | 未实现 | 八爪鱼异常以通用 `RuntimeError`/HTTP 文本进入 `error_msg` |
| `health_status`、最近成功/失败、连续失败摘要 | 未实现 | 本次实施需要新增最小状态计算/展示；是否落库需另行批准 |
| Event、EventOpinion、热度、趋势 | 已实现 | p19/p20 及事件中心 Phase 已落地，不重建核心模型 |
| 事件态势只读接口 | 未实现 | 没有 `/events/{id}/situation`，也没有对应 schema/service |
| EventRiskShadow 影子计算 | 未实现 | 现有 `EventRiskService` 是最高单条内容风险，不能冒充影子分 |
| 传播语义修正 | 未实现 | 页面仍显示“传播溯源/传播链/深度”，代码关系是时间和来源推断 |
| 事件详情画像 | 部分已实现 | 已展示风险、热度、趋势、来源内容和处置记录；缺少态势分布、风险因素、数据充分性 |

因此，后续编码前应坚持增量范围：复用已存在的采集质量能力，补齐标准化健康摘要；新增只读事件态势和影子评分，绝不替换现有告警或重构 `Opinion/Event`。

## 2. 工作区与历史实施状态

当前工作区本身存在大量用户/历史生成的未提交改动，包括采集器、事件聚合、前端页面和静态构建产物。本报告没有修改这些文件，后续实施必须以当前工作区内容为准，不能用旧提交覆盖现有改动。

历史提交 `08cb1609` 已包含“微博八爪鱼/博查/Grok 数据源接入与事件中心 Phase8 治理”；`15b22fec` 已包含风险模型 V2、事件中心幂等收口与告警处置；`f8f38ad5` 已包含事件中心和指挥大屏改造。历史文档中存在与当前代码不一致的旧描述，不能作为当前结构依据。

明确的过往实现/舍弃情况：

1. 早期采集运行状态曾使用模块级内存变量，后来通过 `527069a609a0_p0_collector_runs.py` 落地为 `collector_runs`；因此不能再次设计“内存运行状态”。
2. `DataSource` 的 `last_run_at/last_status/last_error` 在 `0004_phase3_datasource_region_parent.py` 中已建，但采集服务当前没有稳定写回这些缓存字段；管理接口实际还会从最新 `CollectorRun` 推导 `latest_run_status/latest_run_at`。
3. `p16_weibo_comment_run_stats.py` 已为 `CollectorRun` 增加 `comments_seen/comments_skipped`，但这不是评论舆情入库；采集服务仍明确跳过 `weibo_comment`。
4. p19/p20 已将事件地域、主题、状态、热度、趋势加入 `events`；旧文档中“Event 没有 status/heat/trend”的描述已经过时。
5. p7 已为 `event_opinions(event_id, opinion_id)` 增加唯一约束；旧文档中“无唯一约束”的描述已经过时。
6. `admin_data_sources.py` 过去只展示最近运行摘要，后续提交又增加了质量接口和来源页质量列；本次不应重复做一个新的“质量统计页面”。
7. 传播树此前被文档描述为跨来源传播拓扑，但当前实现依据来源上一次节点和总体时间顺序建立父节点，不能视为平台真实转发链。

## 3. 数据模型审计

### 3.1 DataSource

当前字段包括 `key/name/type/class_path/enabled/priority/scope_region_codes/config_json`，以及 `last_run_at/last_status/last_error` 运行态缓存。当前没有：

- `health_status`；
- `last_success_at/last_failure_at`；
- `consecutive_failures`；
- `error_code` 或 Token/认证错误分类。

外键关系方面，`DataSource` 不直接外键到 `CollectorRun`，运行记录通过 `collector_name == DataSource.name` 关联。这种关联已被管理 API 使用，但名称可变性和同名来源风险需要保留在后续实施风险中。

### 3.2 CollectorRun

`CollectorRun` 已持久化每次采集的 `start_time/end_time`、批次、触发方式、原始数量、上游数量、创建/重复/失败/分析数量、确认状态、评论识别/跳过、准入过滤、`status` 和 `error_msg`。它能保存单次运行事实，不能直接表示数据源长期健康。

当前状态来源包括 `running/success/partial/warning/failed/error` 等运行结果；错误原因仍是自由文本，没有稳定错误码。任务超时回收会将运行置为失败并写入回收说明，这部分应保留。

### 3.3 Opinion、Event、EventOpinion、AlertRecord

- `Opinion` 是内容级统一实体，包含来源、正文、地域、内容级风险、情感、关键词、微博 `source_type/author/engagement/external_id` 等；不应在本阶段塞入事件态势快照。
- `EventOpinion` 是事件与内容的多对多桥接，当前有外键和唯一约束，适合作为事件态势计算的输入。
- `Event` 当前已有标题、描述、关键词、风险等级/分数、地域、状态、主题、热度、趋势、成员数量和首末时间，适合作为核心对象；缺少只读风险因素、数据窗口和数据充分性输出。
- `AlertRecord` 已有单条 Opinion/事件引用、规则、触发原因、处理状态、处理人、处理时间和备注。告警评估初始按 Opinion 产生，之后由 `sync_alert_events` 按 `opinion_id` 关联事件；本阶段禁止替换这个生产告警逻辑。

### 3.4 PropagationNode

当前字段有 `event_id/opinion_id/parent_id/source/source_url/title/publish_time/risk_score/sentiment/keywords/depth`。没有平台转发 ID、回复 ID、账号 ID、关系类型或关系证据。模型可保留，但前端语义必须从“真实传播链”调整为“来源与时间态势”。

## 4. 当前采集链路审计

```text
DataSource 表/默认注册表
    ↓ resolve_collectors
CollectorService.collect_and_analyze
    ↓ 创建 CollectorRun
collector.fetch → 准入/去重/规则分析 → Opinion
    ↓
EventAggregator / AlertService / 前端展示
```

### 已实现

- 数据源表驱动装配，并在表不可用时有默认源回退。
- 单一采集批次可通过 `batch_id`/`trigger_type` 聚合。
- 每个来源的运行事实落入 `CollectorRun`，采集器异常不会静默转成 0 条。
- 八爪鱼消费在入库成功后才确认导出，确认失败会影响运行状态并保留 `ack_status/error_msg`。
- 调度器有 PostgreSQL advisory lock 单实例保护；定时采集和告警评估独立调度。
- `/admin/data-sources/quality` 已计算最近运行、成功率、非零/零抓取率、连续失败次数、连续空抓取次数和 `empty_fetch_risk`；来源页已调用该接口展示“采集质量”。
- `/admin/data-sources/test` 已提供管理员受保护的一次真实采集测试，不落库。

### 未实现或不足

- `DataSource.last_status/last_run_at/last_error` 没有在采集任务完成时统一写回，字段是历史缓存而非当前健康摘要。
- 没有 `TOKEN_EXPIRED/AUTH_FAILED/HTTP_ERROR/TIMEOUT/PARSE_ERROR/NO_DATA/UNKNOWN` 标准错误枚举。
- 八爪鱼 `_get_token`、`_fetch_not_exported` 和确认导出函数将不同认证/HTTP/响应结构错误统一抛为 `RuntimeError`，CollectorService 最终只写 `TypeName: message`。
- 质量接口按 `fetched_raw == 0` 统计“空抓取”，不能区分真实无数据、全部被准入过滤、重复数据、解析失败和认证失败；也没有源类型无数据窗口。
- 质量接口的连续失败和空抓取是请求时重算的只读指标，不会驱动健康状态、低频探测、管理员确认或提醒。
- 失败时没有可靠的“最近成功/最近失败/连续失败摘要”源级字段，也没有健康状态优先级。

### 八爪鱼 Token 失效判断

当前能检测到 HTTP 非 200、缺少凭证、Token 接口缺失 `access_token`、拉取数据非 200、响应结构异常，但只能以异常文本识别。代码没有检查 401/403 或上游错误码并映射为 `TOKEN_EXPIRED`，因此管理员看到的是采集运行失败文本，而不是可行动的认证状态。

## 5. 当前事件链路审计

```text
Opinion
  ↓ EventAggregator / EventOpinion
Event
  ↓ AlertService.sync_alert_events（事后关联）
AlertRecord
```

### 风险

`EventRiskService.score_expression()` 在存在成员时取关联 Opinion 风险分的最大值，没有内容数量、增长速度、地域相关性或事件类型的事件级组合。事件列表、事件详情和风险筛选均使用该最高值或其等级映射。

因此本次可以增加 `EventRiskShadow` 纯计算结果，但必须作为非持久化/只读影子结果，不能替换 `Event.risk_score`、`EventRiskService.score_expression()` 或告警阈值。

### 热度/趋势

`EventHeatService` 已实现：成员数量封顶贡献、近 24 小时新增、前 7 日数量对比、互动 JSON 汇总，输出 `heat_score/trend/reason`；并由事件聚合/刷新路径写回 Event 的 `heat_score/trend`。它是已存在的轻量热度能力，不应重复建设第二套热度服务。

不足在于：`reason` 没有稳定作为事件详情 API 返回，指标没有历史快照，互动总量不是增量，且没有数据源异常/样本不足标记。

### 事件详情依赖

当前 `GET /events/{event_id}` 返回事件基础字段、描述、关键词、关联 Opinion 列表和 EventAction 操作记录；前端 `EventDetail.vue` 已展示标题、首末时间、风险、热度、趋势、主题、处置状态、内容列表和操作记录。当前没有：

- `/events/{id}/situation`；
- `risk_factors`；
- `source_distribution/daily_counts/keyword_counts` 事件级聚合返回；
- `data_window/data_sufficiency/stale_sources`；
- 影子风险分和因素明细。

前端已有区域、风险、热度和趋势展示；应确认当前工作区实际版本，不以历史截图或静态旧构建产物判断功能是否存在。

## 6. 既有能力与本次实施范围对照

### 本次必须实施

1. 在后端建立统一错误分类函数/异常映射，至少覆盖 `TOKEN_EXPIRED/AUTH_FAILED/HTTP_ERROR/TIMEOUT/PARSE_ERROR/NO_DATA/UNKNOWN`，错误分类不能由前端猜测。
2. 在不破坏 `CollectorRun` 的前提下，形成源级健康摘要；优先复用现有 `DataSource` 缓存字段，只有当前结构无法满足时才提出最小 `health_status` 等字段变更。
3. 在 `/admin/data-sources` 响应和 `Sources.vue` 中展示健康状态、最近成功/失败、连续失败和错误分类；已有质量列和质量接口应复用而非替换。
4. 新增只读 `GET /events/{id}/situation`，由关联 `EventOpinion + Opinion` 计算风险解释、热度/趋势、来源分布、日计数、关键词、数据窗口和数据充分性。
5. 新增非生产用途事件风险影子计算，不回写 Event、不替换告警逻辑。
6. 将传播页面的“传播溯源/传播链/传播深度”语义收口为“来源与时间态势”，明确当前关系基于来源/时间推断，不代表真实转发关系。

### 本次明确不实施

- 不接入微博评论、不改变 `comments_skipped` 策略。
- 不新增 Content/Post/Comment/Account/Relation 等核心模型。
- 不新增 ES、Kafka、Redis、微服务或图数据库。
- 不修改生产 `Event.risk_score`、Opinion 风险分和现有 AlertService 触发逻辑。
- 不新增官方回应、交办任务、复盘模型；这些属于后续 Phase 8-D。
- 不清理、重聚合或回填历史生产数据。
- 不删除 `PropagationNode`、旧传播接口或已有运行日志。

## 7. 实施前阻断项与建议

当前存在一个需要在编码前确认的数据库边界：用户要求“不新增数据库迁移”，但完整的源级健康摘要需要 `health_status/last_success_at/last_failure_at/consecutive_failures/error_code` 等持久化字段。若严格禁止迁移，第一阶段只能采用以下兼容方案：

- `health_status`、连续失败和最近成功/失败由服务层根据 `CollectorRun` 实时计算并在 API 返回；
- `DataSource.last_*` 暂不作为可信写回字段；
- 标准错误码暂存于运行结果内存/响应或从 `error_msg` 映射，不能作为长期审计字段；
- 事件态势接口全部只读计算，不写 Event。

若希望健康状态在重启后保留，必须另行批准一个最小迁移。没有该批准，本次不应擅自新增列。

另一个前置边界是 Token 修复：本次可以实现错误分类和管理员可见性，但不应修改或写入真实八爪鱼凭证，也不应把测试采集自动变成生产消费确认。

## 8. 审计结论

当前架构适合继续增量实施 Phase 8-0 + Phase 8-A 第一阶段，但不能按原始方案“从零新增质量接口、质量统计和事件基础字段”。这些能力中，质量统计、测试采集、事件热度/趋势、事件处置状态、采集运行日志和事件关联已经存在；真正缺失的是标准化错误语义、源级健康摘要、只读事件态势接口、影子风险计算和传播语义修正。

在完成本报告并确认“是否允许最小数据库迁移”后，才进入编码。当前审计阶段不应继续修改代码。
