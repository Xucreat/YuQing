# Phase Foreign-Source-5G Production UI and Source Expansion

## Execution Scope

- Execution date: 2026-08-09 (Asia/Shanghai).
- Production database: `opinion_db` on `127.0.0.1:5432`.
- Production revision before and after release: `foreign_source_5g_remediation`.
- No production migration was needed or executed.
- The initial release stopped at the explicit confirmation gate. After the
  user's affirmative confirmation, four tested foreign sources were saved and
  one bounded manual production collection was run; evidence is recorded below.
- No real AI call, automatic collection/event/alert evaluation, or external
  notification was performed.

## Isolated Validation

Test database identity was `opinion_test` on `127.0.0.1:5433`, distinct from
`opinion_db`. The isolated checks passed:

- Foreign/UI/source-expansion/remediation focused tests: **24 passed**.
- `python -m compileall -q app tests`: passed.
- `npm run build`: passed.
- `git diff --check`: passed.
- `foreign_source_5a -> foreign_source_5g_remediation` downgrade and upgrade:
  passed; the isolated database ended at `foreign_source_5g_remediation`.
- Migration tables, foreign alert indexes/deduplication constraints, and
  isolated snapshots were checked after upgrade.
- Sanitizer regressions cover `img/src`, `srcset`, `style`, `class`, `id`,
  `script`, `iframe`, `onclick`, `onerror`, `javascript:` links, the NYT
  Chinese example, and foreign opinion/event API boundaries.

## Production Release

The existing deployment method `backend/_d.py` copied the verified
`frontend/dist` build into `backend/app/static`:

- Published files: 44.
- Static rollback backup: `backend/app/static.bak.5g_prod_ui_source_20260809`.
- Uvicorn was restarted only for this project with the existing `0.0.0.0:8000`
  binding; the final listener is the single project process on port 8000.
- `GET /health`: HTTP 200, `status=ok`, `collector_discovery=db_driven`.
- Served root: HTTP 200, entry bundle `/assets/index-Ci6-25_E.js`, HTTP 200.

The restarted backend loaded the verified foreign implementation from
`backend/app/api/foreign.py`, `backend/app/api/foreign_alerts.py`,
`backend/app/api/foreign_events.py`, `backend/app/api/admin_data_sources.py`,
`backend/app/collectors/foreign_rss.py`,
`backend/app/services/foreign_collection_service.py`, and
`backend/app/services/foreign_content_sanitizer.py`.

Authenticated read-only smoke checks using the existing admin identity:

| Endpoint | Result |
|---|---|
| `/api/foreign/sources?size=20` | 200; 3 existing sources, all `enabled=true`, `schedule_enabled=false` |
| `/api/foreign/opinions/8/detail` | 200; body contains no image/script/iframe/event markup |
| `/api/foreign/alerts?size=20` | 200; 1 alert |
| `/api/foreign/alerts/1` | 200; rule, snapshot, evaluation source, article, event field, and actions present |
| `/api/foreign/alert-rules?size=20` | 200; 1 rule |
| `/api/foreign/events?size=20` | 200; 0 formal events |
| `/api/foreign/dashboard/summary?days=7` | 200 |
| `/api/foreign/dashboard/sources?days=7` | 200 |

Foreign automatic gates remained closed:

- Alert automatic evaluation: `enabled=false`, `scheduler_registered=false`.
- Event automatic aggregation: `enabled=false`, `scheduler_registered=false`.
- External notifications: disabled.

## Candidate Probe Results

The four approved candidates were probed again through
`ForeignRSSCollector.probe()` with bounded limits, no database session, no
`CollectorRun`, no `foreign_opinions` write, and no source configuration save.

| Source | Feed | Result |
|---|---|---|
| BBC World | `https://feeds.bbci.co.uk/news/world/rss.xml` | HTTPS/DNS/HTTP 200/XML; 32 raw, 20 valid, 20 titles, 20 summaries, 20 publish times, 1 keyword hit, 0 duplicate URLs, EN 20 |
| BBC Chinese | `https://feeds.bbci.co.uk/zhongwen/simp/rss.xml` | HTTPS/DNS/HTTP 200/XML; 38 raw, 20 valid, 20 titles, 20 summaries, 20 publish times, 0 keyword hits, ZH 13 / mixed 7 |
| VOA Chinese | `https://www.voachinese.com/api/` | HTTPS/DNS/HTTP 200/XML; 20 raw/valid, 20 titles/summaries/publish times, 0 keyword hits, ZH 8 / mixed 12 |
| DW English | `https://rss.dw.com/rdf/rss-en-all` | HTTPS/DNS/HTTP 200/XML; 142 raw, 20 valid, 20 titles/summaries/publish times, 1 keyword hit, 0 duplicate URLs, EN 20 |

CNN remains unsaved because HTTPS/TLS was not accepted. Reuters, AP News, and
DW Chinese remain unavailable under the previously recorded probe results.

## Coverage and Event Validation

The four feeds were fetched in memory only using the existing foreign collector:

- BBC World: 1 matched article.
- BBC Chinese: 0 matched articles.
- VOA Chinese: 0 matched articles.
- DW English: 6 matched articles.
- Total: 7 articles, 7 unique URLs, 0 duplicate URLs.
- No lexical cross-source event candidate was produced (`0` candidates).
- No production `foreign_events` row was created or fabricated.
- The correct event conclusion remains: **事件链路待真实候选**.

This is pre-save/in-memory validation, not production manual collection or
formal event confirmation. No rule-risk rows were generated for the new
sources because no new source was collected into production.

## Domestic Isolation Snapshot

Read-only production counts after release remained:

| Table | Count |
|---|---:|
| `opinions` | 1702 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `foreign_opinions` | 8 |
| `foreign_alerts` | 1 |
| `foreign_events` | 0 |

No domestic table, domestic API, domestic scheduler setting, or domestic test
assertion was changed by this phase.

## Confirmation Gate

The required confirmation question is:

> 是否确认保存通过测试的 BBC World、BBC Chinese、VOA Chinese、DW English，并对这些来源执行有限次数生产人工采集？

The affirmative response was subsequently received on 2026-08-09. The
post-confirmation production actions and their evidence are recorded below.

## Final Status

| Item | Status |
|---|---|
| Production UI/backend release | Passed |
| Candidate source probes | Passed for four listed sources |
| Save-before-test gate | Implemented and isolated-tested |
| Production source save | Completed after explicit confirmation |
| Production manual collection/risk analysis | Completed: 22 new opinions, 22 rule results |
| Event dry-run | Completed: 3 pending previews, 0 persisted candidates/events |
| Formal foreign event | None; not fabricated |
| Automatic scheduling | Closed |
| External notifications | Disabled |
| Phase 6 automation | Not allowed |

## Post-confirmation Production Execution (2026-08-09)

The user explicitly confirmed saving the four tested sources and running a
bounded production manual collection. The confirmation was received after the
pre-save gate; no production source write or collection occurred before it.

### Test-then-save and Source Configuration

Each source was tested through `POST /api/foreign/sources/test` immediately
before creation. All four tests returned HTTP success, XML parsed successfully,
and 20 valid title/URL items were available within the bounded test window:

| Source | ID | Feed | Valid | Keyword hits | Saved |
|---|---:|---|---:|---:|---|
| BBC World | 57 | `https://feeds.bbci.co.uk/news/world/rss.xml` | 20 | 1 | yes |
| BBC Chinese | 58 | `https://feeds.bbci.co.uk/zhongwen/simp/rss.xml` | 20 | 0 | yes |
| VOA Chinese | 59 | `https://www.voachinese.com/api/` | 20 | 15 | yes |
| DW English | 60 | `https://rss.dw.com/rdf/rss-en-all` | 20 | 1 | yes |

All saved rows use `is_foreign=true`, the `foreign_rss` collector,
`enabled=true`, `schedule_enabled=false`, `fetch_full_text=false`, and
`max_items=20`. They were not registered with the domestic registry or
scheduler.

### Bounded Production Manual Collection

One manual collection batch was run for source IDs 57-60:

- batch: `5b6ac032bdd046bbb6170b5e386d7d43`
- scope: `foreign`
- sources: 4
- fetched raw: 232
- matched: 22
- created in `foreign_opinions`: 22
- duplicate URLs/content: 0
- failed sources: 0

Per-source results were BBC World `32/1/1`, BBC Chinese `38/0/0`, VOA Chinese
`20/15/15`, and DW English `142/6/6` for `fetched/matched/created`. The 22
stored URLs are all unique. No domestic `opinions`, `events`, `event_opinions`,
or `alert_records` rows were written.

### Rule Risk Analysis

The existing foreign rule engine (model version `foreign-risk-v1`) analyzed all
22 new opinions in one batch. The run completed with `processed=22`,
`success=22`, `failed=0`; all 22 current results are `analysis_status=completed`
and `risk_level=low`. Language distribution is EN 7, mixed 13, and ZH 2.
No real AI or external model call was made.

### Foreign Event Aggregation Dry-run

`POST /api/foreign/events/rebuild` was executed with `dry_run=true` and the 22
new opinion IDs. The run recorded `input=22`, `deduplicated=22`,
`candidate_previews=3`, `linked=11`, and `created_event_count=0`. All three
previews were single-source VOA groupings with mixed language and confidence
`0.49`; they do not meet the same-language, high-confidence, multi-source
acceptance gate. The previews remain pending and no `foreign_events` or formal
candidate row was created. The correct conclusion is **event chain pending a
real qualifying candidate**; formal event confirmation was not performed.

### Final Production Snapshot and Gates

Read-only checks after collection and analysis:

| Table/setting | Value |
|---|---:|
| Alembic revision | `foreign_source_5g_remediation` |
| Domestic `opinions` | 1702 |
| Domestic `events` | 292 |
| Domestic `event_opinions` | 567 |
| Domestic `alert_records` | 37 |
| `foreign_opinions` | 30 |
| `foreign_alerts` | 1 |
| `foreign_events` | 0 |

Foreign automatic alert evaluation remains disabled and unregistered;
foreign automatic event aggregation remains disabled and unregistered; and
external notifications remain disabled. The global domestic scheduler setting
was not changed (it remains enabled for the domestic pipeline), while every
foreign source has `schedule_enabled=false`.

The production UI/backend release is complete, source expansion and bounded
manual validation are complete, and formal foreign event confirmation remains
outstanding. Phase 6 automation is not authorized by this phase.
