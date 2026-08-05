# Phase MediaCrawler-2F-Fix Implementation Report

## Modified Files

- `backend/app/collectors/mediacrawler_profile.py`
- `backend/app/collectors/mediacrawler_batch.py`
- `backend/app/collectors/mediacrawler_runtime.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/app/core/config.py`
- `backend/tests/test_media_crawler_2e_fix.py`
- `backend/tests/test_media_crawler_2f_fix.py`

No Scheduler, DataSource, Opinion, CollectorRun, Event, Risk, migration, or external MediaCrawler repository files were changed.

## Profile Management Design

`MediaCrawlerProfileManager` is a read-only resolver/checker. It maps:

```text
manual    -> <runtime_root>/profiles/manual
scheduler -> <runtime_root>/profiles/scheduler
```

It exposes `check()`, `readiness()`, and `require()`; it never creates directories, copies browser data, copies cookies, migrates sessions, or deletes profiles. Missing or non-directory profiles raise `MediaCrawlerProfileUnavailableError` at command assembly time.

Current deployment check remains explicit:

```json
{
  "manual": {"exists": false},
  "scheduler": {"exists": false}
}
```

The existing `browser_data/wb_user_data_dir_manual` was not copied or modified. Profile provisioning remains an operator/deployment prerequisite for a later Enable audit.

## Real-Run Gate Design

Added deployment-only setting `MEDIA_CRAWLER_REAL_RUN_GATE` (`media_crawler_real_run_gate`), defaulting to `false`. The prior `media_crawler_enable_real_run` setting remains for backward-compatible explicit Runner tests; the Runtime Factory uses the new gate for production runtime assembly.

- Gate `false`: manual mock/fixture tests remain possible when explicitly requested; scheduler runtime raises `MediaCrawlerRuntimeError` before command/process execution.
- Gate `true`: valid scheduler command assembly is allowed, subject to profile readiness and the existing Runner timeout/process checks.

The gate was not enabled in this phase.

## Batch Locator Design

`MediaCrawlerBatchLocator` provides a single, traversal-safe mapping:

```text
<runtime_root>/runs/<batch_id>/
  metrics.json
  raw/weibo.jsonl
  output/weibo.jsonl
```

Runner initialization and metrics updates now use this locator. `CollectorRun.batch_id` supplied by `CollectorService` therefore resolves to the same future run directory and `metrics.json` path. The locator only computes/inspects paths; it does not create or repair artifacts.

## Historical Batch Compatibility

The legacy `e62641b78a9449d0b9874c380a4aa8b5` batch was inspected read-only. No matching `metrics.json` was found at the unified configured path. It was not backfilled, copied, or rewritten. The result is recorded as `legacy batch missing metrics`; future runs use the unified locator.

## Failure and Safety Semantics

- Missing profile: explicit `MediaCrawlerProfileUnavailableError`.
- Scheduler gate disabled: explicit `MediaCrawlerRuntimeError`.
- Existing Runner timeout, process, empty-output, and lock failures remain failed semantics.
- Scheduler eligibility remains `enabled=true AND schedule_enabled=true`.
- No scheduler was started and no real crawl was invoked.

## Tests

MediaCrawler suite (`tests/test_media_crawler*.py`):

```text
97 passed, 1 warning
```

New `test_media_crawler_2f_fix.py` covers isolated profile paths, missing-profile failure, gate false/true behavior, batch paths, traversal rejection, and legacy missing metrics without auto-creation. The warning is the existing Pydantic class-based configuration deprecation warning.

## Database

NO CHANGE. No DataSource, Opinion, or CollectorRun data was written.

## Migration

NO CHANGE. No Alembic command was executed and no schema was changed.

## DataSource

NO CHANGE. DataSource `id=40` remains `enabled=true`, `schedule_enabled=false`, with the existing business `config_json` unchanged.

## Scheduler

Disabled. Scheduler eligibility and scheduling configuration were not modified.

## Real Crawl

NOT CALLED. No real MediaCrawler subprocess, login, browser profile, cookie, or session was used.

## Final Status

Phase MediaCrawler-2F-Fix: PASS

READY_FOR_ENABLE_AUDIT

