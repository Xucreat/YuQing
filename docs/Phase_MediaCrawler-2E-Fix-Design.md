# Phase MediaCrawler-2E-Fix Design

## 1. Blocker Analysis

Phase 2E PreAudit found a runtime assembly gap, not a DataSource or schema gap.

Current path:

```text
DataSource.config_json
  -> registry validator
  -> MediaCrawlerWeiboCollector
  -> MediaCrawlerRunner(fixture_path=None, command=None)
  -> MediaCrawlerRunnerConfigurationError
```

The registry resolves the collector and preserves `keywords`, `max_items`, and `collection_scope`, but the collector constructor does not consume deployment `MEDIA_CRAWLER_ROOT`, `MEDIA_CRAWLER_ENTRY`, or `MEDIA_CRAWLER_PYTHON`. The manual verification script builds an explicit command separately, so manual execution passes while Scheduler execution is blocked.

The fix must close this runtime contract gap without putting executable paths, credentials, cookies, or profile contents in `data_sources.config_json`. No database schema change or migration is needed.

## 2. Runtime Configuration Design

Introduce one deployment-scoped `MediaCrawlerRuntimeConfig`/factory used by both manual and scheduled triggers.

### Deployment Environment Configuration

These values are process/deployment configuration and must remain outside the database:

- `MEDIA_CRAWLER_ROOT`: immutable external checkout root;
- `MEDIA_CRAWLER_ENTRY`: approved entry script relative to or below that root;
- `MEDIA_CRAWLER_PYTHON`: executable used to launch the entry;
- `MEDIA_CRAWLER_BROWSER_DATA`: browser-data root;
- explicit manual and scheduler profile names/paths below that browser-data root;
- `MEDIA_CRAWLER_ENABLE_REAL_RUN`: explicit real-process safety gate;
- scheduler non-interactive login/profile policy and timeout bounds.

The factory validates that the root, entry, executable, and selected profile exist and are within the approved roots. It returns a typed runtime object, not a mutable dictionary. Missing or invalid runtime configuration fails before subprocess launch and becomes a failed CollectorRun.

### DataSource Business Configuration

The existing `config_json` remains limited to business policy:

- `collector` and `platform`;
- `keywords`;
- `max_items`;
- `collection_scope`;
- approved non-secret collection flags such as comments/sub-comments if later exposed.

No command, Python path, browser path, cookie, token, session, QR credential, or profile contents may be stored in `config_json`.

### Common Runtime Contract

Both triggers call the same runtime factory and command builder:

```text
trigger (manual | scheduled)
  -> resolve business config
  -> resolve deployment runtime + trigger profile
  -> acquire profile/source lock
  -> allocate batch directory
  -> build argv with MediaCrawlerCommandBuilder
  -> MediaCrawlerRunner(command=..., command_cwd=..., browser_data=...)
  -> CollectorService
```

The only trigger-specific inputs are the approved profile and lock identity. `max_items`, keywords, output directory, platform, and JSONL settings are passed through the same builder in both paths.

## 3. Command Injection Design

The implementation should add a single command-injection seam, preferably a `MediaCrawlerRuntimeFactory.create(trigger, batch_context)` or an equivalent Runner command factory. It must:

1. read `python_executable`, `entry`, and `command_cwd` from the validated deployment runtime;
2. call the existing `MediaCrawlerCommandBuilder` with effective DataSource keywords and max items;
3. use the Runner-created batch output directory so native output and `metrics.json` retain one `batch_id`;
4. pass `shell=False` argv to `MediaCrawlerRunner`;
5. require `MEDIA_CRAWLER_ENABLE_REAL_RUN=true` for a real subprocess;
6. reject an empty command, missing entry, unsupported platform, invalid max items, and an interactive scheduler login mode before creating a process.

The manual verification script should be refactored to use this same factory. The Scheduler must not call the manual script as a subprocess and must not duplicate command construction. The DataSource registry should attach only the validated business config; runtime injection remains deployment-owned.

The current command builder defaults to `login_type="qrcode"`. The scheduler policy must not accept that default. The implementation must select and test an approved non-interactive/profile-reuse mode supported by the installed MediaCrawler CLI; if the installed CLI cannot guarantee that mode, the scheduler run must fail closed with `profile unavailable`/`non-interactive login required` rather than attempting QR login.

## 4. Browser Profile Isolation Design

Use separate persistent profiles under the deployment browser-data root:

```text
<browser-data-root>/wb_user_data_dir_manual
<browser-data-root>/wb_user_data_dir_scheduler
```

Rules:

- manual and scheduler never use the same profile path;
- scheduler profile must be pre-provisioned and validated before dispatch;
- scheduler never opens QR login or interactive login fallback;
- scheduler never deletes, replaces, or resets a profile;
- the Runner log contains only redacted profile metadata, never cookies/tokens/profile contents;
- profile validation failure raises a typed runtime error and is persisted as `CollectorRun.status="failed"`.

The profile path is selected by trigger policy, not by DataSource JSON. Profile contents remain on the host filesystem and are not copied into runtime metrics or application logs.

## 5. Concurrency Design

Keep existing Scheduler protections and add one shared source/profile execution lock for manual and scheduled paths.

### Existing Protections to Preserve

- APScheduler per-source job: `max_instances=1`, `coalesce=True`;
- PostgreSQL advisory lock for one scheduler process across backend instances;
- atomic `next_collect_time` claim before dispatch;
- 60-minute DataSource interval;
- 900-second Runner timeout;
- CollectorService write lock for duplicate-check and Opinion writes.

### Required Shared Lock

Acquire a non-schema lock before launching the browser process, keyed by `weibo_mediacrawler + profile identity`. A PostgreSQL advisory lock is preferred because it spans manual and scheduled backend processes and is already used for the scheduler singleton. A host file lock is an acceptable fallback only when deployment topology guarantees one host.

The lock must be held through Runner completion, CollectorService processing, metrics finalization, and failure cleanup. On timeout, process failure, or application crash, PostgreSQL releases the session lock; `finally` blocks release normal-run locks. A second trigger must fail fast or be skipped as `already running`, never launch a second browser profile against the same identity.

An optional read-only running-CollectorRun check may improve operator messages, but it is not a substitute for an atomic lock because `CollectorRun` has no new uniqueness field and a check-then-insert race would remain.

With a 15-minute hard timeout and a 60-minute interval, scheduler-only overlap is bounded. Manual-versus-scheduled overlap is not currently protected and must be covered by the shared lock before gray testing.

## 6. Failure Semantics

The following conditions remain failures, never successful empty runs:

- missing runtime root, entry, executable, or scheduler profile;
- non-interactive login/profile policy violation;
- login/process failure;
- subprocess timeout;
- native raw JSONL present but bounded output empty.

CollectorService continues to create/update a failed CollectorRun with sanitized `error_msg`, `end_time`, and no retry loop. Scheduler catches the propagated error and waits for the next normal schedule opportunity. `metrics.json` is still finalized with the batch id and `failed=1` when a Runner batch has been initialized.

## 7. Test Fix Plan

The two legacy scheduler tests fail before exercising scheduling because `_scheduler_discovery_ok()` now calls the real repository shape. Update test fakes, without weakening the production guard:

- implement `FakeSession.execute(...).mappings().all()` for the discovery query;
- implement `FakeSession.close()` and `commit()` as no-ops;
- return the expected `id/key` rows for the due-source query and accept the claim statement;
- add missing result attributes (`upstream_total`, `upstream_returned`, `duplicate`, `ack_status`) to fake results used by Weibo job tests;
- keep all tests in-memory and avoid production database writes.

Add focused tests for the implementation boundary:

1. runtime factory resolves environment settings and rejects missing/unsafe paths;
2. manual and scheduled triggers produce the same argv except for profile/lock policy;
3. scheduler mode rejects `qrcode`/interactive login;
4. manual and scheduler profile paths are distinct;
5. shared lock prevents a second trigger from launching a subprocess;
6. profile unavailable, timeout, process error, and empty output produce failed CollectorRun semantics;
7. `metrics.json` retains all Phase 2D counters and the same batch id;
8. registry resolution with `schedule_enabled=true` remains validator-backed and does not read runtime secrets from DataSource JSON.

No real Weibo crawl is needed for these tests. The gray Scheduler test should use a fake command and fake profile directories only after the runtime factory tests pass.

## 8. Implementation Scope

Expected implementation files are limited to backend runtime/collector wiring and tests:

- a deployment runtime config/factory module;
- `mediacrawler_command_builder.py` for explicit non-interactive policy inputs;
- `media_crawler_weibo_collector.py` / registry attachment seam;
- Runner lock and command-factory integration;
- Scheduler/manual test fixtures and new runtime safety tests;
- implementation documentation.

Explicitly out of scope:

- DataSource schema or row changes;
- CollectorRun schema changes;
- Alembic migration;
- Opinion, Region, Risk, Event, or Dashboard logic;
- enabling `schedule_enabled`;
- starting Scheduler;
- real Weibo collection;
- modifying the external MediaCrawler repository.

## Final Status

No database schema or migration is required by this design. The current Scheduler remains disabled until the runtime factory, profile isolation, and shared lock are implemented and tested.

**READY_FOR_IMPLEMENTATION**
