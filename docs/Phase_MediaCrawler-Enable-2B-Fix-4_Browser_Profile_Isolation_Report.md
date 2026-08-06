# Phase MediaCrawler-Enable-2B-Fix-4 Browser Profile Isolation Report

Date: 2026-08-05  
Scope: disposable browser-profile isolation only

## Root Cause

The previous scheduler runtime passed the persistent template
`profiles/scheduler` directly as both `MEDIA_CRAWLER_PROFILE_NAME` and
`MEDIA_CRAWLER_BROWSER_DATA`. Chromium consequently wrote Cookies, History,
Local State, cache, and session state into the long-lived deployment profile.

## Architecture Before / After

Before:

```text
MediaCrawlerRuntimeFactory
  -> profiles/scheduler
  -> MediaCrawlerRunner.browser_data = profiles/scheduler
  -> Chromium writes persistent template
```

After:

```text
DataSource batch_id
  -> MediaCrawlerRuntimeFactory.create_runner("scheduler", batch_id)
  -> BrowserProfileIsolationManager
  -> copy profiles/scheduler
       to runtime_profiles/<batch_id>/
  -> MediaCrawlerRunner.browser_data = runtime_profiles/<batch_id>
  -> Chromium writes disposable profile only
  -> success: remove runtime_profiles/<batch_id>
  -> failure: retain runtime_profiles/<batch_id> for audit
```

Manual execution remains unchanged:

```text
manual -> profiles/manual -> login=qrcode
```

## Changed Files

- `backend/app/core/browser_profile_manager.py`
  - Added safe batch-scoped copy and cleanup manager.
  - Rejects invalid batch IDs, refuses overwrite, preserves file metadata, and
    refuses deletion outside `runtime_profiles`.
- `backend/app/collectors/mediacrawler_runtime.py`
  - Added optional `batch_id` to `create_runner`.
  - Scheduler runs with a disposable `runtime_profiles/<batch_id>` copy.
  - Manual and legacy no-batch factory calls retain existing profile behavior.
- `backend/app/collectors/media_crawler_weibo_collector.py`
  - Passes the Collector batch ID into RuntimeFactory.
  - Fails closed if the production scheduler path is invoked without a batch ID.
  - Recreates scheduler runtime when the batch changes.
  - Cleans the runtime profile only after runner and JSONL normalization succeed;
    failures retain it.
- `backend/tests/test_media_crawler_enable_2b_fix4.py`
  - Added six isolation and compatibility regression tests.

No database, migration, DataSource, Scheduler, gate, or MediaCrawler business
logic was changed.

## Runtime Profile Lifecycle

1. Registry creates `MediaCrawlerWeiboCollector` with
   `MediaCrawlerRuntimeFactory`.
2. `CollectorService` supplies the batch ID to `collector.fetch`.
3. Scheduler RuntimeFactory validates the persistent scheduler template.
4. `BrowserProfileIsolationManager` creates exactly
   `runtime_profiles/<batch_id>/`; existing directories are never overwritten.
5. Runner receives the disposable path in both browser environment variables.
6. On successful crawl and JSONL parsing, the disposable directory is removed.
7. On command, timeout, or parsing failure, the disposable directory remains.

## Test Results

Fix-4 tests:

```text
6 passed
```

Full media crawler suite:

```text
118 passed, 1 warning
```

Command:

```text
pytest tests/test_media_crawler*.py -q
```

Covered cases:

- runtime profile creation under the batch ID;
- scheduler runner path differs from the persistent template;
- fake browser writes Cookies/History/Local State only in the runtime copy;
- persistent scheduler profile content and mtimes remain unchanged;
- success cleanup;
- failure retention;
- manual profile and QR login behavior unchanged.

## Security Verification

```text
Persistent profiles/scheduler:
IMMUTABLE IN TESTS

Runtime browser profile:
BATCH-SCOPED AND DISPOSABLE

Batch isolation:
PASS

Manual flow:
UNCHANGED

Database:
NO CHANGE

Migration:
NO CHANGE

DataSource:
NO CHANGE

Scheduler:
NOT STARTED

MEDIA_CRAWLER_REAL_RUN_GATE:
NOT CHANGED

Real MediaCrawler:
NOT CALLED
```

## Final Status

`READY_FOR_FINAL_ISOLATED_DRY_RUN`

The next dry run must verify the same runtime chain while additionally proving
that the persistent scheduler profile has no file or mtime changes and that
the batch runtime profile is removed on success.
