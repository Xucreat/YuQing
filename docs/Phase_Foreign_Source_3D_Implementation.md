# Phase Foreign-Source-3D Implementation

## 1. Scope and Safety

This phase implements only the isolated foreign Dashboard, hotword, source
distribution, and language distribution surfaces. No map component or China
administrative-region visualization was implemented.

The default database was checked read-only:

- Database: `opinion_db`
- Alembic revision: `foreign_source_1`
- `opinions`: 1702
- `events`: 292
- `event_opinions`: 567
- `alert_records`: 37
- `foreign_opinions`: 3
- Foreign running collector runs: 0
- `foreign_fox_news`, `foreign_guardian`, `foreign_nyt_chinese`: `enabled=false`, `schedule_enabled=false`

No migration, downgrade, write, delete, collection, RSS request, AI call,
proxy request, or notification was executed against the default database.

## 2. Actual Changes

Added:

- `backend/app/services/foreign_visualization_service.py`
- `backend/app/api/foreign_visualization.py`
- `backend/tests/test_foreign_source_3d.py`
- This report

Updated:

- `backend/app/api/__init__.py`: registered the foreign visualization router.
- `frontend/src/views/ForeignWorkspace.vue`: added the Dashboard and hotword
  tabs, and extended the existing sources tab with source/language
  distribution. Existing opinion, risk, event, alert, keyword, source
  management, and collection-log behavior remains in the foreign workspace.

The worktree contained extensive pre-existing dirty and untracked files. They
were retained and not reverted or cleaned.

## 3. API and Query Boundary

Implemented endpoints:

- `GET /api/foreign/dashboard/summary`
- `GET /api/foreign/dashboard/trends`
- `GET /api/foreign/dashboard/risk`
- `GET /api/foreign/dashboard/events`
- `GET /api/foreign/dashboard/alerts`
- `GET /api/foreign/dashboard/sources`
- `GET /api/foreign/hotwords`
- `GET /api/foreign/hotwords/trends`
- `GET /api/foreign/hotwords/sources`
- `GET /api/foreign/source-distribution`
- `GET /api/foreign/language-distribution`

All endpoints use the existing authentication and `foreign:risk:read`
permission boundary. Requests accept a bounded `days=1..90` window and return
UTC window metadata, `data_as_of`, and stable empty structures.

The service reads only:

- `foreign_opinions`
- `foreign_risk_results`
- `foreign_event_candidates`
- `foreign_events`
- `foreign_event_opinions`
- `foreign_alerts`
- `collector_runs` with `scope='foreign'`

It does not import or query domestic opinions, events, alerts, keywords,
regions, or `dashboard_service`. No statistics are written to domestic
tables, and no snapshot or materialized-view table was added.

## 4. Dashboard Semantics

The summary separates:

- total foreign articles and window-new articles;
- completed, failed, pending, and status-level risk results;
- candidate, confirmed, archived, and other foreign event states;
- triggered, acknowledged, resolved, and suppressed foreign alerts;
- foreign collector success, failure, running, and latest-run state.

Unanalysed articles are not counted as low risk. Daily trends use the UTC
collection/creation/trigger timestamps and include zero-valued days. Query
errors are converted to safe 503 summaries without database or configuration
details.

## 5. Hotwords

Hotwords use only foreign article title, summary, content, and confirmed
foreign-event titles. The implementation uses local deterministic tokenization:

- English is case-folded with basic plural normalization and a local stopword
  set.
- Chinese is counted as local character bigrams.
- `China`, `Chinese`, and `中国` are excluded from default results.
- Chinese, English, mixed, and unknown content are kept as separate language
  labels where detectable.
- `foreign_risk_terms` and domestic `keywords` are not used as hotword input.
- No translation, AI, RSS, or online service is called.

Hotword list, daily trend, and source grouping endpoints support window,
language, source, and limit filters. Results are read-only and are never
written into domestic hotword data.

## 6. Source and Language Distribution

The existing `/foreign?tab=sources` view now shows a non-map replacement:

- source name and source key;
- language distribution;
- article count;
- completed risk count;
- confirmed event count;
- foreign alert count;
- latest foreign collection status/time;
- failed foreign collection count;
- daily source trend.

The implementation never treats a media source country as an event location,
never uses `region_id`, and never renders a China administrative map.

## 7. Frontend

ForeignWorkspace now exposes:

- `/foreign?tab=dashboard`
- `/foreign?tab=hotwords`
- `/foreign?tab=sources`

The pages display range and update time, loading, empty, failed, and stale
states. Risk analysis states, event states, and alert states remain distinct.
The stale marker is derived from `data_as_of`; the first implementation is
real-time, so normal responses are fresh. All new requests use only
`/api/foreign/*`. Domestic Dashboard, Events, Alerts, Opinions, map, and
router behavior were not changed.

## 8. Permissions, Performance, and Migration

The initial read permission reuses the existing foreign risk read permission;
no new permission migration was needed. There are no rebuild endpoints and no
automatic visualization jobs. The service uses bounded date windows and small
result limits, with foreign indexes already present on the primary time,
status, source, event, and alert columns. A future high-volume implementation
may add foreign snapshot/run tables after measuring query cost; this phase
does not add them.

No migration was required. Consequently, no upgrade/downgrade was run. The
default database remained at `foreign_source_1`. A read-only smoke check was
run against the existing `opinion_test` database at
`foreign_source_3c_remediation`; its counts were unchanged:

```text
opinions=2 events=0 event_opinions=0 alert_records=0
foreign_opinions=16 foreign_risk_results=0 foreign_events=0 foreign_alerts=0
```

The 16 existing foreign samples were preserved. No temporary rows were
created by this phase, so there was no cleanup deletion.

## 9. Tests and Verification

Passed:

- `pytest backend/tests/test_foreign_source_3d.py -q`: 4 passed.
- `python -m compileall backend/app backend/tests`: passed.
- `cd frontend; npm run build`: passed. Existing Vite annotation/chunk
  warnings remain.
- Read-only `opinion_test` smoke check: all ten visualization service methods
  returned successfully and domestic/foreign row counts before and after were
  identical.
- Route inspection confirmed all eleven new paths are registered under
  `/api/foreign/*`.

Known baseline/environment issue:

- `pytest backend/tests/test_foreign_source_3c.py -q` and a focused single-test
  run did not complete within the local 30-second execution window. The test
  database was reachable and already at `foreign_source_3c_remediation`; the
  process produced no assertion result and was terminated by the command
  timeout. No existing test assertion, domestic code, or database row was
  changed. This is recorded as an environment/test-harness timeout, not as a
  new 3D failure.

The broader Phase 1/1.1/3A/3B/3C integration suite was not altered or masked;
the same database-test timeout is a prerequisite issue for a complete
cross-phase run.

## 10. Map Decision and Release Gate

Foreign Dashboard, hotwords, and source/language distribution are implemented
for isolated testing. A map remains intentionally deferred because current
foreign records do not provide a safe event-region semantic and the domestic
map depends on Chinese administrative `region_id` data. Source distribution
and language/time trends are the approved first-stage substitute.

This implementation may proceed to **Phase Foreign-Source-3D small result
acceptance** in a temporary/test database after the integration test timeout
is resolved. It is **not approved for production gray release** until the
acceptance suite passes, permissions are confirmed, query performance is
measured on representative foreign volume, and product owners approve the
foreign read permission and stale-data policy.

## 11. Required Final Statements

- Domestic chain: not modified.
- Domestic Dashboard, hotwords, and map: not modified.
- Production database: not written or migrated.
- Foreign sources: not enabled.
- Automatic scheduling/risk/event/alert evaluation: not enabled.
- Real RSS, external AI, proxy, and notification: not called.
- External notifications: not sent.
- Foreign map: not implemented; intentionally deferred.
