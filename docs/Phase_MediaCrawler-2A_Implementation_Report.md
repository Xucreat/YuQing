# Phase MediaCrawler-2A Implementation Report

## Status

Phase MediaCrawler-2A implementation completed for the approved sentinel-region
design. The existing Opinion schema, database, migration chain, DataSource
registration state, and scheduler state were left unchanged.

## Code Changes

- `backend/app/collectors/source_config.py`
  - Added `collection_scope` with legacy `collection_mode` read compatibility.
  - Rejects `collection_mode=manual` and validates MediaCrawler collector,
    platform, keywords, and `max_items` (1-20).
- `backend/app/api/admin_data_sources.py`
  - Applies the MediaCrawler configuration contract to create/update payloads.
- `backend/app/collectors/media_crawler_registration.py`
  - Uses a disabled, unscheduled national configuration instead of the illegal
    manual collection mode.
- `backend/app/collectors/media_crawler_weibo_collector.py`
  - Reads configured `max_items` with DataSource > constructor > default
    precedence and records the effective value.
  - Converts all publish timestamps to UTC before returning normalized rows.
- `backend/app/collectors/mediacrawler_runner.py`
  - Exposes `effective_max_items` while preserving raw JSONL and bounded output.
- `backend/app/services/opinion_region_service.py`
  - Enforces the existing `000000` sentinel for explicit national collection.

## Verification

- `tests/test_media_crawler_2a.py`: 9 passed.
- Existing MediaCrawler 1A-1K suite: PASS after updating the obsolete
  registration assertion to the `collection_scope` contract.
- No real crawl was called. No DataSource was registered. Scheduler remains
  disabled for MediaCrawler.

## Database and Migration

No database writes, schema changes, or migrations were performed. National
admission requires the pre-existing `regions.code='000000'` row; if that
sentinel is absent, region resolution fails explicitly rather than writing a
null or fabricated foreign key.
## Finalization

The legacy registration test now uses the valid national contract, and
`test_reject_collection_mode_manual` verifies that `manual` is rejected as a
collection scope. A read-only national sentinel audit was added at
`backend/scripts/check_national_region_sentinel.py` and documented in
`docs/Phase_MediaCrawler-2A-Region-Sentinel-Audit.md`.
The audit returned PASS for one row: `id=24`, `code=000000`, `name=全国`.

## Test Final Result

MediaCrawler tests: PASS

The complete MediaCrawler adapter, 1B-1K, and 2A test set passes.

## Region Sentinel

```text
collection_scope=national
        |
        v
RegionResolver
        |
        v
regions.code='000000'
        |
        v
Opinion.region_id
```

## Safety Boundary

```text
Database: NO CHANGE
Migration: NO CHANGE
DataSource: NOT REGISTERED
Scheduler: Disabled
Real Crawl: NOT CALLED
```
