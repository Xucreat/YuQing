# Schema Drift Report

Phase DB-Schema-Drift-Resolve-1 的目标是建立可审计的 Schema baseline，不在本阶段修复数据库。以下结果均来自只读命令、PostgreSQL catalog 查询、ORM metadata 比对和 migration 文件阅读。

## 1. Alembic状态

### 1.1 数据库身份

身份核验通过，未触发停止条件：

|项目|实际结果|
|-|-|
|数据库|`opinion_db`|
|地址|`127.0.0.1:5432`|
|PostgreSQL system identifier|`7663057120701798896`|
|`alembic_version`|`p12_datasource_schedule`|
|身份门禁|`DATABASE IDENTITY: VERIFIED`|

身份查询使用 `SELECT current_database(), inet_server_addr(), inet_server_port(), version_num FROM alembic_version`，并读取 `pg_control_system()` 的 `system_identifier`。`backend/alembic/env.py` 的 `run_migrations_online()` 仍通过 `assert_identity_for_migration()` 执行迁移身份门禁，但本阶段没有执行迁移。

### 1.2 current / heads / branches

实际只读命令结果：

```text
alembic current
p12_datasource_schedule (head)

alembic heads
p12_datasource_schedule (head)

alembic branches
无输出
```

数据库 `alembic_version` 查询结果：

```text
current_database: opinion_db
inet_server_addr: 127.0.0.1
inet_server_port: 5432
version_num: p12_datasource_schedule
```

结论：当前 revision 和 head 一致；migration 图为单 root、单 head、无 branch、无断链。代码目录中有 40 个 revision，当前 head `p12_datasource_schedule` 的父链包含 `p13_weibo_fields` 至 `p31_rbac_ai_perms`，不能仅按文件名前缀判断先后关系。

## 2. Drift统计

### 2.1 `alembic check`完整结果

只读执行 `alembic check`，身份门禁通过，但进程退出码为 `1`，结果为：

```text
FAILED: New upgrade operations detected
```

Alembic 逐项检测到以下对象差异：

```text
bocha_ai_leads:
  remove unique constraint uq_bocha_ai_leads_session_result
  add unique index ix_bocha_ai_leads_session_result
  remove foreign key session_id -> bocha_ai_search_sessions.id ON DELETE CASCADE
  add foreign key session_id -> bocha_ai_search_sessions.id

data_sources:
  remove unique constraint data_sources_key_key
  remove non-unique index ix_data_sources_key
  add unique index ix_data_sources_key

keywords:
  remove database comment on type: monitoring|sensitive
  add index ix_keywords_word

permissions:
  change description nullable: database YES -> ORM NO
  remove unique constraint permissions_code_key
  remove non-unique index ix_permissions_code
  add unique index ix_permissions_code

report_records:
  remove index ix_report_records_created_at
  add index ix_report_records_id

report_templates:
  remove index ix_report_templates_is_public
  add index ix_report_templates_id

role_permissions:
  add unique constraint uq_role_permission

roles:
  change description nullable: database YES -> ORM NO

user_operation_logs:
  remove indexes ix_user_operation_logs_operator / ix_user_operation_logs_target
  add indexes ix_user_operation_logs_operator_user_id / ix_user_operation_logs_target_user_id

user_roles:
  add unique constraint uq_user_role
```

Alembic 同时输出了 PostgreSQL sequence 被识别为 serial-owned sequence 的 INFO 信息。这些 sequence 信息不是 drift 项，不计入下表。

### 2.2 按语义对象统计

低层 Alembic operation 数量会因为“删除旧对象 + 创建新对象”重复计数；下表按需要决策的语义对象计数：

|类型|数量|风险|结论|
|-|-|-|-|
|index|9 个对象，14 个低层操作|低/中|大部分为索引集合或命名差异；`keywords.word` 是实际缺少的单列索引|
|unique|5 个语义对象|低|已有唯一约束或复合主键保证业务唯一性，未发现唯一性裸露缺失|
|fk|1 个|中|`bocha_ai_leads.session_id` 的 CASCADE 行为与 ORM 声明不同|
|nullability|2 个字段|中/高|`permissions.description`、`roles.description` 数据库可空而 ORM 声明非空|
|comment|1 个|低|`keywords.type` 数据库有注释，ORM 未声明|

## 3. 每项详细差异

### 3.1 `bocha_ai_leads(session_id,result_index)` 唯一对象

对象：`bocha_ai_leads` 的 `(session_id, result_index)`。

ORM：`backend/app/models/bocha_ai_lead.py` 的 `__table_args__` 声明 `Index("ix_bocha_ai_leads_session_result", "session_id", "result_index", unique=True)`。

数据库：存在唯一约束 `uq_bocha_ai_leads_session_result`，PostgreSQL 同时显示其对应唯一索引。

差异：ORM 期望命名唯一索引，数据库由 migration 创建的是 named unique constraint。

影响：组合唯一性实际存在，当前不会允许同一搜索会话的同一结果序号重复。差异主要是对象类型和名称，会导致 `alembic check` 持续失败。

建议：**Strategy C，优先保留数据库现状并后续修正 ORM metadata 或明确目标对象**。不要为了让检查通过而立即删除已有唯一约束并重建索引。

来源：`backend/alembic/versions/p25_bocha_ai_search.py` 的 `op.create_table("bocha_ai_leads", ...)` 使用 `sa.UniqueConstraint("session_id", "result_index", name="uq_bocha_ai_leads_session_result")`。

### 3.2 `bocha_ai_leads.session_id` 外键行为

对象：`bocha_ai_leads.session_id -> bocha_ai_search_sessions.id`。

ORM：`backend/app/models/bocha_ai_lead.py` 使用 `ForeignKey("bocha_ai_search_sessions.id")`，未声明 `ondelete="CASCADE"`。

数据库：`bocha_ai_leads_session_id_fkey` 存在，实际选项为 `ON DELETE CASCADE`。

差异：数据库删除搜索会话时级联删除 leads，ORM metadata 没有表达该行为。

影响：这是行为契约差异，不是字段缺失。直接删除父会话时，数据库和 ORM 维护者对级联语义的理解可能不同。

建议：**Strategy C，若数据库 CASCADE 是既定业务语义，则后续修正 ORM metadata；若业务不允许级联，才应评审 Strategy B migration 去除 CASCADE**。本阶段不改变任何一侧。

来源：`backend/alembic/versions/p25_bocha_ai_search.py` 的 `ForeignKeyConstraint(["session_id"], ["bocha_ai_search_sessions.id"], ondelete="CASCADE")`。

### 3.3 `data_sources.key` 唯一对象与索引

对象：`data_sources.key`。

ORM：`backend/app/models/data_source.py` 的 `key` 使用 `mapped_column(String(64), unique=True, index=True, nullable=False)`，Alembic metadata 期望唯一索引语义。

数据库：存在唯一约束/唯一索引 `data_sources_key_key`，另有非唯一索引 `ix_data_sources_key`。

差异：数据库具有一个唯一约束和一个普通重复索引；ORM metadata 期望 `ix_data_sources_key` 为唯一索引。

影响：`key` 的业务唯一性有效；普通重复索引增加对象冗余，差异主要影响 schema 清洁度和迁移 diff。

建议：**Strategy A，当前无需处理**。若未来做对象清理，应在独立 migration 中确认索引使用和锁影响后再删除冗余对象；不作为 MediaCrawler 接入前置动作。

来源：`backend/alembic/versions/0004_phase3_datasource_region_parent.py`，revision=`phase3ds01`，创建 `data_sources` 表及 key 相关对象。

### 3.4 `keywords.type` 列注释

对象：`keywords.type`。

ORM：当前 `backend/app/models/keyword.py` 未声明该列 comment。

数据库：存在列注释 `monitoring|sensitive`。

差异：数据库有说明性 comment，ORM metadata 认为 comment 为空。

影响：不影响读写、约束或业务逻辑，只影响 schema 文档和 `alembic check`。

建议：**Strategy A，保留数据库注释，无需处理**；或在未来 ORM 文档化变更中统一声明。不要为了清除检查输出而删除有价值的数据库说明。

来源：`backend/alembic/versions/kwlex01.py` 的 `COMMENT ON COLUMN keywords.type IS 'monitoring|sensitive'`。

### 3.5 `keywords.word` 单列索引

对象：`keywords.word`。

ORM：`backend/app/models/keyword.py` 的 `word` 使用 `mapped_column(String(128), index=True, nullable=False)`，期望普通索引 `ix_keywords_word`。

数据库：没有 `ix_keywords_word`；数据库存在 `(word, type)` 复合唯一对象 `uq_keywords_word_type`。

差异：ORM 期望的单列普通索引缺失。

影响：复合索引/约束不一定等价于所有 `word` 单列查询的性能路径，可能造成关键词查询计划差异；不属于数据唯一性丢失。

建议：**Strategy B，后续显式 migration 或 Strategy C 调整 ORM，二选一**。应先用真实查询计划和数据量确认是否需要单列索引；不能直接使用自动生成 migration。

来源：`backend/alembic/versions/kwlex01.py` 负责关键词分层和复合唯一策略，并明确清理历史 `ix_keywords_word`；这说明数据库现状可能是有意的历史策略，需先确定目标契约。

### 3.6 `permissions.code` 唯一对象

对象：`permissions.code`。

ORM：`backend/app/models/permission.py` 使用 `mapped_column(String(64), unique=True, index=True, nullable=False)`，期望唯一索引。

数据库：存在唯一约束 `permissions_code_key`，并有非唯一索引 `ix_permissions_code`。

差异：唯一约束 + 普通索引与 ORM 期望的唯一索引对象形态不同。

影响：`code` 唯一性有效；普通索引为冗余对象，当前无唯一性风险。

建议：**Strategy A，当前无需处理**。后续若统一 metadata，应明确保留 constraint 还是改成 unique index，避免无业务收益的对象重建。

来源：`backend/alembic/versions/rbac10001.py` 创建 `permissions` 时定义 `sa.UniqueConstraint("code")` 和 `ix_permissions_code`。

### 3.7 `permissions.description` 可空性

对象：`permissions.description`。

ORM：`backend/app/models/permission.py` 定义 `description: Mapped[str] = mapped_column(String(255), default="")`，按当前 metadata 为非空。

数据库：`information_schema.columns.is_nullable = YES`；当前 NULL 行数为 0，总行数为 26。

差异：数据库允许 NULL，ORM schema 期望 NOT NULL。

影响：未来直接通过 SQL 或其他客户端写入 NULL 时，数据库允许而 ORM 类型契约不允许；当前存量没有 NULL。

建议：**Strategy B 或 C，必须先选择目标契约**。若目标是 ORM 非空，应先设计存量检查/回填再做 migration；若数据库可空是有意兼容策略，应改 ORM metadata。当前禁止任何修复。

来源：`backend/alembic/versions/rbac10001.py` 创建 `permissions.description` 为 nullable；当前模型定义与 migration 定义不同。

### 3.8 `report_records` 索引集合

对象：`report_records` 索引。

ORM：`backend/app/models/report_record.py` 声明 `id = Column(Integer, primary_key=True, index=True)`，并对 `created_by` 声明 `index=True`。

数据库：存在 `ix_report_records_created_by`、`ix_report_records_created_at`；不存在 ORM 期望的 `ix_report_records_id`。

差异：数据库保留 migration 创建的 `created_at` 索引，ORM 期望主键 id 的二级索引。

影响：主键自身已有主键索引，`ix_report_records_id` 通常没有额外收益；`created_at` 是否需要索引取决于报告审计查询。

建议：**Strategy A/C，当前无需处理**。应先确定查询契约；不建议为 `id` 主键重复建立二级索引。

来源：`backend/alembic/versions/p26_report_records.py` 创建 `created_by` 和 `created_at` 索引。

### 3.9 `report_templates` 索引集合

对象：`report_templates` 索引。

ORM：`backend/app/models/report_template.py` 声明主键 `id` 带 `index=True`，`owner_id` 带 `index=True`。

数据库：存在 `ix_report_templates_owner_id`、`ix_report_templates_is_public`；不存在 ORM 期望的 `ix_report_templates_id`。

差异：数据库按 migration 保留 `is_public` 查询索引，ORM metadata 期望主键二级索引。

影响：主键已有主键索引，新增 id 二级索引通常没有收益；`is_public` 索引可能服务公开模板筛选。

建议：**Strategy A/C，当前无需处理**。保留数据库业务查询索引更合理；若要清洁 `alembic check`，应先通过查询计划确定目标并修改 ORM 契约或写显式 migration。

来源：`backend/alembic/versions/p29_report_templates.py` 创建 `owner_id` 和 `is_public` 索引。

### 3.10 `role_permissions` 复合唯一约束

对象：`role_permissions(role_id, permission_id)`。

ORM：`backend/app/models/permission.py` 的 `role_permissions = Table(...)` 声明复合主键，并额外声明 `UniqueConstraint(..., name="uq_role_permission")`。

数据库：复合主键已存在；未发现名为 `uq_role_permission` 的额外 unique constraint。重复计数为 0。

差异：ORM 期望一个冗余 named unique constraint，数据库依靠复合主键提供同等唯一性。

影响：当前业务唯一性没有缺口，额外约束只会重复表达相同规则。

建议：**Strategy C，保留数据库主键，后续移除或调整 ORM 中的冗余 metadata 声明**。不建议新增冗余 constraint migration。

来源：`backend/alembic/versions/rbac10001.py` 同时创建复合主键和 `uq_role_permission`；当前数据库仅保留主键形态。

### 3.11 `roles.description` 可空性

对象：`roles.description`。

ORM：`backend/app/models/role.py` 定义 `description: Mapped[str] = mapped_column(String(255), default="")`，当前 metadata 期望非空。

数据库：`information_schema.columns.is_nullable = YES`；当前 NULL 行数为 3，总行数为 4。

差异：数据库存在真实 NULL 存量，ORM 期望 NOT NULL。

影响：这是本次最需要谨慎处理的 nullability drift。直接把数据库改成 NOT NULL 会因现有 NULL 数据失败或被迫做未审议的数据回填。

建议：**Strategy B 或 C，暂不修复**。先由业务确定 NULL 是否具有兼容语义，再制定数据回填、约束变更和回滚方案；不能在本阶段自动生成或执行 migration。

来源：`backend/alembic/versions/rbac10001.py` 创建 `roles.description` 为 nullable；当前模型定义与数据库实际存量不一致。

### 3.12 `user_operation_logs` 索引名称

对象：`user_operation_logs.operator_user_id`、`user_operation_logs.target_user_id`。

ORM：`backend/app/models/audit.py` 生成 `ix_user_operation_logs_operator_user_id`、`ix_user_operation_logs_target_user_id`。

数据库：实际索引名为 `ix_user_operation_logs_operator`、`ix_user_operation_logs_target`，列相同。

差异：索引名不同，索引列和普通索引语义相同。

影响：不影响查询结果，主要影响运维脚本、迁移 diff 和对象可读性。

建议：**Strategy A，当前无需处理**；如需清洁命名，使用显式 migration 或 ORM 目标统一，禁止自动生成后直接提交。

来源：`backend/alembic/versions/rbac10001.py` 创建上述两个旧名称索引。

### 3.13 `user_roles` 复合唯一约束

对象：`user_roles(user_id, role_id)`。

ORM：`backend/app/models/permission.py` 的 `user_roles = Table(...)` 声明复合主键，并额外声明 `UniqueConstraint(..., name="uq_user_role")`。

数据库：复合主键已存在；未发现名为 `uq_user_role` 的额外 unique constraint。重复计数为 0。

差异：ORM 期望一个冗余 named unique constraint，数据库依靠复合主键提供唯一性。

影响：当前业务唯一性没有缺口。

建议：**Strategy C，保留数据库主键，后续调整 ORM 冗余声明**。不建议新增冗余 constraint migration。

来源：`backend/alembic/versions/rbac10001.py` 创建复合主键和 `uq_user_role`；当前数据库复合主键已足够保证唯一性。

## 4. A类与B类分类结论

### 4.1 A类：纯数据库历史残留或契约表达差异

以下项目当前不影响业务运行，建议保留现状或后续通过 ORM/显式 migration 对齐：

- `keywords.type` comment；
- `data_sources.key`、`permissions.code` 的 constraint/index 对象形态；
- `bocha_ai_leads` 的 unique constraint 与 unique index 命名/表达差异；
- `report_records`、`report_templates` 的索引集合中主键二级索引与业务查询索引差异；
- `user_operation_logs` 索引名称差异；
- `role_permissions`、`user_roles` 的冗余 named unique constraint metadata。

### 4.2 B类：真实结构或行为风险

以下项目需要后续明确目标契约，不能被简单视为命名残留：

- `bocha_ai_leads.session_id` 的数据库 CASCADE 与 ORM 未声明 CASCADE；
- `keywords.word` 缺少 ORM 声明的单列索引，可能有查询性能影响；
- `permissions.description` 的 nullable 不一致；
- `roles.description` 的 nullable 不一致，且数据库已有 3 条 NULL；
- `report_records`、`report_templates` 的索引集合如后续业务查询依赖某一方，需以查询计划决定目标。

## 5. 修复策略

### Strategy A：无需修复

适用：不影响业务语义、数据完整性和关键查询的差异。

- 保留 `keywords.type` 数据库 comment；
- 保留已有业务查询索引 `report_records.created_at`、`report_templates.is_public`；
- 保留 `user_operation_logs` 现有索引名称；
- 不为主键重复建立 `id` 二级索引；
- 不为复合主键重复添加 named unique constraint；
- 暂不清理 `data_sources.key`、`permissions.code` 的冗余普通索引，除非后续专项索引治理确认收益。

### Strategy B：后续新增显式 migration

适用：确认数据库对象必须改变，且需要版本化、可回滚的 schema 变更。

- `keywords.word`：先基于真实查询计划和表规模确认单列索引价值，再决定是否新增；
- `permissions.description`、`roles.description`：先确定 NULL 语义，完成存量 NULL 处置设计，再决定是否转 NOT NULL；
- `bocha_ai_leads.session_id`：只有当业务明确不允许 CASCADE 时，才评审去除数据库 CASCADE；
- 其他索引集合：先确定查询契约，再做显式增删。

本阶段不创建 migration，不执行任何 DDL。

### Strategy C：后续修正 ORM metadata

适用：数据库现状有明确 migration 依据或业务语义合理，而 ORM 表达不准确。

- 为 `bocha_ai_leads.session_id` 明确表达数据库的 CASCADE 语义，或形成正式的反向变更决策；
- 对复合主键上的冗余 unique constraint 做 ORM 语义收口；
- 对 `data_sources.key`、`permissions.code` 的唯一性表达选择统一形式；
- 对 `roles/permissions.description` 选择可空或非空的唯一契约。

本阶段不修改 models。

## 6. MediaCrawler Schema readiness

### 6.1 `data_sources`

未来数据源记录可以直接复用现有表，不需要 migration：

```text
key         = weibo_mediacrawler
type        = social
class_path  = app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
```

证据：

- `data_sources.key` 为 `VARCHAR(64) NOT NULL` 且有唯一性；目标 key 长度满足约束；
- `data_sources.type` 为 `VARCHAR(32) NOT NULL`，数据库没有限制 `social` 的 check constraint；
- `data_sources.class_path` 为 `VARCHAR(256) NOT NULL`，目标路径长度满足约束；
- `data_sources.config_json` 为可空 `TEXT`；
- `schedule_enabled`、`schedule_interval_minutes`、`next_collect_time` 已存在；
- `ck_data_sources_schedule_interval_min` 已存在，要求 `schedule_interval_minutes >= 5`；
- 当前查询没有发现 `key='weibo_mediacrawler'` 的现有数据行，本阶段未插入数据。

### 6.2 `opinions`

无需新增以下字段：

- `platform`：无需新增；
- `external_id`：已存在，`VARCHAR(128)`，可空，并有 `ix_opinions_external_id`；
- `source_type`：已存在，`VARCHAR(32)`，可空，并有 `ix_opinions_source_type`；
- `engagement`：已存在，`JSONB`，可空；
- `url`：已存在，`VARCHAR(1024)`，数据库有 `ix_opinions_url_unique` 部分唯一索引，条件为非 NULL 且非空字符串。

### 6.3 `collector_runs`

无需新增以下字段：

- `batch_id`：已存在，`VARCHAR(64)`，可空，并有 `ix_collector_runs_batch_id`；
- `trigger_type`：已存在，`VARCHAR(16)`，可空；
- `duplicate`：已存在，`INTEGER NOT NULL DEFAULT 0`；
- `admission_filtered`：已存在，`INTEGER NOT NULL DEFAULT 0`；
- 相关的 `upstream_total`、`upstream_returned`、`ack_status`、`comments_seen`、`comments_skipped` 也均已存在。

### 6.4 readiness结论

**MediaCrawler Schema readiness: PASS**

该 PASS 仅表示 MediaCrawler 第一阶段所需业务字段、索引和数据源配置承载能力已经存在，不表示整体 `alembic check` 已通过，也不授权执行数据库写操作。

## 7. 本阶段禁止行为执行情况

- 未修改 `models`；
- 未修改 migration；
- 未创建新的 migration；
- 未执行 `alembic upgrade`；
- 未执行 `alembic downgrade`；
- 未执行 `alembic stamp`；
- 未执行 SQL `ALTER TABLE` 或其他 DDL；
- 未修改数据库数据或结构；
- 未修改 MediaCrawler 或其他业务代码。

## 8. 最终结论

Phase DB-Schema-Drift-Resolve-1 完成。

```text
代码修改: 无
数据库修改: 无
Migration: 无

Schema 状态:
  字段: PASS
  对象: FAIL（alembic check 仍存在对象级 drift）

MediaCrawler 前置条件: PASS
建议下一阶段: Phase MediaCrawler-1A（仅限不新增 schema 的实现路径）
```

进入 Phase MediaCrawler-1A 时必须继续保留本报告中的对象级 drift 清单；若后续实施需要新增数据库对象或执行迁移，应先单独完成 Strategy B/C 的目标契约评审，不得把历史 drift 修复混入 MediaCrawler 接入变更。
