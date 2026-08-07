# Phase MediaCrawler Platform-2-H Scheduler Enablement Plan

## Current State

`xhs_mediacrawler` remains:

```text
enabled=true
schedule_enabled=false
schedule_interval_minutes=60
```

No automatic XHS collection is enabled by this phase.

## Proposed First Gray Setting

After separate human approval only:

```text
enabled=true
schedule_enabled=true
schedule_interval_minutes=120
```

The two-hour interval is the initial low-risk choice because XHS login and
anti-abuse behavior are more sensitive than the existing news-site sources.

## Observation Window

For the first gray period, observe:

- login-state stability and QR/session expiry;
- duplicate rate by `source_type=xhs_note` and `external_id`;
- upstream runtime duration;
- `CollectorRun` success/failure rate;
- raw/output/created/failed counters;
- artifact retention and profile cleanup behavior.

## Safety Conditions

- Enable only `xhs_mediacrawler`; do not change the Weibo source.
- Keep the Scheduler allowlist explicit during the first observation window.
- Use non-interactive scheduler login only after a valid persistent session has
  been provisioned and reviewed.
- Do not enable the source automatically from application startup.
- Roll back by setting `schedule_enabled=false`; no schema change is required.

## Approval Boundary

This document is a readiness plan only. It does not authorize the database
update and does not start Scheduler.

```text
READY_FOR_MANUAL_SCHEDULER_APPROVAL
```

