# Phase MediaCrawler-1B 前审计报告

## 1. 审计目的

本次审计在实现 Phase MediaCrawler-1B 前完成，范围限定为阅读现有代码、只读查询 PostgreSQL 和确认 1A 运行边界。未写入数据库，未启动 MediaCrawler，未调用微博接口。

## 2. 1A 代码核对

### Runner

文件：`backend/app/collectors/mediacrawler_runner.py`

- `MediaCrawlerRunner.run()` 创建 `runtime/mediacrawler/runs/{batch_id}/config`、`output` 和 `crawler.log`。
- `fixture_path` 模式只复制固定 JSONL；显式 `command` 模式使用 `subprocess.run()`。
- 已处理 timeout、非零 exit code、stderr、输出文件缺失和日志脱敏。
- 当前无 command 且无 fixture 时抛出 `MediaCrawlerRunnerConfigurationError`，不会根据配置自动启动 MediaCrawler。

### Collector

文件：`backend/app/collectors/media_crawler_weibo_collector.py`

- `MediaCrawlerWeiboCollector` 继承 `BaseCollector`。
- `fetch(keywords=None, region_kw=None, topic_kw=None)` 返回 `list[dict]`，符合 `CollectorService` 的调用契约。
- `normalize_keywords()` 去空、去重并保持输入顺序。
- `_read_jsonl()` 读取 JSONL、记录读取/解析/失败/重复数量，并按 `mid`、`id`、`external_id` 等字段标准化微博帖子。

## 3. CollectorService 契约

文件：`backend/app/collectors/service.py`

关键流程：

```text
CollectorService.collect_and_analyze()
  -> registry.resolve_collectors_verbose()
  -> collector.fetch(keywords=..., region_kw=..., topic_kw=...)
  -> 基础准入/地域判断
  -> URL 或 title+publish_time 去重
  -> Opinion
  -> RuleFallbackProvider / RiskEngine
  -> CollectorRun 状态与统计
```

因此 MediaCrawler Collector 不应直接访问数据库，也不需要修改 `CollectorService`、`Opinion` 或 `CollectorRun`。

## 4. DataSource 模型与注册能力

文件：`backend/app/models/data_source.py`

已存在并可承载本源所需字段：

- `key`
- `name`
- `type`
- `class_path`
- `config_json`
- `enabled`
- `schedule_enabled`
- `schedule_interval_minutes`
- `next_collect_time`

文件：`backend/app/collectors/registry.py`

- `import_class()` 支持从 `class_path` 动态导入。
- `_resolve_core()` 从 `data_sources` 读取启用源并实例化采集器。
- `config_json` 中的策略键会被剥离，其他构造参数传入 Collector。

文件：`backend/app/api/admin_data_sources.py`

- `create_data_source()` 已有数据源创建接口，并会先调用 `_build_test()`。
- 该创建函数当前没有显式传入 `schedule_enabled`，模型默认值为 `true`。
- 因此本阶段不直接调用该写接口；新增注册规范使用显式 `enabled=false`、`schedule_enabled=false`，并默认 dry-run。

目标注册配置为：

```json
{
  "key": "weibo_mediacrawler",
  "name": "微博（MediaCrawler）",
  "type": "social",
  "class_path": "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector",
  "enabled": false,
  "schedule_enabled": false,
  "schedule_interval_minutes": 60,
  "config_json": "{\"collection_mode\":\"manual\"}"
}
```

## 5. Scheduler 核对

文件：`backend/app/core/scheduler.py`；仓储：`backend/app/collectors/data_source_repository.py`

- `_run_collector_tick()` 只选择 `enabled=true AND schedule_enabled=true` 且到期的源。
- `scheduled_enabled_sources()` 同样要求 `schedule_enabled=true`。
- Scheduler 中没有 MediaCrawler 专用 job。
- 只要目标数据源保持 `schedule_enabled=false`，不会进入现有自动调度；本阶段不修改 Scheduler。

## 6. PostgreSQL 只读身份核验

执行时间：2026-08-04（Asia/Shanghai）。

只读查询结果：

```text
current_database = opinion_db
current_user     = opinion_user
server           = 127.0.0.1:5432
alembic_version  = p12_datasource_schedule
```

`SELECT ... FROM data_sources WHERE key='weibo_mediacrawler'` 返回空集，说明目标数据源尚未注册。

## 7. 前审计结论

1. 1A Runner 与 Collector 可以继续复用。
2. 不需要修改 `CollectorService`、`Scheduler`、`Opinion`、`CollectorRun` 或 `DataSource` 模型。
3. 本阶段应增加显式安全门 `MEDIA_CRAWLER_ENABLE_REAL_RUN`，默认关闭。
4. 数据源注册能力应保持手动、可审计、默认不启用且不纳入调度。
5. 本审计未修改数据库、模型、migration、Scheduler 或现有业务代码。
