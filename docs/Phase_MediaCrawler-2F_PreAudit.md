# Phase MediaCrawler-2F PreAudit

## Scope

This was a read-only production-readiness audit. No code, database row, DataSource setting, profile, Scheduler setting, or migration was modified. No real Weibo collection was started.

## DataSource Status

Read-only query for `weibo_mediacrawler` returned:

| Field | Value |
| --- | --- |
| id | 40 |
| enabled | `true` |
| schedule_enabled | `false` |
| schedule_interval_minutes | 60 |
| class_path | `app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector` |
| scope_region_codes | `null` |
| config_json | `collector=mediacrawler`, `platform=weibo`, `keywords=[大厂县]`, `max_items=10`, `collection_scope=national` |

The business contract is valid, but the source is **not currently a scheduler candidate** because `schedule_enabled=false`. This setting was not changed.

The national sentinel was also queried read-only: `regions.id=24`, `code=000000`, `name=全国`, `level=province`.

## Scheduler Eligibility

The scheduler path is:

`scheduled_enabled_sources -> CollectorService(trigger_type=scheduled) -> registry -> MediaCrawlerWeiboCollector -> MediaCrawlerRuntimeFactory`.

Eligibility requires `enabled=true AND schedule_enabled=true`. The current query returned other scheduled sources but did not return `weibo_mediacrawler`.

Registry validation and collector construction are available without manual constructor parameters. Runtime parameters are not read from DataSource JSON. The source remains excluded from dispatch until an explicit future enablement decision.

## Runtime Factory Readiness

The factory resolves the deployment values below without DataSource injection:

| Runtime value | Read-only result |
| --- | --- |
| Python executable | `D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe` |
| Entry | `D:/code files/mediaCrawler/MediaCrawler/main.py`, exists |
| Runtime root | `D:/code files/mediaCrawler/MediaCrawler` |
| Scheduler login policy | `cookie` (non-interactive) |
| Timeout | 900 seconds |
| Real-run gate | `false` |
| Scheduler profile | `.../profiles/scheduler`, does not exist |

The factory fails closed for missing entry, missing executable, missing profile, and scheduler interactive login. No fail-open path was found. However, the missing scheduler profile and disabled real-run gate block an enablement test.

## Profile Readiness

Expected isolated directories were checked without modification:

- `D:/code files/mediaCrawler/MediaCrawler/profiles/manual`: absent
- `D:/code files/mediaCrawler/MediaCrawler/profiles/scheduler`: absent

An existing `browser_data/wb_user_data_dir_manual` directory is present, but using or copying it into the new isolated profile locations would be an implementation/profile operation and is outside this read-only phase. Scheduler profile readiness is therefore **BLOCKED**. The scheduler login policy is non-interactive (`cookie`); QR/interactive login is rejected by the factory.

## Lock Readiness

`MediaCrawlerRunLock` uses a cross-process OS file lock at `locks/weibo_mediacrawler.lock`, shared by manual and scheduler triggers. A conflict raises `MediaCrawlerLockTimeoutError` after the bounded one-second acquisition window, and context-manager cleanup releases the lock. The lock cannot permanently block after process termination. Lock implementation tests pass.

**Lock readiness: PASS.**

## Historical Run Quality

Read-only `collector_runs` query for the MediaCrawler collector returned four manual runs:

| Batch | Status | Duration | Raw | Output/Created | Filtered | Failed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `e62641b78a9449d0b9874c380a4aa8b5` | success | 28.420s | 10 in CollectorRun (2C report: 16 native raw) | 6 | 4 | 0 |
| `0072bb46b1194dc9a04c0b5689f856bc` | failed | 7.184s | 0 | 0 | 0 | 1 |
| `e6cf180a651244bb927df43067fbb8d9` | failed | 8.851s | 0 | 0 | 0 | 1 |
| `dbd72ce12e774b89ad7eaf57ed6f1d8f` | failed | 8.608s | 0 | 0 | 0 | 1 |

Average duration was 13.265 seconds across all four records and 28.420 seconds for the successful run. The observed successful batch is well below a 60-minute interval, so interval overlap is not indicated by duration alone. However, the historical failure rate is 3/4 and the three failures were runtime command-configuration failures.

The exact 2C batch `e62641b78a9449d0b9874c380a4aa8b5` has a CollectorRun record, but no matching `metrics.json` was found in either the workspace runtime root or the configured external MediaCrawler `runs` directory. This is an auditability/path-alignment gap and must be resolved before periodic operation can be judged fully observable. No files were created or changed during this check.

## Scheduler Frequency Risk

At `schedule_interval_minutes=60`, the successful 28.420-second run would not overlap the next tick. The shared source lock and APScheduler `max_instances=1`/`coalesce=true` controls provide additional overlap protection. Data growth remains bounded by `max_items=10` per run, but a future enablement would still need monitoring for login/session expiry, profile availability, failed-run rate, and metrics/CollectorRun batch alignment.

## Test Result

Read-only MediaCrawler test suite:

```text
90 passed, 1 warning
```

The warning is the existing Pydantic class-based configuration deprecation warning. Scheduler integration tests that write or claim database state were not executed, per the phase red line.

## Enablement Decision

**BLOCKED**

Blocking points:

1. Scheduler profile directory is absent; the existing manual browser profile is in a different location and cannot be copied or modified in this phase.
2. `media_crawler_enable_real_run=false`, so an automatic real run is intentionally fail-closed.
3. The 2C CollectorRun and runtime metrics are not currently aligned to the same discoverable batch path.

No code change, database change, DataSource change, profile change, Scheduler enablement, or migration is authorized by this audit. Do not enter the Enable phase until these blockers are addressed and separately approved.

## Final Conclusion

`BLOCKED`

