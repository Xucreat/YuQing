# MediaCrawler XHS National Configuration Fix

## 1. Root cause

The XHS source had an explicit national collection mode together with regional
strategy values. The old validator treated those strategy keys as mutually
exclusive with national mode and failed during registry assembly:

```json
{
  "collection_mode": "national",
  "filter_mode": "region_only",
  "keyword_scope": "region_topic"
}
```

This restriction was stricter than the ordinary nationwide sources. It also
prevented MediaCrawler from using the shared `keyword_scope` and
`keyword_cursor` behavior.

## 2. Minimal implementation

| File | Change |
| --- | --- |
| `backend/app/collectors/source_config.py` | MediaCrawler national now validates the normal filter/scope value sets and their impossible combinations, instead of forcing `topic_only/topic`. National still requires empty regional codes. |
| `backend/app/api/admin_data_sources.py` | Existing MediaCrawler write-path validation remains in use, including scope-only PATCH rollback behavior. |
| `backend/scripts/migrate_social_sources_national.py` | National migration keeps valid `filter_mode` and `keyword_scope` values and removes only invalid values. |
| `backend/app/collectors/media_crawler_registration.py` | XHS registration uses global enabled keywords and no default regional scope. |
| `backend/tests/test_mediacrawler_national_config.py` | Covers national aliases, regional keyword strategies, empty scope, and migration preservation. |

No database schema, Opinion model, Scheduler, CollectorService main flow, or
ordinary collector behavior was changed by this adjustment.

## 3. Resulting chain

```text
collection_mode=national + scope_region_codes=NULL
  -> resolve effective enabled keywords
  -> apply keyword_scope
  -> select one keyword with keyword_cursor
  -> single-keyword MediaCrawler search
  -> normalizer
  -> filter_mode admission
  -> CollectorService / Opinion
```

`collection_mode` controls collection coverage. `keyword_scope` controls the
search keyword pool. `filter_mode` controls content admission. A regional
keyword hit is a text/strategy match, not proof that the source itself is
bound to that region.

## 4. Current data verification

The Weibo and XHS rows were verified with:

```text
collection_mode=national
scope_region_codes=NULL
keywords=[]
```

There is no default `131028` binding.

## 5. Hidden risks

1. `national + region_only` can still produce a regional text filter over
   nationwide content. It must not be interpreted as geographic containment.
2. Incompatible strategy combinations can produce an empty result pool. The
   validator rejects the known impossible pairs; runtime metrics should still
   monitor empty pools.
3. Expanding the search pool can increase platform requests, duplicates, rate
   limiting, and operational cost.
4. `data_sources.last_status/last_error` has no unified write path; assembly
   failures are visible in `collector_runs`, but the source row can remain
   stale.
5. The frontend permits `max_items` up to 500 while MediaCrawler accepts at
   most 20.
6. One-off database scripts can still bypass the admin API unless they call the
   shared validator.
7. Some XHS runtime tests depend on a local checkout path configured outside
   the repository; that environment mismatch is separate from this fix.

## 6. Verification

Passed:

- 49 configuration and MediaCrawler integration tests
- 21 MediaCrawler platform regression tests
- `compileall`
- `git diff --check`

The remaining XHS runtime test failures are caused by the external checkout
path configured as `D:\code files\mediaCrawler\MediaCrawler`, not by this
configuration change.
