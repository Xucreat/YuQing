# MediaCrawler Legacy Metrics Decision

## Decision

Use strategy A: the legacy batch is unavailable at the unified artifact
location. Do not synthesize or backfill metrics for
`e62641b78a9449d0b9874c380a4aa8b5`.

## Evidence

Read-only inspection with `MediaCrawlerBatchLocator` found no discoverable
run directory, `metrics.json`, raw JSONL, or bounded output JSONL under the
configured runtime root for that batch. No original artifact was available at
an alternate approved location.

## Forward Contract

All new runs must use:

```text
runtime/mediacrawler/runs/<batch_id>/metrics.json
runtime/mediacrawler/runs/<batch_id>/raw/weibo.jsonl
runtime/mediacrawler/runs/<batch_id>/output/weibo.jsonl
```

`CollectorRun.batch_id` is the only lookup key. A missing legacy artifact is
reported as `legacy batch unavailable`; it is not repaired by this phase.
