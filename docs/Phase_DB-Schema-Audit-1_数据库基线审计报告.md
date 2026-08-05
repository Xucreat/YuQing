# Phase DB-Schema-Audit-1 数据库基线审计报告

审计结论：当前目标数据库的业务表和字段与 ORM 模型基本对齐，MediaCrawler 微博接入所需的字段已经存在；Alembic revision 图本身是完整的单链、单 head，数据库当前版本为 `p12_datasource_schedule`。但是，数据库对象级结构与当前 ORM metadata 并非完全一致，`alembic check` 只读检查失败，发现了索引、唯一约束、外键选项、列可空性和列注释漂移。因此当前 Schema 可用于现有业务字段访问，但不能认定为“完全干净、可直接作为无漂移 baseline”的状态。

## 1. 审计范围

本次仅进行只读审计，范围包括：

- `backend/alembic/env.py`、`backend/alembic/versions/` 下全部 migration 文件；
- `backend/app/models/` 下已注册 SQLAlchemy ORM 模型；
- `backend/Dockerfile`、根目录 `docker-compose.yml`、`backend/scripts/init_db.py` 等部署与初始化流程；
- PostgreSQL `public` schema 的 `information_schema`、系统目录和 `alembic_version` 查询；
- 只读执行 `alembic current`、`alembic heads`、`alembic history`、`alembic branches`、`alembic check`。

数据库身份核验结果：`DATABASE_URL` 解析为 `postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db`；数据库 `opinion_db`，PostgreSQL system identifier 为 `7663057120701798896`，身份门禁输出 `DATABASE IDENTITY: VERIFIED`，当时 `opinions` 行数为 1051。未执行任何 `upgrade`、`downgrade`、`stamp`、DDL 或业务写入。

## 2. 当前Alembic状态

### 2.1 current / heads

实际命令输出：

```text
alembic current
p12_datasource_schedule (head)

alembic heads
p12_datasource_schedule (head)

alembic branches
无输出
```

`backend/alembic/env.py` 的 `run_migrations_online()` 通过 `settings.database_url` 建立连接，并调用 `assert_identity_for_migration()`；`target_metadata` 为 `Base.metadata`。当前数据库 `alembic_version` 表实际只有一行：`p12_datasource_schedule`。

### 2.2 migration统计

- 有 revision 定义的 migration 文件：40 个；另有非 revision 的 `__init__.py`；
- 根节点：`0001_initial`；
- head：`p12_datasource_schedule`；
- branch 数量：0；
- branch point：0；
- 断链：未发现；
- 从根到 head 的可达 revision：40 个，全部可达。

### 2.3 完整migration时间线

以下为 `alembic history --verbose` 和文件中 `revision/down_revision` 的只读核对结果，箭头左侧为当前节点，右侧为父节点：

1. `0001_initial` <- `None`，`backend/alembic/versions/0001_initial.py`
2. `0002_add_opinion_analysis_status` <- `0001_initial`，`backend/alembic/versions/0002_add_opinion_analysis_status.py`
3. `0003_add_analysis_suggestion` <- `0002_add_opinion_analysis_status`，`backend/alembic/versions/0003_add_analysis_suggestion.py`
4. `527069a609a0` <- `0003_add_analysis_suggestion`，`backend/alembic/versions/527069a609a0_p0_collector_runs.py`
5. `c0769f234982` <- `527069a609a0`，`backend/alembic/versions/c0769f234982_p1_fulltext_keywords_hebei_sources.py`
6. `p2rbac01` <- `c0769f234982`，`backend/alembic/versions/p2_rbac.py`
7. `phase3ds01` <- `p2rbac01`，`backend/alembic/versions/0004_phase3_datasource_region_parent.py`
8. `ai0005` <- `phase3ds01`，`backend/alembic/versions/0005_ai_report.py`
9. `kwlex01` <- `ai0005`，`backend/alembic/versions/kwlex01.py`
10. `rbac10001` <- `kwlex01`，`backend/alembic/versions/rbac10001.py`
11. `collrunbatch001` <- `rbac10001`，`backend/alembic/versions/collrunbatch001_collection_log_batch.py`
12. `p6urluniq01` <- `collrunbatch001`，`backend/alembic/versions/p6_opinions_url_unique.py`
13. `p7evtuniq01` <- `p6urluniq01`，`backend/alembic/versions/p7_event_opinions_unique.py`
14. `p8phase2a01` <- `p7evtuniq01`，`backend/alembic/versions/p8_phase2a_risk_engine.py`
15. `p9phase2a101` <- `p8phase2a01`，`backend/alembic/versions/p9_phase2a1_risk_explainability.py`
16. `p10_phase2b1` <- `p9phase2a101`，`backend/alembic/versions/p10_phase2b1_alert_operation.py`
17. `p11_phase2b2` <- `p10_phase2b1`，`backend/alembic/versions/p11_phase2b2_risk_category.py`
18. `p12_rbac_roleperms` <- `p11_phase2b2`，`backend/alembic/versions/p12_rbac_roleperms.py`
19. `p13_weibo_fields` <- `p12_rbac_roleperms`，`backend/alembic/versions/p13_weibo_fields.py`
20. `p14_bocha_leads` <- `p13_weibo_fields`，`backend/alembic/versions/p14_bocha_leads.py`
21. `p15_bocha_search_sessions` <- `p14_bocha_leads`，`backend/alembic/versions/p15_bocha_search_sessions.py`
22. `p16_weibo_comment_run_stats` <- `p15_bocha_search_sessions`，`backend/alembic/versions/p16_weibo_comment_run_stats.py`
23. `p17_opinion_admission_fields` <- `p16_weibo_comment_run_stats`，`backend/alembic/versions/p17_opinion_admission_fields.py`
24. `p18_admission_filtered` <- `p17_opinion_admission_fields`，`backend/alembic/versions/p18_collector_run_admission_filtered.py`
25. `p19_event_model_enhancement` <- `p18_admission_filtered`，`backend/alembic/versions/p19_event_model_enhancement.py`
26. `p20_event_heat_trend` <- `p19_event_model_enhancement`，`backend/alembic/versions/p20_event_heat_trend.py`
27. `p21_weibo_export_audit` <- `p20_event_heat_trend`，`backend/alembic/versions/p21_weibo_export_audit.py`
28. `p22_event_actions` <- `p21_weibo_export_audit`，`backend/alembic/versions/p22_event_actions.py`
29. `p23_collector_run_duplicate` <- `p22_event_actions`，`backend/alembic/versions/p23_collector_run_duplicate.py`
30. `p24_bazhu_dynamic_source` <- `p23_collector_run_duplicate`，`backend/alembic/versions/p24_bazhou_dynamic_source.py`
31. `p25_bocha_ai_search` <- `p24_bazhu_dynamic_source`，`backend/alembic/versions/p25_bocha_ai_search.py`
32. `p26_report_records` <- `p25_bocha_ai_search`，`backend/alembic/versions/p26_report_records.py`
33. `p27_keyword_rule_config` <- `p26_report_records`，`backend/alembic/versions/p27_keyword_rule_config.py`
34. `p28_anspire_provider` <- `p27_keyword_rule_config`，`backend/alembic/versions/p28_anspire_provider.py`
35. `p29_report_templates` <- `p28_anspire_provider`，`backend/alembic/versions/p29_report_templates.py`
36. `p29_history_geo_filtered` <- `p29_report_templates`，`backend/alembic/versions/p29_history_geo_filtered.py`
37. `p30_event_actions_deprecated` <- `p29_history_geo_filtered`，`backend/alembic/versions/p30_event_actions_deprecated.py`
38. `p31_rbac_ai_perms` <- `p30_event_actions_deprecated`，`backend/alembic/versions/p31_rbac_ai_perms.py`
39. `sec3b_perm_semantic` <- `p31_rbac_ai_perms`，`backend/alembic/versions/sec3b_perm_semantic.py`
40. `p12_datasource_schedule` <- `sec3b_perm_semantic`，`backend/alembic/versions/p12_datasource_schedule.py`

说明：文件名中同时出现 `p12_rbac_roleperms` 和 `p12_datasource_schedule`，但 revision ID 不重复，且后者明确以 `sec3b_perm_semantic` 为父节点。它不是 Alembic 分支，但命名会增加维护时的认知成本。

## 3. 当前数据库真实Schema

### 3.1 public schema表清单

以下结果来自 `information_schema.columns`，字段数量按实际数据库列统计；所有列出的表均存在。

|表|存在|字段数|
|-|-:|-:|
|`alembic_version`|是|1|
|`alert_records`|是|15|
|`alert_rules`|是|10|
|`bocha_ai_leads`|是|13|
|`bocha_ai_search_sessions`|是|21|
|`bocha_leads`|是|18|
|`bocha_search_sessions`|是|16|
|`collector_runs`|是|21|
|`data_sources`|是|18|
|`event_actions`|是|8|
|`event_opinions`|是|3|
|`events`|是|14|
|`keywords`|是|11|
|`opinions`|是|37|
|`permissions`|是|8|
|`propagation_nodes`|是|13|
|`regions`|是|5|
|`report_records`|是|6|
|`report_templates`|是|8|
|`role_permissions`|是|2|
|`roles`|是|9|
|`user_login_logs`|是|8|
|`user_operation_logs`|是|15|
|`user_roles`|是|2|
|`users`|是|12|

重点表 `users`、`roles`、`permissions`、`user_roles`、`regions`、`opinions`、`events`、`event_opinions`、`keywords`、`data_sources`、`collector_runs`、`alert_records`、`report_records` 均存在。

### 3.2 重点表实际字段

`opinions`（37）：

`id`, `title`, `content`, `source`, `url`, `publish_time`, `region_id`, `risk_score`, `sentiment`, `summary`, `keywords`, `created_at`, `analysis_status`, `analysis_time`, `analysis_suggestion`, `search_vector`, `ai_summary`, `ai_sentiment`, `ai_risk_score`, `ai_keywords`, `ai_analysis_status`, `ai_analysis_time`, `ai_analysis_suggestion`, `severity_score`, `event_state`, `resolution_flag`, `risk_factors`, `risk_model_version`, `risk_category`, `source_type`, `author`, `engagement`, `external_id`, `relevance_score`, `content_type`, `admission_reason`, `geo_filtered`。

`collector_runs`（21）：

`id`, `collector_name`, `start_time`, `end_time`, `fetched_raw`, `created`, `analyzed`, `failed`, `status`, `error_msg`, `batch_id`, `trigger_type`, `comments_seen`, `comments_skipped`, `admission_filtered`, `upstream_total`, `upstream_returned`, `acknowledged`, `unconfirmed`, `ack_status`, `duplicate`。

`data_sources`（18）：

`id`, `key`, `name`, `type`, `class_path`, `enabled`, `priority`, `scope_region_codes`, `config_json`, `last_run_at`, `last_status`, `last_error`, `created_at`, `updated_at`, `schedule_enabled`, `schedule_interval_minutes`, `next_collect_time`, `last_collect_time`。

实际关键字段的数据库属性：

|表.字段|实际类型|可空|实际默认|
|-|-|-|-|
|`opinions.source`|`VARCHAR(128)`|否|无|
|`opinions.source_type`|`VARCHAR(32)`|是|无|
|`opinions.external_id`|`VARCHAR(128)`|是|无|
|`opinions.author`|`VARCHAR(128)`|是|无|
|`opinions.engagement`|`JSONB`|是|无|
|`opinions.publish_time`|`TIMESTAMP`|是|无|
|`opinions.risk_score`|`INTEGER`|否|无|
|`opinions.geo_filtered`|`BOOLEAN`|是|无|
|`collector_runs.batch_id`|`VARCHAR(64)`|是|无|
|`collector_runs.trigger_type`|`VARCHAR(16)`|是|无|
|`collector_runs.comments_seen`|`INTEGER`|否|`0`|
|`collector_runs.comments_skipped`|`INTEGER`|否|`0`|
|`collector_runs.admission_filtered`|`INTEGER`|否|`0`|
|`collector_runs.upstream_total`|`INTEGER`|是|无|
|`collector_runs.upstream_returned`|`INTEGER`|否|`0`|
|`collector_runs.duplicate`|`INTEGER`|否|`0`|
|`collector_runs.ack_status`|`VARCHAR(16)`|否|`'not_applicable'`|
|`data_sources.key`|`VARCHAR(64)`|否|无|
|`data_sources.name`|`VARCHAR(128)`|否|无|
|`data_sources.type`|`VARCHAR(32)`|否|`'news_site'`|
|`data_sources.class_path`|`VARCHAR(256)`|否|无|
|`data_sources.config_json`|`TEXT`|是|无|
|`data_sources.enabled`|`BOOLEAN`|否|`true`|
|`data_sources.schedule_enabled`|`BOOLEAN`|否|`true`|
|`data_sources.schedule_interval_minutes`|`INTEGER`|否|`30`|
|`data_sources.next_collect_time`|`TIMESTAMP`|是|无|

## 4. 核心表字段清单

除重点表外，实际核心表字段如下，来自同一份 `information_schema.columns` 查询：

- `users`：`id`, `username`, `password_hash`, `role`, `created_at`, `is_active`, `last_login`, `is_superuser`, `display_name`, `email`, `last_login_ip`, `updated_at`。
- `roles`：`id`, `name`, `display_name`, `created_at`, `code`, `description`, `is_system`, `is_enabled`, `updated_at`。
- `permissions`：`id`, `code`, `name`, `resource`, `action`, `description`, `group`, `created_at`。
- `user_roles`：`user_id`, `role_id`。
- `regions`：`id`, `code`, `name`, `level`, `parent_code`。
- `events`：`id`, `title`, `description`, `keyword`, `risk_level`, `opinion_count`, `first_time`, `last_time`, `region_id`, `status`, `risk_score`, `topic_category`, `heat_score`, `trend`。
- `event_opinions`：`id`, `event_id`, `opinion_id`。
- `keywords`：`id`, `word`, `weight`, `category`, `type`, `source`, `is_enabled`, `created_at`, `updated_at`, `severity_weight`, `rule_config`。
- `alert_records`：`id`, `rule_id`, `rule_name`, `risk_level`, `opinion_id`, `opinion_title`, `event_id`, `event_title`, `trigger_reason`, `handled`, `created_at`, `status`, `handled_by`, `handled_at`, `handle_note`。
- `report_records`：`id`, `name`, `config_json`, `status`, `created_by`, `created_at`。

## 5. Migration映射关系

以下“字段层状态”只判断字段是否存在、类型/可空性是否与对应 migration 定义一致；对象级索引、约束和注释漂移在第 7 节单独记录。

|字段|数据库存在|对应migration|状态|
|-|-|-|-|
|`opinions.source`|是|`0001_initial.py`|字段一致|
|`opinions.source_type`|是|`p13_weibo_fields.py`|字段一致|
|`opinions.external_id`|是|`p13_weibo_fields.py`|字段一致|
|`opinions.author`|是|`p13_weibo_fields.py`|字段一致|
|`opinions.engagement`|是|`p13_weibo_fields.py`|字段一致|
|`opinions.publish_time`|是|`0001_initial.py`|字段一致|
|`opinions.risk_score`|是|`0001_initial.py`|字段一致|
|`opinions.geo_filtered`|是|`p29_history_geo_filtered.py`|字段一致|
|`collector_runs.batch_id`|是|`collrunbatch001_collection_log_batch.py`|字段一致|
|`collector_runs.trigger_type`|是|`collrunbatch001_collection_log_batch.py`|字段一致|
|`collector_runs.comments_seen`|是|`p16_weibo_comment_run_stats.py`|字段一致|
|`collector_runs.comments_skipped`|是|`p16_weibo_comment_run_stats.py`|字段一致|
|`collector_runs.admission_filtered`|是|`p18_collector_run_admission_filtered.py`|字段一致|
|`collector_runs.upstream_total`|是|`p21_weibo_export_audit.py`|字段一致|
|`collector_runs.upstream_returned`|是|`p21_weibo_export_audit.py`|字段一致|
|`collector_runs.ack_status`|是|`p21_weibo_export_audit.py`|字段一致|
|`collector_runs.duplicate`|是|`p23_collector_run_duplicate.py`|字段一致|
|`data_sources.key`|是|`0004_phase3_datasource_region_parent.py`，revision=`phase3ds01`|字段一致|
|`data_sources.name`|是|`0004_phase3_datasource_region_parent.py`，revision=`phase3ds01`|字段一致|
|`data_sources.type`|是|`0004_phase3_datasource_region_parent.py`，revision=`phase3ds01`|字段一致|
|`data_sources.class_path`|是|`0004_phase3_datasource_region_parent.py`，revision=`phase3ds01`|字段一致|
|`data_sources.config_json`|是|`0004_phase3_datasource_region_parent.py`，revision=`phase3ds01`|字段一致|
|`data_sources.enabled`|是|`0004_phase3_datasource_region_parent.py`，revision=`phase3ds01`|字段一致|
|`data_sources.schedule_enabled`|是|`p12_datasource_schedule.py`|字段一致|
|`data_sources.schedule_interval_minutes`|是|`p12_datasource_schedule.py`|字段一致|
|`data_sources.next_collect_time`|是|`p12_datasource_schedule.py`|字段一致|

字段来源结论：MediaCrawler 微博帖子所需的 `opinions.source_type/author/engagement/external_id` 已由 `p13_weibo_fields.py` 纳入迁移链；采集运行记录所需的 batch、上游统计、评论统计、准入过滤和去重字段也均已有对应 migration。第一阶段按现有字段落库，不存在必须新增的字段级 migration。

## 6. ORM与数据库一致性

### 6.1 表与字段集合

`backend/app/models/` 注册了 24 个业务表。数据库 `public` schema 查询得到 25 个表，其中额外的 1 个是 Alembic 自身的 `alembic_version`；数据库没有 ORM 缺失的业务表，ORM 也没有数据库缺失的业务表。

逐表字段集合比较结果：24 个业务表均无 `db_only` 或 `model_only` 字段。重点模型定义位置为：

- `backend/app/models/opinion.py`：`Opinion`，微博字段在 `source_type`、`author`、`engagement`、`external_id`，历史标记为 `geo_filtered`；
- `backend/app/models/collector_run.py`：`CollectorRun`，包含 `batch_id`、`trigger_type`、上游统计、评论统计、`admission_filtered`、`duplicate` 和 `ack_status`；
- `backend/app/models/data_source.py`：`DataSource`，包含 `key`、`type`、`class_path`、`config_json` 和四个调度字段；
- `backend/app/models/event.py`：`Event`，包含 `region_id`、`status`、`risk_score`、`topic_category`、`heat_score`、`trend` 等字段。

### 6.2 只读alembic check结果

`alembic check` 退出码为 1，输出 `FAILED: New upgrade operations detected`。它没有报告重点字段缺失，但报告以下 metadata 对象差异：

|对象|数据库实际状态|ORM期望|影响判断|
|-|-|-|-|
|`bocha_ai_leads(session_id,result_index)`|名为 `uq_bocha_ai_leads_session_result` 的唯一约束/唯一索引，FK 带 `ON DELETE CASCADE`|`ix_bocha_ai_leads_session_result` 唯一索引，FK 未声明删除动作|对象定义不同，当前唯一性仍有效|
|`data_sources.key`|唯一约束 `data_sources_key_key` + 非唯一 `ix_data_sources_key`|`unique=True,index=True` 对应的唯一索引语义|唯一性仍有效，但对象形态不同|
|`keywords.word`|无单列 `ix_keywords_word`；有 `(word,type)` 唯一约束|模型声明单列普通索引|查询性能对象漂移|
|`keywords.type`|数据库有 `monitoring\|sensitive` 列注释|ORM 未声明该 comment|元数据注释漂移|
|`permissions.code`|唯一约束 + 非唯一索引|唯一索引语义|唯一性仍有效，对象形态不同|
|`permissions.description`|数据库可空|ORM `nullable=False`|模型写入契约与数据库约束不一致|
|`roles.description`|数据库可空|ORM `nullable=False`|模型写入契约与数据库约束不一致|
|`report_records`|数据库有 `created_by`、`created_at` 索引|ORM有 `created_by` 和主键 `id` 索引|索引集合不同，功能不丢失但性能契约不一致|
|`report_templates`|数据库有 `owner_id`、`is_public` 索引|ORM有 `owner_id` 和主键 `id` 索引|索引集合不同|
|`role_permissions`|复合主键保证唯一，无 named unique constraint|ORM另声明 `uq_role_permission`|业务唯一性仍由主键保证|
|`user_roles`|复合主键保证唯一，无 named unique constraint|ORM另声明 `uq_user_role`|业务唯一性仍由主键保证|
|`user_operation_logs`|索引名为 `..._operator`、`..._target`|ORM索引名为 `..._operator_user_id`、`..._target_user_id`|列相同，主要是命名漂移|

其中 migration 证据包括：

- `backend/alembic/versions/p25_bocha_ai_search.py` 创建 `bocha_ai_leads` 的唯一约束和 CASCADE 外键；
- `backend/alembic/versions/0004_phase3_datasource_region_parent.py` 创建 `data_sources` 的 key 约束/索引；
- `backend/alembic/versions/kwlex01.py` 明确清理旧的 `ix_keywords_word`，并执行 `COMMENT ON COLUMN keywords.type IS 'monitoring|sensitive'`；
- `backend/alembic/versions/rbac10001.py` 创建 `permissions`、`role_permissions`、`user_roles`，其中 description 为可空，关联表同时有复合主键和 named unique constraint；
- `backend/alembic/versions/p26_report_records.py` 创建 `report_records` 的 `created_by`、`created_at` 索引；
- `backend/alembic/versions/p29_report_templates.py` 创建 `report_templates` 的 `owner_id`、`is_public` 索引；
- `backend/alembic/versions/rbac10001.py` 创建 `user_operation_logs` 的 `operator`、`target` 索引。

## 7. Schema Drift问题

### 7.1 迁移链与数据库版本

未发现“migration 文件存在但数据库版本停在其之前”的 revision 链问题：当前 `p12_datasource_schedule` 的父链已经包含 `p13_weibo_fields` 至 `p31_rbac_ai_perms`，因为这些 revision 由 `p12_datasource_schedule -> sec3b_perm_semantic -> ... -> p13_weibo_fields` 反向连接在当前 head 的祖先链中。名称中的 `p12` 不代表它早于 `p13`，应以 `down_revision` 图为准。

未发现多个 head、多个 root 或断链。仅凭当前结果不能证明数据库对象是否曾被人工修改；可以确认的是，当前 ORM metadata 与 PostgreSQL 实际对象存在漂移，来源可能是后续模型调整未配套 migration，也可能包含历史对象变更。

### 7.2 漂移边界

- 字段集合漂移：未发现；24 个业务表逐字段一致。
- 重点字段类型/可空性漂移：未发现；但 `permissions.description`、`roles.description` 是非重点字段的 ORM/DB 可空性差异。
- 索引/唯一约束漂移：发现。
- 外键选项漂移：发现 `bocha_ai_leads.session_id` 的 CASCADE 声明差异。
- 注释漂移：发现 `keywords.type` 的数据库注释与 ORM 定义差异。
- 迁移版本漂移：未发现；数据库 version 与当前代码 head 一致。
- 结构 baseline 清洁度：不通过；`alembic check` 失败。

## 8. 风险等级

### Critical

当前未发现 Critical 级别的表缺失、重点字段缺失、多个 head 或 migration 断链。数据库身份也通过了项目安全门禁。

### High

1. ORM metadata 与实际数据库对象不一致，且 `alembic check` 失败。当前没有字段级断裂，但未来新增 migration 或自动生成 migration 时，可能把历史对象差异混入变更，造成非预期索引/约束调整。
2. `permissions.description`、`roles.description` 的 ORM 非空契约与数据库可空结构不一致。若后续依赖 ORM metadata 生成非空迁移，需先检查 NULL 存量并明确目标契约。

### Medium

1. `keywords.word` 单列索引在数据库中不存在，而 ORM 声明存在；关键词按 word 查询的性能契约不一致。
2. 多处索引名称或索引列集合与模型不一致；当前主要影响查询性能和 schema 可解释性，不直接造成数据丢失。
3. `role_permissions`、`user_roles` 的复合主键已经保证唯一，但 ORM 还声明了额外 named unique constraint；若直接按 ORM 生成修复迁移，可能产生冗余对象。
4. `backend/scripts/init_db.py` 在 `init()` 中调用 `Base.metadata.create_all(bind=engine)` 作为安全网；`backend/Dockerfile` 又在启动时执行 `alembic upgrade head && python scripts/init_db.py`。`create_all` 不会修正已存在表的字段/索引漂移，但可能掩盖“迁移缺失仍能建表”的环境问题。

### Low

1. `p12_rbac_roleperms.py` 与 `p12_datasource_schedule.py` 文件名共享 `p12` 前缀，revision ID 实际不同且链路正确；主要是可维护性风险。
2. `user_operation_logs` 索引名变化但列相同，当前主要影响运维排查和迁移 diff 可读性。

## 9. 推荐处理方案

本节只提出方案，不执行任何修复。

### 方案A：保持现有数据库版本并重新确认baseline

数据库当前已经是 `p12_datasource_schedule`，因此不需要再次执行 `alembic stamp`。只有在经过独立的结构、数据和 revision 证据复核，确认数据库确实对应目标 baseline 后，才可以把现有 version 作为可信标记；`stamp` 本身只改变版本标记，不修复对象漂移。

### 方案B：新增显式对账migration

推荐用于当前环境。先由架构负责人决定“数据库现状”还是“ORM metadata”作为目标契约，再新增一份显式 reconciliation migration，逐项处理：索引形态、索引集合、约束命名/重复性、外键删除选项、列可空性和注释。执行前必须做 NULL、重复键、外键引用和查询性能影响检查，禁止用自动生成结果直接上线。

### 方案C：建立全新baseline

仅适用于隔离环境或计划停机后的受控重建：以确认后的目标 schema 生成新的 baseline，并对现有数据库做备份、结构校验和数据恢复演练。当前生产/开发目标库不建议直接采用此方案，不能通过重建来掩盖对象漂移来源。

推荐顺序：不执行方案 A 的 stamp；先形成方案 B 的对象级对账清单和目标契约，再在独立变更阶段实施。方案 C 作为长期整理方案，不作为 MediaCrawler 接入前的即时动作。

## 10. 是否可以进入Phase MediaCrawler-1A

明确结论：**可以进入不新增数据库字段的 MediaCrawler-1A 离线适配器、JSONL fixture 和 schema 读验证；不建议在当前 baseline drift 未明确收口前直接执行依赖数据库迁移的生产实施。**

进入条件：

1. 继续复用现有字段：`opinions.source_type/author/engagement/external_id`，以及现有 `collector_runs` 统计字段；无需新增表或字段。
2. 将 `alembic check` 的对象级漂移列为独立 baseline 对账任务，明确保留或修正的目标对象。
3. 不执行 `stamp`、`upgrade`、`downgrade` 或任何 DDL 作为 MediaCrawler 接入的隐含前置动作。
4. 未来若 Phase MediaCrawler-1A 需要新增数据库对象，必须先完成 migration 目标契约、NULL/重复数据检查和回滚方案评审。

最终判断：业务字段 Schema 对 MediaCrawler 是可用的；Alembic 版本链是可信的单链；整体 Schema 只能评定为“部分可信”，不能评定为“零 drift baseline”。
