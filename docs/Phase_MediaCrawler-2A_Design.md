# Phase MediaCrawler-2A Design Report

设计日期：2026-08-05（Asia/Shanghai）

## 1. Design Scope

本阶段只完成 MediaCrawler 生产接入的设计收口，不实施功能。

- 不修改业务代码、模型、配置文件或 MediaCrawler 外部仓库。
- 不修改数据库，不执行 Alembic。
- 不注册 `weibo_mediacrawler`，不创建 Opinion、CollectorRun 或 Event。
- 不启动 Scheduler。

本设计基于 Phase MediaCrawler-2A-PreAudit 和 Phase 1A-1K 真实样本基线：batch `6219b053d3c045949b9cb77962cdb50b`，native raw 16 行，Runner output 10 行。

只读复核结果：

```text
Database: opinion_db
Alembic: p12_datasource_schedule
data_sources.key='weibo_mediacrawler': empty
Global collector scheduler config: enabled/per_source
MediaCrawler scheduler eligibility: disabled because DataSource is not registered
```

## 2. Current Problem Summary

PreAudit 暴露了四个需要在实现前闭合的问题：

1. `collection_mode=manual` 把采集范围和触发方式混在一起，且 `manual` 不是当前合法范围值。
2. registry 会剥离 `max_items` 后注入 `source_config`，但 MediaCrawler Collector 当前只使用构造参数，不能可靠读取 DataSource 配置中的上限。
3. 空地域范围的微博搜索结果需要明确是全国采集还是区域采集，否则 `Opinion.region_id` 的非空约束可能拒绝数据。
4. MediaCrawler 的时间字符串带有来源格式和可能的时区信息，现有适配器会丢弃 offset，系统尚未形成统一时间规范。

此外，当前系统没有 DataSource 级 `schedule_cron` 字段。已有调度能力是 `schedule_enabled`、`schedule_interval_minutes`、`next_collect_time`，以及全局 `collector_schedule_cron`。

## 3. DataSource Configuration Design

### 3.1 设计原则

采用现有 DataSource 顶层字段承载生命周期和调度状态，采用 `config_json` 承载 MediaCrawler 专属运行策略：

- 顶层 `enabled`：数据源是否允许被解析和人工触发。
- 顶层 `schedule_enabled`：是否进入自动调度候选。
- 顶层 `schedule_interval_minutes`：复用现有 per-source 调度频率。
- 顶层 `scope_region_codes`：regional 模式的实际地域代码。
- `config_json`：平台、关键词、数量上限、采集范围等 MediaCrawler 策略。

不新增 `trigger_mode`、`schedule_cron` 或 `regions` 数据库列。

### 3.2 推荐配置

推荐的 DataSource 顶层结构如下。这里只是设计，不执行 INSERT：

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
  "config_json": "{\"collector\":\"mediacrawler\",\"platform\":\"weibo\",\"keywords\":[\"大厂县\"],\"max_items\":10,\"collection_scope\":\"national\"}"
}
```

`enabled=false` 和 `schedule_enabled=false` 是生产接入初始状态的硬要求。后续生产启用必须是单独评审，不由本设计自动改变。

### 3.3 config_json 字段契约

| 字段 | 类型 | 来源 | 用途 | 是否持久化 |
|---|---|---|---|---|
| `collector` | string | DataSource 配置 | 固定为 `mediacrawler`，用于配置识别 | 是，建议固定校验 |
| `platform` | string | DataSource 配置 | 固定为 `weibo`，传给 native command builder | 是 |
| `keywords` | array[string] | DataSource 专属覆盖；为空时回退监控关键词表 | 形成 MediaCrawler 查询关键词 | 可选 |
| `max_items` | integer | DataSource 策略 | 单次最终标准输出上限，范围 1-20 | 是 |
| `collection_scope` | enum | DataSource 策略 | `regional` 或 `national` | 是 |
| `trigger_mode` | enum | 运行状态派生 | `manual` 或 `scheduler` | 不持久化 |
| `login profile` | path/secret | 运行环境配置 | 供真实 crawler 使用 | 不放入 config_json |
| `save_data_path` | path | Runner 运行时 | 每次运行的临时输出目录 | 不放入 DataSource |
| `get_comment` / `get_sub_comment` | boolean | 固定采集策略 | 生产微博主帖接入阶段均为 false | 可固定在代码/命令策略 |

关键词规则：`keywords` 非空时作为该 DataSource 的查询覆盖；未配置或为空时，使用现有监控关键词表传入的关键词。不能同时存在两个未定义优先级的关键词来源。实施时必须在适配器或配置解析层明确该优先级，并记录有效关键词来源。

`login profile`、Cookie、token、session 和 browser data 内容不得进入数据库、日志或 API 响应。

### 3.4 兼容现有配置系统

当前专用型 DataSource Admin 校验只接受策略键和 `collection_mode`，因此推荐配置需要先完成配置契约扩展：

- 允许 `collector`、`platform`、`keywords`、`collection_scope` 等 MediaCrawler 专用键；
- 仍拒绝未知键和非法类型；
- `enabled`、`schedule_enabled` 保持 DataSource 顶层字段，不重复放入 `config_json`；
- 读取侧可接受旧的 `collection_mode` 作为过渡别名，但只允许 `regional`/`national`；
- `collection_mode=manual` 必须拒绝，不得静默回退。

## 4. Trigger and Scope Separation

### 4.1 collection_scope

`collection_scope` 描述“采集结果的地域准入语义”：

- `regional`：只接受指定地域范围；必须有非空、有效的 `scope_region_codes`。
- `national`：不要求地域范围；`scope_region_codes` 必须为空、NULL，或由兼容层规范化为空。

它不表示人工还是自动触发。

### 4.2 trigger_mode

推荐不把 `trigger_mode` 写入 `config_json`。原因是现有系统已经有等价的生命周期和运行状态字段：

| 语义 | 现有字段/来源 |
|---|---|
| 数据源是否可用 | `DataSource.enabled` |
| 是否进入 Scheduler | `DataSource.schedule_enabled` |
| 自动运行频率 | `schedule_interval_minutes` + `next_collect_time` |
| 本次实际触发类型 | `CollectorService` 的 `trigger_type` / `CollectorRun.trigger_type` |

有效触发方式派生规则：

```text
enabled=false                         -> disabled
enabled=true, schedule_enabled=false  -> manual
enabled=true, schedule_enabled=true   -> scheduler eligible
```

管理员手动触发不应被 `schedule_enabled=false` 阻止；该字段只控制自动调度候选。若未来 API 需要显示 `trigger_mode`，应返回派生值，而不是读取一个可能与 `schedule_enabled` 冲突的 JSON 字段。

如果业务最终要求配置文件中显式保存 `trigger_mode`，则必须增加一致性校验：`manual` 只能对应 `schedule_enabled=false`，`scheduler` 只能对应 `schedule_enabled=true`。本设计不推荐该重复真相方案。

## 5. max_items Flow Design

### 5.1 目标链路

```text
DataSource.config_json.max_items
        |
        v
CollectorRegistry / DataSourceConfig
        |
        v
MediaCrawlerWeiboCollector.source_config
        |
        v
MediaCrawlerRunner.run(max_items=N)
        |
        +--> MediaCrawlerCommandBuilder(..., max_items=N)
        +--> preserve raw native JSONL
        +--> write bounded output/weibo.jsonl
```

### 5.2 各层职责

1. **DataSource**：保存 1-20 的配置值，不保存运行时输出路径。
2. **CollectorRegistry**：解析 JSON，保留完整 `DataSourceConfig`；允许策略键被剥离出构造参数，但必须确保它们可从 `collector.source_config` 读取。
3. **MediaCrawlerWeiboCollector**：在 `fetch()` 开始时从 `source_config.max_items(default)` 解析最终 N；只负责把 N 传给 Runner，不自行切片 JSONL。
4. **MediaCrawlerRunner**：是数量治理的唯一最终控制点。校验 `1 <= N <= 20`，保留 native raw 文件，并把标准 output 限制为前 N 条非空 JSONL 行。
5. **MediaCrawlerCommandBuilder**：把 N 传给 native `--crawler_max_notes_count`，用于减少上游工作量，但不能被视为最终安全限制。

### 5.3 数量语义

当 native 返回 16 行、`max_items=10` 时：

```text
raw_count    = 16
raw JSONL    = 全量保留，不覆盖、不删除
output_count = 10
output JSONL = output/weibo.jsonl，最多 10 行
Collector    = 只读取标准 output，不再二次截断
```

因此 Adapter 不承担数量控制职责，Runner 是唯一最终硬限制位置。`max_items` 缺失、非整数、小于 1 或大于 20 时应在进入 subprocess 前拒绝；生产接入不允许“缺失即无限制”。

### 5.4 失败和审计要求

- native 非零退出、超时或无 JSONL：运行失败，不使用 fixture 降级。
- raw 与 output 路径分别记录在运行结果和日志摘要中。
- 日志只记录数量、路径、退出码、脱敏 stderr，不记录 browser data 内容。
- `raw_count`、`output_count`、adapter valid/invalid/duplicate 统计必须区分，避免把上游数量和最终输出数量混为一谈。

## 6. Regional/National Rule

### 6.1 配置校验

建议新增 MediaCrawler 配置归一化层，但复用已有 `validate_data_source_config` 的模式校验能力：

```text
collection_scope missing
    -> reject for MediaCrawler production registration

collection_scope=regional
    -> scope_region_codes required and non-empty
    -> each code must exist in regions
    -> normalize to internal collection_mode=regional

collection_scope=national
    -> scope_region_codes must be empty/NULL
    -> national Region sentinel must exist
    -> normalize to internal collection_mode=national

other value, including manual
    -> reject before registry or subprocess
```

`scope_region_codes` 是现有 DataSource 字段；本设计不新增 `regions` 列。若需要兼容已有 `scope_region_codes="ALL"`，只在读取归一化为 national，不将 `ALL` 作为新的 canonical 值。

### 6.2 与现有准入逻辑的关系

现有 OpinionRegionService 已支持显式 `collection_mode=national`，并使用 `000000` 全国 Region 哨兵承载无地域命中的 Opinion。设计实施时把 `collection_scope` 映射为现有内部模式即可：

- regional 走现有范围默认地域和地域命中逻辑；
- national 允许无地域命中，并使用全国哨兵；
- 两种模式都继续经过 OpinionAdmissionService，不绕过主题、风险和噪声准入。

## 7. Timezone Standard

### 7.1 存储规范

系统数据库现有 `Opinion.publish_time`、Event 时间字段为 timezone-naive `DateTime`。为保持现有模型不变，统一约定：

> 数据库存储值为 UTC 的 naive datetime。所有写入前必须已经完成 UTC 转换。

### 7.2 Collector 转换位置

转换应发生在 MediaCrawler Adapter 的标准化边界，不能让 CollectorService 为不同来源写特殊判断：

1. 带 timezone offset 的字符串：解析为 aware datetime，转换为 UTC。
2. 无 offset 的 MediaCrawler `create_date_time`：按 MediaCrawler 微博输出协议解释为 `Asia/Shanghai`，再转换为 UTC。
3. 转换完成后，在写入现有 naive `DateTime` 前去掉 tzinfo，但保留 UTC 的时钟值。
4. 空值、非法格式：返回 NULL，并在质量统计中计数；不得用当前时间伪造发布时间。

示例：

```text
2026-08-05 20:00:00+08:00 -> 2026-08-05 12:00:00 (UTC naive)
2026-08-05 20:00:00        -> 先按 Asia/Shanghai 解释，再得到同样 UTC 值
```

### 7.3 API 展示位置

API 序列化层负责把数据库 UTC 值标识为 UTC，并按现有前端约定转换为 `Asia/Shanghai` 展示。推荐 API 对外返回带 offset 的 ISO 8601 字符串，避免前端把 naive 值误读为本地时间。

EventAggregator、排序和时间窗口只消费已规范化的 UTC 值，不再自行猜测来源时区。实施时必须添加带 offset、无 offset、NULL 和非法时间的测试。

## 8. Collector Integration Design

### 8.1 目标链路

```text
MediaCrawler native process
        |
        v
native save_data_path/weibo/jsonl/*.jsonl
        |
        v
MediaCrawlerRunner
  raw preservation + output limit + timeout
        |
        v
MediaCrawlerWeiboCollector.fetch()
  standard Opinion payload + scope/keyword config resolution
        |
        v
CollectorService
  admission -> dedup -> Opinion
        |
        v
RuleFallbackProvider / RiskEngine
        |
        v
EventAggregator -> Event / EventOpinion / heat
```

### 8.2 复用模块

- `MediaCrawlerCommandBuilder`：复用原生 argv 列表协议，禁止 shell 字符串拼接。
- `MediaCrawlerRunner`：复用 real-run gate、timeout、stderr 脱敏、native output discovery、raw/output 分离。
- `MediaCrawlerWeiboCollector`：复用 JSONL 标准化和字段映射。
- `CollectorService`：复用 fetch、admission、去重、Opinion 创建和规则分析流程。
- `OpinionAdmissionService`、`RiskEngine`、`EventAggregator`：复用既有逻辑，不增加微博专用分支。

### 8.3 需要在实施阶段调整的边界

- 配置读取层需要将 `collection_scope` 归一化为现有内部 `collection_mode`。
- MediaCrawler Collector 需要从 `source_config` 读取 `max_items` 和可选关键词覆盖。
- `publish_time` 需要在适配器边界完成 UTC 规范化。
- CollectorService 不应被改成直接调用 MediaCrawler；它只接收标准 Collector payload。

不允许 `collect_and_analyze()` 被人工真实验证脚本调用来替代离线链路验证；生产集成测试必须使用隔离数据库或回滚事务。

## 9. Scheduler Compatibility

### 9.1 现有调度字段

当前 DataSource 没有 `schedule_cron` 字段。已有能力为：

- `enabled`
- `schedule_enabled`
- `schedule_interval_minutes`
- `next_collect_time`
- 全局 `collector_schedule_cron`
- `collector_schedule_mode=per_source` 时的 tick 派发

因此不重复设计 DataSource 级 `schedule_cron`。

### 9.2 trigger_mode=scheduler 的未来实现

未来允许调度时，`trigger_mode=scheduler` 的有效条件应是：

```text
DataSource.enabled = true
DataSource.schedule_enabled = true
next_collect_time is NULL or <= now()
```

调度使用现有 `schedule_interval_minutes` 推进 `next_collect_time`，并以 `trigger_type="scheduled"` 记录运行来源。人工运行使用明确的手动触发接口和 `trigger_type="manual"`，不依赖调度字段。

Scheduler 不得绕过：real-run gate、max_items、timeout、登录态检查和 native JSONL 输出检查。首次生产注册建议仍保持 `schedule_enabled=false`，经过人工稳定性观察后再单独评审自动调度。

### 9.3 与全局 cron 的关系

全局 `collector_schedule_cron` 只决定 Scheduler 何时运行，不为 MediaCrawler 增加新的 per-source cron 语义。per-source 模式下，源级频率仍由 `schedule_interval_minutes` 决定。若未来需要不同 cron 表达式，必须另行评估模型字段和 migration，不能把 `schedule_cron` 随意塞进当前 DataSource 配置后宣称已受支持。

## 10. Migration Assessment

### 情况 A：只使用 config_json

推荐方案不需要 migration：

- 现有 DataSource 已有 `config_json`；
- 现有顶层字段已覆盖 enabled、schedule、scope_region_codes；
- Opinion 已有 social fields、engagement、external_id；
- Event/Risk 链路不需要新列。

需要的是代码级配置解析、校验和 Collector 读取改造，以及测试；这些不等同于 schema migration。

### 情况 B：新增 DataSource 字段

只有在以下需求被确认时才需要 migration：

- 强制把 `collection_scope` 作为 DataSource 独立列；
- 强制把 `trigger_mode` 作为持久状态列；
- 引入 DataSource 级 `schedule_cron`；
- 保存独立的关键词表、登录 profile 引用或 raw 文件审计引用。

本设计不推荐新增这些字段。`trigger_mode` 可由现有字段派生，`collection_scope` 可由 config_json + `scope_region_codes` 表达，调度频率可复用现有 interval。

另一个独立议题是 `(source_type, external_id)` 数据库联合唯一约束。它不是本次接入必需字段，但若要求数据库级并发幂等，需要单独 migration 设计和存量重复数据审计。

## 11. Implementation Plan

### Phase MediaCrawler-2A-Implementation-1：配置契约与归一化

**修改范围：** `backend/app/collectors/source_config.py`、`backend/app/collectors/registry.py`、`backend/app/api/admin_data_sources.py`、MediaCrawler registration helper、对应测试。

**内容：**

- 增加 MediaCrawler 专用配置 schema 校验；
- 支持 `collection_scope`，拒绝 `collection_mode=manual`；
- 校验 keywords、max_items、platform；
- 保证 `max_items` 和 scope 进入 `source_config`；
- 保持 `enabled=false`、`schedule_enabled=false` 的注册默认值。

**风险：** 专用型 DataSource 校验规则变宽后可能误放未知键。

**验收：** 合法配置通过；未知键、非法 scope、空 regional scope、max_items 越界均在 subprocess 前拒绝；现有数据源测试不回归。

### Phase MediaCrawler-2A-Implementation-2：Collector/Runner 参数与时间规范

**修改范围：** `backend/app/collectors/media_crawler_weibo_collector.py`、必要时 `mediacrawler_runner.py` 和共享时间解析工具、native command/adapter 测试。

**内容：**

- Collector 从 `source_config` 解析 max_items 和关键词优先级；
- Runner 保持 raw/output 分离和唯一最终数量限制；
- Adapter 将 MediaCrawler 时间统一转换为 UTC naive；
- 保持 fixture、mock、native output discovery 和 real-run gate 兼容。

**风险：** 时间转换可能改变历史 fixture 的预期值；必须显式更新测试样例语义，不得静默改变生产历史数据。

**验收：** 1J/1K JSONL 回放通过；raw_count 与 output_count 分离；N=1、N=20、N 越界和 timezone 场景通过。

### Phase MediaCrawler-2A-Implementation-3：隔离 Collector 链路验证

**修改范围：** 集成测试和只读/回滚验证工具；不触碰生产 DataSource。

**内容：**

- 用内存 DataSource 对象或隔离测试数据库验证 registry -> Collector -> CollectorService；
- 验证 national/regional 准入、external_id 去重、Opinion 字段映射、RiskEngine 和 EventAggregator；
- 真实 MediaCrawler 只允许沿用已审批的人工小样本入口。

**风险：** CollectorService 会创建 Opinion/CollectorRun，不能对生产数据库执行；必须使用隔离数据库或完整回滚事务。

**验收：** 无 fixture 冒充；真实 JSONL 与标准 payload 一致；测试数据库无残留写入；事件聚合结果可解释。

### Phase MediaCrawler-2A-Implementation-4：生产注册评审

**前置条件：** 上述三个实施阶段通过，且真实样本、配置、时区、准入和数量控制均有记录。

**初始边界：** 仅允许显式注册为 `enabled=false`、`schedule_enabled=false` 的 DataSource；不自动开启 Scheduler。生产启用和自动调度应拆为后续审批阶段。

## 12. Final Recommendation

**READY FOR IMPLEMENTATION**

设计已收口，推荐方案如下：

1. 不新增数据库字段或 migration；使用现有 DataSource 顶层字段和 `config_json`。
2. 用 `collection_scope=regional/national` 表达范围，禁止 `collection_mode=manual`。
3. 不持久化 `trigger_mode`；由 `enabled`、`schedule_enabled` 和运行时 `trigger_type` 派生。
4. 让 Collector 从 `source_config` 读取 `max_items`，由 Runner 保持唯一最终输出硬限制。
5. 统一将 MediaCrawler 时间转换为 UTC，再写入现有 naive DateTime；API 层负责带时区展示。
6. 首次 DataSource 注册保持关闭，不进入 Scheduler，待隔离链路和人工采样验收后另行评审。

本结论只批准进入后续实现阶段，不批准当前生产 DataSource 注册、生产数据写入或自动采集。

## Final Status

```text
Phase MediaCrawler-2A-Design completed
Code Change: NO CHANGE
Database: NO CHANGE
Migration: NO CHANGE
Scheduler: Disabled
DataSource: Not Registered
Report: docs/Phase_MediaCrawler-2A_Design.md
Conclusion: READY FOR IMPLEMENTATION
```
