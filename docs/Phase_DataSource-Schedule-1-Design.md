# Phase DataSource-Schedule-1 设计文档

> 阶段：第二章「设计」（审计已确认，Q1-Q6 采用推荐默认）
> 设计日期：2026-08-03
> 依赖：审计报告 `docs/Phase_DataSource-Schedule-1-Audit.md`（第一章结论全部沿用）
> 性质：**本文件为设计规格，不写业务代码；实施阶段按本文逐条落地。**

---

## 0. 设计目标与范围

| 目标 | 说明 | 对应关系 |
|---|---|---|
| 单源频率 | 每个数据源可独立设置采集间隔（分钟） | 需求 §2 |
| 全局默认 | 管理员可一键统一设置所有/启用源的默认频率 | 需求 §2 |
| 关闭自动采集 | 单源可关闭自动采集，保留手动 | 需求 §2 |
| 保留手动 | `POST /collector/run` 手动采集不变，并支持指定单源 | 需求 §3 |
| 禁用新中间件 | 不引入 Celery/Redis/MQ，复用 APScheduler + 现有 CollectorService | 需求 §4 |
| 兼容性 | 不改 `CollectorRun` 语义、不删手动采集、`next_collect_time` 默认 NULL=立即到期 | 需求 §7 |

**已锁定的决策（Q1-Q6，用户确认采用推荐默认）**

| # | 决策 | 取值 |
|---|---|---|
| Q1 | weibo 纳入 tick？ | **否**（保留独立每小时 cron + ack） |
| Q2 | 迁移错峰 | **做**（`id % 5` 分钟摊到 5 分钟内） |
| Q3 | 最小间隔下限 | **≥5 分钟**（DB CHECK + API 双保险） |
| Q4 | 全局默认是否落表 | **不建表**（由启用源间隔一致性推导） |
| Q5 | 手动指定单源入参 | **`data_source_ids`（int[]）**，后端转 key 过滤 |
| Q6 | tick 频率 | **60 秒**（`IntervalTrigger(seconds=60)`） |

---

## 1. 数据模型与迁移设计

### 1.1 ORM（`backend/app/models/data_source.py`）

在 `DataSource` 现有 14 列之后新增 4 列。导入补充 `text`：

```python
from sqlalchemy import Boolean, DateTime, Integer, String, Text, text

# —— 自动采集调度（Phase DataSource-Schedule-1）——
schedule_enabled: Mapped[bool] = mapped_column(
    Boolean, nullable=False, default=True, server_default=text("true")
)
schedule_interval_minutes: Mapped[int] = mapped_column(
    Integer, nullable=False, default=30, server_default=text("30")
)
next_collect_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
last_collect_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- `default=30` / `default=True` 保证 ORM 新建源（如 `create_data_source`）自动获得默认值，无需改创建逻辑。
- 历史 38 行：迁移 `server_default` 使其自动获得 `true / 30`，**行为等价于今天的 `*/30` 全量**。

### 1.2 Alembic 迁移（新增 1 个）

- 文件：`backend/alembic/versions/p12_datasource_schedule.py`
- `revision = "p12_datasource_schedule"`，`down_revision = "sec3b_perm_semantic"`（当前唯一 head）
- 升级：
  1. 加 4 列（2 个 NOT NULL + server_default，2 个 NULL）。
  2. CHECK 约束 `schedule_interval_minutes >= 5`（命名 `ck_ds_schedule_interval_min`）。
  3. 错峰初始化（Q2）：对 `enabled AND schedule_enabled` 的源，把 `next_collect_time` 摊到未来 `id % 5` 分钟内，避免所有源同分钟到期形成尖峰。
- 降级：依次 `drop_column` 4 列（CHECK 随列删除自动移除）。

```python
"""add per-source schedule columns
Revision ID: p12_datasource_schedule
Revises: sec3b_perm_semantic
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

revision = "p12_datasource_schedule"
down_revision = "sec3b_perm_semantic"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_sources",
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "data_sources",
        sa.Column("schedule_interval_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
    )
    op.add_column(
        "data_sources",
        sa.Column("next_collect_time", sa.TIMESTAMP(), nullable=True),
    )
    op.add_column(
        "data_sources",
        sa.Column("last_collect_time", sa.TIMESTAMP(), nullable=True),
    )
    # Q3 最小间隔下限（DB 级兜底）
    op.create_check_constraint(
        "ck_ds_schedule_interval_min", "data_sources", "schedule_interval_minutes >= 5"
    )
    # Q2 错峰：启用且开启自动采集的源，next 摊到未来 0~4 分钟内
    op.execute(
        text(
            "UPDATE data_sources "
            "SET next_collect_time = now() + make_interval(mins => (id % 5)) "
            "WHERE enabled = true AND schedule_enabled = true"
        )
    )


def downgrade():
    op.drop_column("data_sources", "last_collect_time")
    op.drop_column("data_sources", "next_collect_time")
    op.drop_column("data_sources", "schedule_interval_minutes")
    op.drop_column("data_sources", "schedule_enabled")
```

---

## 2. Scheduler tick 设计

### 2.1 时区一致性策略（根治 R3）

**tick 的全部时间比较与写入一律走 PostgreSQL `now()`（数据库本地时间，Asia/Shanghai 墙钟），不在 Python 侧生成 `datetime`**。原因：

- `data_sources` 时间列是 `TIMESTAMP WITHOUT TIME ZONE`，代码侧 aware UTC 经驱动转换后落库为北京墙钟（审计报告 §3.4 实证）。
- 若 tick 在 Python 用 `datetime.now(timezone.utc)` 与库内北京墙钟比较，会引入瞬时偏差风险；统一用 `now()` 让「选源比较」与「claim 写入」都在同一 DB 时钟域，彻底规避 8 小时偏差。
- PATCH / 批量接口仍用 Python `datetime.now(timezone.utc)`（aware），驱动转换后与 `now()` 落地值同域，二者一致（审计 R3 缓解维持）。

### 2.2 `start_scheduler()` 改造（`backend/app/core/scheduler.py`）

新增配置开关 `collector_schedule_mode`（默认 `per_source`）。在 `collector_schedule_enabled` 为真时：

```python
if settings.collector_schedule_enabled:
    mode = getattr(settings, "collector_schedule_mode", "per_source")
    if mode == "cron":
        # 回滚路径：严格回到今天的行为
        scheduler.add_job(
            _run_collector_job,
            trigger=CronTrigger.from_crontab(settings.collector_schedule_cron),
            id="collector_main", name="Main collector cycle", replace_existing=True,
        )
    else:
        # 本期默认：每分钟 tick 检查到期源
        scheduler.add_job(
            _run_collector_tick,
            trigger=IntervalTrigger(seconds=settings.collector_tick_interval_seconds),
            id="collector_tick", name="Per-source schedule tick",
            max_instances=1, coalesce=True, misfire_grace_time=30, replace_existing=True,
        )
    # weibo 独立链路与 alert_eval 原样保留，不动
    scheduler.add_job(_run_weibo_consumer_job, trigger=CronTrigger.from_crontab(settings.weibo_consumer_schedule_cron), id="weibo_consumer", name="Weibo hourly consumer", replace_existing=True)
```

> `max_instances=1 + coalesce + misfire_grace_time=30` 保证上一 tick 若因后台采集未退出也不会并发叠加（R5）。

### 2.3 `_run_collector_tick()`（claim-then-dispatch，<1s 同步段）

```python
def _run_collector_tick():
    """per_source 调度：每分钟检查到期源，合并为一次并发采集（防政府源防抖 R1）。"""
    db = SessionLocal()
    try:
        # 1) 选源（一次 SQL，走 DB now()，规避时区偏差）
        due = db.execute(
            select(DataSource.id, DataSource.key, DataSource.schedule_interval_minutes)
            .where(
                DataSource.enabled == True,                       # M6 两级开关：enabled 前置
                DataSource.schedule_enabled == True,
                DataSource.key != "weibo_octopus",                # Q1 硬排除 weibo
                or_(
                    DataSource.next_collect_time.is_(None),       # NULL = 立即到期
                    DataSource.next_collect_time <= func.now(),
                ),
            )
            .order_by(DataSource.priority.asc())
        ).all()
        if not due:
            return  # 绝大多数分钟走这条，开销 ≈ 1 次索引查询

        due_ids = [r.id for r in due]
        due_keys = {r.key for r in due}

        # 2) claim（先占位，防重复派发；用 DB now() 保证时区一致）
        db.execute(
            text(
                "UPDATE data_sources "
                "SET last_collect_time = now(), "
                "    next_collect_time = now() + make_interval(mins => schedule_interval_minutes) "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": due_ids},
        )
        db.commit()
    finally:
        db.close()  # claim 完成即释放连接

    # 3) dispatch：合并为一次并发调用（解决 R1 政府源防抖 + M4 批次可读性）
    #    include_keys 传入后台任务，穿透到 CollectorService（见 §4）
    start_task("collector", _run_collect_task, SessionLocal, None, "scheduler", due_keys)
```

- 后台 `collect_and_analyze_concurrent` 只触发**一次** `_uses_government()` 防抖判定（M3/R1），同 tick 多个政府源不会被逐个 429。
- `batch_id` 由 `_run_collect_task` 内部生成，本 tick 的到期源合并为同一批次（M4），采集日志可读。

### 2.4 需要的 import（`scheduler.py`）

```python
from sqlalchemy import select, update, or_, text, func
from app.models.data_source import DataSource
# 已有：from apscheduler.triggers.interval import IntervalTrigger
```

---

## 3. M2 修复设计（并发路径源过滤缺陷）

**唯一一处对 Collector 主流程的改动**（3 行），修复 R2。

`backend/app/collectors/service.py` `collect_and_analyze_concurrent`（当前 L744-753）：

```python
# 修复前（缺陷）：忽略构造器传入的过滤集合，全部源都被装配
resolved = resolve_collectors_verbose(resolve_db, self.collector_type)

# 修复后：透传 include / exclude（与顺序路径 L279-284 完全一致）
resolved = resolve_collectors_verbose(
    resolve_db,
    self.collector_type,
    include_data_source_keys=self.include_data_source_keys,
    exclude_data_source_keys=self.exclude_data_source_keys,
)
```

- `self.include_data_source_keys` / `self.exclude_data_source_keys` 已是 `frozenset | None`（构造器 L174-183 已存）。
- 修复前**禁止**让 tick 走并发路径；修复后 tick 用 `CollectorService(include_data_source_keys=due_keys)` 即精确只采到期源。

---

## 4. 手动单源采集（API 改造）

### 4.1 `POST /collector/run` 加可选 `data_source_ids`

文件 `backend/app/api/collector.py`：

```python
from typing import List, Optional
from pydantic import BaseModel
from app.models.data_source import DataSource

class CollectorRunRequest(BaseModel):
    data_source_ids: Optional[List[int]] = None

@collector_router.post("/run", response_model=CollectorTaskResponse, status_code=200)
def run_collector(
    request: Request,
    body: Optional[CollectorRunRequest] = None,   # 新增，缺省=现有全量行为
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> CollectorTaskResponse:
    include_keys = None
    if body and body.data_source_ids:
        rows = db.execute(
            select(DataSource.key).where(DataSource.id.in_(body.data_source_ids))
        ).scalars().all()
        include_keys = set(rows)          # Q5：id → key 转换；空集合=选中 0 个源
    task_id = start_task(
        "collector", _run_collect_task, SessionLocal,
        current_user.id, current_user.username, include_keys,
    )
    # 审计与返回逻辑不变 ...
```

- **向后兼容**：现有前端手动采集不传 body，FastAPI 接受缺省 → `include_keys=None` → 全量，行为完全不变。
- `include_keys` 为空集合时，`_resolve_core` 过滤后无源 → 不采集（合理边界）。

### 4.2 `_run_collect_task` 穿透 `include_keys`

```python
def _run_collect_task(task, session_factory, operator_id=None, operator_username=None, include_keys=None):
    ...
    service = CollectorService(include_data_source_keys=include_keys)
    result = service.collect_and_analyze_concurrent(session_factory, on_progress=_on_progress, batch_id=batch_id)
```

- 既有手动调用不传第 5 参 → `include_keys=None` → 全量，无回归。

---

## 5. 数据源管理 API 设计

文件 `backend/app/api/admin_data_sources.py`。

### 5.1 `GET /admin/data-sources`（list）序列化新增字段

`_serialize()`（L254-276）追加：

```python
"schedule_enabled": ds.schedule_enabled,
"schedule_interval_minutes": ds.schedule_interval_minutes,
"next_collect_time": ds.next_collect_time.isoformat() if ds.next_collect_time else None,
"last_collect_time": ds.last_collect_time.isoformat() if ds.last_collect_time else None,
"schedule_display": _schedule_display(ds),
```

新增 helper：

```python
def _schedule_display(ds: DataSource) -> str:
    if not ds.schedule_enabled:
        return "已关闭自动采集"
    iv = ds.schedule_interval_minutes
    if iv < 60:
        return f"每 {iv} 分钟"
    if iv == 60:
        return "每小时"
    if iv % 60 == 0:
        return f"每 {iv // 60} 小时"
    return f"每 {iv} 分钟"
```

### 5.2 `PATCH /admin/data-sources/{id}` 新增字段

在 `update_data_source`（L616-677）的 `with audit_write(...)` 块内追加（需 `from datetime import datetime, timezone, timedelta`）：

```python
if "schedule_enabled" in body and body["schedule_enabled"] is not None:
    ds.schedule_enabled = bool(body["schedule_enabled"])
    if ds.schedule_enabled and ds.next_collect_time is None:
        # 重新启用且无下次时间 → 顺延一个间隔，避免立即爆发
        ds.next_collect_time = datetime.now(timezone.utc) + timedelta(minutes=ds.schedule_interval_minutes)

if "schedule_interval_minutes" in body and body["schedule_interval_minutes"] is not None:
    try:
        iv = int(body["schedule_interval_minutes"])
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="schedule_interval_minutes 必须为整数")
    if iv < 5:                                  # Q3 API 级双保险
        raise HTTPException(status_code=422, detail="采集间隔不能小于 5 分钟")
    ds.schedule_interval_minutes = iv
    # 改间隔即重算下次采集时间（以当前时间为基准顺延）
    ds.next_collect_time = datetime.now(timezone.utc) + timedelta(minutes=iv)
```

### 5.3 `POST /admin/data-sources/schedule/batch`（新增，全局统一设置）

```python
@admin_ds_router.post("/schedule/batch")
def batch_update_schedule(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    scope = body.get("scope")
    if scope not in ("all", "enabled_only"):
        raise HTTPException(status_code=422, detail="scope 必须为 all 或 enabled_only")
    se = body.get("schedule_enabled")
    iv = body.get("interval_minutes")
    if not isinstance(se, bool) or iv is None:
        raise HTTPException(status_code=422, detail="schedule_enabled 与 interval_minutes 必填")
    try:
        iv = int(iv)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="interval_minutes 必须为整数")
    if iv < 5:
        raise HTTPException(status_code=422, detail="采集间隔不能小于 5 分钟")

    now = datetime.now(timezone.utc)
    stmt = update(DataSource)
    if scope == "enabled_only":
        stmt = stmt.where(DataSource.enabled == True)
    stmt = stmt.values(
        schedule_enabled=se,
        schedule_interval_minutes=iv,
        next_collect_time=now + timedelta(minutes=iv),
    )
    res = db.execute(stmt)
    db.commit()
    return {"updated": res.rowcount}
```

### 5.4 `GET /admin/data-sources/schedule/summary`（新增，顶部全局设置区展示）

```python
@admin_ds_router.get("/schedule/summary")
def schedule_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("sources:read")),
):
    rows = db.execute(
        select(DataSource.schedule_interval_minutes, func.count())
        .where(DataSource.enabled == True, DataSource.schedule_enabled == True)
        .group_by(DataSource.schedule_interval_minutes)
    ).all()
    dist = {int(iv): int(c) for iv, c in rows}
    if len(dist) == 1:
        return {"mode": "uniform", "interval_minutes": next(iter(dist)), "distribution": dist}
    return {"mode": "mixed", "interval_minutes": None, "distribution": dist}
```

> Q4：**不建 settings 表**；「全局默认频率」= 启用且开启自动采集源的间隔众数/一致值；`mixed` 时前端提示用户当前不一致。

### 5.5 权限矩阵

| 接口 | 权限 | 说明 |
|---|---|---|
| `GET /admin/data-sources` | `sources:read` | 读，analyst 可用 |
| `PATCH /admin/data-sources/{id}` | `require_admin` | 改调度字段 |
| `POST /admin/data-sources/schedule/batch` | `require_admin` | 全局设置 |
| `GET /admin/data-sources/schedule/summary` | `sources:read` | 展示 |
| `POST /collector/run` | `require_admin` | 手动（含指定单源） |

与既有约定一致（M7），新增写接口一律 `require_admin`。

---

## 6. 前端设计（`Sources.vue` + `types/index.ts`）

> ⚠️ `.vue` 受本机 node 虚拟化影响，**实施阶段必须用 node 读写**（见审计报告 §2.3 / 工程约定）。本设计只描述改动点，不在此写实现。

### 6.1 `types/index.ts` — `DataSourceItem` 接口新增

```ts
schedule_enabled: boolean;
schedule_interval_minutes: number;
next_collect_time: string | null;
last_collect_time: string | null;
schedule_display: string;
```

### 6.2 `Sources.vue` 表格新增 4 列（现有 11 列之后）

| 列 | 控件 | 只读条件 |
|---|---|---|
| 自动采集 | `el-switch` | 非 admin 或 `enabled=false` 时禁用 + tooltip「源已停用」 |
| 采集周期 | `el-select`（15/30/60/180/360/720/1440 + 自定义） | 非 admin 禁用 |
| 下次采集 | 文本（格式化 `next_collect_time`） | 始终只读 |
| 最近采集 | 文本（格式化 `last_collect_time`） | 始终只读 |

### 6.3 编辑弹窗新增「自动采集调度」分区

- `el-switch`（schedule_enabled）+ `el-select`（schedule_interval_minutes）。
- 保存：`PATCH /admin/data-sources/{id}` 带这两个字段 → 成功 `reload()`。
- 权限：分区整体对非 admin 隐藏/只读（沿用现有 `usePermission().isSuperuser` 写法）。

### 6.4 顶部全局设置区

- 展示：调 `GET /schedule/summary` → 「当前默认：每 30 分钟 [修改]」（mixed 时显示「多档频率，点击统一」）。
- 「修改」按钮（仅 admin）：弹窗含「应用范围」radio（`all` / `enabled_only`）+ 周期 `el-select` → `POST /schedule/batch` → `reload()`。

### 6.5 状态保持

列表数据全部源自后端字段，`reload()` 重新拉取，天然满足「刷新后状态保持」与 `?tab=sources` 直达。

---

## 7. 配置项设计（`config.py` + `.env`）

`backend/app/core/config.py` 新增（位于 `collector_schedule_cron` 附近）：

```python
# Phase DataSource-Schedule-1：per_source 调度
collector_schedule_mode: str = "per_source"          # per_source | cron（回滚开关）
collector_default_interval_minutes: int = 30         # 新建数据源默认间隔（仅文档意图，ORM default=30 已生效）
collector_tick_interval_seconds: int = 60            # tick 频率（Q6 默认 60s）
# 既有字段保留：collector_schedule_enabled / collector_schedule_cron / weibo_consumer_schedule_cron
```

根目录 `.env` 可加（可选，回滚用）：

```
COLLECTOR_SCHEDULE_MODE=per_source
COLLECTOR_TICK_INTERVAL_SECONDS=60
# 紧急回滚：COLLECTOR_SCHEDULE_MODE=cron → 重启即回到 */30 全量
```

---

## 8. 兼容性设计（R4-R10 缓解）

| 风险 | 缓解（本设计落地动作） |
|---|---|
| R1 政府源防抖 | tick 合并为一次 `collect_and_analyze_concurrent`（§2.3），仅一次防抖判定 |
| R2 并发路径丢过滤 | §3 修复 M2，补传 include/exclude |
| R3 时区偏差 | tick 全用 DB `now()`（§2.2）；PATCH/批量用 aware UTC，落地同域 |
| R4 日志批次膨胀 | 同 tick 合并为 1 批次 + 错峰迁移摊平；监控 `/collection-logs` 耗时 |
| R5 tick 阻塞 | `max_instances=1 + coalesce + misfire_grace_time=30`；claim <1s 后后台派发 |
| R6 claim 后失败 | 符合「按间隔重试」语义；失败仍写 `CollectorRun(failed)` |
| R7 既有测试失败 | §9 更新 `test_weibo_schedule.py` |
| R8 改模型未迁移 | 迁移与模型同次提交；部署先 `alembic upgrade head`；401 探针验证 |
| R9 误采停用源 | tick SQL 双条件 `enabled AND schedule_enabled`；UI 停用行调度列置灰 |
| R10 前端写坏 | 实施阶段前端改动一律 node 读写 + `vite build --max-old-space-size=1400` 验收 |

---

## 9. 测试计划（对应需求第九章）

### 9.1 新增 `backend/tests/test_datasource_schedule.py`

| 需求点 | 用例 | 断言 |
|---|---|---|
| 1 默认仍 30 分钟 | `test_default_schedule_is_30min` | 迁移后既有/新建源 `schedule_enabled=true, interval=30` |
| 2 单源改 60 分钟 | `test_per_source_interval_respected` | 设 60 → 采集后 `next ≈ last + 60min`；第 31 分钟不选、第 61 分钟选 |
| 3 关闭自动采集 | `test_schedule_disabled_never_ticks` | `schedule_enabled=false` 永不入选；手动 `/collector/run` 仍可采 |
| 4 全局批量设置 | `test_batch_schedule_update` | `scope=all` / `enabled_only` 受影响行数正确；非 admin → 403 |
| 5 next 计算 | `test_next_collect_time_calculation` | 时区一致（差值=interval）；NULL 视到期；改间隔即重算 |
| 防回归 | `test_concurrent_path_respects_source_filter` | 修复 M2：传 include 装配数 == 1（不扩到 17） |
| 防回归 | `test_two_gov_sources_same_tick_not_throttled` | 同 tick 两 gov 源均完成，无 `CollectorThrottled`（R1） |

### 9.2 更新 `backend/tests/test_weibo_schedule.py`

按 `collector_schedule_mode` 分支断言：
- `cron` 模式：注册 `collector_main` + `weibo_consumer` + `alert_eval`（保持原 2-job 断言语义）。
- `per_source` 模式：注册 `collector_tick` + `weibo_consumer` + `alert_eval`。

### 9.3 前端验证（无头浏览器缺失，靠 build + 运行时）

- 周期保存 → PATCH 成功 → `reload()` 后列表显示新周期与下次时间。
- 非 admin 账号看不到开关/下拉/「修改」按钮。
- F5 后 `?tab=sources` 直达且数据由后端回填一致。
- `vite build` 通过。

### 9.4 测试执行约定

```
DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@localhost:5432/opinion_test \
DB_IDENTITY_CHECK=off  pytest backend/tests/test_datasource_schedule.py backend/tests/test_weibo_schedule.py -v
```

---

## 10. 实施顺序（8 步，含回滚预置）

```
Step 1  修复 M2（service.py concurrent 路径源过滤）+ 补单测
Step 2  迁移 + 模型 4 列（错峰初始化 next_collect_time + CHECK ≥5）
Step 3  API：list 序列化 / PATCH / batch / summary / collector run 可选入参
Step 4  scheduler：tick job + mode 开关（默认 per_source）
Step 5  后端测试 7 项 + 更新 test_weibo_schedule
Step 6  前端：types + Sources.vue（4 列 / 编辑弹窗 / 全局设置区）+ vite build
Step 7  部署：alembic upgrade head → 重启 uvicorn → 401 探针验证 → 观察 2 个 tick 周期
Step 8  产出 docs/Phase_DataSource-Schedule-1_实施报告.md
```

**回滚方案（预置）**：`.env` 设 `COLLECTOR_SCHEDULE_MODE=cron` → 重启即回今天 `*/30` 全量；新列保留不生效（数据零损失）。彻底回滚：`alembic downgrade -1` 删 4 列。

---

## 11. 验收标准

1. 每个启用源可在 UI 单独设置间隔（15~1440 分钟，下限 5）；关闭后不再被 tick 选中。
2. 全局「统一采集频率」一键应用于所有/启用源，顶部设置区展示当前默认（uniform/mixed）。
3. `POST /collector/run` 不传参 = 现有全量；传 `data_source_ids` = 仅采指定源。
4. 定时批次从「每 30 分钟全量」变为「各源按自身间隔到期触发」，政府源同 tick 不被防抖跳过。
5. 迁移后历史 38 源自动获得 `true/30`，首 tick 行为等价于一次原全量批次；无采集风暴（R3）。
6. 后端 7 项测试 + 更新后的 `test_weibo_schedule` 全绿；前端 `vite build` 通过。
7. 不引入任何新中间件（Celery/Redis/MQ）；`CollectorRun` 语义与手动采集完全不变。

---

**设计结论：规格已就绪，可在确认后按第 10 节顺序进入实施（写代码）。**
