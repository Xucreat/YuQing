# Phase MediaCrawler-Enable-2B-Retry-PreAudit

## 审计结论

本次 Retry 前审计全部通过，未修改代码、数据库、DataSource、Scheduler、
gate 或 profile/cookie/browser 数据。

最终状态：

**READY_FOR_ENABLE_2B_DRY_RUN**

## Previous blocker verification

历史失败 batch `8817beaccae9408ab1370de6e084bd42` 仍存在，且为既有记录：

```text
CollectorRun.id       = 13838
collector_name        = 微博（MediaCrawler）
trigger_type          = scheduled
status                = failed
error_msg             = MediaCrawlerRunnerConfigurationError:
                         no MediaCrawler command configured
```

该记录未被修改。本次审计未创建新的 CollectorRun。

代码层已确认原 blocker 已修复：生产 collector 缺少 RuntimeFactory 时会明确抛出
`MediaCrawlerRuntimeError("MediaCrawler runtime factory missing")`，不再静默创建
裸 `MediaCrawlerRunner()`。

## Registry injection result

只读调用：

```text
resolve_collectors_verbose(
    db,
    include_data_source_keys={"weibo_mediacrawler"},
)
```

结果：

```text
failures              = []
collector              = MediaCrawlerWeiboCollector
collector.runtime_factory = MediaCrawlerRuntimeFactory
collector.runner       = None before trigger-specific runtime creation
```

验证通过：

```text
Scheduler
  -> CollectorService(trigger_type="scheduled")
  -> Registry
  -> MediaCrawlerRuntimeFactory
  -> MediaCrawlerWeiboCollector
```

registry 不再直接构造无 command factory 的 MediaCrawlerRunner。

## RuntimeFactory result

只读调用 `MediaCrawlerRuntimeFactory.config()` 与 `create_runner()` 完成
runtime 对象构造；未执行 command、未启动进程。Manual 与 Scheduler runner
均存在 callable `command_factory`。

### Manual

```text
trigger_type  = manual
python        = D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe
entry         = C:\Users\Administrator\Desktop\YQ\backend\scripts\mediacrawler_standard_entry.py
profile       = D:\code files\mediaCrawler\MediaCrawler\profiles\manual
login_type    = qrcode
real_run_gate = false
```

### Scheduler

```text
trigger_type  = scheduler
python        = D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe
entry         = C:\Users\Administrator\Desktop\YQ\backend\scripts\mediacrawler_standard_entry.py
profile       = D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
login_type    = cookie
real_run_gate = false
```

`profiles/manual` 与 `profiles/scheduler` 路径不同，Scheduler 使用非交互式
cookie login policy，trigger isolation 验证通过。

## Command build result

使用 `MediaCrawlerCommandBuilder.build()` 进行 dry inspection：

```text
command_is_list          = true
command_prefix           = [python_executable, entry]
command_contains_shell_flag = false
subprocess               = not called
```

Runner 的 `subprocess.run(...)` 调用未传入 `shell=True`；底层
`subprocess.Popen` 的 `shell` 默认值为 `False`。本次未执行 Runner。

## Gate status

```text
MEDIA_CRAWLER_REAL_RUN_GATE=false
```

未修改 gate。

## Scheduler status

```text
Scheduler instance       = None (not started)
DataSource.enabled       = true
DataSource.schedule_enabled = false
```

`weibo_mediacrawler` 不在只读查询结果 `scheduled_enabled_sources` 中；
`due_scheduled_sources` 当前为空。

本次未启动 Scheduler，未修改 Scheduler eligibility 或调度状态。

## Database status

只读确认 DataSource：

```text
id=40
key=weibo_mediacrawler
enabled=true
schedule_enabled=false
```

只读确认指定历史 CollectorRun batch 仍存在；未插入、更新或删除任何
CollectorRun。

Migration：**NOT EXECUTED**

## Test result

执行 MediaCrawler 全量测试（Windows PowerShell 下显式展开文件列表，对应
`pytest tests/test_media_crawler*.py -q`）：

```text
107 passed, 1 warning in 6.86s
```

## Safety boundary confirmation

- 未修改代码。
- 未修改数据库或 DataSource。
- 未修改 `schedule_enabled`。
- 未修改 `MEDIA_CRAWLER_REAL_RUN_GATE`。
- 未启动 Scheduler。
- 未调用真实 MediaCrawler。
- 未执行 migration。
- 未修改 profile/cookie/browser 数据。
