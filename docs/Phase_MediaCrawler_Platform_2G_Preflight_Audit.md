# Phase MediaCrawler Platform-2-G Preflight Audit

## Status

`PREFLIGHT_READY`

本报告为 XHS 正式数据源灰度启用前的只读检查。检查期间未修改代码、
数据库、`.env`、生产 DataSource，也未启动新的 Scheduler 或 MediaCrawler。

## Worktree

开始检查时工作区已经存在大量历史 tracked/untracked dirty changes。
这些变化被保留，未执行 `git reset`、`git checkout`、`git clean`、
`git restore` 或批量回滚。

## Formal DataSource Payload

Registration builder：

`backend/app/collectors/media_crawler_registration.py`

目标 source：

```json
{
  "key": "xhs_mediacrawler",
  "name": "小红书（MediaCrawler）",
  "type": "social",
  "class_path": "app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector",
  "enabled": false,
  "schedule_enabled": false,
  "schedule_interval_minutes": 60,
  "scope_region_codes": "131028",
  "config_json": {
    "collector": "mediacrawler",
    "platform": "xiaohongshu",
    "crawler_type": "search",
    "login_type": "qrcode",
    "keywords": ["大厂", "廊坊大厂"],
    "max_items": 20,
    "get_comment": false,
    "get_sub_comment": false,
    "collection_scope": "regional",
    "collection_mode": "regional"
  }
}
```

配置校验通过。运行时路径、Cookie、token、password、shell command 和
profile path 不在 `config_json` 中。

## Admin API

`backend/app/api/admin_data_sources.py` 的 `POST /api/admin/data-sources`
支持 `type=social` 的 platform-neutral MediaCrawler class path，并会：

- 校验 `config_json` 和区域 contract；
- 通过 `MediaCrawlerPlatformCollector` 构建 contract；
- 不启动 MediaCrawler subprocess；
- 对 MediaCrawler source 默认 `schedule_enabled=false`；
- 仅允许 admin 写入。

因此可以安全用于创建本次默认关闭的正式 DataSource。

## Registry

当前解析链路：

```text
xhs_mediacrawler
 -> MediaCrawlerPlatformCollector
 -> mediacrawler capability
 -> platform=xiaohongshu
 -> XHS_PLATFORM_SPEC
 -> XhsNormalizer
```

Registry contract check 通过。现有微博：

```text
weibo_mediacrawler
 -> MediaCrawlerWeiboCollector
```

未改动，数据库中 `DataSource.id=40` 仍为微博源。

## Scheduler Safety

`backend/app/collectors/data_source_repository.py` 的发现条件为：

```text
enabled = true
AND schedule_enabled = true
```

目标 XHS payload 同时设置：

```text
enabled = false
schedule_enabled = false
```

因此不会被自动调度发现。本阶段只允许后续人工触发，不开启 XHS
Scheduler 灰度。

## Runtime Environment

已确认：

- MediaCrawler checkout：
  `D:\code files\mediaCrawler\MediaCrawler`
- upstream commit：
  `1779dde9725f6b7ef42e29022c0054b3e678f1af`
- `libs/douyin.js`：存在
- upstream Python：`D:\code files\mediaCrawler\MediaCrawler\.venv\Scripts\python.exe`
- upstream Playwright Chromium：可解析且 executable 存在
- subprocess cwd contract：checkout root
- profile contract：platform/source/trigger 隔离
- artifact contract：`xhs/jsonl`
- `MEDIA_CRAWLER_ENABLE_REAL_RUN`：当前应用配置为 `false`
- `MEDIA_CRAWLER_REAL_RUN_GATE`：当前应用配置为 `true`

本轮人工真实运行前，需要由明确的临时运行入口显式打开 real-run
enable；不修改 `.env`，不改变 Scheduler 配置。

## Current Database Observation

只读查询结果：

- 当前数据库：`opinion_db`
- `xhs_mediacrawler`：不存在
- `weibo_mediacrawler`：存在，`id=40`、`enabled=true`、
  `schedule_enabled=true`

## Preflight Decision

`PREFLIGHT_READY`

允许执行下一步：创建唯一的 `xhs_mediacrawler` DataSource，且必须保持
`enabled=false`、`schedule_enabled=false`。创建完成后再单独进行一次人工
触发和结果验证。
