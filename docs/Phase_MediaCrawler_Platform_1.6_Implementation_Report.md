# Phase MediaCrawler Platform-1.6 Implementation Report

## Status

`IMPLEMENTED`

`READY_FOR_PLATFORM_2`

本阶段只完成 Generic MediaCrawler Layer Decoupling。未接入新平台，未执行真实采集、真实 Scheduler、数据库迁移或生产配置变更。

## 1. 修改文件

核心实现：

- `backend/app/collectors/mediacrawler_platform.py`
- `backend/app/collectors/mediacrawler_compatibility.py`
- `backend/app/collectors/mediacrawler_weibo_compatibility.py`
- `backend/app/collectors/media_crawler_platform_collector.py`
- `backend/app/collectors/media_crawler_weibo_collector.py`
- `backend/app/collectors/mediacrawler_command_builder.py`
- `backend/app/collectors/mediacrawler_batch.py`
- `backend/app/collectors/mediacrawler_runner.py`
- `backend/app/collectors/mediacrawler_runtime.py`
- `backend/app/collectors/registry.py`
- `backend/app/collectors/source_config.py`

operator-only 调用点：

- `backend/scripts/run_mediacrawler_real_verify.py`
- `backend/scripts/test_mediacrawler_manual.py`

测试：

- MediaCrawler 现有测试中的显式 spec/policy 注入；
- `backend/tests/test_media_crawler_platform_1.py` 新增 Platform-1.6 回归覆盖；
- 相关 MediaCrawler fixture、隔离、配置、Runner、Registry 测试同步更新。

未修改：

- `backend/app/models/`
- `backend/alembic/`
- `backend/app/core/scheduler.py`
- `.env`
- `CollectorService` 业务逻辑
- `DataSource` 真实数据

## 2. 微博兼容迁移位置

微博兼容契约集中在：

- `MediaCrawlerWeiboCollector`
- `mediacrawler_weibo_compatibility.py`
- `WEIBO_PLATFORM_SPEC`
- `WEIBO_COMPATIBILITY_POLICY`

微博 wrapper 显式注入：

- `platform_spec`
- `data_source_key=weibo_mediacrawler`
- legacy profile/artifact/lock policy

因此 `DataSource.id=40` 的 class path 仍然解析为：

```text
app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
```

## 3. 移除的 generic defaults

已移除 generic 层中的：

- `MediaCrawlerPlatformCollector` 默认 platform/source key；
- `MediaCrawlerCommandBuilder` 无 spec 时的微博 fallback；
- `MediaCrawlerRunner` 默认 `artifact_name`、native output parts、platform/source key；
- `MediaCrawlerBatchLocator` 默认微博 artifact；
- `MediaCrawlerRuntimeFactory` 默认微博 platform/source key；
- RuntimeFactory 中基于 `platform == "weibo"` 的 legacy layout 判断；
- DataSource config 中缺少 platform 时的微博隐式 fallback。

现在以下 generic 构造器缺少显式 `PlatformSpec` 时会明确失败：

- `MediaCrawlerPlatformCollector`
- `MediaCrawlerCommandBuilder`
- `MediaCrawlerRunner`
- `MediaCrawlerBatchLocator`
- `MediaCrawlerRuntimeFactory`

未知平台不会进入微博逻辑。

## 4. 兼容性验证

已保持：

- 微博旧 JSONL fixture normalized output；
- `source`、`source_type`、`external_id`、`author`、`url`、`publish_time`、`engagement` 语义；
- 旧微博 artifact 名称 `weibo.jsonl`；
- native output discovery `weibo/jsonl`；
- legacy profile 路径 `profiles/manual`、`profiles/scheduler`；
- legacy lock 路径 `locks/weibo_mediacrawler.lock`；
- manual/scheduler profile isolation；
- 成功清理 disposable profile、失败保留 profile；
- real-run gate 和无 fixture/mock 时不启动真实 MediaCrawler。

## 5. 测试结果

完整 MediaCrawler 测试：

```text
135 passed
```

执行命令：

```powershell
$tests = Get-ChildItem tests -Filter 'test_media_crawler*.py' |
  Sort-Object Name |
  ForEach-Object { $_.FullName }
python -m pytest -q $tests
```

Platform-1/1.6 聚焦测试：

```text
Platform-1 tests: 8 passed
核心/隔离回归: 78 passed
Enable/Registry/Runtime 回归: 26 passed
```

静态检查：

```text
python -m compileall: PASS
git diff --check: PASS
禁改目录 diff: NONE
generic Weibo fallback scan: PASS
```

## 6. 禁止项确认

- 未执行真实采集；
- 未启动真实 MediaCrawler；
- 未执行 Scheduler；
- 未执行数据库迁移；
- 未修改模型或 migration；
- 未修改 `.env`；
- 未修改生产 DataSource；
- 未执行 `git reset`、`git checkout`、`git clean` 或批量回滚。

工作区原有 dirty baseline 已保留。本报告不将无关 tracked/untracked 改动归入 Platform-1.6。

## 7. 结论

Platform-1.6 generic decoupling 已完成。微博生产入口继续通过 `MediaCrawlerWeiboCollector` 使用显式 spec 和 compatibility policy，generic MediaCrawler 层不再隐式选择微博。

当前状态：

```text
IMPLEMENTED
READY_FOR_PLATFORM_2
```
