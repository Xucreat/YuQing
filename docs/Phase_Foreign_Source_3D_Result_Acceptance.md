# Phase Foreign-Source-3D 外网可视化小型结果验收

## 1. 验收结论

**结论：不通过，阻塞在统计失败安全错误处理。**

本阶段发现真实缺陷后按停止条件停止，没有修改代码、配置、数据库结构、既有测试断言或用户数据。

阻塞问题：

- `get_dashboard_summary` 有安全错误包装；但 `get_dashboard_trends`、`get_dashboard_risk`、`get_dashboard_events`、`get_dashboard_alerts`、`get_dashboard_sources`、`get_hotwords`、`get_hotword_trends`、`get_hotword_sources`、`get_source_distribution`、`get_language_distribution` 没有统一安全错误包装。
- `/api/foreign/*` 的 `_run` 只把 `RuntimeError` 转成 503，且直接使用异常文本作为响应详情。
- 使用本地 mock 抛出 `password=hidden` 已复现这些方法返回原始 `RuntimeError password=hidden`。因此数据库异常、连接串、Token 或其他敏感文本存在向 API 泄露的风险。
- 该问题直接违反“统计失败返回安全错误，不显示内部敏感信息”的验收标准，不能判定通过，也不允许生产灰度。

发现缺陷后未继续修改或扩大修复范围。

## 2. 环境和数据库身份

前置检查：

- 工作区：`C:\Users\Administrator\Desktop\YQ`
- `git status --short`：工作区已有大量修改、未跟踪文件和临时目录，全部保留。
- 实际命令：在 `backend` 目录执行 `alembic -c alembic.ini current`
- 默认数据库：`opinion_db`
- 默认 Alembic revision：`foreign_source_1`
- 默认库安全身份校验：通过

默认库只读快照：

| 表/状态 | 数量或状态 |
|---|---:|
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `foreign_opinions` | 3 |
| 外网 `collector_runs` running | 0 |

三个生产外网源均为 `enabled=false`、`schedule_enabled=false`。未在默认库执行迁移、写入、删除或 downgrade。

## 3. 测试数据和限制

使用既有本地测试数据库 `opinion_test`，revision 为
`foreign_source_3c_remediation`。本阶段没有向测试库写入测试数据，以保留已有样本。

只读样本快照：

| 表 | 数量 |
|---|---:|
| `opinions` | 2 |
| `events` | 0 |
| `event_opinions` | 0 |
| `alert_records` | 0 |
| `foreign_opinions` | 16 |
| `foreign_risk_results` | 0 |
| `foreign_event_candidates` | 0 |
| `foreign_events` | 0 |
| `foreign_event_opinions` | 0 |
| `foreign_alerts` | 0 |
| `foreign_alert_runs` | 0 |
| `collector_runs` | 8 |

因此本次环境可验证外网文章、来源、语言和空数据路径，但没有足够的已完成风险、candidate/confirmed/archived 事件和告警状态样本来宣称这些正向状态统计通过。

## 4. Dashboard 验收

已确认并注册以下接口：

- `/api/foreign/dashboard/summary`
- `/api/foreign/dashboard/trends`
- `/api/foreign/dashboard/risk`
- `/api/foreign/dashboard/events`
- `/api/foreign/dashboard/alerts`
- `/api/foreign/dashboard/sources`

在 `opinion_test` 上只读调用成功，返回 UTC 窗口和稳定结构。文章、来源、语言、趋势和空风险/事件/告警结构可返回；调用前后所有表数量一致。

但由于：

1. 现有 fixture 没有风险、事件和告警正向样本；
2. 统计失败接口安全错误泄露缺陷已复现；

Dashboard 不能判定通过。

## 5. 热词验收

已确认并注册：

- `/api/foreign/hotwords`
- `/api/foreign/hotwords/trends`
- `/api/foreign/hotwords/sources`

只读 smoke check 返回结果，且本地 tokenizer 测试通过：`China`、`Chinese`、`中国` 不进入默认热词；中英文处理路径分开；未读取国内关键词表；未调用外部 AI 或在线翻译。

但热词统计方法同样未统一包装统计异常，故“失败状态安全返回”不通过，热词整体验收不能通过。

## 6. 来源和语言分布验收

已确认并注册：

- `/api/foreign/source-distribution`
- `/api/foreign/language-distribution`

只读 smoke check 返回 16 个来源分组和 `zh/en/mixed/unknown` 稳定结构；采集运行状态查询使用 `collector_runs.scope='foreign'`。没有使用中国行政区、`region_id` 或地图接口。

来源分布方法同样存在异常原文泄露缺陷，因此本部分不能判定通过。

## 7. 前端验收

静态检查确认 ForeignWorkspace 包含：

- `/foreign?tab=dashboard`
- `/foreign?tab=hotwords`
- `/foreign?tab=sources`

页面包含：

- 数据范围和更新时间；
- loading、empty、failed、stale 展示；
- Dashboard 日趋势；
- 热词趋势；
- 来源和语言分布；
- 来源趋势；
- 地图未实现。

源码中的新增请求均为 `/api/foreign/*`。未发现外网页面调用国内 Dashboard、Events、Alerts 或地图接口。国内页面未修改。

前端构建通过，但后端失败响应安全性缺陷使前端 failed 状态验收不能整体通过。

## 8. 国内/国外隔离快照

`opinion_test` 可视化只读调用前后快照一致：

```text
opinions=2
events=0
event_opinions=0
alert_records=0
foreign_opinions=16
foreign_risk_results=0
foreign_event_candidates=0
foreign_events=0
foreign_event_opinions=0
foreign_alerts=0
foreign_alert_runs=0
collector_runs=8
```

确认结果：

- 外网统计未写入国内表。
- 外网 API 路由均位于 `/api/foreign/*`。
- 未调用或修改国内 Dashboard、热词、事件、告警和地图服务。
- 外网统计失败 mock 未执行数据库写入。
- 没有地图请求、GeoJSON 请求或中国行政区映射。

## 9. 地图暂缓

地图仍未实现，也没有隐藏地图调用。外网来源分布、语言分布和时间趋势继续作为首期地图替代方案。

本次验收不允许进入地图实现。可以在后续独立只读设计评审中继续讨论地域实体语义，但必须先解决当前统计错误安全问题。

## 10. Phase 3C 超时复核

前序实施阶段已记录：

- `pytest backend/tests/test_foreign_source_3c.py -q --maxfail=1` 在本地执行窗口内超时；
- focused single-test run 同样超时；
- `opinion_test` 可独立连接；
- 之前检查 `pg_stat_activity` 未发现持续数据库锁等待；
- 没有真实 RSS、AI、代理或境外节点等待迹象。

本次在发现 3D 统计错误安全缺陷后按停止条件停止，因此没有再次启动 3C 写入型集成测试。现有证据只能分类为“本地 pytest/测试流程超时，尚未证明是数据库死锁、外部网络等待或 3D 新增回归”。该问题仍需在修复后以明确测试超时重新复核，不能标记为已解决。

## 11. 迁移和清理

Phase 3D 实现没有新增 Alembic migration、快照表或统计运行表。本阶段没有执行 upgrade、downgrade 或迁移往返。

没有创建临时数据库行，因此没有清理删除；已有 16 条 `foreign_opinions` 和采集日志保留。默认 `opinion_db` 未被写入或迁移。

## 12. 测试命令和结果

通过：

- `pytest backend/tests/test_foreign_source_3d.py -q`：4 passed。
- `python -m compileall backend/app backend/tests`：通过。
- `cd frontend; npm run build`：通过，保留既有 Vite warning。
- `opinion_test` 可视化 service 只读 smoke check：11 个方法返回，前后快照一致。
- API 路由静态检查：11 个外网可视化路径已注册。
- 前端源码静态检查：新可视化请求只使用 `/api/foreign/*`，未发现地图调用。

失败/阻塞：

- 统计失败安全错误 mock：失败；除 summary 外的方法泄露原始异常文本。
- Phase 1/1.1/3A/3B/3C 全量回归：因本次阻塞停止，未继续运行。
- 国内 Dashboard、事件、告警聚焦回归：因本次阻塞停止，未继续运行。

## 13. 已知基线问题分类

- Phase 3C pytest 超时：历史/本地测试流程问题，当前证据不足以分类为数据库死锁或外部网络等待；本次未修改其代码和断言。
- 本阶段新增阻塞：3D 可视化统计方法错误安全包装不一致，属于本阶段实现风险，不能按历史基线忽略。
- 前端 Vite warning：构建非阻塞 warning，未归因于本阶段功能失败。

## 14. 是否允许后续阶段

- 外网生产灰度：**不允许**。
- Phase 3D 通过：**未通过**。
- 外网地图实现：**不允许进入实现**，继续暂缓。
- 后续工作首先应补齐统一安全错误包装和安全错误测试，再重新执行本验收；本阶段不在报告中直接修复。

## 15. 最终声明

- 是否修改代码：否，本阶段未修改代码。
- 是否修改数据库结构：否。
- 是否写入生产数据库：否。
- 是否启用外网源：否。
- 是否启用自动调度：否。
- 是否调用真实 RSS、AI、代理或通知：否。
- 是否实现外网地图：否，地图暂缓。
- 是否通过 Phase 3D 小型结果验收：否，因统计失败安全错误泄露问题阻塞。
