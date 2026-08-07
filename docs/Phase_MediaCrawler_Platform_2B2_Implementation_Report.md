# Phase MediaCrawler Platform-2-B2

## Status

`IMPLEMENTED`

最终状态：`OFFLINE_VALIDATION_ONLY`

当前建议：`READY_FOR_PLATFORM_2_C`

本阶段只完成 XHS offline contract validation。未进行真实小红书采集，不启动真实 MediaCrawler。

## Contract Source

`NOT_FOUND`

结论：`CONTRACT_SOURCE_UNAVAILABLE`

- 仓库没有 MediaCrawler 上游源码 checkout；
- 没有 XHS 专属锁定版本、CLI parser 或 native output 实现可供只读确认；
- 历史文档记录过微博外部 commit `1779dde9725f6b7ef42e29022c0054b3e678f1af`，但没有提供可验证的 XHS CLI/output contract；
- `runtime/mediacrawler` 只有既有运行目录和 profile/artifact，不是上游源码证据；
- 本阶段没有安装、下载、导入或启动任何外部 MediaCrawler。

因此 XHS Spec 的 `cli_code`、`crawler_type`、`native_output_parts` 和 login policy 继续保持 `UNKNOWN`/空能力，不做猜测。

## XHS PlatformSpec

字段没有伪造上游值，仍为：

```text
platform              = xiaohongshu
cli_code              = UNKNOWN
crawler_type          = UNKNOWN
artifact_name         = xiaohongshu
native_output_parts   = ()
supported_login_types = empty
capabilities          = empty
allow_real_collection = false
```

通用 `MediaCrawlerPlatformSpec` 未新增平台专用结构。XHS Spec 只用于离线 contract、fixture、路径和 fail-closed 测试。

## Command Contract

结果：`PASS - FAIL CLOSED`

- XHS Spec 的 CLI/crawler/login contract 未解析时，CommandBuilder 明确拒绝生成 argv；
- 不会把 `UNKNOWN` 转成可执行命令；
- 使用测试专用 resolved Spec 验证 argv 的 platform、crawler type、login type、save path 均来自 Spec/调用参数；
- argv 不包含 `weibo` 或 `wb`；
- real-run gate 关闭时注入命令未被执行。

这不代表 XHS 真实 CLI 已被确认，只证明 generic Command Adapter 不会误用未验证 Spec。

本阶段修改了 `backend/app/collectors/mediacrawler_command_builder.py`，仅增加未解析 contract 的 fail-closed 校验；微博已解析 contract 行为不变。

## Artifact Isolation

结果：`PASS`

已验证 `platform=xiaohongshu`、独立 `data_source_key` 和独立 `batch` 形成隔离：

- raw path 使用 `xiaohongshu.jsonl`；
- output path 使用 `xiaohongshu.jsonl`；
- metrics path 位于 XHS/source/batch scope；
- lock path 使用 `locks/xiaohongshu/<data_source_key>.lock`；
- profile path 使用 `profiles/xiaohongshu/<data_source_key>/<trigger>`；
- XHS artifact path 不含微博 artifact。

## Normalizer Validation

结果：`PASS`

已验证：

- 正常 note fixture；
- `external_id`、`content`、`author`、`url`、`publish_time`、`engagement` 统一字段；
- 缺失作者返回 `None`；
- 空正文返回 `None`；
- 缺失时间返回 `None`；
- 非法互动数字安全降为 `0`；
- 重复记录由 generic Collector dedup；
- WeiboNormalizer 未修改。

## Collector Validation

结果：`PASS - OFFLINE ONLY`

`MediaCrawlerPlatformCollector` 能通过显式 XHS Spec 接收 fixture，完成 JSONL 读取、Normalizer、批内去重和 runner metrics 记录。没有新增 XhsCollector，没有修改 CollectorService，也没有 generic Collector 的平台专用分支。

## Weibo Regression

结果：`PASS`

- `MediaCrawlerWeiboCollector` class path 保持不变；
- `DataSource.id=40` 仍通过 `app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector` 兼容入口；
- 既有微博 fixture normalized output、`source/source_type/external_id/engagement` 语义保持；
- legacy 微博 artifact/profile/lock contract 由既有测试继续覆盖；
- 完整 MediaCrawler 测试集通过。

## Database Impact

`NONE`

未新增字段、表或 migration，未修改 models、DataSource、CollectorRun、Opinion 或 CollectorService。

## Real Collection

`NOT EXECUTED`

- 未真实采集；
- 未执行真实小红书采集；
- 未启动真实 MediaCrawler；
- 未启动 Scheduler；
- 未使用真实 Cookie、token 或 profile；
- 未修改 `.env`、生产配置或生产 DataSource。

## Tests

执行：

```powershell
python -m pytest -q backend/tests/test_media_crawler_xhs_platform.py backend/tests/test_media_crawler_xhs_command_contract.py backend/tests/test_media_crawler_xhs_b2.py
$paths = Get-ChildItem backend/tests -Filter 'test_media_crawler*.py' | Sort-Object Name | ForEach-Object { $_.FullName }
python -m pytest -q $paths
```

结果：

```text
XHS/B2 + Platform-1 focused tests: 32 passed
all backend/tests/test_media_crawler*.py: 152 passed
```

所有测试均为 fixture、路径、config、registry、metrics 或 real-run gate 测试。

## Next Step

`READY_FOR_PLATFORM_2_C`

Platform-2-C 仍需先取得可审计的 MediaCrawler 上游 XHS contract source，再决定是否填充真实 `cli_code`、`crawler_type`、login policy 和 native output path。当前结果不授权真实运行。
