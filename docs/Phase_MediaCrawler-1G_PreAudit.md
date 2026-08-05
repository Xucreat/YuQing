# Phase MediaCrawler-1G PreAudit

## Scope

Read-only review of project configuration, MediaCrawler source, profile metadata, and PostgreSQL identity. No database write, migration, scheduler, opinion, or collector-run operation was performed.

## Environment

```text
MEDIA_CRAWLER_ROOT=D:/code files/mediaCrawler/MediaCrawler
MEDIA_CRAWLER_ENTRY=D:/code files/mediaCrawler/MediaCrawler/main.py
MEDIA_CRAWLER_PYTHON=D:/code files/mediaCrawler/MediaCrawler/.venv/Scripts/python.exe
MEDIA_CRAWLER_BROWSER_DATA=D:/code files/mediaCrawler/MediaCrawler/browser_data
MEDIA_CRAWLER_ENABLE_REAL_RUN=false
```

MediaCrawler:

```text
branch: main
commit: 1779dde9725f6b7ef42e29022c0054b3e678f1af
python: 3.11.15
```

Path checks for root, entry, Python, and browser data passed.

## Weibo Profile Metadata

Target: `D:\code files\mediaCrawler\MediaCrawler\browser_data\wb_user_data_dir`

Before sampling:

```text
exists: true
file_count: 388
size_bytes: 33085644
directory_last_write_time: 2026-08-04 16:11:34 +08:00
latest_file_last_write_time: 2026-08-04 16:11:34 +08:00
status: PASS
```

After sampling, a second metadata-only check reported 395 files and 33777467 bytes; directory and latest-file timestamp were `2026-08-04 21:31:34 +08:00`.

No internal filenames, cookie contents, localStorage, sessions, tokens, or account data were read or printed.

## Native Command Protocol

The MediaCrawler source confirms:

```text
--platform wb
--type search
--lt qrcode|phone|cookie
--keywords <comma-separated keywords>
--crawler_max_notes_count <count>
--save_data_option jsonl
--save_data_path <isolated directory>
```

Native output is written below:

```text
<save_data_path>/weibo/jsonl/*.jsonl
```

## Database Read-Only Identity

```text
current_database: opinion_db
alembic_version: p12_datasource_schedule
data_sources.key='weibo_mediacrawler': empty
```

## PreAudit Conclusion

```text
Environment paths: PASS
Profile directory: PASS
Runtime login usability: BLOCKED during real run
Database: NO CHANGE
Migration: NO CHANGE
Scheduler: Disabled
```
