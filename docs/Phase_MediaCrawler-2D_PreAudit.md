# Phase MediaCrawler-2D PreAudit

## 1. Audit Scope

This phase is a read-only production-stability audit of the MediaCrawler Weibo path that passed Phase 2C. No business code, database row, schema, Alembic migration, DataSource configuration, Scheduler state, MediaCrawler external repository, or Weibo profile was changed. No new Opinion or CollectorRun was created, and no real crawl was called by this audit.

## 2. Current State

| Item | Observed state |
| --- | --- |
| DataSource | `id=40`, `key=weibo_mediacrawler` |
| enabled | `true` |
| schedule_enabled | `false` |
| Scheduler instance | not running (`None`) |
| 2C batch | `e62641b78a9449d0b9874c380a4aa8b5` |
| CollectorRun | `id=13604`, `status=success` |
| Runner counts | `raw=16`, `output=10`, `effective_max_items=10` |
| Opinions | 6 admitted, all `region_id=24` / `regions.code=000000` |

## 3. CollectorRun Capability Analysis

The current `collector_runs` model contains `fetched_raw`, `created`, `duplicate`, `admission_filtered`, `failed`, `status`, and `error_msg` (plus lifecycle and acknowledgement fields). It does not contain explicit `output_count`, `admitted_count`, `rejected_count`, or `effective_max_items` columns, and it has no metadata/JSON column suitable for reuse.

Current semantic mapping:

- `created` is the admitted Opinion count (`6` for the 2C batch).
- `duplicate`, `admission_filtered`, and `failed` are separately available.
- `fetched_raw` is populated from the collector's returned/bounded items in the current service path, so it records `10` for this batch rather than the native raw JSONL count `16`.
- `output_count` and `effective_max_items` are therefore available in the Runner result/log, but not persisted as first-class CollectorRun fields.

Recommendation: a future implementation should add an approved, additive observability mechanism for native raw count, bounded output count, admitted/rejected totals, and effective max items. Do not add columns, metadata, or a migration during this pre-audit.

## 4. Phase 2C Data Explanation

The observed quantity chain is:

```text
16 native raw JSONL records
  -> 10 bounded Runner output records
  -> 6 admitted Opinions
```

Classification of the six records outside the bounded output:

- `6`: quantity-bound exclusion by Runner; these records were never evaluated by CollectorService.

Classification of the four bounded records not admitted:

- `4`: Opinion admission filtered them because their admission scores were `10` or `35`, below the acceptance threshold (pure-region/no-public-affairs signal).
- `0`: duplicate rejection.
- `0`: RegionResolver rejection; national sentinel resolution succeeded for evaluated records.
- `0`: invalid JSONL records.

The four rejected output IDs were `5202019916973735`, `5088993034901217`, `5325686120384032`, and `5325111491821795`. The six records outside the Runner bound were `5298939832308170`, `5319973039769559`, `5170579087819952`, `5109693648998231`, `5193470249272442`, and `5325630636819426`.

## 5. Failure Recovery Analysis

The audited failure paths have explicit exception semantics:

1. Login/process failure raises `MediaCrawlerProcessError`.
2. Runner timeout raises `MediaCrawlerTimeoutError`.
3. Native raw records with zero bounded output raises `MediaCrawlerEmptyOutputError`.

`CollectorService._process_collector()` catches collector-level exceptions after creating the running record, sets `CollectorRun.status="failed"`, records a sanitized `error_msg`, sets `end_time`, commits, and re-raises. Thus all three paths produce a failed CollectorRun and do not report success. No automatic retry loop is introduced by this path, so Scheduler cannot spin on the failure.

## 6. Scheduler Safety Analysis

Both scheduled-source repository queries require:

```text
enabled = true AND schedule_enabled = true
```

The registered MediaCrawler source has `enabled=true` but `schedule_enabled=false`, so it is excluded from due and enabled scheduled-source sets. The Scheduler was not started during this audit. Manual execution remains a separate, explicit path.

**Scheduler Safety: PASS**

## 7. DataSource Quality Display

Backend admin endpoints expose the DataSource configuration and basic fetched/created/status health metrics. Collection logs expose admission and duplicate counts, but do not expose Runner `output_count` or `effective_max_items`. Frontend types and views likewise do not provide MediaCrawler-specific display for those two metrics. Dashboard source aggregation uses `Opinion.source` (`weibo`) rather than the DataSource key, so `weibo_mediacrawler` is not distinguishable there.

The existing `Sources.vue`/`DataManage.vue` files are not modified in this audit; these observations are recorded as display gaps only.

## 8. Code Modification Assessment

No immediate safety defect requiring a 2D code change was found. Failure recovery, empty-output semantics, national sentinel admission, and Scheduler exclusion are already enforced. The remaining risk is observability granularity: future implementation should make Runner/output/admission counters durable and visible without changing Opinion, Risk, Event, Region, or Scheduler behavior.

Database changes required now: **NO**

Migration changes required now: **NO**

DataSource changes required now: **NO**

## 9. Test Result

Read-only targeted verification:

```text
pytest tests/test_media_crawler_2b_fix.py -q
8 passed, 1 warning
```

The complete MediaCrawler selection was also attempted with the Windows-equivalent command `pytest tests -k media_crawler -q`. It exceeded the 124-second command limit without a failure assertion; this is recorded as an environment/test-run timeout, not as a passing full-suite result. No real crawler command was invoked by the audit.

## 10. Implementation Readiness

No production safety blocker was found. The next phase may proceed to an explicitly approved implementation of the observability improvements, while preserving the existing 2C boundaries and without enabling Scheduler.

**READY_FOR_IMPLEMENTATION**

## Safety Record

- Modified files: `docs/Phase_MediaCrawler-2D_PreAudit.md` only.
- Database: `NO CHANGE`.
- Migration: `NO CHANGE`.
- DataSource: unchanged by this audit.
- Scheduler: `Disabled` / not started.
- Real Crawl: `NOT CALLED`.
