# Phase MediaCrawler Platform-2-J2 Preflight

## 1. Status

```text
SCHEDULER_GRAY_BLOCKED
```

## 9. Validation Recap

本次只读验证后补充的回归结果：

- `backend/tests/test_media_crawler*.py`：`188 passed`
- `python -m compileall -q backend/app`：`PASS`
- `git diff --check`：未发现格式性 diff 问题

补充确认：

- 当前 8000 backend 进程仍在运行，未启动 Scheduler
- 未修改 `DataSource`
- 未修改 `.env`
- 未修改 `scheduler.py`
- 未修改模型或 migration

本次 J2 未执行 DataSource 变更，未启动新的 backend/Scheduler 进程，未执行
scheduled CollectorService，未启动 MediaCrawler，未修改生产配置。

阻塞原因：

1. XHS scheduler profile 尚未准备完成；
2. 当前 8000 进程是否加载
   `SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler` 无法通过安全只读方式确认。

## 2. DataSource State

只读数据库查询：

```text
id=45
key=xhs_mediacrawler
enabled=true
schedule_enabled=false
schedule_interval_minutes=60
```

当前 `config_json` 保持不变：

```json
{
  "collector": "mediacrawler",
  "platform": "xiaohongshu",
  "crawler_type": "search",
  "login_type": "qrcode",
  "keywords": ["大厂回族自治县"],
  "max_items": 20,
  "get_comment": false,
  "get_sub_comment": false,
  "collection_scope": "regional",
  "collection_mode": "regional"
}
```

本阶段没有修改 `config_json`、keywords、collector 或 platform。

## 3. Candidate Preflight

当前无 allowlist 的只读查询：

```text
all scheduled candidate count=22
xhs_mediacrawler in candidates=false
xhs_mediacrawler due=false
```

使用临时进程环境模拟：

```text
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

在当前数据库状态下：

```text
scheduled candidate count=0
due candidate count=0
```

原因是 allowlist 不绕过：

```text
enabled=true
AND schedule_enabled=true
```

而 XHS 当前 `schedule_enabled=false`。没有执行任何写库操作来伪造正向
candidate 结果。

## 4. Scheduler Process

当前 8000 backend：

```text
PID=24032
start_time=2026-08-06 18:56:45
health=HTTP 200
```

进程环境变量无法通过当前安全只读工具完整读取，因此以下值为：

```text
SCHEDULER_SOURCE_ALLOWLIST=UNKNOWN
```

不能把当前 shell 或 workspace 环境推断为 8000 进程已经加载 allowlist。

本阶段没有停止或重启该进程，也没有启动 Scheduler。

## 5. XHS Scheduler Profile

检查结果：

```text
application profile:
C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_mediacrawler\profiles\xiaohongshu\xhs_mediacrawler\manual
Exists=true
Files=0

scheduler profile:
C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_mediacrawler\profiles\xiaohongshu\xhs_mediacrawler\scheduler
Exists=false

legacy checkout XHS profile:
D:\code files\mediaCrawler\MediaCrawler\profiles\xiaohongshu\xhs_mediacrawler\manual
Exists=false
```

当前 runtime profile 尚未包含可供 scheduler 使用的持久登录状态。Scheduler
要求非交互式登录策略，不能在首次 scheduled run 中依赖二维码交互。

## 6. Required Changes Not Executed

按任务要求，只有预检通过且获得人工批准后，才允许执行：

```text
id=45:
schedule_enabled: false -> true
schedule_interval_minutes: 60 -> 120
```

本次没有执行上述变更。

启动新进程时还必须显式注入：

```text
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

并确认 runtime environment 至少包含：

```text
MEDIA_CRAWLER_ROOT=<dedicated output/runtime root>
MEDIA_CRAWLER_PROFILE_ROOT=<dedicated profile root>
MEDIA_CRAWLER_CHECKOUT_ROOT=D:\code files\mediaCrawler\MediaCrawler
MEDIA_CRAWLER_ENTRY=C:\Users\Administrator\Desktop\YQ\backend\scripts\mediacrawler_standard_entry.py
MEDIA_CRAWLER_PYTHON=D:\code files\mediaCrawler\MediaCrawler\.venv\Scripts\python.exe
MEDIA_CRAWLER_REAL_RUN_GATE=true
MEDIA_CRAWLER_SCHEDULER_LOGIN_TYPE=cookie
```

## 7. Protection Check

本阶段确认未修改：

- `backend/app/core/scheduler.py`
- `backend/app/models/`
- `backend/alembic/`
- `.env`
- 其他 DataSource
- MediaCrawler upstream checkout
- Opinion/CollectorRun schema
- 微博兼容链路

## 8. Decision

当前不满足首次单源灰度运行条件。必须先完成：

1. XHS 持久登录 profile provisioning；
2. 新 backend 进程显式加载
   `SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler`；
3. 在不启动 Scheduler 的情况下确认 allowlist 环境已被新进程继承；
4. 再重新执行 J2 preflight。

```text
SCHEDULER_GRAY_BLOCKED
```
