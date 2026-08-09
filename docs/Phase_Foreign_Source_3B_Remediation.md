# Phase Foreign-Source-3B Remediation

## 1. 结论

本阶段修复了 Phase 3B 小型结果验收中确认的三项阻塞问题：

1. 事件合并后从真实 `foreign_event_opinions` 关系重算指标。
2. 外网事件 UI 展示 `heat_score`、`first_seen_at`、`last_seen_at`。
3. 外网事件运行失败在事件工作台中以明确的 `failed` 状态展示。

外网事件 remediation 范围验收通过。生产外网事件聚合仍未启用，默认业务库仍为 NO-GO。

## 2. 环境和生产保护

- 默认数据库：`opinion_db`。
- 默认库 `alembic current`：`foreign_source_1`。
- 独立测试库：`opinion_test`，通过 `127.0.0.1:5433` 使用，当前 head 为 `foreign_source_3b`。
- 默认库未执行迁移、写入、删除或 downgrade。
- 默认库三个外网源均为 `enabled=false`、`schedule_enabled=false`。
- 未启动自动采集、自动事件聚合或真实外网采集。
- 未访问真实 RSS，未调用外部 AI、代理或境外采集节点。
- 用户已有的外网样本和采集日志未删除；测试库中的 `foreign_opinions=16` 保留。

本阶段所有临时事件、关联、运行和操作记录均在测试库创建并清理。最终测试库快照为：

| 表 | 数量 |
| --- | ---: |
| `opinions` | 2 |
| `events` | 0 |
| `event_opinions` | 0 |
| `alert_records` | 0 |
| `foreign_opinions` | 16 |
| `foreign_events` | 0 |
| `foreign_event_opinions` | 0 |
| `foreign_event_runs` | 0 |
| `foreign_event_actions` | 0 |

## 3. 根因分析

原 `merge_events()` 在移动关联后只更新了目标事件的普通 `count()` 和来源数，未统一从实际关联文章派生全部冗余指标。验收中的两个两文章事件合并后，目标 `opinion_count` 仍为 2；后续拆分继续继承错误值。

原 `split_event()` 也只更新了部分计数，没有统一重算时间、热度和风险等级。前端 `ForeignEvent` 类型及正式事件表没有三项指标；`loadEvents()` 也没有失败状态，事件运行失败没有在事件页呈现。

## 4. 实际改动文件

本阶段实际修改或新增：

- `backend/app/services/foreign_event_service.py`
  - 新增统一 `recompute_foreign_event_metrics()`。
  - 接入候选确认、合并和拆分操作。
  - 增加安全的事件运行错误摘要序列化。
- `frontend/src/views/ForeignWorkspace.vue`
  - 正式事件列表和详情增加热度、首次出现、最近出现。
  - 增加事件加载失败、事件运行失败、失败时间和错误摘要展示。
  - 失败状态使用独立视觉样式，不显示为空白或普通候选。
- `backend/tests/test_foreign_source_3b_remediation.py`
  - 新增合并、重复关联、拆分、API 失败运行和前端契约测试。
- `docs/Phase_Foreign_Source_3B_Remediation.md`
  - 本交付报告。

未修改国内事件、风险、告警、Dashboard、地图、热词代码或测试断言；本阶段没有新增数据库迁移。

## 5. 统一指标重算

`recompute_foreign_event_metrics(db, event_id)` 不负责提交事务。调用方先变更关联，再在同一事务中 flush 并重算，最后统一 commit；异常时由调用方事务回滚。

重算规则如下：

- `opinion_count`：关联 `foreign_opinion_id` 去重计数。
- `source_count`：优先使用 `source_name_snapshot`，为空时回退 `source_key`，再按来源身份去重。
- `first_seen_at` / `last_seen_at`：每篇关联文章使用 `published_at`，为空时回退 `collected_at`，取最早和最晚值。
- `heat_score`：使用关联文章当前、已完成的外网风险结果，取可用 `risk_score` 的最大值；没有可用风险分时为 `0`。这与当前 3B 候选热度快照语义一致，不累加旧事件热度。
- `risk_level`：按关联文章当前完成风险结果的最高级别派生，优先级为 `high > medium > low`；没有可用结果时为 `unknown`。
- `confidence`：保留候选/人工确认产生的相似度置信度，不把事件合并数量伪装成相似度。
- `language`、`event_type`：保留事件候选和人工确认语义；合并仍要求同语言。

该方法在以下关系变化后被调用：

- 候选确认新增文章关联。
- 合并移动或删除重复关联，同时重算目标和归档源事件。
- 拆分移动文章关联，同时重算原事件和新事件。

重复执行不会重复插入同一事件-文章关系；数据库现有唯一约束和服务层重复检查共同保证幂等性。被合并源事件设置为 `archived` 并保留 `canonical_event_id`，源事件空关联后的冗余指标重算为零/空值，避免保留误导性旧数据。

## 6. UI 和失败状态

`/foreign?tab=events` 继续只使用外网 API。正式事件表新增：

- 热度 `heat_score`
- 首次出现 `first_seen_at`
- 最近出现 `last_seen_at`

详情区域也显示同样三项指标；空时间显示 `-`，不会生成错误时间。

事件页面同时读取外网 `event-runs` 的 `status=failed` 结果，并显示：

- `failed` 状态标签
- `finished_at`，没有结束时间时回退到开始时间
- 最多 240 字符的安全错误摘要

事件业务状态与运行状态保持区分。事件列表继续展示 `candidate`、`confirmed`、`monitoring`、`resolved`、`archived` 等业务状态；运行失败通过独立失败区域呈现。错误序列化会隐藏 traceback、数据库驱动、密码、Token、代理和连接串等敏感信息。

国内 `Events.vue`、国内事件路由和国内 API 均未修改。

## 7. 测试结果

外网及本阶段测试，使用隔离测试库并显式指向 `127.0.0.1:5433/opinion_test`：

```text
pytest backend/tests/test_foreign_source_phase1.py \
  backend/tests/test_foreign_source_phase1_1.py \
  backend/tests/test_foreign_source_3a.py \
  backend/tests/test_foreign_source_3b.py \
  backend/tests/test_foreign_source_3b_ui.py \
  backend/tests/test_foreign_source_3b_remediation.py -q
35 passed
```

新增 remediation 用例覆盖：

- 两个各含两篇文章的事件合并后四篇文章、来源去重、首末时间和热度重算。
- 共享文章不重复计数、不重复关联。
- 重复 merge request 不重复计数或插入关联。
- 拆分后原事件和新事件指标正确。
- 失败 `foreign_event_run` 通过外网 API 返回。
- API 序列化和前端三项指标、失败状态静态契约。

其他验证：

```text
python -m compileall backend/app backend/tests       PASS
cd frontend; npm run build                           PASS
```

前端构建仅有既有 Rollup 注释和动态/静态路由分包警告。

## 8. 国内回归

按既有 3B 聚焦命令执行：

```text
pytest backend/tests/test_events.py \
  backend/tests/test_risk_engine.py \
  backend/tests/test_alert_operation.py \
  backend/tests/test_dashboard.py -q
```

结果：`54 passed, 5 failed`。失败均为已有国内基线问题，本阶段没有修改国内代码或断言：

- `test_event_orm_persist`：旧断言认为 `Event.status` 不存在，但当前模型已有该字段。
- `test_same_keyword_one_event`：旧测试期待旧事件标题选择语义，当前聚合标题为聚合摘要格式。
- `test_api_aggregate`：旧测试期待同步聚合结果，当前 API 返回异步 `task_id`。
- `test_api_list_pagination`：依赖旧同步聚合行为，因此列表为空。
- `test_4_viewer_forbidden`：测试库缺少 `viewer` 角色 fixture。

这些失败未涉及 `foreign_*` 表，也没有改变测试库国内快照；不属于本次 remediation 引入的新回归。

## 9. 数据库迁移和回滚

本阶段只修改服务、前端和测试，不新增字段或表，因此没有 remediation 专用 migration，也没有对任何数据库执行 downgrade。

只读迁移检查结果：

- 默认 `opinion_db`：`foreign_source_1`，3B 外网事件表不存在。
- 独立 `opinion_test`：`foreign_source_3b (head)`。
- 本阶段未修改 `foreign_source_3b` 迁移文件。

Phase 3B 原实施报告已记录其独立测试库 migration upgrade/downgrade 往返验证；本阶段不重复对含用户测试样本的库执行破坏性 downgrade。生产库没有迁移、回滚或结构变化。

## 10. 验收结论和后续准入

Phase 3B remediation 在本阶段限定范围内通过：合并指标、拆分指标、重复关联、失败运行 API 和 UI 指标/失败态均已复验通过。外网事件未写入国内 `events` 或 `event_opinions`，也未进入国内告警、Dashboard、地图或热词。

可以进入 **Phase Foreign-Source-3C 告警设计评审**，但只允许进行只读设计评审。进入 3C 实施或生产启用前仍需满足：

1. 在独立预发布库完成正式 migration 往返和权限矩阵验证。
2. 单独收口上述 5 个国内历史基线失败，或由业务确认其兼容性豁免。
3. 完成外网告警独立表、独立 scope、去重/冷却和人工确认设计。
4. 保持外网源、自动调度和自动聚合关闭，直到正式变更审批。

## 11. 最终状态

- 是否修改国内链路：否。
- 是否写入国内 `opinions`、`events` 或 `event_opinions`：否。
- 是否写入生产数据库：否。
- 是否修改生产数据库结构：否。
- 是否启用外网源：否。
- 是否启用自动调度：否。
- 是否执行真实采集：否。
- 是否调用外部 AI：否。
- 是否启用外网告警、Dashboard、地图或热词：否。
- 是否通过 Phase 3B remediation 验收：是，限定为本阶段修复范围。
