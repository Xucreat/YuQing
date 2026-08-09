# Phase Foreign-Source-3C-Implementation
# 外网告警独立链路实施报告

## 1. 实施结论

本阶段已在独立测试库完成外网告警首期实现与聚焦验证。实现链路为：

```text
foreign_risk_results / confirmed foreign_events
    -> ForeignAlertService
    -> foreign_alerts / foreign_alert_runs
    -> /api/foreign/alerts/*
    -> /foreign?tab=alerts
```

本阶段只实现独立外网规则、告警记录、手动评估、Dry-Run、去重、冷却、确认、解决、抑制和站内展示。没有实现外部通知、自动评估、自动调度、候选事件告警或任何国内链路改造。

最终结论：**Phase 3C 实施聚焦验收通过，允许进入 Phase Foreign-Source-3C 小型告警结果验收；不代表允许生产启用。**

## 2. 环境与生产保护

### 2.1 前置检查

已执行：

```text
git status --short
alembic current
```

默认连接身份确认如下：

| 项目 | 结果 |
|---|---|
| 默认数据库 | `opinion_db` |
| 默认 Alembic revision | `foreign_source_1` |
| 外网 3A/3B/3C 后续表 | 默认库不存在，未执行后续生产迁移 |
| Fox News | `enabled=false`, `schedule_enabled=false` |
| The Guardian | `enabled=false`, `schedule_enabled=false` |
| 纽约时报中文网 | `enabled=false`, `schedule_enabled=false` |
| 外网运行中采集任务 | 0 |
| 默认库外网舆情 | 3 条，保留 |
| 默认库国内数据快照 | `opinions=1702`, `events=292`, `event_opinions=567`, `alert_records=37` |

工作区原有修改、未跟踪文件、备份和临时文件均保留，未使用 `git reset`、`git checkout` 或清理命令。

### 2.2 测试库

迁移、写入测试和临时 fixture 使用独立测试库 `opinion_test`（本机 PostgreSQL 测试实例，测试配置端口为 `5433`）。没有在默认 `opinion_db` 上执行 migration、insert、update、delete、truncate 或 downgrade。

Phase 3C 测试创建的规则、告警和运行记录已在测试库清理；用户已有的 `foreign_opinions` 和采集日志未删除。默认库最终仍为 `foreign_source_1`，没有生产结构或数据变化。

本阶段没有访问真实 RSS，没有使用代理或境外采集节点，没有调用外部 AI，也没有发送真实通知。

## 3. 实际改动文件

本阶段 3C 直接新增或接入的文件如下：

| 文件 | 内容 |
|---|---|
| `backend/alembic/versions/foreign_source_3c.py` | 3C migration、权限安装与回滚 |
| `backend/app/models/foreign_alert_rule.py` | `foreign_alert_rules` ORM 模型 |
| `backend/app/models/foreign_alert.py` | `foreign_alerts` ORM 模型 |
| `backend/app/models/foreign_alert_run.py` | `foreign_alert_runs` ORM 模型 |
| `backend/app/services/foreign_alert_service.py` | 独立规则评估、去重、冷却和状态操作 |
| `backend/app/api/foreign_alerts.py` | 外网告警 API、规则 API、运行日志 API |
| `backend/app/api/__init__.py` | 注册外网告警路由 |
| `backend/app/models/__init__.py` | 注册三个外网告警模型 |
| `frontend/src/views/ForeignWorkspace.vue` | `alerts` tab、状态和站内告警操作界面 |
| `backend/tests/test_foreign_source_3c.py` | 3C 规则、隔离、幂等和 API 测试 |

工作区中已有的 Phase 1/1.1/2/3A/3B 修改和其他未跟踪文件没有被撤销、覆盖或整理。本报告不把这些既有文件列为本阶段的业务改动。

## 4. 数据库迁移

迁移文件为 `foreign_source_3c`，`down_revision=foreign_source_3b`。升级创建三张独立外网表和 `foreign:alerts:*` 权限，并向 admin 授予对应权限；不修改国内表。

### 4.1 `foreign_alert_rules`

主要字段：

| 字段 | 说明 |
|---|---|
| `id`, `name`, `description` | 主键和规则描述 |
| `rule_type` | `risk_score`、`risk_level`、`risk_category`、`confirmed_event`、`keyword_combo` |
| `conditions` | JSONB 条件快照 |
| `severity` | `low`、`medium`、`high`、`critical` |
| `is_enabled` | 默认 `false` |
| `cooldown_seconds` | 非负冷却窗口 |
| `deduplication_key_template` | 稳定去重键模板 |
| `rule_version` | 历史规则版本标识 |
| `created_by`, `updated_by` | 用户外键，可置空 |
| `created_at`, `updated_at` | 时间字段 |

规则类型、严重度和冷却值由数据库 CheckConstraint 约束，并对启用状态和规则类型建索引。

### 4.2 `foreign_alerts`

主要字段：

| 字段 | 说明 |
|---|---|
| `rule_id` | 外网规则外键，规则删除时置空 |
| `foreign_opinion_id` | 外网文章外键 |
| `foreign_risk_result_id` | 外网风险结果外键 |
| `foreign_event_id` | 外网事件外键 |
| `severity`, `status` | 严重度和 `triggered/acknowledged/resolved/suppressed/failed` 状态 |
| `title`, `message` | 触发时消息快照 |
| `matched_conditions`, `rule_snapshot` | 命中条件和规则版本快照 |
| `source_name_snapshot`, `opinion_title_snapshot`, `event_title_snapshot` | 关联对象展示快照 |
| `risk_score`, `risk_level` | 触发时风险快照 |
| `deduplication_key` | 去重键 |
| `triggered_at`、确认/解决/抑制字段 | 生命周期时间与操作人 |
| `failure_reason` | 安全错误摘要 |

三个业务关联外键只指向 `foreign_*` 表，并有“至少存在一个业务目标”的 CheckConstraint。状态、严重度、规则、时间、去重键和外网对象字段均有索引。历史记录不依赖国内 `alerts`、`events`、`event_opinions` 或 `opinions`。

### 4.3 `foreign_alert_runs`

记录 `run_type`、运行状态、起止时间、处理数、触发数、去重数、抑制数、失败数、错误摘要、创建人和创建时间。状态为 `running`、`success`、`dry_run` 或 `failed`，用于追溯每次显式评估。

### 4.4 往返验证与回滚

在独立测试库执行并通过：

```text
foreign_source_3a -> foreign_source_3b -> foreign_source_3c upgrade
检查外网告警表、索引、外键和约束
foreign_source_3c -> foreign_source_3b downgrade
再次 upgrade 到 foreign_source_3c
```

回滚只删除本阶段三张 `foreign_alert_*` 表及本阶段权限，不触碰国内表或默认库数据。生产库禁止执行 downgrade。

## 5. ForeignAlertService

`ForeignAlertService` 是唯一业务评估边界。它只读取：

```text
foreign_opinions
foreign_risk_results
foreign_events
foreign_event_opinions
foreign_alert_rules
```

它只写入 `foreign_alerts` 和 `foreign_alert_runs`，不导入或调用国内 `AlertService`，不创建 `Opinion`，不写入 `alerts`、国内 `events` 或 `event_opinions`。服务没有被采集服务或 scheduler 导入，评估只能由显式 API 或测试调用触发。

### 5.1 首期规则

已实现：

1. 风险分阈值：`risk_score >= conditions.threshold`。
2. 风险等级：风险等级属于 `conditions.levels`。
3. 风险类别：风险类别属于 `conditions.categories`。
4. 已确认事件：仅 `event_status=confirmed`，并按 `heat_score_min`、`opinion_count_min` 组合判断。
5. 关键词组合：必须同时具备独立监测词和独立风险词命中，必要时再叠加风险等级。

风险结果只取当前、`analysis_status=completed` 的记录。没有风险结果、结果未完成或分析失败的文章不会触发依赖风险结果的正式告警，保持保守策略。候选事件不会触发事件规则；仅命中 `中国`、`Chinese` 或 `China` 的监测词不会触发高风险告警；外网监测词、风险词和国内词表没有交叉读取。

所有新建规则默认关闭，API 拒绝以启用状态创建新规则。规则启停、管理和评估通过独立 `foreign:alerts:*` 权限控制。未批准的生产规则没有被播种，测试使用本地 fixture 规则。

### 5.2 去重和冷却

去重键由规则、文章/事件、来源、时间桶和 `rule_version` 组成，默认模板为：

```text
rule:{rule_id}:opinion:{opinion_id}:event:{event_id}
```

冷却窗口使用 `cooldown_seconds`。同一去重键在冷却窗口内只计入 `deduplicated_count`，不产生新告警；重复评估和重复采集不会制造重复告警。同一事件的事件级规则使用事件键，避免多文章形成告警风暴。规则快照和消息快照写入历史告警，规则后续修改不改变既有告警内容。

首期不发送升级通知、不做外部通知重试、不做自动恢复广播；确认、解决、抑制均为幂等状态操作，抑制时间和操作人保留。规则评估的单规则异常通过嵌套事务隔离，写入 `foreign_alert_runs` 的失败统计和安全错误摘要；不会删除原文章或已有告警。

## 6. API 与权限

已提供：

| API | 用途 | 权限 |
|---|---|---|
| `GET /api/foreign/alerts` | 列表、分页、排序、筛选 | `foreign:alerts:read` |
| `GET /api/foreign/alerts/{id}` | 告警详情 | `foreign:alerts:read` |
| `GET /api/foreign/alert-rules` | 规则列表 | `foreign:alerts:rules:read` |
| `POST /api/foreign/alert-rules` | 创建默认关闭规则 | `foreign:alerts:rules:write` |
| `PATCH /api/foreign/alert-rules/{id}` | 修改规则 | `foreign:alerts:rules:write`，启停另需 enable 权限 |
| `POST /api/foreign/alerts/{id}/acknowledge` | 确认 | `foreign:alerts:acknowledge` |
| `POST /api/foreign/alerts/{id}/resolve` | 解决 | `foreign:alerts:resolve` |
| `POST /api/foreign/alerts/{id}/suppress` | 抑制 | `foreign:alerts:suppress` |
| `POST /api/foreign/alerts/evaluate` | 有界手动评估/Dry-Run | `foreign:alerts:evaluate` |
| `GET /api/foreign/alert-runs` | 运行日志 | `foreign:alerts:read` |

告警列表支持按状态、严重度、规则、来源、外网事件、外网文章和触发时间筛选，限制分页大小和评估最大处理量为 200。未认证请求被拒绝；管理操作由现有认证、权限和 `audit_write` 审计机制保护。错误响应使用稳定摘要，不返回堆栈、密码、Token、代理配置或连接串。

API 不调用 `/api/alerts/*`，也不返回国内告警、事件或文章数据。`evaluate` 是手动入口，默认 `dry_run=true`，不会被采集流程或自动调度调用。

## 7. 前端入口

`frontend/src/views/ForeignWorkspace.vue` 增加 `/foreign?tab=alerts`：

- 只调用 `/api/foreign/alerts`、`/api/foreign/alert-rules` 和 `/api/foreign/alert-runs` 对应的外网命名空间。
- 展示标题、严重度、状态、规则、关联文章、关联事件、风险分/等级、触发/确认/解决时间和抑制状态。
- 明确显示“告警评估默认关闭”“外部通知默认关闭”“当前仅保存站内记录”。
- 支持有权限用户确认、解决和抑制。
- 展示失败运行的失败状态、时间和安全错误摘要。
- 对 loading、empty、processing、failed、disabled 有独立显示路径。

国内 `Alerts.vue`、Dashboard、Events 和 Opinions 页面没有改动其查询逻辑。

## 8. 通知边界

本阶段只落库站内 `foreign_alerts` 记录，不实现也不调用邮件、短信、企业微信、钉钉、WebSocket 外部发送器或其他真实通知渠道。没有新增通知密钥、Token、代理配置或外部消息记录。未来如增加通知，应新建或明确隔离 `foreign_notification_records`，携带 `foreign` scope、重试上限、错误摘要和消息快照，并继续禁止复用国内 `alert_records` 的发送语义。

## 9. 测试与隔离结果

### 9.1 外网聚焦回归

```text
pytest backend/tests/test_foreign_source_phase1.py ... Phase 1.1/3A/3B/3C 相关测试 -q
40 passed
```

新增 Phase 3C 测试单独结果：

```text
pytest backend/tests/test_foreign_source_3c.py -q
5 passed
```

覆盖风险分规则、确认事件规则、候选事件不触发、监测词与风险词隔离、禁用规则、去重/冷却、状态幂等、失败运行审计、未认证拒绝、API 外网隔离和前端接口契约。

### 9.2 编译与前端构建

```text
python -m compileall backend/app backend/tests
PASS

cd frontend
npm run build
PASS
```

### 9.3 国内回归

国内聚焦回归结果：

```text
54 passed, 5 failed
```

5 条失败均为既有基线问题，本阶段未修改国内代码、测试断言或数据：

| 测试 | 分类 |
|---|---|
| `test_event_orm_persist` | 历史断言与当前 `Event.status` 模型不一致 |
| `test_same_keyword_one_event` | 历史事件标题选择语义与当前实现不一致 |
| `test_api_aggregate` | 历史测试期望同步聚合，当前 API 返回异步 `task_id` |
| `test_api_list_pagination` | 依赖上述历史同步聚合行为 |
| `test_4_viewer_forbidden` | 测试库缺少 `viewer` 角色 fixture |

未发现由 3C 外网告警实现引入的国内真实回归。

隔离断言结果：

| 断言 | 结果 |
|---|---|
| 外网告警不写入国内 `alert_records` | PASS |
| 外网告警只关联 `foreign_*` | PASS |
| candidate 不触发正式告警 | PASS |
| 禁用规则不触发新告警 | PASS |
| 重复去重和 cooldown 生效 | PASS |
| 告警确认/解决幂等 | PASS |
| 失败运行留痕 | PASS |
| 自动调度不调用外网评估 | PASS |
| 外部通知调用次数 | 0 |
| 国内风险、事件、Dashboard、地图、热词链路 | 未接入 |

## 10. 临时数据与生产数据

Phase 3C 测试产生的 `foreign_alert_rules`、`foreign_alerts` 和 `foreign_alert_runs` 临时记录已从独立测试库清理。没有清空或删除 `foreign_opinions`、`foreign_risk_results` 或采集日志。

默认 `opinion_db` 未执行 3C migration，未写入或修改任何数据；三个生产外网源仍 disabled，`schedule_enabled=false`，没有启动采集、自动评估或自动调度。

## 11. 已知限制与进入条件

当前首期实现仍有以下明确边界：

1. 规则默认关闭，生产规则未播种；进入生产前必须完成业务审批和独立小型验收。
2. 只有显式手动评估可运行，自动评估和 scheduler 集成未开启。
3. 只有站内记录，外部通知渠道及其重试、升级、双语模板尚未实现。
4. 风险结果不存在或失败时不会触发依赖风险结果的告警；需要业务确认是否长期采用该保守策略。
5. 来源健康告警未纳入本期评估，避免把采集运行日志混入内容风险告警链路。
6. 国内聚焦回归的 5 条历史基线失败仍需另行治理，不得作为本阶段掩盖或修改对象。

进入 3C 小型告警结果验收前，必须在临时库验证更多真实业务组合：规则启停、confirmed 事件、candidate 隔离、冷却窗口、同事件多文章、确认/解决/抑制权限、失败运行恢复和国内告警快照不变。

## 12. 最终声明

- 未修改国内风险、事件、告警、Dashboard、地图、热词链路。
- 未写入国内 `opinions` 或 `alert_records`。
- 未写入生产数据库，默认 `opinion_db` 未迁移。
- 未启用生产外网源。
- 未启用自动调度。
- 未启用自动告警评估。
- 未执行真实外网采集。
- 未调用外部 AI、代理或境外节点。
- 未发送邮件、短信、企业微信、钉钉或其他外部通知。
- 外网告警仅在独立测试库中使用本地 fixture 验证。
- Phase 3C 实施聚焦验收：**通过**。
- 是否允许进入 Phase 3C 小型告警结果验收：**允许**。
