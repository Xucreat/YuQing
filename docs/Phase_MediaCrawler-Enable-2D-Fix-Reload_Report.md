# Phase MediaCrawler-Enable-2D-Fix-Reload Report

Date: 2026-08-05  
Final status: `READY_FOR_GRAY_RETRY`

## Scope

This phase only reloaded the long-lived Scheduler process from the current YQ
checkout and verified the runtime fingerprint. No production collection, Dry
Run, migration, or business configuration change was performed.

## 1. Old Scheduler owner stopped

The stale Scheduler/Uvicorn process tree was stopped before reload:

| PID | Role | Evidence |
|---:|---|---|
| 34256 | old Uvicorn parent | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe -m uvicorn ...` |
| 18676 | old Uvicorn worker | child of the old parent |

The old PostgreSQL advisory-lock backend owner (`24500`) disappeared after
shutdown. No process outside the target YQ checkout was stopped.

## 2. Advisory lock release and reacquisition

After the old process exited, the Scheduler advisory lock query returned no
owner. The Scheduler was then started once from the current checkout and
reacquired the lock.

Current lock evidence:

| Field | Value |
|---|---|
| advisory lock key | `4726074873081972718` |
| current PostgreSQL backend PID | `46696` |
| backend start | `2026-08-05 17:25:48.975602 +08:00` |
| client/state | `127.0.0.1` / `idle` |

The backend start time follows the new Uvicorn start time, linking the lock to
the reloaded Scheduler instance.

## 3. Reloaded Scheduler owner

| PID | Role | executable | command | started |
|---:|---|---|---|---|
| 48248 | Uvicorn parent | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` | `-m uvicorn app.main:app --host 0.0.0.0 --port 8000` | `2026-08-05 17:25:45 +08:00` |
| 24968 | Uvicorn worker | Workbuddy-hosted worker for the same command | same application command line | `2026-08-05 17:25:45 +08:00` |

The application log reported:

```text
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

Log files:

- `.diag/phase2d_fix_reload/scheduler_20260805_172545.out.log`
- `.diag/phase2d_fix_reload/scheduler_20260805_172545.err.log`

## 4. Scheduler fingerprint

The current-checkout fingerprint is:

| Field | Value |
|---|---|
| project root | `C:\Users\Administrator\Desktop\YQ` |
| git commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| Python executable | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\mediacrawler_runtime.py` |
| runtime_factory_available | `true` |

The in-process introspection used the current YQ virtual environment and
resolved the runtime factory module to the paths above. The Uvicorn log did
not emit a literal `[SchedulerFingerprint]` line, so this report relies on
process executable/working-directory evidence plus current-checkout module
introspection rather than claiming that text was present in the log.

## 5. RuntimeFactory `batch_id` verification

Current source introspection returned:

```text
(self, trigger_type: 'str' = 'manual', *,
 profile_path: 'str | Path | None' = None,
 batch_id: 'str | None' = None,
 mock_command: 'bool' = False)
 -> tuple[MediaCrawlerRunner, MediaCrawlerRunLock, MediaCrawlerRuntimeConfig]
```

Therefore `MediaCrawlerRuntimeFactory.create_runner(...)` supports the
Fix-4 batch-bound runtime profile contract without constructing a production
runner during this audit.

## 6. External Scheduler assessment

The read-only isolation script reported:

```text
owner_pid=46696
registry_runtime_factory=true
possible_other_scheduler=true
```

`possible_other_scheduler=true` is a conservative script flag meaning that an
advisory lock exists; the script does not identify every lock as external.
Owner mapping shows that the sole lock belongs to the freshly started YQ
Scheduler (backend start `17:25:48`, immediately after Uvicorn start
`17:25:45`). Process enumeration found only the current YQ Uvicorn parent and
worker, with no BettaFish process, second checkout, or unknown `app.py`
Scheduler.

Effective isolation result: **no external Scheduler detected**.

## 7. Data and safety checks

Read-only verification after reload:

| Item | Result |
|---|---|
| `DataSource.id=40` | `key=weibo_mediacrawler`, `enabled=true` |
| `schedule_enabled` | `false` |
| `MEDIA_CRAWLER_REAL_RUN_GATE` | `false` |
| `MEDIA_CRAWLER_ENABLE_REAL_RUN` | `false` |
| database/schema/migration | unchanged |
| real MediaCrawler | not called |
| Dry Run | not executed |
| scheduler enable | not performed |

No profile, cookie, browser template, DataSource, or gate state was modified.

## 8. Acceptance decision

All reload-specific acceptance checks pass:

- old owner stopped;
- advisory lock released and reacquired by the new owner;
- current Scheduler owner is from `C:\Users\Administrator\Desktop\YQ`;
- `runtime_factory_available=true`;
- `create_runner(batch_id=...)` is supported;
- no external Scheduler was found after owner mapping;
- no database or collection side effects occurred.

## Final status

`READY_FOR_GRAY_RETRY`

This phase does not authorize a Dry Run or long-term Scheduler enable. Any
subsequent gray retry remains a separate, explicitly approved operation.
