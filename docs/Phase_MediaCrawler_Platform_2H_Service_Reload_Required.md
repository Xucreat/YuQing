# Phase MediaCrawler Platform-2-H Service Reload Required

## Status

`SERVICE_RESTART_REQUIRED`

## Reason

当前 8000 端口 backend 进程没有加载当前工作区中已经支持 XHS 评论开关字段的 Admin API contract。

## Evidence

### Running process

```text
PID: 13156
command:
"C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe"
-m uvicorn app.main:app --host 0.0.0.0 --port 8000
start time: 2026-08-06 16:43:07
```

### Current source

```text
HEAD: 793e61d0b32d1ed8a2458fe6658fd077af41bc05

backend/app/api/admin_data_sources.py modified:
2026-08-06 16:51:54

backend/app/collectors/registry.py modified:
2026-08-06 17:10:22

backend/app/collectors/media_crawler_platform_collector.py modified:
2026-08-06 17:10:22
```

工作区本身是 dirty，不能仅通过 HEAD 判断运行进程是否等于当前代码；但进程启动早于上述关键文件修改，足以构成 reload-required 证据。

### API mismatch

当前源码期望：

```text
POST duplicate xhs_mediacrawler:
configuration accepted, then 409 key exists

PATCH id=45 with get_comment="yes":
boolean validation error
```

live 8000 实际返回：

```text
POST /api/admin/data-sources
HTTP 422
{"detail":"MediaCrawler config contains unsupported keys: get_comment, get_sub_comment"}

PATCH /api/admin/data-sources/45
HTTP 422
{"detail":"MediaCrawler config contains unsupported keys: get_comment"}
```

这说明 live process 仍使用旧版 MediaCrawler config allowlist。

## Required Action

等待人工确认后，仅重启 backend application，使其加载当前工作区代码。

允许：

- 重启 backend application；
- 重启后验证 `GET /health`；
- 验证 `GET /api/admin/data-sources`；
- 使用不落库/可控错误请求复验 POST/PATCH contract。

禁止：

- 修改 `backend/app/core/scheduler.py`；
- 修改 `.env`；
- 修改数据库、DataSource 或 migration；
- 开启 `schedule_enabled`；
- 启动 Scheduler；
- 执行真实 MediaCrawler；
- 修改微博链路或 upstream checkout。

## Restart Safety Note

应用 lifespan 会调用 `start_scheduler()`。因此未经人工确认不得直接重启，避免旧/新 Scheduler 实例加载后产生意外自动采集。重启前应继续保持：

```text
xhs_mediacrawler.enabled=true
xhs_mediacrawler.schedule_enabled=false
```

## Current State

```text
BLOCKED_ON_HUMAN_RESTART_CONFIRMATION
```

