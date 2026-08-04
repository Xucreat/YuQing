# Phase DataSource-Schedule-Fix-1 数据源调度装配链路修复实施报告

> 生成日期：2026-08-03
> 范围：数据源发现（registry）与调度装配链路一致性修复
> 严格遵守：不改采集器业务、不改 Opinion/Event/Risk 链路、不改前端、不引入 MQ/ES/Redis/Celery、不做调度策略升级、不做全国模式

---

## 0. 重要前置发现（与任务前提的偏差，须先说明）

任务描述的现象为：「`resolve_collectors()` 因 `DataSource` ORM 引用未迁移字段抛 `UndefinedColumn`，被**静默回退到 `DEFAULT_SOURCES`（9 个硬编码源）**，导致 `bazhou_gov_xzdt` 等仅 DB 启用的源不进 scheduler」。

**只读审计确认：该现象在当前生产环境（127.0.0.1:5432/opinion_db，即 `db_identity_check` 校验的 VERIFIED 库）已不再复现。** 证据：

- `data_sources` 实际 **18 列，已包含全部 4 个调度字段**（`schedule_enabled` / `schedule_interval_minutes` / `next_collect_time` / `last_collect_time`）。
- `alembic current == heads == p12_datasource_schedule` —— **迁移 `p12` 已应用，数据库已在最新迁移 head**。
- 当前 `resolve_collectors(db)` 返回 **17 个采集器，与 `data_sources.enabled=true` 的 17 行完全一致**；`bazhou_gov_xzdt`、`bazhou_gov` 均在结果中；结果**不等于** `DEFAULT_SOURCES`（9 个），即**未发生静默回退**。

推断：该迁移很可能是在上一阶段（DataSource-Config-1）验证之后被应用，故本阶段接手时已无「缺列」这一直接触发条件。

**但任务明确要求的加固仍然成立且已落地**：
1. 发现链路仍采用 `db.query(DataSource)`（本质 `SELECT *`），**未来**一旦 ORM 新增字段而未及时迁移，仍会整表失败并回退——根因机制仍在。
2. 原 fallback 仅 `logger.warning`（低可见度），不符合「禁止静默 / 可观测」要求。

故本阶段在「不改动可用行为」的前提下，补齐上述两项加固（Phase 3 + Plan B 的防御性部分），并保留 Plan A 已完成的事实。

---

## 1. 审计结果

### 1.1 DataSource 模型 vs 生产库结构差异

| 字段 | ORM 存在 | DB 存在 | 状态 |
|---|---|---|---|
| id / key / name / type / class_path | ✅ | ✅ | 一致 |
| enabled / priority | ✅ | ✅ | 一致 |
| scope_region_codes / config_json | ✅ | ✅ | 一致 |
| last_run_at / last_status / last_error | ✅ | ✅ | 一致 |
| created_at / updated_at | ✅ | ✅ | 一致 |
| **schedule_enabled** | ✅ | ✅ | 一致（迁移已加） |
| **schedule_interval_minutes** | ✅ | ✅ | 一致（迁移已加） |
| **next_collect_time** | ✅ | ✅ | 一致（迁移已加） |
| **last_collect_time** | ✅ | ✅ | 一致（迁移已加） |

> 结论：**当前无字段缺失**。差异风险仅在未来 ORM 演进时复现。

### 1.2 registry 数据源发现逻辑（修改前）

`app/collectors/registry.py :: _resolve_core`：

```
db.query(DataSource).filter(enabled==True).order_by(priority,id).all()   # 等价于 SELECT *
   │ 任一映射列在 DB 缺失 → SQLAlchemy 抛 UndefinedColumn
   ▼
except Exception:
   logger.warning("读取 data_sources 失败，回退默认源")   # ← 仅 warning，可见度低
   rows = None
   ▼
if not rows: rows = DEFAULT_SOURCES   # ← 9 个硬编码源，不含 bazhou_gov_xzdt
```

**当前真实调用链（生产已验证）**：

```
data_sources 表 (17 enabled)
      │  resolve_collectors(db)  [已改为显式列查询，见 §3]
      ▼
CollectorService.collect_and_analyze(...)
      ▲
      │  _run_collector_tick()  ──  raw SQL:
scheduler                              SELECT id,key FROM data_sources
      │                                 WHERE enabled AND schedule_enabled
      │                                       AND key!='weibo_octopus'
      │                                       AND next_collect_time<=now()
      ▼                                  ↓ (到期源 key 集合)
CollectorService(include=到期源keys)   → 逐源采集
```

scheduler 本身已通过 raw SQL 直接读 `data_sources`（含 `schedule_enabled` / `next_collect_time`），属 DB 驱动；其正确性依赖迁移字段存在（已满足）。

---

## 2. 根因

- **直接根因（历史）**：`DataSource` ORM 模型比生产库多 4 个调度字段，ORM 整表加载（`SELECT *`）在缺列时抛 `UndefinedColumn`，被 `except` 捕获后**静默**回退到 9 个硬编码源，使「数据源管理页显示启用」与「scheduler 实际采集列表」不一致。
- **当前状态**：该直接根因已被迁移 `p12` 消除（字段已补齐）。
- **残留风险（本次修复目标）**：
  1. 发现查询为 `SELECT *`，对**未来**字段漂移零容忍 → 需改为显式列。
  2. 回退仅为 `warning`，运维难以察觉 → 需 loud ERROR + 健康标记。

---

## 3. 修复方案

### 方案选择

| 方案 | 适用性 | 结论 |
|---|---|---|
| **A：执行迁移同步** | 迁移 `p12` 已存在且已应用（DB 在 head） | ✅ 已完成（无需重跑；重跑为 no-op） |
| **B：显式列查询（禁止 SELECT *）** | 防御未来字段漂移、消除整表失败 | ✅ 本次落地 |
| **Phase 3：禁止静默回退** | 无论 A/B，回退必须可观测 | ✅ 本次落地 |

> 未采用「大规模重写发现机制 / 新增健康子系统」等扩展动作，严守范围。

### 具体修改

**`backend/app/collectors/registry.py`**

1. 新增模块级观测状态（供 `/health` 读取）：
   ```python
   last_discovery_degraded: bool = False
   last_discovery_error: Optional[str] = None
   ```
2. 发现查询改为**仅选取装配所需字段**（禁止 `SELECT *`）：
   ```python
   rows = [dict(r) for r in db.execute(
       select(DataSource.id, DataSource.key, DataSource.name,
              DataSource.class_path, DataSource.scope_region_codes,
              DataSource.config_json)
       .where(DataSource.enabled == True)
       .order_by(DataSource.priority, DataSource.id)
   ).mappings().all()]
   ```
   → 即使未来 ORM 增列未迁移，发现链路也不再整表失败。
3. DB 读取成功即清除降级标记；**异常时**改为 loud `logger.error("DataSource registry DB load failed. collector discovery degraded to DEFAULT_SOURCES. ...")`，并置 `last_discovery_degraded=True` + 记录错误（原 `logger.warning` 提升为 ERROR，**不再静默**）。
4. `_resolve_core` 内以 `global last_discovery_degraded, last_discovery_error` 写回模块级标记（修复初版因局部变量遮蔽导致标记失效的问题，已由验证 `[E]` 捕获并修正）。

**`backend/app/main.py`**

5. `/health` 端点新增发现状态（满足「health 可发现」）：
   ```python
   @app.get("/health")
   def health():
       from app.collectors import registry as _registry
       degraded = _registry.last_discovery_degraded
       return {"status": "ok",
               "collector_discovery": "degraded" if degraded else "db_driven",
               "collector_discovery_error": _registry.last_discovery_error if degraded else None}
   ```

---

## 4. 修改文件列表

| 文件 | 改动 |
|---|---|
| `backend/app/collectors/registry.py` | 显式列查询（禁止 SELECT *）；降级标记 `last_discovery_degraded`/`last_discovery_error`；回退日志由 warning 升级为 ERROR 并显式标记 |
| `backend/app/main.py` | `/health` 暴露 `collector_discovery` 状态（db_driven / degraded） |

未改动：任何采集器业务逻辑、Opinion/Event/Risk 链路、前端、调度策略、数据库数据（无手工 UPDATE/DELETE）。

---

## 5. 验证结果

验证脚本：`backend/_verify_schedule_fix.py`（只读 + 安全模拟，不修改生产数据）。

### 5.1 数据源发现（registry）

| 指标 | 结果 |
|---|---|
| `data_sources` 总行 / 启用 | 38 / 17 |
| `resolve_collectors(db)` 返回数 | **17** |
| 是否等于 `DEFAULT_SOURCES`(9) | **否**（证明非回退） |
| `bazhou_gov_xzdt` 在发现列表 | **是** |
| `bazhou_gov` 在发现列表 | **是** |
| `last_discovery_degraded` | **False**（DB 正常） |

→ **PASS**：发现完全由 DB 配置驱动，bazhou 已纳入。

### 5.2 scheduler 验证

| 指标 | 结果 |
|---|---|
| scheduler 候选集（enabled + schedule_enabled） | 17 |
| `bazhou_gov_xzdt` 在候选集 | **是** |
| `bazhou_gov_xzdt` schedule_enabled / interval / next_collect_time 已初始化 | True / 30 / 已设 |

→ **PASS**：scheduler 候选集含 `bazhou_gov_xzdt`，到点即被逐源 tick 认领采集。

### 5.3 Phase DataSource-Config-1 回归

| 指标 | 结果 |
|---|---|
| 全部采集器注入 `source_config` | **是** |
| `get_int("max_items", 10)` / `get_str("filter_mode", ...)` / `get_str("keyword_scope", ...)` | 正常（缺省降级生效） |

→ **PASS**：配置化能力未被本阶段改动影响。

### 5.4 模拟 DB 查询失败（禁止静默）

| 指标 | 结果 |
|---|---|
| 回退结果数 | 9（`DEFAULT_SOURCES`，安全兜底保留） |
| `last_discovery_degraded` | **True** |
| 捕获日志含 `DataSource registry DB load failed` | **是**（ERROR 级） |
| `/health` 在降级时输出 | `{"status":"ok","collector_discovery":"degraded","collector_discovery_error":"RuntimeError: ..."}` |

→ **PASS**：DB 失败时不再静默——loud ERROR + 健康标记 + `/health` 可观测。

---

## 6. 部署说明

- 上述代码改动需**重启后端 uvicorn** 后方生效（当前运行实例仍加载旧 `registry.py`/`main.py`）。
- 因迁移 `p12` 已应用，**当前生产采集行为本就正确**（17 源全量驱动、bazhou 已在采集）；本次重启仅启用「降级可观测 + 未来字段漂移免疫」加固，属零行为风险的安全增强。
- 重启后建议观察：`GET /health` 应返回 `"collector_discovery": "db_driven"`；若某次 DB 异常，该字段会变 `degraded` 并伴随 ERROR 日志，即可第一时间发现。

---

## 7. 本阶段明确未做

- 不新增采集器；不修改 Collector 业务逻辑；不改动 Opinion/Event/Risk 链路。
- 不修改前端页面；不引入 Redis/ES/MQ/Celery；不做调度策略升级；不做全国模式。
- 不手工修改 `data_sources` 业务数据、不 DELETE 数据源、不重跑已应用的迁移（无必要）。
