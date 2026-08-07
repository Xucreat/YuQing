# Phase MediaCrawler Platform-2-E2 Preflight Report

## 1. Scope

This report records the read-only preflight for the first controlled XHS
real-runtime attempt. No application code, database, Scheduler, `.env`,
production DataSource, or upstream MediaCrawler source was modified.

Checked at: `2026-08-06T16:22:21+08:00`

## 2. Worktree

The worktree was already dirty before this phase. Existing tracked and
untracked changes are preserved.

The upstream checkout was also already dirty:

- checkout: `D:\code files\mediaCrawler\MediaCrawler`
- HEAD: `1779dde9725f6b7ef42e29022c0054b3e678f1af`
- existing upstream dirty files include `media_platform/kuaishou/client.py`,
  `media_platform/kuaishou/core.py`, and `tools/browser_launcher.py`
- existing upstream untracked paths include `.workbuddy/`, `locks/`, `profiles/`,
  `runs/`, and `runtime_profiles/`

No upstream changes were made by this preflight.

## 3. Environment Checks

| Check | Result | Evidence |
|---|---|---|
| `MEDIA_CRAWLER_ROOT` | PASS | `D:\code files\mediaCrawler\MediaCrawler` exists |
| `MEDIA_CRAWLER_PYTHON` | PASS | upstream `.venv\Scripts\python.exe` executes |
| upstream MediaCrawler commit | PASS | `1779dde9725f6b7ef42e29022c0054b3e678f1af` |
| `libs/douyin.js` | PASS | exists under checkout root |
| XHS upstream imports | PASS | `main.py` imports `media_platform.xhs.XiaoHongShuCrawler` |
| XHS native browser contract | PASS | upstream code uses `browser_data/xhs_user_data_dir` |
| XHS CLI contract | PASS | `xhs`, `search/detail/creator`, `qrcode/phone/cookie`, `jsonl` |
| project environment checker | PASS | `backend/scripts/check_mediacrawler_env.py` returned `Overall: PASS` |
| Playwright module | PASS | available in project/upstream virtual environments |
| Chromium executable | PASS | Playwright reports `chrome.exe` under `ms-playwright` |
| headless smoke launch | BLOCKED | local Chromium headless shell exited with ICU error; no MediaCrawler was started |

The existing `D:\code files\mediaCrawler\MediaCrawler\browser_data` contains
multiple platform profiles, including `xhs_user_data_dir`. Those profiles are
production/upstream runtime state and are not used by this phase.

## 4. Real-Run Gate

Current application settings resolve to:

```text
media_crawler_enable_real_run = false
media_crawler_real_run_gate = true
XHS_PLATFORM_SPEC.allow_real_collection = false
```

The explicit subprocess enable gate is therefore closed. The XHS platform
spec also remains intentionally non-production:

```text
allow_real_collection = false
```

The gate must not be changed in `.env` or production configuration as part of
this preflight.

## 5. Entry/CWD Contract Difference

The configured application entry is:

```text
C:\Users\Administrator\Desktop\YQ\backend\scripts\mediacrawler_standard_entry.py
```

This is an application wrapper outside the upstream checkout. The configured
checkout root is separately:

```text
D:\code files\mediaCrawler\MediaCrawler
```

Because `media_crawler_checkout_root` is empty, the current runtime code derives
`checkout_root` from the entry parent unless an explicit runtime override is
provided. With the current settings, that would point at
`backend\scripts`, not the upstream checkout. A real attempt must not proceed
with that unresolved context.

## 6. Preflight Decision

`BLOCKED`

Classification:

- A. MediaCrawler startup: not attempted; current entry/cwd contract is unsafe.
- B. Login: not reached.
- C. Artifact: not reached.
- D. Schema: not reached.
- E. Normalizer: not reached.
- F. Collector/database: not reached.

No real MediaCrawler process, browser session, Scheduler, database write,
production profile, or production DataSource was started or modified.

