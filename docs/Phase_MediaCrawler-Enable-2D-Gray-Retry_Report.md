# Phase MediaCrawler-Enable-2D-Gray-Retry Report

Date: 2026-08-05  
Final status: `READY_FOR_SCHEDULER_ENABLE_OBSERVATION`

## 1. Scheduler owner fingerprint

### Gray execution owner

| Field | Value |
|---|---|
| parent PID | `49740` |
| worker PID | `45244` |
| executable | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| command | `-m uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| project root | `C:\Users\Administrator\Desktop\YQ` |
| git commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\mediacrawler_runtime.py` |
| runtime_factory_available | `true` |
| advisory lock backend PID | `26620` |
| advisory lock backend start | `2026-08-05 18:01:30.907503 +08:00` |

Only the YQ owner held the lock. No BettaFish, second checkout, or unrelated
`app.py` Scheduler was found.

### Restored owner

After rollback, the same YQ checkout was restarted as the sole owner:

| Field | Value |
|---|---|
| parent PID | `44448` |
| worker PID | `40152` |
| advisory lock backend PID | `27128` |
| backend start | `2026-08-05 18:21:41.991326 +08:00` |
| `MEDIA_CRAWLER_REAL_RUN_GATE` | `false` |
| `SCHEDULER_SOURCE_ALLOWLIST` | unset |

## 2. Gray control fingerprint

The execution owner was launched with process-scoped variables only:

```text
SCHEDULER_SOURCE_ALLOWLIST=weibo_mediacrawler
MEDIA_CRAWLER_REAL_RUN_GATE=true
```

Effective gray fingerprint:

```text
source_allowlist=["weibo_mediacrawler"]
real_run_gate=true
runtime_factory_available=true
```

No `.env` or persistent deployment configuration was changed. The
`[SchedulerFingerprint]` application line was not redirected into the Uvicorn
log by the current logger setup; the process launch environment, owner
lifecycle, lock ownership, successful scheduled command, and source-isolation
results are the audit evidence for this run.

## 3. DataSource change

Before execution:

```text
id=40
key=weibo_mediacrawler
enabled=true
schedule_enabled=false
```

The only intentional database change was:

```text
schedule_enabled: false -> true
```

After the single scheduled tick, it was immediately restored:

```text
schedule_enabled: true -> false
```

`enabled`, `config_json`, keywords, interval, and all other DataSource rows
were not changed.

## 4. Execution timeline

| Time | Event |
|---|---|
| 17:58:54 | Precheck completed; target disabled and 22 other scheduled sources recorded |
| 18:01:25 | Gray owner started from current YQ checkout |
| 18:01:30 | Gray owner acquired advisory lock |
| 18:01 | Process-scoped allowlist and gate were injected |
| 18:02 | id=40 `schedule_enabled` enabled |
| 18:15:30.976102 | Scheduler natural due tick created the target CollectorRun |
| 18:15:59.733848 | MediaCrawler scheduled run completed successfully |
| 18:16 | id=40 `schedule_enabled` restored to false |
| 18:21:38 | Gate=false owner restarted |
| 18:21:41.991326 | Restored owner acquired advisory lock |

No manual CollectorService call, retry, or direct subprocess invocation was
used.

## 5. CollectorRun result

| Field | Value |
|---|---|
| CollectorRun.id | `14070` |
| collector_name | `微博（MediaCrawler）` |
| trigger_type | `scheduled` |
| batch_id | `bbbbd56d852b490b90492bb5fdb50b45` |
| status | `success` |
| start_time | `2026-08-05 18:15:30.976102` |
| end_time | `2026-08-05 18:15:59.733848` |
| duration | approximately `28.76s` |
| fetched_raw | `10` |
| failed | `0` |
| created | `0` |
| duplicate | `6` |
| admission_filtered | `4` |

The MediaCrawler run log records a real command with exit code `0`, normalized
JSONL output, and `raw_count=16`, `output_count=10`.

## 6. Metrics

Actual metrics file:

```text
D:\code files\mediaCrawler\MediaCrawler\runs\bbbbd56d852b490b90492bb5fdb50b45\metrics.json
```

```json
{
  "batch_id": "bbbbd56d852b490b90492bb5fdb50b45",
  "collector": "mediacrawler",
  "raw_count": 16,
  "output_count": 10,
  "created": 0,
  "duplicate": 6,
  "admission_filtered": 4,
  "failed": 0
}
```

## 7. Runtime profile lifecycle

The production deployment root resolved from the existing environment is:

```text
D:\code files\mediaCrawler\MediaCrawler
```

The scheduled RuntimeFactory contract used:

```text
template:
D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler

runtime:
D:\code files\mediaCrawler\MediaCrawler\runtime_profiles\bbbbd56d852b490b90492bb5fdb50b45
```

The runtime profile was batch-bound and was absent after successful cleanup:

```text
runtime_profiles/<batch_id> exists: false
```

The run log confirms a real MediaCrawler subprocess completed successfully;
the RuntimeFactory code path supplies the batch-scoped profile to the Runner
and the collector performs success cleanup.

## 8. Persistent profile integrity

Authoritative template:

```text
D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
```

The prior exact snapshot and post-run comparison show:

| Metric | Before baseline | After | Result |
|---|---:|---:|---|
| file_count | `549` | `549` | unchanged |
| directory_count | `163` | `163` | unchanged |
| root mtime ns | `1785919142691390300` | `1785919142691390300` | unchanged |
| file additions | `0` | `0` | unchanged |
| file removals | `0` | `0` | unchanged |
| file content/mtime changes | `0` | `0` | unchanged |

Profile integrity result: `PASS`.

The initial shell fallback snapshot in the precheck was corrected to the
resolved production root; the final comparison used the exact production
template snapshot and found zero differences.

## 9. Other-source isolation

There were 22 other `enabled=true AND schedule_enabled=true` sources before
the run. Their aggregate state fingerprint was:

```text
before: 74e14e9c3db319d3c869cdc3b97eb43e409800bb4511eccd3dc9fbd0e16ba916
after:  74e14e9c3db319d3c869cdc3b97eb43e409800bb4511eccd3dc9fbd0e16ba916
```

The execution window contained exactly one new scheduled CollectorRun:

```text
CollectorRun.id=14070
collector_name=微博（MediaCrawler）
```

No other source had a changed `next_collect_time` or `last_collect_time`, and
no other source CollectorRun was created by this tick.

## 10. Rollback verification

Final state:

```text
DataSource.id=40.schedule_enabled=false
MEDIA_CRAWLER_REAL_RUN_GATE=false
SCHEDULER_SOURCE_ALLOWLIST=unset
```

The restored single Scheduler owner is from the YQ checkout and holds the
advisory lock. No second Scheduler remains.

## 11. Safety confirmation

| Area | Result |
|---|---|
| Business code | unchanged during execution |
| Database schema/migration | no change |
| DataSource config_json | unchanged |
| Other DataSources | unchanged |
| `.env` | unchanged |
| Persistent scheduler profile | unchanged |
| Real MediaCrawler | called exactly once |
| Weibo interface | called by the approved single MediaCrawler run |
| Retry | not performed |
| Long-term enablement | not performed |

## Final decision

`READY_FOR_SCHEDULER_ENABLE_OBSERVATION`
