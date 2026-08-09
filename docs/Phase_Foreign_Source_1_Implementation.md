# Phase Foreign-Source-1 实施报告

## 已完成

- 新增独立外网链路：`foreign_keywords`、`foreign_opinions`
- 复用 `data_sources`，通过 `config_json.is_foreign=true` 标记外网源
- 复用 `collector_runs`，通过 `scope='foreign'` 隔离外网日志
- 新增独立外网 API：`/api/foreign/*`
- 新增 `ForeignRSSCollector`
- 新增外网工作台 `/foreign`
- 外网源默认禁用、默认不启用调度
- 外网采集不写入国内 `opinions`，不进入风险/事件/告警/Dashboard/地图/热词链路

## 关键文件

- `backend/alembic/versions/foreign_source_1.py`
- `backend/app/models/foreign_keyword.py`
- `backend/app/models/foreign_opinion.py`
- `backend/app/models/collector_run.py`
- `backend/app/collectors/foreign_rss.py`
- `backend/app/services/foreign_collection_service.py`
- `backend/app/api/foreign.py`
- `backend/app/api/admin_data_sources.py`
- `backend/app/collectors/data_source_repository.py`
- `frontend/src/views/ForeignWorkspace.vue`
- `frontend/src/router/index.ts`
- `backend/tests/test_foreign_source_phase1.py`

## 数据库迁移

- 新增 `foreign_source_1`
- 新增 `foreign_keywords`
- 新增 `foreign_opinions`
- 为 `collector_runs` 增加 `scope`、`proxy_used`
- 初始化 3 条外网关键词：
  - 中国
  - Chinese
  - China
- 初始化 3 个外网数据源：
  - Fox News
  - The Guardian
  - 纽约时报中文网

## 验证结果

- `python -m compileall` 通过
- `pytest backend/tests/test_foreign_source_phase1.py -q -vv --tb=short`：9 passed
- `cd frontend; npm run build` 通过
- `cd backend; alembic current` 显示 `foreign_source_1 (head)`
- `cd backend; alembic upgrade head` 通过

## 仍需注意

- 外网源目前保持默认禁用，启用前仍应确认来源授权与访问频率
- 若后续要开放外网正文抓取，仍需按来源条款继续复核 robots / 订阅限制
- 当前前端外网工作台独立于国内页面，国内页面行为未改动
