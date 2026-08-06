# MediaCrawler Enable Rollback Plan

This plan applies to the later Enable change. It was not executed during the
Enable-2A approval check.

## Rollback Operations

1. Set the MediaCrawler DataSource `schedule_enabled=false`.
2. Set deployment `MEDIA_CRAWLER_REAL_RUN_GATE=false` and restart the backend
   process so the gate is reloaded.
3. Keep `DataSource.enabled=true` when the source should remain available for
   approved manual operation. Set `enabled=false` only when manual execution
   must also be blocked; this is a broader operational stop and requires its
   own approval.
4. Stop source dispatch by leaving the source ineligible for the scheduler and
   verify it is absent from both scheduled and due source queries. Do not
   delete or rewrite historical runs.
5. Retain all `CollectorRun`, raw/output artifacts, metrics, and logs for
   audit. Do not delete historical data.

## Verification

After rollback, confirm:

```text
weibo_mediacrawler.enabled=true (or explicitly disabled by approval)
weibo_mediacrawler.schedule_enabled=false
MEDIA_CRAWLER_REAL_RUN_GATE=false
weibo_mediacrawler absent from scheduled_enabled_sources and due_scheduled_sources
```

The source lock and failed-run semantics remain unchanged during rollback.
