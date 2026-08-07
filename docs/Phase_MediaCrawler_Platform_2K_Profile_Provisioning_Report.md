# Phase MediaCrawler Platform-2-K Profile Provisioning Report

## 1. Current Status

```text
READY_FOR_SCHEDULER_GRAY
```

This phase completed offline provisioning and operator QR login verification.
It did not enable scheduling or run Scheduler.

## 2. Profile Architecture

The trigger-scoped contract is:

```text
<profile_root>/<platform>/<source_key>/<trigger>
```

XHS paths:

```text
manual:    C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_mediacrawler\profiles\xiaohongshu\xhs_mediacrawler\manual
scheduler: C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_mediacrawler\profiles\xiaohongshu\xhs_mediacrawler\scheduler
```

The RuntimeFactory resolves the scheduler path correctly. The profile adapter
keeps browser/session state isolated and does not change checkout-relative
subprocess imports.

## 3. Provisioning Result

The scheduler profile now contains the controlled provisioning marker plus the
operator-created browser/session state:

```text
exists: true
entry_count: 312 files
marker: PROFILE_PROVISIONING.json
marker_credentials_persisted: false
operator_login_completed: true
```

The marker is deployment metadata only and contains no credentials. The
browser/session state is stored locally under the isolated scheduler profile;
its contents were not printed, committed, or stored in the database.

## 4. Runtime Environment Verification

An isolated child process was launched for verification only. It inherited:

```text
SCHEDULER_SOURCE_ALLOWLIST=xhs_mediacrawler
```

Observed result:

```text
status: PASS
process_environment: xhs_mediacrawler
scheduler_config_allowlist: [xhs_mediacrawler]
repository_scheduled_include_keys: [xhs_mediacrawler]
repository_due_include_keys: [xhs_mediacrawler]
collector_include_data_source_keys: [xhs_mediacrawler]
dispatch_trigger_type: scheduled
scheduler_loop_started: false
```

The probe replaced database/session/service boundaries with in-memory probes;
it did not call CollectorService work and did not launch MediaCrawler.

## 5. Allowlist Verification

The process-scoped allowlist is read by
`backend/app/core/scheduler.py` from `SCHEDULER_SOURCE_ALLOWLIST`. It is passed
through repository candidate discovery and CollectorService dispatch.

Current database state remains:

```text
DataSource.id: 45
key: xhs_mediacrawler
enabled: true
schedule_enabled: false
schedule_interval_minutes: 60
```

Consequently, the real current candidate query returns no XHS candidate even
when the allowlist is simulated. The allowlist does not bypass
`schedule_enabled`.

## 6. Scheduler Safety Confirmation

- 8000 backend health: HTTP 200.
- Current backend PID: 24032.
- Current scheduler advisory lock owner: none.
- No Scheduler loop was started by this phase.
- `schedule_enabled` was not changed.
- The live process environment variable could not be safely inspected from the
  current read-only Windows process inspection; its value is recorded as
`UNKNOWN`, not inferred from the current shell. The separate child-process
propagation probe passed.

## 7. Regression Result

```text
pytest backend/tests/test_media_crawler*.py -q: 190 passed, 1 warning
python -m compileall -q backend/app: PASS
git diff --check: PASS
```

The warning is the existing Pydantic class-based-config deprecation warning.

Protected paths were unchanged:

```text
backend/app/models/           NONE
backend/alembic/              NONE
backend/app/core/scheduler.py NONE
.env                          NONE
```

## 8. Files Changed In This Phase

The phase added only these reports:

```text
docs/Phase_MediaCrawler_Platform_2K_Profile_Audit.md
docs/Phase_MediaCrawler_Platform_2K_Profile_Provisioning_Report.md
```

The provisioning and verification scripts/tests referenced by this report
were already present in the working tree and were exercised without changing
their implementation in this phase.

## 9. Final Decision

```text
READY_FOR_SCHEDULER_GRAY
```

The next controlled operation is the J2 gray-enable preflight and explicit
human approval. Keep `schedule_enabled=false` and do not start Scheduler until
the allowlist is injected into the new Scheduler process and the one-source
candidate check returns only `xhs_mediacrawler`.
