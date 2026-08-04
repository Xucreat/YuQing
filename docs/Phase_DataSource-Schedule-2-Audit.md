# Phase DataSource-Schedule-2-A 数据采集运行监控中心 · 实施前只读审计

- **审计目标**：确认在不改采集逻辑 / 不改 Scheduler / 不新增 DB 字段的前提下，能否建设「数据采集运行监控能力」。
- **审计性质**：**严格只读**——❌ 不修改代码 / 数据库 / 字段，❌ 不跑 migration，❌ 不改 Scheduler / Collector / 采集流程。
- **审计日期**：2026-08-03
- **审计人**：Senior Developer（高级开发工程师）
- **结论速览**：✅ **数据充足，可在零新增字段、零迁移下建设监控中心**；现有 `data_sources` + `collector_runs` + `DataSourceHealthSummaryService` 已覆盖全部所需事实，前端 Sources.vue 组件可大量复用。仅需（可选）新增 1–2 个只读聚合接口。

---

## 0. 审计合规声明

本轮审计**未做任何修改**：未触碰 `.py` / `.vue` / `.ts` / 配置 / 数据库 / 迁移。以下所有结论均基于只读检查。

---

## 确认项核对表（用户指定检查点）

### 后端

| # | 确认项 | 结果 | 证据 |
| --- | --- | --- | --- |
| 1 | `schedule_enabled` | ✅ 存在 | `backend/app/models/data_source.py:38` |
| 1 | `schedule_interval_minutes` | ✅ 存在 | `data_source.py:40`（默认30，CHECK≥5） |
| 1 | `next_collect_time` | ✅ 存在 | `data_source.py:42` |
| 1 | `last_collect_time` | ✅ 存在 | `data_source.py:44` |
| 2 | `status` | ✅ 存在 | `backend/app/models/collector_run.py:32` |
| 2 | `trigger_type` | ✅ 存在 | `collector_run.py:14`（`manual`/`scheduled`，历史 NULL） |
| 2 | `batch_id` | ✅ 存在 | `collector_run.py:12`（同触发共享，index） |
| 2 | `start_time` / `end_time` | ✅ 存在 | `collector_run.py:15-16` |
| 2 | `fetched_raw` | ✅ 存在 | `collector_run.py:17` |
| 2 | `created` | ✅ 存在 | `collector_run.py:20` |
| 2 | `duplicate` | ✅ 存在 | `collector_run.py:21` |
| 2 | `failed` | ✅ 存在 | `collector_run.py:23` |
| 2 | `error_msg` | ✅ 存在 | `collector_run.py:33` |
| 3 | 健康状态计算 | ✅ 已有 | `backend/app/services/data_source_health.py` → `DataSourceHealthSummaryService.summarize()` |
| 3 | 失败次数统计 | ✅ 已有 | `health_reason` 含 `consecutive_failures`（连续失败次数） |
| 3 | 最近运行状态 | ✅ 已有 | list 序列化返回 `latest_run_status` / `latest_run_at`（`admin_data_sources.py:303-304`）+ 每源 `health_summary` |

> ⚠️ **陷阱提示**：`DataSource.last_run_at` / `last_status` / `last_error`（`data_source.py:51-53`）物理存在，但采集流程**从不写回（恒为 NULL）**，监控中心必须改用 `collector_runs` + 健康服务，不可信这三列。

### 前端

| # | 确认项 | 结果 | 证据 |
| --- | --- | --- | --- |
| - | 健康状态展示 | ✅ 可复用 | `Sources.vue:91-97` 健康 pill（`healthPill`/`healthText`） |
| - | 运行历史弹窗 | ✅ 可复用 | `Sources.vue:148`「查看历史」→ `openHistory` → `GET /{id}/runs`（`Sources.vue:655-670`） |
| - | 调度配置弹窗 | ✅ 可复用 | 单源「调度」PATCH 弹窗 + 批量「统一采集频率设置」弹窗（`Sources.vue` 已含） |
| - | 时间格式化 | ✅ 可复用 | `Sources.vue` `formatTime()` 已存在 |

---

## 1. 当前能力

**调度配置能力（已上线，来自 Phase DataSource-Schedule-1）**
- 单数据源自定义采集频率（`PATCH /api/admin/data-sources/{id}`）。
- 全部/启用源统一频率（`POST /api/admin/data-sources/schedule/batch`）。
- 自动采集开关（`schedule_enabled`）。
- 下次采集时间展示（`next_collect_time`，前端已渲染）。

**运行数据采集能力（已有）**
- 每次采集在 `collector_runs` 落一条完整记录：`trigger_type`、`batch_id`、`start_time`、`end_time`、`status`、`fetched_raw`、`created`、`duplicate`、`analyzed`、`failed`、`error_msg` 等。
- 手动触发 `POST /api/collector/run`（支持 `data_source_ids` 指定单/多源），自动聚合，写审计 `COLLECT_RUN`。
- Scheduler 双路径（逐源 tick `due_scheduled_sources` + cron 候选），`pg_try_advisory_lock` 单例保护。

**健康计算能力（已有，动态、不落库）**
- `DataSourceHealthSummaryService` 从 `collector_runs` 算出：`health_status`(healthy/degraded/unhealthy/paused/unknown)、`last_run_at`、`last_success_at`、`last_failure_at`、`consecutive_failures`、`last_error_code`、`last_error_message`、`last_valid_data_time`、`data_freshness`(fresh/stale)、`health_reason`。
- 列表接口 `GET /api/admin/data-sources` 每项内含 `health_summary` + `latest_run_status` + `latest_run_at`。

**前端可视化能力（已有）**
- Sources.vue 已渲染：健康状态 pill、自动采集 switch、采集周期、下一次采集、最近采集、最近状态、最近抓取/新增、采集质量、查看历史弹窗、调度弹窗。

---

## 2. 可复用数据

**A. 调度配置（来自 `data_sources`，零成本）**
`schedule_enabled`、`schedule_interval_minutes`、`next_collect_time`、`last_collect_time`、`enabled`、`priority`、`name`、`key`、`type`、`scope_region_codes`。

**B. 运行事实（来自 `collector_runs`，经 `GET /{id}/runs` 或聚合查询）**
`trigger_type`（手动/定时区分）、`batch_id`（批次追溯）、`start_time`/`end_time`（耗时）、`status`、`fetched_raw`/`created`/`duplicate`/`analyzed`/`failed`（质量计数）、`error_msg`（失败归因）。

**C. 健康快照（来自 `DataSourceHealthSummaryService`，列表已带）**
`health_status`、`consecutive_failures`、`last_error_code`、`last_error_message`、`last_failure_at`、`last_valid_data_time`、`data_freshness`、`health_reason`。

**D. 既有 API（直接调用，不改后端）**
- `GET /api/admin/data-sources`（含 health_summary / latest_run_status / latest_run_at / schedule_*）
- `GET /api/admin/data-sources/{id}/runs`（逐源运行记录，`_run_to_dict` 含 `trigger_type`/`batch_id`/`status`/`error_msg`）
- `GET /api/admin/data-sources/schedule/summary`（uniform/mixed 模式）
- `POST /api/collector/run`（手动补采入口，支持 `data_source_ids`）

**E. 前端可复用资产**
- 类型：`DataSourceItem`、`DataSourceHealthSummary`、`CollectorRunItem`（建议补 `trigger_type`/`batch_id`）、`DataSourceScheduleSummary`。
- 组件/函数：健康 pill（`healthPill`/`healthText`）、运行历史弹窗（`openHistory`）、调度弹窗、`formatTime()`。

---

## 3. 缺失能力

| # | 缺失能力 | 说明 | 根数据是否具备 |
| --- | --- | --- | --- |
| L1 | **跨源总览聚合**（总数/启用/自动/健康分布） | 现有 list 返回每项 health，但无「一键汇总」接口；前端需自行聚合或新增 overview 接口 | ✅ 数据齐，缺聚合入口 |
| L2 | **近 24h 运行统计**（总次数/成功/失败/平均耗时/失败率） | `collector_runs` 有数据，但**无统计接口**；前端逐源拉取过重 | ✅ 数据齐，缺统计接口 |
| L3 | **异常数据源列表视图** | 需筛 `health_status ∈ {unhealthy, degraded}`，前端可基于 list 做，但无专门接口/视图 | ✅ 可复用 list 筛选 |
| L4 | **最近运行记录视图** | 可复用 `/{id}/runs` + 跨源查询（目前仅逐源，无全局最近运行） | ⚠️ 逐源有，缺全局 |
| L5 | **前端手动补采按钮** | `POST /collector/run` 已存在但前端无入口 | — 前端未接 |
| L6 | **前端 `CollectorRunItem` 缺字段** | 类型无 `trigger_type`/`batch_id`/`upstream_total` | 后端已返回，前端类型小改 |

> 注：L1–L5 均为**聚合/展示层缺失**，根数据已全部存在；不改变采集与 Scheduler 即可补齐。

---

## 4. 是否需要新增字段

**结论：❌ 不需要新增任何数据库字段。**

- 监控中心所需全部字段已存在于 `data_sources`（`schedule_*` / `next_collect_time` / `last_collect_time`）与 `collector_runs`（运行全字段）及动态健康服务。
- 若未来要「缓存每源健康快照免重算」，可加 `DataSource.health_status` 等列（Phase 8 候选），但**本阶段非必须**，监控中心在读取时计算即可。
- 严禁新增表/字段，符合本阶段红线。

---

## 5. 是否需要新增接口

**结论：核心监控可零新增接口复用现有 API；为获得「总览计数」与「近24h统计」建议新增 2 个只读聚合接口（纯 SELECT，不改表、不改采集）。**

| 接口 | 是否必须 | 替代方案 |
| --- | --- | --- |
| `GET /api/admin/data-sources/monitor/overview` | 推荐（对应 2-B 规划） | 可由前端拉全量 list 后本地聚合，但源多时偏重；后端聚合更优 |
| `GET /api/admin/collector-runs/stats`（近24h） | 推荐（对应 2-B 规划） | 现有无统计接口；逐源 `/runs` 累加过重，建议后端只读聚合 |
| 异常列表 / 最近运行 | 否，可复用 | `GET /admin/data-sources`（带 health_summary）+ `GET /{id}/runs` 即可 |

> 两个新接口均为**只读 SELECT 聚合**，不写库、不触发采集、不影响 30 分钟自动调度，完全符合「不改变 Scheduler / Collector / 采集流程」约束。

---

## 6. 推荐实施范围（Phase DataSource-Schedule-2-B 草案，待授权）

> 以下为「实施后规划」，本阶段**不执行**；须获授权后进入。

### 后端（仅只读聚合，零字段/零迁移）
- `GET /api/admin/data-sources/monitor/overview` → `{ total_sources, enabled_sources, auto_sources, healthy_count, degraded_count, failed_count, latest_runs[] }`（基于现有查询聚合）。
- `GET /api/admin/collector-runs/stats?range=24h` → `{ last24h_total, success_count, failed_count, avg_duration, failure_rate }`（对 `collector_runs` 聚合）。
- 可选：扩展 `CollectorRunItem` 返回（前端类型补 `trigger_type`/`batch_id`）——仅改序列化字段，不动表。

### 前端（新建视图，复用既有）
- 新增 `DataSourceMonitor.vue`：
  1. **总览卡片**：数据源总数 / 自动采集数 / 正常数 / 异常数（调 overview）。
  2. **异常数据源列表**：名称 + 最近失败时间 + 错误原因 + 连续失败次数（筛 health_status）。
  3. **最近运行记录**：数据源 + 触发方式 + 开始/结束时间 + 状态（调 stats / runs）。
  4. **手动补采入口**：复用 `POST /api/collector/run`（可选 `data_source_ids`）。
- 复用 Sources.vue 的健康 pill、`formatTime()`、历史弹窗逻辑。
- 遵循项目主题切换与 premium 交互规范。

### 边界红线（与本次审计一致）
- ❌ 不新增/修改数据库字段、不执行迁移。
- ❌ 不改变 Scheduler / Collector / 采集流程；不影响现有 30 分钟自动采集。
- ❌ 不影响数据源管理页面（新增独立视图，不改动 Sources.vue 既有行为）。
- ❌ 不引入 Redis / ES / MQ / Celery / 任务队列。

### 验收标准（草案）
- [ ] 不修改数据库结构、不修改 Scheduler / Collector。
- [ ] 不影响现有 30 分钟自动采集与数据源管理页面。
- [ ] 监控视图展示总览卡片 + 异常列表 + 最近运行 + 手动补采。
- [ ] 构建通过、页面加载 < 1.5s、主题切换正常。
- [ ] 形成实施报告。

---

## 7. 审计结论

✅ **数据模型已完全具备建设「数据采集运行监控中心」的条件**：调度配置（`schedule_*`/`next_collect_time`）、运行事实（`collector_runs` 全字段）、健康快照（`DataSourceHealthSummaryService`）三套数据齐备，前端 Sources.vue 健康展示 / 历史弹窗 / 调度弹窗 / 时间格式化均可复用。

🚀 **推荐路线**：零新增字段、零迁移；后端仅新增 2 个只读聚合接口（overview / stats），前端新建 `DataSourceMonitor.vue` 复用既有资产，即可交付完整监控中心，严守本阶段全部红线。

---

**本阶段（只读审计）已完成，已停止。等待下一步授权进入 Phase DataSource-Schedule-2-B 实施。**
