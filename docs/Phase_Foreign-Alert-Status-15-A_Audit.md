# Phase Foreign-Alert-Status-15-A Audit

> **Audit type**: Pure read-only investigation. No source / DB / schema / migration changes were made.
> **Audit date**: 2026-08-14
> **Scope**: Establish a reliable "status contract decision package" for unifying the foreign `foreign_alerts.status` vocabulary with the domestic `alert_records.status` vocabulary.
> **Method**: Static analysis of `backend/app` (models / schemas / services / api), `frontend/src` (vue/ts), `backend/alembic/versions`; read-only `SELECT` against production `127.0.0.1:5432/opinion_db`.

---

## 1. Executive Summary

The two alert systems use **two genuinely different lifecycle vocabularies**, not a cosmetic labeling difference:

- **Domestic `alert_records.status`** CHECK: `pending / processing / resolved / ignored / false_positive` (5 states). Direct, free-set disposition — any state can be set from any other; a derived `handled` boolean mirrors `{resolved, ignored, false_positive}`.
- **Foreign `foreign_alerts.status`** CHECK: `triggered / acknowledged / resolved / suppressed / failed` (5 states). Born as `triggered` by the rule engine; `failed` is **present in the CHECK but never written** to a foreign alert row (vestigial). The manual *handle* API only accepts **3** target states: `acknowledged / resolved / suppressed`.

There is **no intersection** except `resolved`. The domestic concepts `pending`, `processing`, `ignored`, `false_positive` have **no native foreign lifecycle state**; the foreign concepts `triggered`, `acknowledged`, `suppressed`, `failed` have **no native domestic equivalent**.

The frontend already keeps **two separate vocabularies** in one page (`frontend/src/views/Alerts.vue`): the domestic handle dialog offers 5 options, the foreign handle dialog offers 3 (`acknowledged/resolved/suppressed`). The user's request is to make the foreign dialog *look* like the domestic one.

**Recommendation (see §14): Option A — presentation-layer unified disposition adapter, zero schema change.** A literal, settable 5-state foreign dropdown requires **Option B (extend the foreign CHECK via DDL)**, which introduces dead/never-produced states and is **not** recommended unless product mandates exact parity.

---

## 2. Scope / Red Lines

| Allowed | Performed |
| --- | --- |
| Read source / migration / schema | ✅ node-authored reads of real layer |
| Production DB read-only `SELECT` | ✅ `pg_catalog` + `GROUP BY` (SELECT only) |
| Static / hardcoded reference scan | ✅ 214 backend + 82 frontend occurrences |
| Read-only test / analysis script | ✅ `_db_audit.py` (SELECT-only) |
| Create audit report Markdown | ✅ this file |

| Forbidden (NOT done) | Evidence |
| --- | --- |
| Modify source / frontend / DB / schema | none |
| CREATE / run Alembic migration | none |
| UPDATE / DELETE / INSERT on production | none |
| Implement any recommended option | none — decision deferred to next phase |

---

## 3. Domestic Status Audit

### 3.1 Model (authoritative)
`backend/app/models/alert.py:50-53` — `AlertRecord.status` column, `String(32)`, `default="pending"`, `server_default="pending"`.
`backend/app/models/alert.py:84-96` — `__table_args__` CHECK:

```
backend/app/models/alert.py:89-92
CheckConstraint("status IN ('pending','processing','resolved','ignored','false_positive')", name="ck_alert_records_status")
```

Companion field `handled: Boolean` (`:49`) — dual-written: `resolved/ignored/false_positive → handled=True` (comment :45-48).

### 3.2 API Schema
`backend/app/schemas/alert.py:83` — `_ALLOWED_HANDLE_STATUS = {"pending","processing","resolved","ignored","false_positive"}`.
`backend/app/schemas/alert.py:61` — response `status: str = "pending"`; `:87` — handle request default `status="resolved"`.

### 3.3 API endpoint
`backend/app/api/alerts.py:79` — `_ALLOWED_ALERT_STATUSES` (same 5).
`backend/app/api/alerts.py:223-262` — `PUT /alerts/records/{record_id}/handle`:
- `:182` rejects unknown status with 422.
- `:255` `rec.status = new_status` (free-set, **no state machine**).
- `:256` `rec.handled = new_status in _RESOLVED_STATES` where `_RESOLVED_STATES = {resolved, ignored, false_positive}` (`:220`).
- permission `alerts:write` (`:228`).

### 3.4 Service (creation)
`backend/app/services/alert_service.py:153` — domestic alert created with `status="pending"`.

### 3.5 Frontend
`frontend/src/views/Alerts.vue:53` — domestic filter options `pending/processing/resolved/ignored/false_positive` (labels 待处理/处理中/已解决/已忽略/误报).
`frontend/src/views/Alerts.vue:94-99` — domestic handle dialog options (same 5).
`frontend/src/views/Alerts.vue:132-133` — `STATUS_TEXT` / `STATUS_TAG` maps (pending=danger, processing=warning, resolved=success, ignored=info, false_positive=info).

### 3.6 Canonical Domestic Status Set (cross-confirmed)

| State | DB CHECK | Backend allowed | API | Frontend | Semantic |
| --- | --- | --- | --- | --- | --- |
| `pending` | ✅ | ✅ | ✅ | 待处理/danger | New, unhandled |
| `processing` | ✅ | ✅ | ✅ | 处理中/warning | Actively being handled |
| `resolved` | ✅ | ✅ | ✅ | 已解决/success | Closed as resolved (`handled=True`) |
| `ignored` | ✅ | ✅ | ✅ | 已忽略/info | Triaged away (`handled=True`) |
| `false_positive` | ✅ | ✅ | ✅ | 误报/info | Marked non-actionable (`handled=True`) |

**Observation**: DB = API = Frontend = 5 states. The only derived duplicate is `handled` boolean. No mismatch.

---

## 4. Foreign Alert Status Audit

### 4.1 Model (authoritative)
`backend/app/models/foreign_alert.py:18-22` — CHECK:
```
CheckConstraint("status IN ('triggered','acknowledged','resolved','suppressed','failed')", name="ck_foreign_alerts_status")
```
`backend/app/models/foreign_alert.py:71` — `status` column `default="triggered"`, `server_default="triggered"`.
Also `evaluation_source` CHECK (`:67-69`, default `rule`) allows `rule/ai/manual_review_ai` — **3 values, one more than domestic** (see §18 Open Questions).

### 4.2 DB schema (production, read-only verified)
`pg_catalog` confirms `ck_foreign_alerts_status` = `status::text = ANY (ARRAY['triggered','acknowledged','resolved','suppressed','failed'])`.
Indexes: `ix_foreign_alerts_status` (`:31`), plus `ix_foreign_alerts_severity`, `ix_foreign_alerts_rule_id`, `ix_foreign_alerts_evaluation_source` (`:31-45`).
FKs: `acknowledged_by/resolved_by/suppressed_by → users.id` (`:89-97`). Timestamps `acknowledged_at/resolved_at/suppressed_at` (`:86-88`). `failure_reason` (`:98`).

### 4.3 Service — state write matrix
`backend/app/services/foreign_alert_service.py:34` — `ALERT_STATUSES = {"triggered","acknowledged","resolved","suppressed","failed"}`.
`backend/app/services/foreign_alert_service.py:236` — `evaluate()` creates alert with `"status": "triggered"`.

**Two distinct mechanisms:**

**(a) Strict state machine `transition()`** — `:430-445`:
```
"acknowledge": (("triggered",), "acknowledged")
"resolve":     (("acknowledged",), "resolved")
"suppress":    (("triggered","acknowledged"), "suppressed")
```
Used by automated/evaluate/manual-review flows. `triggered→acknowledged→resolved`; `triggered/acknowledged→suppressed`.

**(b) Lenient direct-set `handle()` / `set_status()`** — `:580-665` (docstring "domestic-style handle"):
- `:593` `if status not in ALERT_STATUSES or status in {"triggered","failed"}: raise` → **target states restricted to {acknowledged, resolved, suppressed}**.
- `:639` `alert.status = status`; `:640-648` sets `acknowledged_at/_by` / `resolved_at/_by` / `suppressed_at/_by` accordingly. Writes a `ForeignAlertAction` audit row.

### 4.4 API endpoint
`backend/app/api/foreign_alerts.py:441-443` — `ForeignAlertHandlePayload.status: str` (description literally `"目标处置状态：acknowledged | resolved | suppressed"`).
`backend/app/api/foreign_alerts.py:446-450` — `_STATUS_HANDLE_PERM` maps `acknowledged→foreign:alerts:acknowledge`, `resolved→foreign:alerts:resolve`, `suppressed→foreign:alerts:suppress`.
`backend/app/api/foreign_alerts.py:453-500` — `PUT /foreign/alerts/{alert_id}/handle`: validates target ∈ the 3 perm keys (`:463-465` → 400 otherwise), checks permission, calls `ForeignAlertService.set_status(...)` (`:480`). Returns serialized action + alert.

→ **The foreign handle API is hard-wired to accept only `acknowledged / resolved / suppressed`.** It can never receive `pending/processing/ignored/false_positive` (would 400 at `:465` before reaching the service).

### 4.5 Frontend
`frontend/src/views/Alerts.vue:58` — foreign filter options `triggered/acknowledged/resolved/suppressed/failed` (labels 待确认/已确认/已解决/已抑制/失败).
`frontend/src/views/Alerts.vue:89-93` — foreign handle dialog options **only** `acknowledged/resolved/suppressed` (已确认/已解决/已抑制).
`frontend/src/views/Alerts.vue:132` — `FOREIGN_TEXT` map.
`frontend/src/views/Alerts.vue:163-168` — `submitHandle()` sends `PUT /foreign/alerts/{id}/handle` with `handleForm.status`.

### 4.6 Foreign Persistence Status (verified)

| State | In DB CHECK | Produced by lifecycle | Settable via handle API | Semantic |
| --- | --- | --- | --- | --- |
| `triggered` | ✅ | ✅ `evaluate()` | ❌ (excluded :593) | Born / unacknowledged |
| `acknowledged` | ✅ | ✅ transition/handle | ✅ | Seen, in progress |
| `resolved` | ✅ | ✅ transition/handle | ✅ | Closed resolved |
| `suppressed` | ✅ | ✅ transition/handle | ✅ | Muted/ended without resolution |
| `failed` | ✅ | ❌ **never written** | ❌ (excluded :593) | Vestigial system state |

**Mismatch (flagged)**: `DB CHECK (5) ≠ handle-API-accepts (3) ≠ lifecycle-produces (4: triggered,ack,resolved,suppressed)`. `failed` is in the CHECK but dead.

---

## 5. Database Constraint Audit (production, read-only `SELECT`)

`ck_alert_records_status` (actual DDL):
```
((status)::text = ANY (ARRAY['pending'::varchar,'processing'::varchar,'resolved'::varchar,'ignored'::varchar,'false_positive'::varchar]))
```
`ck_foreign_alerts_status` (actual DDL):
```
((status)::text = ANY (ARRAY['triggered'::varchar,'acknowledged'::varchar,'resolved'::varchar,'suppressed'::varchar,'failed'::varchar]))
```
Both confirmed live via `pg_constraint`/`pg_get_constraintdef`. Migration origin:
- `backend/alembic/versions/foreign_source_3c.py:115` — creates `ck_foreign_alerts_status`.
- `backend/alembic/versions/p10_phase2b1_alert_operation.py:93,133` — creates / drops `ck_alert_records_status`.
- **Precedent for altering a foreign CHECK**: `backend/alembic/versions/foreign_alert_manual_review_ai_source.py:19-36` already did `ALTER TABLE foreign_alerts DROP CONSTRAINT ck_foreign_alerts_evaluation_source` + recreate widened — proves Option B is feasible and has a template.

---

## 6. API / Service Audit

| Concern | Domestic | Foreign |
| --- | --- | --- |
| Handle route | `PUT /alerts/records/{id}/handle` (`alerts.py:223`) | `PUT /foreign/alerts/{id}/handle` (`foreign_alerts.py:453`) |
| Status exposure | Direct DB status (`_alert_record_payload`) | Direct DB status (`serialize_alert`) |
| Validation | 422 if ∉ 5-set (`:182`) | 400 if ∉ {ack,resolve,suppress} (`:465`) |
| State machine | None (free-set) | Strict `transition()` + lenient `handle()` |
| Permission | `alerts:write` | per-state `foreign:alerts:acknowledge/resolve/suppress` |
| Audit row | `HANDLE_ALERT` (`:248`) | `HANDLE_FOREIGN_ALERT` + `ForeignAlertAction` |
| `handled` boolean | ✅ derived | ❌ (status is the single source of truth) |

`ForeignAlertAction` audit table CHECK (`backend/app/models/foreign_alert_action.py:24,28`): `previous_status/new_status IN ('triggered','acknowledged','resolved','suppressed','failed')` — must be widened in lockstep if Option B extends the alert CHECK.

---

## 7. Frontend Audit

`frontend/src/views/Alerts.vue` is the **single unified page** holding both vocabularies:

- Domestic filter `:53`, handle dialog `:94-99`, maps `:132-133` → 5 states.
- Foreign filter `:58`, handle dialog `:89-93`, maps `:132` → 5 states (incl `failed`).
- `submitHandle()` (`:163-175`) branches on `handlingScope` and calls the correct endpoint with `handleForm.status`.

**Frontend already has an independent foreign status vocabulary.** Unifying the *handle dropdown* requires only changing `:89-93` (and optionally the filter `:58` + `FOREIGN_TEXT` labels), i.e. a frontend-only change for Option A.

---

## 8. Status Lifecycle Audit

### 8.1 Domestic
```
[created by alert_service.py:153 as 'pending']
   │  PUT /alerts/records/{id}/handle  (alerts.py:223, free-set, no ordering)
   ▼
[pending] ⇄ [processing] ⇄ [resolved] ⇄ [ignored] ⇄ [false_positive]
   (any → any; resolved/ignored/false_positive set handled=True)
```
No scheduler/collector auto-transition. Human-only.

### 8.2 Foreign
```
[evaluate() creates 'triggered'  (foreign_alert_service.py:236)]
   │
   ├─ transition()  (strict, :442-444)
   │     triggered ──acknowledge──▶ acknowledged ──resolve──▶ resolved
   │     triggered/acknowledged ──suppress──▶ suppressed
   │
   └─ handle()/set_status()  (lenient, :593, target ∈ {ack,resolve,suppress})
         any-current ──▶ acknowledged | resolved | suppressed   (no ordering enforced)
```
- `failed`: **never assigned** to a foreign alert row (verified by scan + DB distribution). `failure_reason` exists but unused in current data.
- No scheduler auto-resolves (MEMORY: scheduler does not auto-resolve foreign alerts).
- Irreversible terminal states: `resolved`, `suppressed` (no transition out defined). `acknowledged` can still → resolved/suppressed.

---

## 9. Production Data Read-only Audit

```
alert_records: total = 38
  pending        = 31
  false_positive = 7
  (processing/resolved/ignored = 0 in current data)

foreign_alerts: total = 6
  triggered    = 5
  acknowledged = 1
  (resolved/suppressed/failed = 0 in current data)
```
- **No status values outside either CHECK** (UNEXPECTED VALUES: none).
- `foreign_alerts` with `failure_reason NOT NULL` = 0 → confirms `failed` is unused.
- **Historical-data dependency is LOW**: only 38 domestic + 6 foreign rows; the only non-default rows are 7 domestic `false_positive` and 1 foreign `acknowledged`. Any mapping/migration impact is tiny and well-contained.

---

## 10. Hardcoded Status Reference Audit (selected, high-impact)

| File | Line | State(s) | Use | Hardcoded | Risk if unified |
| --- | --- | --- | --- | --- | --- |
| `backend/app/api/alerts.py` | 79 | pending…false_positive | `_ALLOWED_ALERT_STATUSES` | ✅ | low (domestic) |
| `backend/app/api/alerts.py` | 220,256 | resolved,ignored,false_positive | `handled` dual-write | ✅ | medium (must keep) |
| `backend/app/schemas/alert.py` | 83 | pending…false_positive | handle request allow-list | ✅ | low |
| `backend/app/api/foreign_alerts.py` | 441-443 | ack,resolve,suppress | payload desc | ✅ | **high (must change for Option A/B)** |
| `backend/app/api/foreign_alerts.py` | 446-450 | ack,resolve,suppress | `_STATUS_HANDLE_PERM` | ✅ | **high** |
| `backend/app/services/foreign_alert_service.py` | 34 | 5 foreign | `ALERT_STATUSES` | ✅ | high |
| `backend/app/services/foreign_alert_service.py` | 442-444 | transition map | state machine | ✅ | medium (keep strict) |
| `backend/app/services/foreign_alert_service.py` | 593 | triggered,failed | excluded targets | ✅ | **high (gates Option B)** |
| `backend/app/models/foreign_alert.py` | 20 | 5 foreign | CHECK | ✅ | **DB DDL (Option B)** |
| `backend/app/models/foreign_alert_action.py` | 24,28 | 5 foreign | audit CHECK | ✅ | DB DDL (Option B) |
| `frontend/src/views/Alerts.vue` | 58,89-93,132 | both sets | filter/dialog/maps | ✅ | medium (Option A) |
| `backend/alembic/versions/foreign_source_3c.py` | 115 | 5 foreign | migration CREATE | ✅ | Option B template |
| `backend/alembic/versions/foreign_alert_manual_review_ai_source.py` | 19-36 | evaluation_source | CHECK widen (precedent) | ✅ | template for Option B |

Full backend scan: **214** status-string occurrences across 62 files; foreign-specific concentrated in `foreign_alert_service.py` (13), `api/foreign.py` (11), `foreign_collection_service.py` (11). Full frontend scan: **82** occurrences; `Alerts.vue` (13) holds both vocabularies.

---

## 11. Domestic vs Foreign Status Semantic Matrix

| Domestic | Domestic semantic | Foreign candidate | Foreign semantic | Semantically equivalent? | Directly mappable? | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `pending` | New, unhandled | `triggered` | Born by rule engine, unacknowledged | **Partial** (both = "not yet acted") | Display-only map triggered→待处理 | Foreign never *enters* pending; cannot be set to pending |
| `processing` | Actively handled | `acknowledged` | Seen, owner assigned, in progress | **Partial** (both = "in progress") | Map acknowledged→处理中 | acknowledged has no "work started" nuance |
| `resolved` | Closed resolved | `resolved` | Closed resolved | ✅ **Yes** | ✅ Direct | none |
| `ignored` | Triaged away as non-actionable | `suppressed` | Muted/ended without resolution | **Close but NOT equal** | Map suppressed→已忽略 (display) | ignored = "not relevant"; suppressed = "silenced/ended" — different audit intent |
| `false_positive` | Marked erroneous/unwanted | *(none)* | no native state | ❌ **No** | Requires Option B (`false_positive` added) or reuse `suppressed` | If reused suppressed → loses "false alarm" semantics |
| *(none)* | — | `triggered` | born state | → maps to `pending` (display) | see pending row | — |
| *(none)* | — | `failed` | system/error state | ❌ No domestic equivalent | Display-only as "失败/异常" | must NOT be a disposition state |
| *(none)* | — | `acknowledged` | → maps to `processing` | see processing row | — | — |
| *(none)* | — | `suppressed` | → maps to `ignored` | see ignored row | — | — |

**Key distinctions the audit insists on:**
- `ignored` vs `suppressed`: ignored = triaged as irrelevant; suppressed = actively silenced/ended. Not identical.
- `false_positive` vs `suppressed`: false_positive asserts the alert was wrong; suppressed ends it without judging correctness.
- `pending` vs `triggered`: pending is a *human queue* concept; triggered is an *auto-born* concept. Foreign alerts are never "pending".
- `processing` vs `triggered`: processing implies human work started; triggered implies nobody has touched it.
- `failed` vs disposition states: `failed` is a system/error state, **not** a human disposition. Must remain outside any unified disposition vocabulary.

---

## 12. Architecture Options

### Option A — Application / Presentation-layer Mapping (adapter)
Map foreign lifecycle states ↔ domestic disposition labels for **display and handle-button labeling**, keep `foreign_alerts.status` CHECK unchanged.
- **Pros**: Zero DB/DDL change; zero downtime; no migration; no historical rewrite; lowest risk; reversible (frontend-only + optional shared DTO).
- **Cons**: Two of the 5 domestic labels (`待处理`=pending, `误报`=false_positive) are **display-only / not settable** in foreign (no foreign target state). Product must accept that the foreign handle cannot *set* "待处理" or "误报".
- **Implementation**: single adapter module `FOREIGN_STATUS ↔ DISPOSITION` (backend DTO + mirrored frontend map). Foreign handle dialog relabels `acknowledged→处理中`, `suppressed→已忽略`; `triggered` displays as `待处理` (read-only); `failed` displays as system badge. Drop `误报` from foreign handle (or hide). `foreign_alert_action.py` CHECK untouched.
- **Affects**: frontend `Alerts.vue:58,89-93,132`; optional shared util. No backend status enum change.

### Option B — Extend `foreign_alerts.status` CHECK (DDL migration)
Add `pending, processing, ignored, false_positive` to the CHECK (keep `triggered, acknowledged, resolved, suppressed, failed`), so the foreign handle can accept the full domestic 5-set.
- **Pros**: Literal parity — foreign handle dropdown can show/set exactly the 5 domestic states.
- **Cons**: Introduces **dead/never-produced states** (`pending`, `processing` — foreign is born `triggered`, never "pending"/"processing"); `false_positive` collides semantically with `suppressed`. Requires Alembic migration touching `ck_foreign_alerts_status` **and** `ck_foreign_alert_actions_*` (lockstep). `set_status()` exclusions (`:593`) and `_STATUS_HANDLE_PERM` (`:446-450`) must be rewritten. Production DDL risk; needs staged deploy; careful with the strict `transition()` matrix.
- **Migration design**: follow `foreign_alert_manual_review_ai_source.py:19-36` precedent — `ALTER TABLE foreign_alerts DROP CONSTRAINT ck_foreign_alerts_status` + recreate; same for `foreign_alert_action`. Idempotent, reversible (downgrade recreates old CHECK).

### Option C — Dual-layer status (`lifecycle_status` + `disposition_status`)
Split foreign_alerts into a system lifecycle status and a human disposition status.
- **Pros**: Theoretically cleanest separation.
- **Cons**: Over-engineered for current scale; invasive (new column + migration + every read/write path + frontend); high regression risk; not justified by the small data volume and single-page UI.

### Option D — Other (recommended framing)
**Canonical Disposition Contract with a controlled two-way adapter (Option A framing, explicit mapping table).** Define one source of truth:
```
triggered    → pending   (display only)
acknowledged → processing
resolved      → resolved
suppressed    → ignored
failed        → (system badge, not a disposition)
```
Keep DB as-is. This satisfies "consistent UI, no operation split" for the 3 real foreign dispositions, and honestly flags the 2 unmappable domestic labels as an open product decision (§18).

---

## 13. Risk Assessment

| Risk | Option A | Option B |
| --- | --- | --- |
| Production DDL / downtime | None | Yes (brief lock onALTER) |
| Historical data migration | None | None (only 6 rows; map naturally) |
| Regression in strict transition() | None | Must update `:593`/`:446` carefully |
| Dead/never-produced states | None | Yes (`pending`/`processing`) |
| Semantic loss | Low (suppressed↔ignored nuance) | Medium (false_positive↔suppressed collapse) |
| Reversibility | Full (frontend revert) | Needs downgrade migration |
| Audit/foreign_alert_action CHECK | Untouched | Must widen in lockstep |

---

## 14. Recommended Architecture

> **RECOMMENDED: Option A (Presentation-layer unified disposition adapter) — zero schema change.**

**Why:** The two systems are genuinely different lifecycles, not just labels. The foreign handle already mirrors domestic *mechanism* (lenient direct-set). The only real gap is vocabulary/UX. Option A removes the "operation split" the user reported, with **no DB change, no downtime, no migration, fully reversible**, and preserves the strict `transition()` state machine and the `foreign_alert_action` audit integrity.

**Why not B:** Introduces dead states (`pending`/`processing` are never produced by the foreign lifecycle) and collapses `false_positive`↔`suppressed` semantics; needs production DDL + lockstep audit-table migration + careful service rewrite.

**Why not C:** Over-engineered at current scale (38 + 6 rows, single page).

**Database impact**: NONE.
**Backend impact**: Optional shared DTO/adapter only (no enum/CHECK change). `set_status`/`_STATUS_HANDLE_PERM` unchanged.
**Frontend impact**: `Alerts.vue:58,89-93,132` relabel via adapter; `误报` hidden from foreign handle (or shown disabled).
**Migration risk**: NONE.
**Historical data migration**: NONE.
**Zero downtime**: YES (frontend-only deploy).
**Staged release**: Not required; can ship with the next frontend build.

**Caveat / condition**: Option A makes the foreign handle *look* domestic, but `待处理`(pending) and `误报`(false_positive) remain display-only (no foreign target). If product **mandates** these two be *settable* in foreign, that requires **Option B** (extend CHECK) — see §18 Open Question OQ-1.

---

## 15. Proposed Implementation Phases (next phase, NOT executed here)

1. **P1 — Adapter module**: add `foreign_status_to_disposition` / `disposition_to_foreign_status` in a shared backend util + mirrored frontend const. Single source of truth. (read-only safe to add)
2. **P2 — Frontend relabel**: `Alerts.vue` foreign filter/dialog use adapter; `triggered→待处理`(display), `acknowledged→处理中`, `suppressed→已忽略`; `failed` → system badge; hide/disable `误报`.
3. **P3 — Verify**: confirm handle sends the correct underlying foreign status (`acknowledged/resolved/suppressed`); no 400/409 regressions.
4. **(Optional) P4 — Option B** only if OQ-1 resolves to "must be settable": Alembic migration widening both CHECKs + service rewrite (follow `foreign_alert_manual_review_ai_source.py` precedent).

---

## 16. Migration Strategy

- **Option A**: No migration.
- **Option B (if chosen)**: 
  - New Alembic version in `backend/alembic/versions/`.
  - `op.execute("ALTER TABLE foreign_alerts DROP CONSTRAINT ck_foreign_alerts_status")` + recreate with widened `IN (...)`.
  - Same for `foreign_alert_action` previous/new_status CHECK.
  - `downgrade()` reverses both. Idempotent; test on `opinion_test` (`DB_IDENTITY_CHECK=off`) first; `pg_dump` backup before apply (per `scripts/db_identity_check.py` + backfill pattern).
  - Staged: deploy backend (service rewrite) then frontend.

---

## 17. Verification Strategy

- Unit: adapter round-trip `disposition↔foreign_status` for all 6 states.
- API contract test: `PUT /foreign/alerts/{id}/handle` still accepts `acknowledged/resolved/suppressed`; rejects `triggered/failed` (409) — unchanged.
- DB read-only re-check: `SELECT status, count(*) FROM foreign_alerts GROUP BY status` unchanged.
- Frontend: handle dialog shows domestic labels; submit sends correct underlying status; history timeline (`foreignText`) still resolves.
- Regression: domestic handle unchanged (`alerts.py:223` untouched).

---

## 18. Open Questions

- **OQ-1 (product decision)**: Must the foreign handle be able to *set* `待处理`(pending) and `误报`(false_positive)? If yes → Option B. If "display consistency is enough" → Option A.
- **OQ-2**: Should `failed` ever be written to `foreign_alerts.status`? Currently dead. If a future "evaluation failed" state is wanted, it needs its own lifecycle + Option B.
- **OQ-3 (secondary)**: `evaluation_source` CHECK differs — domestic `{rule, manual_review_ai}` vs foreign `{rule, ai, manual_review_ai}`. Out of scope for status unification but a related cross-system inconsistency; flag for a separate audit if unifying provenance display.
- **OQ-4**: `foreign_alert_action.previous_status/new_status` CHECK must be widened in lockstep with any Option B — confirm before migration.

---

## 19. Final Decision Gate

| Item | Result |
| --- | --- |
| Domestic canonical status confirmed | ✅ `pending/processing/resolved/ignored/false_positive` |
| Foreign persistence status confirmed | ✅ `triggered/acknowledged/resolved/suppressed/failed` (failed vestigial) |
| `foreign_alerts.status` actual CHECK confirmed | ✅ via `pg_catalog` |
| Model/Schema/Service/API audited | ✅ |
| Frontend audited | ✅ `Alerts.vue` |
| Lifecycle audited | ✅ |
| Production status distribution (read-only) | ✅ 38 / 6 rows, no outliers |
| Hardcoded references scanned | ✅ 214 backend + 82 frontend |
| Semantic matrix built | ✅ §11 |
| A/B/C evaluated | ✅ §12 |
| Recommended architecture | ✅ Option A |
| Production DDL required | ✅ **NO** (Option A) / YES (Option B) |
| Historical migration required | ✅ **NO** |
| Implementation impact clarified | ✅ §14 |
| Next phase defined | ✅ §15 |
| Code/DB unchanged | ✅ PASS |

**Status: PASS** (read-only audit complete; no modifications made).

---

## 20. Files Inspected

Backend (real layer, node-read):
- `backend/app/models/alert.py` (`:45-96`)
- `backend/app/models/foreign_alert.py` (`:18-112`)
- `backend/app/models/foreign_alert_action.py` (`:24,28`)
- `backend/app/schemas/alert.py` (`:61,83,87`)
- `backend/app/api/alerts.py` (`:79,182,220,223-262`)
- `backend/app/api/foreign_alerts.py` (`:441-500`)
- `backend/app/services/foreign_alert_service.py` (`:34,236,430-445,580-665`)
- `backend/app/services/alert_service.py` (`:153`)
- `backend/alembic/versions/foreign_source_3c.py` (`:115`)
- `backend/alembic/versions/p10_phase2b1_alert_operation.py` (`:93,133`)
- `backend/alembic/versions/foreign_alert_manual_review_ai_source.py` (`:19-36`)

Frontend (real layer, node-read):
- `frontend/src/views/Alerts.vue` (`:53,58,89-99,132-133,162-175`)

Database (read-only `SELECT`):
- `pg_catalog.pg_constraint` for `ck_alert_records_status`, `ck_foreign_alerts_status`
- `alert_records` (total 38; pending 31, false_positive 7)
- `foreign_alerts` (total 6; triggered 5, acknowledged 1)

Read-only analysis scripts (temporary, not committed):
- `_db_audit.py` (SELECT-only), `_code_search.js`, `_code_search2.js`, `_fe_search.js`, `_mig_search.js`, `_mig2.js`, `_grep_failed.js`, `_read_*.js` probes.
