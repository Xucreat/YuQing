# Phase DataSource-Schedule-1 — 后端实施报告（Step 1–6，前端暂停）

> 阶段范围：**仅后端**。前端（Sources.vue 调度字段/编辑弹窗/全局设置区）按用户指令在确认后另起 `Phase DataSource-Schedule-1-Frontend`，本报告不包含前端改动。
>
> 实施严格遵循设计文档 `docs/Phase_DataSource-Schedule-1-Design.md` 与总体原则：
> 不引入 Redis / Celery / MQ / 分布式框架；不改变 `CollectorRun` 字段语义、现有 Collector 架构、手动采集行为、`weibo_consumer` 独立链路。

---

## 1. 修改文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app/collectors/service.py` | 代码修复 (M2) | `collect_and_analyze_concurrent()` 内 `resolve_collectors_verbose` 补传 `include/exclude`（L747 附近） |
| `backend/alembic/versions/p12_datasource_schedule.py` | 新增迁移 | 4 个调度字段 + CHECK + `id%5` 错峰初始化 |
| `backend/app/models/data_source.py` | 模型同步 | `DataSource` 增加 4 个映射列 |
| `backend/app/api/admin_data_sources.py` | API 新增/增强 | PATCH 支持 `schedule_enabled`/`schedule_interval_minutes`；新增 `POST /schedule/batch`、`GET /schedule/summary`；`_serialize` 增加 4 字段 |
| `backend/app/api/collector.py` | API 增强 | `POST /collector/run` 新增可选 `data_source_ids`（缺省=全量，向后兼容） |
| `backend/app/core/scheduler.py` | Scheduler 改造 | 新增 `collector_tick`（per_source 默认）；`start_scheduler` 按 `collector_schedule_mode` 注册 |
| `backend/app/core/config.py` | 配置新增 | `collector_schedule_mode` / `collector_default_interval_minutes` / `collector_tick_interval_seconds` |
| `backend/tests/test_datasource_schedule.py` | 测试新增 | 7 项（含 M2 回归） |
| `backend/tests/test_weibo_schedule.py` | 测试同步 | scheduler 测试支持 per_source 模式 + 新增 tick 合并调用测试 |

---

## 2. 数据库迁移 `p12_datasource_schedule`

- **down_revision**: `sec3b_perm_semantic`（经 `alembic script_directory` 权威确认的 DAG head，非文件名猜测）
- **新增列**（`data_sources`）：
  - `schedule_enabled` BOOLEAN，server_default `true`
  - `schedule_interval_minutes` INTEGER，server_default `30`
  - `next_collect_time` TIMESTAMP，nullable
  - `last_collect_time` TIMESTAMP，nullable
- **约束**：`CHECK (schedule_interval_minutes >= 5)`（命名 `ck_data_sources_schedule_interval_min`）
- **初始化**：已有行 `schedule_enabled=true`、`schedule_interval_minutes=30`；`next_collect_time` 按 `now() + make_interval(mins => id % 5)` **错峰**初始化（规避集体同刻触发）。
- **未改动** `collector_runs`（满足「不改变 CollectorRun 语义」）。
- **验证（测试库 5433/opinion_test）**：迁移 `upgrade head` 成功；4 列存在；全部源 `schedule_enabled=t`/`interval=30`；`next_collect_time` 按 `id%5` 正确分散；CHECK 约束就位。

---

## 3. API 变化

### 3.1 `PATCH /admin/data-sources/{id}`（增强）
- 新增支持字段 `schedule_enabled`、`schedule_interval_minutes`。
- 规则：**修改周期 或 由关闭改为启用**时，基于 PG `now()` 重算 `next_collect_time`（使用 `text("now() + make_interval(mins => :iv)")`，全部时区运算在 PG 侧完成，规避 R3 的 8 小时偏差）。
- `schedule_interval_minutes < 5` → 422。
- 权限：`require_admin`（与既有写操作一致）。

### 3.2 `POST /admin/data-sources/schedule/batch`（新增）
- 请求：`{ scope: "all" | "enabled_only", schedule_enabled?, schedule_interval_minutes? }`
- 行为：批量设置启用源（或全部源）的调度字段；`schedule_interval_minutes` 变更时按 `now() + make_interval(mins => iv + id%5)` 错峰重算 `next_collect_time`。
- 返回：`{ affected_count: int }`
- 权限：`require_admin`。至少需提供 `schedule_enabled` 或 `schedule_interval_minutes` 之一，否则 422。

### 3.3 `GET /admin/data-sources/schedule/summary`（新增）
- 返回当前频率状态：
  - 统一：`{ mode:"uniform", interval_minutes:30, enabled_auto_count:N }`
  - 混合：`{ mode:"mixed", distribution:{30:10,60:5}, enabled_auto_count:N }`
- 统计口径：仅「启用且开启自动采集」的源（`enabled=true AND schedule_enabled=true`），与 tick 选源口径一致。
- 权限：`get_current_user`（列表级，与既有只读接口一致）。

### 3.4 `POST /collector/run`（增强）
- 新增可选体参 `data_source_ids: int[]`。
- 透传链路：`run_collector` → `start_task(..., data_source_ids)` → `_run_collect_task(..., data_source_ids)` → 解析为 `key` 集合 → `CollectorService(include_data_source_keys=keys, exclude_data_source_keys=set())`。
- **不传参数 = 原全量采集语义**（向后兼容，未改变手动采集行为）。

---

## 4. Scheduler 变化

### 4.1 新增 `collector_tick`（默认 `per_source` 模式）
- **触发**：`IntervalTrigger(seconds=collector_tick_interval_seconds)`，默认 60s；`max_instances=1`、`coalesce=True`、`misfire_grace_time=30`。
- **流程（claim-then-dispatch，时间全部走 PG `now()`）**：
  1. `SELECT id, key FROM data_sources WHERE enabled=true AND schedule_enabled=true AND key!='weibo_octopus' AND (next_collect_time IS NULL OR next_collect_time <= now())`
  2. 一次性 `UPDATE ... SET last_collect_time=now(), next_collect_time=now()+make_interval(mins => schedule_interval_minutes) WHERE id = ANY(:ids)`（用各行自身间隔，事务内完成占位，防止本 tick 重复选中）
  3. **合并为一次** `CollectorService(include_data_source_keys=到期源key集合).collect_and_analyze_concurrent(...)`，**禁止逐源分别调用**。
- **为何合并**：政府源 5 秒防抖 `_GOV_LAST_RUN_AT` 是模块级单时间戳，且仅在**整批结束后**更新一次（service.py:837）。同一次合并调用内多个政府源互不触发 Throttle——这正是测试 #7 验证的设计保证。

### 4.2 `start_scheduler` 改造
- `collector_schedule_mode == "per_source"`（默认）：注册 `collector_tick`（Interval 60s）+ 保留 `weibo_consumer`（每小时 15 分 cron）+ `alert_eval`。
- 其它值（如 `cron`）：回滚为旧的全局固定 cron 全量采集（`_run_collector_job`），兼容历史行为。
- `weibo_consumer`、`alert_eval` **均保留**，未改动其独立链路。

---

## 5. 测试结果

运行命令（**注意**：本机 `localhost` 解析 IPv6 会导致 PG 连接挂起，须显式用 `127.0.0.1`）：
```bash
DATABASE_URL="postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5433/opinion_test" \
DB_IDENTITY_CHECK=off COLLECTOR_TYPE=mock \
pytest tests/test_datasource_schedule.py tests/test_weibo_schedule.py -q
```
**结果：`12 passed`（EXIT=0）**，覆盖要求的 7 项 + 原有 scheduler 测试：
1. ✅ 默认 30 分钟（迁移 server_default）
2. ✅ 单源 60 分钟（PATCH）
3. ✅ 关闭自动采集（tick 选源 SQL 排除）
4. ✅ 批量设置（`/schedule/batch`）
5. ✅ `next_collect_time` 计算（PG 侧比较，时区一致）
6. ✅ M2 并发路径源过滤（include/exclude 透传）
7. ✅ 两个政府源同 tick 不触发 Throttle（合并单次调用）
- 同步更新 `test_weibo_schedule.py`：per_source 模式 scheduler 注册断言 + 新增 `test_collector_tick_merges_due_sources_into_one_call`（验证 tick 仅实例化一次 `CollectorService`、include=到期源集合）。

---

## 6. 风险与待确认

### 6.1 已闭环的风险
- **R3 时区 8 小时偏差**：所有 `next_collect_time` 计算与比较均在 PG 侧（`now()` / `make_interval`），不混用 Python `datetime.now(timezone.utc)` 与 naive 落地，彻底规避。
- **R2 并发路径丢过滤（M2）**：`collect_and_analyze_concurrent` 已补传 `include/exclude`，并有回归测试守护。
- **R1 政府源防抖**：通过「合并单次调用」规避同 tick 互相拦截，测试 #7 守护。
- **实施期发现的真实生产缺陷**：原 `func.make_interval(mins=...)` 写法会因 SQLAlchemy 通用 `Function` 拒绝未知关键字参数而 500；已改为 `text("now() + make_interval(mins => :iv)")`（inline 整数，无注入风险），测试 2/4/5 已覆盖此路径。

### 6.2 待确认 / 未执行（需你拍板）
- **生产部署验证（部署到 5432/opinion）**：本阶段迁移仅施加于**测试库**（5433/opinion_test，`DB_IDENTITY_CHECK=off`）。生产库（5432，`db_identity_check` 须通过）的迁移施加与 uvicorn 重启**尚未执行**——按安全边界，生产库写操作需你显式确认后再做。生产 DAG head 已确认同为 `sec3b_perm_semantic`，迁移可干净衔接。
- **新建数据源的 `next_collect_time`**：`create_data_source` 未设置该字段（保持 NULL），tick 选源含 `next_collect_time IS NULL OR ...` 条件，故新建源会被视为「待采集」立即纳入，符合预期；若你希望新建源也错峰延后，可在前端阶段一并处理。
- **最小间隔下限 5 分钟**：DB CHECK + API 双保险已就位（API 拒绝 <5）。

### 6.3 兼容性声明
- `CollectorRun` 字段语义未变；现有 Collector 架构未变；手动采集（无 `data_source_ids`）行为完全不变；`weibo_consumer` 独立链路未变。

---

## 7. 下一步
- 等待确认：**(a)** 是否执行生产部署（迁移 + 重启 uvicorn + 冒烟验证）；**(b)** 是否进入 `Phase DataSource-Schedule-1-Frontend`（Sources.vue 前端改造）。
- 前端阶段将依赖本报告中的 API 契约（`PATCH` 字段、`/schedule/batch`、`/schedule/summary`、`/collector/run` 的 `data_source_ids`）。
