# Phase MediaCrawler-2A Design Fix

## Decision

`collection_scope` is the public MediaCrawler collection contract and accepts
only `regional` or `national`. The legacy `collection_mode` key is read for
backward compatibility when it contains `regional` or `national`; the value
`manual` is rejected because it describes triggering, not collection scope.
The validator does not write or synthesize a new `collection_mode` key.

For national collection, `Opinion.region_id` is resolved through the existing
region-resolution service to the pre-seeded sentinel `regions.code='000000'`.
The adapter never writes a region id, and no model, database constraint, or
migration is changed. An explicit national collection uses the sentinel even
when the text mentions a locality; regional collection continues to use the
existing factual region-resolution rules.

## Configuration Contract

MediaCrawler config may contain `collector='mediacrawler'`,
`platform='weibo'`, an optional list of non-empty `keywords`, `max_items` in
the inclusive range 1-20, and `collection_scope` (`regional` or `national`).
The existing DataSource top-level fields continue to own `enabled`,
`schedule_enabled`, `schedule_interval_minutes`, and `scope_region_codes`.
The first registration payload remains disabled and unscheduled.

## Quantity and Time Boundaries

The effective item limit is resolved in this order:

1. `DataSource.config_json.max_items`
2. collector constructor value
3. collector default (10)

The runner is the only quantity boundary. It preserves raw native JSONL,
writes bounded output JSONL, and reports `raw_count`, `output_count`, and
`effective_max_items` in `MediaCrawlerRunResult`. The adapter reads output
without slicing a second time.

Publish timestamps are normalized to UTC. Offset-aware values are converted;
timezone-less values are interpreted as `Asia/Shanghai` and then converted.
The returned value is a naive UTC `datetime`, matching the existing database
`DateTime` contract. For example,
`2026-08-04T12:00:00+08:00` becomes `2026-08-04 04:00:00` UTC.

## Non-Goals

No Opinion schema change, database migration, DataSource registration,
scheduler enablement, real crawl, or Event/Risk/Dashboard rewrite is part of
this phase.
