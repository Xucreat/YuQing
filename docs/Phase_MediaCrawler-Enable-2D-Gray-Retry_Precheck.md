# Phase MediaCrawler-Enable-2D-Gray-Retry Precheck

Date: 2026-08-05  
Precheck result: `PASS`

## Scheduler owner

Current Uvicorn process tree:

| PID | Role | executable | command | started |
|---:|---|---|---|---|
| 48248 | parent | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` | `-m uvicorn app.main:app --host 0.0.0.0 --port 8000` | 2026-08-05 17:25:45 +08:00 |
| 24968 | worker | Workbuddy worker for the same YQ command | same application command line | 2026-08-05 17:25:45 +08:00 |

Advisory lock:

```text
key=4726074873081972718
owner_pid=46696
```

The PostgreSQL lock backend belongs to the current YQ Uvicorn instance. No
BettaFish scheduler, second checkout, or unrelated `app.py` scheduler was
found.

The read-only isolation script's raw
`possible_other_scheduler=true` is a conservative “lock exists” warning; it
does not identify an external owner.

## Current code fingerprint

| Field | Value |
|---|---|
| project root | `C:\Users\Administrator\Desktop\YQ` |
| git commit | `b1b18a0267421c90ccf279aa1fc2ea3936766c35` |
| Python | `C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe` |
| registry | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\registry.py` |
| collector | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\media_crawler_weibo_collector.py` |
| runtime | `C:\Users\Administrator\Desktop\YQ\backend\app\collectors\mediacrawler_runtime.py` |
| runtime_factory_available | `true` |
| `create_runner(batch_id=...)` | supported |

## DataSource state

Read at `2026-08-05 17:58:54 +08:00`:

| Field | Value |
|---|---|
| id | `40` |
| key | `weibo_mediacrawler` |
| enabled | `true` |
| schedule_enabled | `false` |
| schedule interval | `60` minutes |
| next_collect_time | `2026-08-05 18:15:02.943790 +08:00` |
| config_json | unchanged |
| other enabled scheduled sources | `22` |

No DataSource row was modified during precheck.

## Persistent profile snapshot

Actual configured scheduler template:

```text
C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\profiles\scheduler
```

| Field | Value |
|---|---:|
| file_count | `554` |
| directory_count | `260` |
| root mtime UTC | `2026-08-05 06:03:14` |
| aggregate SHA-256 | `921769beb026779a28db7d0fe7df1c876f8a91d5a684bff5fd010469da8454b5` |

This snapshot is the post-run comparison baseline. The template is not to be
written by the gray retry.

## Gate before reload

The existing long-lived Scheduler was started before the gray-control reload
and must not be trusted to contain the new process environment. It will be
replaced by the same single YQ owner with temporary process variables:

```text
SCHEDULER_SOURCE_ALLOWLIST=weibo_mediacrawler
MEDIA_CRAWLER_REAL_RUN_GATE=true
```

No `.env` or persistent configuration change is authorized.

## Precheck decision

`PASS` — proceed to stop/reload the existing single owner, verify the
allowlist/gate fingerprint, and only then enable DataSource id=40.

## Profile path correction

The first shell-level snapshot above was taken against the YQ-local fallback
directory. The running deployment resolves `MEDIA_CRAWLER_ROOT` from the
existing environment to:

```text
D:\code files\mediaCrawler\MediaCrawler
```

Therefore the authoritative production template is:

```text
D:\code files\mediaCrawler\MediaCrawler\profiles\scheduler
```

The prior Final Isolated Dry Run snapshot for this exact template recorded
`file_count=549`, `directory_count=163`, and
`root_mtime_ns=1785919142691390300`. A post-run exact file-by-file comparison
found zero added, removed, or changed files and the same root mtime. The final
report uses this resolved production path and comparison evidence.
