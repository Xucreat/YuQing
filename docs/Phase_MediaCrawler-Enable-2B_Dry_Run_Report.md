# Phase MediaCrawler-Enable-2B Dry Run

## Approval

Approval recorded before execution:

```text
MediaCrawler real run approved
```

Pre-run state:

```text
DataSource.id=40
enabled=true
schedule_enabled=false
persisted MEDIA_CRAWLER_REAL_RUN_GATE=false
```

For this one-shot process only, the approved gate was supplied as a process
environment override (`MEDIA_CRAWLER_REAL_RUN_GATE=true`). It was not written
to deployment configuration. `schedule_enabled` was temporarily set to true,
then restored to false in a `finally` block.

## Execution

The source was temporarily visible to the scheduler eligibility and due
queries. The equivalent scheduler execution path was invoked once through:

```text
CollectorService(include_data_source_keys={"weibo_mediacrawler"})
  -> collect_and_analyze_concurrent(SessionLocal, trigger_type="scheduled")
```

Batch:

```text
8817beaccae9408ab1370de6e084bd42
```

No retry was performed after the failure.

## Scheduler Path

The source was discovered when temporarily enabled, then the path stopped at
collector command assembly:

```text
DataSource
 -> scheduled/due source query
 -> registry
 -> MediaCrawlerWeiboCollector
 -> CollectorService(trigger_type=scheduled)
 -> Runtime boundary
```

Registry constructed `MediaCrawlerWeiboCollector` without injecting
`MediaCrawlerRuntimeFactory`. The collector therefore fell back to a bare
`MediaCrawlerRunner()` with no command factory, producing:

```text
MediaCrawlerRunnerConfigurationError:
no MediaCrawler command configured; use fixture_path or an explicit mock command
```

This is a code integration blocker for a future phase. It was not fixed or
retried in this one-shot dry run.

## Runtime Observation

The deployment runtime itself was available:

```text
python=D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe
entry=C:\Users\Administrator\Desktop\YQ\backend\scripts\mediacrawler_standard_entry.py
root=D:\code files\mediaCrawler\MediaCrawler
profile=D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
login_policy=cookie
```

The failure occurred before the Runtime Factory command path was reached.

## Runner Result

```text
raw_count=0
output_count=0
effective_max_items=10
```

No external MediaCrawler process was called because command assembly failed
first.

## CollectorRun

```text
collector_name=微博（MediaCrawler）
batch_id=8817beaccae9408ab1370de6e084bd42
status=failed
trigger_type=scheduled
duration_seconds=0.063
fetched_raw=0
created=0
duplicate=0
admission_filtered=0
failed=1
```

## Opinion

No Opinion was created by this batch. A read-only query found no `source=weibo`
Opinion between this CollectorRun's start and end timestamps. Other sources
were running concurrently in the application and were excluded from this
batch assessment.

## Risk/Event

No new MediaCrawler Opinion was admitted, so no Risk or Event record was
generated for this batch. Existing records were not modified.

## Metrics

Path:

```text
D:\code files\mediaCrawler\MediaCrawler\runs\8817beaccae9408ab1370de6e084bd42\metrics.json
```

Content summary:

```json
{
  "batch_id": "8817beaccae9408ab1370de6e084bd42",
  "collector": "mediacrawler",
  "raw_count": 0,
  "output_count": 0,
  "effective_max_items": 10,
  "created": 0,
  "duplicate": 0,
  "admission_filtered": 0,
  "failed": 1
}
```

`metrics.json` exists; raw and output JSONL do not because the process never
started.

## Rollback

Rollback completed immediately after the attempt:

```text
DataSource.schedule_enabled=false
persisted MEDIA_CRAWLER_REAL_RUN_GATE=false
weibo_mediacrawler absent from scheduled/due lists after rollback
```

The failed CollectorRun, metrics, and crawler log were retained. No historical
batch was deleted.

## Test Result

```text
pytest tests/test_media_crawler*.py -q
101 passed, 1 warning in 6.63s
```

The warning is the existing Pydantic class-based-config deprecation warning.

## Final Status

**FAILED**

The scheduled trigger and DataSource discovery were exercised once, but the
run failed before command creation because registry does not inject the
MediaCrawler Runtime Factory into `MediaCrawlerWeiboCollector`. A future fix
must close that integration gap and undergo a new explicitly approved dry run.

Database: one failed `CollectorRun` and its normal audit artifacts were created; no Opinion was created by this batch.

Migration: NO CHANGE

Scheduler: Dry Run completed then source dispatch disabled

Real Crawl: scheduled attempt made once; external MediaCrawler process NOT CALLED
