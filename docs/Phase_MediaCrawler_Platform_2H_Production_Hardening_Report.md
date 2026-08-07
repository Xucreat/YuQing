# Phase MediaCrawler Platform-2-H Production Hardening Report

## Status

`READY_FOR_SCHEDULER_GRAY`

XHS manual production verification succeeded after the authorized backend
reload. Scheduler gray enablement remains disabled.

## 1. Service Reload

Before reload, PID `13156` started at `2026-08-06 16:43:07` and served stale
Admin config validation. After human authorization, backend was reloaded from
the current workspace at approximately `2026-08-06 17:54:28`, PID `28004`.

The reload inherited temporary process-only:

```text
COLLECTOR_SCHEDULE_ENABLED=false
ALERT_EVAL_ENABLED=false
```

`.env` was not changed. Scheduler was not started by the reloaded process.

## 2. Health and Admin API

```text
GET /health
HTTP 200
collector_discovery=db_driven
```

The application exposes `/health`, not `/api/health`; `/api/health` returned
the expected route-level `404` and no code was changed for this unrelated path
prefix difference.

After reload:

```text
POST /api/admin/data-sources
HTTP 200
```

The temporary `xhs_contract_reload_test` source was accepted with
`get_comment=false` and `get_sub_comment=false`, and the response explicitly
confirmed that no real subprocess was started. It was immediately deleted.

```text
PATCH /api/admin/data-sources/45
HTTP 200
```

The formal XHS config was restored after the contract probe. No test source
remains.

## 3. Formal DataSource

```text
id=45
key=xhs_mediacrawler
type=social
class_path=app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector
enabled=true
schedule_enabled=false
schedule_interval_minutes=60
```

Current `config_json` contains:

```json
{
  "collector": "mediacrawler",
  "platform": "xiaohongshu",
  "crawler_type": "search",
  "login_type": "qrcode",
  "keywords": ["大厂回族自治县"],
  "max_items": 20,
  "get_comment": false,
  "get_sub_comment": false,
  "collection_scope": "regional",
  "collection_mode": "regional"
}
```

No cookie, token, password, shell command, executable path or profile path is
stored in `config_json`.

## 4. XHS Manual Run

The first retry was blocked by a stale runtime-root/profile-root pairing. A
second retry using the existing Chrome wrapper and explicit one-shot runtime
overrides completed successfully.

```text
keyword: 大厂回族自治县
trigger_type: manual
CollectorRun.id: 15122
collector_name: MediaCrawler[xiaohongshu]
status: success
fetched_raw: 20
created: 20
duplicate: 0
analyzed: 20
failed: 0
```

Runtime time:

```text
2026-08-06 18:40:35 - 18:43:34 Asia/Shanghai
```

The XHS login flow completed through the existing QR login path. The native
artifact was discovered at:

```text
runtime/mediacrawler/xhs_mediacrawler/runs/
11e86755b06a4b61afcfe3c0fd1f854d/xiaohongshu/xhs_mediacrawler/
output/xhs/jsonl/search_contents_2026-08-06.jsonl
```

Metrics reported `raw_count=20`, `output_count=20`, `created=20`,
`duplicate=0`, and `failed=0`. The retained log records the exact keyword and
contains redacted XHS session fields only.

## 5. Opinion Verification

Before this run, XHS Opinion count was 20. After the run:

```text
source=xiaohongshu
source_type=xhs_note
total=40
complete external_id/content/publish_time records=40
new records from this run=20
```

No Weibo schema or compatibility behavior was changed.

## 6. Scheduler Safety

Read-only query after the run:

```text
xhs_mediacrawler enabled=true
xhs_mediacrawler schedule_enabled=false
xhs_mediacrawler scheduler candidates=0
```

The existing Scheduler candidate contract remains:

```text
enabled=true AND schedule_enabled=true
```

The proposed two-hour gray plan is documented separately in
`docs/Phase_MediaCrawler_Platform_2H_Scheduler_Enablement_Plan.md` and requires
manual approval.

## 7. Tests and Verification

Required verification:

```text
pytest backend/tests/test_media_crawler*.py -q
python -m compileall backend/app
git diff --check
```

Actual results:

```text
185 passed, 1 warning
compileall PASS
git diff --check PASS
```

## 8. Modified Files

This phase added only:

- `backend/scripts/verify_xhs_production_manual_run.py`
- `backend/tests/test_media_crawler_xhs_production_contract.py`
- `docs/Phase_MediaCrawler_Platform_2H1_Service_Reload_Report.md`
- `docs/Phase_MediaCrawler_Platform_2H_Scheduler_Enablement_Plan.md`
- `docs/Phase_MediaCrawler_Platform_2H_Production_Hardening_Report.md`

The existing preflight and reload-required reports were preserved.

## 9. Prohibited Changes Confirmation

- no model changes;
- no migration or `ALTER TABLE`;
- no `backend/app/core/scheduler.py` changes;
- no `.env` changes;
- no upstream MediaCrawler changes;
- no new Collector;
- no Weibo compatibility changes;
- no Scheduler startup or automatic XHS collection;
- no test DataSource remains.

## Final State

```text
READY_FOR_SCHEDULER_GRAY
```
