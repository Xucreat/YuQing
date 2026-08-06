# Phase MediaCrawler-Enable-2E-Observation Report

Date: 2026-08-05  
Checkout: `C:\Users\Administrator\Desktop\YQ`  
Observation window: `2026-08-05 18:37:48` to `2026-08-05 19:22:35 +08:00`  
Final status: `READY_FOR_PRODUCTION_ENABLE`

This report covers the controlled observation enablement only. Formal
production enablement was not performed. At the end of the observation,
`DataSource.id=40.schedule_enabled` was restored to `false` and the
process-scoped real-run gate was restored to `false`.

## 1. Scheduler Stability

The Scheduler was reloaded through the same YQ checkout because the existing
owner had the expected default gate `false`. The reload stopped the old owner
before starting the new one; no second Scheduler was started.

Final owner:

| Field | Value |
|---|---|
| YQ Uvicorn PID | `45452` |
| same Uvicorn child PID | `43388` |
| Python executable | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| project root | `C:\Users\Administrator\Desktop\YQ` |
| git commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| advisory lock backend PID | `23664` |
| advisory lock backend start | `2026-08-05 19:25:29.407959+08:00` |
| registry module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime module | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\mediacrawler_runtime.py` |
| runtime_factory_available | `true` |
| final real-run gate | `false` |

No second Uvicorn Scheduler, BettaFish `app.py`, or other checkout Scheduler
was found. The Scheduler remained alive and held the single advisory lock
through the observation and final restore.

Observation sampling covered:

- 39 one-minute samples from enablement through the first target run;
- 6 one-minute post-run samples;
- 45 Scheduler tick observations in total;
- no manual `CollectorService` call, direct subprocess, or manual
  MediaCrawler runner was used.

## 2. CollectorRun Statistics

The only target CollectorRun created in this observation window was:

| id | batch_id | trigger_type | status | start | end | duration | fetched_raw | created | duplicate | admission_filtered | failed |
|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 14115 | `f05aaf2df7d442689152747bbaee23d0` | `scheduled` | `success` | 19:15:39.498553 | 19:16:07.645567 | 28.147s | 10 | 0 | 6 | 4 | 0 |

Target scheduled success rate: `1/1 = 100%`  
Target scheduled failure rate: `0/1 = 0%`

The Runner metrics for the same batch were:

```json
{
  "batch_id": "f05aaf2df7d442689152747bbaee23d0",
  "raw_count": 16,
  "output_count": 10,
  "created": 0,
  "duplicate": 6,
  "admission_filtered": 4,
  "failed": 0
}
```

The target schedule claim advanced normally:

```text
last_collect_time = 2026-08-05 19:15:39.480570
next_collect_time = 2026-08-05 20:15:39.480570
```

## 3. MediaCrawler Execution

The scheduled path reached the real MediaCrawler command:

```text
Scheduler
  -> DataSourceRepository
  -> claim
  -> CollectorService(trigger_type=scheduled)
  -> Registry
  -> MediaCrawlerWeiboCollector
  -> RuntimeFactory
  -> batch runtime profile
  -> MediaCrawler
```

The MediaCrawler process exited with code `0`. The crawler log records
successful browser launch, Weibo client creation, search, note detail
fetching, and normalized JSONL output.

The observation run used the DataSource configuration without changing it:

```json
{
  "collector": "mediacrawler",
  "platform": "weibo",
  "keywords": ["大厂县"],
  "max_items": 10,
  "collection_scope": "national"
}
```

## 4. Data Quality

### Raw record contract

The batch contained 16 raw records. All 16 had:

- non-empty `content`;
- non-empty `nickname`;
- non-empty `create_time`;
- non-empty `note_url`.

The approved collector mapping is:

```text
content       -> Opinion.content
nickname      -> Opinion.author
create_time   -> Opinion.publish_time
note_id       -> Opinion.external_id
note_url      -> Opinion.url
source        -> "weibo"
source_type   -> "weibo_post"
```

### Opinion table

The observation run created no new Opinion rows because all 10 bounded
records were either already present or rejected by admission:

```text
duplicate=6
admission_filtered=4
created=0
failed=0
```

This is not treated as a collection failure. It is consistent with the
existing URL/external-id deduplication and the configured admission window.

Across the existing 108 Weibo Opinion rows:

| Check | Result |
|---|---:|
| source non-empty | 108/108 |
| content non-empty | 108/108 |
| author non-empty | 108/108 |
| url non-empty | 108/108 |
| publish_time non-null | 78/108 |
| non-null publish_time in reasonable range | 78/78 |

The 30 historical rows with a null `publish_time` predate this observation
and were not modified. The current raw batch had a usable `create_time` on
all 16 records.

### Regional quality

The raw batch used the proper regional keyword `大厂县`. Regional references
in raw content were:

| Term | Matching records |
|---|---:|
| `大厂县` | 13 |
| `廊坊` | 10 |
| `燕郊` | 1 |
| `固安` | 0 |
| `永清` | 1 |
| `香河` | 3 |

Fourteen of 16 raw records contained at least one of the checked regional
terms. The exact phrase `互联网大厂` appeared in zero records. The sample
therefore did not show the prohibited semantic substitution of “大厂县”
with “internet big company”.

## 5. Profile Isolation

Authoritative persistent template:

```text
D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
```

The batch runtime profile was created while CollectorRun `14115` was
running:

```text
D:\code files\mediaCrawler\MediaCrawler\runtime_profiles\f05aaf2df7d442689152747bbaee23d0
```

After successful completion, that directory was absent.

Persistent scheduler profile comparison:

| Metric | Before | During/post-run | Result |
|---|---:|---:|---|
| file_count | 549 | 549 | unchanged |
| directory_count | 163 | 163 | unchanged |
| root mtime ns | 1785919142691390300 | 1785919142691390300 | unchanged |
| aggregate SHA-256 | `f8f24930a08a0fc2aa6e6dfdbdd7d8ee338fc9a91ad86eff2c18668add4ddd6c` | same | unchanged |

No profile pollution was detected.

## 6. Other DataSource Impact

There were 22 other enabled scheduled sources before and after observation.
They were not modified by the enable/restore operation.

During the observation window, other sources produced their own normal
scheduled CollectorRuns. The runs were separate from target batch
`f05aaf2df7d442689152747bbaee23d0`; all observed other-source runs completed
successfully. Their `next_collect_time` and `last_collect_time` advanced only
as a result of their own normal scheduler claims.

The other-source state fingerprint changed as normal scheduled work
progressed, but the count remained 22 and no other-source failure or
cross-source CollectorRun attribution was observed.

## 7. Problems and Exceptions

### Controlled environment reload

The original long-lived owner had `MEDIA_CRAWLER_REAL_RUN_GATE=false`, which
is the deployment default. A first wrapper attempt did not inject the
process environment correctly and was stopped before DataSource enablement.
No CollectorRun, Opinion, profile, or DataSource change resulted from that
attempt.

The owner was then reloaded successfully with process-scoped gate `true` for
the observation and finally reloaded with gate `false`. `.env` was never
modified.

### `created=0`

The target run created zero new Opinions. This was explained by
`duplicate=6` and `admission_filtered=4`; the run had `failed=0`, valid raw
content, and successful MediaCrawler execution. No corrective change was
made.

No unresolved production-blocking problem was found in this observation.

## 8. Final State and Recommendation

Final database state:

```text
DataSource.id=40
enabled=true
schedule_enabled=false
config_json unchanged
```

Final runtime state:

```text
single YQ Scheduler owner
advisory lock held by the final owner
MEDIA_CRAWLER_REAL_RUN_GATE=false
SCHEDULER_SOURCE_ALLOWLIST unset
```

Acceptance checklist:

| Condition | Result |
|---|---|
| Scheduler unique owner | PASS |
| RuntimeFactory continuously available | PASS |
| Scheduled MediaCrawler run successful | PASS |
| No persistent profile pollution | PASS |
| No abnormal other-source impact | PASS |
| No observation-window failure | PASS |
| Weibo data path and mapping valid | PASS |
| Regional filtering effective | PASS |

Recommendation: `READY_FOR_PRODUCTION_ENABLE`.

This is a readiness recommendation only. Formal production enablement remains
a separate explicit approval step; this phase did not leave the MediaCrawler
DataSource scheduled.
