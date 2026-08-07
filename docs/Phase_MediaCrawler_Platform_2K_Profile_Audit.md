# Phase MediaCrawler Platform-2-K Profile Architecture Audit

## Scope

This is an offline profile and runtime audit only. No DataSource was changed,
the Scheduler was not started, and no MediaCrawler subprocess was launched.

## Profile Contract

The application profile contract is:

```text
<profile_root>/<platform>/<source_key>/<trigger>
```

For XHS the resolved paths are:

```text
manual:    runtime/mediacrawler/xhs_mediacrawler/profiles/xiaohongshu/xhs_mediacrawler/manual
scheduler: runtime/mediacrawler/xhs_mediacrawler/profiles/xiaohongshu/xhs_mediacrawler/scheduler
```

`MediaCrawlerProfileManager.normalize_trigger()` maps `scheduled` to the
`scheduler` scope. The scheduler therefore does not silently reuse the manual
scope.

## Lifecycle Findings

1. Scheduler runs require the independent `scheduler` profile. The runtime
   factory resolves it through `MediaCrawlerProfileManager.profile_path("scheduler")`.
2. When a scheduler batch is created, `BrowserProfileIsolationManager` copies
   the provisioned scheduler template to a batch-scoped runtime profile. The
   template is not mutated by the run.
3. `MediaCrawlerProfileAdapter` receives the trigger-specific application
   profile and materializes the upstream XHS native view under an isolated
   `upstream_profiles/<platform>/<source>/<trigger>` path. It does not own the
   subprocess working directory.
4. `MediaCrawlerRuntimeFactory` keeps the upstream checkout as subprocess cwd,
   the application profile as browser/session state, and the runtime root as
   artifact output. These roots are independent.
5. The adapter supports the `scheduler` trigger generically; no XHS-specific
   runtime branch is required.

## Current Filesystem Evidence

The scheduler profile was provisioned from the empty non-secret template and
then completed by the operator through the isolated QR login flow:

```text
path: runtime/mediacrawler/xhs_mediacrawler/profiles/xiaohongshu/xhs_mediacrawler/scheduler
exists: true
files: 312
marker: PROFILE_PROVISIONING.json
marker_credentials_persisted: false
operator_login_completed: true
```

The existing manual profile remains trigger-isolated and contains no files.
The provisioning marker contains no cookie, token, password, QR code, or
browser state. Browser session state is present only in the local scheduler
profile and was not read, printed, committed, or placed in the database.

## Audit Result

```text
AUDIT_READY
```

The profile architecture supports independent scheduler provisioning. A
operator login is complete. Scheduling remains disabled pending gray-enable
approval.
