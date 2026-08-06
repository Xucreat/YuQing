# MediaCrawler Enable Approval Checklist

## Infrastructure

- [PASS] runtime entry: `mediacrawler_standard_entry.py`
- [PASS] Python executable: MediaCrawler `.venv` Python exists
- [PASS] scheduler profile: isolated profile directory exists
- [PASS] login state: `WeiboClient.pong` returned `LOGIN_PASS`

## Safety

- [PASS] lock: cross-process source lock with bounded conflict failure
- [PASS] failure semantics: failed process, timeout, empty output, and lock conflict fail closed
- [PASS] metrics: batch metrics path and `failed=1` updates are covered
- [PASS] scheduler source eligibility: `schedule_enabled=false`, source absent from scheduled/due queries

## Approval

- [ ] real-run gate approval (`MEDIA_CRAWLER_REAL_RUN_GATE` remains `false`)
- [ ] schedule enable approval (`DataSource.schedule_enabled` remains `false`)

## Boundary

This checklist records readiness only. No Dry Run, scheduled crawl, DataSource
update, migration, Opinion creation, or CollectorRun creation was performed.
