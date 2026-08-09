# Phase Foreign-Source-4C + 4D + 4E 生产人工上线报告

## 1. 执行摘要

- 执行时间：2026-08-08 17:28:48 +08:00
- 数据库：`opinion_db`
- 生产 migration：已执行并成功到达 `foreign_source_3c_remediation`
- 三个外网源：已启用人工采集，自动调度保持关闭
- 外网正文抓取：保持关闭，`fetch_full_text=false`
- 外网风险：8/8 条规则分析成功
- 外网事件：候选重建 dry-run 成功，未自动确认或物化正式事件
- 外网告警：无规则；dry-run 成功，未生成告警
- 外部通知：未发送
- 结论：**人工上线门禁通过；不允许进入下一阶段自动化建设**

## 2. 生产迁移

### 2.1 版本核对

实际执行 `alembic current` 和 `alembic heads`，结果均为：

```text
foreign_source_3c_remediation (head)
```

迁移链：

```text
p32_mediacrawler_keyword_cursor
  -> foreign_source_1
  -> foreign_source_3a
  -> foreign_source_3b
  -> foreign_source_3c
  -> foreign_source_3c_remediation
```

迁移文件：

- `backend/alembic/versions/foreign_source_1.py`
- `backend/alembic/versions/foreign_source_3a.py`
- `backend/alembic/versions/foreign_source_3b.py`
- `backend/alembic/versions/foreign_source_3c.py`
- `backend/alembic/versions/foreign_source_3c_remediation.py`

### 2.2 结果

已验证外网表、索引、约束和权限存在。主要新增对象包括：

- `foreign_keywords`、`foreign_opinions`
- `foreign_risk_terms`、`foreign_analysis_runs`、`foreign_risk_results`
- `foreign_event_candidates`、`foreign_events`、`foreign_event_opinions`
- `foreign_event_runs`、`foreign_event_actions`
- `foreign_alert_rules`、`foreign_alerts`、`foreign_alert_runs`
- `foreign_alert_actions`
- `collector_runs.scope`、`collector_runs.proxy_used` 及相关索引

生产备份状态：已完成当前生产库备份并验证可读。备份位于工作区外临时目录：

```text
C:\Users\Administrator\AppData\Local\Temp\yq-foreign-source-4c-backup\opinion_db_20260808_foreign_source_4c.dump
```

- 文件大小：2,337,156 bytes
- SHA-256：`8da4ca6ad5f0b5dc3fee43c756c2ce5f3dd4afc590c4c01871423d7b1018ee33`
- `pg_restore --list`：419 个可读条目

该备份是在迁移和人工灰度操作完成后生成的当前状态快照，不等同于迁移前恢复点；迁移前备份时序证据仍属于变更记录遗留风险。

未执行生产 downgrade。生产回滚不得使用直接 downgrade 删除外网表，必须使用经过验证的数据库备份或快照恢复。

## 3. 三个来源配置

| 来源 | RSS feed | class_path | 关键词 | enabled | schedule_enabled | proxy_used | fetch_full_text |
|---|---|---|---|---:|---:|---:|---:|
| Fox News | `https://moxie.foxnews.com/google-publisher/world.xml` | `app.collectors.foreign_rss.ForeignRSSCollector` | 中国、Chinese、China | true | false | false | false |
| The Guardian | `https://www.theguardian.com/world/rss` | `app.collectors.foreign_rss.ForeignRSSCollector` | 中国、Chinese、China | true | false | false | false |
| 纽约时报中文网 | `https://cn.nytimes.com/rss/` | `app.collectors.foreign_rss.ForeignRSSCollector` | 中国、Chinese、China | true | false | false | false |

全局配置保持不变：

- `collector_schedule_enabled=True`
- `alert_eval_enabled=True`
- `collector_schedule_mode=per_source`

国内 scheduler 仍排除 `is_foreign=true` 和 `foreign_rss` 数据源。外网风险、事件、告警均未接入自动 scheduler。

## 4. 人工采集结果

本次真实 RSS 访问按 Fox News、The Guardian、纽约时报中文网顺序逐个执行。

| 来源 | run id | RSS/HTTP | 原始条数 | 关键词命中 | 新增 | 重复 | 失败 | scope | proxy_used |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| Fox News | 16047 | success | 25 | 0 | 0 | 0 | 0 | foreign | false |
| The Guardian | 16048 | success | 45 | 1 | 0 | 1 | 0 | foreign | false |
| 纽约时报中文网 | 16049 | success | 20 | 5 | 5 | 0 | 0 | foreign | false |

`foreign_opinions` 当前共 8 条，其中本次纽约时报中文网新增 5 条。正文抓取保持关闭，没有访问 RSS 正文页面。

Fox News 本次请求成功但关键词命中为 0，按既定策略保留成功零命中结果，没有扩大关键词范围或绕过访问限制。

## 5. 外网风险分析

执行方式：规则分析器 `foreign-rule-engine`，版本 `foreign-risk-v1`，批量处理 8 条文章。

- `foreign_analysis_runs.id=1`
- 状态：`success`
- 处理：8
- 成功：8
- 失败：0
- 写入：仅 `foreign_risk_results`
- AI 外发：关闭
- 国内风险表：未写入

8 条结果均为：

- `analysis_status=completed`
- `risk_score=20`
- `risk_level=low`
- `risk_category=none`
- `matched_terms=[]`

这表示当前已配置的外网风险词未命中；采集关键词“中国/Chinese/China”没有被当作风险词使用。

## 6. 外网事件处理

执行 `ForeignEventService.rebuild_candidates(dry_run=true)`：

- `foreign_event_runs.id=1`
- 状态：`dry_run`
- 输入文章：8
- 去重后：7
- 候选数：1
- 关联文章数：2
- 候选置信度：0.49
- 来源数：1
- 正式事件创建数：0
- 自动确认：0

候选仅保留在 dry-run 预览中，没有创建 `foreign_event_candidates`、`foreign_events` 或 `foreign_event_opinions` 数据。没有写入国内 `events` 或 `event_opinions`。

当前阶段没有人工确认样本，因为唯一候选置信度较低且 dry-run 明确不物化事件。正式事件人工确认仍需后续业务人员选择候选并显式确认。

## 7. 外网告警

当前 `foreign_alert_rules` 数量为 0，未自行创建或启用规则。

执行 `ForeignAlertService.evaluate(dry_run=true)`：

- `foreign_alert_runs.id=1`
- 状态：`dry_run`
- 处理数：0
- 触发数：0
- 去重数：0
- 失败数：0
- `foreign_alerts` 写入数：0

没有执行真实告警评估，没有创建外网告警，没有发送短信、邮件、Webhook 或其他外部通知。告警处置备注、前后状态和操作历史将在存在明确业务规则并获批准进行真实评估后验收。

## 8. Dashboard、热词和来源分布

外网可视化服务只读查询已验证通过：

- `/api/foreign/dashboard/summary`
- `/api/foreign/dashboard/trends`
- `/api/foreign/dashboard/risk`
- `/api/foreign/dashboard/events`
- `/api/foreign/dashboard/alerts`
- `/api/foreign/dashboard/sources`
- `/api/foreign/hotwords`
- `/api/foreign/hotwords/trends`
- `/api/foreign/source-distribution`
- `/api/foreign/language-distribution`

7 天窗口结果：

- 外网文章总数：8
- 外网来源数：3 个真实来源，另含 2 个既有 fixture 来源记录
- 风险完成：8
- 正式事件：0
- 外网告警：0
- 语言分布：英文 3、混合 5、中文 0、未知 0

已修复外网趋势接口在滚动窗口跨自然日时的日期桶 `KeyError`，修复范围仅限 `backend/app/services/foreign_visualization_service.py`，未修改国内 Dashboard 服务。

前端 `ForeignWorkspace.vue` 的可视化请求均使用 `/api/foreign/*`。未发现调用国内 Dashboard、国内热词或国内地图 API。外网地图本阶段未实现，页面继续使用来源分布和语言分布替代。

## 9. 国内数据前后快照

生产库当前快照：

| 表 | 数量 | 内容摘要 |
|---|---:|---|
| `opinions` | 1702 | 前后摘要一致 |
| `events` | 292 | 前后摘要一致 |
| `event_opinions` | 567 | 前后数量一致 |
| `alert_records` | 37 | 前后摘要一致 |

已在采集后、风险分析后、事件 dry-run 后和告警 dry-run 后复核。外网数据没有污染国内 opinions、风险、事件、告警、Dashboard、热词或地图链路。

## 10. 测试与构建

- 外网聚焦测试：160 passed
- 国内风险、可见性和 Dashboard 回归：26 passed
- 本次 `backend/app` 纯内存 Python 编译：173/173 通过
- 前端 Vite 生产构建：通过，输出到工作区外临时目录
- 测试库连接修正：测试夹具默认使用 `localhost:5433`，本机服务监听 `127.0.0.1:5433`；通过 `DATABASE_URL` 命令级覆盖后完整外网套件通过，未修改测试文件
- 工作区已有临时脚本 `_fixnav.py`、`rewrite_al.py` 存在历史语法错误，未修改
- 既有国内 baseline 测试失败项未修改，包括 datasource schedule 默认约束、collector response contract、event model status 断言和 alert viewer 角色夹具

## 11. 失败项与遗留风险

1. 当前备份是迁移后快照，不是迁移前恢复点；生产数据库恢复演练仍未完成。
2. `foreign_opinions` 中保留两个既有 `fixture_*` 测试来源记录，来源分布因此显示 5 个分组；本阶段未删除既有数据。
3. 外网风险词当前没有命中，风险结果仅验证规则链路可写入，尚未验证中高风险分类效果。
4. 生产事件只完成候选 dry-run，未对低置信度候选执行正式确认；隔离测试已验证人工确认、文章数、来源数、时间和热度指标。
5. 外网没有业务告警规则，未执行真实告警评估；隔离测试已验证规则匹配、去重和处置状态链路。
6. 三个来源的授权、robots、访问频率、代理/境外节点责任和正文保存边界仍需业务、合规和网络负责人确认。
7. 外网地图尚未实现。

## 12. 回滚方式

### 业务回滚

立即停止人工采集，并将三个来源设置为：

```text
enabled=false
schedule_enabled=false
fetch_full_text=false
```

保留运行日志和外网样本，不直接删除或清空外网数据；保持国内全局调度和告警配置不变。

### 数据库回滚

不得将 `alembic downgrade` 作为生产常规回滚方式，因为 3A/3B/3C downgrade 会删除外网表及数据。生产数据库回滚必须使用已验证的备份或快照恢复，并在恢复后核对国内快照和 Alembic revision。

当前已有可读的迁移后快照，但没有迁移前恢复点；数据库级回滚仍必须由 DBA 使用经过批准的恢复点执行，不得直接 downgrade。

## 13. 下一阶段准入

**人工阶段通过，但自动化准入不通过。**

在进入自动化前，必须补齐：

- 迁移前恢复点补证或 DBA 恢复演练证据；
- 事件正式确认样本；
- 事件人工确认样本；
- 明确且审批后的外网告警规则；
- 真实告警评估与站内处置闭环；
- 来源授权、robots、频率、代理和正文策略审批；
- 责任人、值班和熔断机制；
- 至少 24-72 小时人工观察窗口。
