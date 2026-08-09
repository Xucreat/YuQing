# Foreign Source Scope Fix, Domestic Audit, and Event Readiness

## Phase status

- Production database: `opinion_db` at `127.0.0.1:5432`.
- Production revision: `foreign_source_5g_remediation` (head).
- This phase has completed code changes, isolated validation, the approved production release, and one bounded manual production collection.
- The scope fix was published after creating static backup `backend/app/static.scope-fix-backup.20260809_183918` and restarting the project Uvicorn on port 8000 with `backend/scripts/restart_backend.ps1 -Port 8000 -WaitSeconds 30`.
- Production health and root checks returned HTTP 200. Production API checks confirmed that `source_ids=null` and `source_ids=[]` return HTTP 422. The served lazy bundle `ForeignWorkspace-COxOsmnU.js` contains `all_sources` and no longer submits `source_ids:null`.
- No AI call, formal event confirmation, automatic task, automatic alert evaluation, or external notification was performed.

## Domestic drift audit

The three rows corresponding to the earlier `1702 -> 1705` increase are:

| ID | Source | Created at | Publish time | External ID | Source type | Analysis |
|---:|---|---|---|---|---|---|
| 1703 | 新华网 | 2026-07-27 18:30:26.104231 | 2026-07-27 00:00:00 | null | null | completed |
| 1704 | 人民网 | 2026-07-27 18:30:40.486177 | 2026-03-17 00:00:00 | null | null | completed |
| 1705 | 人民网 | 2026-07-27 18:30:40.526932 | 2026-07-27 00:00:00 | null | null | completed |

They were created by domestic scheduled batch
`a637c0bdc55e40e597eaae3681edc109`, whose runs started at
`2026-08-09 17:49:39` and ended between `17:49:46` and `17:49:56`:

- 通山新闻: fetched 14, created 1, failed 0;
- 通山民生新闻: fetched 14, created 2, failed 0;
- all other domestic runs in that batch: created 0, failed 0.

The foreign batch began at `17:58:48` and ended at `17:59:05`. It was
therefore not time-overlapping with the domestic batch. Every row in that
foreign batch has `scope='foreign'` and `trigger_type='manual'`.

The foreign collection service imports and writes `ForeignOpinion` and
foreign-scoped `CollectorRun` records only; it does not import the domestic
`Opinion`, `Event`, `EventOpinion`, or `AlertRecord` models. No evidence of
foreign contamination was found. The domestic scheduler remains an existing
independent process and was not modified or stopped.

## Scope fix

The manual collection contract now has explicit semantics at all three
layers:

- API payload: `{ "source_ids": [..] }` is required for a selected run.
- `source_ids=null` or `source_ids=[]` is rejected with HTTP 422.
- Duplicate IDs, missing/disabled sources, and non-foreign source IDs are rejected.
- Full collection is available only through the explicit `{ "all_sources": true }` operation; combining it with `source_ids` is rejected.
- The service rejects implicit `None`/empty selection as well, preventing a direct caller from silently falling back to all enabled sources.
- The workspace's primary collection action submits `[57, 58, 59, 60]`.
- A separate “Collect all sources” action requires an explicit confirmation and submits `all_sources=true`.

No source `enabled` or `schedule_enabled` value was changed.

## Isolated validation

Test database: `127.0.0.1:5433/opinion_test` with `DB_IDENTITY_CHECK=off`.

- Scope/API/service/UI tests: `5 passed`.
- Existing foreign collection tests plus scope tests: `25 passed`.
- Foreign remediation/UI focused tests: `132 passed`.
- Full `tests/test_foreign*.py`: **188 passed**.
- `python -m compileall -q app tests`: passed.
- `npm run build`: passed.
- `git diff --check`: passed.
- Migration round-trip `foreign_source_5a -> foreign_source_5g_remediation`: passed in the isolated database.

The first test attempt using repository-default `localhost:5433` exceeded the
timeout during connection. Re-running with the explicit IPv4 test endpoint
completed successfully; no assertion was changed or masked.

The isolated tests cover selected-source forwarding, empty/null rejection,
explicit full-scope operation, non-foreign/disabled rejection, foreign-only
scope logging, domestic-table isolation, deduplication, sanitized content,
and event dry-run behavior.

## Production pre-gate snapshot

| Table/setting | Current value |
|---|---:|
| Domestic opinions | 1705 |
| Domestic events | 292 |
| Domestic event_opinions | 567 |
| Domestic alert_records | 37 |
| Foreign opinions | 31 |
| Foreign risk results | 31 |
| Foreign alerts | 1 |
| Foreign event candidates | 0 |
| Foreign formal events | 0 |
| Foreign event runs | 9 |

Sources 54-60 remain enabled but all have `schedule_enabled=false`. Foreign
automatic alert evaluation reports `enabled=false` and
`scheduler_registered=false`; foreign automatic event aggregation reports the
same; external notifications report `false`.

## Approved production collection

Exactly one production request was submitted, with no implicit full-scope fallback:

```json
{"source_ids":[57,58,59,60]}
```

- Task ID: `40afe26b692e494e83ab46aea3e5e79f`
- Service batch ID: `21fd26ff13be41939d37e3577671ca4a`
- Status: `success`; sources `4`; fetched raw `229`; matched `22`; created `0`; duplicate `22`; failed `0`.
- Collector runs `16405` (BBC World: 29/1/0/1/0), `16406` (BBC Chinese: 38/0/0/0/0), `16407` (VOA Chinese: 20/15/0/15/0), and `16408` (DW English: 142/6/0/6/0), in fetched/matched/created/duplicate/failed order.
- All four runs have `scope='foreign'`, `trigger_type='manual'`, and `status='success'`. No runs were created for sources `54`, `55`, or `56`.
- No new foreign opinions were created, so no new risk-analysis call was made. Existing foreign risk status remains `31/31 completed`.

## Event dry-run

One event rebuild dry-run was executed against the 23 existing articles from sources 57-60:

```json
{"opinion_ids":[9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31],"dry_run":true}
```

- Run ID: `10`; input `23`; deduplicated `23`; candidate previews `4`; linked articles `8`; formal events created `0`; status `dry_run`.
- Each preview was a single-source VOA group with two opinions and confidence `0.65365-0.672292`, below the current formal threshold `0.72`.
- Therefore no qualifying real event candidate exists. No formal `foreign_events` or `foreign_event_candidates` rows were written.

## Final production snapshot

| Table/setting | Final value |
|---|---:|
| Domestic opinions | 1705 |
| Domestic events | 292 |
| Domestic event_opinions | 567 |
| Domestic alert_records | 37 |
| Foreign opinions | 31 |
| Foreign risk results | 31 |
| Foreign alerts | 1 |
| Foreign event candidates | 0 |
| Foreign formal events | 0 |
| Foreign event runs | 10 |

Sources 54-60 remain `enabled=true` and `schedule_enabled=false`. Foreign alert auto evaluation reports `enabled=false`, `scheduler_registered=false`; foreign event auto aggregation reports the same; external notifications remain `false`.

Final readiness conclusion: no real qualifying candidate exists; the event chain remains pending a real candidate.
chain remains `待真实候选`. No threshold changes, fixture promotion, forced
merge, or Phase 6 automation is permitted.

## Final production conclusion (authoritative)

The scope fix is published and the single authorized four-source manual collection completed successfully. It created no new foreign opinions and no formal events. Domestic counts remained unchanged during this operation. AI, formal event confirmation, automatic tasks, automatic alert/event evaluation, and external notifications all remained disabled.
