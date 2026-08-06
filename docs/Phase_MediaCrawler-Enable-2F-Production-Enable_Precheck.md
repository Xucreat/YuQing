# Phase MediaCrawler-Enable-2F-Production-Enable Precheck

Date: 2026-08-06  
Precheck completed: `2026-08-06T09:15:43+08:00`  
Operator clarification received: `2026-08-06`  
Precheck result: `READY_FOR_PRODUCTION_RELOAD`

This document is read-only evidence for the requested production enablement.
No process was stopped or started, no advisory lock was acquired or released,
no DataSource was updated, no CollectorService was called, and no MediaCrawler
process was executed.

## Reconciled Precheck Findings

The operator confirmed that the following two changes were intentional
production preparation actions:

   ```text
   DataSource.id=40.schedule_enabled=true
   config_json.max_items=20
   ```

These values are accepted as the current production target state. Since
`schedule_enabled` is already `true`, this phase will not repeat the
`false -> true` database write. The production enablement action is therefore
an idempotent confirmation of the already-enabled state, followed by the
required Scheduler reload and observation.

   ```text
   authorized database write in this phase: none
   ```

No rollback or corrective database write was performed.

## 1. Scheduler Owner

Current application process tree:

| PID | Role | Executable | Command | Started |
|---:|---|---|---|---|
| 45452 | YQ Uvicorn owner | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` | `-m uvicorn app.main:app --host 0.0.0.0 --port 8000` | 2026-08-05 19:25:25 |
| 43388 | same Uvicorn child | `C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe` | same YQ Uvicorn command line | 2026-08-05 19:25:25 |

PostgreSQL advisory lock:

| Field | Value |
|---|---|
| lock key | `4726074873081972718` |
| lock backend PID | `23664` |
| backend start | `2026-08-05 19:25:29.407959+08:00` |
| client address | `127.0.0.1` |
| state | `idle` |

The lock backend belongs to the current YQ Uvicorn lifecycle. Process
inspection found no second Uvicorn Scheduler, no BettaFish `app.py` Scheduler,
and no Python Scheduler from another checkout.

Owner fingerprint from the current YQ checkout:

| Field | Value |
|---|---|
| project root | `C:\Users\Administrator\Desktop\YQ` |
| git commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| Python executable | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\mediacrawler_runtime.py` |
| runtime_factory_available | `true` |

## 2. RuntimeFactory Contract

The current code supports the required scheduled batch contract without
calling it:

```text
MediaCrawlerRuntimeFactory.create_runner(
    trigger_type="scheduled",
    batch_id=<id>
)
```

Inspected signature:

```text
(self, trigger_type: 'str' = 'manual', *,
 profile_path: 'str | Path | None' = None,
 batch_id: 'str | None' = None,
 mock_command: 'bool' = False)
 -> tuple[MediaCrawlerRunner, MediaCrawlerRunLock, MediaCrawlerRuntimeConfig]
```

`batch_id` is present as a keyword-only parameter. No runner was created during
this precheck, so no runtime profile was created.

## 3. Gate and Allowlist

The deployment `.env` was read only. Its SHA-256 was:

```text
6363D37FA7F608ACCE510B57120669AD26286EB457454FA0F4F5A2BB7A08A135
```

| Setting | Actual precheck value | Production requirement |
|---|---|---|
| `MEDIA_CRAWLER_REAL_RUN_GATE` | `false` | `true` after same-owner reload |
| `MEDIA_CRAWLER_ENABLE_REAL_RUN` | `false` | unchanged; `.env` must not be edited |
| `SCHEDULER_SOURCE_ALLOWLIST` | unset in deployment configuration | unset |

The current owner was last deliberately restored with the process-scoped gate
`false` after Phase 2E. The current `.env` also has gate `false`; no `.env`
change is authorized. A same-owner reload with process-scoped gate `true`
would be required only after the DataSource/config drift is reconciled.

## 4. Actual DataSource State

Read from PostgreSQL at `2026-08-06 09:15:07 +08:00`:

| Field | Actual value |
|---|---|
| id | `40` |
| key | `weibo_mediacrawler` |
| name | `微博（MediaCrawler）` |
| enabled | `true` |
| schedule_enabled | `true` |
| next_collect_time | `2026-08-06 10:05:54.162248` |
| last_collect_time | `2026-08-05 19:15:39.480570` |
| schedule_interval_minutes | `60` |
| class_path | `app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector` |
| config_json | `{"collector":"mediacrawler","platform":"weibo","keywords":["大厂县"],"max_items":20,"collection_scope":"national"}` |
| config_json SHA-256 | `0f1530ad911de6ed672f2b75546744eed625ec3c103d97ee33119876d811a7c2` |

Other enabled scheduled sources: `22`.

No DataSource row was modified by this precheck.

## 5. Recent Target Runs

Recent target history was read only:

| id | batch_id | trigger_type | status | fetched_raw | created | duplicate | admission_filtered | failed |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 14115 | `f05aaf2df7d442689152747bbaee23d0` | scheduled | success | 10 | 0 | 6 | 4 | 0 |
| 14070 | `bbbbd56d852b490b90492bb5fdb50b45` | scheduled | success | 10 | 0 | 6 | 4 | 0 |
| 14043 | `6a40d960b3594a3baa20cba2b1755293` | scheduled | failed | 0 | 0 | 0 | 0 | 1 |

Historical failed runs were not modified or deleted. They are not treated as
new failures from this precheck.

## 6. Browser Profile Baseline

Authoritative production template:

```text
D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
```

| Metric | Baseline |
|---|---:|
| file_count | `549` |
| directory_count | `163` |
| root mtime ns | `1785919142691390300` |
| root mtime UTC | `2026-08-05T08:39:02.691390+00:00` |
| aggregate SHA-256 | `f8f24930a08a0fc2aa6e6dfdbdd7d8ee338fc9a91ad86eff2c18668add4ddd6c` |
| runtime profile directories currently present | `0` |

The aggregate hash uses sorted relative path, file size, file mtime
nanoseconds, and file-content SHA-256. The same algorithm must be used for
any later production comparison.

## 7. Safety Confirmation

| Area | Result |
|---|---|
| business code | no change |
| database schema | no change |
| migration | not run |
| `.env` | no change |
| Scheduler owner | not stopped or started |
| advisory lock | not acquired or released |
| DataSource 40 | no change |
| other DataSources | no change |
| CollectorService | not called |
| MediaCrawler | not executed |
| historical CollectorRuns | no deletion or update |
| historical Opinions | no deletion or update |

## Decision

`READY_FOR_PRODUCTION_RELOAD`

Phase 2F may continue with:

1. Same-owner Scheduler reload with process-scoped
   `MEDIA_CRAWLER_REAL_RUN_GATE=true`.
2. `SCHEDULER_SOURCE_ALLOWLIST` unset.
3. No repeat DataSource write.
4. Real Scheduler-path observation using the approved `max_items=20`
   configuration.

No production reload had been performed at the time of this precheck.
