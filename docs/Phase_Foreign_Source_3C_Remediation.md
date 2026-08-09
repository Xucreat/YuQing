# Phase Foreign-Source-3C-Remediation
# 外网告警处置审计完整性修复与复验报告

## 1. 结论

本阶段已修复 Phase 3C 小型告警验收发现的处置审计缺口，并在独立测试库完成复验。

修复后，确认、解决、抑制操作会在同一事务中保存：

- 操作备注
- 操作前状态
- 操作后状态
- 操作类型
- 操作人
- 操作时间
- 关联 `foreign_alert_id`

**Phase 3C 小型外网告警结果验收：重新通过。**

**允许进入 Phase Foreign-Source-3D 设计评审；不允许生产启用、自动评估或外部通知。**

## 2. 根因分析

原实现的 `ForeignAlertService.acknowledge/resolve/suppress` 只更新 `foreign_alerts` 状态并直接提交；API 外层的通用 `audit_write` 只记录动作和资源，未保存状态变化快照，也没有接收备注。前端处置按钮直接发送空请求，因此无法形成完整的外网处置审计链。

该问题还带来两个风险：

1. 无法证明一次操作实际从哪个状态转换到哪个状态。
2. 通用国内操作日志不能替代外网业务 action，也不适合承载外网处置历史。

本阶段新增独立 `foreign_alert_actions`，并将业务状态更新和 action 写入统一到 `ForeignAlertService.transition()`。

## 3. 实际改动文件

本阶段直接新增或修改：

| 文件 | 变更 |
|---|---|
| `backend/app/models/foreign_alert_action.py` | 新增外网处置 action ORM 模型 |
| `backend/alembic/versions/foreign_source_3c_remediation.py` | 新增 action 表 migration 和 downgrade |
| `backend/app/models/__init__.py` | 注册 `ForeignAlertAction` |
| `backend/app/services/foreign_alert_service.py` | 新增事务化状态转换、锁、action 写入和查询 |
| `backend/app/api/foreign_alerts.py` | 处置 note 请求、action 响应、历史查询 API |
| `frontend/src/views/ForeignWorkspace.vue` | 备注输入、处置历史和安全错误展示 |
| `backend/tests/test_foreign_source_3c_remediation.py` | 新增 remediation 测试 |
|

工作区中已有的 Phase 1 至 3C 修改、未跟踪文件、备份和临时文件全部保留；未使用 `git reset`、`git checkout` 或清理命令。未修改国内代码、国内测试断言或国内 UI。

## 4. 数据模型与迁移

### 4.1 `foreign_alert_actions`

新增字段：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `foreign_alert_id` | 外键，仅关联 `foreign_alerts`，`CASCADE` 删除 |
| `action_type` | `acknowledge`、`resolve`、`suppress` |
| `previous_status` | 操作前数据库状态 |
| `new_status` | 本次实际写入状态 |
| `note` | 非空处置备注 |
| `actor_id` | 当前认证用户的 `users.id`；API 操作始终传入当前用户 |
| `created_at` | 服务端 UTC 时间 |
| `metadata` | JSONB，目前仅保存幂等标记 |

action 表的业务目标只有 `foreign_alerts`；`actor_id` 是认证用户外键，不关联任何国内告警或处置表。`action_type`、前状态和新状态有 CheckConstraint，并对告警、时间和类型建立索引。

### 4.2 Migration

新增 revision：

```text
foreign_source_3c_remediation
down_revision = foreign_source_3c
```

在独立 `opinion_test` 完成：

```text
foreign_source_3c
    -> upgrade foreign_source_3c_remediation
    -> 验证 action 表、索引、外键和约束
    -> downgrade foreign_source_3c
    -> 确认 action 表消失且既有数据不变
    -> upgrade foreign_source_3c_remediation
```

往返通过。默认 `opinion_db` 没有执行 migration 或 downgrade。

## 5. 事务处理与状态转换

`ForeignAlertService.transition()` 的顺序为：

1. 对目标 `foreign_alerts` 行执行 `SELECT ... FOR UPDATE`。
2. 从数据库读取 `previous_status`。
3. 校验 action 类型、备注非空和状态转换。
4. 更新告警状态、操作时间和操作人。
5. 创建 `ForeignAlertAction`，写入前状态、新状态、备注、操作者和时间。
6. `flush` 后一次性提交。
7. 刷新告警和 action 并返回结果。

允许的转换：

```text
triggered   -> acknowledged
triggered   -> suppressed
acknowledged -> resolved
acknowledged -> suppressed
```

非法转换会回滚且不会写入 action。异常会回滚状态和 action，并向 API 返回安全错误摘要。

### 5.1 幂等与并发

同一告警重复执行相同 action 时，服务读取既有同类型、同目标状态的 action 并原样返回，不重复插入 action；响应带 `idempotent=true`。

目标告警行锁保证两个用户并发处置时只有一个操作先完成，另一个操作在读取最新状态后得到幂等结果或安全状态冲突，不会形成错误状态链。事务 flush 失败测试确认告警状态恢复原值且 action 数量为 0。

## 6. API 变更

处置接口现在要求 JSON body：

```json
{"note": "人工确认原因"}
```

接口：

```text
POST /api/foreign/alerts/{alert_id}/acknowledge
POST /api/foreign/alerts/{alert_id}/resolve
POST /api/foreign/alerts/{alert_id}/suppress
GET  /api/foreign/alerts/{alert_id}/actions
```

处置响应至少包含：

```text
alert_id
action_type
previous_status
new_status
note
actor_id
created_at
idempotent
```

并附带更新后的外网告警快照。note 缺失、空白或超长时返回 422；未授权用户不能查看或写入 action。处置权限保持独立：

```text
foreign:alerts:acknowledge
foreign:alerts:resolve
foreign:alerts:suppress
foreign:alerts:read
```

通用 `audit_write` 继续保留，并额外记录 action 类型、备注、前状态、新状态和幂等标记；它不能替代 `foreign_alert_actions`。

Action API 只查询当前 `foreign_alert_id` 的外网处置历史，不返回国内告警、事件或文章。

## 7. 前端变更

`/foreign?tab=alerts` 处置流程现在：

1. 点击确认、解决或抑制后打开备注输入框。
2. 空白备注禁止提交。
3. 请求只调用 `/api/foreign/alerts/{id}/{action}`。
4. 成功后刷新告警和 `/api/foreign/alerts/{id}/actions`。
5. 展示 action 类型、备注、原状态、新状态、操作人和操作时间。
6. 处置历史按服务端时间升序展示。
7. 失败时显示 API 的安全错误摘要。
8. 无权限用户的操作按钮保持禁用。

国内 `Alerts.vue`、国内告警 API、Dashboard、事件、地图和热词逻辑未修改。

## 8. 测试结果

### 8.1 新增 remediation 测试

```text
pytest tests/test_foreign_source_3c_remediation.py -q
5 passed
```

覆盖：

- acknowledge action 完整字段
- resolve action 完整字段
- suppress action 完整字段
- 空白 note 返回 422
- 非法状态转换不写 action
- 重复确认和重复抑制幂等
- API action 历史查询和未认证拒绝
- 并发确认/抑制只形成一个合法状态链
- 事务 flush 失败回滚告警和 action
- 国内 `alert_records` 数量不变

### 8.2 外网全链路回归

```text
pytest tests/test_foreign_source_phase1.py \
  tests/test_foreign_source_phase1_1.py \
  tests/test_foreign_source_3a.py \
  tests/test_foreign_source_3b.py \
  tests/test_foreign_source_3b_remediation.py \
  tests/test_foreign_source_3b_ui.py \
  tests/test_foreign_source_3c.py \
  tests/test_foreign_source_3c_remediation.py -q
45 passed
```

### 8.3 编译和前端构建

```text
python -m compileall app tests
PASS

cd frontend
npm run build
PASS
```

前端构建只有既有 Vite/Rollup warning，没有失败。

### 8.4 国内聚焦回归

```text
69 passed, 7 failed
```

7 条失败均为已有国内基线或测试环境问题，本阶段未修改：

| 测试 | 分类 |
|---|---|
| `test_case4_collector_writeback_version_and_factors` | FakeCollector 与当前 `region_kw` 调用签名不一致 |
| `test_keyword_governance_context_words_zero_weight` | 测试库敏感词治理数据未达到零权重预期 |
| `test_4_viewer_forbidden` | 测试库缺少 `viewer` 角色 fixture |
| `test_event_orm_persist` | 历史断言与当前 `Event.status` 模型不一致 |
| `test_same_keyword_one_event` | 历史事件标题选择语义与当前实现不一致 |
| `test_api_aggregate` | 历史期望同步聚合，当前 API 返回异步 `task_id` |
| `test_api_list_pagination` | 依赖上述历史同步聚合行为 |

未发现 remediation 引起的国内告警、事件、风险或 Dashboard 回归。

## 9. 国内/国外隔离结果

默认生产库只读复核：

| 项目 | 结果 |
|---|---:|
| Alembic revision | `foreign_source_1` |
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `foreign_opinions` | 3 |
| 外网运行中采集任务 | 0 |

三个外网源仍为 `enabled=false`、`schedule_enabled=false`。

测试库最终：

| 项目 | 结果 |
|---|---:|
| Alembic revision | `foreign_source_3c_remediation` |
| 已有 `foreign_opinions` | 16，保留 |
| `foreign_alerts` 临时记录 | 0 |
| `foreign_alert_runs` 临时记录 | 0 |
| `foreign_alert_actions` 临时记录 | 0 |
| 国内 `opinions/events/event_opinions/alert_records` | 测试过程未被外网 action 写入 |

`foreign_alert_actions` 只通过 `foreign_alert_id` 关联 `foreign_alerts`，没有国内告警关联。没有调用外部通知，自动外网告警评估未启用。

## 10. 临时数据清理

新增 remediation 测试创建的外网文章、告警和 action 已清理。测试库保留原有 16 条 `foreign_opinions`；默认库原有外网样本和采集日志未删除。未执行任何生产库删除、truncate 或 downgrade。

## 11. 未扩展事项

本阶段没有实现或启用：

- 外网 Dashboard
- 外网地图
- 外网热词
- 外部邮件、短信、企业微信、钉钉或其他通知
- 自动告警评估
- 外网采集调度
- 生产外网源
- 国内告警链路改造

## 12. 最终声明

- 已修复外网告警处置审计完整性问题。
- 已新增独立 `foreign_alert_actions` 表和 migration。
- 状态更新与 action 写入在同一事务中完成。
- 已支持备注、前/后状态、操作人、操作时间和关联告警。
- 未修改国内链路、国内测试断言或国内数据库数据。
- 未写入生产数据库；默认 `opinion_db` 仍为 `foreign_source_1`。
- 未启用外网源、自动调度或自动告警评估。
- 未发送外部通知。
- 未执行真实 RSS，未调用外部 AI、代理或境外采集节点。
- Phase 3C remediation 验收：**通过**。
- 是否允许进入 Phase Foreign-Source-3D 设计评审：**允许**。
- 是否允许生产启用：**不允许，需后续独立生产审批和启用验收**。
