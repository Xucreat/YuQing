# Foreign Source Cross-Language Event Design Review

## Scope and decision

This review is read-only. It queried production with `SELECT` statements only,
ran the required analytical samples in memory, and did not call RSS, AI,
proxies, automatic event/alert jobs, or external notifications. No production
candidate, event, audit row, configuration, schema, or domestic row was
created or changed.

**Decision: CONDITIONAL GO for isolated implementation and labeled data
collection; NO-GO for cross-language automatic confirmation in production.**

Recommended next state:

1. Keep same-language (`en`/`zh`) high-confidence, multi-source automatic
   confirmation behind the existing disabled gate.
2. Generate cross-language candidates only when the new evidence contract is
   satisfied, with `pending` status and mandatory human review.
3. Do not enable cross-language automatic confirmation until a labeled corpus,
   offline precision/recall evaluation, and an explicit production approval
   exist.

## Production read-only snapshot

Snapshot source: `opinion_db` at `127.0.0.1:5432`, read on 2026-08-09;
Alembic revision `foreign_source_5g_remediation`.

| Item | Value |
|---|---:|
| Domestic `opinions` | 1705 |
| Domestic `events` | 292 |
| Domestic `event_opinions` | 567 |
| Domestic `alert_records` | 37 |
| Foreign `foreign_opinions` | 31 |
| Foreign `foreign_risk_results` | 31 |
| Foreign `foreign_event_candidates` | 0 |
| Foreign `foreign_events` | 0 |
| Foreign `foreign_event_opinions` | 0 |
| Foreign `foreign_event_runs` | 10 |

The 31 foreign rows include 29 rows attached to configured source IDs 54-60
and two historical fixture rows with no source ID. All seven configured
sources are `enabled=true` and `schedule_enabled=false`.

| Source | Persisted articles | Normalized language | Stored keyword presence* | Published range |
|---|---:|---|---:|---|
| Fox News | 0 | - | 0/0 | - |
| The Guardian | 1 | EN 1 | 1/1 | 2026-08-06 |
| 纽约时报中文网 | 5 | ZH 5 | 5/5 | 2026-08-03..2026-08-07 |
| BBC World | 1 | EN 1 | 1/1 | 2026-08-08 |
| BBC Chinese | 0 | - | 0/0 | - |
| VOA Chinese | 16 | ZH 16 | 16/16 | 2026-08-04..2026-08-09 |
| DW English | 6 | EN 6 | 6/6 | 2026-07-16..2026-08-08 |

\* Presence means the persisted article text contains `中国`, `china`, or
`chinese`; it is not a claim that the article describes one event. The latest
approved 57-60 manual collection fetched 229 raw items, matched 22, created 0,
duplicated 22, and failed 0.

The normalized language total is EN 8 and ZH 21. No genuine mixed-language
article was required to form the current production conclusion; the event
service still has an explicit `mixed`/`unknown` path for noisy rows.

### Pairwise coverage

Across the 29 canonical configured-source articles there are 261 cross-source
pairs, 93 same-language pairs, 123 pairs within 72 hours, and 68 pairs that
are both same-language and within the 72-hour window. The maximum current
lexical score is only `0.194410`, below the candidate threshold `0.55`.

The strongest real pair is BBC World article 9 and DW English article 25,
8.855 hours apart, both about Typhoon Dolphin:

| Score | Title similarity | Content similarity | Time proximity | Matched terms |
|---:|---:|---:|---:|---|
| 0.194410 | 0.125000 | 0.028571 | 0.877018 | `dolphin`, `typhoon` |

This is a recall/feature-coverage failure, not a time-window failure. No pair
reached the current `0.55` candidate threshold.

### Event runs and automation

All ten production `foreign_event_runs` are `scope='foreign'`, `dry_run=true`,
and `status='dry_run'`. Run 10 processed the 23 existing articles from sources
57-60, produced four previews, linked eight articles, and created zero formal
events. The four previews were single-source VOA groups with two articles each
and confidence `0.653650-0.672292`; the formal threshold is `0.72`, and the
multi-source gate is not met.

The current automatic event setting is `false`, with threshold `0.72`, window
72 hours, and `scheduler_registered=false`. Automatic alert evaluation,
automatic collection, and external notifications remain disabled.
## Current implementation behavior

The audited implementation is in:

- `backend/app/services/foreign_event_service.py`
- `backend/app/services/foreign_event_auto_aggregation_service.py`
- `backend/app/services/foreign_content_sanitizer.py`
- `backend/app/models/foreign_event_candidate.py`
- `backend/app/models/foreign_event.py`
- `backend/app/models/foreign_event_opinion.py`
- `backend/app/models/foreign_event_run.py`
- `backend/app/api/foreign_events.py`
- `frontend/src/views/ForeignWorkspace.vue`

The current chain is:

1. Canonicalize by `duplicate_of_id`, URL, and content hash.
2. Build one normalized analytical document from title, summary, and body.
3. Detect `en`, `zh`, `mixed`, or `unknown`.
4. Partition articles by the detected language. English and Chinese articles
   therefore never enter the same group.
5. Within a language, reject article pairs outside 72 hours and score the
   remaining pair as `0.40 * title + 0.45 * content + 0.15 * time`.
   Title-anchor overlap is evidence only and is not double weighted.
6. Build a candidate only above `0.55`. Mixed/unknown groups are capped at
   `0.49` confidence and cannot pass automatic confirmation.
7. Automatic confirmation requires candidate status `candidate`, language
   `en` or `zh`, confidence at least `0.72`, at least two articles, and at
   least two sources. The service is feature-gated off.
8. The UI exposes a foreign-only dry-run, candidate list, manual confirm/reject,
   and foreign event detail/actions. It does not expose a cross-language
   candidate evidence workflow.

### Why no formal event exists

The result is caused by several distinct factors:

| Finding | Classification | Effect |
|---|---|---|
| 29 configured articles, with zero Fox News and BBC Chinese rows and only one BBC World row | Data coverage | Too few independent narratives to form a robust event |
| Latest 57-60 run created no new rows | Data state | Existing sparse corpus remains unchanged |
| Same-language grouping and at least two sources | Expected policy | Correctly blocks mixed-language and single-source confirmation |
| Confidence threshold `0.72` and candidate threshold `0.55` | Expected policy | No observed cross-source pair reaches even `0.55`; lowering it would be unsafe |
| Lexical Jaccard on translated/paraphrased stories | Algorithm limitation | Misses semantic equivalence across languages and paraphrases |
| Language grouping by exact class | Expected policy plus recall limit | English and Chinese stories cannot currently become one candidate |
| NYT caption/photo-credit text remains in normalized analytical input | Implementation defect | Adds Latin/template noise and can distort language and similarity |
| Pair scoring tokenizes both titles using the left article language | Implementation limitation | Safe for current same-language groups, unsafe as a future cross-language primitive |
| Candidate `language` is one scalar and evidence is untyped JSON | Data-model limitation | No first-class language pair, entity evidence, or cross-language reason |

The time gate and duplicate suppression are behaving as designed. The absence
of formal events should not be treated as evidence that the sources never cover
the same story.

## Isolated sample matrix

These samples were constructed in memory with no network and no database
writes. `Eligible` means the current automatic gate would accept the group.

| # | Sample | Languages | Observed score/result | Candidate | Eligible / auto-confirm | Review |
|---:|---|---|---|---|---|---|
| 1 | Same event, two English sources | EN / EN | score 1.000, confidence 1.000 | yes | yes / yes | no |
| 2 | Same event, two Chinese sources | ZH / ZH | score 1.000, confidence 1.000 | yes | yes / yes | no |
| 3 | Same event, one English and one Chinese source | EN / ZH | partitioned into separate language groups | no | no / no | pending by design |
| 4 | Similar topic, different event | EN / EN | score 0.195 | no | no / no | no candidate |
| 5 | Multiple articles from one source | EN / EN | score 1.000, source count 1 | yes | no / no | manual review required |
| 6 | Same-source duplicate URL | EN / EN | canonical count 1 | no | no / no | duplicate removed |
| 7 | Low-similarity pair | EN / EN | score 0.150 | no | no / no | no candidate |
| 8 | Same text outside the 72-hour window | EN / EN | 73-hour delta; group rejected | no | no / no | no candidate |
| 9 | Chinese text with brands, names, acronyms, and entities | ZH | normalized language `zh`; resources/entities removed | n/a | n/a | safe normalization baseline |
| 10 | Original NYT HTML with image, script, and caption | ZH | language `zh`; image/script removed, caption retained | n/a | n/a | **cleaning defect confirmed** |

The current implementation therefore already proves same-language automatic
eligibility in isolation, while it has no cross-language candidate path to put
sample 3 into a human queue.
## Options assessment

| Option | Accuracy / risk | Network or AI | Cost / latency | Privacy | Domestic impact | Reuse / rollback | Assessment |
|---|---|---|---|---|---|---|---|
| A. Lexical similarity plus normalization/entity matching | Low cost and explainable; recall remains limited for translation/paraphrase; entity false positives must be controlled | None | Low / low | Strong | None; foreign-only | Reuses existing evidence and gates; easy rollback | Required baseline, not sufficient alone |
| B. Local multilingual embedding | Better semantic recall; model drift and near-topic false merges require calibration | No external network; local model dependency | Medium-high / medium | Strong if model is local | None; foreign-only | Version model and score; reversible behind a flag | Best technical experiment after A |
| C. Translate then compare | Better lexical bridge but translation can erase distinctions and introduce errors | Local translation can avoid network; quality varies | Medium-high / high | Depends on translator | None; foreign-only | Version translation; rollback is straightforward | Useful offline benchmark, not first production path |
| D. External AI/translation service | Potentially highest recall, but opaque errors, prompt/model drift, network failures, and data leakage | Requires external network/AI | High / high | Weakest | None if isolated, but operational risk high | Harder to reproduce and rollback | Prohibited for this phase and unsuitable now |
| E. Hybrid: same-language auto, cross-language pending/manual | Controls false merges; cross-language recall improves without automatic risk | None initially; can add B/C offline later | Low now / bounded review latency | Strong | None; foreign-only | Reuses current candidate/event/alert paths; clear flag rollback | **Recommended** |

## Recommended architecture

### Confirmation policy

1. Keep current same-language automatic confirmation semantics and thresholds.
2. Add a separate cross-language candidate generator. It may create a
   `pending` candidate only when time, URL, entity, and semantic evidence are
   present; it must never set `confirmation_source='auto'`.
3. Require manual review for every cross-language candidate. The review action
   must show both source languages, source list, article timestamps, common
   entities, score decomposition, and rejection reasons.
4. Accumulate reviewer decisions as a labeled corpus. Re-evaluate precision,
   recall, and false-merge rate before considering any automatic gate.

### Evidence contract

Extend candidate `evidence_json` first, without a new table, with a versioned
object containing:

```json
{
  "cross_language": true,
  "language_set": ["en", "zh"],
  "language_confidence": {"en": 0.99, "zh": 0.99},
  "source_list": ["BBC World", "VOA Chinese"],
  "article_ids": [9, 10],
  "time_delta_hours": 8.85,
  "common_entities": [{"value": "...", "type": "person|place|org", "evidence": "..."}],
  "similarity": {
    "title_lexical": 0.12,
    "content_lexical": 0.03,
    "semantic": 0.00,
    "time": 0.88,
    "method_version": "foreign-cross-v1"
  },
  "eligibility_reasons": ["cross_language_requires_manual_review"],
  "manual_required": true
}
```

The existing scalar `language` can remain `mixed` for compatibility, but a
future additive `language_set`/`cross_language` field is preferable for
filtering and indexing. Do not overload `confidence` without recording which
features produced it.

### Flags and services

Add two independent foreign-only settings, both defaulting to `false`:

- `foreign_event_cross_language_enabled`: permits candidate generation only.
- `foreign_event_cross_language_auto_confirm_enabled`: permits automatic
  confirmation only after a separately approved evaluation.

The second flag must be ineffective unless the first is enabled and the
candidate passes a stricter cross-language policy. In the first implementation,
add `ForeignCrossLanguageEventService` and reuse `ForeignEventRun` with a
version such as `foreign-cross-v1` for an isolated run log. A new dedicated run
model is not required initially; introduce one only if pending-review volume,
model versions, or reviewer labeling outgrow the existing run contract.

### API and UI

Add foreign-only, read-safe endpoints or extend existing serializers without
touching domestic APIs:

- expose cross-language flags and policy status beside the existing auto status;
- allow `dry_run=true` cross-language analysis with an explicit `analysis_version`;
- return `pending` previews with evidence and rejection reasons;
- keep non-dry-run candidate persistence permissioned and disabled by default;
- add candidate evidence/detail UI, language-pair filters, and a mandatory
  review reason for confirm/reject;
- show cross-language candidates separately from auto-eligible same-language
  candidates;
- retain existing foreign event, alert, and audit serializers after manual
  confirmation.

No domestic endpoint, model, scheduler, dashboard, map, hotword, or alert path
needs to change. Foreign alerts can continue to consume only confirmed foreign
events after the existing foreign-only boundary.

## Data-source recommendation

Do not add sources solely to increase article count. First run read-only probes
and verify stable overlapping coverage. A second stable Chinese source and
China-focused English feeds would improve cross-language evidence, but source
addition must remain separately approved, bounded, and `schedule_enabled=false`.
The current zero-row Fox News and BBC Chinese sources are a coverage gap, not a
reason to lower event thresholds.
## Test and verification results

- Full `tests/test_foreign*.py`: **187 passed, 1 failed**.
- The one failure is
  `test_confirmed_foreign_event_can_be_closed_and_frontend_uses_probe_contract`;
  it expects the stale UI string `sourceTestResult.success`. No assertion was
  changed, and no production data was involved.
- Event, normalization, and scope-focused subset: **24 passed**.
- `python -m compileall -q app tests`: passed.
- `npm run build`: passed.
- `git diff --check`: passed (line-ending warnings only).
- In-memory ten-sample matrix: completed; no writes or network calls.

The focused event tests confirm same-language candidate metrics, duplicate URL
suppression, mixed-language non-grouping, auto eligibility, foreign-only scope,
and domestic snapshot isolation. The full-suite UI failure remains an explicit
follow-up test-contract issue; it is not evidence for changing event thresholds.

## Domestic isolation evidence

The production read-only snapshot before and after this review is unchanged:
`opinions=1705`, `events=292`, `event_opinions=567`, `alert_records=37`.
The audited foreign event service imports and writes only `foreign_event_*`
models, and the foreign UI/API use `/foreign/...` routes. No domestic model,
scheduler, dashboard, map, hotword, or alert code was modified or invoked.

## Next-stage implementation split

1. **Normalization fix:** remove caption/photo-credit/template nodes before
   analytical text construction; add NYT regression fixtures and verify output
   is plain, bounded text.
2. **Evidence baseline:** add entity extraction, language confidence, score
   decomposition, and explicit rejection reasons to dry-run evidence only.
3. **Cross-language dry-run:** implement `ForeignCrossLanguageEventService`
   behind `foreign_event_cross_language_enabled=false`; compare Option A and a
   local embedding/translation benchmark without production writes.
4. **Pending review UX:** add evidence/detail, language-pair filters, reviewer
   reason, and labeled decision export within the foreign workspace.
5. **Offline acceptance:** measure precision, recall, false-merge rate,
   cross-language coverage, latency, and reproducibility on a labeled corpus.
6. **Separate approval gate:** only after acceptance may anyone consider the
   auto-confirm flag; default remains off and Phase 6 automation remains out
   of scope.

## Required answers

1. Immediate cross-language automatic confirmation: **No**.
2. Same-language automatic confirmation: **Yes, keep it**, but leave the
   existing foreign auto setting disabled until its normal production gate is
   approved.
3. Cross-language candidates: **pending only** at first; never auto-confirm.
4. Evidence fields: **Yes**, add common entities, time delta, source list,
   score decomposition, language combination/confidence, and explanation.
5. Independent settings: **Yes**, add the two foreign-only flags above.
6. Defaults: **Both false**.
7. New model/service/run log: **New isolated service and versioned run log;
   reuse `ForeignEventRun` initially, extend candidate evidence additively**.
8. China-focused sources: **Continue targeted read-only source evaluation**,
   with separate approval before persistence or collection.
9. Domestic isolation: **Yes**, all proposed changes can remain in foreign
   services, foreign tables, foreign routes, and foreign UI state.

No cross-language implementation, production event, automatic confirmation, or
Phase 6 automation is authorized by this review.

## Post-review implementation addendum

The isolated follow-up implementation is documented in
`docs/Phase_Foreign_Source_Cross_Language_Candidate_Implementation.md`. It adds
an opt-in `foreign-cross-v1` candidate generator using shared Latin/entity
tokens, preserves the existing lexical formula and thresholds, records explicit
evidence, and forces every mixed candidate to manual `pending` review. Both
cross-language settings remain `false`; no production candidate/event was
created. The implementation also closes the NYT/template sanitization gap and
adds the source-probe `success`/`ok` compatibility contract.

Verification after the addendum: the complete foreign suite passed **192/192**;
the focused cross-language, normalization, and source-scope suite passed
**13/13**; compileall, frontend build, and diff check passed. An isolated test
database migration downgrade/upgrade round-trip returned to
`foreign_source_5g_remediation`. The production domestic and foreign counts
remained `1705/292/567/37` and `31/0/0/10` respectively.
