# Phase Foreign-Source Event Coverage Diagnostics

## Scope and Safety

- Diagnostic date: 2026-08-09 (Asia/Shanghai).
- This phase was read-only against production `opinion_db` on
  `127.0.0.1:5432`.
- No RSS request, proxy, AI call, event rebuild endpoint, alert evaluation,
  scheduler task, configuration write, or production data write was performed.
- The current implementation was exercised only with in-memory samples and in
  the isolated `opinion_test` database.

## Production Read-only Snapshot

| Item | Value |
|---|---:|
| Database identity | `opinion_db` / `127.0.0.1:5432` |
| Alembic revision | `foreign_source_5g_remediation` |
| Domestic `opinions` | 1702 |
| Domestic `events` | 292 |
| Domestic `event_opinions` | 567 |
| Domestic `alert_records` | 37 |
| `foreign_opinions` | 30 |
| `foreign_risk_results` | 30 current results |
| `foreign_event_candidates` | 0 |
| `foreign_events` | 0 |
| `foreign_event_runs` | 8 |

The same counts, revision, source count (7), event count, and automation status
were observed in the final read-only snapshot. No production row changed during
this diagnostic.

Foreign automatic event aggregation is disabled, with `scheduler_registered=false`,
confidence threshold `0.72`, and a `72` hour window. Automatic alert evaluation
and external notifications are also disabled. All seven foreign sources have
`schedule_enabled=false`.

### Source Coverage

The raw/matched values below come from the latest persisted foreign collector
runs. Valid-item values for the four newly approved feeds come from their
bounded pre-save probe; no new network probe was run in this read-only phase.

| Source | Raw items | Valid items | Matched | Hit rate | Persisted articles | Detected language | Published range |
|---|---:|---:|---:|---:|---:|---|---|
| Fox News | 25 | n/a | 0 | 0.0% | 0 | n/a | n/a |
| The Guardian | 45 | n/a | 1 | 2.2% | 1 | EN 1 | 2026-08-06 |
| 纽约时报中文网 | 20 | n/a | 5 | 25.0% | 5 | mixed 5 | 2026-08-03..08-07 |
| BBC World | 32 | 20 | 1 | 3.1% | 1 | EN 1 | 2026-08-08 |
| BBC Chinese | 38 | 20 | 0 | 0.0% | 0 | n/a | n/a |
| VOA Chinese | 20 | 20 | 15 | 75.0% | 15 | mixed 13, ZH 2 | 2026-08-04..08-08 |
| DW English | 142 | 20 | 6 | 4.2% | 6 | EN 6 | 2026-07-16..08-08 |

All 28 articles belonging to configured sources have unique URLs. Two older
`fixture_en_*` rows (source ID null, fixture URLs) are present in
`foreign_opinions`; they are not among the seven configured sources and were
excluded from coverage and event conclusions. They were not modified.

All persisted articles have at least one of the current broad collection
keywords (`中国`, `Chinese`, `China`). This is a collection filter statistic,
not evidence that the articles describe one event.

### Risk and Event Runs

- Current foreign rule results: 30/30 completed; all are low risk.
- Latest production event run: ID 8, `dry_run`, input 22, deduplicated 22,
  3 previews, 11 linked articles, 0 created events, 0 failures.
- The three previews were the existing VOA-only groups and were not persisted
  as candidates by the dry-run.

## Pairwise Coverage Analysis

The latest 22-article collection produced 111 cross-source pairs. Only 6 pairs
were same-language EN/EN, 27 were within 72 hours, and only 1 pair was both
same-language and within the window. Zero cross-source pairs reached the
candidate similarity threshold `0.55`. Across all 28 configured-source
articles, there were 248 cross-source pairs, 13 same-language pairs, 119 within
72 hours, 3 same-language-within-window pairs, and still zero pairs at `0.55`.

| Source pair | Pairs | Same-language | Within 72h | Max score | Best evidence |
|---|---:|---:|---:|---:|---|
| BBC World / DW English | 6 | 6 | 1 | 0.213696 | Typhoon/Dolphin anchor overlap only |
| BBC World / Guardian | 1 | 1 | 1 | 0.071025 | No shared anchor |
| Guardian / DW English | 6 | 6 | 1 | 0.110468 | Weak common token only |
| Guardian / VOA Chinese | 15 | 0 | 15 | 0.142065 | Language mismatch |
| NYT Chinese / VOA Chinese | 75 | 0 | 64 | 0.146265 | Raw HTML/no shared title anchor |
| BBC/DW / VOA Chinese | 105 | 0 | 26 | <=0.145303 | Language mismatch |

For the best pair in each source combination, the separate lexical signals
were:

| Source pair | Best pair | Title Jaccard | Summary Jaccard | Body Jaccard | Time delta |
|---|---|---:|---:|---:|---:|
| BBC World / DW English | 9 / 25 (Typhoon Dolphin) | 0.125 | 0.028571 | 0.028571 | 8.85h |
| BBC World / Guardian | 9 / 1 | 0.000 | 0.080460 | 0.080460 | 47.56h |
| Guardian / DW English | 1 / 25 | 0.050 | 0.044444 | 0.044444 | 38.71h |
| NYT Chinese / VOA Chinese | 4 / 17 | 0.000 | 0.027778 | 0.027778 | 5.13h |
| Guardian / VOA Chinese | 1 / 18 | 0.000 | 0.012500 | 0.012500 | 5.31h |

The service currently combines summary and body into one content feature and
uses the detected language of the left article for tokenization. For mixed
Chinese rows this means Chinese text is not tokenized as Chinese bigrams, while
raw HTML/Latin fragments remain available to the ASCII tokenizer. This explains
the low cross-language scores and is a concrete recall defect, not evidence that
the articles describe a different event.

The strongest real cross-source pair is BBC World article 9 and DW English
article 25 (8.85 hours apart), both about Typhoon Dolphin. Its title similarity
and anchor overlap are only `0.125`, content similarity `0.028571`, and total
score `0.213696`, far below `0.55`. This is a coverage/topic-overlap failure,
not a time-window failure.

## Why the Three VOA Previews Failed

The in-memory reconstruction of the latest 22-article input exactly reproduced
the three dry-run groups:

| Group | Articles | Sources | Language | Confidence | Pair evidence |
|---|---:|---:|---|---:|---|
| VOA interview/audio cluster | 6 | 1 | mixed | 0.49 | title/anchor 1.0, content 0..1.0 |
| VOA daily broadcast cluster | 2 | 1 | mixed | 0.49 | title/content 1.0 |
| VOA focus/audio cluster | 3 | 1 | mixed | 0.49 | title 1.0, content 0.667 |

The service deliberately caps a `mixed` or `unknown` group at `0.49`. The
automatic eligibility gate additionally requires language `en` or `zh`,
confidence `>=0.72`, at least 2 articles, and at least 2 sources. Therefore
every group fails three independent checks: mixed language, confidence below
threshold, and single-source evidence. No formal event was appropriate.

## Language Diagnosis

The detector classifies an article as mixed if it contains any CJK and any ASCII
letter anywhere in title, summary, or content. This creates false mixed results:

- 13 of 15 VOA articles are overwhelmingly Chinese (223-491 CJK characters)
  but include `VOA`, `NASA`, `FBI`, `SpaceX`, names, or HTML entities such as
  `&ldquo;`/`&rdquo;`.
- Two VOA articles become pure ZH when HTML entities are removed; the remaining
  mixed labels still contain only short brand/name/acronym fragments rather than
  an English article body.
- All five historical NYT Chinese articles are detected as mixed because the
  stored content still contains image/style/class/src attributes and photo
  credits with many Latin letters. The API sanitizer hides this at output, but
  `foreign_event_service._article_text()` consumes the raw stored content.

This is an implementation/normalization defect that reduces Chinese cross-source
recall. It is separate from the expected policy that genuinely mixed-language
groups must remain pending.

## Gate and Algorithm Classification

| Condition | Finding | Classification |
|---|---|---|
| Keyword coverage | Broad China/Chinese keywords yield 22 matches but mostly single-source or digest items; BBC Chinese had 0 matches | Data coverage/filter strategy |
| Same-language requirement | Correctly prevents mixed-language auto-confirmation | Expected business policy |
| Confidence `0.55` / `0.72` thresholds | No real cross-source pair reached even `0.55`; threshold was not the primary blocker | Expected policy; recall risk only after better features |
| Minimum 2 articles | VOA groups satisfy it; not a blocker | Expected policy |
| Minimum 2 sources | All three real groups have source_count=1 | Expected business policy; direct blocker |
| 72-hour window | Many pairs are within 72 hours, but lexical scores remain low | Not a time-window problem |
| Lexical Jaccard | Correctly rejects unrelated articles, but cannot bridge translation/paraphrase and is affected by raw HTML | Feature/normalization limitation |
| Single-source restriction | Prevents confirming repeated VOA broadcasts as external events | Expected business policy |
| Raw historical HTML in event input | NYT content includes external markup/asset text in stored rows | Implementation defect |

## Isolated Reproduction

In-memory fixtures used the current `foreign-event-v1` grouping and eligibility
logic (no production connection and no writes):

| Sample | Result |
|---|---|
| Same event, two EN sources | Candidate confidence 1.0; auto eligible |
| Same event, two ZH sources | Candidate confidence 1.0; auto eligible |
| Same-source duplicate content | Canonicalized from 2 to 1; no candidate |
| Different events, two sources | No candidate |
| Same event described EN/ZH | No same-language group; remains pending |
| Multiple articles, one source | Candidate may form, but auto eligibility false (`source_count=1`) |
| Low-confidence pair | No candidate below `0.55` |

The full related foreign test sweep on the isolated database returned
`178 passed, 1 failed`. The sole failure is
`test_foreign_source_api_validates_feeds_and_keeps_schedule_manual`: its
`https://fixture.test/rss` network fixture was not intercepted in this run, so
the API correctly returned the controlled `422 Foreign feed request failed`
instead of the test's expected `201`. No production database was involved, no
assertion was changed, and the event/remediation/UI focused tests passed. This
fixture harness failure is a test-environment gap, not evidence of a production
event algorithm failure.

## Decision and Next-stage Plan

**Decision: CONDITIONAL GO for isolated design/implementation work; NO-GO for
enabling production automatic event confirmation.**

1. Add or approve more China-focused sources only after read-only probes show
   overlapping event coverage, especially a second stable Chinese source and
   English sources with China-specific geopolitical feeds.
2. Design a language-normalization boundary that removes HTML tags/attributes,
   decodes entities, and discounts source brands/acronyms before event language
   detection. This requires a separate design review and regression fixtures.
3. Evaluate translated/semantic cross-language similarity as a separate design
   track; do not silently relax the same-language auto-confirmation rule.
4. Add diagnostics for source_count, language confidence, pair scores, and
   rejection reasons to event previews before changing thresholds.
5. Keep the 72-hour window, `0.55`/`0.72` thresholds, current keywords,
   automatic scheduling, and mixed-language policy unchanged until the design
   review and isolated acceptance are approved.

No recommendation in this report authorizes production writes, formal event
confirmation, automatic collection, automatic alerts, or external
notifications.
