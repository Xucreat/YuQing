# Phase MediaCrawler-Enable-2B-Final-Isolated-DryRun Report

Date: 2026-08-05  
Checkout: `C:\Users\Administrator\Desktop\YQ`  
Git commit: `b1b18a0267421c90ccf279aa1fc2ea3936766c35`

## 1. Owner Fingerprint

| Field | Value |
|---|---|
| one-shot pid | `17116` |
| python executable | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| project root | `C:\Users\Administrator\Desktop\YQ` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime_factory_available | `true` |
| advisory lock owner | PostgreSQL backend PID `24500` |

The advisory-lock backend start (`2026-08-05 15:46:02 +08:00`) matches the
current YQ Uvicorn start (`2026-08-05 15:45:55 +08:00`). Process inspection
found no BettaFish, second checkout, unknown `app.py`, or other scheduler.

`check_scheduler_isolation.py` printed `possible_other_scheduler=true` because
its current implementation treats any existing advisory lock as a warning. The
owner mapping above establishes the effective isolation result as:

```text
possible_other_scheduler=false
```

No process was stopped and no lock was acquired or released.

## 2. Precheck

### DataSource and gate

```text
id=40
key=weibo_mediacrawler
enabled=true
schedule_enabled=false
scheduled sources: absent
due sources: absent
MEDIA_CRAWLER_REAL_RUN_GATE=false (normal process)
MEDIA_CRAWLER_ENABLE_REAL_RUN=false
```

The source `next_collect_time` was already past due while
`schedule_enabled=false`. To prevent the already-running YQ scheduler from
claiming the source concurrently, this controlled call left
`schedule_enabled=false` and invoked only the explicitly requested one-shot
`CollectorService(..., trigger_type="scheduled")` path.

### Persistent profile snapshot

Template:

`D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler`

Before snapshot:

[before_profile_snapshot.json](C:\Users\Administrator\Desktop\YQ\docs\Phase_MediaCrawler-Enable-2B-Final-Isolated-DryRun_before_profile_snapshot.json)

```text
file_count=549
directory_count=163
root_mtime_ns=1785919142691390300
profile_tree_sha256=ff8433ca99dcbb7049dd6f2ef10110fb4fd5fb6a069f647c2df4364cf0108ad2
```

## 3. Execution Timeline

| Time | Event |
|---|---|
| T0 `16:55` | Owner/process/lock, DataSource, gate, and template prechecks passed. |
| T1 `16:57:26` | Process-local `MEDIA_CRAWLER_REAL_RUN_GATE=true`; no persistent config changed. |
| T2 `16:57:26` | Single scheduled `CollectorService` call started. |
| T3 `16:57:26` | Batch-scoped runtime profile created. |
| T4 `16:57:55` | MediaCrawler exited `0`; JSONL normalized; runtime profile observed before cleanup. |
| T5 `16:57:55` | `CollectorRun.id=14024` committed as `success`. |
| T6 `16:57:55` | Runtime profile removed; DataSource/gate rollback verification passed. |

No retry was executed. No long-term Scheduler was started.

## 4. CollectorRun Result

| Field | Value |
|---|---|
| batch_id | `c4998f2792ea4a05b709c6a8936f41c2` |
| CollectorRun.id | `14024` |
| collector_name | `微博（MediaCrawler）` |
| trigger_type | `scheduled` |
| status | `success` |
| start_time | `2026-08-05 16:57:26.878294` |
| end_time | `2026-08-05 16:57:55.164986` |
| duration | `28.286692 s` |
| fetched_raw | `10` |
| created | `0` |
| duplicate | `6` |
| admission_filtered | `4` |
| failed | `0` |

Metrics:

`D:\code files\mediaCrawler\MediaCrawler\runs\c4998f2792ea4a05b709c6a8936f41c2\metrics.json`

```json
{
  "batch_id": "c4998f2792ea4a05b709c6a8936f41c2",
  "raw_count": 16,
  "output_count": 10,
  "created": 0,
  "duplicate": 6,
  "admission_filtered": 4,
  "failed": 0
}
```

## 5. RuntimeFactory Chain Evidence

```text
DataSource discovery
  -> Registry.resolve_collectors_verbose(real DB session)
  -> MediaCrawlerWeiboCollector
  -> runtime_factory = MediaCrawlerRuntimeFactory
  -> runner initially None
  -> create_runner("scheduler", batch_id)
  -> BrowserProfileIsolationManager
  -> MediaCrawlerCommandBuilder
  -> MediaCrawlerRunner(command_factory=...)
  -> real MediaCrawler subprocess exit_code=0
  -> JSONL normalize
  -> CollectorRun success
```

Observed:

- resolved collector: `MediaCrawlerWeiboCollector`
- runtime factory: `MediaCrawlerRuntimeFactory`
- runner before runtime creation: `None`
- runner command: `mediacrawler_standard_entry.py ... --lt cookie ...`
- runner browser/profile environment:
  `D:\code files\mediaCrawler\MediaCrawler\runtime_profiles\c4998f2792ea4a05b709c6a8936f41c2`

## 6. Runtime Profile Evidence

Template profile:

`D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler`

Disposable runtime profile:

`D:\code files\mediaCrawler\MediaCrawler\runtime_profiles\c4998f2792ea4a05b709c6a8936f41c2`

The runtime profile existed immediately before successful cleanup. Both
`MEDIA_CRAWLER_PROFILE_NAME` and `MEDIA_CRAWLER_BROWSER_DATA` pointed to the
runtime profile, never to `profiles/scheduler`.

After cleanup:

```text
runtime_profiles/c4998f2792ea4a05b709c6a8936f41c2: NOT EXISTS
```

## 7. Profile Integrity Comparison

After snapshot:

[after_profile_snapshot.json](C:\Users\Administrator\Desktop\YQ\docs\Phase_MediaCrawler-Enable-2B-Final-Isolated-DryRun_after_profile_snapshot.json)

| Check | Before | After | Result |
|---|---:|---:|---|
| file count | 549 | 549 | PASS |
| directory count | 163 | 163 | PASS |
| root mtime_ns | 1785919142691390300 | 1785919142691390300 | PASS |
| profile tree SHA-256 | `ff8433ca99dcbb7049dd6f2ef10110fb4fd5fb6a069f647c2df4364cf0108ad2` | `ff8433ca99dcbb7049dd6f2ef10110fb4fd5fb6a069f647c2df4364cf0108ad2` | PASS |
| per-file SHA-256/mtime | unchanged | unchanged | PASS |

## 8. Rollback Verification

```text
schedule_enabled=false
MEDIA_CRAWLER_REAL_RUN_GATE=false after process exit
weibo_mediacrawler NOT IN scheduled sources
weibo_mediacrawler NOT IN due sources
runtime profile removed after success
```

No `.env`, deployment setting, schema, migration, historical CollectorRun, or
browser template was modified.

## 9. Test Result

Command:

```text
pytest tests/test_media_crawler*.py -q
```

Result:

```text
118 passed, 1 warning
```

## 10. Final Decision

`READY_FOR_SCHEDULER_ENABLE_APPROVAL`

The final isolated scheduled run succeeded, the disposable profile was used and
removed, and `profiles/scheduler` passed exact file-count, directory-count,
mtime, and hash comparison. Do not enable a long-term Scheduler in this phase;
the result is approval for the next scheduler enablement decision only.
