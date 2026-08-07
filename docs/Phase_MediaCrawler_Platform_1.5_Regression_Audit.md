# Phase MediaCrawler Platform-1.5 回归审计报告

## 1. 状态

`BLOCKED`

微博生产链路的行为回归通过，但严格的 Platform-1.5 架构验收未通过：通用 MediaCrawler 层仍保留微博默认值和微博兼容判断。

本阶段为只读审计。未修改业务代码、数据库、DataSource、Scheduler、`.env` 或生产配置；未执行真实采集、真实 Scheduler 或真实 MediaCrawler。

## 2. 工作区检查

审计开始时执行：

```text
git status --short --branch
git diff --stat
git diff --cached --stat
```

结果：

- branch：`main...origin/main`
- worktree：dirty，存在大量既有 tracked/untracked 改动
- `git diff --stat`：22 个 tracked 文件，包含既有任务改动及 Platform-1 改动
- `git diff --cached --stat`：空
- 未执行 `git reset`、`git checkout`、`git clean`、`git restore`
- 本阶段只新增本报告文件，未覆盖或回滚其他改动

禁区检查结果：

```text
FORBIDDEN_DIFF_NONE
DIFF_CHECK_OK
```

未发现 `CollectorRun`、`Opinion`、`Scheduler`、`alembic/versions`、`.env` 或前端构建产物的本阶段变更。

## 3. DataSource.id=40 验证

使用只读 SQLAlchemy 查询，未执行 commit、flush 或写操作。

结果：

```json
{
  "id": 40,
  "key": "weibo_mediacrawler",
  "name": "微博（MediaCrawler）",
  "type": "social",
  "class_path": "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector",
  "enabled": true,
  "schedule_enabled": false,
  "scope_region_codes": "131000",
  "config_json": {
    "collector": "mediacrawler",
    "platform": "weibo",
    "keywords": [],
    "max_items": 20,
    "collection_scope": "regional",
    "collection_mode": "regional"
  }
}
```

class path 动态解析结果：

```text
MediaCrawlerWeiboCollector
  -> MediaCrawlerPlatformCollector
  -> collector_capability = mediacrawler
```

结果：`PASS`

## 4. 调用链验证

旧入口：

```text
DataSource.id=40
  -> class_path
  -> MediaCrawlerWeiboCollector
  -> CollectorService
```

当前链路：

```text
CollectorService.collect_and_analyze()
  -> resolve_collectors_verbose()
  -> registry._resolve_core()
  -> registry.import_class()
  -> registry._build_collector()
  -> MediaCrawlerRuntimeFactory
  -> MediaCrawlerWeiboCollector
  -> MediaCrawlerPlatformCollector.fetch()
  -> MediaCrawlerPlatformCollector._ensure_runtime()
  -> MediaCrawlerRunner.run()
  -> MediaCrawlerPlatformCollector._read_jsonl()
  -> WeiboNormalizer.normalize()
  -> CollectorService._process_collector()
  -> Opinion / Admission / Risk / Event aggregation
```

关键证据：

- `backend/app/collectors/registry.py:_resolve_core`
- `backend/app/collectors/registry.py:_build_collector`
- `backend/app/collectors/media_crawler_weibo_collector.py:MediaCrawlerWeiboCollector`
- `backend/app/collectors/media_crawler_platform_collector.py:fetch`
- `backend/app/collectors/media_crawler_platform_collector.py:_read_jsonl`
- `backend/app/collectors/mediacrawler_normalizers.py:WeiboNormalizer`
- `backend/app/collectors/service.py:_process_collector`

`CollectorService` 对 MediaCrawler 使用 `collector_capability == "mediacrawler"` 判断，没有新增 `if platform == "weibo"` 或 `if key == "weibo_mediacrawler"` 分支。

现有 `weibo_octopus` 分支属于原有八爪鱼链路，不是本次 MediaCrawler 分支，未修改。

结果：`PASS`

## 5. Fixture 回归

fixture：

```text
backend/tests/fixtures/media_crawler/weibo.jsonl
```

通过：

```text
MediaCrawlerPlatformCollector
  + WeiboNormalizer
  -> normalized records
```

当前输出的核心记录：

| external_id | source | source_type | author | url | publish_time | engagement |
|---|---|---|---|---|---|---|
| `mc-1001` | `weibo` | `weibo_post` | `廊坊观察` | `https://weibo.com/1001/mc-1001` | `2026-08-04 02:00:00` | likes=12000, comments=3, reposts=5 |
| `mc-1002` | `weibo` | `weibo_post` | `本地居民` | `https://weibo.com/1002/mc-1002` | `2026-08-04 02:01:00` | 0, 0, 0 |
| `mc-1003` | `weibo` | `weibo_post` | 空 | 空 | null | 0, 0, 0 |

旧行为依据：

- 既有 `test_media_crawler_adapter.py` fixture assertions；
- 既有 title fallback、重复记录、非法 JSONL 行、互动数字和日期解析测试。

字段核对：

- `source`：一致
- `source_type`：一致
- `external_id`：一致
- `author`：一致
- `url`：一致
- `content`：一致
- `publish_time`：一致
- `engagement`：一致

结果：`PASS`

## 6. Opinion 映射回归

`CollectorService._process_collector()` 保持既有映射：

```text
item.title         -> Opinion.title
item.content       -> Opinion.content
item.source        -> Opinion.source
item.url           -> Opinion.url
item.publish_time  -> Opinion.publish_time
item.source_type   -> Opinion.source_type
item.author        -> Opinion.author
item.engagement    -> Opinion.engagement
item.external_id   -> Opinion.external_id
```

证据位置：

- `backend/app/collectors/service.py:605-619`

本阶段未向生产数据库写入任何 Opinion，也未执行真实 CollectorService 数据库闭环。

去重、Admission、Risk、Event aggregation 仍通过原有 Service 代码路径执行；相关模型文件没有本阶段变更。

结果：`PASS（静态映射审计；未执行生产写入）`

## 7. Profile / Lock / Artifact 隔离

已验证的路径逻辑：

```text
legacy Weibo:
  profiles/manual
  profiles/scheduler
  locks/weibo_mediacrawler.lock
  runs/<batch_id>/output/weibo.jsonl

scoped source:
  profiles/weibo/<source_key>/manual
  profiles/weibo/<source_key>/scheduler
  locks/weibo/<source_key>.lock
  runs/<batch_id>/weibo/<source_key>/output/weibo.jsonl
```

已覆盖：

- manual/scheduler profile 不同；
- scheduler disposable profile；
- 成功后 disposable profile 清理；
- 失败后 disposable profile 保留；
- persistent profile 不被 fake browser 写入；
- artifact、profile、lock scope 不覆盖；
- 不启动真实 crawler。

测试结果：通过相关隔离测试。

结果：`PASS`

## 8. Command 兼容

微博 PlatformSpec：

```text
platform = weibo
cli_code = wb
crawler_type = search
artifact_name = weibo
native_output_parts = weibo/jsonl
```

argv 快照保持：

```text
--platform wb
--type search
--save_data_option jsonl
--save_data_path <resolved output directory>
```

未知 platform、非法 login_type、非法 crawler_type、非法 runtime 配置和关闭 real-run gate 均能明确拒绝。

结果：微博 argv 兼容 `PASS`。

## 9. 发现问题

### P1：通用层仍存在微博默认值和微博判断

文件：

- `backend/app/collectors/media_crawler_platform_collector.py:46-73`
- `backend/app/collectors/mediacrawler_command_builder.py:39`
- `backend/app/collectors/mediacrawler_batch.py:50`
- `backend/app/collectors/mediacrawler_runner.py:109-110, 289, 304`
- `backend/app/collectors/mediacrawler_runtime.py:153-162`

问题：

- `MediaCrawlerPlatformCollector` 类级默认值仍为 `weibo_mediacrawler` / `weibo`；
- 通用 Collector 仍包含 `self.platform == "weibo"` 分支；
- `MediaCrawlerCommandBuilder` 无 spec 时默认解析 `weibo`；
- `MediaCrawlerBatchLocator` 默认 `artifact_name="weibo"`；
- `MediaCrawlerRunner` 默认 `artifact_name="weibo"`、`native_output_parts=("weibo", "jsonl")`、`source_key="weibo_mediacrawler"`；
- RuntimeFactory 使用 `_legacy_layout` 和 `platform == "weibo"` 判断维持旧布局。

影响：

- 当前微博生产链路没有观察到行为回归；
- 但严格意义上通用层仍然可以隐式回退到微博语义；
- Platform-1.5 的“通用层不存在 `wb` / `weibo.jsonl` / 微博 artifact 硬编码”验收条件未满足；
- 后续平台接入如果遗漏显式 PlatformSpec，可能产生错误的 artifact、profile 或 native output discovery。

建议修复：

1. 通用 Collector、Runner、BatchLocator、CommandBuilder、RuntimeFactory 改为要求显式 `PlatformSpec` 或显式 artifact contract；
2. 将微博兼容默认值集中在 `MediaCrawlerWeiboCollector` 兼容层；
3. 将 legacy path 兼容策略封装为独立 compatibility policy，不在通用类中使用 `platform == "weibo"`；
4. 修复后重新执行 Platform-1.5 全量回归审计。

按本阶段要求，发现问题后未自行修改。

## 10. 数据库影响

```text
migration: NONE
model change: NONE
DataSource write: NO
Opinion write: NO
```

DataSource.id=40 只执行了只读查询。

## 11. 测试执行

完整 MediaCrawler 测试：

```text
PowerShell:
$tests = Get-ChildItem tests -Filter 'test_media_crawler*.py'
python -m pytest -q $tests

结果：133 passed
```

Platform-1.5 聚焦测试：

```text
python -m pytest -q \
  tests/test_media_crawler_platform_1.py \
  tests/test_media_crawler_adapter.py \
  tests/test_media_crawler_enable_2b_fix4.py \
  tests/test_media_crawler_2e_fix.py \
  tests/test_media_crawler_2f_fix.py

结果：34 passed
```

未执行：

- 真实微博采集；
- 真实 MediaCrawler；
- 真实 Scheduler；
- 数据库迁移；
- 生产写入。

此前尝试的 `test_collector.py`、`test_data_source_quality.py`、`test_datasource_schedule.py` 在当前环境中超时，未产生失败栈。

## 12. 最终结论

微博入口、class path、fixture normalized output、Opinion 字段映射、profile/lock/artifact 隔离、argv 和安全 gate 均通过回归验证。

但由于通用层仍保留微博默认值和微博判断，严格 Platform-1.5 架构审计不能签发：

```text
BLOCKED
```

完成通用层微博默认值清理并重新通过本报告中的回归项后，才可进入：

```text
READY_FOR_PLATFORM_2
```
