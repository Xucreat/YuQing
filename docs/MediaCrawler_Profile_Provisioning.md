# MediaCrawler Profile Provisioning

This document defines the operator-controlled profile preparation required
before scheduler enablement. The application only checks readiness; it never
creates, copies, migrates, or deletes browser state.

## Paths

The deployment runtime must provide two isolated directories:

```text
<MEDIA_CRAWLER_ROOT>/profiles/manual/
<MEDIA_CRAWLER_ROOT>/profiles/scheduler/
```

The current deployment has neither directory. Existing `browser_data` folders
are not treated as scheduler profiles and must not be copied automatically.

## Sources and Isolation

- The manual profile is provisioned by an operator using the approved manual
  login procedure.
- The scheduler profile is provisioned separately, with a dedicated service
  account/session and an explicit approval record.
- Never copy `browser_data/wb_user_data_dir_manual`, cookies, tokens, or
  session databases into the scheduler directory.
- Manual and scheduler runs share the source lock, but never share a browser
  profile.

## Permissions

The service account needs read/write access to its own profile directory and
read access to the MediaCrawler runtime. Profile contents must be excluded
from source control, database fields, application logs, and support bundles.

## Lifecycle and Deletion

Provisioning and rotation are deployment operations. Rotate the scheduler
session through the approved account process, stop scheduled execution first,
and retain the old profile only according to the security retention policy.
Deletion requires an explicit operator approval and must not be performed by
application startup or a failed collection.

## Risks

Missing or expired scheduler state must fail closed as a failed CollectorRun;
it must not trigger QR login, copy a manual profile, or silently run without a
profile. Profile readiness must be rechecked immediately before any enable
approval.
