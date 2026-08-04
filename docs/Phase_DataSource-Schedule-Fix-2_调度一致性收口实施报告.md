# Phase DataSource-Schedule-Fix-2 调度一致性收口实施报告

> 关联阶段：基于 Phase DataSource-Schedule-Audit-2（只读审计）的 B 类小修复建议。
> 严格约束已遵守：未修改采集器业务逻辑 / Opinion·Event·Risk 链路 / 前端 / 数据库结构 / migration；不引入 Redis·ES·MQ·Celery；不改变当前生产采集行为；旧配置兼容。

## 1. 修改原因

Audit-2 只读审计（见 `docs/Phase_DataSource-Schedule-Audit-2_调度链路一致性审计报告.md`）发现 scheduler 与 registry 在 `data_sources` 查询上**口径分叉**，存在两类结构风险（当时未触发，但属隐患）：

- **R1（查询漂移）**：`enabled=true` 过滤条件在 `scheduler._run_collector_tick` 与 `registry._resolve_core` 各维护一份；`schedule_enabled`、`key != 'weibo_octopus'` 等条件分散在 SQL / include-exclude 两处。未来任一侧变更易产生「页面启用但 scheduler 不采集 / 反之」的不一致。
- **R2（语义分叉）**：`per_source` 模式的 tick 会过滤 `schedule_enabled=true`，而 `cron` 模式（`_run_collector_job`）直接全量 enabled、**忽略 `schedule_enabled`**，两种调度模式语义矛盾。
- **R3（降级悬空）**：若 registry 发现降级（DB 异常 → `DEFAULT_SOURCES` 9 硬编码源），其 key 与真实 DB key 不匹配，scheduler 已 claim 推进 `next_collect_time` 却因 include 不匹配而漏采——属「静默漏采」，与 Fix-1「禁止静默」原则相悖。

本阶段目标：用最小改动收口上述分叉（B 类小修复），**不重构调度架构**。

## 2. 修改文件

| 文件 | 改动类型 | 说明 |
|---|---|---|
| `backend/app/collectors/data_source_repository.py` | **新增** | 轻量只读查询封装：`enabled_sources()` / `due_scheduled_sources()` / `scheduled_enabled_sources()`，统一查询条件、禁止 SELECT *、仅选所需字段。 |
| `backend/app/collectors/registry.py` | 修改 | `_resolve_core` 内联 `enabled` 查询 → 调用 `repository.enabled_sources(db)`；移除已无用的 `from sqlalchemy import select` 导入；降级 / `last_discovery_degraded` 标记逻辑不变。 |
| `backend/app/core/scheduler.py` | 修改 | `_run_collector_tick` 改用 `due_scheduled_sources(db)`；`_run_collector_job`（cron）改用 `scheduled_enabled_sources(db)` 并 `include` 以遵守 `schedule_enabled`；两入口 dispatch 前加 `_scheduler_discovery_ok()` 实时探测，失败则 ERROR + skip。 |
| `backend/app/main.py` | 无 | `/health` 已在 Fix-1 暴露 `collector_discovery`，满足 Fix-3「可观测」，直接复用。 |

**未改动**：collectors/* 采集逻辑、models、前端、数据库结构、migration、Opinion/Event/Risk 链路、Redis/ES/MQ/Celery。

## 3. 修改前后链路

### 修改前
```
scheduler._run_collector_tick():
    内联 SQL: enabled=true AND schedule_enabled=true AND key!='weibo_octopus'
              AND next_collect_time<=now()            ← 查询分散在 scheduler
    → CollectorService(include=due_keys)
        → registry._resolve_core():
              内联 SQL: enabled=true (6 列)          ← 查询分散在 registry
              ❌ 无 schedule_enabled 过滤

scheduler._run_collector_job()  [cron]:
    CollectorService(exclude={'weibo_octopus'})      ← 全量 enabled，忽略 schedule_enabled
```

### 修改后
```
scheduler._run_collector_tick():
    if not _scheduler_discovery_ok(): return          ← Fix-3 实时探测门禁
    due = due_scheduled_sources(db)                  ← 统一仓储（含 schedule_enabled + 到期 + 排除 weibo）
    → CollectorService(include=due_keys)
        → registry._resolve_core():
              rows = enabled_sources(db)             ← 统一仓储（仅 enabled，装配字段）

scheduler._run_collector_job()  [cron]:
    if not _scheduler_discovery_ok(): return          ← Fix-3 实时探测门禁
    keys = scheduled_enabled_sources(db)             ← 统一仓储（enabled + schedule_enabled，排除 weibo）
    → CollectorService(include=keys, exclude={'weibo_octopus'})  ← Fix-2 遵守 schedule_enabled
```

**全部查询条件收口到 `data_source_repository` 三个函数**，scheduler 与 registry 不再各自维护 SQL。

## 4. 是否改变生产行为

| 维度 | 结论 | 依据 |
|---|---|---|
| 当前 17 生产源采集行为 | **不改变** | 生产 `collector_schedule_mode=per_source`；17 个 enabled 源**全部 `schedule_enabled=true`**（实测 0 个 false），故 cron 收口（Fix-2）在 per_source 生产模式下无实际差异；仅对未来「关闭某源自动调度」场景生效。 |
| per_source tick 实际采集集合 | **不变** | `due_scheduled_sources` 的 WHERE 与旧 `_run_collector_tick` 内联 SQL **逐字等价**（验证 B 已证明 0 差异）。 |
| 降级行为 | **从「静默漏采」改为「可观测拦截」** | Fix-3 使 DB 不可达时不再 claim+漏采，而是 ERROR + 跳过，且 `/health` 已暴露 `collector_discovery=degraded`。此为**安全增强**，不改变正常路径行为。 |
| 旧配置兼容 | **兼容** | 无新增字段、无 migration；`config_json` 策略键（Config-1）读取链路未触碰（验证 E 通过）。 |

**结论：当前生产 17 个数据源的采集行为完全一致；新增仅为防御性一致性与可观测性增强。**

## 5. 验证结果

验证脚本：`backend/_verify_schedule_fix2.py`（只读 + 沙盒，未修改任何生产数据）。

| 项 | 结果 | 说明 |
|---|---|---|
| **A. Repository 一致性** | ✅ | `enabled_sources()` 17 == `resolve_collectors()` 17，0 装配失败，key 集合一致。 |
| **B. scheduler 候选一致性** | ✅ | `due_scheduled_sources()` 与旧 scheduler SQL 结果逐字一致（0 差异）；构造到期源（事务回滚）后非空场景仍一致且回滚还原。 |
| **C. cron/per_source 一致性** | ✅ | 事务内将 `bazhou_gov_xzdt` 置 `schedule_enabled=false`：per_source 与 cron **均正确排除**，回滚后原值还原（True）。 |
| **D. degraded 防护** | ✅ | monkeypatch 模拟 DB 发现失败：tick 与 cron **均被拦截**（输出 ERROR 日志、未构造 CollectorService、未推进周期）。 |
| **E. Config-1 回归** | ✅ | 6 重点源（xinhua/people/chinanews/baidu_news/government/bazhou_gov_xzdt）`source_config` 均注入；`max_items`/`filter_mode`/`keyword_scope` 可读取且配置可覆盖。 |

验证输出节选：
```
[A] repo=17 == registry=17，无分叉
[B] due 候选与旧 SQL 完全一致（0 个）；到期场景一致，回滚后 government 已还原
[C] bazhou_gov_xzdt 在 cron 与 per_source 下均被正确排除，回滚已还原原值=True
[D] 发现降级时 tick/cron 均被拦截（ERROR 日志 + 跳过，无假 run / 不推进周期）
[E] 6 个重点源 source_config 均注入；max_items/filter_mode/keyword_scope 读取正常且可被配置覆盖
全部验证通过：6 项
```

## 6. 未解决事项 / 后续建议

| 项 | 状态 | 说明 |
|---|---|---|
| R4（DB 降级窗口候选悬空） | 部分缓解 | 本次 Fix-3 在 dispatch 前拦截，避免「claim 后漏采」；但当 DB 持续故障时，真实源本周期不执行（等效跳过）。仍建议后续让 registry 在降级时**不 claim**，使源在恢复后立即补采。当前已实现可观测（`/health`），运维可及时发现。 |
| cron 模式是否推进 `next_collect_time` | 保持旧行为 | cron 由全局表达式驱动，不管理 `next_collect_time`，与 per_source 职责划分一致，本次未改。 |
| 统一 repository 是否纳入写方法 | 本次未做 | 仓库按 Phase 要求保持只读；claim UPDATE 仍留 scheduler（单事务原子性）。如需进一步收口可后续评估，但非必须。 |
| 真实 scheduler 运行验证 | 待部署 | 代码改动需**重启后端 uvicorn** 后生效。受 memory 中「勿擅自 kill 运行中的 uvicorn（父子进程级联风险）」约束，本次未自行重启；验证通过单测/沙盒覆盖，未做生产运行时采集。

### 部署须知
- 重启 backend 后生效（仅增强一致性 / 可观测性，**不改变**正常路径 17 源采集行为）。
- 重启请遵循既有安全流程（先锁定 LISTENING PID、确认非父子关系再处理），避免误杀提供 API 的父进程。

---

## 验收标准对照

| 验收项 | 结果 |
|---|---|
| ✅ scheduler 与 registry 不再维护重复查询逻辑 | repository 三函数统一承载 |
| ✅ cron/per_source schedule_enabled 语义一致 | Fix-2 已对齐 |
| ✅ degraded 状态不会继续派发悬空任务 | Fix-3 实时探测 + 拦截 |
| ✅ Phase DataSource-Config-1 不回归 | 验证 E 通过 |
| ✅ 当前 17 个生产数据源行为保持一致 | 实测 17=17，模式 per_source，无行为变更 |
| ✅ 不新增基础设施 | 仅 1 新增文件（轻量封装），无 Redis/ES/MQ/Celery |
