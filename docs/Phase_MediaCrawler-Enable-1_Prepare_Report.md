# Phase MediaCrawler-Enable-1 Prepare

## Changes

- Added operator-facing profile provisioning guidance.
- Added an enable approval checklist that keeps the real-run gate and
  `schedule_enabled` closed.
- Documented the legacy metrics decision without creating historical data.
- Added scheduler command-resolution regression tests using temporary runtime
  settings only.
- Updated the Runner/Runtime Factory boundary so the absolute scheduler
  profile is passed as `MEDIA_CRAWLER_PROFILE_NAME` and the external
  MediaCrawler checkout remains the subprocess working directory.
- No production database, schema, migration, or runtime profile was changed;
  no real crawler command was invoked.

## Profile Preparation

`MediaCrawlerProfileManager` remains read-only. It resolves isolated
`profiles/manual` and `profiles/scheduler` paths and reports missing paths
without creating or copying state. Both production paths are currently
absent. The required manual provisioning procedure is documented in
`docs/MediaCrawler_Profile_Provisioning.md`; the application will not copy
`browser_data`, cookies, sessions, or tokens.

The runtime boundary now passes the resolved scheduler path through
`MEDIA_CRAWLER_PROFILE_NAME`. The standard entry maps that value to
`config.USER_DATA_DIR`; the runner uses the MediaCrawler checkout as `cwd`,
so the upstream browser launcher resolves the same isolated directory rather
than falling back to `browser_data/wb_user_data_dir`.

## Runtime Command

The scheduler path is verified as:

```text
scheduled trigger
  -> MediaCrawlerRuntimeFactory
  -> MediaCrawlerCommandBuilder
  -> MediaCrawlerRunner
```

With deployment `MEDIA_CRAWLER_ENTRY` and `MEDIA_CRAWLER_PYTHON` present, the
factory resolves the executable, entry, Weibo arguments, cookie login policy,
and scheduler profile path. Missing entry/executable fails during factory
resolution; no `no MediaCrawler command configured` fallback is used by this
path. The new `test_scheduler_command_resolution` test covers command
available, command missing, and gate-closed cases without starting a process.

## Gate Status

`MEDIA_CRAWLER_REAL_RUN_GATE=false` remains unchanged. Scheduled real execution
fails closed with `MediaCrawlerRuntimeError` before process execution. Manual
fixture/mock tests remain available. Gate approval belongs to the explicit
Enable phase and is not performed here.

## Metrics Decision

The legacy batch `e62641b78a9449d0b9874c380a4aa8b5` has no discoverable
`metrics.json` or JSONL artifacts at the unified locator. It is marked
`legacy batch unavailable`; no synthetic metrics were written. Future batches
continue to use `runs/<batch_id>/metrics.json`, with `CollectorRun.batch_id` as
the lookup key. See `docs/Phase_MediaCrawler-Legacy-Metrics-Decision.md`.

## Failure Validation

The existing runner and runtime tests confirm that missing command, missing
profile, gate=false, timeout, non-zero process exit, empty bounded output, and
lock conflict remain failed-run paths with `metrics.failed=1` where a batch is
initialized. The historical 3/4 runtime configuration failures are therefore
covered by an explicit regression test and no longer silently resolve through
the scheduler path.

## Test Result

Command:

```text
pytest tests/test_media_crawler*.py -q
```

Result after this phase: **101 passed, 1 warning**. The warning is the existing
Pydantic class-based-config deprecation warning. No scheduler integration test,
database-writing test, or real crawl was executed.

## Database

NO CHANGE

## Migration

NO CHANGE

## DataSource

NO CHANGE (`id=40`, `schedule_enabled=false`)

## Scheduler

Disabled

## Real Crawl

NOT CALLED

## Final Status

**BLOCKED**

Enable recheck is required after an operator provisions an isolated scheduler
profile and the explicit enable approval process addresses the still-closed
real-run gate. This phase intentionally does not enable production execution.
