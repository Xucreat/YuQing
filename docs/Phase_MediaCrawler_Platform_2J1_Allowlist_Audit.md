# Phase MediaCrawler Platform-2-J1 Scheduler Allowlist Audit

## 1. Status

```text
READY_FOR_SCHEDULER_GRAY_APPROVAL
```

本阶段只读审计和临时 process-environment candidate 验证已完成。未修改代码、
DataSource、`.env`、模型或 migration，未启动 Scheduler，未执行真实采集。

## 2. Allowlist Definition

实现位置：

```text
backend/app/core/scheduler.py
```

关键函数：

```text
_normalize_source_allowlist()
_configured_source_allowlist()
```

`_configured_source_allowlist()` 在 Scheduler 进程启动/装配时读取：

```text
SCHEDULER_SOURCE_ALLOWLIST
```

读取方式为当前进程环境变量，值按逗号分隔并规范化为
`frozenset[str]`。未配置或空字符串表示 `None`，保留全量候选语义。

本阶段没有修改 `.env`，只在独立 Python 进程中临时设置环境变量进行查询。

## 3. Filtering Scope

### 3.1 Repository Queries

实现位置：

```text
backend/app/collectors/data_source_repository.py
```

两个查询都支持 `include_keys`：

```text
due_scheduled_sources(db, include_keys=...)
scheduled_enabled_sources(db, include_keys=...)
```

当 `include_keys` 非空时，Repository 在 SQL 中追加：

```sql
AND key IN :include_keys
```

共同基础条件仍为：

```text
enabled = true
AND schedule_enabled = true
AND key != 'weibo_octopus'
```

### 3.2 Scheduler Dispatch

`backend/app/core/scheduler.py` 在调度任务中使用进程级 allowlist：

- cron 模式向 `scheduled_enabled_sources()` 传入 allowlist；
- per-source tick 模式向 `due_scheduled_sources()` 传入 allowlist；
- per-source claim 更新也追加同一 allowlist 条件；
- 组装 `CollectorService` 时使用实际过滤后的
  `include_data_source_keys`；
- scheduled dispatch 使用 `trigger_type="scheduled"`。

因此 allowlist 同时影响候选查询、claim 范围、Scheduler dispatch 和
CollectorService source include。

## 4. Current Database Observation

只读查询结果：

```text
xhs_mediacrawler:
id=45
enabled=true
schedule_enabled=false
schedule_interval_minutes=60
```

无 allowlist 时：

```text
scheduled candidate count=22
due candidate count=22
```

XHS 不在其中，因为当前 `schedule_enabled=false`。

## 5. Temporary Allowlist Verification

### 5.1 Simulated XHS Allowlist

临时进程环境：

```text
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

实际查询结果：

```text
scheduled candidate count=0
scheduled candidate keys=[]
due candidate count=0
due candidate keys=[]
```

这是当前 DataSource 状态的正确结果，而不是 allowlist 失效：allowlist
只能缩小候选范围，不能绕过 `schedule_enabled=false`。

本阶段禁止修改 DataSource，因此不能把 `id=45` 临时改成
`schedule_enabled=true` 来制造一个生产写入验证。

### 5.2 Enabled-Source Control

为验证 allowlist 的正向过滤语义，使用当前已开启调度的
`weibo_mediacrawler` 做只读控制：

```text
SCHEDULER_SOURCE_ALLOWLIST=weibo_mediacrawler
scheduled candidate count=1
scheduled candidate keys=["weibo_mediacrawler"]
due candidate count=1
due candidate keys=["weibo_mediacrawler"]
```

结果没有混入其他 21 个候选，证明 Repository 和 Scheduler 使用的
`include_keys` 过滤语义生效。

## 6. Live Process Risk

8000 backend 进程可通过命令行确认正在运行，`GET /health` 返回 HTTP 200。
但当前只读工具无法安全读取该 Windows 进程的完整环境变量，因此：

```text
live SCHEDULER_SOURCE_ALLOWLIST=UNKNOWN
```

不能根据当前 shell 的环境变量推断 8000 进程已经加载 allowlist。
需要在不启动 Scheduler 的前提下，由后续受控进程启动/服务审计确认：

```text
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

## 7. Single-Source Gray Readiness

代码契约满足以下条件：

```text
DataSource:
enabled=true
schedule_enabled=true

Process:
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

在这两个条件同时成立时，候选查询理论上只能返回：

```json
["xhs_mediacrawler"]
```

当前不能在生产数据库中得到该正向结果，因为本阶段禁止打开
`schedule_enabled`。这属于安全边界，不是代码缺口。

## 8. Conclusion

allowlist 机制已经存在且覆盖：

```text
scheduled_enabled_sources()
due_scheduled_sources()
Scheduler dispatch
CollectorService include_data_source_keys
```

不需要新增设计或修改业务代码。下一阶段应在人工批准后，以进程环境注入
allowlist，再执行 DataSource 开关变更和 Scheduler 单源灰度。

```text
READY_FOR_SCHEDULER_GRAY_APPROVAL
```
