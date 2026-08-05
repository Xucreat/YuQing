# Phase MediaCrawler-2E-Fix Implementation Report

## Modified Files

- `backend/app/collectors/mediacrawler_runtime.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/app/collectors/media_crawler_weibo_collector.py`
- `backend/app/collectors/service.py`
- `backend/app/core/config.py`
- `backend/scripts/run_mediacrawler_real_verify.py`
- `backend/tests/test_media_crawler_2e_fix.py`
- `backend/tests/test_weibo_schedule.py` (mock compatibility only)

## Runtime Factory

`MediaCrawlerRuntimeFactory` is the single deployment-runtime seam for manual and scheduler execution. It reads Python executable, MediaCrawler entry, runtime root, timeout, login policy, and profile root from deployment settings. DataSource business JSON is never used for executable paths, profiles, cookies, tokens, or browser data.

The factory selects `runtime/mediacrawler/profiles/manual/` or `runtime/mediacrawler/profiles/scheduler/` by trigger type and fails closed when scheduler configuration requests an interactive login mode.

## Command Builder

Both trigger paths use the existing `MediaCrawlerCommandBuilder` through a Runner `command_factory`. The command is assembled after the isolated batch output directory exists, with `shell=False`; Scheduler does not hard-code a command and DataSource does not store one.

## Profile Isolation

Manual and scheduler runs receive distinct profile directories. Profile paths are passed as deployment runtime environment to the Runner and are never written to DataSource config or logs. Missing profiles fail closed as a MediaCrawler runtime failure; QR/interactive login is rejected for scheduler runs.

## Lock Mechanism

`MediaCrawlerRunLock` uses an OS file lock (`msvcrt` on Windows and `fcntl` on POSIX) under `runtime/mediacrawler/locks/weibo_mediacrawler.lock`. It is cross-process, released in `finally`/context-manager cleanup, and therefore does not leave a permanent lock after process exit. The source-wide lock intentionally serializes manual and scheduler executions even though their profiles are isolated.

## Scheduler Injection Chain

`Scheduler -> CollectorService(trigger_type=scheduled) -> registry -> MediaCrawlerWeiboCollector -> MediaCrawlerRuntimeFactory -> MediaCrawlerCommandBuilder -> MediaCrawlerRunner`.

Scheduler eligibility was not changed: only `enabled=true AND schedule_enabled=true` is eligible. The registered `weibo_mediacrawler` source remains disabled for scheduling, and no Scheduler was started.

## Failure Semantics Validation

Existing Runner exceptions remain authoritative:

- missing command/runtime configuration: failed path;
- non-zero process exit: failed path;
- timeout: failed path;
- raw records with empty bounded output: `MediaCrawlerEmptyOutputError` and `metrics.failed=1`;
- lock conflict: `MediaCrawlerLockTimeoutError`, with the current batch metrics marked failed.

CollectorService continues to persist `CollectorRun.status=failed` through its existing exception handler and updates MediaCrawler metrics best-effort without changing other collectors.

## Tests

MediaCrawler suite (`tests/test_media_crawler*.py`): **90 passed, 1 warning**.

Scheduler mock regression (`tests/test_weibo_schedule.py -k "not registry_source_filtering"`): **4 passed, 1 deselected, 1 warning**. The deselected legacy test performs database writes; it was not run under the no-write boundary. The broad `pytest tests -k scheduler -q` command was stopped after it stalled in an unrelated database integration setup and produced no assertion result.

## Database

NO CHANGE. No DataSource row was inserted or updated. No Opinion or CollectorRun was created by this implementation or its tests.

## Migration

NO CHANGE. No Alembic command was executed and no schema/model table was changed.

## DataSource

NOT REGISTERED or modified. Existing `weibo_mediacrawler` settings remain unchanged, including `schedule_enabled=false`.

## Scheduler

Disabled. Eligibility logic and scheduler configuration were not modified.

## Real Crawl

NOT CALLED. No real MediaCrawler process, browser profile, login flow, or external repository was invoked.

## Final Status

Phase MediaCrawler-2E-Fix-Implementation: PASS

READY_FOR_2F
