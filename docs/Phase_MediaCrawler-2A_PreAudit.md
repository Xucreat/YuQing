# Phase MediaCrawler-2A PreAudit Report

审计日期：2026-08-04（Asia/Shanghai）

## 1. Audit Scope

本报告是 MediaCrawler 进入生产 Collector 链路前的只读审计。

- 未修改业务代码、模型、Scheduler 或 MediaCrawler 外部仓库。
- 未执行 Alembic upgrade/downgrade/stamp。
- 未执行 INSERT、UPDATE、DELETE。
- 未注册 `data_sources.weibo_mediacrawler`。
- 未创建 Opinion、CollectorRun 或 Event。
- 未启动 Scheduler。

既有 Phase 1A-1K 的真实采样基线：batch `6219b053d3c045949b9cb77962cdb50b`，native raw JSONL 16 行，Runner 标准 output 10 行，数量控制和适配器回放已通过。该基线未在本阶段重新调用微博。

## 2. Current Architecture

```text
MediaCrawler native command
        |
        v
MediaCrawlerRunner
        |
        +--> raw/weibo.jsonl       (保留原始输出)
        +--> output/weibo.jsonl    (标准、受 max_items 限制)
        v
MediaCrawlerWeiboCollector.fetch()
        |
        v
CollectorService._process_collector()
        |
        +--> admission / 去重
        +--> Opinion
        +--> RuleFallbackProvider + RiskEngine
        v
EventAggregator（手动 Collector API 或 Scheduler 采集后调用）
        |
        v
Event / EventOpinion / Event heat
```

当前 CollectorService 实现位于 `backend/app/collectors/service.py`，不是 `backend/app/services/`。其主流程是 `collector.fetch()` -> admission/去重 -> Opinion -> 规则分析/RiskEngine；MediaCrawler Collector 不需要直接访问数据库。

## 3. Environment and Database Baseline

### MediaCrawler 环境

| 项目 | 结果 |
|---|---|
| `MEDIA_CRAWLER_ROOT` | PASS，`D:\code files\mediaCrawler\MediaCrawler` |
| `MEDIA_CRAWLER_ENTRY` | PASS，`main.py` 存在 |
| `MEDIA_CRAWLER_PYTHON` | PASS，MediaCrawler `.venv` Python 可执行；1J 记录版本 3.11.15 |
| `MEDIA_CRAWLER_BROWSER_DATA` | PASS，browser data 目录及 `wb_user_data_dir_manual` 已通过只读元数据检查 |
| real-run gate | PASS，真实运行只能通过显式人工确认和进程级开关开启 |
| MediaCrawler commit | `1779dde9725f6b7ef42e29022c0054b3e678f1af` |

### PostgreSQL 只读结果

```text
current_database = opinion_db
PostgreSQL       = 16.6
alembic_version   = p12_datasource_schedule
data_sources.key = 'weibo_mediacrawler' -> empty
```

只读核验同时确认全国 Region 哨兵 `000000`、廊坊市 `131000`、大厂县 `131028` 均存在。数据库没有本阶段写入。

## 4. Collector Compatibility

文件：`backend/app/collectors/media_crawler_weibo_collector.py`

适配器读取 JSONL 后要求正文非空，解析失败或重复行不返回给 CollectorService。标准返回项包含 `title`、`content`、`source`、`source_type`、`url`、`publish_time`、`external_id`、`author`、`engagement`。

| MediaCrawler 字段 | 系统字段 | 状态 | 审计结论 |
|---|---|---|---|
| `note_id` / `mid` / `id` | `external_id` | PASS | 作为微博平台 ID；缺失时退回 URL 或 title+时间去重 |
| `note_url` / `url` | `url` | PASS | 映射到 Opinion.url；空 URL 仍需服务层辅助去重 |
| `text` / `content` | `content` | PASS | 空正文被适配器判为无效 |
| `nickname` / `author` | `author` | PASS | 可空，写入社媒扩展字段 |
| `create_date_time` | `publish_time` | PASS* | 支持 ISO 和常见日期格式；当前会去掉 timezone，见风险 |
| `liked_count` | `engagement.likes` | PASS | 数字、逗号和单位值归一化为非负整数 |
| `comments_count` | `engagement.comments` | PASS | 归一化为非负整数 |
| `shared_count` | `engagement.reposts` | PASS | 归一化为非负整数 |

固定字段：`source="weibo"`、`source_type="weibo_post"`。标题缺失时使用正文首句，长度限制为 512 字符。

**Collector Compatibility 结论：** 数据形状与 `CollectorService.fetch()` 契约兼容；进入生产前仍需解决配置契约和时区语义问题，因此整体不是 READY。

## 5. Opinion Mapping Audit

`CollectorService._process_collector()`（约 `service.py:384` 起）将适配器结果映射如下：

| Opinion 字段 | 来源/处理 | 结果 |
|---|---|---|
| `title` | 适配器标题或正文首句 | PASS |
| `content` | 标准正文 | PASS，Opinion 非空约束满足 |
| `source` | `weibo`，为空时回退采集器名 | PASS |
| `source_type` | `weibo_post` | PASS，Opinion 可空字符串字段 |
| `external_id` | 微博 `mid`/`note_id` 等 | PASS，已有索引 |
| `url` | `note_url` 等 | PASS，已有非空 URL 部分唯一索引 |
| `publish_time` | 解析后的 `datetime` | PASS*，需统一时区策略 |
| `author` | `nickname` | PASS，可空 |
| `engagement` | likes/comments/reposts JSONB | PASS |
| `region_id` | OpinionRegionService 准入结果 | NEEDS DESIGN CHANGE | 全国/主题微博必须明确 national mode 或有效地域命中 |

Opinion 模型已经具备上述社媒字段，不需要新增列。`Opinion.region_id` 是 NOT NULL，因此一个没有地域命中、又没有显式 national mode 的全国微博条目不能进入 Opinion。

### 去重

服务层第一优先键为 `(source_type, external_id)`，其次为 URL，URL 为空时使用 `title + publish_time`。微博 `note_id` 适合作为 `external_id`，并且比 URL 稳定。

数据库层目前只有 `external_id` 普通索引，没有 `(source_type, external_id)` 唯一约束。URL 有非空部分唯一索引。服务层查询加上并发写入锁和 IntegrityError 兜底，但同一 external ID 的数据库级最终一致性仍依赖服务层。是否增加联合唯一约束应作为独立设计/迁移评审，不在本阶段实施。

### 时间

`parse_publish_time()` 会把带 offset 的 datetime 转成 naive datetime；Opinion 使用 SQLAlchemy `DateTime`，因此类型上可写入，但 offset 被丢弃，可能造成跨时区记录偏移。该问题不阻断离线 Adapter，但生产接入前应明确“统一 UTC”或“统一本地时区”的约定并补测试。

## 6. Risk/Event Impact

### RiskEngine

链路已存在且无需修改：

1. Opinion 创建后由 `RuleFallbackProvider` 产生基础情感、摘要、关键词和基础风险结果。
2. `RiskEngine.refine(title, content, sentiment)` 计算 `risk_score`、`severity_score`、`event_state`、`resolution_flag`、`risk_factors` 和 `risk_category`。
3. MediaCrawler 的 engagement 不作为 RiskEngine 核心输入，但会进入 OpinionAdmission 的互动加分逻辑。

结论：RiskEngine 核心逻辑无需 MediaCrawler 专用分支，PASS。

### Event

CollectorService 本身不在 `_process_collector()` 内直接创建 Event。手动 Collector API 在采集完成后调用 `auto_aggregate_after_collect()`；Scheduler 的采集任务也在采集后调用同一聚合入口。EventAggregator 使用 Opinion 的风险、关键词和发布时间完成聚合，EventHeatService 还会使用 engagement 计算热度贡献。

结论：现有 Event 流程可复用，PASS；需要在后续受控集成测试中验证“全国模式、无地域命中、单条高风险微博”的聚合结果。不得在本阶段修改 Event/Risk 流程。

## 7. DataSource Integration Proposal

当前 `data_sources.key='weibo_mediacrawler'` 为空，未注册。

已有字段足以承载基础接入：`key`、`name`、`type`、`class_path`、`enabled`、`schedule_enabled`、`schedule_interval_minutes`、`scope_region_codes`、`config_json`。建议后续人工评审时使用：

```json
{
  "key": "weibo_mediacrawler",
  "name": "微博（MediaCrawler）",
  "type": "social",
  "class_path": "app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector",
  "enabled": false,
  "schedule_enabled": false,
  "schedule_interval_minutes": 60,
  "scope_region_codes": null,
  "config_json": "{\"collection_mode\":\"national\",\"max_items\":10}"
}
```

这只是设计建议，没有执行写入。

### 已发现的配置契约问题

1. `collection_mode` 当前只允许 `regional` / `national`；既有注册工具写入的 `collection_mode=manual` 不符合 `source_config.py` 和 Admin API 校验。`manual` 应作为触发方式/运营策略，而不是 `collection_mode` 值。
2. 专用采集器 Admin API 只接受策略键和 `collection_mode`，不会接受用户示例中的 `collector`、`platform`、`keywords`、`enabled` 等混入 `config_json` 的字段。`enabled` 和 `schedule_enabled` 是 DataSource 顶层字段。
3. registry 会从构造参数中剥离 `max_items`，再通过 `collector.source_config` 注入完整配置；当前 MediaCrawlerWeiboCollector 构造后使用 `self.max_items`，没有回读 `source_config.max_items()`。因此上面的 `max_items` 设计值当前不能可靠成为生产运行限制。
4. `keywords` 应继续由现有监控关键词表经 `CollectorService.fetch(keywords=...)` 传入。若要求每个 DataSource 自己维护关键词列表，需要单独定义配置契约和读取路径，不能把未知字段直接塞入当前专用型 `config_json`。

上述问题需要代码/配置契约设计变更后再实施，且不需要立即新增数据库列。

## 8. Scheduler Compatibility

Scheduler 查询条件为：

```text
enabled = true
AND schedule_enabled = true
AND key <> 'weibo_octopus'
```

支持的是全局 cron 或 per-source `schedule_interval_minutes`/`next_collect_time`，没有 DataSource 级 `schedule_cron` 字段。MediaCrawler 可以复用现有 Scheduler，但必须先解决：

- 注册时显式 `enabled=false`、`schedule_enabled=false`，避免模型默认值 `true` 带来误启用。
- `max_items` 的配置读取和硬限制。
- national/regional 准入策略。
- 真实 crawler 的人工/进程级安全门不能被调度路径绕过。

只读时全局配置显示 `collector_schedule_enabled=true`、`collector_schedule_mode=per_source`、`alert_eval_enabled=true`；这不代表 MediaCrawler 已调度。由于目标 DataSource 不存在，MediaCrawler 当前不会成为 Scheduler 候选。结论：**MediaCrawler Scheduler 当前有效状态为 Disabled；全局 Scheduler 配置本身不是 Disabled。**

## 9. Migration Requirement Assessment

### 当前结论：不需要为基础接入新增 migration

现有 DataSource、Opinion、CollectorRun、Event 和 EventOpinion 结构已经覆盖基础字段和链路，目标 DataSource 查询为空，数据库版本为 `p12_datasource_schedule`。

### 需要单独评审但本阶段不实施的事项

- 是否为 `(source_type, external_id)` 增加数据库联合唯一约束。
- 是否允许 DataSource 级关键词覆盖、平台参数、登录 profile 标识和运行上限持久化。
- 是否需要保存 raw/native JSONL 的审计引用。

这些需求若被确认，才可能形成新的 schema/migration 阶段；不能在 2A PreAudit 中顺带实现。

## 10. Risks

| 等级 | 风险 | 影响 |
|---|---|---|
| High | `max_items` 进入 registry 后未被 MediaCrawler Collector 从 `source_config` 读取 | 生产上限可能失效，违反数量治理 |
| High | `collection_mode=manual` 与当前校验枚举冲突 | 既有注册 payload 无法通过 Admin API，或读取侧回退为 regional |
| High | 空 scope 的全国微博缺少明确 national mode 时会被地域准入拒绝 | 真实搜索结果可能全部无法进入 Opinion |
| Medium | 带 offset 的发布时间被转换为 naive datetime | 跨时区排序、事件时间窗口可能偏移 |
| Medium | external_id 无数据库联合唯一约束 | 并发边界下服务层去重仍需依赖锁和异常兜底 |
| Medium | MediaCrawler 是外部进程，登录态、超时、输出协议和原始文件生命周期需持续运维 | 可能产生成功退出但无可解析输出的运行 |
| Low | engagement 字段缺失或格式异常 | 影响准入加分和 Event heat，不影响 Opinion 基本字段落库 |

## 11. Test Audit

已有 Phase 1A-1K 定向回归测试基线为 `58 passed, 1 warning`，覆盖 native command、JSONL adapter、Runner 输出发现、real-run gate 和 1K 数量控制。

后续实现阶段建议新增：

- DataSource registry 与 `source_config.max_items()` 读取测试；
- `collection_mode=national` 与空/有效地域命中的 admission 测试；
- MediaCrawler JSONL 字段和时区解析测试；
- `(source_type, external_id)` 幂等/并发边界测试；
- Collector API 采集后 EventAggregator 的集成测试，使用回滚事务或隔离测试数据库；
- Scheduler 候选测试，明确 `enabled=false` 或 `schedule_enabled=false` 时不选中。

本阶段未新增测试，也未运行会触发业务写入的 CollectorService 集成流程。

## 12. Recommendation

**NEEDS DESIGN CHANGE**

理由不是数据库结构缺失，而是当前生产接入配置契约与 MediaCrawler 的运行上限/地域模式语义尚未闭合：

1. 先确定 `manual` 是触发类型而非 `collection_mode`，并采用合法的 `regional` 或 `national` 配置。
2. 明确 DataSource 关键词的唯一来源，优先复用现有监控关键词表。
3. 让 MediaCrawler Collector 从 registry 注入的 `source_config` 读取并执行 `max_items`，保持 Runner 作为最终硬限制。
4. 明确发布时间的时区规范，并补齐准入、去重和事件聚合测试。

完成上述设计确认后，再进入实现评审；本报告不批准生产 DataSource 注册或自动调度。

## Final Status

```text
Phase MediaCrawler-2A-PreAudit completed
Code Change: NO CHANGE
Database: NO CHANGE
Migration: NO CHANGE
Scheduler: Disabled for MediaCrawler (global scheduler config remains enabled)
DataSource: Not Registered
Report: docs/Phase_MediaCrawler-2A_PreAudit.md
Conclusion: NEEDS DESIGN CHANGE
```
