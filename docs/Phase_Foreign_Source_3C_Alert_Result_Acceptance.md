# Phase Foreign-Source-3C
# 小型外网告警结果验收报告

## 1. 验收结论

本阶段在独立测试库完成了外网告警链路的部分结果验收，但未达到全部通过标准。

**最终结论：No-Go，Phase 3C 小型结果验收未通过。**

阻塞原因：确认、解决、抑制接口虽然有独立权限和通用操作日志，但当前不接收或保存备注，也没有在外网告警记录或外网告警操作审计中保存“原状态/新状态”。现有 `OperationLog` 只记录动作、操作者、资源和结果，不能满足本阶段要求的完整人工处置审计。发现该缺陷后停止继续扩展验收，没有修改代码或测试断言。

本阶段只新增本报告文件。没有修复实现缺陷。

## 2. 验收环境与生产保护

### 2.1 默认数据库

已执行：

```text
git status --short
alembic current
```

默认数据库身份已确认：

| 项目 | 结果 |
|---|---|
| 数据库 | `opinion_db` |
| 默认 Alembic revision | `foreign_source_1` |
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| 国内 `alert_records` | 37 |
| `foreign_opinions` | 3 |
| 外网运行中任务 | 0 |

三个外网源只读状态：

| 来源 | `enabled` | `schedule_enabled` |
|---|---:|---:|
| Fox News | false | false |
| The Guardian | false | false |
| 纽约时报中文网 | false | false |

默认库未执行 3C migration、写入、删除、truncate 或 downgrade。已有外网样本和采集日志未删除。

### 2.2 测试数据库

所有 3C 迁移和测试写入使用独立 `opinion_test`，连接到本机测试 PostgreSQL `127.0.0.1:5433`。测试库允许临时 fixture 和 migration 往返，未连接默认生产库进行写操作。

外部通知相关环境变量均未设置：

```text
FOREIGN_ALERT_EVAL_ENABLED=UNSET
FOREIGN_NOTIFICATION_ENABLED=UNSET
FOREIGN_EMAIL_ENABLED=UNSET
FOREIGN_SMS_ENABLED=UNSET
FOREIGN_WEBHOOK_ENABLED=UNSET
```

本阶段没有访问真实 RSS、外部 AI、代理或境外采集节点，没有发送任何通知。

## 3. 测试样本与覆盖范围

已有 `backend/tests/test_foreign_source_3c.py` 使用唯一后缀 fixture，并在测试结束清理。本次实际覆盖的样本和行为包括：

| 样本/行为 | 结果 |
|---|---|
| 高风险外网文章 + completed risk result | 已覆盖 |
| confirmed 外网事件 | 已覆盖 |
| candidate/非 confirmed 事件不触发 | 已由实现测试覆盖 |
| 监测词 `China` 与风险词隔离 | 已覆盖 |
| 禁用规则 | 已覆盖 |
| 错误规则和失败运行 | 已覆盖 |
| 相同文章/规则去重 | 已覆盖 |
| 告警确认、解决幂等 | 已覆盖 |
| 低风险文章 | 本次未单独覆盖 |
| `analysis_status=failed` 的风险结果 | 本次未单独构造 |
| 两篇文章关联同一 confirmed 事件的风暴控制 | 本次未单独覆盖 |
| 冷却窗口结束后的再次触发 | 本次未覆盖 |
| 不同来源但相同内容 | 本次未覆盖 |
| 抑制操作 API 幂等 | 本次未完成 |
| 非管理员权限 API | 本次未完成 |

由于人工处置审计缺陷已构成阻塞，未继续补充未覆盖样本。

## 4. 规则命中验收

已执行的 3C 专项测试验证了：

- 风险分阈值规则可以命中。
- `confirmed_event` 规则可以命中。
- 未确认事件不会触发正式告警。
- 仅由 `中国`、`Chinese` 或 `China` 监测词组成的关键词规则不会直接触发告警。
- 禁用规则不会产生新告警。
- 告警记录保存 `rule_id`、命中条件、外网文章/风险结果/事件关联、去重键、触发时间和规则快照。
- 告警严重度来自外网规则配置。
- 标题、消息和失败摘要没有暴露密码、Token、代理配置或内部堆栈。

风险结果不存在或分析失败时，当前服务仅从 `analysis_status=completed` 且为 current 的风险结果评估风险类规则，符合保守策略；但本次没有针对 failed risk result 构造独立样本，故该条仅作为实现静态结论，不作为完整结果验收通过项。

## 5. 去重与冷却

已验证：

- 相同规则和相同外网文章重复评估不会产生第二条告警。
- 相同去重键会计入 `deduplicated_count`。
- 重复执行评估保持幂等。
- `foreign_alert_runs` 保存处理数、触发数、去重数和失败数。
- 规则版本参与去重键和规则快照。

本次未完成以下要求的独立结果验证：

- 冷却时间结束后重新命中是否产生新告警。
- 同一 confirmed 事件多篇文章是否始终只形成事件级告警。
- 两个不同来源但相同内容的去重策略。

因此去重基础行为可判定为通过，完整 cooldown 验收为未完成。

## 6. 告警状态与人工处置

模型约束支持：

```text
triggered -> acknowledged -> resolved
triggered/acknowledged -> suppressed
failed（运行或告警失败留痕）
```

3C 专项测试已验证服务层确认、解决操作的重复调用保持幂等，失败规则会写入失败运行状态和安全错误摘要。

### 6.1 阻塞缺陷

当前实现存在以下审计缺口：

1. `foreign_alerts` 只有 `acknowledged_by`、`resolved_by`、`suppressed_by` 和对应时间，没有原状态、新状态和备注字段。
2. 当前没有 `foreign_alert_actions` 或等价的外网告警处置明细表。
3. `/api/foreign/alerts/{id}/acknowledge`、`resolve`、`suppress` 没有请求体，不接收备注。
4. API 使用通用 `audit_write` 写入动作日志，但调用时没有传入状态变化或备注详情。
5. 前端只发送空请求并显示操作按钮，没有收集或展示处置备注。

因此无法证明每次操作都保存“操作人、操作时间、操作类型、原状态、新状态、目标告警、原因/备注”。这违反本阶段第八节要求，触发停止条件，人工处置验收判定失败。

## 7. API 验收

已通过的 API/契约检查：

| 检查项 | 结果 |
|---|---|
| 未认证访问 `/api/foreign/alerts` | 401，PASS |
| 外网告警列表只返回外网告警结构 | PASS |
| 外网规则列表接口可访问 | PASS |
| 外网运行日志接口可访问 | PASS |
| 新建规则默认关闭 | PASS |
| API 拒绝以启用状态创建新规则 | PASS |
| 手动 Dry-Run 可执行 | PASS |
| 评估参数有最大数量限制 | PASS |
| API 不调用国内告警接口 | 静态隔离 PASS |
| API 不调用真实 RSS、AI 或通知 | PASS |

未完成或不能判定通过：

- 确认、解决、抑制接口的非管理员权限端到端验证。
- 处置备注和原/新状态审计验证。
- 所有要求筛选项的独立数据结果验证。

## 8. 前端验收

`/foreign?tab=alerts` 静态和构建检查结果：

- 告警列表调用 `/foreign/alerts`，失败运行调用 `/foreign/alert-runs`。
- 未调用国内 `/api/alerts/*`、Dashboard、Events 或热词接口。
- 展示标题、严重度、状态、规则、文章快照、事件快照、风险分/等级、触发/确认/解决/抑制时间。
- 页面明确显示告警评估默认关闭、外部通知默认关闭、当前仅保存站内记录。
- 失败运行显示 `failed`、结束/开始时间和安全错误摘要。
- 有权限控制确认、解决和抑制按钮。
- `loading`、空数据、加载失败和评估中状态存在对应显示。
- `npm run build` 通过。

前端目前只展示文章/事件快照或 ID，没有提供人工处置备注输入；这与上述审计缺陷一致，因此前端验收只能部分通过。

## 9. 国内链路隔离

默认生产库只读前后快照一致：

| 表 | 验收后快照 |
|---|---:|
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `foreign_opinions` | 3 |

独立测试库 3C migration 后外网告警表存在，测试清理后临时记录为 0：

| 表 | 清理后数量 |
|---|---:|
| `foreign_opinions` | 16，已有测试库样本保留 |
| `foreign_risk_results` | 0 |
| `foreign_events` | 0 |
| `foreign_alerts` | 0 |
| `foreign_alert_runs` | 0 |

数据库外键检查确认 `foreign_alerts` 只关联：

```text
foreign_alert_rules
foreign_opinions
foreign_risk_results
foreign_events
users
```

没有关联国内 `alerts`、`events`、`event_opinions` 或 `opinions`。3C 服务不导入国内 `AlertService`，也没有接入国内 Dashboard、地图、热词或事件链路。外部通知调用次数为 0，自动外网评估任务没有运行。

## 10. Migration 验收

在独立 `opinion_test` 完成：

```text
foreign_source_3c (head)
-> alembic downgrade foreign_source_3b
-> 确认 foreign_alert_rules / foreign_alerts / foreign_alert_runs 消失
-> 确认国内表与 foreign_opinions 数量保持
-> alembic upgrade foreign_source_3c
-> 确认三张表、14 个告警相关索引、外键和 CheckConstraint 存在
```

结果：**upgrade/downgrade/upgrade 通过**。默认 `opinion_db` 没有执行 migration 或 downgrade。

## 11. 测试命令与结果

### 11.1 外网聚焦测试

```text
pytest tests/test_foreign_source_3c.py -q
5 passed

pytest tests/test_foreign_source_phase1.py \
  tests/test_foreign_source_phase1_1.py \
  tests/test_foreign_source_3a.py \
  tests/test_foreign_source_3b.py \
  tests/test_foreign_source_3b_remediation.py \
  tests/test_foreign_source_3b_ui.py \
  tests/test_foreign_source_3c.py -q
40 passed
```

测试必须显式使用 `127.0.0.1:5433/opinion_test`。使用默认 `localhost:5433` 时曾因本机测试 PostgreSQL 仅监听 IPv4 而在 124 秒超时；这是环境连接问题，未改动测试夹具。

### 11.2 国内聚焦回归

```text
69 passed, 7 failed
```

已知/历史或测试环境问题如下，未修改：

| 测试 | 分类 |
|---|---|
| `test_event_orm_persist` | 历史断言与当前 `Event.status` 模型不一致 |
| `test_same_keyword_one_event` | 历史事件标题选择语义与当前实现不一致 |
| `test_api_aggregate` | 历史测试期望同步聚合，当前 API 返回异步 `task_id` |
| `test_api_list_pagination` | 依赖上述历史同步聚合行为 |
| `test_4_viewer_forbidden` | 测试库缺少 `viewer` 角色 fixture |
| `test_case4_collector_writeback_version_and_factors` | 测试 FakeCollector 与当前 `region_kw` 调用签名不一致 |
| `test_keyword_governance_context_words_zero_weight` | 当前测试库敏感词治理数据未达到该测试的零权重预期 |

没有发现 3C 告警实现导致国内 `opinions`、`events`、`event_opinions` 或 `alert_records` 变化。

### 11.3 编译与构建

```text
python -m compileall app tests
PASS

cd frontend
npm run build
PASS
```

构建仅报告既有 Vite/Rollup warning，没有构建失败。

## 12. 临时数据清理

3C 测试创建的规则、告警、运行日志、文章、风险结果和事件 fixture 已清理。测试库当前：

```text
foreign_alerts=0
foreign_alert_runs=0
Phase 3C fixture rules=0
Phase 3C fixture opinions=0
```

已有 16 条测试库 `foreign_opinions` 保留；默认生产库已有 3 条外网舆情和采集日志保留。

## 13. 是否允许进入下一阶段

**不允许进入生产启用或外网告警自动评估。**

在进入下一阶段前，至少需要：

1. 新增 `foreign_alert_actions` 或等价的 scope 隔离审计结构。
2. 为确认、解决、抑制 API 增加备注请求字段。
3. 保存操作前状态、操作后状态、操作人、时间、原因/备注和目标告警。
4. 增加非管理员权限端到端测试。
5. 增加 cooldown 到期重触发、同事件多文章和 failed risk result fixture 测试。
6. 重新执行本验收，且不得修改国内测试断言来掩盖基线失败。

## 14. 最终声明

- 本阶段未修改代码、配置或既有测试断言。
- 仅新增本验收报告。
- 临时测试库执行了 3C migration upgrade/downgrade/upgrade；默认生产库未迁移。
- 未写入生产数据库。
- 未启用三个生产外网源。
- 未启用外网采集调度。
- 未启用自动告警评估。
- 未执行真实外网采集。
- 未调用外部 AI、代理或境外采集节点。
- 未发送邮件、短信、企业微信、钉钉或其他外部通知。
- 未接入 Dashboard、地图或热词。
- 外网告警与国内告警、事件和风险数据保持表和 API 隔离。
- Phase Foreign-Source-3C 小型外网告警结果验收：**未通过，No-Go**。
