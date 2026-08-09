# Phase Foreign-Source-5A 至 5E 实施报告

## 1. 执行信息

- 执行时间：2026-08-08（Asia/Shanghai）
- 执行范围：仅隔离测试库 `opinion_test`
- 测试库目标：`127.0.0.1:5433/opinion_test`
- 当前 Alembic revision：`foreign_source_5a`
- 目标 revision：`foreign_source_5a`
- 生产数据库：`opinion_db`，已完成只读审计，未迁移、未修改
- 生产 Alembic revision：`foreign_source_3c_remediation`
- 生产外网源：Fox News、The Guardian、纽约时报中文网均为 `enabled=true`、`schedule_enabled=false`、`fetch_full_text=false`
- 生产外网数据快照：`foreign_opinions=8`、`foreign_risk_results=8`、`foreign_events=0`、`foreign_alerts=0`、`foreign_alert_rules=0`、`foreign_keywords=3`
- 生产国内数据快照：`opinions=1702`、`events=292`、`event_opinions=567`、`alert_records=37`

本阶段遵守目标文件中的生产门禁。生产仅执行只读审计；未执行生产 migration、规则启用、真实 RSS、真实 AI 或真实告警评估。

## 2. 当前缺口与实施内容

### 5A：详情与双研判

- 新增 `foreign_ai_results`，AI 结果与规则风险结果分离保存。
- 外网详情 API 返回文章、规则结果、当前 AI 结果和分析运行历史。
- 新增外网专用 AI API 权限 `foreign:ai:analyze`。
- AI 复用 `DeepSeekProvider`，生产环境默认由 `FOREIGN_AI_REVIEW_ENABLED` 关闭；测试使用 mock，不访问真实 AI。
- 外网列表和风险列表均进入完整外网详情弹窗。

### 5B：关键词管理

- `foreign_keywords` 新增 `type`、`source`、`weight`、`severity_weight`、`rule_config` 和索引。
- 支持分页、搜索、主题/类型/启用状态筛选、新增、编辑、启停、删除、批量启停和主题选项。
- 唯一约束冲突返回 409；外网关键词服务只访问 `foreign_keywords`。
- 监测关键词仍由 `foreign_keywords` 驱动采集匹配；风险词仍由 `foreign_risk_terms` 驱动规则分析，两个页面不共享同一可变字段。

### 5C：数据源管理

- 外网数据源列表只接受 `config_json.is_foreign=true` 的记录。
- 新增前必须执行 RSS/HTTP/XML 探测；探测不写入 `foreign_opinions`、`opinions`、`collector_runs` 或下游表。
- 外网采集器强制使用 `foreign_rss`，正文抓取强制关闭，调度字段强制保持手动模式。
- 支持源编辑、启停、RSS 配置、超时、重试、最大条数、robots 开关、手动测试和 scope=foreign 的采集历史。
- 探测和采集错误只返回安全摘要，不返回代理地址、密码、Token 或原始敏感异常。

### 5D：事件链路

- 外网候选、候选详情、人工确认/拒绝、事件详情、关联文章、风险结果、合并、拆分、关闭和操作历史均使用 `foreign_*` 表。
- 同语言相似文章才进入候选；候选默认不自动确认。
- 合并、拆分和状态操作会重新计算文章数、来源数、首末时间、热度和风险等级。
- 运行失败记录限定 `scope=foreign`，错误摘要经过脱敏。

### 5E：告警链路

- 支持五种规则类型：`risk_score`、`risk_level`、`risk_category`、`confirmed_event`、`keyword_combo`。
- 规则定义校验、冷却、去重、列表、详情、处置历史、确认、解决、抑制和非法状态转换均已实现。
- 新规则默认停用；前端不自行创建业务阈值，真实评估仍需人工确认。
- 告警、处置和运行记录只写 `foreign_alerts`、`foreign_alert_actions`、`foreign_alert_runs`。
- 不实现外部通知；没有邮件、短信、Webhook 或其他通知调用。

### 实施文件与权限

- 后端 API：`backend/app/api/foreign.py`、`foreign_events.py`、`foreign_alerts.py`、`foreign_visualization.py`。
- 后端服务：`foreign_ai_service.py`、`foreign_collection_service.py`、`foreign_event_service.py`、`foreign_alert_service.py`、`foreign_visualization_service.py`。
- 外网模型：`foreign_ai_result.py`、`foreign_event*.py`、`foreign_alert*.py`、`foreign_risk_result.py`、`foreign_keyword.py`。
- 前端入口：`frontend/src/views/ForeignWorkspace.vue`，所有外网请求使用 `/foreign/*`。
- 外网权限按文章、风险、AI、关键词、数据源、事件和告警分别校验；既有 3A/3B/3C 权限与本阶段新增权限均在隔离 migration 中验证。

## 3. Migration 验证

Migration 文件：

- `backend/alembic/versions/foreign_source_5a.py`
- down revision：`foreign_source_3c_remediation`
- 新增 `foreign_keywords` 管理字段及索引。
- 新增 `foreign_ai_results`、约束和索引。
- 新增外网专用权限；既有 3A/3B/3C 外网权限保持不变。
- 新增外网告警 `(rule_id, deduplication_key)` 唯一去重索引。

隔离库实际执行结果：

```text
upgrade  foreign_source_3c_remediation -> foreign_source_5a  PASS
downgrade foreign_source_5a -> foreign_source_3c_remediation PASS
upgrade  foreign_source_3c_remediation -> foreign_source_5a  PASS
current  foreign_source_5a
heads    foreign_source_5a
```

往返后确认 `foreign_keywords` 新字段和 `foreign_ai_results` 物理表存在。严格快照断言确认国内 `opinions`、`events`、`event_opinions`、`alert_records` 前后相等，且 `foreign_keywords(id, word, category, is_enabled)` 前后相等。生产 migration 未执行。

## 4. 隔离证据与快照

隔离测试库往返后快照：

| 表 | 行数 |
|---|---:|
| `opinions` | 2 |
| `events` | 0 |
| `event_opinions` | 0 |
| `alert_records` | 0 |
| `foreign_keywords` | 3 |
| `foreign_opinions` | 18 |
| `foreign_risk_results` | 0 |
| `foreign_events` | 0 |
| `foreign_alerts` | 0 |
| `foreign_ai_results` | 0 |

外网聚焦测试在每个写入场景前后比较国内表，未发现国内 opinions、events、event_opinions 或 alert_records 变化。外网 API 不接受国内 opinion/event/alert ID 越权读取，外网页面只调用 `/api/foreign/*`。

测试库的三个种子外网源保持 `enabled=false`、`schedule_enabled=false`，配置为 `foreign_rss`、`is_foreign=true`，正文抓取保持关闭。测试中的 RSS 探测使用 mock，不访问真实 RSS。生产只读审计确认三个源当前已启用人工采集，但未执行本阶段的生产采集操作。

数据源运行历史当前仍按 `collector_name` 关联。若未来出现同名来源或来源重命名，历史可能产生歧义；后续可增加 `source_id`/`source_key` 快照并在隔离环境验证后再评估生产迁移，不在本阶段直接修改生产表。

### 5D 隔离真实验收

- 使用四篇隔离外网文章生成同语言候选，先完成 dry-run，再持久化候选并人工确认正式事件。
- 两个正式事件合并后，文章数、来源数、首末时间、热度和风险等级按关联文章重算；随后拆出两篇文章形成新事件，原事件和新事件指标均重算正确。
- 合并、拆分操作均写入 `foreign_event_actions`，运行范围为 `scope='foreign'`；国内 `opinions`、`events`、`event_opinions` 快照保持不变。

### 5E 隔离真实验收

- 在隔离库以 `dry_run=false` 执行风险分数和已确认事件规则，至少一条规则命中并写入 `foreign_alerts`。
- 重复评估命中同一去重键时计入 `deduplicated_count`，不产生第二条告警；冷却和停用规则均不误触发。
- 告警确认、解决、抑制、非法状态转换、并发锁和事务失败回滚均已验证；处置备注、前状态、后状态、操作人和操作时间写入 `foreign_alert_actions`。
- 隔离验收未写入国内 `alert_records`，未调用任何外部通知渠道。

## 5. 测试结果

执行命令覆盖：

```text
python -m compileall -q backend/app backend/tests                  PASS
python -m pytest -q [外网 3A-3D、修复回归、5A-5E 聚焦测试]           166 passed
npm run build                                                        PASS
```

新增聚焦测试：

- 外网详情和 mock AI 成功写入 `foreign_ai_results`，不写国内表。
- RSS 探测返回 HTTP/XML/条数/命中信息且零写入。
- RSS 探测失败时不回显密码、代理地址、Token 或敏感异常原文。
- 外网关键词 CRUD、批量状态、唯一约束冲突。
- 告警规则启用门禁和新规则默认停用。
- 事件候选、人工确认、合并、拆分、指标重算和国内事件快照隔离。
- 告警真实评估、去重、冷却、确认/解决/抑制、并发控制和事务回滚。
- 既有 3A、3B、3C、3D 事件/告警/可视化隔离回归。

构建仅有既有 Vite chunk warning 和依赖注释 warning，无构建失败。

## 6. 未完成事项和风险

- 未执行生产 migration，因此生产仍需在单独审批、备份和停写窗口后迁移到 `foreign_source_5a`。
- 未执行真实生产 RSS；没有对外网访问限制、代理可用性或真实源内容作生产结论。
- 未执行真实 AI；生产 AI 开关保持关闭，测试结果为 mock 结果。
- 未在生产创建、启用或真实评估外网告警规则；本阶段仅完成隔离库能力和验证。
- 地图仍未实现，外网 Dashboard 继续使用来源分布和语言分布。
- 迁移往返证明 schema 可回滚/重做，但不构成生产直接 downgrade 方案。

## 7. 生产迁移与外网源启用步骤

生产后续步骤必须由人工单独确认：

1. 备份并校验 `opinion_db`，核对 `alembic current/heads`，确认国内数据快照。
2. 在隔离库结果通过后执行 `alembic upgrade foreign_source_5a`，检查 foreign 表、权限、告警去重索引和国内数据快照。
3. 迁移成功后核对 Fox News、The Guardian、纽约时报中文网的 feed、关键词、采集器、代理环境变量、`fetch_full_text=false` 和 `schedule_enabled=false`。
4. 取得单独的外网源启用确认后，仅允许人工采集；保持国内 scheduler、全局配置和外网自动调度不变。
5. 逐个手动采集并记录 HTTP/RSS/XML、原始条数、关键词命中、新增、重复、失败、`scope='foreign'`、代理状态和国内快照。
6. 取得单独确认后，才可在生产进行人工风险、事件或告警评估；本阶段不执行这些生产操作。

本阶段生产只读审计显示三个源已经是 `enabled=true`、`schedule_enabled=false`、`fetch_full_text=false`，因此没有重复修改生产源配置。

## 8. 生产回滚方式

发生问题时优先恢复备份或执行前向修复 migration；不得把直接生产 downgrade 当作默认回滚方案。隔离环境已验证的技术回退命令为 `alembic downgrade foreign_source_3c_remediation`，但不能替代生产备份恢复流程。

## 9. 结论

5A–5E 的代码、隔离 migration、前端构建和外网聚焦测试已完成。当前**不允许进入 Phase 6 外网自动化建设**，也不构成生产人工上线通过；必须先完成生产迁移审批、真实 RSS/人工采集验收、人工风险/事件/告警验收和生产前后快照记录。
