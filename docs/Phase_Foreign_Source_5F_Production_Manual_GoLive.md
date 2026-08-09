# Phase Foreign-Source-5F 生产人工上线报告

## 1. 执行摘要

- 执行日期：2026-08-08（Asia/Shanghai）
- 数据库：`opinion_db`
- 生产 revision：`foreign_source_5a`，与 `alembic heads` 一致
- 生产备份：已完成并通过 `pg_restore --list` 验证
- 三个外网源：`enabled=true`、`schedule_enabled=false`
- 外网正文抓取：`fetch_full_text=false`
- 真实 RSS：三个来源均已人工访问并采集成功
- 外网规则风险：8 条文章均有当前规则结果；本次复评按内容版本幂等跳过重复写入
- 外网事件：候选重建 dry-run 完成，无合格的高置信生产候选，无正式事件
- 外网告警：无生产规则；dry-run 完成，无告警，无外部通知
- 结论：**Phase 5F 生产人工上线通过；不允许进入 Phase 6 自动化建设**

本报告明确区分真实生产操作、dry-run、幂等跳过和隔离测试结果。AI 复核、自动采集、自动风险、自动事件、自动告警和外部通知均未执行。

## 2. 生产迁移

### 2.1 备份和版本

生产备份：

```text
C:\Users\Administrator\Desktop\YQ\runtime\foreign_source_5f\opinion_db_before_foreign_source_5a_20260808_222958.dump
```

- 文件大小：2,339,243 bytes
- SHA-256：`6A859256E9E89C6DCCF6CD223AED0F5A8628E274C7C15C80B3394F14CFA596B8`
- `pg_restore --list`：通过

实际生产迁移：

```text
foreign_source_3c_remediation -> foreign_source_5a
alembic current              -> foreign_source_5a
alembic heads                -> foreign_source_5a (head)
```

目标 migration 文件及依赖链：

- `backend/alembic/versions/foreign_source_1.py`
- `backend/alembic/versions/foreign_source_3a.py`
- `backend/alembic/versions/foreign_source_3b.py`
- `backend/alembic/versions/foreign_source_3c.py`
- `backend/alembic/versions/foreign_source_3c_remediation.py`
- `backend/alembic/versions/foreign_source_5a.py`

已核验：`foreign_ai_results` 表、`foreign_keywords` 的 5 个管理字段及索引、外网权限/admin 关联、外网告警去重唯一索引均存在。未执行生产 downgrade，未修改国内表结构。

## 3. 前端发布和服务

已授权发布的 plain Vite 包：

```text
C:\Users\Administrator\Desktop\YQ\frontend\_phase5f_plain_build_20260808
```

- 44 个文件逐项 SHA-256 与发布目标匹配
- `index.html` SHA-256：`4DF18B029590A33E2B50936BAB455A86129DB4472AE8863B1E7E64F79F3FB83B`
- 新版 `ForeignWorkspace` JS/CSS 已落入 `backend\app\static\assets`
- 原生产静态目录备份：`backend\app\static.bak.5f_publish_20260808_230251`
- 未删除旧静态资源；入口已指向新版资源

已重启且仅针对 8000 Uvicorn：

- 新父进程：43972
- 新工作进程：4784
- 监听：`0.0.0.0:8000`
- `/health`：HTTP 200，`collector_discovery=db_driven`

验收期间发现并修复一个外网 Dashboard 缺陷：热词趋势将 `(word, language)` 元组作为 JSON 键，导致 HTTP 500；已改为使用字符串词键，重新编译、重启并验证 `/api/foreign/hotwords/trends` 返回 HTTP 200。修改范围仅为 `backend/app/services/foreign_visualization_service.py`，并新增外网回归测试。

## 4. 三个来源配置

| 来源 | RSS feed | class_path | 关键词 | enabled | schedule_enabled | proxy_used | fetch_full_text |
|---|---|---|---|---:|---:|---:|---:|
| Fox News | `https://moxie.foxnews.com/google-publisher/world.xml` | `app.collectors.foreign_rss.ForeignRSSCollector` | 中国、Chinese、China | true | false | false | false |
| The Guardian | `https://www.theguardian.com/world/rss` | `app.collectors.foreign_rss.ForeignRSSCollector` | 中国、Chinese、China | true | false | false | false |
| 纽约时报中文网 | `https://cn.nytimes.com/rss/` | `app.collectors.foreign_rss.ForeignRSSCollector` | 中国、Chinese、China | true | false | false | false |

代理配置只记录环境变量名 `FOREIGN_HTTP_PROXY`，不记录代理值；本次运行未使用代理。全局配置保持：

- `collector_schedule_enabled=True`
- `alert_eval_enabled=True`
- `collector_schedule_mode=per_source`

## 5. 真实 RSS 人工采集

每个来源使用一次生产 `foreign_rss` 采集请求；未抓取正文。HTTP 200 且 XML 解析成功视为 feed 成功。

| 来源 | collector_run | HTTP/XML | 原始条数 | 关键词命中 | 新增 | 重复 | 失败 | scope | trigger_type | proxy_used |
|---|---:|---|---:|---:|---:|---:|---:|---|---|---:|
| Fox News | 16137 | 200 / 成功 | 25 | 0 | 0 | 0 | 0 | foreign | manual | false |
| The Guardian | 16138 | 200 / 成功 | 45 | 1 | 0 | 1 | 0 | foreign | manual | false |
| 纽约时报中文网 | 16139 | 200 / 成功 | 20 | 5 | 0 | 5 | 0 | foreign | manual | false |

本次没有新增行是因为命中文章已存在于生产 `foreign_opinions`，去重逻辑正常工作。采集后 `foreign_opinions=8`，没有写入国内 `opinions`。

采集证据：

- `runtime/foreign_source_5f/collection_fox_news_20260808.json`
- `runtime/foreign_source_5f/collection_guardian_20260808.json`
- `runtime/foreign_source_5f/collection_nyt_chinese_20260808.json`
- `runtime/foreign_source_5f/production_before_rss_20260808.json`
- `runtime/foreign_source_5f/production_after_rss_20260808.json`

## 6. 外网风险人工验收

执行方式为 `ForeignRiskService` 规则分析，模型版本 `foreign-risk-v1`，未调用 AI。

- 最新分析运行：`foreign_analysis_runs.id=2`
- 状态：`success`
- 处理：8
- 失败：0
- `FOREIGN_AI_REVIEW_ENABLED=false`
- 当前结果：8 条 `completed`、8 条 `low`、风险分均为 20、类别均为 `none`、风险词命中为空
- 本次 `success_count=0` 是内容哈希和模型版本幂等命中既有当前结果后的预期行为；既有 8 条当前结果来自生产规则运行 `id=1`，没有重复插入
- 结果只存在于 `foreign_risk_results`，国内风险链路未调用

## 7. 外网事件人工验收

执行 `ForeignEventService.rebuild_candidates(dry_run=true)`：

- `foreign_event_runs.id=2`
- `scope=foreign`、`trigger_type=dry_run`、状态 `dry_run`
- 输入文章：8；去重后：7
- 候选：1；关联文章：2；来源：1；置信度：0.49
- 正式事件创建：0
- `foreign_event_candidates` 前后均为 0
- `foreign_events` 前后均为 0

该候选低于确认阈值，且本阶段禁止自动确认，因此没有伪造或物化生产事件。没有写入国内 `events` 或 `event_opinions`。

## 8. 外网告警人工验收

生产 `foreign_alert_rules` 数量为 0，因此没有创建、启用或推断业务阈值。

执行 `ForeignAlertService.evaluate(dry_run=true)`：

- `foreign_alert_runs.id=2`
- 状态：`dry_run`
- 处理：0；触发：0；去重：0；抑制：0；失败：0
- `foreign_alerts` 前后均为 0
- 未发送短信、邮件、Webhook 或其他外部通知

告警处置备注、前状态、后状态和操作历史的生产变更没有发生；状态机和处置审计已在隔离 5A-5E 测试中验证。

## 9. Dashboard、热词和来源分布

生产只读 HTTP smoke test 覆盖 12 个外网接口，全部 HTTP 200：

- 外网源、采集运行记录
- Dashboard summary、trends、risk、events、alerts、sources
- 热词、热词趋势
- 来源分布、语言分布

7 天运行结果：文章总数 8、窗口文章 8、风险完成 8、正式事件 0、告警 0；热词返回 30 项、热词趋势返回 8 个日期桶。

`frontend/src/views/ForeignWorkspace.vue` 的外网请求均使用 `/foreign/*`，由前端 API 基址形成 `/api/foreign/*`；未发现调用国内 Dashboard、国内热词或国内地图 API。地图本阶段仍未实现，页面继续使用来源分布和语言分布替代。

## 10. 国内数据隔离

生产 RSS 前后及风险、事件 dry-run、告警 dry-run 后，以下逐行 JSON 摘要均未变化：

| 表 | 行数 | max(id) | SHA-256 |
|---|---:|---:|---|
| `opinions` | 1702 | 2960 | `ab9f0fa67bb00ffbc5cde0b0115e7cc18acb56fe55977de48ec0f0ae068ec0b4` |
| `events` | 292 | 696 | `ab76aba4168a64be5d4b44a3813874cb06d2ca3f9e7dcfdf81eae58a5dfb7848` |
| `event_opinions` | 567 | 1507 | `b5cb184d975517845ca7650de9be6debcc65643e3a14c96e0d05c885c07183c4` |
| `alert_records` | 37 | 138 | `6896fef031dac5e606f9f43347106360eed5fc034ff81358b0bba406c2a2057e` |

采集后的外网运行中，`scope='foreign'` 的最新 3 条均为 `trigger_type='manual'`；手动采集之后没有外网 scheduled run。国内全局开关保持原值。

## 11. 测试和构建

- `python -m compileall -q app tests`：通过
- 外网聚焦测试：`167 passed`
- 新增热词趋势 JSON 键回归测试：通过
- 已验证 Vite plain production build：44 个文件，构建包可读，发布入口与包哈希一致
- 生产静态资源 HTTP smoke：入口、ForeignWorkspace JS/CSS、favicon 均 HTTP 200
- 生产外网 HTTP smoke：12/12 HTTP 200

一次使用 `localhost:5433` 的测试命令因本机 IPv6 解析等待而超时，未作为通过依据；改用已验证的 `127.0.0.1:5433/opinion_test` 后完整外网聚焦测试通过。超时期间启动的 pytest 进程已清理，未停止生产 Uvicorn 或 PostgreSQL。

## 12. 失败项和遗留风险

1. 本次真实 RSS 没有新增文章，只有 Guardian 1 条、纽约时报 5 条命中记录被去重；后续新内容是否持续到达仍需人工观察。
2. 风险复评命中幂等结果，没有新增风险结果行；当前 8 条规则结果有效且已展示。
3. 生产没有外网告警规则和正式事件，因此真实告警处置和正式事件状态变更本次没有生产样本；对应状态机已由隔离测试验证。
4. 代理变量未提供有效值，本次直连成功；未来若访问限制变化，需单独评估代理可用性。
5. 外网地图尚未实现，当前产品能力是来源分布和语言分布。
6. 工作区原有用户修改、临时文件和未跟踪文件均保留，未执行 reset、checkout、clean 或删除操作。

## 13. 回滚方式

### 数据库

优先使用已验证的生产备份恢复，或执行经过隔离验证的前向修复 migration。不得把生产直接 downgrade 作为默认回滚方案。备份恢复点为：

```text
C:\Users\Administrator\Desktop\YQ\runtime\foreign_source_5f\opinion_db_before_foreign_source_5a_20260808_222958.dump
```

### 前端和后端

- 前端静态资源恢复目录：`backend/app/static.bak.5f_publish_20260808_230251`
- 将生产静态目录恢复到备份后，再按已批准的服务窗口重启 8000 Uvicorn
- 仅停止和启动明确属于 8000 Uvicorn 的进程，不影响国内数据库和其他用户进程

## 14. 下一阶段决策

本阶段人工链路已经上线并通过验收，但以下开关必须继续保持：

- 外网源自动调度关闭：`schedule_enabled=false`
- 外网自动风险、自动事件、自动告警关闭
- `FOREIGN_AI_REVIEW_ENABLED=false`
- 外部通知关闭

**不允许进入 Phase 6 自动化建设。** 下一阶段前必须补充明确的外网告警业务阈值、人工事件确认样本、自动化调度审批、AI 成本与数据外发审批，以及外部通知审批。

## 15. 证据索引

- 生产迁移备份：`runtime/foreign_source_5f/opinion_db_before_foreign_source_5a_20260808_222958.dump`
- 采集前快照：`runtime/foreign_source_5f/production_before_rss_20260808.json`
- 采集后快照：`runtime/foreign_source_5f/production_after_rss_20260808.json`
- 风险分析：`runtime/foreign_source_5f/risk_analysis_20260808.json`
- 事件 dry-run：`runtime/foreign_source_5f/event_dry_run_20260808.json`
- 告警 dry-run：`runtime/foreign_source_5f/alert_dry_run_20260808.json`
- 最终生产复核：`runtime/foreign_source_5f/final_production_verification_20260808.json`
- 风险和运行详情：`runtime/foreign_source_5f/final_risk_and_runtime_detail_20260808.json`
