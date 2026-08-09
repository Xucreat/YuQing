# Foreign Source Production Release and Manual Smoke Report

## Authorization and scope

- Objective file: `C:\Users\Administrator\.codex\attachments\a98848fc-251e-4b52-8d7b-57ce37e5e1a0\goal-objective.md`.
- User authorization: confirm publication and permit one bounded manual foreign collection.
- Production database: `opinion_db` at `127.0.0.1:5432`.
- Revision: `foreign_source_5g_remediation`.
- No production migration, domestic code/config/API/scheduler change, AI call, external notification, or formal foreign event confirmation was performed.

## Release

- Verified frontend build was copied to `backend/app/static`.
- Rollback backup: `backend/app/static.release-backup.20260809_174821`.
- Only the project Uvicorn on port 8000 was restarted with `backend/scripts/restart_backend.ps1`.
- `GET /health` and the served frontend entry/assets returned HTTP 200.
- API smoke covered foreign sources, opinions/detail, risk results, alerts/detail/actions, alert rules, event/candidate lists, collection runs, and safe 404/error handling.
- The production UI smoke confirmed alert detail, sanitized article detail, alert history, rule-create validation/preview, and source management. No source was edited or saved during the smoke.

## Sanitization

The article detail response was checked for `img`, `src`, `srcset`, `script`, `iframe`, `style`, `class`, `id`, event attributes, `javascript:`, `svg`, `meta`, `link`, `object`, and `embed`; none were present. The detail showed source, title, publish time, summary, cleaned body, rule analysis, AI result, rule/source snapshot, status, and history.

## One manual collection

The single production collection batch was `e8d8884a6e98472da073141588b7dd75`. The UI action submitted `source_ids: null`, so the backend processed all seven currently enabled foreign sources (54-60), rather than the narrower 57-60 subset anticipated during the gate review. This was one bounded run only; it was not retried.

| Source ID | Source | Raw fetched | Keyword-matched | Created | Duplicate | Failed | Run ID |
|---:|---|---:|---:|---:|---:|---:|---:|
| 54 | Fox News | 25 | 0 | 0 | 0 | 0 | 16395 |
| 55 | The Guardian | 45 | 1 | 0 | 1 | 0 | 16396 |
| 56 | New York Times Chinese | 20 | 5 | 0 | 5 | 0 | 16397 |
| 57 | BBC World | 32 | 1 | 0 | 1 | 0 | 16391 |
| 58 | BBC Chinese | 38 | 0 | 0 | 0 | 0 | 16392 |
| 59 | VOA Chinese | 20 | 15 | 1 | 14 | 0 | 16393 |
| 60 | DW English | 142 | 6 | 0 | 6 | 0 | 16394 |
| **Total** |  | **322** | **28** | **1** | **27** | **0** | **16391-16397** |

The only new row was `foreign_opinion_id=31` from VOA Chinese. Its rule analysis was run once (`foreign_analysis_run=9`, `foreign-rule-v1`), completed successfully, and used no AI provider.

Post-collection risk-result integrity: 31/31 foreign opinions have a completed
rule risk result; 0 are incomplete or failed.

## Event and alert gates

- Foreign event dry-run: `foreign_event_run=9`, input 1, deduplicated 1, candidates 0, created events 0, status `dry_run`.
- Formal `foreign_events`: 0. No event was fabricated or confirmed.
- Foreign alert automatic evaluation: `enabled=false`, `scheduler_registered=false`.
- Foreign event automatic aggregation: `enabled=false`, `scheduler_registered=false`.
- External notifications: `external_notifications_enabled=false`; none were sent.
- All source rows 54-60 remain `schedule_enabled=false`; `fetch_full_text=false`.

## Before/after snapshots

Foreign gate snapshot before collection: opinions 30, risk results 30, alerts 1, event candidates 0, formal events 0, event runs 8. After the one batch and rule analysis: opinions 31, risk results 31, alerts 1, event candidates 0, formal events 0, event runs 9.

The prior domestic gate snapshot was `opinions=1702`, `events=292`, `event_opinions=567`, `alert_records=37`. The final read-only snapshot is `opinions=1705`, `events=292`, `event_opinions=567`, `alert_records=37`. The three additional domestic rows have timestamps around 17:49:47-17:49:55, before the foreign batch began at 17:58:48; the foreign collection/risk/event code writes only foreign tables. Because the domestic count drifted between snapshots, domestic invariance cannot be claimed by this report and should receive a separate scheduler audit. No attempt was made to modify or roll back domestic data.

## Conclusion

- Code implementation: passed by the prior isolated regression, compile, build, and diff checks.
- Production release and read-only UI/API smoke: passed.
- One manual foreign collection: completed, bounded, 7 sources, 322 raw items, 28 matches, 1 new article, 27 duplicates, 0 failures; scope deviation (`null` versus 57-60) is recorded above.
- Rule risk analysis: passed for the single new article; AI was not called.
- Event acceptance: not achieved; there is no real formal event (`事件链路待真实候选`).
- Automatic foreign collection/event/alert automation and Phase 6 remain disabled.
