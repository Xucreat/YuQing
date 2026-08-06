# Phase MediaCrawler-Enable-2B-Retry-DryRun Report

## 1. Approval state

前置审计状态：

```text
Phase MediaCrawler-Enable-2B-Retry-PreAudit: PASS
```

本次仅执行一次受控 `trigger_type="scheduled"` dry run。未启动长期
Scheduler，未执行 migration，未修改 schema/profile/cookie/browser 数据。

## 2. Before state

执行前只读状态：

```text
DataSource id             = 40
DataSource key            = weibo_mediacrawler
enabled                   = true
schedule_enabled         = false
MEDIA_CRAWLER_REAL_RUN_GATE = false
MediaCrawler CollectorRun count = 9
Opinion max id            = 2396
```

Runtime 前置条件：

```text
entry exists              = true
scheduled profile exists  = true
scheduled login policy    = cookie
python executable exists  = true
```

## 3. Execution path

临时启用仅作用于本次执行：

```text
schedule_enabled = true
MEDIA_CRAWLER_REAL_RUN_GATE = true
```

DataSource discovery 确认 `weibo_mediacrawler` 同时进入：

```text
scheduled_enabled_sources
due_scheduled_sources
```

随后执行：

```text
CollectorService(
    include_data_source_keys={"weibo_mediacrawler"}
).collect_and_analyze(
    db,
    trigger_type="scheduled",
)
```

未调用 manual trigger，未启动 APScheduler。

## 4. Batch result

受控调用生成 batch：

```text
batch_id = 4537c05fb4a548eea639cddae3c12589
```

结果：

```text
fetched_raw = 0
created     = 0
duplicate   = 0
analyzed    = 0
failed      = 1
```

失败阶段：

**command build / Runner configuration**

错误：

```text
MediaCrawlerRunnerConfigurationError:
no MediaCrawler command configured;
use fixture_path or an explicit mock command
```

未进行自动 retry。

## 5. CollectorRun

受控 batch 对应记录：

```text
CollectorRun.id = 13974
status          = failed
trigger_type    = scheduled
start_time      = 2026-08-05 15:42:19.304059
end_time        = 2026-08-05 15:42:19.336578
duration        = 0.032519 seconds
error           = MediaCrawlerRunnerConfigurationError:
                  no MediaCrawler command configured;
                  use fixture_path or an explicit mock command
fetched_raw     = 0
created         = 0
duplicate       = 0
analyzed        = 0
failed          = 1
admission_filtered = 0
```

## 6. Metrics

Metrics 文件存在：

```text
D:\code files\mediaCrawler\MediaCrawler\runs\
4537c05fb4a548eea639cddae3c12589\metrics.json
```

内容摘要：

```json
{
  "batch_id": "4537c05fb4a548eea639cddae3c12589",
  "raw_count": 0,
  "output_count": 0,
  "effective_max_items": 10,
  "created": 0,
  "duplicate": 0,
  "admission_filtered": 0,
  "failed": 1
}
```

`raw/weibo.jsonl` 与 `output/weibo.jsonl` 不存在，因为 command 未成功解析/启动。

## 7. Opinion

本次受控 batch 未创建 Opinion：

```text
new Opinion count = 0
```

因此本次没有可验证的 `region_id=24` 全国 sentinel 记录。

## 8. Risk/Event

采集后的 Event 聚合调用返回：

```json
{
  "created": 0,
  "updated": 0,
  "linked": 0,
  "incremental": true
}
```

本次无新增 Opinion，因此无新增 Risk/Event 结果可验证。

## 环境并发说明

审计期间发现一个在本次任务开始前已存在的外部进程：

```text
C:\Users\Administrator\Desktop\weiyu\BettaFish\.venv\Scripts\python.exe app.py
started = 2026-08-03 15:40:02
```

该进程不是本次任务启动的 Scheduler。临时开启 `schedule_enabled` 期间，它另
产生了一个并发 scheduled batch：

```text
batch_id       = 1cf8ed6eb22e40f987100ee0ed0d668b
CollectorRun   = 13973
status         = success
fetched_raw    = 10
output_count   = 10
duplicate      = 6
admission_filtered = 4
created        = 0
```

该记录不计入本次受控 batch 结果，但说明环境存在外部调度并发，不能将本次
验证视为完全隔离的单进程生产 dry run。

## 9. Rollback verification

无论失败结果，均执行强制回滚：

```text
DataSource.schedule_enabled = false
MEDIA_CRAWLER_REAL_RUN_GATE = false
```

回滚后只读确认：

```text
DataSource.enabled          = true
DataSource.schedule_enabled = false
target in scheduled sources = false
target in due sources       = false
```

未删除历史失败记录，未回滚或修改 schema/DataSource enabled 状态。

## 10. Tests

执行 MediaCrawler 全量测试（Windows PowerShell 下显式展开文件列表，对应
`pytest tests/test_media_crawler*.py -q`）：

```text
107 passed, 1 warning in 7.06s
```

## 最终状态

**FAILED_NEEDS_FIX**

原因：本次受控 scheduled batch 在 Runner command configuration 阶段失败，
且执行期间存在未由本任务启动的外部调度进程。必须先定位该 command 注入/
运行时实例不一致问题并隔离外部 Scheduler，之后才能再次执行 Dry Run。
