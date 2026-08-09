# Phase Foreign-Source-5G Remediation: Alert and Event Acceptance

## Execution

- Execution time: 2026-08-09T01:33:45+08:00
- Scope: code remediation, isolated test database validation, frontend build, and production read-only audit.
- Production writes: none.
- Real RSS, AI, proxy, external notification, scheduler, and production alert evaluation: none in this remediation run.

## Production Read-Only Baseline

- Database: `opinion_db` on `127.0.0.1:5432`.
- Current revision: `foreign_source_5a`.
- Repository target head: `foreign_source_5g_remediation`.
- Foreign sources: `foreign_fox_news`, `foreign_guardian`, and `foreign_nyt_chinese` are all `enabled=true`, `schedule_enabled=false`.
- Domestic settings: `collector_schedule_enabled=true`, `alert_eval_enabled=true`, `collector_schedule_mode=per_source`.
- Foreign automatic gates: alert auto evaluation `false`; event auto aggregation `false`.
- Foreign counts: opinions 8, risk results 8, AI results 1, candidates 0, events 0, alert rules 1, alerts 0.
- Foreign automatic runs: event 0, alert 0.
- Domestic snapshot: opinions 1702, events 292, event_opinions 567, alert_records 37.
- Uvicorn health check: `http://127.0.0.1:8000/health` returned HTTP 200.

The production revision remains `foreign_source_5a`; the remediation migration was not applied. No production source, rule, event, alert, or scheduler setting was changed.

## Remediation Implemented

- Added an independent `foreign_alert_auto_evaluation_enabled` gate, defaulting to false.
- Added `ForeignAlertService.auto_evaluate()` with `run_type=auto`; it is not registered with the domestic scheduler.
- Preserved rule-first alert evaluation. AI can be used as a `risk_score` fallback only when its current admission is `included`.
- Shared deduplication and cooldown handling prevents rule and AI paths from creating duplicate alerts for the same rule/article bucket.
- Added read-only foreign alert auto-evaluation status API.
- Added automatic foreign event aggregation behind its existing independent gate, with same-language, high-confidence, multi-source eligibility.
- Automatic event confirmation and candidate updates are committed as one transaction. Failure rolls back event/candidate writes and records a sanitized failed auto run.
- Added read-only foreign event auto-aggregation status API.
- Extended foreign event and alert metadata for `auto` versus `manual` provenance.
- Added isolated tests for rule/AI alert paths, admission filtering, default-off gates, event eligibility, mixed-language pending candidates, domestic table isolation, rollback sanitization, and concurrent alert insertion.
- Added a database-level unique deduplication index and PostgreSQL `ON CONFLICT DO NOTHING` handling for concurrent foreign alert evaluation.
- Extended the foreign workspace data contract and view with AI admission actions/history, automatic gate status, event review/confirmation provenance, event evidence, and alert evaluation source/AI result details.

## Changed Files

- `backend/alembic/versions/foreign_source_5g_remediation.py`
- `backend/app/core/config.py`
- `backend/app/models/foreign_alert.py`
- `backend/app/services/foreign_alert_service.py`
- `backend/app/services/foreign_event_auto_aggregation_service.py`
- `backend/app/api/foreign_alerts.py`
- `backend/app/api/foreign_events.py`
- `backend/tests/test_foreign_source_5g_remediation.py`
- `frontend/src/views/ForeignWorkspace.vue`

## Isolated Migration Validation

Test database: `127.0.0.1:5433/opinion_test`, with `DB_IDENTITY_CHECK=off`.

- `alembic downgrade foreign_source_5a`: passed after making downgrade constraint removal tolerant of databases created with an earlier copy of the migration.
- `alembic upgrade foreign_source_5g_remediation`: passed.
- `alembic current`: `foreign_source_5g_remediation`.
- Foreign tables, columns, indexes, and constraints were exercised by the migration and ORM tests.
- The test database was the only database modified by migration commands. Known test-created auto-run rows were removed from the isolated test database before the final round-trip; no production data was touched.

## Test Results

- Foreign focused regression: **154 passed**.
- New remediation tests: **7 passed**.
- The final frontend table pass aligned the candidate/event provenance columns with their headers and empty-state spans.
- Python compile: passed with `python -m compileall -q app tests`.
- Frontend build: passed with `npm run build`.
- `git diff --check`: passed.
- Foreign workspace API paths remain under `/api/foreign/*`.

Domestic focused regression was run without changing domestic code or assertions. It reported 10 existing failures in `test_alert_operation.py`, `test_events.py`, `test_collector.py`, and `test_phase1_risk_model.py`. The failures concern the pre-existing viewer role seed, domestic event model/async aggregation behavior, mock collector `region_kw` compatibility and expected volume, and domestic keyword weights. They are unrelated to the remediation files and were not masked or modified.

## Isolation and Residual Risk

- Production domestic counts were unchanged in the read-only before/after audit.
- No production foreign event or alert was fabricated.
- Automatic foreign alert evaluation and automatic foreign event aggregation remain disabled.
- No external notification adapter is called by the foreign alert path.
- Production cannot claim the new remediation schema or runtime path is live until `foreign_source_5g_remediation` is separately approved and applied. The production database remains on `foreign_source_5a`.
- Production AI result and the existing production rule remain from the prior phase; this run did not re-evaluate them.
- Domestic regression failures remain open and should be triaged separately.

## Rollback

- No production rollback was needed because no production write occurred.
- For the isolated test database, the validated migration path is `foreign_source_5g_remediation -> foreign_source_5a` and back to `foreign_source_5g_remediation`.
- Production rollback must use the recorded backup and an approved recovery procedure; a blind production downgrade is not recommended.

## Next-Phase Manual Acceptance Gate

Before production manual acceptance, obtain explicit confirmation for each item:

- production backup is complete and the target database identity is re-verified;
- apply `foreign_source_5g_remediation` to production;
- inspect the migration result and confirm domestic table/data snapshots are unchanged;
- select the bounded foreign article/event samples and confirm whether real foreign AI data may be sent;
- confirm the exact foreign alert rule IDs and whether real in-app evaluation is permitted;
- keep foreign automatic collection, automatic event aggregation, automatic alert evaluation, and external notifications disabled;
- confirm that any real acceptance actions are limited to `foreign_*` tables and in-app audit records.

No production migration, real foreign alert evaluation, automatic task, or external notification is authorized by this remediation report.

## Conclusion

- Alert dual-path remediation: **isolated acceptance passed; production deployment pending**.
- Automatic event remediation: **isolated acceptance passed; production deployment pending**.
- Production foreign AI/event/alert formal acceptance: **not completed in this remediation run**.
- Domestic isolation: **read-only production snapshot unchanged; focused domestic regression still has 10 unrelated failures**.
- Phase 6: **not permitted**. Automatic foreign collection, risk, event, alert evaluation, and external notification remain disabled.
