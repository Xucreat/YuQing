# Phase MediaCrawler Platform-2-G Production Enablement Report

## Status

`REAL_SOURCE_ENABLED`

XHS 正式 DataSource 已创建并保持人工灰度：`enabled=true`、
`schedule_enabled=false`。一次人工真实采集成功，未开启自动 Scheduler。

## 1. DataSource

```text
id: 45
key: xhs_mediacrawler
name: 小红书（MediaCrawler）
type: social
class_path:
  app.collectors.media_crawler_platform_collector.MediaCrawlerPlatformCollector
enabled: true
schedule_enabled: false
schedule_interval_minutes: 60
scope_region_codes: 131028
```

`config_json`：

```json
{
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
```

没有新增数据库字段或 migration。微博 `DataSource.id=40` 保持：

```text
key=weibo_mediacrawler
enabled=true
schedule_enabled=true
class_path=...MediaCrawlerWeiboCollector
```

## 2. Creation and Admin API

源码级 Admin contract 检查通过：

- `type=social` 解析为 platform-neutral collector；
- `config_json` 校验通过；
- contract build 不启动 subprocess；
- 未配置凭据、token、profile path 或 shell command。

执行时发现 8000 端口上的既有应用进程早于 Phase F 代码启动，其 live
`POST /api/admin/data-sources` 返回 422，错误为旧进程不认识
`get_comment/get_sub_comment`。为避免重启现有服务并意外启动其 Scheduler，
本次使用同一 registration payload 在事务中创建了唯一的 `id=45`；
数据库回读与当前源码 Registry 均通过。后续应用进程重启后，Admin API
应重新验证 POST/PATCH。

## 3. Real Collection

运行日期：`2026-08-06`

最终成功运行：

```text
UTC:    2026-08-06T09:11:06Z - 2026-08-06T09:12:48Z
时区:   2026-08-06 17:11:06 - 17:12:48 Asia/Shanghai
耗时:   约 101.9 秒
keyword: 大厂
max_items: 20
crawler_type: search
login_type: qrcode
```

Upstream：

```text
checkout: D:\code files\mediaCrawler\MediaCrawler
commit:   1779dde9725f6b7ef42e29022c0054b3e678f1af
cwd:      D:\code files\mediaCrawler\MediaCrawler
```

最终 argv（敏感值未写入）：

```text
D:\code files\mediaCrawler\MediaCrawler\.venv\Scripts\python.exe
C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_phase2e2_verify_keyword\mediacrawler_chrome_entry.py
--platform xhs
--lt qrcode
--type search
--keywords 大厂
--get_comment false
--get_sub_comment false
--save_data_option jsonl
--crawler_max_notes_count 20
--save_data_path
C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_mediacrawler\runs\9f2f976c6da84e1c8ce84fabccbfef70\xiaohongshu\xhs_mediacrawler\output
```

二维码登录在 `09:11:54Z` 被 upstream UI 确认成功，随后搜索完成。

## 4. Artifact

```text
native:
runtime/mediacrawler/xhs_mediacrawler/runs/9f2f976c6da84e1c8ce84fabccbfef70/
xiaohongshu/xhs_mediacrawler/output/xhs/jsonl/
search_contents_2026-08-06.jsonl

bounded output:
.../output/xiaohongshu.jsonl

raw copy:
.../raw/xiaohongshu.jsonl

metrics:
.../metrics.json
```

Metrics：

```json
{
  "platform": "xiaohongshu",
  "source_key": "xhs_mediacrawler",
  "raw_count": 20,
  "output_count": 20,
  "created": 20,
  "duplicate": 0,
  "failed": 0,
  "effective_max_items": 20
}
```

真实字段覆盖包括：

```text
note_id, type, title, desc, video_url, time, last_update_time,
creator_hash, nickname, liked_count, collected_count, comment_count,
share_count, image_list, tag_list, last_modify_ts, note_url, source_keyword
```

成功 run 的 native/raw/output JSONL 已做结构化脱敏，移除
`xsec_token/xsec_source`；业务 URL 同样清理，避免访问令牌进入 API。
成功后 native disposable profile 已清理，application profile 保留。

## 5. CollectorRun

```text
id: 15077
collector_name: MediaCrawler[xiaohongshu]
trigger_type: manual
status: success
fetched_raw: 20
created: 20
duplicate: 0
analyzed: 20
failed: 0
batch_id: 9f2f976c6da84e1c8ce84fabccbfef70
```

## 6. Opinion

数据库回读：

```text
source: xiaohongshu
source_type: xhs_note
count: 20
external_id: 全部非空
content: 全部非空
publish_time: 全部存在
duplicate: 0
```

没有发现新增微博记录，微博链路未被本次 XHS 运行改变。

XHS Normalizer 的核心映射：

```text
external_id  <- note_id
title        <- title
content      <- desc
author       <- nickname
url          <- note_url（去除 xsec_token/xsec_source）
publish_time <- time
engagement   <- liked_count/comment_count/collected_count/share_count
```

## 7. API and Frontend

使用管理员认证对现有 API 做只读验证：

```text
GET /api/opinions?source=xiaohongshu&page=1&size=20
HTTP 200
total=20
returned=20
source=["xiaohongshu"]
source_type=["xhs_note"]
external_ids_nonempty=true
urls_have_xsec_token=false
```

```text
GET /api/opinions/sources
HTTP 200
xiaohongshu present=true
```

`frontend/src/views/Opinions.vue` 已通过 `/opinions/sources` 动态读取来源，
并直接展示 Opinion 的 source 字段；无需修改 UI。

## 8. Scheduler

```text
enabled=true
schedule_enabled=false
```

当前 Scheduler candidate 数量为 `0`。本阶段没有启动 Scheduler，没有修改
`backend/app/core/scheduler.py`。Scheduler readiness 详见：

`docs/Phase_MediaCrawler_Platform_2G_Scheduler_Readiness.md`

## 9. Runtime Fixes Applied

本阶段为完成正式运行补齐了两项必要的通用适配：

1. RuntimeFactory 将字符串 checkout settings 归一化为 `Path`，保证
   checkout-relative imports 的 cwd contract 可用；
2. Registry 将 DataSource 的 `login_type` 传递到 RuntimeFactory，确保
   `config_json.login_type=qrcode` 不被环境默认 cookie 覆盖；
3. XHS Normalizer 和 Runner 日志增加会话 query 字段脱敏。

未新增 XHS Collector，未修改 CollectorService 业务契约、Opinion schema、
CollectorRun schema 或微博 compatibility。

## 10. First Attempts and Failure Classification

- live Admin POST：旧 8000 进程返回 422，未写入；
- 第一次手动装配：RuntimeFactory 字符串 `.resolve()`，已修复；
- 第二次 upstream：bundled Chromium `TargetClosedError`，未生成 artifact；
- 第三次 upstream：旧环境 login type 为 cookie，XHS 返回账号无权限；
- 最终运行：Chrome wrapper + source-local qrcode，登录、artifact、pipeline
  全部成功。

失败尝试均未创建 Opinion；最终成功 run 是 `CollectorRun.id=15077`。

## 11. Tests

```text
python -m pytest -q backend/tests/test_media_crawler*.py
181 passed, 1 warning

python -m compileall -q backend/app
PASS

git diff --check
PASS
```

额外验证：

- Registry resolve：PASS；
- Scheduler candidate with schedule disabled：0；
- API opinion readback：HTTP 200；
- XHS artifact sensitive-field scan：PASS；
- application/native profile lifecycle：PASS；
- 前端 source options contract：PASS。

## 12. Prohibited Changes Confirmation

- 未修改 `backend/app/models/`；
- 未修改 `backend/alembic/`；
- 未修改 `backend/app/core/scheduler.py`；
- 未修改 `.env`；
- 未修改 upstream MediaCrawler checkout；
- 未新增数据库字段或 migration；
- 未修改 Opinion / CollectorRun schema；
- 未启动新的 Scheduler；
- 未做自动采集；
- 未修改微博 `DataSource.id=40` 或微博 compatibility。

工作区开始时已 dirty；历史 tracked/untracked changes 均保留。

## 13. Final State

```text
REAL_SOURCE_ENABLED
```

XHS 当前为人工灰度启用，自动调度仍关闭。任何进一步开启
`schedule_enabled` 的操作需要单独审批。
