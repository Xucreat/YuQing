# Phase Foreign-Source-5G Production Manual E2E Acceptance

## 1. Execution Summary

- Execution date: 2026-08-09 (Asia/Shanghai)
- Production database: `opinion_db` on `127.0.0.1:5432`
- Production migration before this phase: `foreign_source_5a`
- Production migration after this phase: `foreign_source_5g_remediation` (head)
- Production backup confirmed before migration:
  `runtime/foreign_source_5f/opinion_db_before_foreign_source_5a_20260808_222958.dump`
- Scope: one real AI result was reused, one real foreign alert evaluation was executed, and no alert state transition was performed.
- Phase 6: **not permitted**.

The user explicitly authorized the production migration, frontend publication, one real AI analysis for `foreign_opinion_id=8`, creation and enablement of the approved alert rule, and one real in-app alert evaluation with `dry_run=false`. No external notification was authorized or sent. The mixed-language, single-source, confidence `0.49` event candidate was explicitly not confirmed.

## 2. Production Migration and Release

Migration file applied:

- `backend/alembic/versions/foreign_source_5g_remediation.py`

Validation performed in the isolated database `127.0.0.1:5433/opinion_test`:

- `foreign_source_5a -> foreign_source_5g_remediation`: passed
- downgrade/upgrade round trip: passed
- foreign tables, indexes, constraints, and permissions: passed
- remediation tests: `7 passed`
- foreign focused regression: `154 passed`

Production result:

- `alembic current`: `foreign_source_5g_remediation`
- `alembic heads`: `foreign_source_5g_remediation`
- No production downgrade was executed.
- The migration added the foreign AI alert admission and admission-action tables, event and candidate provenance fields, AI alert provenance fields, and the foreign alert deduplication index. It did not alter domestic table definitions.

Frontend and service release:

- `frontend/dist` was published to `backend/app/static`.
- Static backup: `backend/app/static.bak.5g_publish_20260809_`
- 8000 Uvicorn was restarted as authorized.
- `GET http://127.0.0.1:8000/health`: HTTP 200, `status=ok`.

## 3. Runtime Configuration and Source Isolation

The three production sources remain:

| Source | Enabled | Schedule enabled | Collector | Full text |
|---|---:|---:|---|---:|
| Fox News | true | false | `app.collectors.foreign_rss.ForeignRSSCollector` | false |
| The Guardian | true | false | `app.collectors.foreign_rss.ForeignRSSCollector` | false |
| 纽约时报中文网 | true | false | `app.collectors.foreign_rss.ForeignRSSCollector` | false |

Global domestic settings were unchanged:

- `collector_schedule_enabled=true`
- `alert_eval_enabled=true`
- `collector_schedule_mode=per_source`

Foreign automatic gates remain closed:

- foreign alert automatic evaluation: `enabled=false`, `scheduler_registered=false`
- foreign event automatic aggregation: `enabled=false`, `scheduler_registered=false`
- external notifications: disabled
- no scheduled foreign run was created by this phase

The foreign detail UI continues to use `/api/foreign/*` endpoints. Foreign map functionality remains unimplemented; source distribution remains the supported replacement.

## 4. Production AI Acceptance

Authorized scope:

- Article: `foreign_opinion_id=8`
- Source: 纽约时报中文网
- Title: `新西兰外长攻击华裔议员，中国提出正式抗议`
- Real AI calls: 1
- Article content was sent to the authorized external AI service.

Result:

- `foreign_ai_results.id=1`
- `foreign_analysis_runs.id=5`
- `status=completed`, `is_current=true`
- model version: `foreign-ai-v1`
- sentiment: `negative`
- AI risk score: `75`
- AI result and analysis run were written only to foreign tables.
- Production detail API returned HTTP 200 and displayed the system rule result and AI result together.

AI alert admission was explicitly approved and recorded:

- `foreign_alert_admissions.id=1`
- AI result: `foreign_ai_result_id=1`
- transition: `excluded -> included`
- actor: user `1`
- admission audit action: recorded

**AI manual acceptance: passed.**

## 5. Production Foreign Event Acceptance

The authorized event operation was candidate reconstruction only:

- `ForeignEventService.rebuild_candidates(dry_run=true)`
- `foreign_event_runs.id=6`
- scope: `foreign`
- input articles: `8`
- candidates: `1`
- candidate articles: `2`
- sources: `1`
- language: `mixed`
- confidence: `0.49`

The candidate was not persisted or confirmed because it is mixed-language, single-source, and below the accepted confidence level. No threshold or algorithm was changed.

Current production event state:

- `foreign_event_candidates=0`
- `foreign_events=0`
- `foreign_event_opinions=0`
- domestic `events` and `event_opinions` were not written

**Formal foreign event acceptance: not passed. The deployed event chain remains dry-run only.**

## 6. Production Foreign Alert Acceptance

Only the previously approved and enabled rule was used:

| Field | Value |
|---|---|
| Rule ID | `1` |
| Name | 外网高风险分数告警 |
| Type | `risk_score` |
| Condition | `{"threshold": 70}` |
| Severity | `high` |
| Cooldown | `3600` seconds |
| Enabled | true |
| Notification | in-app only; no external notification |

Preflight dry-run:

- `foreign_alert_runs.id=5`
- status: `dry_run`
- predicted trigger count: `1`
- `foreign_alerts` remained `0` during the dry-run

Authorized real evaluation:

- API: `POST /api/foreign/alerts/evaluate`
- payload: `{"dry_run": false, "max_items": 200}`
- `foreign_alert_runs.id=6`
- status: `success`
- processed: `1`
- triggered: `1`
- deduplicated: `0`
- suppressed: `0`
- failed: `0`

Created alert:

- `foreign_alerts.id=1`
- rule: `foreign_alert_rules.id=1`
- `foreign_opinion_id=8`
- `foreign_ai_result_id=1`
- `foreign_alert_admission_id=1`
- `evaluation_source=ai`
- risk score: `75`
- status: `triggered`
- severity: `high`
- alert detail API: HTTP 200
- alert actions: `0`

The alert list and detail APIs show the AI provenance, rule snapshot, matched condition, article, source, and cooldown deduplication key. No email, SMS, webhook, or other external notification was sent.

**Real foreign alert evaluation: passed.**

**Alert handling acceptance: pending.** No acknowledge, resolve, or suppress action was executed because the current authorization covered evaluation only, not an alert state transition. The required action audit record therefore does not yet exist.

## 7. Data Isolation Snapshot

Current production counts after this phase:

| Table | Count |
|---|---:|
| `foreign_opinions` | 8 |
| `foreign_risk_results` | 8 |
| `foreign_ai_results` | 1 |
| `foreign_event_candidates` | 0 |
| `foreign_events` | 0 |
| `foreign_alert_rules` | 1 |
| `foreign_alerts` | 1 |
| `foreign_alert_runs` | 6 |
| `foreign_alert_actions` | 0 |

Domestic before/after snapshot comparison:

| Table | Baseline | Current | Result |
|---|---:|---:|---|
| `opinions` | 1702 | 1702 | unchanged |
| `events` | 292 | 292 | unchanged |
| `event_opinions` | 567 | 567 | unchanged |
| `alert_records` | 37 | 37 | unchanged |

The production alert response contains only foreign identifiers and does not create rows in domestic opinions, events, event links, or alert records. Foreign execution logs use `scope='foreign'` where applicable.

**Domestic isolation: passed.**

## 8. Verification Results

- Production migration: passed, current/head `foreign_source_5g_remediation`
- Isolated migration round trip: passed
- Remediation tests: `7 passed`
- Foreign focused tests: `154 passed`
- Python compile: passed
- Frontend build: passed
- `git diff --check`: passed
- Production detail API: HTTP 200
- Foreign alert list/detail/actions APIs: HTTP 200
- 8000 Uvicorn health check: HTTP 200
- Foreign automatic alert gate: off
- Foreign automatic event gate: off
- External notification status: off

Test connection note: the first remediation test invocation used the fixture
default `localhost:5433` and timed out during test startup. A direct connection
check showed the isolated PostgreSQL instance was reachable at IPv4
`127.0.0.1:5433/opinion_test` and no production connection was involved. The
owned timed-out test process was stopped, the isolated fixture residue was
cleaned by its `fixture_5g_*` / `Phase 5G *` identifiers only, and the same
tests were rerun with an explicit IPv4 test URL: `7 passed` in 0.92 seconds.

Known unrelated domestic focused regression failures remain from the prior acceptance work. No domestic code, domestic assertion, or domestic production data was modified to mask them. They are not counted as foreign acceptance failures, but they remain a release risk for any broader domestic regression claim.

## 9. Failure Items and Residual Risks

1. No formal production foreign event exists because the only candidate was explicitly rejected for manual confirmation.
2. No alert action audit exists because no acknowledge, resolve, or suppress action was authorized or executed.
3. Therefore the strict condition “AI result + confirmed event + real alert + real alert action” is not satisfied.
4. Foreign automatic collection, AI, risk, event, and alert automation remain disabled by design.
5. External notifications remain disabled. The alert is an in-app record only.
6. The AI result contains externally processed article content and should continue to be handled under the approved data-use boundary.

## 10. Rollback and Recovery

- Do not use a blind production Alembic downgrade as the default rollback.
- To stop future foreign alert creation, disable rule `1` through the foreign alert rule API and preserve the audit record.
- The production recovery backup is:
  `runtime/foreign_source_5f/opinion_db_before_foreign_source_5a_20260808_222958.dump`
- Static release backup is:
  `backend/app/static.bak.5g_publish_20260809_`
- Database restoration or migration recovery requires a fresh identity check, backup verification, and an approved recovery operation. The newly created foreign AI/admission/alert rows must be included in the recovery decision.

## 11. Final Conclusion

| Acceptance item | Conclusion |
|---|---|
| AI manual acceptance | **Passed** |
| Formal foreign event acceptance | **Not passed; dry-run only** |
| Real foreign alert evaluation | **Passed** |
| Alert acknowledge/resolve/suppress acceptance | **Pending explicit authorization and execution** |
| Domestic isolation | **Passed** |
| Automatic scheduling | **Closed** |
| External notifications | **Not sent; disabled** |
| Phase 6 | **Not allowed** |

The accurate overall conclusion is:

> **Phase 5G partially completed: production AI acceptance passed, real foreign in-app alert evaluation passed, the event chain remains dry-run only, and alert handling remains pending. This is not a full “Phase 5G production AI, event, and alert manual acceptance passed” conclusion.**
