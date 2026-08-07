# Phase MediaCrawler Platform-2-J1 Allowlist Verification Report

## 1. Allowlist Code Location

```text
backend/app/core/scheduler.py
```

读取函数：

```text
_configured_source_allowlist()
```

环境变量：

```text
SCHEDULER_SOURCE_ALLOWLIST
```

读取只发生在 Scheduler 进程上下文，不写入 DataSource 或数据库。

## 2. Filtering Locations

```text
backend/app/collectors/data_source_repository.py
```

过滤入口：

```text
scheduled_enabled_sources(db, include_keys=...)
due_scheduled_sources(db, include_keys=...)
```

Scheduler 负责将 process-scoped allowlist 传入这两个查询，并将过滤后的
keys 传给：

```text
CollectorService(include_data_source_keys=...)
```

per-source tick 的 claim SQL 也使用同一 allowlist。

## 3. Candidate Results

### No Allowlist

```text
candidate count=22
```

其中包括：

```text
weibo_mediacrawler
```

但不包括 XHS，因为：

```text
xhs_mediacrawler.schedule_enabled=false
```

### Simulated XHS Allowlist

```text
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

当前生产状态下查询结果：

```text
scheduled candidate count=0
due candidate count=0
```

原因是 allowlist 不会绕过 DataSource 的 `schedule_enabled` 条件。

### Control Verification

```text
SCHEDULER_SOURCE_ALLOWLIST=weibo_mediacrawler
```

查询结果：

```text
scheduled candidate count=1
scheduled candidate keys=["weibo_mediacrawler"]
due candidate count=1
due candidate keys=["weibo_mediacrawler"]
```

该控制验证证明 allowlist 不会产生 `22 + xhs`，而是将候选限制为指定 key。

## 4. Live Process Status

```text
GET /health -> HTTP 200
```

8000 backend 的完整进程环境变量当前无法通过安全只读方式读取，因此：

```text
SCHEDULER_SOURCE_ALLOWLIST=UNKNOWN
```

不能确认正在运行的 8000 进程已经加载 allowlist。

## 5. Single-Source Condition

代码层面满足单源灰度所需的过滤契约。要得到预期：

```json
["xhs_mediacrawler"]
```

必须同时具备：

```text
DataSource.id=45:
enabled=true
schedule_enabled=true

Scheduler process:
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

本阶段未修改前者，也未启动后者，因此没有执行真实 Scheduler 验证。

## 6. Safety Confirmation

本阶段确认：

- 未开启 XHS `schedule_enabled`；
- 未启动 Scheduler；
- 未执行真实采集；
- 未修改生产 DataSource；
- 未修改 `.env`；
- 未修改 `scheduler.py`；
- 未修改 Repository 查询逻辑；
- 未修改 CollectorService；
- 未修改模型或 migration；
- 未修改 upstream MediaCrawler。

## 7. Next Step

下一阶段必须先获得人工批准，再执行：

1. 以进程环境注入：
   ```text
   SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
   ```
2. 只修改 DataSource `id=45` 的调度开关和间隔；
3. 启动受控 Scheduler；
4. 首次 tick 前确认 candidate 只有 XHS；
5. 进入 24 小时灰度观察。

```text
READY_FOR_SCHEDULER_GRAY_APPROVAL
```
