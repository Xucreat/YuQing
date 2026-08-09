# Phase Foreign-Source-3D-Remediation

## 1. 结论

**Phase 3D remediation 安全修复通过。**

外网可视化的 11 个统计方法现在统一将异常转换为固定的
`FOREIGN_VISUALIZATION_QUERY_FAILED`，API 不再返回原始异常文本。敏感信息矩阵覆盖 `password=hidden`、`token=hidden`、`secret=hidden`、代理 URL、traceback、路径和 SQL，全部通过。

Phase 3D 小型结果验收可以重新执行。生产灰度仍需等待重新验收和跨 Phase 集成测试超时问题的独立处理；本阶段不扩大范围修复该历史问题。

## 2. 根因分析

原实现的问题链路为：

1. `get_dashboard_summary` 之外的统计方法直接向上抛出数据库或统计异常。
2. `/api/foreign/*` 的 `_run` 使用 `str(exc)` 作为 503 `detail`。
3. 前端可视化错误处理优先显示后端返回的 `detail`。
4. 来源聚合正常响应还会返回 `collector_runs.error_msg` 截断文本，可能包含代理、连接串或其他内部配置。

因此 mock 的 `password=hidden` 能够穿过服务和 API 错误边界。

## 3. 实际修改

仅修改外网可视化范围：

- `backend/app/services/foreign_visualization_service.py`
  - 新增 `ForeignVisualizationError`。
  - 新增 `safe_visualization_query` 统一 guard。
  - 覆盖全部 11 个实际统计方法。
  - 原始异常不写入异常文本，也不以 traceback 形式记录日志；日志只记录固定事件和错误码。
  - 聚合响应移除 `collector_runs.error_msg`，只保留运行状态和时间。
- `backend/app/api/foreign_visualization.py`
  - `_run` 统一返回固定 503 JSON。
  - 结构：`error_code`、固定 `detail`、随机 `request_id`。
  - 保留参数错误的 422 行为。
  - 防御性捕获未被 guard 覆盖的异常，不返回异常对象或异常文本。
- `frontend/src/views/ForeignWorkspace.vue`
  - Dashboard、hotwords、sources 只使用错误码、HTTP 状态和白名单文案。
  - 不再读取可视化请求的原始 `response.data.detail`。
- `backend/tests/test_foreign_source_3d_remediation.py`
  - 新增 11 方法 × 5 敏感异常类型的服务和 API 响应矩阵。
  - 新增前端错误白名单静态检查。

没有修改国内服务、国内 API、国内页面、数据库模型或 Alembic 文件。

## 4. 统一错误响应

统计失败统一返回 HTTP 503：

```json
{
  "error_code": "FOREIGN_VISUALIZATION_QUERY_FAILED",
  "detail": "外网可视化数据暂时不可用",
  "request_id": "server-generated-random-id"
}
```

响应不包含：原始异常、SQL、数据库驱动文本、连接串、密码、Token、Secret、代理地址、traceback 或内部路径。

空数据仍返回正常聚合结构；查询失败返回 503，不伪装成零值成功。

## 5. 覆盖矩阵

每个方法分别使用以下 5 类异常进行 mock：

1. `password=hidden`
2. `token=hidden`
3. `secret=hidden`
4. `proxy=http://user:password@example.test`
5. `Traceback: internal path C:/private/app.py` 与 SQL 文本

| 实际方法 | password | token | secret | proxy | traceback/SQL |
|---|---:|---:|---:|---:|---:|
| `get_dashboard_summary` | PASS | PASS | PASS | PASS | PASS |
| `get_dashboard_trends` | PASS | PASS | PASS | PASS | PASS |
| `get_dashboard_risk` | PASS | PASS | PASS | PASS | PASS |
| `get_dashboard_events` | PASS | PASS | PASS | PASS | PASS |
| `get_dashboard_alerts` | PASS | PASS | PASS | PASS | PASS |
| `get_dashboard_sources` | PASS | PASS | PASS | PASS | PASS |
| `get_hotwords` | PASS | PASS | PASS | PASS | PASS |
| `get_hotword_trends` | PASS | PASS | PASS | PASS | PASS |
| `get_hotword_sources` | PASS | PASS | PASS | PASS | PASS |
| `get_source_distribution` | PASS | PASS | PASS | PASS | PASS |
| `get_language_distribution` | PASS | PASS | PASS | PASS | PASS |

实际代码中的方法名为 `get_hotwords`、`get_hotword_trends` 和
`get_hotword_sources`，对应用户要求中的 foreign hotword 接口。

## 6. 正常返回安全性

已检查正常聚合结构：

- Dashboard 只返回聚合数字、状态分布、趋势和 UTC 元数据。
- 热词只返回词、语言、计数、趋势和来源聚合，不返回正文或摘要。
- 来源/语言分布只返回聚合计数、状态、时间和趋势。
- `collector_runs.error_msg` 不再进入 Dashboard/source distribution 响应。
- 外网可视化服务仍只查询 foreign 表以及 `collector_runs.scope='foreign'`。
- 没有读取国内 `opinions`、国内 `events`、国内 `alerts`、国内关键词、国内 Dashboard 或 region 数据。

## 7. 前端安全

`/foreign?tab=dashboard`、`/foreign?tab=hotwords` 和
`/foreign?tab=sources` 的错误处理只允许：

- 503/`FOREIGN_VISUALIZATION_QUERY_FAILED`：`外网可视化数据暂时不可用`
- 403：权限不足提示
- 422：请求参数无效提示
- 其他情况：固定通用失败提示

页面不拼接原始异常内容，不展示 SQL、路径、连接配置或密钥。空数据和失败状态仍分别处理。国内页面错误行为未改动。

## 8. 数据库和隔离快照

默认数据库只读身份：

- Database: `opinion_db`
- Alembic: `foreign_source_1`
- `opinions=1702`
- `events=292`
- `event_opinions=567`
- `alert_records=37`
- `foreign_opinions=3`
- 三个外网源 `enabled=false`、`schedule_enabled=false`

未在默认库执行迁移、写入、删除或 downgrade。

测试库 `opinion_test` 前后快照：

```text
opinions=2
events=0
event_opinions=0
alert_records=0
foreign_opinions=16
foreign_risk_results=0
foreign_events=0
foreign_alerts=0
collector_runs=8
```

修复测试和只读 smoke check 前后数量一致。没有删除已有外网样本或日志，没有新增迁移。

## 9. 测试命令与结果

通过：

- `pytest backend/tests/test_foreign_source_3d.py backend/tests/test_foreign_source_3d_remediation.py -q`
  - `115 passed`
- `python -m compileall backend/app backend/tests`
  - 通过
- `cd frontend; npm run build`
  - 通过，保留既有 Vite warning
- 测试库 11 个统计方法只读 smoke check
  - 全部返回，前后快照一致
- `days=0` 参数检查
  - 仍返回 422，未被统一异常 catch 改成 503

跨 Phase 回归：

- 命令：`pytest backend/tests/test_foreign_source_phase1.py backend/tests/test_foreign_source_phase1_1.py backend/tests/test_foreign_source_3a.py backend/tests/test_foreign_source_3b.py backend/tests/test_foreign_source_3c.py -q --maxfail=1`
- 明确超时：60 秒
- 结果：超时，无测试断言输出；已终止本次 pytest 子进程。
- `opinion_test` 可连接，测试库快照未变化；无真实 RSS、AI、代理或通知等待证据。
- 分类：既有本地 pytest/集成 fixture 流程超时，尚未证明为数据库死锁；不归因于本次 remediation 改动。

## 10. 迁移、生产和外部依赖

- 本阶段无需数据库迁移。
- 未执行 upgrade、downgrade 或数据库结构变更。
- 未写入默认 `opinion_db`。
- 未启用外网源、自动调度或自动告警。
- 未访问真实 RSS、外部 AI、代理或境外节点。
- 未发送通知。
- 未修改国内链路。

## 11. 最终判定

- 是否修改国内链路：否。
- 是否修改数据库结构：否。
- 是否写入默认数据库：否。
- 是否启用外网源：否。
- 是否启用自动调度：否。
- 是否访问真实 RSS、AI、代理或通知：否。
- 是否仍存在本阶段目标的敏感信息泄露风险：未发现；矩阵全部通过。
- 是否通过 Phase 3D remediation：是。
- 是否允许重新执行 Phase 3D 小型结果验收：是。
- 是否允许生产灰度：否，需先重新完成 3D 结果验收并处理跨 Phase 集成测试超时。
