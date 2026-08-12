# YQ Next-Phase Delivery Report

Date: 2026-08-11

## Recommendation

`GO WITH RISKS`

The requested code paths are implemented and the running application passed the browser smoke checks below. Release should wait for an isolated deployment migration and a successful CI/test-database run; the local pytest command exceeded its 124-second execution limit during application startup.

## Baseline

- Baseline report: `C:\Users\Administrator\Desktop\YQ\BASELINE_FREEZE_REPORT.md`
- Readiness record: `C:\Users\Administrator\Desktop\YQ\IMPLEMENTATION_READINESS.md`
- Read-only database snapshot: `C:\Users\Administrator\Desktop\YQ\runtime\baseline_20260811_095157\opinion_db.dump`
- Baseline counts: 3 users, 4 roles, 56 permissions, 55 data sources, 40 foreign opinions, 0 foreign events, 1 foreign alert, 1 foreign rule.

## Implemented

- Current-user password change API at `POST /api/users/me/password`, with old-password, length, confirmation, and unchanged-password validation. Audit records contain reason codes and no password values. The response requires re-login; the frontend clears the token and redirects to login.
- Foreign collection permissions `foreign:sources:collect` and `foreign:sources:collect_all`, including migration `backend/alembic/versions/foreign_source_5h_next_phase.py`.
- Backend-approved foreign source scope at `GET /api/foreign/sources/approved`; the workspace no longer relies on fixed IDs.
- Duplicate manual collection protection via task deduplication and 409 responses.
- Foreign-only scheduled collection state and status endpoint. The schedule is opt-in and defaults to disabled; it filters `enabled`, `schedule_enabled`, and `is_foreign` sources and records scheduled runs.
- Unified alert center tabs for domestic alerts, foreign alerts, and foreign alert rules, with foreign evaluation and permitted acknowledge/resolve/suppress actions.
- Password entry point and dialog in `frontend/src/components/AppLayout.vue`.

## Verification

- `python -m compileall -q backend/app`: passed.
- `npm run build`: passed (Vite production build).
- `GET http://127.0.0.1:8000/health`: HTTP 200.
- Task deduplication assertion: passed (`DuplicateTaskError` for an equivalent running task).
- Browser: existing authenticated session opened the password dialog; `/alerts` showed foreign alert and foreign rule tabs with live data; `/foreign` showed backend-provided source names and both collection controls.
- Browser evidence:
  - `C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase\foreign_workspace_after.png`
  - `C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase\alerts_unified_after.png`

## Risks and gaps

1. **High**: `pytest` focused invocation (`tests/test_rbac_hardening.py -k ...`) did not finish within 124 seconds during application/test-database startup. CI or a healthy isolated PostgreSQL test instance must run the complete suite before release.
2. **High**: the new permission migration has not been applied to the current production-like database. Apply it only through the deployment migration process, then verify the permission matrix for non-admin roles.
3. **Medium**: automatic RSS -> risk -> event -> alert execution was implemented behind default-off configuration but was not enabled against a live test source in this pass. Validate it in an isolated environment with a stable RSS fixture.
4. **Medium**: JWTs are not server-side revoked by password change; the frontend clears the token and forces re-login. Existing tokens remain valid until normal expiry.
5. **Low**: the existing health test expects the older exact response shape and should be updated to assert `status == ok` while allowing discovery metadata.

## Changed files

- `backend/app/api/users.py`
- `backend/app/schemas/user.py`
- `backend/app/api/foreign.py`
- `backend/app/core/task_manager.py`
- `backend/app/core/config.py`
- `backend/app/core/scheduler.py`
- `backend/app/services/foreign_collection_service.py`
- `backend/alembic/versions/foreign_source_5h_next_phase.py`
- `frontend/src/components/AppLayout.vue`
- `frontend/src/views/ForeignWorkspace.vue` (backend-driven source scope and collection permission wiring already present in the working baseline)
- `frontend/src/views/Alerts.vue`

Domestic collection, dashboard, opinion, event, alert, and user pages were not intentionally reworked. Do not perform real external writes or enable high-frequency scheduling until the migration, role matrix, and isolated RSS end-to-end run are confirmed.
# Next-phase continuation audit - 2026-08-11

## Completed in this continuation

- Replaced `frontend/src/views/Alerts.vue` with one unified center containing only `预警规则` and `预警记录`; each tab has domestic/foreign scope controls. Foreign rules support create, edit, enable, disable, delete. Foreign records support status/severity/source/time filtering, detail, history, acknowledge, resolve, and suppress. Legacy `tab=foreign` and `tab=foreign-rules` query values map to the unified tabs.
- Rebuilt `frontend/src/views/Users.vue` as a readable user-management view. Editing a user exposes password management; self-change uses `/api/users/me/password` with old/new/confirmation fields, while administrator reset uses `/api/users/{id}/reset-password` without an old password.
- `frontend/src/views/ForeignWorkspace.vue` now loads approved sources from `/foreign/sources/approved`, has explicit selected-source collection, a separate full-collection action, scheduler state, a source-management tab, and per-source schedule controls. Legacy foreign alert tabs redirect to `/alerts`.
- Manual foreign collection now generates one batch ID before task submission and returns the same ID used by the worker and collection runs.
- Scheduler source timing advances after a successful pipeline return; failed runs remain retryable and publish an explicit failed/ retryable state.
- `frontend/vite.config.js` uses the explicit local backend address `127.0.0.1:8000` for development proxying.

## Verification

- `frontend`: `npm run build` PASS.
- Backend syntax: `python -m compileall -q app` PASS.
- Focused tests: `tests/test_health.py` and `tests/test_foreign_collection_scope.py`: `6 passed`.
- Isolated password API smoke: PASS for wrong-old, too-short, success/new login, admin reset, ordinary-user `403`; temporary test users removed.
- `/health`: live response contains `status=ok` (the health test now asserts only this stable contract).
- Browser evidence captured with the authenticated local app session:
  - `C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase-20260811_134619\alerts-foreign-records.png`
  - `C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase-20260811_134619\alerts-foreign-rules.png`
  - `C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase-20260811_134619\foreign-dashboard-scheduler.png`
  - `C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase-20260811_134619\system-users.png`
  - `C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase-20260811_134619\acceptance-login-failure.png`
- The browser verified `/foreign?tab=alerts` redirects to `/alerts?tab=records&scope=foreign` and the unified foreign record is visible. The fresh acceptance origin correctly rejected the README-era administrator password; no password reset was attempted.

## Isolated database audit

- Test PostgreSQL is `127.0.0.1:5433/opinion_test`; production-like `5432` was not written.
- Read-only counts from the isolated database: alembic revision `foreign_effective_risk_1`, users `1`, roles `0`, permissions `35`, foreign-marked sources `7`.
- Alembic head is `foreign_effective_risk_1`. The repository safety gate refused generic `alembic current/upgrade` because the workspace `.env` baseline expects the production database fingerprint while the isolated test database has a different identity and only two opinions. This is an environment-gate blocker, not a production migration attempt.

## Remaining gaps / release recommendation

- Full pytest collection remains blocked by the pre-existing missing `pypdf` dependency in `tests/test_report_phase3_frontend_contract.py`; the broader run also contains a stale AI fallback assertion when a DeepSeek key is configured.
- Vite dev-server acceptance could not be used because installed dependency files contain binary-corrupted bytes; production build and the isolated static/proxy acceptance server were used instead.
- Recommend `GO WITH RISKS` until the test dependency/environment gate is repaired and a fresh-origin login is run with an approved test account. No production data writes or external collection runs were performed.

## Final verification update - 2026-08-11

- Focused foreign/source/RSS/scheduler/risk suite: `209 passed`.
- `python -m compileall -q app`: PASS.
- `npm run build`: PASS (Vite production build; only existing Rollup annotation/dynamic-import warnings).
- `GET http://127.0.0.1:8000/health`: HTTP 200, `status=ok`, `collector_discovery=db_driven`.
- Alembic repository head: `foreign_schedule_defaults`.
- Updated stale frontend contract tests to assert unified Alerts routing and backend-driven source selection.
- Restored RSS collector's guarded `http_get` compatibility seam and foreign risk analysis support for both `foreign_risk_terms` and current sensitive `foreign_keywords`; failure persistence now handles exceptions before result creation.
- Full `pytest -q` remains environment-blocked during collection because `pypdf` is not installed for `tests/test_report_phase3_frontend_contract.py`.

The recommendation remains `GO WITH RISKS`: the requested implementation is verified in the focused scope, while the missing test dependency, isolated migration gate, default-off automation, and JWT expiry limitation remain release risks.
