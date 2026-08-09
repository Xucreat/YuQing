# Phase Foreign-Source-3B-Implementation 实施报告

## 1. 结论

本阶段已在独立测试库 `opinion_test` 完成外网事件候选、相似度确认和人工确认链路实现。默认业务库仍为 `opinion_db`，未在默认库执行迁移、写入或 downgrade。

最终结论：外网事件隔离实现通过；候选生成和人工确认链路通过新增外网测试；生产启用仍为 NO-GO，等待正式预发布迁移、人工标注样本和国内基线问题单独收口。

明确状态：

- 未修改国内事件服务、国内事件表、国内事件 API、国内 Events 页面或国内测试断言。
- 未写入国内 `events`、`event_opinions` 或 `opinions`。
- 未写入默认生产库；默认库已有的 3 条 `foreign_opinions` 和 3 条 `scope=foreign` 采集日志均保留。
- 未启用 Fox News、The Guardian、纽约时报中文网；三个固定源在默认库均为 `enabled=false`、`schedule_enabled=false`。
- 未启用自动事件聚合、自动确认、外网告警、外网 Dashboard、外网地图或外网热词。
- 未触发真实 RSS、外部 AI、代理或境外采集节点。
- 候选重建默认为 Dry-Run；只有受权限控制的人工/API 操作可以将候选确认成正式外网事件。

## 2. 实际改动文件

本阶段新增或修改的 3B 文件如下。工作区中 Phase 1、1.1、2、3A 以及其他历史任务产生的修改和未跟踪文件全部保留，未执行 reset、checkout 或清理。

- `backend/alembic/versions/foreign_source_3b.py`
- `backend/app/api/__init__.py`
- `backend/app/api/foreign_events.py`
- `backend/app/models/__init__.py`
- `backend/app/models/foreign_event.py`
- `backend/app/models/foreign_event_candidate.py`
- `backend/app/models/foreign_event_opinion.py`
- `backend/app/models/foreign_event_run.py`
- `backend/app/models/foreign_event_action.py`
- `backend/app/services/foreign_event_service.py`
- `backend/tests/test_foreign_source_3b.py`
- `backend/tests/test_foreign_source_3b_ui.py`
- `frontend/src/views/ForeignWorkspace.vue`

本阶段没有改动国内 `EventAggregator`、`Event`、`EventOpinion`、国内事件 API 或国内 Events 页面。

## 3. 数据库迁移

迁移文件为 `foreign_source_3b`，父版本为 `foreign_source_3a`，当前测试库 head 为 `foreign_source_3b`。

新增表：

### `foreign_event_candidates`

保存待人工审核的候选事件和可解释证据：

- `id`, `candidate_key`
- `title`, `summary`, `language`, `candidate_status`
- `confidence`, `event_type`, `risk_level_snapshot`, `heat_score_snapshot`
- `first_seen_at`, `last_seen_at`, `opinion_count`, `source_count`
- `aggregation_version`, `evidence_json`
- `representative_opinion_id`, `reviewed_by`, `reviewed_at`, `rejection_reason`
- `created_at`, `updated_at`

`candidate_key` 唯一；状态约束为 `candidate/rejected/converted/superseded`。候选证据 JSON 保存公式、阈值、相似度方法、候选原因、监测词忽略规则、文章 ID 和逐对评分。

### `foreign_events`

保存人工确认后的正式外网事件：

- `id`, `title`, `summary`, `language`, `event_status`, `event_type`
- `risk_level`, `heat_score`, `first_seen_at`, `last_seen_at`
- `opinion_count`, `source_count`, `confidence`, `aggregation_version`
- `origin_candidate_id`, `canonical_event_id`
- `created_at`, `updated_at`, `confirmed_by`, `confirmed_at`
- `resolved_at`, `archived_at`

正式事件状态为 `confirmed/monitoring/resolved/archived`。合并时源事件保留为 archived，并通过 `canonical_event_id` 指向目标事件。

### `foreign_event_opinions`

仅关联外网事件和外网文章：

- `id`, `foreign_event_id`, `foreign_opinion_id`
- `relation_type`, `similarity_score`, `matched_terms`, `evidence_json`
- `created_at`, `created_by`

`(foreign_event_id, foreign_opinion_id)` 唯一。外键只指向 `foreign_events`、`foreign_opinions` 和用户审计实体，不指向国内 `events` 或 `event_opinions`。

### `foreign_event_runs`

保存候选重建运行：

- 固定 `scope='foreign'`
- `trigger_type`, `aggregation_version`
- `input_count`, `deduplicated_count`, `candidate_count`, `linked_count`
- `created_event_count`, `updated_event_count`, `rejected_count`, `failed_count`
- `status`, `dry_run`, `error_message`
- `started_at`, `finished_at`, `created_by`, `created_at`

### `foreign_event_actions`

保存确认、拒绝、合并、拆分和状态变更审计：

- `action_type`
- `candidate_id`, `foreign_event_id`, `target_event_id`
- `actor_user_id`, `old_status`, `new_status`
- `reason`, `request_id`, `payload_json`, `created_at`

`request_id` 唯一，用于人工操作幂等和重试追踪。

### Upgrade/Downgrade 验证

在 `opinion_test` 执行并验证：

1. `alembic current`：`foreign_source_3b (head)`。
2. 保存国内和 3A 外网计数。
3. `alembic downgrade foreign_source_3a`：5 张 3B 表消失；`opinions=2`、`events=0`、`event_opinions=0`、`foreign_keywords=3`、`foreign_opinions=16` 和 3A 风险表数据保持不变。
4. `alembic upgrade foreign_source_3b`：5 张表恢复，head 正确。
5. 使用 SQLAlchemy inspector 验证外键和索引：`foreign_event_opinions` 只引用 `foreign_events`/`foreign_opinions`；`foreign_events` 不引用国内 `events`；候选、事件、运行和审计索引均存在。
6. 未在默认 `opinion_db` 执行 upgrade 或 downgrade。

## 4. 候选算法

服务边界为 `ForeignEventService`，输入只来自 `ForeignOpinion`，可读取 `foreign_risk_results` 作为风险快照，但风险结果不是事件准入的唯一条件。

处理顺序：

```text
foreign_opinions
  -> URL/content_hash canonical 去重
  -> language 分区
  -> 72 小时时间窗口
  -> 标题、摘要/正文和标题锚点词 lexical similarity
  -> candidate
  -> 人工确认
  -> foreign_events + foreign_event_opinions
```

评分公式：

```text
pair_score =
    0.35 * title_similarity
  + 0.25 * content_similarity
  + 0.25 * anchor_overlap
  + 0.15 * time_proximity
```

实现使用轻量 lexical Jaccard，不引入重量级依赖、不调用外部 AI 或在线向量服务。`0.55` 是候选最低阈值，`0.72` 是高置信度参考阈值；首期两者都只生成候选，不自动确认。不同来源最多提供小幅 source diversity bonus，不能替代文本相似度。

候选证据保存：

- `similarity_score`
- `similarity_method=lexical_jaccard`
- `similarity_threshold=0.55`
- `aggregation_version=foreign-event-v1`
- 实际共享标题词 `matched_terms`
- `candidate_reason`
- 标题、内容、锚点和时间逐项分数

`中国`、`China`、`Chinese` 仅为监测词，在事件评分中被忽略，不能因为监测词相同而直接聚合。

## 5. 语言和重复隔离

- 英文只和英文进入自动候选召回。
- 中文只和中文进入自动候选召回。
- 中英文不会自动聚合。
- `mixed` 和 `unknown` 不进入纯中英文组，只能形成低置信度候选或等待人工审核。
- 相同 URL 或相同 `content_hash` 只保留 canonical 文章参与事件候选。
- 原始 `foreign_opinions` 不删除；来源删除后，事件仍通过事件快照和关联文章的 `source_name_snapshot` 展示。

## 6. 状态和人工确认

候选状态：

```text
candidate -> converted
candidate -> rejected
candidate -> superseded
```

正式事件状态：

```text
confirmed -> monitoring -> resolved -> archived
archived -> monitoring      # 受权限控制的人工重新激活
```

候选默认是 `candidate`，不会自动成为 `confirmed`。确认、拒绝、合并、拆分和状态变更均写入 `foreign_event_actions`，并支持 `request_id` 幂等。合并只允许同语言事件，保留源事件和目标事件关系；拆分生成新外网事件并保留原事件 ID、新事件 ID、迁移文章 ID 和操作原因。

## 7. API 和前端

新增独立 API 命名空间：

- `GET /api/foreign/events`
- `GET /api/foreign/events/{event_id}`
- `GET /api/foreign/events/{event_id}/opinions`
- `GET /api/foreign/events/candidates`
- `POST /api/foreign/events/candidates/{candidate_id}/confirm`
- `POST /api/foreign/events/candidates/{candidate_id}/reject`
- `POST /api/foreign/events/{event_id}/merge`
- `POST /api/foreign/events/{event_id}/split`
- `POST /api/foreign/events/{event_id}/status`
- `POST /api/foreign/events/rebuild`
- `GET /api/foreign/event-runs`
- `GET /api/foreign/event-actions`

查询接口只查询 `foreign_*` 表。重建有数量上限，默认 `dry_run=true`，并受外网事件重建权限控制。API 错误不会返回数据库堆栈或敏感配置。

前端入口为 `/foreign?tab=events`，保留原有 `/foreign` 工作台。事件页包含候选和正式事件区域，展示标题、语言、状态、风险快照、文章数、来源数、置信度和详情；详情只调用外网事件接口并展示关联外网文章。国内 `/events` 路由和 Events 页面未改动。

## 8. 权限和审计

迁移新增外网事件权限：

- `foreign:events:read`
- `foreign:events:candidates:read`
- `foreign:events:confirm`
- `foreign:events:merge`
- `foreign:events:split`
- `foreign:events:status`
- `foreign:events:rebuild`

权限写入采用幂等 INSERT；管理员角色在测试迁移中获得外网事件权限。所有 API 经过当前认证和权限依赖，人工事件动作同时写入应用审计和 `foreign_event_actions`。外网事件运行固定 `scope='foreign'`，不复用国内 `collector_runs` 或国内事件操作日志。

## 9. 隔离验收

新增 3B 测试覆盖并通过：

- 同语言文章可生成候选。
- 中英文文章不会自动聚合。
- URL/content hash 去重降级。
- 候选生成幂等。
- 候选默认不是 confirmed。
- 人工确认后只创建 `foreign_events` 和 `foreign_event_opinions`。
- 国内 `opinions/events/event_opinions` 数量不变。
- 国内 `/api/events` 不返回外网事件。
- 外网事件 API 只返回外网事件和外网文章。
- 事件运行固定 `scope='foreign'`，人工动作可审计。
- UI 入口和 API 静态隔离，不调用国内事件 API。

最终测试库快照：

- `opinions=2`
- `events=0`
- `event_opinions=0`
- `foreign_keywords=3`
- `foreign_opinions=16`
- `foreign_event_candidates=0`
- `foreign_events=0`
- `foreign_event_opinions=0`
- `foreign_event_runs=0`
- `foreign_event_actions=0`

最后四项为测试 fixture 清理后的空值，不代表删除了用户样本；用户样本在 `foreign_opinions` 中保留。

## 10. 测试命令和结果

测试均使用本地 PostgreSQL `opinion_test`，连接串带 `connect_timeout=3`，未访问真实 RSS、AI 或境外节点。

```powershell
$env:DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@localhost:5433/opinion_test?connect_timeout=3'
$env:DB_IDENTITY_CHECK='off'
pytest tests/test_foreign_source_3b.py tests/test_foreign_source_3b_ui.py -q
```

结果：`5 passed`。

```powershell
pytest tests/test_foreign_source_3a.py tests/test_foreign_source_phase1_1.py tests/test_foreign_source_phase1.py -q
```

结果：`26 passed`。

```powershell
python -m compileall backend/app backend/tests
```

结果：通过。

```powershell
cd frontend
npm run build
```

结果：通过；只有既有 Rollup 注释和动态/静态路由分包提示。

国内聚焦回归执行：

```powershell
pytest tests/test_events.py tests/test_risk_engine.py tests/test_alert_operation.py tests/test_dashboard.py -q
```

结果：`54 passed, 5 failed`。5 个失败均为已存在的国内基线问题，不是本阶段外网实现引入：

- `Event` 模型当前已有 `status` 字段，但旧测试仍断言不存在。
- 国内事件标题当前按新叙事格式生成，但旧测试仍期待旧标题。
- 国内事件聚合接口当前异步返回 `task_id`，旧测试仍期待同步聚合结果。
- 国内聚合分页测试依赖同步任务完成，和当前异步契约不一致。
- 告警测试库缺少 `viewer` 角色 fixture。

这些失败与 Phase 1.1/3A 报告中记录的国内历史模型、API 和 fixture 基线问题一致。本阶段没有修改国内实现、测试断言或生产数据，故没有为了测试变绿而掩盖它们。

## 11. 生产保护和未解决风险

默认库只读核验结果：

- database: `opinion_db`
- Alembic: `foreign_source_1 (head)`
- Fox News: disabled / schedule disabled
- The Guardian: disabled / schedule disabled
- 纽约时报中文网: disabled / schedule disabled
- 已有 `foreign_opinions=3` 和 `scope=foreign` 采集日志 `3` 条，均为用户授权人工灰度样本

当前环境 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`FOREIGN_HTTP_PROXY`、`FOREIGN_HTTPS_PROXY` 均未设置。没有部署或连接境外节点。未发现数据库任务/作业表，也没有运行中的外网 scheduler 进程。

未解决风险：

1. 生产默认库仍停留在 `foreign_source_1`，不能直接执行 3B 迁移。
2. 国内基线测试仍有历史模型/API/fixture 失败，正式上线前应单独建立国内回归修复任务。
3. 当前事件候选是轻量 lexical 规则，尚未经过足够人工标注样本校准。
4. 事件合并仅允许同语言自动候选/人工操作；跨语言合并策略需要业务确认，当前禁止自动跨语言聚合。
5. `foreign_event_actions` 是当前事件链路审计表，后续需纳入统一审计检索和保留策略。
6. 外网事件仍未接入告警、Dashboard、地图和热词，后续阶段必须继续保持表、API、任务和权限隔离。

## 12. 下一阶段前置条件

进入外网告警设计评审前必须满足：

1. 在独立预发布库完成 `foreign_source_3a -> foreign_source_3b` upgrade/downgrade 验证。
2. 完成国内基线失败项的独立修复或明确兼容测试，不修改外网链路来绕过。
3. 使用多个来源、多个时间窗口和人工标注样本校准候选阈值。
4. 明确是否允许人工确认后的外网事件触发任何外网告警；默认仍关闭。
5. 设计独立的 `foreign_alert_rules`、`foreign_alerts` 和通知审计表，不复用国内告警查询。
6. 继续确认三个外网源 `enabled=false`、`schedule_enabled=false`，由正式变更窗口单独授权启用。

## 13. Phase 3B 验收判断

Phase Foreign-Source-3B-Implementation：**条件通过（实现与隔离通过，生产启用不通过）**。

实现层面满足：独立表、独立服务、同语言候选、相似度证据、人工确认、合并/拆分/归档审计、双向 API 隔离和前端 `/foreign?tab=events` 入口。

生产层面保持 NO-GO：不迁移默认库、不启用来源、不启用自动调度、不启用自动确认、不接入告警/Dashboard/地图/热词；待上述前置条件完成后再进行正式变更评审。
