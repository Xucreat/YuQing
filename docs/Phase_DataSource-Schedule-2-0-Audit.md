# Phase DataSource-Schedule-2-0 调度运营能力实施前只读审计

- **审计目标**：评估当前 `Scheduler / CollectorRun / DataSource` 数据是否足以支撑「调度运营中心」建设。
- **审计性质**：**严格只读**（不修改代码 / 不修改数据库 / 不新增字段 / 不执行迁移 / 不改变 Scheduler·Collector 行为）。
- **审计日期**：2026-08-03
- **审计人**：Senior Developer（高级开发工程师）
- **结论速览**：✅ **核心运营能力可零新增字段、零迁移落地**；全部所需数据已存在于 `data_sources` + `collector_runs` + `DataSourceHealthSummaryService`，并通过既有 API 暴露。仅需在「聚合统计」与「前端可视化」两层做轻量补充。

---

## 0. 审计范围与合规声明

| 范围 | 审计对象 | 是否只读 |
| --- | --- | --- |
| backend scheduler | `backend/app/core/scheduler.py` | ✅ 仅读 |
| collector_runs 表 | `backend/app/models/collector_run.py` | ✅ 仅读 |
| data_sources 表 | `backend/app/models/data_source.py` | ✅ 仅读 |
| CollectorRun 模型 | 同上 | ✅ 仅读 |
| 数据源 API | `backend/app/api/admin_data_sources.py`、`backend/app/api/collector.py` | ✅ 仅读 |
| 前端数据管理结构 | `frontend/src/views/Sources.vue`、`frontend/src/types/index.ts` | ✅ 仅读（node 读取，未改） |

**未做任何修改**：未触碰任何 `.py` / `.vue` / `.ts` / 配置 / 数据库 / 迁移文件。本报告仅描述现状与建议。

---

## 1. 当前调度数据模型

### 1.1 `data_sources` 表（数据源 + 调度配置主轴）

| 字段 | 类型 | 说明 | 运营中心可用性 |
| --- | --- | --- | --- |
| `id` | int PK | 主键 | ✅ 标识 |
| `key` | str(64) unique | 内部标识（baidu_news 等） | ✅ |
| `name` | str(128) | 显示名 | ✅ |
| `type` | str(32) | gov_site/news_site/search/rss | ✅ |
| `class_path` | str(256) | 采集器类路径 | ➖ 内部用 |
| `enabled` | bool | 启用/停用 | ✅ 纳入运营看板 |
| `priority` | int | 兜底优先级 | ✅ |
| `schedule_enabled` | bool (default true) | **是否纳入自动调度** | ✅ 关键调度字段 |
| `schedule_interval_minutes` | int (default 30, CHECK≥5) | **采集间隔（分钟）** | ✅ 关键调度字段 |
| `next_collect_time` | DateTime null | **下次自动采集时间**（scheduler tick 据此派发） | ✅ 关键调度字段 |
| `last_collect_time` | DateTime null | 上次自动采集时间 | ✅ 关键调度字段 |
| `scope_region_codes` | str(256) null | 覆盖区域（CSV / ALL） | ✅ |
| `config_json` | Text null | 站点专属配置 | ➖ |
| `last_run_at` | DateTime null | **运行态缓存列** | ⚠️ 见 1.4 |
| `last_status` | str(16) null | **运行态缓存列** | ⚠️ 见 1.4 |
| `last_error` | Text null | **运行态缓存列** | ⚠️ 见 1.4 |
| `created_at` / `updated_at` | DateTime | 时间戳 | ✅ |

### 1.2 `collector_runs` 表（每次采集的运行记录——运营事实源）

| 字段 | 类型 | 说明 | 运营中心可用性 |
| --- | --- | --- | --- |
| `id` | int PK | 主键 | ✅ |
| `collector_name` | str(128) | 采集器名（== `data_sources.name`） | ✅ 关联键 |
| `batch_id` | str(64) null, index | **一次触发（手动/定时）内所有源共享** | ✅ 批次追溯 |
| `trigger_type` | str(16) null | **`manual` / `scheduled`** | ✅ 区分来源 |
| `start_time` / `end_time` | DateTime | 起止时间 | ✅ 耗时/SLA |
| `fetched_raw` / `upstream_total` / `upstream_returned` | int | 抓取量 | ✅ |
| `created` / `duplicate` / `analyzed` / `failed` | int | 入库/去重/分析/失败计数 | ✅ 质量指标 |
| `acknowledged` / `unconfirmed` / `ack_status` | int/str | 确认状态 | ✅ |
| `comments_seen` / `comments_skipped` / `admission_filtered` | int | 评论/准入 | ➖ |
| `status` | str(16) | running/success/failed/… | ✅ 运行状态 |
| `error_msg` | Text null | 错误详情 | ✅ 失败归因 |

> 关键事实：`collector_runs` 已具备「逐源 + 逐批次 + 触发方式 + 成功/失败计数 + 耗时 + 错误」的完整运营审计链，是建设运营中心的**事实主表**。

### 1.3 Scheduler 调度逻辑（`backend/app/core/scheduler.py`）

- **逐源 tick 路径**：`due_scheduled_sources(db)` 选自 `enabled AND schedule_enabled AND key != 'weibo_octopus' AND (next_collect_time IS NULL OR next_collect_time <= now())`，返回 `{id, key, schedule_enabled, schedule_interval_minutes, next_collect_time}`。claim 后推进 `next_collect_time`。
- **cron 候选路径**：`cron_candidate_sources(db)` 选启用且开启自动采集的源（不考虑 `next_collect_time`，由全局 cron 驱动）。
- **单例保护**：`pg_try_advisory_lock` 保证多 uvicorn 实例下仅一个真正调度，Grok 等启用后不会双采。
- 行为边界：**本审计未改变上述任何逻辑**。

### 1.4 `DataSource.last_run_at/last_status/last_error` 现状（重要）

- 三列物理存在（迁移 `0004_phase3_datasource_region_parent.py` 已建）。
- **代码审计确认：采集服务运行中从不写回这三列**（grep 全仓仅 `admin_data_sources.py` 序列化读取，且恒为 `None`；`data_source_health.py` 的健康摘要是从 `collector_runs` 重新计算的，不依赖这三列）。
- 结论：**这三列不能作为运营事实字段**，运营中心应统一以 `collector_runs` + `DataSourceHealthSummaryService` 为真相源。

### 1.5 既有数据源 API（运营中心可直接调用）

| 方法 / 路径 | 权限 | 返回 / 作用 |
| --- | --- | --- |
| `GET /api/admin/data-sources` | sources:read | 列表；每项含 `schedule_enabled`、`schedule_interval_minutes`、`next_collect_time`、`last_collect_time`、`latest_run_status`、`latest_run_at`、**`health_summary`** |
| `PATCH /api/admin/data-sources/{id}` | require_admin | 单源改 `enabled/priority/schedule_enabled/schedule_interval_minutes`（改间隔自动重算 `next_collect_time`） |
| `POST /api/admin/data-sources/schedule/batch` | require_admin | 批量设 `scope=all|enabled_only` 的 `schedule_enabled`/`interval_minutes`，按 id 错峰重算 `next_collect_time` |
| `GET /api/admin/data-sources/schedule/summary` | 登录 | `{mode: uniform|mixed, interval_minutes, distribution, enabled_auto_count}` |
| `GET /api/admin/data-sources/{id}/runs` | sources:read | 该源 `collector_runs` 分页（`_run_to_dict`：含 `batch_id`、`trigger_type`、`status`、`error_msg` 等） |
| `POST /api/collector/run` | require_admin | **手动触发采集**，支持 `data_source_ids` 指定单/多源；自动聚合；写审计 `COLLECT_RUN` |
| `GET /api/collector/status` | 登录 | 内存态采集进度（**重启丢失**，非持久） |

### 1.6 健康计算服务（`DataSourceHealthSummaryService`）

从 `collector_runs` 动态算出每源健康快照（不落库）：
`health_status`(healthy/degraded/unhealthy/paused/unknown)、`last_run_at`、`last_success_at`、`last_failure_at`、`consecutive_failures`、`last_error_code`、`last_error_message`、`last_valid_data_time`、`data_freshness`(fresh/stale)、`health_reason`。

### 1.7 前端现状（`Sources.vue` + `types/index.ts`）

- 表格已含运营相关列：**健康状态**、最近状态、最近抓取/新增、采集质量、最近运行时间、**自动采集**(switch)、**采集周期**、**下一次采集**、**最近采集**、操作（含「调度」单源 PATCH、「统一采集频率设置」批量）。
- 「查看历史」弹窗调用 runs 接口，展示 `CollectorRunItem` 列表。
- 类型齐备：`DataSourceItem`、`DataSourceHealthSummary`、`DataSourceScheduleSummary`、`DataSourceScheduleBatchRequest/Response`、`CollectorRunItem`。

---

## 2. 可直接复用字段（零成本）

运营中心建设**无需新字段**即可复用的资产：

**A. 调度配置（来自 `data_sources`）**
- `schedule_enabled`、`schedule_interval_minutes`、`next_collect_time`、`last_collect_time`、`enabled`、`priority`、`scope_region_codes`、`name`、`key`、`type`。

**B. 运行事实（来自 `collector_runs`，经 `/runs` 或聚合查询）**
- `trigger_type`（手动/定时区分）、`batch_id`（批次追溯）、`start_time`/`end_time`（耗时/SLA）、`status`、`fetched_raw`/`created`/`duplicate`/`analyzed`/`failed`（质量）、`error_msg`（归因）。

**C. 健康快照（来自 `DataSourceHealthSummaryService`）**
- `health_status`、`consecutive_failures`、`last_error_code`、`last_valid_data_time`、`data_freshness`、`health_reason`。

**D. 既有 API（直接调用，不改后端）**
- 列表 / 单源 PATCH / 批量 / summary / runs / 手动触发 `collector/run`。

**E. 既有前端类型与组件**
- `DataSourceItem`、`DataSourceHealthSummary`、`CollectorRunItem`、`DataSourceScheduleSummary`；Sources.vue 的表格列、健康 pill、历史弹窗、调度弹窗均可复用或迁移。

---

## 3. 缺失能力（运营中心视角）

| # | 缺失能力 | 影响 | 现状缺口 |
| --- | --- | --- | --- |
| M1 | **跨源调度总览聚合** | 无法一眼看到「X 个正常 / Y 个降级 / Z 个异常」「统一/混合模式」 | `/schedule/summary` 只给模式+计数，无健康分布；需前端从列表 `health_summary` 聚合或新增聚合接口 |
| M2 | **采集运行统计（时间维度）** | 无「近 24h 运行次数 / 成功 / 失败 / 平均耗时」 | `collector_runs` 有数据，但**无统计接口**，前端只能逐源拉取（重） |
| M3 | **成功率趋势 / 健康时间线** | 无法画 sparkline / 趋势图 | 健康服务只返回最新快照，无历史序列 |
| M4 | **调度时间线视图** | 无「未来 N 小时内各源何时跑」的排程表 | 需前端按 `next_collect_time` 排序自绘 |
| M5 | **失败告警面板** | 异常源无集中暴露 | 需前端筛 `health_status ∈ {unhealthy, degraded}` |
| M6 | **手动触发入口（前端）** | `POST /collector/run` 已存在但**前端无按钮** | 仅后端能力，UI 未接 |
| M7 | **实时进度持久化** | `collector/status` 重启即失 | 仅影响「进行中」可视化，完成后 `collector_runs` 已落库 |
| M8 | **SLA/新鲜度阈值配置暴露** | 健康服务的 `fresh_within_hours`/`stale_after_days` 为硬编码默认 | 如需可调需改配置（非本阶段必要） |
| M9 | **前端 `CollectorRunItem` 缺字段** | 类型无 `trigger_type`/`batch_id`/`upstream_total` | 后端 `_run_to_dict` 已返回，前端类型需补（小改，非 DB 字段） |

> 注：M1–M6 均为**展示/聚合层**缺失，根数据均已存在；M7 为已知固有限制（不影响历史运营分析）。

---

## 4. 是否需要新增表 / 字段

**结论：建设「调度运营中心（只读可视化 + 既有手动触发 + 调度管理）」——不需要新增任何表或字段。**

| 场景 | 是否需新增 | 说明 |
| --- | --- | --- |
| 运营中心 v1（看板 + 健康分布 + 调度时间线 + 手动触发 + 失败面板） | ❌ 不需要 | 全部复用 §2 字段与 API |
| 若需「缓存每源健康快照，免每次重算」 | ⚠️ 可选 | 可加 `DataSource.health_status`/`last_success_at`/`last_failure_at`/`consecutive_failures`/`last_error_code`（Phase 8 已规划的候选列）——但**非必须**，运营中心可在读取时计算 |
| 若需「健康/运行指标时间线」 | ⚠️ 可选 | 可加 `data_source_health_snapshots` 表或物化视图做时序存储 |
| 若需「失败自动告警」 | ⚠️ 可选 | 需新增通知/告警表或接入外部通道 |

> 本阶段边界（只读审计）下，**推荐 v1 路线：零新增字段、零迁移**，所有能力用现有数据 + 只读聚合查询 + 前端可视化实现。新增表/字段列为「可选增强」，留待后续阶段决策。

---

## 5. 前端展示建议

### 5.1 推荐结构：新增独立「调度运营中心」视图（不污染数据源管理）

- 路由：`/operations`（或 `DataManage` 新增 tab「运营中心」），复用既有 `api` 实例与 `usePermission().isSuperuser` 门禁。
- 组件建议：
  1. **总览卡片区**：调用 `GET /schedule/summary` + 列表 `health_summary` 聚合 → 展示「启用源数 / 自动采集数 / 模式(uniform+mixed)/健康分布(正常·降级·异常)」。
  2. **运行统计卡片**（M2）：新增轻量只读统计接口或前端基于 `/runs` 聚合 → 「近24h 运行次数 / 成功 / 失败 / 平均耗时」。
  3. **调度时间线**（M4）：按 `next_collect_time` 升序，展示「未来 24h 各源采集排程」列表/甘特。
  4. **数据源健康表**（复用 Sources.vue 列）：健康状态 / 自动采集 / 采集周期 / 下一次采集 / 最近采集 / 最近状态；行内「查看历史」「调度」复用既有弹窗。
  5. **失败告警面板**（M5）：筛 `health_status ∈ {unhealthy, degraded}`，展示 `last_error_code` + `health_reason` + 连续失败次数。
  6. **手动采集按钮**（M6）：调用既有 `POST /collector/run`（可选 `data_source_ids`）；触发后轮询 `collector/status` 或刷新 runs。

### 5.2 可直接复用的前端资产

- 类型：`DataSourceItem`、`DataSourceHealthSummary`、`CollectorRunItem`（建议补 `trigger_type`/`batch_id`）、`DataSourceScheduleSummary`。
- 组件/样式：Sources.vue 的「健康 pill」(`healthPill`/`healthText`)、「采集质量」渲染、「查看历史」弹窗、`formatTime()`。
- API 封装：沿用单一 `api` 实例内联 URL 风格（与现有 `Sources.vue` 一致）。

### 5.3 体验增强（premium 取向，可选）

- `next_collect_time` 渲染为相对倒计时（「约 12 分钟后」），hover 显示绝对时间。
- 健康分布用环形/条形图（ECharts 已集成于项目）。
- 失败面板用红色态 + 磁吸悬停微交互。
- 暗色/亮色主题切换（项目既有规范，运营中心须遵循）。

---

## 6. 下一阶段实施计划（Phase DataSource-Schedule-2-1，草案）

> 以下为「实施前规划」，须经授权后进入实现；本阶段**不执行**。

### 6.1 后端（最小、只读、零迁移）

| 任务 | 内容 | 是否改表 |
| --- | --- | --- |
| B1 | 新增 `GET /api/admin/data-sources/schedule/overview`：聚合 summary + 健康分布 + 可选运行统计（基于现有查询，纯读） | ❌ |
| B2 | 新增 `GET /api/admin/collector-runs/stats?range=24h`：总次数/成功/失败/平均耗时/逐源成功率（对 `collector_runs` 聚合查询） | ❌ |
| B3 | 确认 `POST /collector/run` 的 `data_source_ids` 手动触发契约，供前端接入（**已实现，仅接线**） | ❌ |
| B4（可选） | 扩展 `CollectorRunItem` 返回（前端类型补 `trigger_type`/`batch_id`） | ❌ |

### 6.2 前端（新建视图，复用既有）

| 任务 | 内容 |
| --- | --- |
| F1 | 新增 `OperationsCenter.vue`（或 `DataManage` tab），含总览卡片 / 统计卡片 / 调度时间线 / 健康表 / 失败面板 / 手动采集按钮 |
| F2 | 复用 Sources.vue 的健康 pill、历史弹窗、调度弹窗逻辑 |
| F3 | 补 `types/index.ts`：`CollectorRunItem` 增加 `trigger_type`/`batch_id`（小改，非 DB 字段） |
| F4 | 遵循主题切换与 premium 交互规范 |

### 6.3 边界红线（与本次审计一致）

- ❌ 不新增/修改数据库字段、不执行迁移。
- ❌ 不改变 Scheduler / Collector 的派发与采集行为（仅新增只读聚合查询 + 调用既有手动触发 API）。
- ❌ 不引入消息队列 / ES / Redis（项目既有红线）。
- ❌ 不触碰事件聚合与风险模型。

### 6.4 验收标准（草案）

- [ ] 运营中心页展示：健康分布、模式、近24h运行统计、调度时间线。
- [ ] 失败面板正确列出 unhealthy/degraded 源及错误码。
- [ ] 「手动采集」按钮可触发 `collector/run` 并刷新 runs。
- [ ] 全量复用既有 API 与类型，无新增 DB 字段、无迁移。
- [ ] 构建通过、页面加载 < 1.5s、主题切换正常。

---

## 7. 审计结论

✅ **当前 `Scheduler / CollectorRun / DataSource` 数据模型已具备支撑调度运营中心的核心能力**：调度配置（`schedule_*`/`next_collect_time`/`last_collect_time`）、运行事实（`collector_runs` 全量字段）、健康快照（`DataSourceHealthSummaryService`）三套数据齐备，且均已通过既有 API 暴露。

⚠️ **唯一需澄清的陷阱**：`DataSource.last_run_at/last_status/last_error` 三列**恒为空、不可信**，运营中心必须改用 `collector_runs` + 健康服务作为真相源（本报告已规避）。

🚀 **建议下一阶段（2-1）走「零新增字段 / 零迁移」路线**：仅新增 1–2 个只读聚合 API + 一个前端运营中心视图，即可交付完整的调度运营中心，完全符合本次只读审计的五项严格要求。
