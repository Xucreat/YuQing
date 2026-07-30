# Phase 8-0 + Phase 8-A 第一阶段实施报告

## 1. 修改文件

### 后端

- `backend/app/services/error_codes.py`：新增 Python 层 `ErrorCode` 枚举和错误文本映射；HTTP 401、token invalid、unauthorized、access token expired 统一映射为 `TOKEN_EXPIRED`。
- `backend/app/services/data_source_health.py`：新增 `DataSourceHealthSummaryService`，基于 `DataSource` 与最近 `CollectorRun` 计算健康摘要，不落库。
- `backend/app/api/admin_data_sources.py`：`GET /admin/data-sources` 增加 `health_summary`。
- `backend/app/services/event/risk_shadow.py`：新增 `EventRiskShadowService`，输出 `event-risk-shadow-v1`、分数、等级和解释因素。
- `backend/app/services/event/situation.py`：新增 `EventSituationService`，计算事件来源、时间、关键词、热度、趋势、数据充分性和陈旧来源。
- `backend/app/api/events.py`：新增只读 `GET /api/events/{id}/situation`。
- `backend/tests/test_phase8_readonly.py`：新增 Phase 8 健康摘要、错误码和事件影子计算测试。

### 前端

- `frontend/src/types/index.ts`：增加数据源健康摘要类型。
- `frontend/src/components/AppLayout.vue`：将传播入口、页面标题和副标题统一为“来源与时间态势”。
- `frontend/src/views/Sources.vue`：在既有数据源列表展示健康状态、原因、错误码和连续失败次数，保留质量与运行历史。
- `frontend/src/views/EventDetail.vue`：展示事件态势只读摘要、数据充分性和风险因素解释。
- `frontend/src/views/Propagation.vue`：页面语义改为“来源与时间态势”，增加推断关系提示，隐藏传播层级、路径和传播主体展示。

## 2. 架构影响

- 仍为 FastAPI + SQLAlchemy 单体架构，无 ES、Redis、Kafka、微服务或新的监控系统。
- 健康摘要和事件态势均为请求时只读计算，复用现有 `CollectorRun`、`DataSource`、`EventOpinion`、`Opinion`。
- 现有采集、事件聚合、告警触发和 `Event.risk_score` 未被替换。影子风险只作为解释性建议结果返回。
- `CollectorRun.error_msg` 保持原始错误文本；标准错误码只在健康摘要中派生。

## 3. 数据库变化说明

- 数据库：无 migration、无新表、无字段变更。
- 数据：无生产数据回写；未修改 `Event`、`Opinion`、`AlertRecord`、`CollectorRun` 历史记录。

## 4. 新增接口与响应能力

- `GET /api/admin/data-sources`：每个数据源增加 `health_summary`，包含健康状态、最近运行/成功/失败、连续失败、标准错误码、最近有效数据时间、数据新鲜度和原因。
- `GET /api/events/{id}/situation`：返回 `data_window`、`data_sufficiency`、`source_distribution`、`daily_counts`、`keyword_distribution`/`keyword_counts`、`risk_factors`、`heat`、`trend`、`stale_sources` 和影子风险结果。

## 5. 测试结果

- `python -m compileall -q app`：通过。
- `npm run build`：通过。
- 已将最新 `frontend/dist_new3` 构建产物同步到 `backend/app/static`，FastAPI `8000` 页面实际加载新 bundle。
- `pytest -q tests/test_phase8_readonly.py -k "not situation"`：5 passed。
- 包含真实测试库写入的事件态势集成测试在当前环境因 PostgreSQL 测试库连接超时未完成；未修改任何生产数据。

## 6. 风险说明

- `DataSource` 与 `CollectorRun` 通过 `collector_name == DataSource.name` 关联，保留了现有命名耦合；后续可在不改表的前提下增加稳定 key 关联策略。
- “长期无有效数据”使用服务层时间窗口判定，窗口变化不会回写历史状态。
- 影子风险与现行风险并存，前端已标注为只读研判结果，不能作为告警或处置依据。
- 当前环境缺少可用的 PostgreSQL 测试库，集成测试需要在测试库可用后补跑。

## 7. 后续建议

- 在隔离测试库可用后补跑完整 Phase 8 集成测试和现有回归测试。
- 根据管理员确认的业务口径校准“新鲜数据”与“长期无数据”窗口。
- 后续阶段再评估事件详情中来源/时间态势图表化；本阶段不引入评论、互动快照、EventTask、官方回应模型、图数据库或 AI 自动决策。
