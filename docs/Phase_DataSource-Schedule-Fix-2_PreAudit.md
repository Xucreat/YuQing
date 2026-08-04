# Phase DataSource-Schedule-Fix-2 预审计（Pre-Audit，只读）

> 本文件为 Step 1 强制产出物。全部内容为**只读审计**（源码阅读 + SELECT 查询 + 内存模拟），未对代码 / 数据库 / 配置 / migration 做任何修改。修改仅在审计通过后进行。

## 1. 当前 scheduler 调用位置

入口：`backend/app/core/scheduler.py`

| 函数 | 触发方式 | 数据源筛选逻辑（当前） |
|---|---|---|
| `start_scheduler()` | uvicorn 启动 / PG 咨询锁单例抢到后 | 按 `settings.collector_schedule_mode` 注册 job |
| `_run_collector_tick()` | `per_source` 模式，IntervalTrigger(60s) | **内联 SQL**：`enabled=true AND schedule_enabled=true AND key!='weibo_octopus' AND (next_collect_time IS NULL OR <= now())` → 选源 → claim UPDATE 推进 `next_collect_time` → `CollectorService(include=due_keys)` |
| `_run_collector_job()` | `cron` 模式（非 per_source），全局 CronTrigger | **无 schedule_enabled 过滤**：`CollectorService(exclude_data_source_keys={'weibo_octopus'})` → 全量 enabled |
| `_run_weibo_consumer_job()` | 独立 hourly cron | 仅 `weibo_octopus`，与本次无关 |
| `_run_alert_eval_job()` | IntervalTrigger | 预警评估，与数据源发现无关 |

当前生产 `collector_schedule_mode = per_source`（config.py:67），故生产实际走 `_run_collector_tick`；`_run_collector_job`（cron）仅在不启用 per_source 时生效，但仍属本阶段需收口的分叉路径。

## 2. 当前 registry 查询位置

位置：`backend/app/collectors/registry.py` → `_resolve_core()`

```python
rows = [
    dict(r) for r in db.execute(
        select(DataSource.id, DataSource.key, DataSource.name,
               DataSource.class_path, DataSource.scope_region_codes,
               DataSource.config_json)
        .where(DataSource.enabled == True)
        .order_by(DataSource.priority.asc(), DataSource.id.asc())
    ).mappings().all()
]
```

- 仅按 `enabled=true` 过滤（**不含 `schedule_enabled` / `next_collect_time`**）。
- 异常时 `last_discovery_degraded=True` + `logger.error`，回退 `DEFAULT_SOURCES`（9 硬编码源）。
- 返回 6 列（已在 Fix-1 阶段从 SELECT * 改为显式列）。

## 3. 重复 SQL 条件（分叉点）

| 查询条件 | scheduler（_run_collector_tick） | registry（_resolve_core） |
|---|---|---|
| `enabled=true` | ✅ | ✅ |
| `schedule_enabled=true` | ✅（tick）/ ❌（cron job） | ❌ |
| `key != 'weibo_octopus'` | ✅ | ❌（靠 include/exclude 兜） |
| `next_collect_time` 到期 | ✅ | ❌ |
| 字段集 | id,key (+ schedule_enabled,interval,nct) | id,key,name,class_path,scope,config_json |

**重复 / 分叉结论：**
- `enabled=true` 在两个文件各写一份（未来漂移风险，Audit-2 R1）。
- `schedule_enabled` 语义在 cron 模式被忽略（Audit-2 R2）——本阶段 Fix-2 收口。
- `key != 'weibo_octopus'` 在 scheduler 用 SQL、在 registry 用 include/exclude，逻辑分散。

## 4. 修改文件计划

| 文件 | 改动 | 类型 |
|---|---|---|
| `backend/app/collectors/data_source_repository.py` | **新增**，封装 `enabled_sources()` / `due_scheduled_sources()` / `scheduled_enabled_sources()`，统一查询条件 | 新增只读封装 |
| `backend/app/collectors/registry.py` | `_resolve_core` 内联 enabled 查询 → 改为调用 `enabled_sources(db)`；降级 / `last_discovery_degraded` 逻辑不变 | 最小替换 |
| `backend/app/core/scheduler.py` | `_run_collector_tick` 改用 `due_scheduled_sources(db)`；`_run_collector_job` 改用 `scheduled_enabled_sources(db)` 并 `include` 以遵守 `schedule_enabled`；两入口 dispatch 前加 `_scheduler_discovery_ok()` 实时探测 | 最小替换 + 降级防护 |
| `backend/app/main.py` | 不修改（`/health` 已暴露 `collector_discovery`，满足可观测，Fix-3 复用之） | 无 |

**明确不修改：** collectors/* 采集逻辑、models/opinion.py、models/event.py、前端、数据库结构、migration、Opinion/Event/Risk 链路、Redis/ES/MQ/Celery。

## 5. 风险评估

| 风险 | 等级 | 说明 / 缓解 |
|---|---|---|
| 行为变更（当前生产 17 源） | 低 | 生产 17 个 enabled 源 **全部 schedule_enabled=true**（实测 0 个 false），故 Fix-2 的 cron 收口在 per_source 生产模式下**不改变任何实际采集行为**；仅对未来「关闭某源自动调度」场景生效。 |
| 降级防护死锁 | 中→已规避 | 若仅检查 `last_discovery_degraded` 旧值做门禁，DB 恢复后该值仍为 True 会导致永久跳过。本方案改用 `_scheduler_discovery_ok()` **每次实时探测**（复用 repository 真实查询），DB 恢复即自动解除，无死锁。 |
| 查询漂移 | 低 | repository 集中 SQL，两处调用同一实现，消除重复维护。 |
| 验证不写库 | 低 | 验证脚本仅 SELECT + 内存模拟；唯一需验证「schedule_enabled=false 排除」用**事务回滚**（UPDATE 后 ROLLBACK，DB 字节不变），并校验回滚后值还原。 |

## 6. 审计通过判定

- [x] scheduler 调用位置已定位（per_source tick + cron job 双路径）
- [x] registry 查询位置已定位（_resolve_core 内联 enabled 查询）
- [x] 重复 / 分叉 SQL 条件已列出
- [x] 修改文件计划已明确且均落在允许范围（新增 1 + 改 2，不动采集逻辑 / 模型 / 前端 / 库）
- [x] 风险已评估，关键死锁风险已有规避方案

**审计通过，可进入 Step 2 最小修改。**
