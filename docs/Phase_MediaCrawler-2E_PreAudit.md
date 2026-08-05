# Phase MediaCrawler-2E PreAudit

## Scope and Safety Boundary

This was a read-only gray-scheduler pre-audit. `schedule_enabled` was not changed, the Scheduler was not started, no DataSource or database row was modified, no migration was executed, and no real Weibo crawl was called.

## Current Production State

| Item | State |
| --- | --- |
| DataSource | `id=40`, `key=weibo_mediacrawler` |
| enabled | `true` |
| schedule_enabled | `false` |
| schedule_interval_minutes | `60` |
| Scheduler | Disabled / not started |
| Recent successful batch | `e62641b78a9449d0b9874c380a4aa8b5` |

## 1. Scheduler Architecture and Eligibility

The scheduled-source repository uses the following gates for both scheduling modes:

```text
enabled = true AND schedule_enabled = true
```

Per-source mode additionally requires `next_collect_time IS NULL OR next_collect_time <= now()` and excludes `weibo_octopus`. Cron mode also requires `schedule_enabled=true`; it does not bypass that gate. Therefore the current MediaCrawler row (`enabled=true`, `schedule_enabled=false`) is not eligible and cannot enter the scheduler queue.

The future registry path was verified with an in-memory DataSource row (no database access):

```text
DataSource.config_json
  -> data_source_repository.enabled_sources()
  -> registry._parse_config()
  -> validate_data_source_config()
  -> MediaCrawlerWeiboCollector constructor
  -> _attach_meta(source_config)
```

The result was one `MediaCrawlerWeiboCollector`, no registry failures, `data_source_key=weibo_mediacrawler`, `max_items=10`, and `collection_scope=national`.

**Registry resolution: PASS**

### Scheduler Execution Blocker

The resolved collector is not executable by the current scheduler path. `MediaCrawlerWeiboCollector.__init__()` creates `MediaCrawlerRunner(fixture_path=fixture_path)` without a command. The production DataSource config carries strategy fields but no command/entry, while `MediaCrawlerRunner.run()` refuses to proceed when `runner.command is None` and raises `MediaCrawlerRunnerConfigurationError("no MediaCrawler command configured...")`.

The explicit command builder is used by the manual verification script, not by registry/Scheduler construction. The current environment has `MEDIA_CRAWLER_ENTRY` configured, but the collector does not consume it. Consequently, changing only `schedule_enabled` to `true` would create a failed CollectorRun rather than a successful scheduled crawl.

**Scheduler-ready execution: BLOCKED**

## 2. Concurrency Audit

Scheduler-only protections are present:

- Per-source APScheduler job uses `max_instances=1` and `coalesce=True`.
- Each tick claims due rows by advancing `next_collect_time` before dispatch.
- A PostgreSQL advisory lock makes the scheduler a cross-process singleton.
- Due sources are merged into one `collect_and_analyze_concurrent()` call.
- CollectorService uses an instance write lock around duplicate-check/Opinion writes, preventing duplicate DB admission across worker threads.

Thus two scheduler ticks in the same configured scheduler instance, or two backend instances competing for the scheduler singleton, should not create two scheduled runs for the same claimed source. The write lock does not serialize the network/browser phase, and there is no source-level lock shared between a manual trigger and a scheduled trigger. A future gray test must therefore include an explicit manual-versus-scheduled overlap decision before enabling both paths together.

**Scheduler tick concurrency: PASS**

## 3. Browser Profile Safety

The Runner passes `MEDIA_CRAWLER_BROWSER_DATA` to an explicitly injected subprocess and does not delete, replace, or recursively remove a browser profile. It also redacts cookie/token/authorization/browser-data values in Runner logs. The real-run gate remains closed by default (`media_crawler_enable_real_run=false`).

However, no scheduler-specific profile/login policy is enforced because the scheduler cannot currently construct the explicit command or profile selection used by the manual verification script. Once command wiring exists, the gray test must prove that an existing profile is selected, QR/login fallback is disabled, and profile paths are not shared by overlapping manual and scheduled processes.

**Profile safety for current disabled state: PASS**

**Profile safety for future automatic execution: BLOCKED pending command/profile wiring**

## 4. Schedule Interval Analysis

The registered interval is 60 minutes. The Runner timeout setting is 900 seconds (15 minutes), so the configured timeout leaves approximately 45 minutes of schedule slack. A timed-out run cannot exceed the next 60-minute due window through the Runner itself.

This does not remove the manual-versus-scheduled overlap gap described above, nor does it make an unconfigured Runner executable. No timing change was made during this audit.

**Interval overlap risk for scheduler-only execution: LOW / PASS**

## 5. Failure Recovery

The existing exception paths are explicit:

- login/process failure -> `MediaCrawlerProcessError`;
- Runner timeout -> `MediaCrawlerTimeoutError`;
- raw records with zero bounded output -> `MediaCrawlerEmptyOutputError`;
- missing Runner command -> `MediaCrawlerRunnerConfigurationError`.

After a CollectorRun is created, `CollectorService._process_collector()` catches these exceptions, sets `status="failed"`, records a sanitized `error_msg`, sets `end_time`, commits, and re-raises. The scheduler catches the propagated error at its job boundary; it does not perform an in-process infinite retry. The next attempt is governed by the normal schedule interval.

The current unconfigured scheduler path would therefore fail visibly and safely, but it would not collect data.

**Failure recovery semantics: PASS**

## 6. Metrics Compatibility

The Phase 2D metrics writer is independent of trigger type. For any Runner invocation it writes the same batch file:

```text
runtime/mediacrawler/runs/<batch_id>/metrics.json
```

with:

```text
raw_count
output_count
effective_max_items
created
duplicate
admission_filtered
failed
```

CollectorService updates the same file after MediaCrawler admission/analysis. Failure paths mark `failed=1`; empty raw and empty output remains an allowed empty result. The metrics path is therefore compatible with a future scheduler invocation, although the current scheduler cannot reach a successful Runner invocation because command wiring is missing.

**Metrics compatibility: PASS**

## 7. Read-Only Test Evidence

The complete MediaCrawler suite was run with explicit PowerShell file expansion:

```text
pytest tests/test_media_crawler*.py -q
82 passed, 1 warning
```

The warning is the existing Pydantic class-based configuration deprecation warning. Selected scheduler tests were also inspected/executed without starting a real scheduler. Two legacy fake-session tests fail at the new `_scheduler_discovery_ok()` guard because their mocks do not implement `.mappings()` / `.execute()`; this is a test-fixture mismatch, not evidence that the production eligibility or lock path is unsafe. Those tests were not modified in this read-only phase.

## 8. Changes Required Before Gray Scheduler Test

The following blocker must be resolved in a later implementation phase:

1. Inject an approved, explicit MediaCrawler command/entry and existing-profile policy into the registry-created collector, without putting secrets or mutable profile contents in `DataSource.config_json`.
2. Add a source-level/manual-versus-scheduled overlap policy or lock if both triggers may be used concurrently.
3. Update scheduler test fakes to satisfy the discovery guard before relying on those tests as a gray-scheduler gate.

No database schema change, migration, DataSource update, Scheduler enablement, or real crawl is authorized as part of this pre-audit.

## Final Conclusion

**BLOCKED**

Blocking point: `schedule_enabled=true` would resolve the collector but cannot execute a MediaCrawler command because `MediaCrawlerWeiboCollector` does not receive the configured `MEDIA_CRAWLER_ENTRY`/command or a scheduler-safe profile policy. Code changes are required before any gray Scheduler test. Database changes and migrations are not required by this finding, and Scheduler must remain disabled.

## Safety Record

- Database: `NO CHANGE`
- Migration: `NO CHANGE`
- DataSource: `NO CHANGE`
- Scheduler: `Disabled`
- Real Crawl: `NOT CALLED`
