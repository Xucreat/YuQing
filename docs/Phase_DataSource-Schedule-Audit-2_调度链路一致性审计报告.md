# Phase DataSource-Schedule-Audit-2 数据源调度链路一致性审计报告

> 阶段性质：**只读审计**（未修改任何代码 / 数据库 / 配置 / migration）。
> 审计时间：2026-08-03
> 数据库身份门禁：`DATABASE IDENTITY: VERIFIED`（生产库 `opinion_db`）
> 可复跑脚本：`backend/_audit_schedule_audit2.py`（仅 SELECT + 内存模拟，不写库）

---

## 1. 审计范围

确认 scheduler 调度链路与 registry 数据源发现逻辑是否一致，重点排查：

- 是否存在「**数据源管理页显示启用 → registry 发现正常 → scheduler 实际不采集**」的口径分叉；
- scheduler 实际采集源的来源（复用 registry 还是自带查询）；
- `enabled` / `schedule_enabled` / `next_collect_time` 在各链路的口径差异；
- 调度字段 (`schedule_enabled` / `schedule_interval_minutes` / `next_collect_time` / `last_collect_time`) 的生命周期与读写位置；
- collector 失败 / DB 异常时的恢复行为与可观测性。

涉及文件（仅阅读）：

| 文件 | 角色 |
|---|---|
| `app/core/scheduler.py` | 调度器入口、tick 派发逻辑、claim 语句 |
| `app/collectors/registry.py` | `resolve_collectors` / `resolve_collectors_verbose`（装配器） |
| `app/collectors/service.py` | `CollectorService`（接入 registry、执行采集） |
| `app/api/admin_data_sources.py` | 调度字段写入口（schedule 配置端点） |
| `app/api/collector.py` | 手动采集入口 `/collector/run` |
| `app/models/data_source.py` | ORM 模型（4 个调度字段定义） |

---

## 2. scheduler 真实调用链

### 2.1 入口与装配

```
FastAPI 启动 (app/main.py:35 start_scheduler())
  │
  ├─ _try_acquire_scheduler_lock()           # PG 会话级咨询锁，跨进程单例
  │     └─ 仅抢到锁的进程启动调度器（其余进程 API/手动采集正常）
  │
  └─ AsyncIOScheduler.add_job(...)
        │
        ├─ [per_source 模式] IntervalTrigger(seconds=tick) → _run_collector_tick()
        └─ [cron 模式]       CronTrigger(collector_schedule_cron) → _run_collector_job()
```

### 2.2 实际采集路径（`per_source` 模式，当前生产生效）

```
_run_collector_tick()
  │
  ├─ (1) 自带 SQL：SELECT id,key FROM data_sources
  │          WHERE enabled=true
  │            AND schedule_enabled=true
  │            AND key != 'weibo_octopus'
  │            AND (next_collect_time IS NULL OR next_collect_time <= now())
  │       → 得到「到期待采集源」due_keys
  │
  ├─ (2) claim：UPDATE data_sources
  │          SET last_collect_time=now(),
  │              next_collect_time=now()+make_interval(mins=>schedule_interval_minutes)
  │          WHERE id = ANY(due_ids)        ← 先占位，避免重复选中
  │       → db.commit()
  │
  ├─ (3) CollectorService(include_data_source_keys=due_keys)
  │          → resolve_collectors_verbose(db, include=due_keys)
  │              → registry 读取 enabled 源，按 include 过滤 = due_keys 子集
  │              → 构建采集器；装配失败 → failures → CollectorRun(status=failed)
  │
  └─ (4) collect_and_analyze_concurrent(SessionLocal, trigger_type="scheduled")
         → 逐源 fetch() → 入库 → 自动聚合
```

### 2.3 关键判定

- **scheduler 是「采集闸门」**：实际采集源由 scheduler 自带 SQL（步骤 1）决定，registry 仅作为「装配器」按 `include=due_keys` 构建实例。
- **registry 参与，但不决定调度集合**：registry 负责把 DB 行变成可运行的 collector 对象，不判断「何时采集 / 是否自动调度」。

---

## 3. registry 与 scheduler 关系

| 维度 | registry (`resolve_collectors`) | scheduler tick (`_run_collector_tick`) |
|---|---|---|
| 查询方式 | ORM `select(6 个显式字段)` | 原生 `text()` SQL |
| 过滤条件 | `enabled = true` | `enabled AND schedule_enabled AND (next_collect_time 到期) AND key!='weibo_octopus'` |
| 读取字段 | id/key/name/class_path/scope_region_codes/config_json | id/key（+ 写 next_collect_time/last_collect_time） |
| 角色 | 装配（行 → collector 实例） | 调度闸门（选源 + 占位 + 触发） |
| 失败处理 | 装配失败 → `failures` → `CollectorRun(failed)` | 异常 → `logger.exception` 记录，不中断批 |

**结论**：两者是**分层协作**而非冲突——scheduler 先用更严格的口径选出「到期源」，再交 registry 装配。在 `per_source` 模式下，有效采集集 = `registry(enabled) ∩ scheduler候选` = `scheduler候选`（候选 ⊂ enabled），数学上一致。

⚠️ 但两者是**两条独立 SQL 路径**，存在口径分叉风险（见第 6 节）。

---

## 4. 数据源一致性验证（生产只读）

### 4.1 全局统计

| 指标 | 数量 |
|---|---|
| `data_sources` 总行数 | 38 |
| `enabled = true` | **17** |
| `enabled AND schedule_enabled = true`（scheduler 候选基准） | **17** |
| 其中 `next_collect_time` 当前已到期 | 0（迁移/admin 已将时间推至未来，到点即派发） |
| `enabled` 但 `schedule_enabled = false` | **0** |
| `registry.resolve_collectors(db)` 返回 | **17** |
| scheduler 实际候选（去 weibo 后） | **17** |
| 实际生效集（候选 ∩ registry） | **17** |

**验证结果**：
- `registry 数 (17) == enabled 数 (17)` ✅
- `scheduler 候选 (17) ⊆ registry 发现 (17)`，无悬空候选 ✅
- 全部 17 个 enabled 源均可成功装配（无 config_json / 类导入错误）✅

### 4.2 重点源逐源表

| source | enabled | schedule_enabled | 在 registry | 在 scheduler 候选 | 结论 |
|---|---|---|---|---|---|
| government | ✅ | ✅ | ✅ | ✅ | OK（自动调度参与） |
| xinhua | ✅ | ✅ | ✅ | ✅ | OK |
| people | ✅ | ✅ | ✅ | ✅ | OK |
| chinanews | ✅ | ✅ | ✅ | ✅ | OK |
| baidu_news | ✅ | ✅ | ✅ | ✅ | OK |
| bazhou_gov_xzdt | ✅ | ✅ | ✅ | ✅ | OK |
| bazhou_gov | ✅ | ✅ | ✅ | ✅ | OK |

**验收标准达成**：
- ✅ scheduler 入口明确（`_run_collector_tick`）；
- ✅ 实际采集源来源明确（scheduler 自带 SQL → include → registry 装配）；
- ✅ registry 是否参与明确（参与装配，不参与调度决策）；
- ✅ DB 启用源 (17) 与 scheduler 候选 (17) 一致，7 个重点源全部对齐；
- ✅ 给出后续修改结论（见第 7 节）。

> **当前生产环境结论：未触发「页启用 / registry 正常 / scheduler 不采集」的不一致。** 但第 6 节指出该现象在结构上**可被 `schedule_enabled=false` 触发**，需小修复加固。

---

## 5. 调度字段生命周期

| 字段 | 读取位置 | 写入位置 | 用途 |
|---|---|---|---|
| `schedule_enabled` | scheduler tick WHERE 子句（`scheduler.py:66`） | admin 调度端点（`admin_data_sources.py:628`）；迁移 `p12` 默认值 | 自动调度总开关（仅 `per_source` 模式生效） |
| `schedule_interval_minutes` | scheduler claim UPDATE（`make_interval(mins => ...)`，`scheduler.py:81`） | admin 调度端点（`:629`）；迁移 `p12` 默认值 | 计算下一次采集间隔 |
| `next_collect_time` | scheduler tick WHERE（`scheduler.py:68`）+ claim 计算（`:81`） | claim UPDATE（`:81`）；admin 错峰重算（`:622`） | 到期判定 + 下次时间 |
| `last_collect_time` | **仅展示**（admin 输出 `:283`）；不参与任何调度决策 | claim UPDATE（`scheduler.py:80`） | 记录上次实际采集时刻（展示用，非决策字段） |

补充：
- 手动采集 `/collector/run`（`api/collector.py:103`）：`CollectorService(include=选定 ids)` 或直接 `CollectorService()`，**不查 `schedule_enabled`**——手动即显式，绕过自动调度开关。
- `weibo_octopus` 由独立 consumer job（`_run_weibo_consumer_job`）处理，被排除在主 tick 之外。

---

## 6. 风险列表

### R1（中）— 双查询路径口径分叉：`schedule_enabled=false` 可造成「页启用但 scheduler 不采集」
- **位置**：`scheduler.py:62-70`（自带 SQL 含 `schedule_enabled=true`）vs `registry.py:236`（仅 `enabled=true`）。
- **机制**：`schedule_enabled=false` 的源，UI 显示「启用」、registry 能发现（装配），但 scheduler tick 永远不派发 → 表现为「管理页启用却不被自动采集」。
- **当前状态**：生产 17 个 enabled 源 `schedule_enabled` 全为 true，**未触发**。
- **影响范围**：仅 `per_source` 模式；若某天把某源 `schedule_enabled` 置 false（如临时暂停），即出现页/调度不一致。属**设计允许的暂停语义**，但 UI 文案「启用」易误导运维认为在采集。

### R2（中）— 双查询路径分叉：`cron` 模式完全忽略 `schedule_enabled`
- **位置**：`scheduler.py:235` `_run_collector_job` → `CollectorService(exclude={weibo_octopus})`，**无 `schedule_enabled` 过滤**，收集全部 enabled。
- **机制**：模式切换后，`schedule_enabled` 对采集集**完全失效**——与 `per_source` 模式行为矛盾。
- **当前状态**：生产 `collector_schedule_mode=per_source`，cron 路径未激活，但代码存在且语义与 per_source 不一致。
- **影响范围**：若将来切到 cron 模式，所有 enabled 源（含 `schedule_enabled=false`）都被全量采集，R1 的「暂停」语义失效。

### R3（低）— claim-before-dispatch：采集失败也推进 `next_collect_time`
- **位置**：`scheduler.py:76-87`（claim UPDATE 先 commit）→ `:93` 才执行 `collect_and_analyze_concurrent`。
- **机制**：若本次派发整体抛异常、或某源装配失败，其 `next_collect_time` 已被推至下一周期 → 本周期采集丢失，顺延到下次。
- **是否静默**：**否**。`collect_and_analyze_concurrent` 内部装配失败写 `CollectorRun(status=failed)`；scheduler 顶层 `except` 走 `logger.exception`（非 swallow）。属「延迟一周期重试」，非永久跳过。

### R4（低）— 降级回退时候选悬空（残留风险）
- **位置**：registry DB 读取失败 → `DEFAULT_SOURCES`（9 个硬编码 key）；但 scheduler 已用真实 DB claim 了真实 due 源并推进 `next_collect_time`。
- **机制**：`include=due_keys`（真实 key）过滤 `DEFAULT_SOURCES`（固定 9 key）→ 真实源不匹配 → 不装配、不采集，且 `next_collect_time` 已推进；若 DB 持续不可用，每周期重复 → **降级期间等效永久跳过**。
- **当前状态**：生产 registry DB 读取正常（`degraded=False`，`/health` 显式暴露），**未触发**。`/health` 已可观测（Fix-1 已落地）。
- **影响范围**：仅 DB 故障降级窗口；概率低，但属 Fix-1 未彻底消除的尾部风险。

### R5（信息）— `last_collect_time` 不参与决策
- 仅写入 + 展示，无调度逻辑依赖。无风险，仅作生命周期记录。

---

## 7. 后续建议

### A. 无需修改（当前）
- 当前生产（per_source 模式，17 enabled 源全部 `schedule_enabled=true`）链路完全一致，bazhou_gov_xzdt / bazhou_gov 等均正常进入 scheduler。
- Phase Config-1 的配置化（`source_config` / `max_items` / `filter_mode` / `keyword_scope`）经 registry 装配注入，未因 Schedule 改造失效（Audit-2 验证 registry 17 源全部装配成功，配置正常读取）。

### B. 小修复建议（推荐，低风险）
1. **统一查询入口（repository）**：将 scheduler 的「到期源查询」与 registry 的「enabled 源查询」收敛到同一数据访问函数（如 `DataSourceRepository.due_sources()` / `.enabled_sources()`），避免两条独立 SQL 漂移。优先级：中（防 R1/R4 未来复现）。
2. **`cron` 模式也尊重 `schedule_enabled`**：让 `_run_collector_job` 与 tick 共用同一候选集，消除 R2 的模式语义矛盾。若确需「全量」，显式用独立开关而非隐式忽略。
3. **UI 文案/状态分离**：将 `enabled`（注册/可见）与 `schedule_enabled`（自动调度）在管理页分别展示（如「已注册 / 自动调度开」），避免运维把「启用」误读为「正在采集」，消除 R1 的误导性。不新增字段，仅前端展示优化。
4. **claim 与 dispatch 同事务（可选）**：将 `next_collect_time` 推进放到采集成功后或事务内，降低 R3 的「失败即丢一周期」窗口。注意需权衡「防重复派发」语义，建议作为独立小 Phase 评估。

### C. 架构调整（当前不必要）
- 不需要把 scheduler 改成直接调用 `resolve_collectors` 作为唯一真相源。当前「scheduler 选源 + registry 装配」分层清晰、职责单一，仅在**查询入口**层面收敛即可（见 B.1）。
- 不需要引入消息队列 / Redis / Celery（与既有约束一致）。

---

## 附：验收对照

| 验收项 | 结果 |
|---|---|
| 明确 scheduler 入口 | ✅ `_run_collector_tick`（per_source）/ `_run_collector_job`（cron） |
| 明确实际采集源来源 | ✅ scheduler 自带 SQL 选源 → include → registry 装配 |
| 明确 registry 是否参与 | ✅ 参与装配，不参与调度决策 |
| DB 启用源 与 scheduler 候选一致 | ✅ 17 = 17（含 7 重点源全对齐） |
| 是否需后续修改 | ✅ 当前无阻断性不一致；建议 B 类小修复（非必须） |

> 本审计**未做任何修改**。如需实施 B 类小修复，建议另立 Phase（如 `Phase DataSource-Schedule-Fix-2`），并复用本报告的 R1–R4 作为范围定义。
