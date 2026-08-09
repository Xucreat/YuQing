# Foreign Source Event Normalization Remediation

## Scope

This remediation is limited to the foreign pipeline. It does not change domestic
opinion, event, alert, dashboard, scheduler, or keyword logic, and it performs
no production collection, migration, AI call, notification, or source write.

## Root Cause

The foreign sanitizer was only applied at selected HTML/API boundaries. Event
and risk services still joined persisted title, summary, and body fields directly.
That allowed HTML entities, NYT layout markup, image URLs, and repeated fields to
distort script counts and lexical overlap. Language detection treated every
Latin character as evidence of `mixed`, and similarity weighted title overlap
twice. The API fixture patched a collector instance helper while the source
validation path used the module-level `requests.get` call.

## Implementation

- Added bounded foreign text normalization in
  `backend/app/services/foreign_content_sanitizer.py`.
- Entity decoding, Unicode NFKC normalization, template/navigation/resource
  removal, URL removal, whitespace and punctuation normalization, repeated
  title/summary/body suppression, and title/summary fallback are applied before
  analysis.
- Event article text, event language detection, event tokenization, risk
  analysis text, risk language detection, and similarity inputs now share the
  same normalized boundary.
- Chinese articles containing short brands, acronyms, names, and numbers remain
  `zh`; continuous English prose with Chinese remains `mixed`.
- Similarity keeps the existing lexical threshold (`0.55`), high-confidence
  threshold (`0.72`), 72-hour window, minimum two articles, minimum two sources,
  and same-language auto-confirmation gate. Title anchor overlap remains
  explainability evidence and is no longer double-weighted in the score.
- The API source-validation fixture patches the collector's actual
  `requests.get` path and asserts that no real `fixture.test` request is made.

## Regression Coverage

Added `backend/tests/test_foreign_event_normalization.py` for HTML entities,
external images/scripts, historical markup, duplicate fields, language classes,
normalized risk/event input, same-language similarity, and mixed-language
pending candidates.

The existing foreign source test now uses an isolated HTTP response fixture for
API validation. Existing event metric recomputation, duplicate suppression,
rollback, sensitive-error sanitization, UI, and source-probe tests remain in the
foreign suite.

## Verification

- Foreign source suite: `179 passed`
- Foreign normalization suite: `4 passed`
- Combined foreign verification after migration round-trip: `183 passed`
- `python -m compileall -q backend/app backend/tests`: passed
- `npm run build` in `frontend`: passed
- `git diff --check`: passed (line-ending warnings only)
- Isolated migration round-trip `foreign_source_5g_remediation -> foreign_source_5a -> foreign_source_5g_remediation`: passed
- Tests used the isolated IPv4 database
  `127.0.0.1:5433/opinion_test` with `DB_IDENTITY_CHECK=off`.

## Acceptance Boundary

Code and isolated-test verification are complete. No production migration,
backup, new-source persistence, manual collection, or automatic scheduling was
performed. A production release remains gated on explicit user approval for
those operations.

## Production Read-Only Snapshot

The read-only snapshot after verification reported:

- database `opinion_db`, `127.0.0.1:5432`, revision
  `foreign_source_5g_remediation`;
- domestic counts unchanged at `opinions=1702`, `events=292`,
  `event_opinions=567`, `alert_records=37`;
- foreign counts `foreign_opinions=30`, `foreign_event_candidates=0`,
  `foreign_events=0`, `foreign_alerts=1`, `foreign_event_runs=8`;
- seven foreign sources, all with `schedule_enabled=false`;
- foreign automatic event aggregation and automatic alert evaluation disabled.

No production write or real RSS request was performed. The code is ready for a
separate event-design review; Phase 6 automation is not enabled or proposed by
this change.
