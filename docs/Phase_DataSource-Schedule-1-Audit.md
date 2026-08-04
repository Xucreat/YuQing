# Phase DataSource-Schedule-1 只读审计报告

> 审计范围：数据源级采集调度配置能力建设（自定义采集频率）
> 审计时间：2026-08-03
> 审计性质：**只读审计，未修改任何代码 / 数据库 / 配置**
> 生产库确认：`opinion_db@127.0.0.1:5432`（PG16，read-only 查询）

---

## 0. 结论摘要（TL;DR）

| 项目 | 结论 |
|---|---|
| DataSource 模型是否存在 | ✅ 存在（`data_sources` 表，14 列），**无任何调度相关字段** |
| 数据源管理 API | ✅ 存在（`/api/admin/data-sources`，list / create / PATCH / runs / quality / logs） |
| scheduler 实现位置 | ✅ `backend/app/core/scheduler.py`（APScheduler `AsyncIOScheduler`，进程内，无 Celery/Redis） |
| 30 分钟 cron 配置位置 | ✅ `config.py:59` `collector_schedule_cron="*/30 * * * *"` + 根目录 `.env:COLLECTOR_SCHEDULE_CRON` |
| collector_main 调度入口 | ✅ `scheduler.py:31 _run_collector_job()` → `CollectorService.collect_and_analyze()`（job id 字面量就叫 `collector_main`） |
| CollectorRun 记录逻辑 | ✅ `service.py:_process_collector()` 每源一条，同批次共享 `batch_id` |
| 是否可扩展现有表实现 | ✅ **可以**，加 4 列即可，无需新建调度系统、无需引入 Redis/Celery/MQ |
| 主要拦路风险 | ⚠️ 4 个（并发路径过滤缺陷 / 政府源 5 秒防抖 / 时区语义 / 采集日志批次膨胀），均有明确缓解方案 |

**总体判断：改造可行，属于「扩展现有表 + 替换一个 job 触发器」级别的改动，不触碰 Collector 架构本体。**

---

## 1. 当前调度链路

### 1.1 链路全貌（实测）

```
FastAPI lifespan (main.py:35)
  │
  └─ start_scheduler()                                    scheduler.py:138
       │
       ├─ 门禁1：settings.collector_schedule_enabled       config.py:58  (=True)
       ├─ 门禁2：pg_try_advisory_lock(单例锁)              scheduler.py:91-113
       │         └─ 多实例(8000/8011)只有一个进程真正跑调度
       │
       └─ AsyncIOScheduler
            ├─ job "collector_main"   CronTrigger("*/30 * * * *")   ← 固定 30 分钟
            │    └─ _run_collector_job()                      scheduler.py:31
            │         └─ CollectorService(exclude={"weibo_octopus"})
            │              └─ collect_and_analyze(db, trigger_type="scheduled")
            │                   ├─ resolve_collectors_verbose(db)   ← 读 data_sources(enabled=true)
            │                   └─ for c in collectors:  ← **顺序串行**
            │                        _process_collector()  → 每源写一条 CollectorRun
            │              └─ auto_aggregate_after_collect()
            │
            ├─ job "weibo_consumer"   CronTrigger("15 * * * *")     ← 独立每小时
            │    └─ _run_weibo_consumer_job()                 scheduler.py:48
            │         └─ CollectorService(include={"weibo_octopus"}) + ack 回执语义
            │
            └─ job "alert_eval"       IntervalTrigger(30min)
                 └─ _run_alert_eval_job()                     scheduler.py:79

手动链路（并行存在，不走 scheduler）：
POST /api/collector/run  (require_admin)                     api/collector.py:131
  └─ start_task("collector", _run_collect_task)  ← 后台线程任务，立即返回 task_id
       └─ CollectorService().collect_and_analyze_concurrent(...)  ← **并发 6 线程**
            └─ 同样每源一条 CollectorRun（trigger_type="manual"）
```

### 1.2 现状 = 全局单一节奏（问题所在）

```
scheduler
   │
   └── 每 30 分钟（对所有源一视同仁）
         │
         └── collect_and_analyze()
               ├── 大厂县政府网站      ← 政府公告日更，30 分钟是浪费
               ├── 百度新闻            ← 时效性高，30 分钟合理
               ├── 新华网 / 人民网 / 中国新闻网
               ├── 廊坊/三河/香河/固安/霸州/永清/大城/文安 政府网 …
               └── （共 17 个启用源，串行执行）
```

### 1.3 生产实测运行特征（`collector_runs` 只读统计）

| 指标 | 实测值 |
|---|---|
| 定时批次总数 | 440 批 / 6971 条 run（2026-07-25 ~ 2026-08-03） |
| 每批数据源数 | 17（= 当前 enabled 源数） |
| 定时批次耗时 | **147 ~ 185 秒**（串行） |
| 手动批次耗时 | **28 秒**（并发 6 线程，同样 17 源） |
| 定时触发点 | 严格 `:00` / `:30`（本地时间，APScheduler 用系统时区） |
| weibo_scheduled | 仅 3 条（该源当前 `enabled=false`） |

> 关键数据点：**串行 150s vs 并发 28s**，说明未来 tick 派发应优先复用并发路径。

---

## 2. 涉及文件清单

### 2.1 后端（必改）

| 文件 | 关键位置 | 当前职责 | 本期需要的动作 |
|---|---|---|---|
| `backend/app/models/data_source.py` | 全文 19-56 | DataSource ORM，14 列 | **加 4 列** |
| `backend/app/core/scheduler.py` | 31-45、138-159 | job 注册 + 采集 job 体 | **加 tick job，替换固定 cron** |
| `backend/app/core/config.py` | 56-64 | `collector_schedule_cron` 等 | 加调度模式开关 + 默认间隔 |
| `backend/app/api/admin_data_sources.py` | 361-434（list）/ 599-686（PATCH） | 数据源 CRUD | **序列化加字段 + PATCH 加字段 + 新增批量接口** |
| `backend/app/api/collector.py` | 126-157 | `POST /collector/run` | **加可选「指定数据源」入参（向后兼容）** |
| `backend/app/collectors/service.py` | 724-834（并发路径） | 采集主流程 | **修复并发路径忽略 include/exclude 的缺陷** |
| `backend/alembic/versions/` | head=`sec3b_perm_semantic` | 迁移链 | **新增 1 个迁移（down_revision=`sec3b_perm_semantic`）** |

### 2.2 后端（只读依赖，不改）

| 文件 | 说明 |
|---|---|
| `backend/app/collectors/registry.py` | `_resolve_core()` 已支持 `include/exclude_data_source_keys`，**tick 可直接复用，零改动** |
| `backend/app/models/collector_run.py` | CollectorRun 结构**不改**（合规要求） |
| `backend/app/core/permissions.py` | `require_admin` / `require_permission("sources:read")` 现成可用 |
| `backend/app/main.py` | lifespan 已调 `start_scheduler()`，无需改 |
| `backend/app/services/data_source_health.py` | 健康摘要，读 CollectorRun，不受影响 |

### 2.3 前端

| 文件 | 行数 | 说明 |
|---|---|---|
| `frontend/src/views/Sources.vue` | 891 行 | **数据源管理主页面**：表格 11 列 + 配置弹窗 + 新建弹窗 + 历史弹窗。需加「自动采集/周期/下次/最近」4 列、编辑弹窗调度区、顶部全局设置区 |
| `frontend/src/views/DataManage.vue` | 135 行 | Tab 容器（关键词/数据源/采集日志/AI线索），`?tab=sources` 直达。**无需改** |
| `frontend/src/types/index.ts` | — | `DataSourceItem` 接口，需加 4 个字段 + 新增全局设置请求/响应类型 |
| `frontend/src/views/CollectionLog.vue` | 88 行 | 采集日志，读 `/collection-logs`。**无需改**，但批次数量会变多（见风险 R4） |

> ⚠️ 前端 `.vue` 文件受本机 node 虚拟化影响：原生 Read/grep 读出为压缩字节，**必须用 node 读写**（见工程约定）。

### 2.4 测试

| 文件 | 说明 |
|---|---|
| `backend/tests/test_weibo_schedule.py` | 现有 scheduler 注册测试（断言 2 个 job + cron 表达式），**本期改造会使其失败，需同步更新** |
| `backend/tests/conftest.py` | 测试库 `opinion_test`，`DB_IDENTITY_CHECK=off`，`COLLECTOR_TYPE=mock` |
| 新增 | `tests/test_datasource_schedule.py`（本期 5 项后端验证） |

---

## 3. 数据模型情况

### 3.1 `data_sources` 现有结构（生产实测 14 列）

| 列 | 类型 | 说明 |
|---|---|---|
| id | integer | PK |
| key | varchar(64) | 唯一标识，registry 过滤键 |
| name | varchar(128) | 显示名，**同时是 `collector_runs.collector_name` 的关联键** |
| type | varchar(32) | gov_site / news_site / search / rss / api / generic_site |
| class_path | varchar(256) | 采集器类路径 |
| enabled | boolean | 启停（**决定是否被 registry 装配**） |
| priority | integer | 排序 |
| scope_region_codes | varchar(256) | 区域 CSV |
| config_json | text | 站点配置 |
| last_run_at / last_status / last_error | — | **运行态缓存列，当前采集流程从不写入（恒为空）** |
| created_at / updated_at | timestamp | — |

**结论：无 `schedule_enabled` / `schedule_interval_minutes` / `next_collect_time` / `last_collect_time` 任一字段，必须新增。**

### 3.2 生产数据实况

- 总数据源 **38 个**，其中 **enabled=true 17 个**
- 启用源清单：大厂县政府网站、百度新闻、新华网、人民网、中国新闻网、廊坊市政府网-本市动态、霸州市政府网-乡镇动态、廊坊市政府网、廊坊新闻网、三河/香河(×2)/固安/霸州/永清/大城/文安 政府网
- 停用源 21 个（河北省内其它地市、weibo_octopus、grok_search 等）

### 3.3 `collector_runs`（不改，仅确认语义）

- 每「源 × 每次运行」一条；同一次触发的所有源共享 `batch_id`
- `trigger_type` ∈ `manual` / `scheduled` / `weibo_scheduled` / （历史脏值 `verify` / `manual_verify` / `https_fix_verify`）
- 采集日志页按 `COALESCE(batch_id, start_time::text)` 聚合成"一次采集"
- **本期不新增/不改语义**，只会改变「一个 batch 里包含几个源」的分布

### 3.4 时区语义（重要发现）

```
DB session TimeZone = Asia/Shanghai
data_sources / collector_runs 的时间列均为 timestamp WITHOUT time zone
代码写入的是 datetime.now(timezone.utc)（aware）
→ 驱动/PG 转换后，库里实际落的是「北京本地墙钟」
   实证：定时批次 start_time = 2026-08-03 10:30:00，恰为本地 10:30，而非 UTC 02:30
```

**约束：新增的 `next_collect_time` / `last_collect_time` 必须沿用同一约定——Python 侧一律用 `datetime.now(timezone.utc)` 生成 aware 值，交由驱动统一转换；禁止混用 `datetime.utcnow()` 裸 naive 值，否则会产生 8 小时偏差。**

---

## 4. 关键机制发现（改造必须绕开的坑）

| # | 机制 | 位置 | 对本期的影响 |
|---|---|---|---|
| M1 | **跨进程单例锁**：`pg_try_advisory_lock`，只有抢到锁的进程跑调度 | scheduler.py:91-113 | ✅ 有利：tick 天然不会双跑，无需再造分布式锁 |
| M2 | **并发路径忽略源过滤**：`collect_and_analyze_concurrent` 内部调 `resolve_collectors_verbose(db, type)` 时**未传 include/exclude**（service.py:747），而顺序路径传了（service.py:279-284） | service.py:747 | ⚠️ 必须修：否则 tick 用并发路径会把「到期的 3 个源」变成「全部 17 个源」 |
| M3 | **政府源 5 秒防抖**：`_GOV_LAST_RUN_AT` 模块级，`collect_and_analyze*` **每次调用检查一次**，命中抛 `CollectorThrottled` | service.py:69-72、298-302 | ⚠️ 若 tick 对每个到期源各发一次调用，第 2 个政府源必被 429 静默跳过。**必须把同一 tick 的到期源合并为一次调用** |
| M4 | **batch_id 语义**：一次调用 = 一个 batch | service.py:276-287 | 合并调用同时解决了采集日志可读性（见 R4） |
| M5 | **weibo_octopus 独立链路**：独立 cron + ack 回执 + `trigger_type="weibo_scheduled"` | scheduler.py:48-77 | 本期**不纳入 tick**，硬排除，零回归 |
| M6 | **enabled 是装配前置**：`enabled=false` 的源根本不会被 registry 返回 | registry.py:194-199 | `schedule_enabled` 与 `enabled` 是**两级开关**，需在文档/UI 明确：`enabled=false` → 自动+手动都不采 |
| M7 | **权限模型**：读 = `sources:read`（analyst 有）；写 = `require_admin`（`sources:write` 权限码存在但无任何端点使用） | admin_data_sources.py / permissions.py | 新增写接口一律 `require_admin`，与既有一致 |

---

## 5. 推荐改造方案

### 5.1 数据模型（扩展现有表，1 个迁移）

```python
# alembic: down_revision = "sec3b_perm_semantic"（当前唯一 head）
schedule_enabled         BOOLEAN     NOT NULL DEFAULT true     # 是否自动采集
schedule_interval_minutes INTEGER    NOT NULL DEFAULT 30       # 间隔分钟
next_collect_time        TIMESTAMP   NULL                      # 下次计划时间
last_collect_time        TIMESTAMP   NULL                      # 最近一次自动采集
```

- 历史数据兼容：`server_default` 保证既有 38 行自动获得 `true / 30`，**行为等价于今天的 `*/30`**
- `next_collect_time` 迁移后为 NULL，**tick 将 NULL 视为「立即到期」**；首个 tick 会把全部到期源合并成 1 个批次执行（等价于一次现有的全量定时批次），可接受
- 可选增强：迁移时按 `id % 5` 分钟错峰写入 `next_collect_time`，让 17 个源摊到 5 分钟内（避免与现状同样的尖峰）——**建议采纳**
- 约束建议：`CHECK (schedule_interval_minutes >= 5)`，防止误填 1 分钟把政府站打爆
- **不改 `collector_runs`，不改现有列语义**

### 5.2 Scheduler 改造（tick 模式 + 可回滚开关）

```
start_scheduler()
  ├─ if settings.collector_schedule_mode == "per_source":     ← 新配置，默认 per_source
  │     add_job(_run_collector_tick, IntervalTrigger(minutes=1), id="collector_tick",
  │             max_instances=1, coalesce=True, misfire_grace_time=30)
  └─ else:  # "cron" —— 一行配置回滚到今天的行为
        add_job(_run_collector_job, CronTrigger(collector_schedule_cron), id="collector_main")

  weibo_consumer / alert_eval 两个 job 原样保留，不动
```

`_run_collector_tick()` 采用 **claim-then-dispatch**（tick 本身 <1s，绝不阻塞）：

```
1) 选源（一次 SQL）
   SELECT * FROM data_sources
   WHERE enabled = true
     AND schedule_enabled = true
     AND key <> 'weibo_octopus'
     AND (next_collect_time IS NULL OR next_collect_time <= now)
   ORDER BY priority

2) 若为空 → 直接返回（绝大多数分钟走这条，开销 ≈ 1 次索引查询）

3) claim（先占位，防重复派发）
   对选中源：last_collect_time = now
             next_collect_time = now + interval
   commit  ← 即使随后采集失败，也不会在下一分钟重复触发（按间隔重试）

4) dispatch（合并成 1 次调用，解决 M3 防抖 + M4 批次可读性）
   CollectorService(include_data_source_keys=set(due_keys))
       .collect_and_analyze_concurrent(SessionLocal, trigger_type="scheduled", batch_id=...)
   → 在后台线程执行；tick 立即返回
   → 采集完成后照旧 auto_aggregate_after_collect()
```

配套：修复 M2（`collect_and_analyze_concurrent` 内的 `resolve_collectors_verbose` 补传 include/exclude），这是本期**唯一**对 Collector 主流程的改动，3 行，且顺序路径已有同款写法可对照。

### 5.3 采集执行（不改架构）

- 复用现有 `CollectorService` + `registry` 的 `include_data_source_keys` 过滤能力
- 「指定 datasource 执行」通过 **key 集合过滤**实现，语义等价于需求书里的 `collector_main(datasource_id=xxx)`，但零侵入（registry 天然按 key 过滤）
- 依旧每源写一条 `CollectorRun`，`trigger_type="scheduled"`，字段含义完全不变

### 5.4 API 变更（全部向后兼容）

| 方法 | 路径 | 权限 | 变更 |
|---|---|---|---|
| GET | `/api/admin/data-sources` | `sources:read` | 响应**新增** 4 字段 + `schedule_display`（如「每 30 分钟」/「已关闭」） |
| PATCH | `/api/admin/data-sources/{id}` | `require_admin` | 入参**新增** `schedule_enabled` / `schedule_interval_minutes`；改间隔时自动重算 `next_collect_time` |
| POST | `/api/admin/data-sources/schedule/batch` | `require_admin` | **新增**：`{scope: "all"\|"enabled_only", schedule_enabled, interval_minutes}` → 批量更新 + 返回受影响条数 |
| GET | `/api/admin/data-sources/schedule/summary` | `sources:read` | **新增**：返回「当前默认频率」（所有启用源间隔一致时返回该值，否则返回 `mixed` + 分布），供顶部全局设置区展示。**不新建 settings 表** |
| POST | `/api/collector/run` | `require_admin` | **可选 body** `{data_source_ids?: int[]}`；不传 = 现有全量行为，**完全不变** |

> 全局默认频率不落新表：由「所有启用源的 interval 众数/一致值」推导，避免引入第二处真相。

### 5.5 前端改造（`Sources.vue` + `types/index.ts`）

1. **表格新增 4 列**：自动采集（开关，非 admin 显示只读文案）、采集周期（下拉 15/30/60/180/360/720/1440 + 自定义）、下一次采集时间、最近采集时间
2. **顶部全局设置区**：`统一采集频率设置 · 当前默认：30 分钟 [修改]` → 弹窗（应用范围 = 所有数据源 / 仅当前启用数据源；周期选择）→ 调批量接口 → `reload()`
3. **权限**：沿用 `usePermission().isSuperuser`（与现有 `enabled` 开关、优先级输入框完全一致的写法），非 admin 只读展示
4. **状态保持**：所有状态源自后端字段，刷新后由 `reload()` 重新拉取，天然满足「刷新后状态保持」

### 5.6 配置项（`config.py` + `.env`）

```python
collector_schedule_mode: str = "per_source"     # per_source | cron  ← 回滚开关
collector_default_interval_minutes: int = 30    # 新建数据源默认间隔
collector_tick_interval_seconds: int = 60       # tick 频率（默认 60s）
collector_schedule_cron: str = "*/30 * * * *"   # 保留，mode=cron 时生效（回滚用）
collector_schedule_enabled: bool = True         # 保留，总开关语义不变
```

---

## 6. 风险分析

| # | 风险 | 等级 | 成因 | 缓解措施 |
|---|---|---|---|---|
| R1 | **政府源 5 秒防抖导致源被静默跳过** | 🔴 高 | `CollectorThrottled` 按「每次服务调用」判定，tick 若逐源调用，同分钟第 2 个政府源必被拒 | tick 内**合并为一次调用**（`include_data_source_keys=due_keys`）；测试用例覆盖「同分钟 2 个 gov 源同时到期」 |
| R2 | **并发路径丢失源过滤**（M2 缺陷） | 🔴 高 | `service.py:747` 未透传 include/exclude，会导致「只想采 3 个源」变成「采全部 17 个」，且 weibo 源可能被误采 | 先修缺陷 + 单测断言「传 include 时只装配对应源」；修复前禁止让 tick 走并发路径 |
| R3 | **时区偏差 8 小时** | 🟠 中 | 库为 naive 列 + 会话时区 Asia/Shanghai；若新代码用 `datetime.utcnow()` 写 `next_collect_time`，会比现实早 8 小时 → 每分钟都判定到期 → **采集风暴** | 统一 `datetime.now(timezone.utc)`（aware）；单测断言「间隔 60 分钟后 next 与 last 差值 = 60 分钟」；灰度首日观察 tick 命中频次 |
| R4 | **采集日志批次数量膨胀** | 🟠 中 | 现状 48 批/天；差异化后若各源频率错开，可能升至数百批/天，`/collection-logs` 是**全量聚合后 Python 分页**（admin_data_sources.py:756-782），批次数增长会拖慢该接口 | ①同分钟到期源合并成 1 批次（天然抑制）；②错峰迁移让源尽量对齐整点分钟；③监控该接口耗时，必要时下一期改为 SQL 分页 |
| R5 | **tick 抖动 / 长任务阻塞** | 🟠 中 | APScheduler `max_instances=1`，若 tick 内同步执行 150s 采集，后续 tick 被跳过 | claim-then-dispatch：tick 只做 SQL + 派发（<1s），采集在后台线程；`coalesce=True` + `misfire_grace_time=30` |
| R6 | **claim 后采集失败 → 本轮丢采** | 🟡 低 | 先更新 `next_collect_time` 再采集，失败不会立即重试 | 符合「按间隔重试」的产品语义；失败仍写 `CollectorRun(status=failed)`，健康摘要与质量统计照常告警 |
| R7 | **既有 scheduler 测试失败** | 🟡 低 | `test_weibo_schedule.py:76-104` 断言恰好 2 个 job 且 cron=`*/30` | 同步更新该测试（按 mode 分支断言），不删除原 cron 分支的覆盖 |
| R8 | **多实例并行改模型未迁移** | 🟡 低 | 历史教训：改 ORM 列但未迁移 → `UndefinedColumn` 故障 | 迁移与模型同一次提交；重启前先跑 `alembic upgrade head`；重启后用 401 探针法验证新后端已加载 |
| R9 | **误采停用源** | 🟡 低 | `enabled` 与 `schedule_enabled` 两级开关易混淆 | tick SQL 双条件 `enabled=true AND schedule_enabled=true`；UI 对 `enabled=false` 的行将调度列置灰 + tooltip 说明 |
| R10 | **前端文件虚拟化写坏** | 🟠 中 | 本机 node 虚拟化：非 node 途径写 `.vue` 会产生乱码字节 | 前端改动一律走 node 读写；改完 `vite build`（`--max-old-space-size=1400`）验证 |

---

## 7. 测试计划映射（对应需求书第九章）

### 后端（新增 `tests/test_datasource_schedule.py`）

| 需求 | 用例 | 断言要点 |
|---|---|---|
| 1. 默认仍 30 分钟 | `test_default_schedule_is_30min` | 迁移后新建/既有源 `schedule_enabled=true, interval=30`；tick 选源结果与 30 分钟节奏一致 |
| 2. 单源改 60 分钟 | `test_per_source_interval_respected` | 百度新闻设 60 → 采集后 `next = last + 60min`；第 31 分钟不被选中，第 61 分钟被选中 |
| 3. 关闭自动采集 | `test_schedule_disabled_never_ticks` | `schedule_enabled=false` 的源永不出现在 tick 选源结果；手动 `/collector/run` 仍可采 |
| 4. 全局批量设置 | `test_batch_schedule_update` | `scope=all` / `enabled_only` 两种范围的受影响行数正确；非 admin → 403 |
| 5. next_collect_time 计算 | `test_next_collect_time_calculation` | 时区一致（差值精确等于 interval）；NULL 视为到期；改间隔后立即重算 |
| 附加（防回归） | `test_concurrent_path_respects_source_filter` | 修复 M2：传 include 时装配数量 == 1 |
| 附加（防回归） | `test_two_gov_sources_same_tick_not_throttled` | 覆盖 R1：同分钟两个 gov 源都完成采集，无 `CollectorThrottled` |
| 兼容 | 更新 `test_weibo_schedule.py` | `mode=cron` 分支仍注册 2 job；`mode=per_source` 分支注册 tick + weibo |

测试执行方式（沿用既有约定）：
```
DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@localhost:5432/opinion_test \
DB_IDENTITY_CHECK=off  pytest backend/tests/test_datasource_schedule.py -v
```

### 前端

- 配置保存：改周期 → PATCH 成功 → `reload()` 后列表显示新周期与新的下次采集时间
- 权限控制：非 admin 账号看不到开关/下拉/「修改」按钮，只见只读文案
- 刷新保持：F5 后 `?tab=sources` 直达且数据由后端回填一致
- 构建验收：`vite build` 通过（本机无头浏览器缺失，交互靠构建 + 运行时验证）

---

## 8. 实施顺序建议（等待确认后执行）

```
Step 1  修复 M2（并发路径源过滤）+ 补单测           ← 独立可回滚，先落
Step 2  迁移 + 模型 4 列（错峰初始化 next_collect_time）
Step 3  API：list 序列化 / PATCH / 批量 / summary / collector run 可选入参
Step 4  scheduler：tick job + mode 开关（默认 per_source）
Step 5  后端测试 7 项 + 更新 test_weibo_schedule
Step 6  前端：types + Sources.vue（表格列 / 编辑弹窗 / 全局设置区）+ vite build
Step 7  部署：alembic upgrade head → 重启 uvicorn → 401 探针验证 → 观察 2 个 tick 周期
Step 8  产出 docs/Phase_DataSource-Schedule-1_实施报告.md
```

**回滚方案（预置）**：`.env` 设 `COLLECTOR_SCHEDULE_MODE=cron` → 重启即回到今天的 `*/30` 全量行为，新列保留但不生效（数据零损失）；如需彻底回滚，迁移 `downgrade()` 删 4 列。

---

## 9. 待确认事项（请拍板后再进入实施）

| # | 问题 | 建议默认 |
|---|---|---|
| Q1 | `weibo_octopus` 是否纳入统一 tick？ | **不纳入**，保留独立每小时 cron + ack 语义（零回归） |
| Q2 | 迁移时是否对 17 个启用源做错峰（`id % 5` 分钟）？ | **做**，避免所有源同分钟到期形成尖峰 |
| Q3 | 是否设置最小间隔下限（如 ≥5 分钟）？ | **设**，DB CHECK + API 校验双保险，防误填 1 分钟打爆政府站 |
| Q4 | 「全局默认频率」是否需要独立持久化（新建 settings 表）？ | **不需要**，由启用源间隔一致性推导，避免第二处真相 |
| Q5 | 手动指定单源采集，入参用 `data_source_ids` 还是 `keys`？ | **`data_source_ids`**（与前端列表 id 对齐，后端内部转 key 过滤） |
| Q6 | tick 频率 60 秒是否合适？ | **合适**，空转开销 = 每分钟一次带索引的 SQL |

---

**审计结论：具备实施条件。等待确认后按第 8 节顺序执行，不提前改动任何代码。**
