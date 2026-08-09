# Phase Foreign-Source-3D
# 3D Remediation 后重新验收

## 1. 结论摘要

本次复验确认 Phase 3D Remediation 的安全错误处理修复项通过：11 个外网可视化统计方法均将敏感异常转换为统一安全错误，API 不返回异常原文，前端可视化页面不直接展示后端 `detail`，外网服务未引入国内业务模型。

但本次不能判定完整的 Phase 3D 端到端结果验收通过。原因是跨 Phase 集成测试在明确的 60 秒边界内再次超时，且当前隔离测试库连接状态不稳定，无法用真实外网 fixture 完成 Dashboard、热词和来源统计数值的端到端复核。因此本报告结论为：**3D Remediation 安全项通过，完整 3D 结果验收条件性通过，生产人工灰度不放行**。

## 2. 环境与限制

- 工作区：`C:\Users\Administrator\Desktop\YQ`。
- 本阶段未修改代码、配置、数据库结构或既有测试断言；工作区原有修改、未跟踪文件和临时文件均保留。
- 使用的 3D/Remediation 复验测试为数据库无关 fixture/mock；未访问真实 RSS、外部 AI、代理、境外节点或通知渠道。
- `alembic -c backend/alembic.ini current` 只读检查结果：默认数据库为 `opinion_db`，revision 为 `foreign_source_1`。未执行 upgrade、downgrade 或其他迁移。
- 从工作区根目录直接执行 `alembic current` 会因 `alembic.ini` 位于 `backend` 而提示配置缺失；使用实际配置路径复验成功，该现象不代表数据库变化。
- 已存在的两个 Uvicorn 进程属于 2026-08-07 启动的既存服务；本次没有停止它们。跨 Phase 超时产生的 pytest 及其子进程已仅按本次命令精确清理，复核后没有 pytest 残留。
- 三个外网源、自动调度、自动告警、真实采集和外部通知均未启用。

## 3. Remediation 修复项复验

### 3.1 统一错误处理

`foreign_visualization_service.py` 的 `safe_visualization_query` 覆盖以下方法：

1. `get_dashboard_summary`
2. `get_dashboard_trends`
3. `get_dashboard_risk`
4. `get_dashboard_events`
5. `get_dashboard_alerts`
6. `get_dashboard_sources`
7. `get_hotwords`
8. `get_hotword_trends`
9. `get_hotword_sources`
10. `get_source_distribution`
11. `get_language_distribution`

API 层的 `_run` 对 `ForeignVisualizationError` 和防御性未知异常均返回 HTTP 503 及稳定结构：

```json
{
  "error_code": "FOREIGN_VISUALIZATION_QUERY_FAILED",
  "detail": "外网可视化数据暂时不可用",
  "request_id": "<随机请求标识>"
}
```

服务端日志只记录固定错误码，不记录完整异常、SQL、连接串或配置内容。正常响应仍只输出统计聚合字段；采集失败摘要不再从 `collector_runs` 原样暴露。

### 3.2 敏感异常测试矩阵

矩阵中的“通过”表示：响应为 HTTP 503；`error_code` 一致；`detail` 为固定安全文本；响应不包含异常原文、敏感词、SQL、连接串或 traceback。

| 统计方法 | password | token | secret | proxy URL | traceback/路径/SQL | SQL connection error |
|---|---:|---:|---:|---:|---:|---:|
| `get_dashboard_summary` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_dashboard_trends` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_dashboard_risk` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_dashboard_events` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_dashboard_alerts` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_dashboard_sources` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_hotwords` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_hotword_trends` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_hotword_sources` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_source_distribution` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |
| `get_language_distribution` | 通过 | 通过 | 通过 | 通过 | 通过 | 通过 |

结果：

- `115 passed`，覆盖 11 个方法、5 类敏感异常及统一 API 错误结构。
- 另以 SQL 连接错误 mock 对 11 个方法逐一复核，`11/11 passed`。
- `get_dashboard_summary` 的既有安全行为未回退。
- API 响应不包含 `password`、`token`、`secret`、`proxy`、traceback、SQL 或内部路径。

## 4. Dashboard、热词与来源统计复验

### 4.1 接口边界

已检查的接口为：

- `/api/foreign/dashboard/summary`
- `/api/foreign/dashboard/trends`
- `/api/foreign/dashboard/risk`
- `/api/foreign/dashboard/events`
- `/api/foreign/dashboard/alerts`
- `/api/foreign/dashboard/sources`
- `/api/foreign/hotwords`
- `/api/foreign/hotwords/trends`
- `/api/foreign/hotwords/sources`
- `/api/foreign/source-distribution`
- `/api/foreign/language-distribution`

服务文件只导入 `CollectorRun`、`ForeignOpinion`、`ForeignRiskResult`、`ForeignEvent`、`ForeignEventOpinion`、`ForeignEventCandidate` 和 `ForeignAlert`。未导入国内 `Opinion`、国内事件、国内告警、国内关键词、敏感词或行政区模型。

### 4.2 结果检查

- 时间窗口统一使用 UTC，并返回 `window_start`、`window_end`、`data_as_of` 和 `timezone`。
- Dashboard 结构区分文章、风险分析状态、风险等级、事件状态、告警状态、采集运行状态。
- 热词只基于外网文章和 confirmed 外网事件；中英文分开处理；`China`、`Chinese`、`中国` 被作为监测词排除，不作为默认热词结果；未读取国内关键词表。
- 来源和语言分布只返回聚合字段；未映射到河北、中国行政区或地图接口。
- 空数据通过稳定的空数组、零值或 `status=empty` 表达；查询失败通过 503 安全错误表达，不伪装为零值。
- `ForeignWorkspace` 的 dashboard、hotwords、sources 页面只调用 `/foreign/*` API，未发现国内 Dashboard、Events、Alerts 或地图 API 调用。

本轮目标测试主要是数据库无关的契约和安全测试，未重新构造完整外网统计 fixture 以核对具体数值。因此上述统计逻辑完成了静态边界和结构复验，但真实样本下的数量、趋势、风险、事件和告警数值仍需在可用隔离数据库中补做端到端验收。

## 5. 前端验收

检查入口：

- `/foreign?tab=dashboard`
- `/foreign?tab=hotwords`
- `/foreign?tab=sources`

结果：

- 三个 tab 的 API 调用均位于 `/foreign/*` 范围内。
- `loading`、空数据、失败和 stale 状态有独立分支或展示标记。
- `visualizationFailure` 只按状态码和白名单 `error_code` 映射固定消息，不读取 `response.data.detail`。
- 页面不渲染数据库错误、路径、SQL、Token、代理或异常堆栈。
- sources 入口明确标注无地图；静态扫描未发现地图、`region_id` 或中国行政区调用。
- 国内 Dashboard、热词、地图和事件页面未被修改为调用外网接口。

## 6. 国内/国外数据隔离

### 6.1 代码隔离

- 外网可视化服务没有国内业务模型导入。
- 外网接口挂载在 `/api/foreign/*`，未复用国内 Dashboard、热词、Events 或 Alerts API。
- 外网统计方法没有写操作；没有新增统计快照表、运行日志或国内统计表写入。
- 统计失败不会修改国内数据。

### 6.2 只读快照

默认库只读身份检查确认：数据库为 `opinion_db`，revision 为 `foreign_source_1`；本次没有对默认库执行迁移或写入。当前可读国内快照包含 `opinions=1702`、`events=292`；默认库未处于 3A/3B/3C 完整生产迁移状态，部分外网告警统计表不可用，符合本阶段不在默认库启用 3D 的限制。

隔离测试数据库由测试公共 fixture 指向 `opinion_test:5433`。本轮 3D 目标测试使用 mock，不写入数据库；可读的基础快照为 `opinions=2`、`events=0`、`event_opinions=0`。由于该连接端点在本轮复核期间出现等待，未把不稳定的外网表计数作为功能验收依据。测试前后没有执行任何写入、删除或迁移。

结论：没有观察到外网统计写入国内 `alerts`、Dashboard 统计或其他国内业务表；但完整的真实样本前后数值快照需在稳定的隔离数据库连接上补验。

## 7. 测试、编译与构建

已执行：

```text
pytest backend/tests/test_foreign_source_3d.py backend/tests/test_foreign_source_3d_remediation.py -q
115 passed, 1 warning

python -m compileall backend/app backend/tests
通过

cd frontend; npm run build
通过，Vite 2360 modules transformed
```

前端构建只有既有依赖注释和动态/静态导入提示，没有构建失败。

`git diff --check` 没有发现空白错误，仅输出工作区既有文件的 LF/CRLF 转换警告。

## 8. 跨 Phase 集成超时复核

命令：

```text
pytest backend/tests/test_foreign_source_phase1.py backend/tests/test_foreign_source_phase1_1.py backend/tests/test_foreign_source_3a.py backend/tests/test_foreign_source_3b.py backend/tests/test_foreign_source_3c.py -q --maxfail=1
```

结果：在 60 秒限制内未产生断言输出，命令以超时退出（工具记录约 64 秒，退出码 124）。本轮确认：

- 未看到外部网络请求迹象。
- 未看到数据库错误或锁错误输出。
- 超时后只残留本次命令启动的 pytest 进程，已精确清理；既存 Uvicorn 未停止。
- 当前证据不足以证明是数据库死锁、外部网络等待或本次 3D Remediation 引入的功能回归。
- 同一跨 Phase 命令在前一轮 3D Remediation 验证中已有相同超时记录，因此暂按既有本地 pytest/集成 fixture 或连接环境基线问题分类。

该问题尚未完成根因定位，故不能把跨 Phase 全量回归标记为通过。它是生产人工灰度的阻塞项，但不是本次敏感信息修复已引入真实回归的证据。

## 9. 已知国内基线失败

本轮没有修改国内代码、国内测试断言或国内数据库。跨 Phase 测试仅表现为超时，没有新的国内断言失败输出；既有国内基线失败继续按历史/环境问题保留，未被删除、放宽或掩盖。后续需在稳定隔离测试环境中单独完成国内风险、事件、告警和 Dashboard 聚焦回归。

## 10. 地图状态

外网地图仍未实现，也没有隐藏地图请求。sources tab 采用来源、语言和趋势聚合替代，不把来源国家当成舆情发生地，不使用国内 `region_id`，不映射到河北或全国地图。

## 11. 最终 Go/No-Go

### 已通过

- 3D Remediation 的统一安全错误处理：通过。
- 11 个方法的 6 类敏感异常响应矩阵：通过。
- 前端错误白名单和外网 API 边界：通过。
- Python 编译和前端构建：通过。
- 默认数据库未迁移、未写入；外网源、调度和通知未启用：通过。

### 尚未通过或需补验

- 完整真实样本 Dashboard/热词/来源数值验收：未完成。
- 跨 Phase 集成测试：60 秒超时，尚未完成根因定位。
- 稳定隔离数据库前后数据快照：需补做，当前仅有基础只读快照和数据库无关 fixture 结果。

### 决策

1. **3D Remediation 安全修复项：GO。**
2. **完整 Phase 3D 结果重新验收：条件性通过，不宣称全部通过。**
3. **生产人工灰度：NO-GO。** 在稳定隔离数据库上完成真实外网 fixture 数值验收，并解决或明确跨 Phase 超时根因后，才可重新评估。
4. 不允许启用外网源、自动调度、自动告警或外部通知。
5. 不允许执行默认 `opinion_db` 的迁移、写入、删除或 downgrade。

## 12. 最终确认

- 未修改代码。
- 未修改配置。
- 未修改数据库结构。
- 未写入默认数据库或生产数据。
- 未启用外网源。
- 未启用自动调度或自动告警。
- 未调用真实 RSS、外部 AI、代理或境外节点。
- 未发送外部通知。
- 未实现外网地图。
- 本次没有发现新的敏感信息泄露；在已覆盖的 11×6 矩阵范围内风险已关闭。
- 完整 3D 结果验收因统计 fixture 和跨 Phase 超时仍需补验，生产灰度不允许进入。
