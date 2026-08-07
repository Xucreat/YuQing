# Phase MediaCrawler Platform-2-E2 Real Runtime Closed Loop Report

## 1. Status

`REAL_RUNTIME_VALIDATED`

本阶段完成一次受控的 XHS 最小真实运行闭环。运行使用临时 source key、
隔离 runtime/profile/output 和测试数据库；未启动 Scheduler，未修改生产配置。

## 2. Runtime

- 运行日期：`2026-08-06`
- MediaCrawler checkout：
  `D:\code files\mediaCrawler\MediaCrawler`
- upstream commit：
  `1779dde9725f6b7ef42e29022c0054b3e678f1af`
- subprocess cwd：checkout root
- profile root：
  `C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_phase2e2_verify_keyword\application_profiles`
- output root：
  `C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_phase2e2_verify_keyword`
- application profile：
  `...\application_profiles\xiaohongshu\xhs_phase2e2_verify\manual`
- native browser profile：由 adapter 临时绑定并在成功后清理
- 生产 `browser_data`：未使用
- source key：`xhs_phase2e2_verify`
- keyword：`大厂`
- crawler type：`search`
- login：`qrcode`
- max items：`5`
- 实际耗时：约 `110.34s`，`08:31:53Z` 至 `08:33:43Z`

## 3. Real argv

真实命令由 `PlatformSpec` 和通用 CommandBuilder 生成，敏感信息未写入
argv：

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
--crawler_max_notes_count 5
--save_data_path
C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_phase2e2_verify_keyword\runs\xhs_phase2e2_verify_keyword\xiaohongshu\xhs_phase2e2_verify\output
```

验证：

- subprocess cwd 为 checkout root；
- argv 不包含 `weibo` 或 `wb`；
- 未使用 Cookie、token 或 password 参数。

## 4. Login

二维码登录流程成功：

- upstream 首次检查登录态为 false；
- 进入二维码登录；
- UI 元素确认登录成功；
- XHS crawler 随后进入 search；
- 临时 native profile 在运行期间可用，成功后按约定清理；
- application profile 保留用于失败审计和后续受控验证。

运行日志和 JSONL 中出现的 `xsec_token` 已在保留证据中脱敏，secret scan
结果为 `PASS`。未将 Cookie、token 或 browser state 写入代码、数据库或
生产配置。

## 5. Native Artifact

最终 native artifact：

```text
C:\Users\Administrator\Desktop\YQ\runtime\mediacrawler\xhs_phase2e2_verify_keyword\runs\xhs_phase2e2_verify_keyword\xiaohongshu\xhs_phase2e2_verify\output\xhs\jsonl\search_contents_2026-08-06.jsonl
```

结果：

- subprocess exit code：`0`
- native JSONL records：`20`
- Runner bounded output：`5`
- normalized output：
  `...\runs\xhs_phase2e2_verify_keyword\xiaohongshu\xhs_phase2e2_verify\output\xiaohongshu.jsonl`
- metrics：`raw_count=20`、`output_count=5`、`failed=0`
- duplicate：`0`

真实 native JSONL 顶层字段包括：

```text
note_id
type
title
desc
video_url
time
last_update_time
creator_hash
nickname
liked_count
collected_count
comment_count
share_count
image_list
tag_list
last_modify_ts
note_url
source_keyword
```

真实记录未直接暴露 `xsec_token` 顶层字段；保留的证据文件已对 URL token
和敏感字段做脱敏。

## 6. Normalizer

`XhsNormalizer` 对真实 JSONL 成功映射：

- `external_id` <- `note_id`
- `title` <- `title`
- `content` <- `desc`
- `author` <- `nickname`
- `url` <- `note_url`
- `publish_time` <- `time`，epoch milliseconds
- `engagement.likes` <- `liked_count`
- `engagement.comments` <- `comment_count`
- `engagement.collections` <- `collected_count`
- `engagement.reposts` <- `share_count`
- `source`：`xiaohongshu`
- `source_type`：`xhs_note`

5 条进入 Collector pipeline 的记录均具有非空 `external_id`、content、
author、publish_time 和 engagement 对象。

## 7. Collector Pipeline and Database

首次 CollectorService 尝试被测试库既有 schema 的
`data_sources.keyword_cursor` 缺失阻断；未执行 migration。随后在一次性
测试进程中旁路该旧 schema 查询，保持 CollectorService 主流程、去重、
Admission、Risk 和事件契约不变。

测试数据库：

```text
opinion_test
postgresql+psycopg://opinion_user:***@127.0.0.1:5433/opinion_test
```

最终入库结果：

- `created=5`
- `analyzed=5`
- `duplicate=0`
- `failed=0`
- `admission_filtered=0`
- `CollectorRun.status=success`
- `CollectorRun.collector_name=MediaCrawler[xiaohongshu]`
- `CollectorRun.trigger_type=manual`
- 真实 Opinion source：`xiaohongshu`
- 真实 Opinion source_type：`xhs_note`
- external_id：全部非空
- analysis_status：`completed`

本次使用 test-only `scope_region_codes=['131028']` 满足现有 Opinion
region/admission 合约；未写入生产 DataSource。

## 8. Frontend Observability

使用测试数据库和认证后的 FastAPI API 只读验证，未进入应用 lifespan，
因此未启动 Scheduler：

```text
GET /api/opinions?source=xiaohongshu&page=1&size=20
HTTP 200
total=5
returned=5
source=["xiaohongshu"]
source_type=["xhs_note"]
external_ids_nonempty=true
```

`GET /api/opinions/sources` 同样返回 `HTTP 200`，来源选项包含
`xiaohongshu`。前端 `Opinions.vue` 使用该列表接口展示 `row.source`，
因此 XHS 来源已满足舆情列表的可观察性契约；未修改 UI。

## 9. First Attempt and Failure Classification

第一次真实尝试分类为 `A. MediaCrawler 启动失败`：Playwright bundled
Chromium 启动崩溃，未进入登录、未生成 artifact。随后使用一次性浏览器
runtime wrapper 完成最终受控运行，未修改 upstream checkout。

中间一次尝试曾因 PowerShell stdin 编码将关键词显示为 `??`，该结果未作为
验收证据；最终运行使用 UTF-8 argv，关键词确认为 `大厂`。

## 10. Tests and Checks

已通过：

```text
python -m pytest -q backend/tests/test_media_crawler*.py
python -m compileall backend/app
git diff --check
```

结果：

- MediaCrawler tests：`171 passed`
- compileall：`PASS`
- diff check：`PASS`
- frontend API readback：`PASS`
- secret scan：`PASS`

## 11. Prohibited Changes Confirmation

- 未修改 `backend/app/models/`
- 未修改 `backend/alembic/`
- 未修改 `backend/app/core/scheduler.py`
- 未修改 `.env`
- 未修改生产 DataSource
- 未修改 Opinion / CollectorRun 结构
- 未修改微博逻辑或 `WeiboCompatibilityPolicy`
- 未修改 upstream MediaCrawler
- 未启动 Scheduler
- 未执行 migration
- 未使用生产 profile、Cookie、token 或 password

工作区在本阶段开始前已 dirty；既有 tracked/untracked changes 均保留。

## 12. Next Step

建议下一阶段先进行人工批准的受控灰度评审，包括账号登录态轮换、XHS
采集频率和风控边界、测试库证据清理策略，以及在生产启用前重新确认
real-run gate 和 DataSource 配置审批。

当前最终状态：

```text
REAL_RUNTIME_VALIDATED
```
