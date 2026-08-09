# Phase Foreign-Source-5G UI and Source Expansion

## Scope and Gate

This implementation remains foreign-only. No production migration, production
data write, real RSS collection, external AI request, scheduler registration, or
external notification was executed. Existing workspace modifications and
untracked artifacts were preserved. Domestic opinions, events, alerts,
Dashboard, map, hotword, and scheduler code were not changed by this phase.

## Files and Migration

Direct implementation/test surfaces for this phase are:

- `backend/app/services/foreign_content_sanitizer.py`
- `backend/app/collectors/foreign_rss.py`
- `backend/app/services/foreign_collection_service.py`
- `backend/app/api/foreign.py`
- `backend/app/api/foreign_events.py`
- `backend/app/api/foreign_alerts.py`
- `backend/app/api/admin_data_sources.py`
- `frontend/src/views/ForeignWorkspace.vue`
- `backend/tests/test_foreign_source_5g_ui_expansion.py`

No additional schema migration was introduced solely for this UI/source-expansion
phase. The previously implemented `backend/alembic/versions/foreign_source_5g_remediation.py`
is the required foreign schema head and was validated only in the isolated test
database; it was not applied to production during this phase.

## Implemented Changes

- Added `backend/app/services/foreign_content_sanitizer.py`. Foreign RSS content
  is cleaned before foreign opinion creation and is cleaned again at all foreign
  opinion/event detail API boundaries. Script, style, iframe, object, embed,
  SVG, image, metadata, link, event, class, id, style, source, and source-set
  content is removed. Only the safe paragraph/list/emphasis/blockquote/link
  subset remains; links require `http` or `https`. Sanitizer failure falls back
  to plain text.
- Extended foreign source probes with valid-article, URL duplicate, language,
  HTTP/XML, and per-feed failure evidence. Source create and update now require
  a successful bounded probe before persistence. Probe calls do not write
  `foreign_opinions`, domestic `opinions`, or `collector_runs`.
- Added `language` to the foreign configuration allowlist so a successful
  language-aware source probe can actually pass the save gate.
- Added a foreign source language field while keeping existing source defaults
  disabled and `schedule_enabled=false`.
- Alert titles now open the foreign article or foreign event detail contract.
  The dialog shows source, title, publish time, summary, sanitized body, rule
  result, AI result, rule snapshot, evaluation source (`rule`/`ai`), status, and
  trigger metadata.
- Alert actions continue to use the existing foreign API and state-transition
  transaction. A separate history dialog shows action type, actor, time, prior
  state, new state, note, and related alert.
- Moved alert-rule CRUD to a dedicated `告警规则` tab. The modal supports name,
  type, conditions/threshold, severity, cooldown, description, enabled-state
  visibility, validation, and a JSON preview. New rules remain disabled until
  the existing enable permission/API is used.

## Sanitization Evidence

The regression fixture includes publisher `div`, `img src`, `style`, `script`,
`iframe`, `onclick`, and `javascript:` link input. The API/collector boundary
returns only the safe text and tags, keeps the HTTPS source link, removes the
image/resource URL and unsafe link, and strips all attributes. Sanitizer errors
fall back to plain text. Historical opinion, legacy `/original`, and event detail
serializers call the same backend sanitizer before returning content to the UI.

## Verification

- `python -m compileall -q app tests`: passed.
- `npm run build`: passed.
- `git diff --check`: passed.
- Isolated migration round trip `foreign_source_5a -> foreign_source_5g_remediation`
  and back: passed; isolated database ended at `foreign_source_5g_remediation`.
- Foreign focused regression plus new UI/sanitizer/source-probe tests: **24 passed** using
  `127.0.0.1:5433/opinion_test` with `DB_IDENTITY_CHECK=off`.
- The first test invocation stalled on the repository-default `localhost:5433`
  fixture address; it was stopped and rerun with the isolated IPv4 endpoint.
  No assertion was changed or failure masked. Only owned `fixture_5g_*` residue
  in the isolated test database was removed before the clean rerun.

## Source Expansion Status

A read-only bounded network audit was run directly through
`ForeignRSSCollector.probe()` with no database session, no `CollectorRun`, no
`foreign_opinions` write, and no source configuration save. DNS, HTTP/XML,
title/summary/publish-time presence, keyword hits, language recognition, URL
duplicates, and failure behavior were recorded for each feed.

| Candidate | Feed result | Evidence |
|---|---|---|
| BBC World | **Passed technically** | `https://feeds.bbci.co.uk/news/world/rss.xml`; HTTPS/DNS/HTTP 200/XML; 32 raw, 20 bounded valid, 20 titles, 20 summaries, 20 publish times, 1 keyword hit, 0 URL duplicates, EN 20 |
| BBC Chinese | **Passed technically** | `https://feeds.bbci.co.uk/zhongwen/simp/rss.xml`; HTTPS/DNS/HTTP 200/XML; 38 raw, 20 bounded valid, 20 titles, 20 summaries, 20 publish times, 0 current keyword hits, ZH 13 / mixed 7 |
| VOA Chinese | **Passed technically** | `https://www.voachinese.com/api/`; HTTPS/DNS/HTTP 200/XML; 20 raw and valid, 20 titles/summaries/publish times, 0 current keyword hits, ZH 8 / mixed 12 |
| DW English (fallback for unavailable DW Chinese feed) | **Passed technically** | `https://rss.dw.com/rdf/rss-en-all`; HTTPS/DNS/HTTP 200/XML; 142 raw, 20 bounded valid, 20 titles/summaries/publish times, 1 keyword hit, EN 20 |
| CNN World | **Conditional** | `http://rss.cnn.com/rss/edition_world.rss`; HTTP feed returned 200/XML with 29 raw and 20 valid; HTTPS endpoint timed out, so TLS acceptance is pending |
| Reuters | **Failed** | DNS resolved, but bounded request did not return usable HTTP/XML |
| AP News | **Failed** | Tested official feed host did not resolve / return usable XML; alternate `index.rss` also failed |
| DW Chinese | **Failed** | HTTPS returned an empty “no feed by that name” response |

The four technically passing candidates, plus the conditional HTTP-only CNN
sample, were fetched in memory only for coverage and event dry-run evidence:
BBC World 1 matched article, CNN 1 (conditional; HTTPS/TLS was not accepted),
BBC Chinese 0, VOA Chinese 0, and DW English 6 (8 total; 8 unique URLs; 0
duplicate URLs). One BBC/DW article pair overlapped within 72 hours; all other
source-pair overlaps were 0.
The lexical candidate scorer produced 0 cross-source topic candidates from this
bounded sample. No formal event was created, and the correct result remains
“事件链路待真实候选”. Existing isolated event tests still verify same-language,
high-confidence, multi-source candidate generation and mixed-language pending
behavior.

The production read-only isolation snapshot recorded in the referenced 5G
reports was unchanged for domestic tables: `opinions=1702`, `events=292`,
`event_opinions=567`, and `alert_records=37` before and after the foreign work.
No domestic rows, scheduler settings, or domestic API paths were written by
this phase.

These four technically passing candidates are **not saved** to the production
data-source configuration. They remain approval-gated additions because the phase explicitly
requires user confirmation before saving a new source or running bounded manual
collection. The three existing foreign sources were not modified.

## Acceptance Conclusion

| Item | Result |
|---|---|
| Code implementation | Passed |
| Isolated validation | Passed (24 focused tests, compile, build, diff check) |
| Production manual functionality | Not executed; explicit confirmation required |
| Data-source expansion | Isolated technical audit complete; production/config addition pending explicit authorization |
| Real formal foreign event | None created or fabricated |
| Automatic foreign collection/event/alert scheduling | Still closed |
| External notifications | Disabled and not sent |

Before any production action, obtain explicit confirmation for backup, required
foreign migration, saving a tested new source, and bounded manual collection.
Phase 6 automation remains out of scope.

## Production authorization addendum (2026-08-09)

The subsequent user authorization permitted publication and one bounded manual
foreign collection. The resulting production release, batch evidence, rule
analysis, event dry-run, gate status, and the recorded source-scope deviation
are documented in
`docs/Phase_Foreign_Source_Production_Release_Manual_Smoke.md`.

## Production Gate Record

No new production approval was received or used in this phase. Consequently:

| Operation | Record |
|---|---|
| Production backup | Not executed |
| Foreign migration | Not executed in production; isolated validation only |
| Save new foreign sources | Not executed; four technically passing candidates remain unsaved |
| Bounded manual collection of new sources | Not executed |
| Production data, AI, scheduler, and notifications | No writes, calls, registrations, or notifications |
