# Phase MediaCrawler-Enable-2B-Isolated-DryRun Report

Date: 2026-08-05  
Checkout: `C:\Users\Administrator\Desktop\YQ`  
Commit: `b1b18a0267421c90ccf279aa1fc2ea3936766c35`

## 1. Owner Fingerprint

The read-only isolation check and the one-shot execution process reported:

| Field | Value |
|---|---|
| pid (one-shot process) | `32908` |
| hostname | `KF-XHL` |
| python | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| project_root | `C:\Users\Administrator\Desktop\YQ` |
| git_commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| registry | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime_factory | `true` |
| trigger_type | `scheduled` |

The PostgreSQL advisory lock owner was backend PID `24500`. Its backend start time (`2026-08-05 15:46:02 +08:00`) aligned with the current YQ Uvicorn process start (`2026-08-05 15:45:55 +08:00`). No BettaFish `app.py` or other checkout scheduler process was present.

## 2. Isolation Result

Application-process isolation passed:

- current scheduler owner is associated with the YQ checkout;
- no external `app.py`/BettaFish scheduler was detected;
- the target source was not scheduled or due before the one-shot call;
- no long-lived Scheduler was started by this task.

The run was nevertheless not fully safety-clean: the configured Chromium scheduler profile was written by the real browser process during the crawl. Files observed with timestamps after the run began included `Default/Network/Cookies`, `History`, `Local State`, cache databases, and session/cache files. This violates the phase rule prohibiting profile/cookie/browser data modification.

## 3. Execution Timeline

| Time | Event |
|---|---|
| T0 `16:36` | Owner, process, DataSource, gate, and future `next_collect_time` prechecks passed. |
| T1 `16:38:35` | Process-local `MEDIA_CRAWLER_REAL_RUN_GATE=true`; only DataSource `id=40.schedule_enabled` temporarily set to `true`. |
| T2 `16:38:35` | Fresh DB registry resolve and `CollectorService.collect_and_analyze(db, trigger_type="scheduled")` invoked exactly once. |
| T3 `16:39:03` | MediaCrawler subprocess exited `0`; `CollectorRun.id=14018` committed as `success`. |
| T4 `16:39:03` | `schedule_enabled` restored to `false`; target absent from scheduled and due queries. |
| T5 `16:40` | MediaCrawler test suite completed: `112 passed, 1 warning`. |

No retry was issued.

## 4. Collector Result

| Field | Value |
|---|---|
| batch_id | `67b09e5df50642b3adad0b907c6ac3e3` |
| CollectorRun.id | `14018` |
| collector_name | `微博（MediaCrawler）` |
| trigger_type | `scheduled` |
| status | `success` |
| duration | `28.108647 s` |
| fetched_raw | `10` |
| raw_count (runner metrics) | `16` |
| output_count | `10` |
| created | `0` |
| duplicate | `6` |
| admission_filtered | `4` |
| analyzed | `0` |
| failed | `0` |

Metrics:

`D:\code files\mediaCrawler\MediaCrawler\runs\67b09e5df50642b3adad0b907c6ac3e3\metrics.json`

The metrics payload was:

```json
{
  "batch_id": "67b09e5df50642b3adad0b907c6ac3e3",
  "collector": "mediacrawler",
  "raw_count": 16,
  "output_count": 10,
  "created": 0,
  "duplicate": 6,
  "admission_filtered": 4,
  "failed": 0
}
```

Other artifacts:

- raw: `D:\code files\mediaCrawler\MediaCrawler\runs\67b09e5df50642b3adad0b907c6ac3e3\raw\weibo.jsonl`
- normalized output: `D:\code files\mediaCrawler\MediaCrawler\runs\67b09e5df50642b3adad0b907c6ac3e3\output\weibo.jsonl`
- crawler log: `D:\code files\mediaCrawler\MediaCrawler\runs\67b09e5df50642b3adad0b907c6ac3e3\crawler.log`

`created=0` is consistent with the recorded duplicate/admission-filter counts and is allowed by the phase criteria.

## 5. Runtime Chain Evidence

The scheduled path demonstrated:

```text
DataSource id=40
  -> resolve_collectors_verbose(real DB session)
  -> Registry._build_collector
  -> MediaCrawlerWeiboCollector(
       runtime_factory=MediaCrawlerRuntimeFactory,
       runner=None
     )
  -> _ensure_runtime("scheduled")
  -> MediaCrawlerRuntimeFactory.create_runner("scheduler")
  -> MediaCrawlerCommandBuilder.build(...)
  -> MediaCrawlerRunner(command_factory=<factory>, mock_command=False)
  -> subprocess (exit_code=0)
```

Observed assertions:

- `collector.runtime_factory`: `MediaCrawlerRuntimeFactory`
- `collector.runner` before execution: `None`
- `runner.command_factory` after runtime creation: present
- `runtime_config.real_run_gate`: `true` in the controlled process only
- native output discovered and normalized into `output/weibo.jsonl`

The previous `no MediaCrawler command configured` failure did not recur.

## 6. Rollback and Safety Confirmation

Post-run read-only verification:

- `DataSource.id=40.enabled=true`
- `DataSource.id=40.schedule_enabled=false`
- `weibo_mediacrawler` absent from scheduled sources
- `weibo_mediacrawler` absent from due sources
- `.env` was not edited
- `MEDIA_CRAWLER_REAL_RUN_GATE` is false in the normal process
- `MEDIA_CRAWLER_ENABLE_REAL_RUN` remains false
- no migration or schema change was executed
- no historical `CollectorRun` was deleted or altered
- no long-term Scheduler was started by this task

Fixed safety summary:

```text
Database:
NO SCHEMA/CONFIG CHANGE; expected one-shot CollectorRun audit row only

Migration:
NO CHANGE

DataSource:
restored

Scheduler:
disabled after run

Gate:
false after rollback

Real Crawl:
CALLED ONCE
```

## 7. Tests

Command:

```text
pytest tests/test_media_crawler*.py -q
```

Result:

```text
112 passed, 1 warning
```

## 8. Final Decision

`BLOCKED_BY_ENVIRONMENT`

The RuntimeFactory/CommandBuilder/Runner chain and scheduled execution are healthy, and the one-shot run succeeded. Acceptance is blocked because the real browser process modified the configured scheduler profile (including browser cache/history/cookie-related files), contrary to the strict “do not modify profile/cookie/browser data” requirement.

Before Phase 2C, use a disposable or copy-on-write scheduler browser profile and repeat the same isolated procedure. Do not enable a long-term Scheduler until that profile-isolation control is in place.
