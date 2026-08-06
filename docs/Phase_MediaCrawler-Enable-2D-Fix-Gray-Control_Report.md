# Phase MediaCrawler-Enable-2D-Fix-Gray-Control Report

Date: 2026-08-05  
Final status: `READY_FOR_GRAY_RETRY`

## Scope

This phase adds an optional Scheduler source allowlist and makes the
real-run gate observable as process-scoped startup state. It does not change
the database schema, DataSource model, `config_json`, browser profile
templates, or production enablement state.

No Scheduler was started and no real MediaCrawler process was executed.

## Changed Files

### `backend/app/collectors/data_source_repository.py`

- Added optional `include_keys` to `due_scheduled_sources`.
- Added optional `include_keys` to `scheduled_enabled_sources`.
- Applied the allowlist in the SQL predicate (`key IN (...)`) before rows are
  returned.
- Preserved the existing all-source behavior when `include_keys=None`.
- Empty allowlists return no candidates.

### `backend/app/core/scheduler.py`

- Added process-scoped `SCHEDULER_SOURCE_ALLOWLIST` parsing.
- Added `start_scheduler(source_allowlist=...)` override.
- Applied the allowlist before candidate discovery, before claim, and before
  CollectorService assembly.
- Added a defense-in-depth allowlist predicate to the `data_sources` claim
  update.
- Scheduler fingerprint logging now includes:

```text
source_allowlist=...
real_run_gate=...
```

- Existing advisory-lock behavior is unchanged; a process that cannot acquire
  the lock does not instantiate a second Scheduler.

### `backend/tests/test_media_crawler_enable_2d_fix_gray_control.py`

Added regression coverage for:

1. SQL-level source allowlist filtering.
2. Claim isolation from sources outside the allowlist.
3. `gate=false` rejecting real scheduled command construction.
4. `gate=true` preserving the `batch_id` runtime-profile contract.
5. Advisory-lock failure preventing creation of a second Scheduler owner.

## Gray Control Contract

Default production behavior remains unchanged:

```python
start_scheduler()
```

means all scheduled sources remain eligible.

For an explicitly approved isolated process, the allowlist can be supplied
without changing `.env` or the database:

```text
SCHEDULER_SOURCE_ALLOWLIST=weibo_mediacrawler
```

or programmatically:

```python
start_scheduler(source_allowlist={"weibo_mediacrawler"})
```

The allowlist is enforced in the repository query, so non-target sources are
not returned and cannot be claimed. The claim statement also repeats the
allowlist as a defense-in-depth guard.

## Gate Isolation

`MEDIA_CRAWLER_REAL_RUN_GATE` remains a process-start configuration. The
existing RuntimeFactory behavior is preserved:

- `false`: scheduled `command_factory` raises
  `MediaCrawlerRuntimeError` before a real command is built.
- `true`: `create_runner(trigger_type="scheduled", batch_id=...)` creates a
  batch-scoped disposable profile and builds the scheduled command contract.

The gate is not persisted to DataSource state and `.env` was not modified.
The long-lived Scheduler must be reloaded with the explicitly approved
process environment before a future gray retry.

## Validation

Executed from `backend`:

```text
pytest tests/test_media_crawler*.py -q
```

PowerShell file expansion was used to pass the matching test files explicitly.
Result:

```text
123 passed, 1 warning in 5.49s
```

Additional validation:

```text
compileall PASS
git diff --check PASS
```

The existing `test_weibo_schedule.py` database-backed test was not included in
the media-crawler glob; when run separately it waits on its test database
connection in this environment. No production database was touched by the
implementation or validation.

## Safety Confirmation

| Area | Result |
|---|---|
| Database schema | NO CHANGE |
| DataSource rows | NO CHANGE |
| `config_json` | NO CHANGE |
| `.env` | NO CHANGE |
| Browser template/profile | NO CHANGE |
| Scheduler startup | NOT STARTED |
| Real MediaCrawler | NOT CALLED |
| Weibo API | NOT CALLED |
| Migration | NOT RUN |
| Second Scheduler owner | NOT CREATED |

## Acceptance

The gray-control implementation is ready for the next explicitly approved
reload and isolated retry:

- source allowlist is optional and backward-compatible;
- allowlist is enforced before query result use and before claim;
- gate behavior is explicit and process-scoped;
- RuntimeFactory `batch_id` behavior remains covered;
- advisory-lock singleton protection remains covered;
- all MediaCrawler tests pass.

## Final Status

`READY_FOR_GRAY_RETRY`
