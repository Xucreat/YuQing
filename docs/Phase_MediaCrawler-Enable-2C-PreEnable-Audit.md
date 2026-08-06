# Phase MediaCrawler-Enable-2C PreEnable Audit

Date: 2026-08-05  
Checkout: `C:\Users\Administrator\Desktop\YQ`  
Git commit: `b1b18a0267421c90ccf279aa1fc2ea3936766c35`

## 1. Scheduler Configuration Audit

Read-only settings:

```text
collector_schedule_enabled=true
collector_schedule_mode=per_source
collector_tick_interval_seconds=60
alert_eval_enabled=true
MEDIA_CRAWLER_REAL_RUN_GATE=false
MEDIA_CRAWLER_ENABLE_REAL_RUN=false
```

Owner fingerprint:

| Field | Value |
|---|---|
| audit process python | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| project_root | `C:\Users\Administrator\Desktop\YQ` |
| git_commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime_factory_available | `true` |
| PostgreSQL advisory lock owner | backend PID `24500` |

The lock backend started at `2026-08-05 15:46:02 +08:00`, matching the current
YQ Uvicorn process started at `2026-08-05 15:45:55 +08:00`. Process inspection
found no BettaFish, second checkout, unknown `app.py`, or other scheduler.
Therefore the effective unique owner is the target YQ checkout.

The isolation script prints `possible_other_scheduler=true` conservatively
whenever any advisory lock exists. Owner-to-process mapping makes the effective
value `false`; this is a diagnostic-script limitation, not a second owner.

No scheduler was started or stopped by this audit.

## 2. MediaCrawler Source Readiness

```text
id=40
key=weibo_mediacrawler
name=微博（MediaCrawler）
enabled=true
schedule_enabled=false
next_collect_time=2026-08-05 16:42:19.298471
schedule_interval_minutes=60
class_path=app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
scheduled sources: absent
due sources: absent
```

Current `config_json` is source-local and unchanged:

```json
{
  "collector": "mediacrawler",
  "platform": "weibo",
  "keywords": ["大厂县"],
  "max_items": 10,
  "collection_scope": "national"
}
```

Enabling this source would affect only the `weibo_mediacrawler` key because
Scheduler discovery filters the selected source keys before Registry assembly.

## 3. Runtime Isolation Readiness

Verified statically:

- `MediaCrawlerRuntimeFactory.create_runner(..., batch_id=...)` exists.
- Scheduler execution creates `runtime_profiles/<batch_id>/`.
- `BrowserProfileIsolationManager` validates batch IDs, refuses overwrite,
  copies with metadata preservation, and refuses cleanup outside
  `runtime_profiles`.
- `profiles/scheduler` is the persistent template.
- With a production scheduled batch ID, Runner `browser_data` and
  `profile_name` point to the disposable runtime profile, not the template.
- Missing scheduler batch IDs fail closed in `MediaCrawlerWeiboCollector`.
- Successful crawl/JSONL normalization cleans the runtime profile; failures
  retain it for audit.

The previous final isolated dry run already proved this behavior with batch
`c4998f2792ea4a05b709c6a8936f41c2`; the template profile hash and mtime were
unchanged.

## 4. Scheduler Execution Safety

### CollectorService lifecycle

Production lifecycle:

```text
CollectorService(...)
  -> __init__: self.collectors=[]
  -> collect_and_analyze(real DB)
  -> resolve_collectors_verbose(db, ...)
  -> self.collectors=resolved.collectors
  -> execute
```

Concurrent scheduled lifecycle uses the same real-DB resolve:

```text
collect_and_analyze_concurrent(SessionLocal, trigger_type="scheduled")
  -> resolve_collectors_verbose(resolve_db, ...)
  -> execute collectors with per-worker DB sessions
```

The only eager constructor path is the explicit `collector_type="mock"` fixture
path or caller-injected collectors. Production collectors are not created from
`db=None`.

### Registry path

```text
DataSource discovery
  -> Registry._build_collector
  -> MediaCrawlerWeiboCollector(runtime_factory=MediaCrawlerRuntimeFactory)
```

`resolve_collectors` and `resolve_collectors_verbose` share `_resolve_core`; the
verbose variant adds failure details but does not use a different injection
path.

### Cache and bare Runner review

- Registry `_CLASS_CACHE` caches imported classes only, not collector instances.
- No module-level production collector singleton was found.
- No scheduler closure stores a production collector across ticks.
- `MediaCrawlerRunner` is constructed in RuntimeFactory for production runtime,
  in the fixture branch for offline tests, and in explicit operator/test scripts.
- No scheduler production path constructs a bare Runner without a
  `command_factory`, fixture, or RuntimeFactory boundary.

## 5. Tests

Command:

```text
pytest tests/test_media_crawler*.py -q
```

Result:

```text
118 passed, 1 warning
```

No real MediaCrawler, browser, Scheduler start, database write, migration, or
gate change occurred during this audit.

## 6. Final Decision

`READY_FOR_SCHEDULER_ENABLE`

The target checkout owns the scheduler lock, the source is correctly isolated
and disabled, the scheduled path resolves through the real DB and Registry,
RuntimeFactory/profile isolation is ready, no hidden production collector cache
or bare Runner path was found, and the complete MediaCrawler test suite is
green.

This report authorizes the next enablement step only; it does not enable the
Scheduler or change any runtime configuration.
