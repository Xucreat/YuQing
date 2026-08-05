# Phase MediaCrawler-Enable-0 PreAudit

## Scope

本阶段为只读启用前审计。审计期间未修改业务代码、数据库数据、DataSource 配置、Scheduler 状态、运行门禁或 MediaCrawler profile；未执行 Alembic migration、启动 Scheduler、真实微博采集，也未创建 Opinion 或 CollectorRun。

## Current State

### DataSource

| Field | Value |
|---|---|
| id | `40` |
| key | `weibo_mediacrawler` |
| enabled | `true` |
| schedule_enabled | `false` |
| schedule_interval_minutes | `60` |
| class_path | `app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector` |
| scope_region_codes | `null` |
| config_json | `collector=mediacrawler`, `platform=weibo`, `keywords=["大厂县"]`, `max_items=10`, `collection_scope=national` |

The contract is valid: `max_items` is within 1-20 and `collection_scope` is `regional` or `national`. No `collection_mode=manual`, runtime path, executable path, cookie, token, or profile value is stored in `config_json`. The national sentinel remains `regions.id=24`, `code=000000`, `name=全国`.

### Deployment Runtime (read only)

```text
MEDIA_CRAWLER_ROOT: D:/code files/mediaCrawler/MediaCrawler
MEDIA_CRAWLER_PYTHON: D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe
MEDIA_CRAWLER_ENTRY: D:/code files/mediaCrawler/MediaCrawler/main.py
MEDIA_CRAWLER_TIMEOUT_SECONDS: 900
MEDIA_CRAWLER_REAL_RUN_GATE: false
MEDIA_CRAWLER_LOGIN_TYPE: qrcode
MEDIA_CRAWLER_SCHEDULER_LOGIN_TYPE: cookie
MEDIA_CRAWLER_PROFILE_ROOT: ""
```

The configured entry and Python executable are present. The runtime factory resolves a non-interactive `cookie` login policy for scheduled runs. With the gate set to `false`, scheduled real execution is intentionally blocked before process execution.

## Findings

### 1. DataSource Contract

**PASS**. The source is a valid future scheduler candidate, but it is currently not eligible because `schedule_enabled=false`.

### 2. Scheduler Chain and Eligibility

**PASS for current safety; BLOCKED for enablement.** The scheduler uses the `enabled=true AND schedule_enabled=true` eligibility query and the source was absent from the current scheduled-source result (`due_scheduled_sources=[]`). A future enable would follow DataSource -> scheduler -> `CollectorService(trigger_type=scheduled)` -> registry -> `MediaCrawlerWeiboCollector` -> runtime factory. No current manual-only parameter injection was found in this path. The chain is not permitted to execute real work while the gate is false.

### 3. Runtime Factory

**BLOCKED.** Deployment runtime values are available and are not read from DataSource config, but `MEDIA_CRAWLER_REAL_RUN_GATE=false`. The implementation is fail-closed: a scheduled trigger raises `MediaCrawlerRuntimeError` before command/process execution. This is the intended state until explicit enable approval, but it prevents production scheduler enablement now.

### 4. Profile Readiness

**BLOCKED.** The profile manager expects:

```text
D:\code files\mediaCrawler\MediaCrawler\profiles\manual
D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
```

Both paths are absent (`exists=false`, `is_directory=false`). Existing `browser_data/wb_user_data_dir` and `browser_data/wb_user_data_dir_manual` were observed but were not copied, moved, opened, or modified. The profile manager correctly returns an explicit missing-profile result and does not create or migrate account state. A scheduler profile must be provisioned through a separately approved, controlled process before enablement; this audit did not perform that action.

### 5. Lock Safety

**PASS.** `MediaCrawlerRunLock` uses an OS-level cross-process lock at `locks/weibo_mediacrawler.lock`, shared by manual and scheduler triggers. Acquisition is bounded, conflicts raise `MediaCrawlerLockTimeoutError`, and the context manager releases the lock in `finally`; process termination does not leave a permanent lock.

### 6. Batch Metrics Observability

**BLOCKED / legacy gap.** `MediaCrawlerBatchLocator` defines the expected mapping:

```text
runtime/mediacrawler/runs/<batch_id>/
  metrics.json
  raw/weibo.jsonl
  output/weibo.jsonl
```

For legacy batch `e62641b78a9449d0b9874c380a4aa8b5`, the configured runtime root contains no discoverable run directory, `metrics.json`, raw JSONL, or output JSONL. This is recorded as `legacy batch missing metrics`; no backfill or write was performed.

### 7. Failure Semantics

**PASS in code path, but enablement remains blocked by prerequisites.** Missing profile, gate=false, timeout, non-zero process exit, `raw_count > 0 && output_count == 0`, and lock conflict are routed to failed-run semantics; the metrics path records `failed=1` for a failed run. No silent success path was identified for these error conditions.

### 8. Historical Production Evidence

Read-only `collector_runs` inspection found four MediaCrawler runs:

| Metric | Result |
|---|---:|
| total runs | 4 |
| success | 1 |
| failed | 3 |
| average duration | 13.265 s |
| latest successful batch | `e62641b78a9449d0b9874c380a4aa8b5` |
| latest failure | `dbd72ce12e774b89ad7eaf57ed6f1d8f` |

The three failures were all `MediaCrawlerRunnerConfigurationError: no MediaCrawler command configured`. No historical profile failure, login failure, or overlap was observed. The historical failure rate is 75%, so it is not sufficient evidence for periodic automatic execution.

## Test Result

Command executed from `backend`:

```text
pytest tests/test_media_crawler*.py -q
```

Result:

```text
97 passed, 1 warning in 6.18s
```

The warning is the existing Pydantic class-based-config deprecation warning. No scheduler integration test that writes or claims production state was executed.

## Enable Decision

| 项目 | 状态 |
|---|---|
| DataSource contract | PASS |
| Scheduler chain | PASS (currently disabled) |
| Runtime Factory | BLOCK |
| Real-run gate | BLOCK (`false`, intentionally blocked until enable approval) |
| Scheduler profile | BLOCK (missing) |
| Lock | PASS |
| Metrics path | BLOCK (legacy batch gap) |
| Failure semantics | PASS |

**BLOCKED**

Enablement is not approved. The blocking conditions are the absent scheduler profile, the intentionally closed real-run gate, the missing discoverable metrics for the legacy production batch, and the observed historical runtime configuration failure rate. Resolving these requires an explicit enable-preparation/change process; no such changes were made in this read-only audit.

Database:
NO CHANGE

Migration:
NO CHANGE

DataSource:
NO CHANGE

Scheduler:
Disabled

Real Crawl:
NOT CALLED
