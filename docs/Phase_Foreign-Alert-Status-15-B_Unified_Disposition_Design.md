# Phase Foreign-Alert-Status-15-B Unified Disposition Design

> **Phase type**: Design & Implementation Plan (read-only). No source / frontend / DB schema / migration / production data was modified.
> **Date**: 2026-08-14
> **Depends on**: `docs/Phase_Foreign-Alert-Status-15-A_Audit.md` (PASS). All facts below are grounded in (a) that report and (b) a fresh read of the **current working-tree** source via the node real-layer (`Read`/bash overlay mis-detects several backend `.py` files as binary; node `fs` reads valid text — see §3 note).
> **Goal**: Produce an implementation-ready design package so Phase 15-C can start without re-auditing architecture.

---

## 1. Executive Summary

The product now requires foreign alerts to support the **same "误报 (false positive)" human disposition** as domestic alerts — not just for UI parity, but because rules can wrongly trigger and operators must mark and later analyse false alarms. The previous 15-A **Option A (presentation-only mapping) is explicitly rejected** by this requirement, and **cramming the domestic 5-state vocabulary into `foreign_alerts.status` is forbidden** by the task brief.

**Recommended architecture: Option 2 — two orthogonal columns on `foreign_alerts`.**
- `status` (unchanged) = **Foreign Lifecycle Status** (`triggered / acknowledged / resolved / suppressed / failed`), owned by the existing strict `transition()` + lenient `set_status()` machinery.
- `disposition_status` (NEW) = **Unified Disposition Status** (`pending / processing / resolved / ignored / false_positive`), the human verdict, canonical vocabulary shared with domestic `alert_records.status`.

The two are **coordinated but decoupled**: a single new service method `set_disposition()` writes `disposition_status` and derives the coordinated lifecycle transition internally, so `status` never carries two domains. `false_positive` drives lifecycle to `suppressed` (same as `ignored`) but is recorded distinctly in `disposition_status` — preserving the "suppressed ≠ false_positive" semantics (principle 2). Hiding false positives is a **query/view filter** (`disposition_status != 'false_positive'`), never a `DELETE` (principle 3). No `is_hidden` column is added (§7/§11) — `disposition_status` already expresses the hide condition, avoiding duplicate semantics.

**Lifecycle state machine is untouched** (§16, principle 5): `transition()` keeps its 3 strict edges; `set_disposition()` only *orchestrates* calls into the existing lifecycle setters.

---

## 2. Confirmed Requirements

1. Foreign alerts MUST support a human "误报" disposition, equivalent in meaning to domestic `alert_records.status = 'false_positive'`.
2. Rule-triggered warnings are not always correct; operators need to mark erroneous triggers and later compute rule false-positive rates.
3. "隐藏误报" must be available on the foreign alert list, mirroring domestic — **without deleting** the original record.
4. Must NOT adopt 15-A Option A (presentation-only) as the final solution.
5. Must NOT simply copy the domestic 5 states into `foreign_alerts.status`.
6. Domestic `alert_records.status` stays as the canonical disposition vocabulary and is NOT modified (principle 4).
7. Lifecycle status and human disposition must be decoupled (principle 5).
8. Every human disposition (`resolved`/`ignored`/`false_positive`, and `processing`) must be individually auditable: who / when / which alert / what verdict (principle 6).
9. This phase is design-only — no code/DB/migration changes were made.

---

## 3. Current Architecture

> **Read-note (operational, NON-BLOCKING)**: Several backend `.py` files (e.g. `backend/app/services/foreign_alert_service.py`) are mis-detected as binary by the `Read` tool / bash `file` (magic bytes `88 7d 1c`). Node `fs` reads the **real, valid 32 KB text**. The running backend is unaffected (it imports the same real layer). The design below quotes the actual working-tree code read via node. No action is taken in this phase; flagged only for awareness (OQ-6).

### 3.1 Foreign lifecycle (authoritative, unchanged in this design)
- Model `backend/app/models/foreign_alert.py:18-22` — `status` CHECK: `triggered/acknowledged/resolved/suppressed/failed`.
- `:71` — `status` column `String(16)`, `default="triggered"`, `server_default="triggered"`.
- `foreign_alert_service.py:34` — `ALERT_STATUSES = {"triggered","acknowledged","resolved","suppressed","failed"}`.
- `:236` — `evaluate()` creates alerts with `"status": "triggered"`.
- `:430-445` — **strict** `transition()` map: `acknowledge: triggered→acknowledged`, `resolve: acknowledged→resolved`, `suppress: triggered/acknowledged→suppressed`.
- `:574-670` — **lenient** `set_status()` (domestic-style handle): target ∈ `{acknowledged,resolved,suppressed}`, excludes `triggered`/`failed`. Writes `ForeignAlertAction` audit row.
- `serialize_alert()` `:708-742` returns only `status` (no disposition yet).
- API `foreign_alerts.py:441-500` — `PUT /foreign/alerts/{id}/handle` payload `{status, note}`; `_STATUS_HANDLE_PERM` maps `acknowledged→foreign:alerts:acknowledge`, `resolved→foreign:alerts:resolve`, `suppressed→foreign:alerts:suppress`; rejects other targets with HTTP 400.
- List `list_foreign_alerts()` `:181-233` filters by `status` against the 5-value set; returns `serialize_alert`.

### 3.2 Domestic (reference, unchanged)
- `alert.py:51-53` — `status` `String(32)`, CHECK 5 (`pending/processing/resolved/ignored/false_positive`), `default/server_default="pending"`.
- `:49` — `handled` boolean dual-written with `status ∈ {resolved,ignored,false_positive} → handled=True`.
- `alerts.py:223-262` — `PUT /alerts/records/{id}/handle` free-sets `status` (any of 5), dual-writes `handled`, uses `alerts:write`.

### 3.3 Frontend (`Alerts.vue`, read via node)
- `:58` foreign filter uses lifecycle values (待确认/已确认/已解决/已抑制/失败).
- `:69` foreign list "处置状态" column renders `foreignText(row.status)` — i.e. it shows **lifecycle** as the disposition column today (the core mismatch).
- `:89-93` foreign handle dialog offers only `acknowledged/resolved/suppressed`.
- `:94-99` domestic handle dialog offers the 5 disposition states incl. 误报.
- `:132` `STATUS_TEXT` (domestic 5) and `FOREIGN_TEXT` (foreign 5) maps coexist.
- `:54` domestic already has a `隐藏误报` switch (`exclude_status='false_positive'`). Foreign has none.

### 3.4 Production data (read-only SELECT, this phase)
- `foreign_alerts` = 6: `triggered`=5, `acknowledged`=1 (all `rule_id=3`); `foreign_alert_actions`=6.
- `alert_records` = 38: `pending`=31, `false_positive`=7.
- No `status` outside either CHECK. `failed` never written (confirmed again).

---

## 4. Two Status Domains

### A. Foreign Lifecycle Status (`status`, unchanged)
| State | Meaning | Produced by | Modified by | Human-settable? | Terminal? | Re-enterable? |
|---|---|---|---|---|---|---|
| `triggered` | Born by rule engine, unacknowledged | `evaluate()` | `transition()/set_status()` | No (excluded target) | No | → acknowledged/resolved/suppressed |
| `acknowledged` | Seen / owner assigned / in progress | `transition(acknowledge)` / `set_status(acknowledged)` | same | Yes (handle) | No | → resolved / suppressed |
| `resolved` | Closed as a real, validated alert | `transition(resolve)` / `set_status(resolved)` | same | Yes (handle) | **Yes** | No |
| `suppressed` | Muted / ended without resolution | `transition(suppress)` / `set_status(suppressed)` | same | Yes (handle) | **Yes** | No |
| `failed` | System/error state (never produced) | — | — | No | n/a | n/a |

**`failed` is retained** in the CHECK per the brief ("不要因为它当前没有数据就擅自删除"). It is a *system* lifecycle state, never a human disposition, and never written today. If a future "evaluation failed" state is wanted it needs its own decision (OQ-2).

### B. Unified Disposition Status (`disposition_status`, NEW)
| State | Meaning | Maps to lifecycle (coordinated) |
|---|---|---|
| `pending` | New alert in the human disposition queue. **Initial default only; not a manual button.** | (no lifecycle change — stays `triggered`) |
| `processing` | A human has begun handling it. | `triggered→acknowledged` (if still triggered) |
| `resolved` | Human confirms it is a valid alert and completes disposition. | `→resolved` |
| `ignored` | Human judges it need not be treated as a valid alert. | `→suppressed` |
| `false_positive` | Human judges the rule/system wrongly triggered it. | `→suppressed` |

**`ignored` ≠ `false_positive`** (explicit, principle 2): `ignored` = "not relevant / triaged away"; `false_positive` = "the alert was *wrong* (rule/system error)". Both end the lifecycle the same way (`suppressed`) but the disposition column preserves *why*, which is exactly what the rule-quality analytics (§17) need.

---

## 5. Lifecycle × Disposition Matrix

Only **5 canonical persistent combinations** are valid. `pending` and `processing` are initial/in-progress; `resolved/ignored/false_positive` are final verdicts.

| lifecycle \ disposition | pending | processing | resolved | ignored | false_positive |
|---|---|---|---|---|---|
| `triggered` | ✅ initial | ❌ (coords→acknowledged) | ✅ via 已解决 (lenient→resolved) | ❌ (coords→suppressed) | ❌ (coords→suppressed) |
| `acknowledged` | ❌ (once acked, ≥processing) | ✅ | ✅ | ✅ (→suppressed) | ✅ (→suppressed) |
| `resolved` | ❌ | ❌ | ✅ terminal | ❌ conflict | ❌ conflict |
| `suppressed` | ❌ | ❌ | ❌ conflict | ✅ terminal | ✅ terminal |
| `failed` | ❌ (system state) | ❌ | ❌ | ❌ | ❌ |

**Canonical persistent states (the target set):**
1. `(triggered, pending)` — just created.
2. `(acknowledged, processing)` — acknowledged / being handled.
3. `(resolved, resolved)` — valid alert, closed.
4. `(suppressed, ignored)` — muted, triaged away.
5. `(suppressed, false_positive)` — muted, judged erroneous.

**Forbidden examples (must be rejected by `set_disposition`):**
- `resolved + ignored/false_positive` — a closed *valid* alert cannot also be "not actionable"/"wrong".
- `suppressed + resolved` — a muted alert cannot also be "valid & resolved".
- `triggered + false_positive` directly — must go through `suppressed` first (coordinated).
- `failed + anything` — `failed` is outside human disposition.

The matrix is enforced by `set_disposition()` (§9), not by a DB CHECK (the two columns are independent; the constraint is business logic). Rationale: a DB composite CHECK would forbid the legitimate *transient* during a coordinated transition and complicates the additive migration. Service-level enforcement with a unit test is sufficient and matches how domestic `handled` dual-write is enforced in code, not by constraint.

---

## 6. False Positive Workflow

```
foreign alert
   │  evaluate() → status='triggered', disposition_status='pending'  (auto, on creation)
   ▼
[ operator clicks "处理中" ]      →  disposition=processing, lifecycle triggered→acknowledged
   ▼
[ operator judges the alert ]
   ├── "已解决"   → disposition=resolved,    lifecycle →resolved
   ├── "已忽略"   → disposition=ignored,     lifecycle →suppressed
   └── "误报"     → disposition=false_positive, lifecycle →suppressed
```

**When the operator clicks "误报" (the core §9 question):**
- `disposition_status = 'false_positive'`
- `status = 'suppressed'` (lifecycle ends, same as `ignored`)
- The **distinction** is carried entirely by `disposition_status`. This is the recommended answer: `false_positive` is a *disposition verdict*, not a *lifecycle state*; lifecycle ends (`suppressed`) exactly as for `ignored`, but the record now answers "was this alert wrong?" = yes.

Why not keep lifecycle as-is for false_positive? Because an un-suppressed (`triggered`/`acknowledged`) alert is still "active" in the lifecycle sense; leaving it active while calling it a false positive would keep it in active queues and contradict the "ended" semantics. Driving `suppressed` cleanly closes the lifecycle while `disposition_status` preserves the verdict.

---

## 7. Hidden False Positive Design

- **No `is_hidden` / `hidden_at` / `hidden_by` column is added.** `disposition_status = 'false_positive'` *is* the hide condition (§11).
- Default list query: `WHERE disposition_status != 'false_positive'` (or, equivalently, a `disposition_filter` enum defaulting to `hide_fp`).
- `ignored` is **NOT** hidden by default — only `false_positive` is (per requirement; they are distinct).
- Three view modes (recommended):
  - **隐藏误报** (default): `exclude disposition_status='false_positive'`.
  - **全部**: no disposition filter.
  - **仅误报**: `disposition_status='false_positive'` (for review / analytics).
- Deletion is never used; "hide" is a display/filter concern only (principle 3).

---

## 8. API Contract

**Recommended surface: `disposition_status` is the primary verb; `status` becomes coordinated internally (so `status` stops carrying two domains).**

```jsonc
// PUT /foreign/alerts/{id}/handle
{
  "disposition_status": "false_positive",   // NEW, primary. One of the 5 disposition states.
  "note": "规则误报，已复核",                 // required (existing note policy)
  "status": "suppressed"                     // OPTIONAL legacy field.
}
```

Rules:
1. **New unified flow** sends `disposition_status`. The service derives/validates the coordinated lifecycle transition (§6/§9) and writes **both** columns atomically.
2. **Backward compatibility**: if `disposition_status` is omitted but legacy `status` is present, map it to a disposition (`acknowledged→processing`, `resolved→resolved`, `suppressed→ignored`) and proceed — old clients keep working.
3. If **both** are present, `disposition_status` is authoritative; `status` (if given) must be consistent with the coordinated target or it is rejected (409).
4. Validation: `disposition_status ∈ {pending,processing,resolved,ignored,false_positive}`; `status ∈ ALERT_STATUSES`; the resulting combination must satisfy §5.
5. Permission is checked by disposition value (§11), not by `status`.

This satisfies §12's mandate: `status` no longer bears two domains — it is purely the lifecycle, set by the service from the human's disposition intent.

---

## 9. Backend Service Design

- **Keep `transition()` and `set_status()` exactly as-is** (lifecycle owners; strict machine preserved — principle 5 / §16).
- **Add `ForeignAlertService.set_disposition()`**:

```python
# PROPOSED (not applied). Coordination only; no domain conflation.
DISPOSITION_STATES = {"pending","processing","resolved","ignored","false_positive"}
# coordinated lifecycle target per disposition action
_DISP_LIFECYCLE = {
    "processing": "acknowledged",
    "resolved":   "resolved",
    "ignored":    "suppressed",
    "false_positive": "suppressed",
    # pending: no lifecycle change (initial only)
}

@staticmethod
def set_disposition(db, alert_id, *, disposition_status, note, user_id):
    disposition_status = (disposition_status or "").strip().casefold()
    if disposition_status not in DISPOSITION_STATES:
        raise ValueError(f"Unsupported disposition_status: {disposition_status}")
    # matrix guard
    alert = db.scalar(select(ForeignAlert).where(ForeignAlert.id==alert_id).with_for_update())
    if alert is None or alert.evaluation_source not in {"rule","manual_review_ai"}:
        raise LookupError("Foreign alert not found")
    _assert_disposition_allowed(alert.status, disposition_status)  # enforces §5
    target_lifecycle = _DISP_LIFECYCLE.get(disposition_status)
    if target_lifecycle and alert.status != target_lifecycle:
        # reuse existing lifecycle setter (strict or lenient as appropriate)
        ForeignAlertService.set_status(db, alert_id, status=target_lifecycle,
                                       note=note, user_id=user_id)
    alert.disposition_status = disposition_status
    alert.updated_at = _utcnow()
    # audit (§10)
    db.add(ForeignAlertDispositionAction(foreign_alert_id=alert.id,
            previous_disposition=old_disp, new_disposition=disposition_status,
            note=note, actor_id=user_id))
    db.commit(); db.refresh(alert)
    return alert
```

- `pending` is **not** offered as a manual action, so `_DISP_LIFECYCLE` has no entry for it; setting it programmatically remains possible (initial creation only). If a future "reopen" is needed, see OQ-1.
- `set_disposition` is the **only** writer of `disposition_status`. Lifecycle setters never touch it (decoupling).

---

## 10. Audit Log Design

**Recommended: Option B — new dedicated table `foreign_alert_disposition_actions`.**

```python
# PROPOSED model (not applied)
class ForeignAlertDispositionAction(Base):
    __tablename__ = "foreign_alert_disposition_actions"
    __table_args__ = (
        CheckConstraint(
            "previous_disposition IN ('pending','processing','resolved','ignored','false_positive')",
            name="ck_fa_disp_act_prev"),
        CheckConstraint(
            "new_disposition IN ('pending','processing','resolved','ignored','false_positive')",
            name="ck_fa_disp_act_new"),
        Index("ix_fa_disp_act_alert_id", "foreign_alert_id"),
        Index("ix_fa_disp_act_created_at", "created_at"),
    )
    id, foreign_alert_id FK(foreign_alerts, CASCADE),
    previous_disposition, new_disposition, note,
    actor_id FK(users), created_at, metadata_json JSONB
```

Rationale (vs Option A — extending `ForeignAlertAction`):
- Keeps the **lifecycle** audit (`ForeignAlertAction`, with its `action_type IN (acknowledge,resolve,suppress)` and 5-value status CHECKs) **pristine** — no CHECK widening of the lifecycle domain (principle 1/5).
- Disposition history is **independently queryable**, e.g. "all false_positive verdicts by user X in range" for rule-quality analytics (§17) — a single-column query, not a JSON dig.
- Mirrors the project's existing pattern of separate `*_actions` tables (`foreign_alert_actions`, `foreign_alert_admission_actions`).
- Every false_positive click now yields a row: `who (actor_id) / when (created_at) / which alert (foreign_alert_id) / what (new_disposition='false_positive')` — satisfies principle 6.

Option A (add `previous_disposition`/`new_disposition` nullable columns + their own CHECKs to `ForeignAlertAction`) is viable and lighter (one table, one timeline) but couples lifecycle and disposition audit rows; **B is preferred** for clean separation. Either is acceptable; the implementation phase may pick A if migration simplicity is prioritised — flag in 15-C.

---

## 11. Permission Design

Current foreign perms: `foreign:alerts:acknowledge`, `foreign:alerts:resolve`, `foreign:alerts:suppress`. Domestic uses single `alerts:write`.

`foreign:alerts:false_positive` (required) — maps to `disposition_status='false_positive'`. Reusing `foreign:alerts:suppress` would conflate "muted" with "wrong alert" in both the permission model and the audit, and would let a `suppress`-only operator mark false positives unintentionally. A dedicated permission lets admins grant suppress without granting false-positive marking, and makes the sensitive "rule was wrong" verdict explicitly controllable.

`set_disposition` permission map:
| disposition | required permission |
|---|---|
| processing | `foreign:alerts:acknowledge` |
| resolved | `foreign:alerts:resolve` |
| ignored | `foreign:alerts:suppress` |
| false_positive | `foreign:alerts:false_positive` (NEW) |
| pending | none (initial/auto only) |

Domestic `alert_records.status` is unchanged (principle 4); for symmetry a future `alerts:false_positive` could be added but is **out of scope** (OQ-3).

---

## 12. Frontend Design (`Alerts.vue`)

Goal: foreign UX converges with domestic, showing the **unified disposition** as primary.

1. **Columns**: foreign list "处置状态" column renders `disposition_status` via `STATUS_TEXT` (待处理/处理中/已解决/已忽略/误报) as the main tag; show lifecycle as a **secondary sub-badge** (`来源生命周期: {foreignText(row.status)}`) for traceability. (Today it wrongly shows `foreignText(row.status)` — fix this.)
2. **Handle dialog** (`:89-93`): replace the 3 lifecycle options with the 4 manual disposition actions — 处理中 / 已解决 / 已忽略 / 误报. (No "待处理" button; it is initial/display-only.)
3. **`submitHandle`** (`:163-175`): for foreign, send `{ disposition_status: handleForm.disposition }` (keep optional `status` for legacy). Reuse `STATUS_TEXT` for labels.
4. **Filter bar** (`:57-62`): add a disposition filter + a 全部 / 隐藏误报(默认) / 仅误报 segmented control, mirroring domestic `隐藏误报` (`:54`). Keep the lifecycle `status` filter as an "advanced" selector.
5. **History dialog** (`:86`): show both lifecycle actions (`foreign_alert_actions`) and disposition actions (`foreign_alert_disposition_actions`) — two timelines or merged by `created_at`.
6. Lifecycle `failed` remains a system badge (never a disposition) — display only.

---

## 13. Query / Filter / Statistics Design

- `GET /foreign/alerts` gains:
  - `disposition_status` (exact match, validated against 5-set, else 422).
  - `disposition_filter` enum: `all` | `hide_fp` (default) | `only_fp`. Default hides false positives; **does NOT hide `ignored`**.
  - Keep existing `status` (lifecycle) filter for advanced use.
- **Default list** must NOT hide `ignored` — only `false_positive` is filtered by default (fixes the risk that lumping `suppressed`/`ignored`/`false_positive` together would wrongly hide valid `ignored` rows).
- **Statistics** (new endpoint or extended `/foreign/alerts/stats`):
  - counts by `disposition_status`;
  - handling rate = `(resolved+ignored+false_positive)/total`;
  - per-rule false-positive rate (§17).
- Pagination / sorting unchanged (existing `page/size` + `triggered_at desc`).

---

## 14. Database Schema Design

**Column `foreign_alerts.disposition_status`** (follows existing project pattern: `String` + `CheckConstraint`, *not* SQLAlchemy `Enum` — see `alert.py:51`, `foreign_alert.py:71`):

```python
# PROPOSED (model addition, not applied)
disposition_status: Mapped[str] = mapped_column(
    String(16), nullable=False, default="pending", server_default="pending"
)
# in __table_args__:
CheckConstraint(
    "disposition_status IN ('pending','processing','resolved','ignored','false_positive')",
    name="ck_foreign_alerts_disposition_status",
),
Index("ix_foreign_alerts_disposition_status", "disposition_status"),
```

- **Name**: `disposition_status` (per brief; fits the `status`/`evaluation_source` naming of the table).
- **Type**: `String(16)` + CHECK (matches domestic `String(32)`/`String(16)` style).
- **Default**: `default="pending"`, `server_default="pending"` — new alerts enter `pending`.
- **Nullable**: `False` (always has a verdict; default covers creation).
- **CHECK**: the 5 disposition states.
- **Index**: **YES** — the default list filters `!= 'false_positive'` and stats group by it; an index avoids seq scans as data grows.
- **New table** `foreign_alert_disposition_actions` (§10, Option B).

---

## 15. Historical Data Migration

Current prod: `foreign_alerts`=6 (`triggered`=5, `acknowledged`=1), all `rule_id=3`. **Design only — not executed.**

Backfill rule (deterministic, idempotent):
| existing `status` | → `disposition_status` |
|---|---|
| `triggered` | `pending` |
| `acknowledged` | `processing` |
| `resolved` | `resolved` |
| `suppressed` | `ignored` |
| `failed` | `pending` (fallback; none exist) |

- Safe: additive column with `server_default`; backfill only fills the new column, no semantic loss.
- Idempotent: re-running yields the same values.
- **Downgrade**: `DROP COLUMN disposition_status` + `DROP TABLE foreign_alert_disposition_actions`. Because the column/table are new and additive, dropping them loses only the newly-computed disposition data, which is fully reconstructable from `status` via the same rule. No historical domestic-style data is destroyed.
- Identity check: the backfill writes data, so it must run with `DB_IDENTITY_CHECK=off` (per the project's `scripts/db_identity_check.py` + backfill pattern); `pg_dump` backup taken before apply (same safety as 15-A/①B).

---

## 16. Lifecycle State Machine Compatibility

- **`transition()` is NOT modified** — its 3 strict edges remain the only path for automated/evaluate/manual-review lifecycle moves.
- `set_disposition()` may call `set_status()` (lenient) to coordinate lifecycle (e.g. `suppressed` for `ignored`/`false_positive`, `resolved` for `resolved`, `acknowledged` for `processing`). It never calls `transition()` for the lenient jumps, preserving the explicit strict-vs-lenient split already in the code.
- `false_positive ⇒ status='suppressed'` goes through the **existing** `set_status('suppressed')` path, so `status` only ever takes values from `ALERT_STATUSES`. No new lifecycle value is introduced.
- Regression test mandated (§22): `transition()` behaviour must be byte-for-byte unchanged.

---

## 17. Rule False-positive Analytics

- `foreign_alerts.rule_id` already exists (FK + `ix_foreign_alerts_rule_id`).
- With `disposition_status`, per-rule false-positive rate is:
  ```
  trigger_count      = SELECT count(*) FROM foreign_alerts WHERE rule_id = :r
  fp_count           = SELECT count(*) FROM foreign_alerts WHERE rule_id = :r AND disposition_status = 'false_positive'
  fp_rate            = fp_count / trigger_count
  ```
- **No new fields needed** (principle: no duplicate data). The new `foreign_alert_disposition_actions` table also supports "who marked what false positive when" for deeper analysis.

---

## 18. Architecture Alternatives

| Option | Description | Verdict |
|---|---|---|
| 1 | Copy domestic 5 states into `foreign_alerts.status` | **REJECTED** — brief forbids; collapses lifecycle semantics; violates principle 1. |
| **2** | `status` (lifecycle) + `disposition_status` (unified) dual columns | **RECOMMENDED** — clean separation, indexable, matches domestic `status`+`handled` dual-write pattern, additive & low-risk. |
| 3 | Separate `disposition` table only (no column on `foreign_alerts`) | Rejected — list/hide queries would need a JOIN; less convenient for the default `!= false_positive` filter and indexing; more complex for the common read path. |
| 4 | 15-A Option A (presentation-only) | **REJECTED** by the new requirement — `false_positive` must be *settable* on foreign. |
| (audit) A vs B | Extend `ForeignAlertAction` vs new `foreign_alert_disposition_actions` table | **B preferred** (§10); A acceptable if migration simplicity wins in 15-C. |

**Recommendation: Option 2 + audit Option B.**

---

## 19. Recommended Architecture

```
                Foreign Lifecycle (status)          Unified Disposition (disposition_status)
                -------------------------           --------------------------------------
                triggered  ──acknowledge──▶ acknowledged ──resolve──▶ resolved (terminal)
                     │                                   │
                     └──suppress──▶ suppressed (terminal) ┘
                                                   │
                                        Human Disposition (set_disposition)
                                                   │
              ┌────────────────────────┬───────────┴───────────┬──────────────────┐
              ▼                        ▼                       ▼                  ▼
         processing               resolved                 ignored          false_positive
     (lifecycle→acknowledged)  (lifecycle→resolved)   (lifecycle→suppressed) (lifecycle→suppressed)
                                                   │
                                    default list hides ONLY false_positive
                                    (ignored stays visible)
```

- `status` = system lifecycle (owned by `transition()`/`set_status()`).
- `disposition_status` = human verdict (owned by `set_disposition()`).
- `set_disposition` coordinates lifecycle internally; `status` never carries two domains.
- `false_positive` and `ignored` both end lifecycle as `suppressed` but differ in `disposition_status`.
- "Hide false positive" = `disposition_status != 'false_positive'` filter; no delete; no `is_hidden` column.

---

## 20. Implementation Phases (Phase 15-C)

| Phase | Scope | Files (modify) | Risk | Tests | Acceptance |
|---|---|---|---|---|---|
| **15-C1 DB Migration** | Add column + CHECK + index + new table + backfill | `backend/alembic/versions/<new>.py` | Low (additive) | migration upgrade/downgrade on `opinion_test` | column/index/table exist; backfill correct; downgrade clean |
| **15-C2 Model / Schema / Service** | `disposition_status` column; `ForeignAlertDispositionAction` model; `set_disposition()`; `serialize_alert` adds `disposition_status`; `DISPOSITION_STATES` | `models/foreign_alert.py`, `models/foreign_alert_disposition_action.py`(new), `services/foreign_alert_service.py`, `schemas/*` | Medium | unit: 5 states legal, illegal rejected, matrix guard, lifecycle coord | service writes both columns atomically; `transition()` unchanged |
| **15-C3 API** | Extend `ForeignAlertHandlePayload` (`disposition_status`); rewrite handle route to call `set_disposition`; add `disposition_status`/`disposition_filter` to list; permission map (incl. new `foreign:alerts:false_positive`); seed perm | `api/foreign_alerts.py`, permission seed | Medium | API tests (§22) | handle accepts disposition; legacy `status` still works; 400/403/409 correct |
| **15-C4 Frontend** | Disposition column + sub-badge; 4-action dialog; `submitHandle` sends `disposition_status`; filter + 全部/隐藏误报/仅误报; history shows disposition actions | `frontend/src/views/Alerts.vue` | Medium | manual + e2e (§22) | UI matches domestic; false positive hides by default but visible via 仅误报 |
| **15-C5 Audit / Permission** | Register `foreign:alerts:false_positive` in permission catalog/seed; document mapping | permission config/seed | Low | perm test | new perm enforceable |
| **15-C6 Tests** | Backend unit + API + DB + frontend (§22) | `backend/tests/*`, `frontend/*` | Low | full suite green | coverage of matrix + regression |
| **15-C7 Production Read-only Verification** | `SELECT` distribution pre/post; no data loss | (none modified) | Low | report | counts consistent; backfill idempotent |
| **15-C8 Frontend Build / Deployment** | `vite build` (clear `.vite` cache), `cpSync` dist→`backend/app/static`, restart uvicorn (with migration applied first) | build pipeline | Low | smoke test | UI shows disposition; handle works |

> Note: clear `frontend/node_modules/.vite` before build (stale build-cache trap observed in prior phases).

---

## 21. Migration Strategy

```python
# PROPOSED Alembic (not applied). Follows precedent
# backend/alembic/versions/foreign_alert_manual_review_ai_source.py
def upgrade():
    # 1) new disposition column (additive, NOT NULL + server_default => safe backfill)
    op.add_column("foreign_alerts",
        sa.Column("disposition_status", sa.String(16), nullable=False,
                  server_default="pending"))
    op.create_check_constraint(
        "ck_foreign_alerts_disposition_status", "foreign_alerts",
        "disposition_status IN ('pending','processing','resolved','ignored','false_positive')")
    op.create_index("ix_foreign_alerts_disposition_status",
                    "foreign_alerts", ["disposition_status"])
    # 2) new audit table
    op.create_table("foreign_alert_disposition_actions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("foreign_alert_id", sa.Integer,
                  sa.ForeignKey("foreign_alerts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_disposition", sa.String(16), nullable=False),
        sa.Column("new_disposition", sa.String(16), nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("actor_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("metadata", sa.dialects.postgresql.JSONB, nullable=False,
                  server_default="{}"),
        sa.CheckConstraint("previous_disposition IN (...5...)","ck_fa_disp_act_prev"),
        sa.CheckConstraint("new_disposition IN (...5...)","ck_fa_disp_act_new"),
    )
    op.create_index("ix_fa_disp_act_alert_id","foreign_alert_disposition_actions",["foreign_alert_id"])
    op.create_index("ix_fa_disp_act_created_at","foreign_alert_disposition_actions",["created_at"])
    # 3) historical backfill (idempotent; run with DB_IDENTITY_CHECK=off; pg_dump first)
    op.execute("""
        UPDATE foreign_alerts SET disposition_status =
          CASE status
            WHEN 'triggered' THEN 'pending'
            WHEN 'acknowledged' THEN 'processing'
            WHEN 'resolved' THEN 'resolved'
            WHEN 'suppressed' THEN 'ignored'
            ELSE 'pending' END
        WHERE disposition_status IS NULL OR disposition_status = 'pending'
    """)

def downgrade():
    op.drop_index("ix_fa_disp_act_created_at", table_name="foreign_alert_disposition_actions")
    op.drop_index("ix_fa_disp_act_alert_id", table_name="foreign_alert_disposition_actions")
    op.drop_table("foreign_alert_disposition_actions")
    op.drop_index("ix_foreign_alerts_disposition_status", table_name="foreign_alerts")
    op.drop_constraint("ck_foreign_alerts_disposition_status", "foreign_alerts")
    op.drop_column("foreign_alerts", "disposition_status")
```

- `failed` stays in the lifecycle CHECK (unchanged). The new disposition CHECK is independent.
- `down_revision` must chain after the latest migration (resolve at 15-C1 time).

---

## 22. Test Strategy

**Backend Unit**
- 5 disposition states accepted; illegal value rejected (422/400).
- `set_disposition` matrix guard: rejects forbidden combos (e.g. `resolved+ignored`, `triggered+false_positive` without suppress).
- lifecycle ↔ disposition coordination correct (`false_positive`→`suppressed`, `ignored`→`suppressed`, `resolved`→`resolved`, `processing`→`acknowledged`).
- `ignored` ≠ `false_positive` (distinct `disposition_status` values; both end `suppressed`).
- `transition()` unchanged (regression).

**API**
- Domestic `PUT /alerts/records/{id}/handle` unaffected.
- Foreign handle with `disposition_status` works; legacy `status`-only still works (mapped).
- Permission: missing perm → 403; unknown disposition → 400; forbidden combo → 409.
- Idempotent re-submit returns existing/updated state.
- List `disposition_filter`: `hide_fp` (default, excludes only `false_positive`), `all`, `only_fp`.

**Database**
- CHECK enforces 5 disposition values; default `pending`; NOT NULL; index exists.
- Migration `upgrade` then `downgrade` on `opinion_test` returns schema to baseline; backfill idempotent.

**Frontend**
- 5-state display (待处理/处理中/已解决/已忽略/误报); lifecycle sub-badge.
- Default hides false positives; 全部 shows them; 仅误报 shows only them.
- Click 误报 → lifecycle becomes 已抑制, disposition 误报; click 已忽略 → 已忽略.
- Status refresh + pagination/filter work; history shows disposition actions.

**Regression**
- `ForeignAlertService.transition()` behaviour identical (no new edges).
- Existing `foreign_alert_actions` rows/flows intact.

---

## 23. Production Rollout Strategy

Additive migration ⇒ **zero-downtime capable**:
1. **Apply migration** (additive column + table + backfill). Old backend ignores the new column (it only writes `status`; new column gets `server_default`). Safe.
2. **Deploy backend** (new code reads/writes `disposition_status`, API accepts `disposition_status`, legacy `status` mapped). Old frontend still sends `status` → mapped to disposition. No 500.
3. **Deploy frontend** last (shows disposition, sends `disposition_status`).

Short version skew is safe because: (a) the column is additive with a default, (b) the API accepts both old and new payloads, (c) `transition()` is untouched. Recommend staging: migration → backend → frontend, with a health check between steps.

---

## 24. Rollback Strategy

- **Code**: revert frontend then backend to pre-15-C tags.
- **DB**: run migration `downgrade()` — drops the new table and column. Because both are additive and the disposition data is fully reconstructable from `status` via the backfill rule, rollback loses no pre-existing data. (Any *new* false_positive verdicts recorded between deploy and rollback are lost — acceptable; they can be re-marked.)
- **Perm**: remove `foreign:alerts:false_positive` from seed if rolled back.

---

## 25. Open Questions

- **OQ-1 (NON-BLOCKING)**: Should operators be able to **reopen/reset** an alert to `pending` (e.g. from `suppressed+false_positive` back to `triggered+pending`)? Current design treats `pending` as initial/display-only (no manual button) to keep the matrix clean. If product wants reopen, add a `reopen` disposition action (maps to `triggered`, requires `foreign:alerts:acknowledge`). *Blocks nothing — implement as a later enhancement.*
- **OQ-2 (NON-BLOCKING)**: Should `failed` lifecycle ever be produced? Today it is dead. Keep in CHECK; if a future "evaluation failed" state is wanted, decide separately (it is a system state, never a disposition).
- **OQ-3 (NON-BLOCKING)**: For domestic/foreign symmetry, should domestic also gain a dedicated `alerts:false_positive` permission? Out of scope (domestic unchanged, principle 4). Flag for a separate decision.
- **OQ-4 (NON-BLOCKING)**: If `failed` is ever produced, what `disposition_status` applies? Recommend `pending` or `processing` (system error, not a human verdict) — decide when `failed` is implemented.
- **OQ-5 (NON-BLOCKING)**: Audit Option A vs B (§10) — B preferred; 15-C may choose A for fewer objects. Does not block design.
- **OQ-6 (OPERATIONAL, NON-BLOCKING)**: Node real-layer vs bash/Read overlay reports `foreign_alert_service.py` (and possibly others) as binary (`88 7d 1c`) while node reads valid text and the running backend is fine. Tooling artifact only; no code action in this phase. Recommend a separate investigation of the overlay corruption outside 15-B.

No **BLOCKING** questions — the design is complete and implementation-ready.

---

## 26. Final Decision Gate

| Item | Result |
|---|---|
| 15-A report read & used as fact base | ✅ |
| lifecycle vs disposition clearly separated | ✅ (two columns) |
| five unified dispositions defined | ✅ pending/processing/resolved/ignored/false_positive |
| `false_positive` semantics explicit | ✅ distinct from `ignored`/`suppressed` |
| `ignored` vs `false_positive` distinguished | ✅ |
| lifecycle × disposition matrix built | ✅ §5 (5 canonical states + forbidden list) |
| state transitions designed | ✅ `set_disposition` coordinates lifecycle |
| "hide false positive" designed | ✅ filter on `disposition_status`, no delete |
| `is_hidden` field justified (not added) | ✅ §7/§11 |
| API contract designed | ✅ `disposition_status` primary, legacy `status` compat |
| backend service designed | ✅ `set_disposition` added; `transition()`/`set_status()` kept |
| audit log designed | ✅ new `foreign_alert_disposition_actions` (Option B) |
| permission designed | ✅ + new `foreign:alerts:false_positive` |
| frontend designed | ✅ disposition column + 4-action dialog + filters |
| query/filter/stats designed | ✅ `disposition_status`/`disposition_filter` |
| DB schema designed | ✅ column + CHECK + index + table |
| migration upgrade/downgrade designed | ✅ §21 |
| historical backfill designed | ✅ §15 (idempotent, safe) |
| strict lifecycle compatibility confirmed | ✅ `transition()` untouched |
| rule false-positive analytics feasible | ✅ `rule_id` + `disposition_status`, no new fields |
| alternatives compared | ✅ §18 (Option 2 recommended) |
| recommended architecture stated | ✅ §19 |
| implementation phases split | ✅ 15-C1..C8 |
| test strategy defined | ✅ §22 |
| rollout strategy defined | ✅ §23 (zero-downtime capable) |
| rollback strategy defined | ✅ §24 |
| open questions listed | ✅ §25 (all NON-BLOCKING) |
| **No source modified** | ✅ |
| **No DB modified** | ✅ |
| **No migration created/run** | ✅ |
| **No production data modified** | ✅ |

**Status: PASS**
