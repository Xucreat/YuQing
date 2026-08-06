# Phase MediaCrawler-Enable-2E-Observation Precheck

Date: 2026-08-05  
Precheck completed: `2026-08-05T18:33:15+08:00`  
Scope: read-only observation precheck; no database, code, `.env`, profile,
Scheduler, or DataSource state was changed.

## Precheck Decision

`READY_AFTER_SAME_OWNER_RELOAD`

The current long-lived YQ owner is the only Scheduler owner, but its
process-scoped `MEDIA_CRAWLER_REAL_RUN_GATE` is `false`. The `.env` value is
also `false` by design and is not to be changed. Before enabling DataSource
`id=40`, the same YQ owner must be reloaded once with a process-scoped
`MEDIA_CRAWLER_REAL_RUN_GATE=true`; no second Scheduler may be started.

## 1. Scheduler Owner

### Current process tree

| PID | Role | Python executable | Command | Started |
|---:|---|---|---|---|
| 44448 | YQ Uvicorn owner | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` | `-m uvicorn app.main:app --host 0.0.0.0 --port 8000` | 2026-08-05 18:21:38 |
| 40152 | same Uvicorn child | `C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe` | same YQ Uvicorn command line | 2026-08-05 18:21:38 |

PostgreSQL advisory lock:

| Field | Value |
|---|---|
| lock key | `4726074873081972718` |
| current lock backend PID | `27128` |
| backend start | `2026-08-05 18:21:41.991326+08:00` |
| client address | `127.0.0.1` |
| state | `idle` |

The lock backend start is within the current YQ Uvicorn startup window and
matches the single active owner. Process inspection found no second
`uvicorn`, no BettaFish `app.py`, and no Python Scheduler process from another
checkout. The only matching application process is the YQ checkout above.

### Owner fingerprint

| Field | Value |
|---|---|
| project root | `C:\Users\Administrator\Desktop\YQ` |
| git commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| Python executable | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\mediacrawler_runtime.py` |
| runtime_factory_available | `true` |
| Scheduler mode | `per_source` |
| Scheduler tick | `60` seconds |
| source allowlist | unset |

The current deployment runtime config is valid without creating a runtime
profile:

| Field | Value |
|---|---|
| MediaCrawler root | `D:\code files\mediaCrawler\MediaCrawler` |
| MediaCrawler Python | `D:\code files\mediaCrawler\MediaCrawler\.venv\Scripts\python.exe` |
| entry | `C:\Users\Administrator\Desktop\YQ\backend\scripts\mediacrawler_standard_entry.py` |
| scheduler profile | `D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler` |
| scheduler login type | `cookie` |
| runtime factory config | valid |

## 2. DataSource State

Read from PostgreSQL at `2026-08-05 18:33:15 +08:00`:

| Field | Value |
|---|---|
| id | `40` |
| key | `weibo_mediacrawler` |
| enabled | `true` |
| schedule_enabled | `false` |
| next_collect_time | `2026-08-05 19:15:30.971713` |
| schedule_interval_minutes | `60` |
| config_json | `{"collector":"mediacrawler","platform":"weibo","keywords":["大厂县"],"max_items":10,"collection_scope":"national"}` |

Other enabled scheduled sources: `22`.

Other source keys:

`government`, `baidu_news`, `xinhua`, `people`, `chinanews`,
`hebei_daily`, `langfang_gov`, `sanhe_gov`, `xianghe_gov`, `guan_gov`,
`langfang_news`, `xianghe_news`, `bazhou_gov`, `yongqing_gov`,
`dacheng_gov`, `wenan_gov`, `langfang_bsdt_gov`, `bazhou_gov_xzdt`,
`people_news_site_hebei_langfang`, `lf_hebccw_cn_lfyw`,
`chinanews_hebei_sxjj`, `xinhua_hebei`.

No DataSource row was modified by this precheck.

## 3. Gate State

| Source | Value |
|---|---|
| `.env: MEDIA_CRAWLER_REAL_RUN_GATE` | `false` |
| current long-lived owner setting | `false` |
| `.env: MEDIA_CRAWLER_ENABLE_REAL_RUN` | `false` |
| scheduler login type | `cookie` |

The current environment is not sufficient for a real scheduled MediaCrawler
execution. The approved next action is a same-checkout, same-owner reload
with only process-scoped `MEDIA_CRAWLER_REAL_RUN_GATE=true`. `.env` remains
unchanged.

## 4. Scheduler Discovery Path

The source is registered through the current database-driven path:

```text
Scheduler
  -> DataSourceRepository
  -> due_scheduled_sources(enabled AND schedule_enabled)
  -> claim
  -> CollectorService(trigger_type=scheduled)
  -> registry
  -> MediaCrawlerWeiboCollector
  -> MediaCrawlerRuntimeFactory
  -> batch runtime profile
  -> MediaCrawler
```

The current target row is not eligible while `schedule_enabled=false`.
Registry/runtime modules are present, and `MediaCrawlerRuntimeFactory.config`
resolves the scheduler root, entry, cookie login policy, and template without
writing a runtime profile.

## 5. Scheduler Profile Baseline

Authoritative persistent template:

```text
D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
```

Snapshot algorithm for the aggregate hash: sorted relative file path,
file size, file mtime nanoseconds, and file-content SHA-256 are fed into one
SHA-256 digest. This same algorithm must be used before and after each
observation run.

| Metric | Baseline |
|---|---:|
| file_count | `549` |
| directory_count | `163` |
| root mtime ns | `1785919142691390300` |
| root mtime UTC | `2026-08-05T08:39:02.691390+00:00` |
| aggregate SHA-256 | `f8f24930a08a0fc2aa6e6dfdbdd7d8ee338fc9a91ad86eff2c18668add4ddd6c` |

No `runtime_profiles/<batch_id>` directory was created during precheck.

## 6. Safety Confirmation

| Area | Result |
|---|---|
| business code | no change |
| database schema | no change |
| migration | not run |
| `.env` | no change |
| DataSource rows | no change |
| historical CollectorRun rows | no deletion or update |
| Scheduler profile | no change |
| second Scheduler | not started |
| direct MediaCrawler run | not started |
