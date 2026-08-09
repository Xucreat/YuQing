# Phase Foreign-Source-Cross-Language-Candidate-Implementation

## Outcome

This phase implements a foreign-only, opt-in cross-language **candidate** path.
It never performs automatic cross-language confirmation. Production RSS, AI,
proxy, scheduler, alerts, notifications, domestic tables, and formal event
confirmation were not invoked.

Decision: **CONDITIONAL GO for isolated candidate generation and manual review;
NO-GO for cross-language automatic confirmation.**

## Production read-only snapshot

Read-only snapshot on 2026-08-09 from `opinion_db` at `127.0.0.1:5432`, revision
`foreign_source_5g_remediation`:

| Table / setting | Value |
|---|---:|
| `opinions` | 1705 |
| `events` | 292 |
| `event_opinions` | 567 |
| `alert_records` | 37 |
| `foreign_opinions` | 31 |
| `foreign_event_candidates` | 0 |
| `foreign_events` | 0 |
| `foreign_event_runs` | 10 |
| latest approved sources 57-60 | raw 229, matched 22, created 0, duplicates 22, failed 0 |

Persisted foreign article counts were: BBC World 1, DW English 6, The Guardian
1, VOA Chinese 16, New York Times Chinese 5, with no persisted Fox News or BBC
Chinese rows and two historical duplicate fixture rows. All configured foreign
sources were enabled for manual use and had scheduling disabled. All ten event
runs were foreign dry-runs; no candidate or event row existed at the snapshot.

The configuration read-only check returned:

```text
foreign_event_auto_aggregation_enabled = false
foreign_event_cross_language_enabled = false
foreign_event_cross_language_auto_confirm_enabled = false
foreign_alert_auto_evaluation_enabled = false
scheduler_registered = false for foreign event auto-aggregation
```

Domestic counts were re-queried after verification and remained unchanged.

## Changes implemented

### Normalization and language inputs

`foreign_content_sanitizer.py` now removes figures, captions, picture/source
nodes, menu/dialog/template chrome, media and script/style resources, noisy
publisher classes, and photo/publisher credit lines before analytical text is
constructed. HTML entities are decoded, URLs and resource attributes are
removed, block boundaries are preserved during filtering, and output remains
bounded plain text for language/risk/similarity logic.

`score_pair()` now computes title and content similarity independently and does
not double-count the title anchor. Existing same-language thresholds and the
72-hour window are unchanged.

### Gated cross-language candidates

`foreign_event_cross_language_enabled` and
`foreign_event_cross_language_auto_confirm_enabled` were added with defaults of
`false`. Cross-language grouping is explicitly opt-in and restricted to `en`
and `zh` rows within 72 hours. The cross-language scorer extracts only shared
Latin/entity-like tokens, retains the existing `0.40*title + 0.45*content +
0.15*time` formula and `0.55` candidate threshold, and requires shared title
evidence. It does not translate text, load a model, call AI, or use a network.

Cross-language candidates are stored as `language="mixed"`,
`review_source="manual"`, `candidate_status="candidate"`, version
`foreign-cross-v1`, and include source list, language pair, time delta, common
entities, score decomposition, threshold, opinion IDs, and a mandatory pending
reason. `confirm_candidate(..., confirmation_source="auto")` rejects mixed
candidates. The auto aggregation service rejects the cross-language auto flag
as unsupported, so the flag cannot silently enable confirmation.

Same-language grouping and automatic eligibility remain unchanged: `en`/`zh`,
confidence threshold `0.72`, at least two articles, at least two sources, and
the existing foreign-only feature gate.

### Probe/UI compatibility

Foreign source probes now expose canonical `success`, compatibility `ok`, and a
bounded status (`success`, `partial`, `failed`, or `no_valid_articles`). The
ForeignWorkspace save/test flow uses one helper that accepts the canonical
field and compatibility fallbacks, while retaining the existing
`sourceTestResult.success` contract.

## Isolated verification matrix

The fixture tests use `opinion_test` only and clean their rows after each case;
no real RSS or AI call is made.

| Case | Result |
|---|---|
| Two English sources, same event | Same-language candidate behavior remains available |
| Two Chinese sources, same event | Existing same-language path remains eligible when thresholds are met |
| One English + one Chinese source | Opt-in candidate is `mixed`, `pending`, manual-only |
| Similar topic, different event | Shared-entity and score threshold prevent a candidate |
| Single-source multiple articles | Source-count gate prevents automatic confirmation |
| Duplicate URL/content hash | Canonicalization removes duplicate input |
| Low similarity | No candidate |
| Time delta over 72 hours | Pair rejected |
| Chinese brands/names/acronyms | Language remains `zh` unless genuine prose is mixed |
| NYT HTML figure/caption/image/script/template | Media/template text removed; article text retained |

The cross-language fixture also verifies that no `ForeignEvent` is created and
that enabling the unsupported auto-confirm flag raises a permission error.

## Test results

Passed:

- `tests/test_foreign_event_cross_language_candidate.py`: **4 passed**
- Existing UI/probe contract regression: **passed**
- `python -m compileall -q app tests`: **passed**
- `frontend npm run build`: **passed**
- `git diff --check`: **passed** (only existing line-ending warnings)

The complete foreign suite passed **192/192** in the isolated test environment
with scheduler and alert evaluation disabled for the test process. No failing
assertion was suppressed or edited.

## Architecture and next stage

1. Keep same-language auto-confirmation policy and its current thresholds; do
   not enable it in production without the existing approval gate.
2. Keep cross-language generation behind `foreign_event_cross_language_enabled`
   and allow only pending/manual review.
3. Keep both flags default `false`; automatic cross-language confirmation is not
   implemented and must remain disabled.
4. Reuse `ForeignEventCandidate`, `ForeignEvent`, `ForeignEventOpinion`, and
   `ForeignEventRun` with versioned evidence initially. Add a dedicated model
   only if reviewer labels or model-version telemetry outgrow the JSON evidence
   contract.
5. Add foreign-only UI evidence panels and language-pair filters before any
   production candidate persistence is approved.
6. Build a labeled Chinese/English corpus and benchmark lexical/entity,
   multilingual embedding, and translation approaches offline. Measure
   precision, recall, false merges, latency, privacy, and reproducibility.
7. Continue read-only evaluation of China-focused English and Chinese sources;
   source additions require separate approval and remain manual/schedule-off.

No domestic code path, domestic table, scheduler, alert, dashboard, map,
hotword, or notification path is required for this architecture. The phase does
not create production candidates/events and does not enter Phase 6 automation.
