# Phase MediaCrawler-2D Implementation Report

## Modified Files

- `backend/app/collectors/mediacrawler_runner.py`
- `backend/app/collectors/media_crawler_weibo_collector.py`
- `backend/app/collectors/service.py`
- `backend/tests/test_media_crawler_2d.py`
- `docs/Phase_MediaCrawler-2D_Implementation_Report.md`

No CollectorRun model, Opinion model, Region model, RiskEngine, Event model, Scheduler, DataSource registration, migration, or MediaCrawler external repository was modified.

## Metrics Design

Each MediaCrawler Runner invocation creates one file at:

```text
runtime/mediacrawler/runs/<batch_id>/metrics.json
```

The file is initialized before execution and updated in place after CollectorService admission/analysis. It contains exactly the batch-level counters:

```json
{
  "batch_id": "<batch id>",
  "collector": "mediacrawler",
  "raw_count": 0,
  "output_count": 0,
  "effective_max_items": 0,
  "created": 0,
  "duplicate": 0,
  "admission_filtered": 0,
  "failed": 0
}
```

The metrics writer uses the Runner batch directory and batch id as the sole identity. It is a file-based observability path and does not add CollectorRun columns or write database state. Metrics updates are best-effort after the CollectorRun counters are computed and cannot change CollectorService success/failure semantics.

## Batch Example

The Phase 2C baseline batch remains the audit example; it was not re-run:

```text
batch_id:             e62641b78a9449d0b9874c380a4aa8b5
raw_count:            16
output_count:         10
effective_max_items:  10
created:               6
duplicate:             0
admission_filtered:    4
failed:                0
```

The new implementation will produce the same shape for future offline, manual, or approved production batches. No real Weibo crawl was used to generate this report.

## Runner and CollectorService Behavior

- Runner records `raw_count`, `output_count`, and `effective_max_items` immediately for every initialized batch.
- CollectorService writes `created`, `duplicate`, `admission_filtered`, and `failed` back to the same batch file for MediaCrawler only.
- Login/process failure, timeout, and `raw_count > 0 && output_count == 0` all leave `failed=1` and preserve the existing exception semantics.
- `raw_count == 0 && output_count == 0` remains a successful empty-data result with `failed=0`.

## Tests

The requested MediaCrawler test set was run with explicit PowerShell file expansion (Windows pytest does not expand the shell glob itself):

```text
pytest tests/test_media_crawler*.py -q
82 passed, 1 warning
```

The new `tests/test_media_crawler_2d.py` covers:

- `raw=16`, `output=10`, and `effective_max_items=10`;
- `created=6` and `admission_filtered=4` metrics;
- duplicate metrics;
- process/login failure metrics;
- timeout metrics;
- raw records with empty bounded output failing with `MediaCrawlerEmptyOutputError`.

The warning is the existing Pydantic class-based configuration deprecation warning and is unrelated to MediaCrawler behavior.

## Database

NO CHANGE. No production database was queried for mutation and no Opinion or CollectorRun was created.

## Migration

NO CHANGE. No Alembic command was executed and no migration file was added.

## Scheduler

Disabled. Scheduler code and configuration were not modified or started.

## Real Crawl

NOT CALLED. Tests use local fixtures and injected mock commands only; no external MediaCrawler repository or Weibo login profile was used.

## Final Status

**READY_FOR_2E**
