# Phase MediaCrawler Platform-2-C2

## Status

`IMPLEMENTED`

`READY_FOR_PLATFORM_2_D`

本阶段完成 XHS 的 multi-crawler-mode contract 和通用 profile adapter
接线。结果仍然是 offline/runtime contract only，不授权生产启用。

## Contract Source

`FOUND`

依据前序审计报告中的只读证据：

- MediaCrawler commit:
  `1779dde9725f6b7ef42e29022c0054b3e678f1af`
- CLI platform: `xhs`
- crawler modes: `search`, `detail`, `creator`
- login types: `qrcode`, `phone`, `cookie`
- output: `jsonl`
- native output: `xhs/jsonl`
- XHS native browser profile: `browser_data/xhs_user_data_dir`

本阶段未修改外部 MediaCrawler checkout，未启动其 CLI。

## 修改文件

本阶段实际修改：

- `backend/app/collectors/mediacrawler_runtime.py`
- `backend/app/collectors/media_crawler_platform_collector.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/tests/test_media_crawler_xhs_platform.py`
- `backend/tests/test_media_crawler_xhs_command_contract.py`
- `backend/tests/test_media_crawler_xhs_runtime_contract.py`
- `docs/Phase_MediaCrawler_Platform_2C2_Implementation_Report.md`

前序 dirty worktree 中已存在并被本阶段复用：

- `backend/app/collectors/mediacrawler_platform.py`
- `backend/app/collectors/mediacrawler_profile_adapter.py`
- `backend/app/collectors/mediacrawler_normalizers.py`
- `backend/tests/fixtures/media_crawler/xiaohongshu.jsonl`

其他已有 dirty changes 未覆盖、删除或回滚。

## Multi Crawler Mode Contract

`MediaCrawlerPlatformSpec` 已使用通用字段表达 mode：

```text
supported_crawler_types = ("search", "detail", "creator")
default_crawler_type = "search"
```

微博保持：

```text
supported_crawler_types = ("search",)
default_crawler_type = "search"
```

`MediaCrawlerCommandBuilder` 只读取 `PlatformSpec`，不包含
`if platform == "xiaohongshu"` 或其他 XHS 专用分支。

XHS argv contract 已验证：

```text
--platform xhs
--type search|detail|creator
--lt qrcode|phone|cookie
--save_data_option jsonl
```

未知 mode fail closed，argv 不包含 `weibo` 或 `wb`。

## Profile Adapter

通用 `MediaCrawlerProfileAdapter` 已接入 `MediaCrawlerRuntimeFactory`。

应用 profile：

```text
profiles/xiaohongshu/<source_key>/<manual|scheduler>
```

native runtime view：

```text
runtime/upstream_profiles/xiaohongshu/<source_key>/<manual|scheduler>/
  browser_data/xhs_user_data_dir
```

adapter 按 platform、source key、trigger 创建 native view，并将
`command_cwd` 指向对应 native runtime root。profile path、Cookie、token
均不进入 `DataSource.config_json`。

成功路径：

- 清理 native profile view；
- scheduler disposable profile 继续按既有 Collector 生命周期清理。

失败路径：

- 保留 native profile view；
- 保留 scheduler disposable profile；
- 保留失败证据供审计。

微博的 `upstream_profile_parts=()` 保持 identity mapping，并继续使用
`WEIBO_COMPATIBILITY_POLICY` 的 legacy profile、artifact、lock layout。

## XHS Runtime Compatibility

`PASS - OFFLINE FAKE UPSTREAM`

fake upstream contract 验证：

- 可以读取 `browser_data/xhs_user_data_dir`；
- `sourceA/manual`、`sourceA/scheduler`、`sourceB/manual` 互不污染；
- native JSONL 可从 `xhs/jsonl` 被发现；
- native output 可被现有 XHS Normalizer 读取；
- 成功后 native profile view 被清理；
- 失败或 gate 阻断时 profile 被保留。

XHS `allow_real_collection` 仍为 `false`。即使环境 gate 被误设为开启，
generic Runner 也会在 subprocess 前拒绝 XHS real run。

## Normalizer

`XhsNormalizer` 继续复用通用 Normalizer registry，并验证：

- `note_id -> external_id`
- `title`
- `desc -> content`
- `nickname -> author`
- `note_url -> url`
- `time -> publish_time`
- `liked_count`
- `comment_count`
- `collected_count`
- `share_count`

日期、中文互动单位、空字段、非法互动数字、重复记录行为保持既有
Normalizer/Collector 语义。微博 Normalizer 和旧 fixture 输出未改变。

fixture 和 normalized output 均拒绝保留：

```text
xsec_token
cookie
access_token
browser state
```

## Weibo Regression

`PASS`

- `DataSource.id=40` class path 仍为
  `app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector`；
- `MediaCrawlerWeiboCollector` 仍通过 shared
  `MediaCrawlerPlatformCollector` 生命周期运行；
- `WEIBO_PLATFORM_SPEC` 的 `wb`、`weibo/jsonl`、`weibo.jsonl` 语义保持；
- legacy profile 和 lock policy 保持；
- 微博 scheduler/manual isolation 回归通过；
- 未在 generic 层增加微博业务分支。

## Database Impact

`NONE`

未修改：

- `backend/app/models/`
- `backend/alembic/`
- `Opinion`
- `CollectorRun`
- `DataSource` schema
- 数据库字段、表或 migration

## Scheduler Impact

`NONE`

未修改 `backend/app/core/scheduler.py`，未启动 Scheduler，也未增加任何
平台专用 Scheduler 分支。

## Tests

定向 C2 测试：

```powershell
python -m pytest -q backend/tests/test_media_crawler_xhs_runtime_contract.py
```

结果：`8 passed`

全部 MediaCrawler 测试：

```powershell
$paths = Get-ChildItem backend/tests -Filter 'test_media_crawler*.py' |
  Sort-Object Name | ForEach-Object { $_.FullName }
python -m pytest -q $paths
```

结果：`160 passed`

其他验证：

```text
python -m compileall -q backend/app       PASS
git diff --check                          PASS
generic XHS/Weibo branch scan             PASS
禁改目录 tracked diff                    NONE
```

## Prohibited Actions Confirmation

- 未真实采集小红书；
- 未启动真实 MediaCrawler；
- 未启动 Scheduler；
- 未使用真实 Cookie、token 或账号；
- 未修改生产 DataSource；
- 未修改 `.env`；
- 未修改数据库或 migration；
- 未修改 models、Opinion、CollectorRun；
- 未执行 `git reset`、`git checkout`、`git clean` 或 `git restore`；
- 未覆盖、删除或批量回滚既有 dirty changes。

## Next Step

`READY_FOR_PLATFORM_2_D`

下一阶段仍应保持 XHS real-run gate 关闭，直到完成显式 operator review、
生产 profile readiness 检查和真实运行授权流程。本报告不构成生产启用批准。

当前状态：

```text
IMPLEMENTED
OFFLINE_RUNTIME_CONTRACT_VALIDATED
READY_FOR_PLATFORM_2_D
```
