# Phase MediaCrawler-Enable-2D Scheduler Enable Report

Date: 2026-08-05  
Checkout: `C:\Users\Administrator\Desktop\YQ`  
Git commit: `b1b18a0267421c90ccf279aa1fc2ea3936766c35`

## 1. Enable-Before Snapshot

Owner fingerprint:

| Field | Value |
|---|---|
| current YQ scheduler executable | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| project root | `C:\Users\Administrator\Desktop\YQ` |
| git commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| advisory lock owner | PostgreSQL backend PID `24500` |
| gate | `false` |

The advisory-lock owner matched the current YQ Uvicorn process. No second
Scheduler, BettaFish process, or other checkout was started.

DataSource before enable:

```text
id=40
key=weibo_mediacrawler
enabled=true
schedule_enabled=false
```

The target was the only due source after enable; existing scheduled sources
were not due at the observed tick.

Profile snapshot:

[before snapshot](C:\Users\Administrator\Desktop\YQ\docs\Phase_MediaCrawler-Enable-2D-Scheduler_Enable_before_snapshot.json)

```text
template = D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
file_count = 549
directory_count = 163
root_mtime_ns = 1785919142691390300
tree_sha256 = ff8433ca99dcbb7049dd6f2ef10110fb4fd5fb6a069f647c2df4364cf0108ad2
```

## 2. Enable Action

The only configuration write was:

```text
data_sources.id=40.schedule_enabled: false -> true
```

No code, schema, migration, `config_json`, `.env`, gate, or profile template
was changed.

## 3. Scheduler Tick Result

The existing Scheduler owner claimed the target at approximately
`2026-08-05 17:15:02 +08:00`. The target `due` query changed from present to
absent and `last_collect_time`/`next_collect_time` were advanced, proving the
real scheduled tick path reached DataSource claim logic.

The scheduled collector then failed before RuntimeFactory could create a
batch-scoped runtime profile:

```text
CollectorRun.id=14043
batch_id=6a40d960b3594a3baa20cba2b1755293
collector_name=微博（MediaCrawler）
trigger_type=scheduled
status=failed
failed=1
error=TypeError: MediaCrawlerRuntimeFactory.create_runner()
       got an unexpected keyword argument 'batch_id'
```

This is a stale-process failure. The long-running Uvicorn/Scheduler process was
started at `15:45:55`, before the Fix-4 RuntimeFactory changes made at
`16:45:31`; it had not reloaded the current checkout.

No retry was issued. The failure occurred before runtime profile creation, so
the batch metrics path does not exist:

```text
D:\code files\mediaCrawler\MediaCrawler\runs\6a40d960b3594a3baa20cba2b1755293\metrics.json
```

## 4. Profile Isolation Verification

Post-failure snapshot:

[after snapshot](C:\Users\Administrator\Desktop\YQ\docs\Phase_MediaCrawler-Enable-2D-Scheduler_Enable_after_snapshot.json)

```text
file_count unchanged: true
directory_count unchanged: true
root mtime unchanged: true
tree SHA-256 unchanged: true
result: PASS
```

The persistent scheduler profile was not modified. No
`runtime_profiles/<batch_id>` directory was created because the stale process
failed before receiving the new `batch_id` argument.

## 5. Safety Rollback / Containment

Because the first scheduled tick failed, `schedule_enabled` was immediately
restored to false to prevent an automatic failure loop:

```text
id=40.enabled=true
id=40.schedule_enabled=false
weibo_mediacrawler in scheduled sources: false
weibo_mediacrawler in due sources: false
MEDIA_CRAWLER_REAL_RUN_GATE=false
```

The current Scheduler owner was not stopped. No permanent deployment setting was
changed.

## 6. Tests

Command:

```text
pytest tests/test_media_crawler*.py -q
```

Result:

```text
118 passed, 1 warning
```

## 7. Final Decision

`BLOCKED_NEEDS_FIX`

The failure is isolated to the stale long-running Scheduler process, not the
current Fix-4 checkout. The process must be replaced/reloaded through the
approved operational procedure before another enable attempt. Do not enable
`weibo_mediacrawler` again until the running Scheduler loads the current
RuntimeFactory contract and a new scheduled tick can create and clean a
batch-scoped runtime profile successfully.
