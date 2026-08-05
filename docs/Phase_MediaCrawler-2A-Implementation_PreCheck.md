# Phase MediaCrawler-2A Implementation PreCheck

检查日期：2026-08-05（Asia/Shanghai）

## 1. Check Scope

本次只读实施前检查未修改代码、数据库、配置或 MediaCrawler 外部仓库，未执行 Alembic，未注册 DataSource，未启动 Scheduler，未调用真实微博。

## 2. Current Database/DataSource Schema

只读确认：

```text
Database: opinion_db
Alembic: p12_datasource_schedule
data_sources.key='weibo_mediacrawler': 0 rows
```

现有 `DataSource` 字段已具备：

- `key`, `name`, `type`, `class_path`
- `enabled`
- `schedule_enabled`
- `schedule_interval_minutes`
- `next_collect_time`
- `scope_region_codes`
- `config_json`

没有新增字段的必要，但当前 Admin 专用 DataSource 校验只允许策略键和 `collection_mode`，还不接受本阶段要求的 `collector`、`platform`、`keywords`、`collection_scope`。

关键 Opinion schema 事实：

```text
opinions.region_id -> regions.id
nullable = false
```

`Opinion.region_id` 是 NOT NULL 外键，不能保存 `None`。

## 3. Collector Registry Loading Flow

当前 registry 流程：

```text
DataSource.config_json
        |
        v
registry._parse_config()
        |
        v
registry._split_strategy_keys()
        |  max_items/filter_mode/keyword_scope 被从构造参数剥离
        v
collector = cls(**remaining_config)
        |
        v
registry._attach_meta()
        |  注入 scope_region_codes、data_source_key、完整 source_config
        v
MediaCrawlerWeiboCollector
```

这条链路能够承载配置，但 MediaCrawler Collector 当前尚未从 `source_config` 读取 `max_items`；它只使用构造参数中的 `self.max_items`。因此 Phase 2A 的配置读取改造尚未实施。

## 4. MediaCrawler Collector Lifecycle

当前 `MediaCrawlerWeiboCollector.fetch()`：

1. 清理关键词并去重；
2. 调用 `MediaCrawlerRunner.run()`；
3. 读取 Runner 标准 `output/weibo.jsonl`；
4. 将 JSONL 行转换为标准 payload；
5. 对无效正文和重复记录做 adapter 级解析统计；
6. 返回 `CollectorService` 可消费的 dict 列表。

当前没有 `items[:max_items]` 的 Adapter 二次数量切片；最终 output 数量由 Runner 控制。配置优先级和 `effective_max_items` 日志字段尚未实施。

## 5. Runner Quantity Control

Runner 当前已具备：

- `raw_output_path`
- `raw_count`
- `output_count`
- native JSONL discovery
- raw 文件保留
- bounded `output/weibo.jsonl`
- `max_items` 1-20 校验

当前 `MediaCrawlerRunResult` 尚未包含 `effective_max_items`。这是可独立实施的兼容性增强，不是本次阻断原因。

目标实现应保持：

```text
native raw JSONL
        |
        v
Runner raw preservation + bounded output
        |
        v
Adapter reads output only
```

## 6. Time Parsing Flow

当前 `media_crawler_weibo_collector.parse_publish_time()` 支持 ISO 和常见日期格式，但对带 offset 的 datetime 会直接去掉 `tzinfo`，没有先转换为 UTC。

因此：

```text
2026-08-04T12:00:00+08:00
```

当前实现不能保证产生语义正确的 UTC datetime。Phase 4 的 UTC 改造可以在 Adapter 边界完成，不需要修改 Opinion schema。

## 7. CollectorService and Region Flow

当前 CollectorService 流程为：

```text
collector.fetch()
  -> OpinionRegionService.decide()
  -> OpinionAdmissionService.evaluate()
  -> _already_exists()
  -> Opinion(region_id=region_decision.region_id)
  -> RuleFallbackProvider / RiskEngine
```

当前显式 `collection_mode=national` 且无地域命中时，`OpinionRegionService` 会查询全国哨兵 Region，并返回该 Region 的 id；它不会返回 `None`。这是为了满足 `Opinion.region_id` NOT NULL。

当前 national 无显式模式且无地域命中时会被拒绝，避免产生非法 Opinion。

## 8. Existing Test Baseline

执行命令：

```text
pytest tests/test_media_crawler_adapter.py \
tests/test_media_crawler_1b.py \
tests/test_media_crawler_1c.py \
tests/test_media_crawler_1d.py \
tests/test_media_crawler_1e.py \
tests/test_media_crawler_1f.py \
tests/test_media_crawler_1g.py \
tests/test_media_crawler_1h.py \
tests/test_media_crawler_1i.py \
tests/test_media_crawler_1j.py \
tests/test_media_crawler_1k.py -q
```

结果：

```text
58 passed, 1 warning in 4.47s
```

本阶段未新增 `test_media_crawler_2a.py`，因为实施在 PreCheck 后因硬约束冲突停止。

## 9. PreCheck Result

```text
Environment: PASS
DataSource schema: PASS
Registry flow: PASS with pending config extension
Collector lifecycle: PASS with pending config/time changes
Runner quantity control: PASS baseline
Time standard: NEED IMPLEMENTATION
National region_id contract: BLOCKED
Overall: BLOCKED
```

阻断详情见：`docs/Phase_MediaCrawler-2A-Implementation_Blocker.md`。
