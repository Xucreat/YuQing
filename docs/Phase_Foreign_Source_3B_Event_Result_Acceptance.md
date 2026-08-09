# Phase Foreign-Source-3B 小型外网事件结果验收报告

验收结论：**不通过，阻塞修复后重新验收**。

本阶段只做了测试库/fixture 验收，没有修复发现的问题。按要求未修改 Python、Vue、TypeScript、配置、既有测试断言或数据库结构；本报告是本阶段唯一新增文件。

## 1. 环境和保护确认

默认库只读确认：

- 数据库：`opinion_db`
- Alembic：`foreign_source_1`
- 固定外网源：Fox News、The Guardian、纽约时报中文网均为 `enabled=false`、`schedule_enabled=false`
- 默认库已有 `foreign_opinions=3`、`scope=foreign` 采集日志 3 条，均保留
- 默认库国内快照：`opinions=1702`、`events=292`、`event_opinions=567`

测试库为独立 PostgreSQL `opinion_test`，端口 `5433`，当前 head 为 `foreign_source_3b`。测试结束后快照为：

| 表 | 数量 |
|---|---:|
| `opinions` | 2 |
| `events` | 0 |
| `event_opinions` | 0 |
| `alert_records` | 0 |
| `foreign_opinions` | 16 |
| `foreign_events` | 0 |
| `foreign_event_opinions` | 0 |
| `foreign_event_runs` | 0 |
| `foreign_event_actions` | 0 |

本次临时样本使用随机 `accept3b_*` 前缀，结束后残留为 0。未删除或清空既有 `foreign_opinions`、`foreign_risk_results` 或 `collector_runs`。

环境未使用真实 RSS、外部 AI、HTTP 代理或境外节点；未启用生产源、自动调度或自动生产事件聚合。

## 2. 实际检查范围

已阅读：

- `docs/Phase_Foreign_Source_3B_Implementation.md`
- `docs/Phase_Foreign_Source_3B_Event_Design_Review.md`
- `docs/Phase_Foreign_Source_3A_Implementation.md`
- `docs/Phase_Foreign_Source_3A_Risk_Result_Acceptance.md`
- `docs/Phase_Foreign_Source_1_1_Acceptance.md`

已检查：

- `ForeignEventService`
- `foreign_events`、`foreign_event_opinions`、`foreign_event_candidates`、`foreign_event_runs`、`foreign_event_actions` 模型
- `/api/foreign/events*` API
- `ForeignWorkspace.vue` 的 `events` 区域
- Phase 3B 及 UI 测试

工作区已有修改、未跟踪文件和临时文件均保留，未使用回滚或清理工作区命令。

## 3. 临时样本和结果

独立测试库中准备了 14 条带随机前缀的临时文章，覆盖：

- 两组高度相似英文文章
- 一组高度相似中文文章
- 一组中英文表达相近文章
- 一组仅共享 `China` 但主题不同的英文文章
- URL/content hash 去重标记样本
- mixed 语言样本

结果：

- 英文同语言候选：通过，`confidence=1.0`
- 中文同语言候选：通过，`confidence=1.0`
- 中英文自动聚合：未发生
- 仅共享 `China` 的不同主题：未生成候选
- mixed 内容：进入候选，`confidence=0.515`，低于 `0.55` 候选阈值，未自动确认
- content hash 重复：canonical 数量降为 1
- `duplicate_of_id` 标记重复：canonical 数量降为 1
- 候选默认状态：`candidate`，未直接成为 `confirmed`

数据库存在 `foreign_opinions.url` 唯一约束，因此尝试直接插入两个相同 URL 的文章时被约束拒绝；这属于入库层防重行为。现有实现对已落库重复关系使用 `duplicate_of_id` 表达，未形成重复事件关联。

## 4. 候选证据和隔离

候选证据已保存：

- `aggregation_version`
- `similarity_score`
- `similarity_method=lexical_jaccard`
- `similarity_threshold=0.55`
- `matched_terms`
- `candidate_reason`

候选只读取 `foreign_opinions`，风险快照为可选辅助信息，不替代相似度判断。未写入 `opinions`、`events` 或 `event_opinions`。

中英文隔离和监测关键词不作为事件锚点的规则通过上述临时样本验证。

## 5. 人工操作验收

在测试库中实际执行了：

- `candidate -> confirmed`
- 两个同语言事件合并
- 一个事件拆分
- `confirmed -> monitoring -> resolved -> archived`
- 使用相同 `request_id` 重复合并/拆分，接口返回同一目标事件
- 未认证访问 `/api/foreign/events`：HTTP `401`
- 管理员查询外网事件和事件详情：HTTP `200`
- 国内 `/api/events` 未返回外网事件
- 失败候选重建抛出可追踪异常，原始 `foreign_opinions` 保留

以下项目未形成通过结论：

- 本次发现合并统计缺陷后停止，未继续执行完整的驳回权限矩阵。
- 未认证已验证，普通已认证但无外网事件管理权限的用户矩阵未完成。
- 风险结果存在/失败/缺失三种状态对事件候选的完整组合测试未完成。

## 6. 阻塞缺陷

### 6.1 合并后事件统计错误

临时样本中，两个各含 2 篇文章的同语言事件合并后，目标事件返回：

```text
target.opinion_count = 2
```

预期应为 4。随后拆分操作也基于错误的目标计数继续运行。缺陷位置位于 `backend/app/services/foreign_event_service.py` 的 `merge_events` 统计更新逻辑附近（当前实现约第 645 行）。

这会直接影响：

- 外网事件文章数量展示
- 来源数量和事件详情统计的可信度
- 后续外网事件 Dashboard/告警的输入质量

本阶段未修复，必须修复后重新验收合并、拆分、关联表和计数一致性。

### 6.2 外网事件 UI 字段不完整

`frontend/src/views/ForeignWorkspace.vue` 的正式事件列表当前没有展示：

- `heat_score`
- `first_seen_at`
- `last_seen_at`

本阶段要求正式事件列表显示热度、首次出现时间和最近更新时间，当前未满足。事件详情也只显示语言、状态、文章数和摘要，未显示完整时间和热度字段。

### 6.3 UI 缺少明确失败状态

`loadEvents()` 使用 loading 和 empty 状态，但没有独立的 failed 状态变量或失败占位内容。请求失败时没有与事件页绑定的稳定失败状态展示；当前只在部分人工操作中通过消息提示错误。

## 7. API 和前端验收

已通过：

- `/api/foreign/events*` 与国内 `/api/events` 命名空间隔离
- API 查询只返回外网事件及外网文章
- 外网事件详情可返回 `foreign_opinions`
- 认证依赖有效，未认证请求被拒绝
- 候选 Dry-Run 默认不落候选正式记录
- 事件 API 支持语言、置信度、来源、时间和状态等筛选代码路径
- `/foreign?tab=events` 入口存在
- 前端事件调用使用 `/foreign/events*`

未通过或未完成：

- 正式事件列表字段不完整，见 6.2。
- 事件页失败态不完整，见 6.3。
- 合并后的统计值不正确，API 详情会暴露该错误。

## 8. 国内隔离验收

测试前后国内快照保持：

- `opinions=2`
- `events=0`
- `event_opinions=0`
- `alert_records=0`

测试期间未调用国内事件聚合服务，也未写入国内事件关联表。外网事件 API 不返回国内事件，外网事件服务没有接入国内告警、Dashboard、地图或热词链路。

默认库只做了身份和状态 SELECT，国内数据和既有外网样本未被本阶段修改。

## 9. 迁移验收

Phase 3B 实施阶段已在独立 `opinion_test` 完成：

1. `foreign_source_3a -> foreign_source_3b` upgrade。
2. 验证 5 张事件表、外键、索引和约束。
3. downgrade 回 `foreign_source_3a`，确认国内表和 3A 表数据不变。
4. 再次 upgrade 到 `foreign_source_3b`。

本验收阶段没有对默认 `opinion_db` 执行 migration 或 downgrade。当前默认库仍为 `foreign_source_1`。

## 10. 测试命令和结果

```powershell
$env:DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@localhost:5433/opinion_test?connect_timeout=3'
$env:DB_IDENTITY_CHECK='off'
pytest tests/test_foreign_source_3b.py tests/test_foreign_source_3b_ui.py -q
```

结果：`5 passed`。

```powershell
pytest tests/test_foreign_source_phase1.py tests/test_foreign_source_phase1_1.py tests/test_foreign_source_3a.py -q
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

结果：通过；仅有既有 Rollup 注释和动态/静态路由分包提示。

国内聚焦回归的既有记录为 `54 passed, 5 failed`。失败对应旧国内模型字段/标题语义、异步事件 API 契约和 viewer fixture，不是本阶段外网代码引入；本阶段没有修改国内代码或断言。

## 11. 明确状态

- 是否修改代码：否。
- 是否修改数据库结构：否。
- 是否写入默认/生产数据库：否。
- 是否启用生产外网源：否。
- 是否启用自动调度：否。
- 是否启用自动事件聚合：否。
- 是否启用自动事件确认：否。
- 是否调用外部 AI：否。
- 是否访问真实 RSS：否。
- 是否使用代理或境外采集节点：否。
- 是否修改国内链路：否。
- 用户已有外网样本和采集日志是否保留：是。

## 12. Phase 3C 前置判断

当前不允许进入 Phase Foreign-Source-3C 外网告警设计评审的实施阶段。进入下一阶段前必须：

1. 修复合并/拆分后的 `opinion_count`、`source_count` 和关联表一致性问题。
2. 补齐正式事件列表热度、首次时间、最近时间和失败态展示。
3. 补充驳回、无管理权限用户、风险结果存在/失败/缺失和操作审计测试。
4. 重新执行 3B 小型验收，确认国内快照、默认库身份和生产源状态不变。
5. 在独立预发布库重新完成 migration 往返验证。

当前 Go/No-Go：**NO-GO**。外网事件基础隔离和候选生成可继续保留，但在阻塞缺陷修复并重新验收前，不得启用生产外网事件聚合、外网告警或任何下游链路。
