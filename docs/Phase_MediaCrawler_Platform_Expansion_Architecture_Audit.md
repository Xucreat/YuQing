# Phase MediaCrawler Platform Expansion Architecture Audit

**Phase:** `MediaCrawler-Platform-Expansion-0-Architecture-Audit`  
**角色:** Senior Backend Architect  
**审计日期:** 2026-08-06  
**审计性质:** 只读架构审计与扩展方案设计  
**最终状态:** `ARCHITECTURE_PLAN_READY`

## 0. 约束与审计范围

本阶段只读取当前工作区代码、测试和既有 MediaCrawler 设计/验收文档，未执行以下操作：

- 未修改业务代码；
- 未修改数据库或 `DataSource`；
- 未修改 `.env`；
- 未修改 `Scheduler`；
- 未执行真实采集；
- 未执行数据库迁移；
- 未启动新的 MediaCrawler 进程；
- 未回滚或覆盖工作区中已有的用户改动。

当前工作区存在大量未提交改动。本报告以审计时实际文件内容为准，尤其以当前 MediaCrawler 生产灰度相关文件为准。

## 1. 执行摘要

### 1.1 总体判定

当前微博实现已经具备**多平台扩展所需的运行边界和业务闭环基础**，但还没有形成真正的平台无关的 `MediaCrawlerPlatformCollector` 架构。

更准确的结论是：

> **具备增量扩展能力，但不具备“复制一个微博类即可安全接入任意平台”的通用能力。**

已经可以复用的能力包括：

- `BaseCollector -> fetch() -> CollectorService -> Opinion` 的统一业务链路；
- `RuntimeFactory -> Runner -> subprocess` 的外部进程边界；
- 批次目录、JSONL、原始文件保留、日志和 metrics；
- manual/scheduler profile 分离；
- scheduler 批次级临时 profile 隔离；
- Registry 的动态类导入、配置注入和装配失败可见化；
- `CollectorRun` 的批次、状态、统计和错误审计；
- `Opinion` 已有社媒扩展字段和去重字段。

仍然写死微博语义的关键位置包括：

- `media_crawler_weibo_collector.py` 同时承担通用 JSONL 读取、字段标准化、微博映射和去重；
- `MediaCrawlerCommandBuilder` 固定 `platform=wb`、`crawler_type=search`，并拒绝其他平台；
- `MediaCrawlerRunner` 和 `MediaCrawlerBatchLocator` 固定使用 `weibo.jsonl`；
- `source_config.validate_data_source_config()` 固定只允许 `platform=weibo`；
- Registry 只在 `data_source_key == "weibo_mediacrawler"` 时注入 runtime factory；
- `CollectorService` 对 `weibo_mediacrawler` 做关键词轮询和特殊 `fetch()` 调用；
- MediaCrawler metrics 更新函数只认 `weibo_mediacrawler`；
- 评论跳过、日志文案和部分统计分支使用微博专用命名。

因此，建议的目标不是直接把 `MediaCrawlerWeiboCollector` 复制成五个新类，而是：

1. 抽出 `MediaCrawlerPlatformCollector` 共享生命周期；
2. 将平台差异收敛到 `PlatformSpec`、命令参数适配器和 `Normalizer`；
3. 保留 `MediaCrawlerWeiboCollector` 作为兼容薄壳，确保 `DataSource.id=40` 当前生产链路不被破坏；
4. 新平台采用显式配置和显式平台注册，不改变 `CollectorService`、`Scheduler`、`CollectorRun`、`Opinion` 的稳定契约。

### 1.2 数据库结论

本阶段及后续第一轮多平台接入**不需要数据库结构变化**：

- 不新增 `DataSource.platform`；
- 不新增 `DataSource.collector_type`；
- 不新增独立 `DataSource.source_type`；
- 不新增 `raw_data` 表；
- 不新增 `CollectorRun.platform`；
- 不新增 `Opinion.platform`。

建议复用：

```text
DataSource.key       = weibo_mediacrawler / xhs_mediacrawler / douyin_mediacrawler
DataSource.type      = social
DataSource.class_path= MediaCrawlerWeiboCollector 或 MediaCrawlerPlatformCollector
DataSource.config_json
                      = collector/platform/平台参数的版本化 JSON
Opinion.source       = weibo / xiaohongshu / douyin / kuaishou / bilibili / tieba
Opinion.source_type  = weibo_post / xhs_note / douyin_video / ...
Opinion.external_id  = 平台原始唯一 ID
Opinion.author       = 平台作者显示名
Opinion.engagement   = 平台原始互动统计 JSONB
```

## 2. 当前微博实现审计

### 2.1 Collector 类结构

当前结构：

```text
BaseCollector
    |
    +-- fetch() -> list[dict]
            |
            +-- MediaCrawlerWeiboCollector
                    |
                    +-- resolve keywords
                    +-- select runtime / profile
                    +-- invoke Runner
                    +-- read JSONL
                    +-- normalize Weibo row
                    +-- batch de-duplicate
```

证据：

- `backend/app/collectors/base.py:9-19`
- `backend/app/collectors/media_crawler_weibo_collector.py:164-197`
- `backend/app/collectors/media_crawler_weibo_collector.py:250-308`
- `backend/app/collectors/media_crawler_weibo_collector.py:315-416`

优点：

- Collector 不直接写数据库；
- `fetch()` 返回统一的 `list[dict]`；
- runtime、runner 和 normalization 已经与业务入库解耦；
- 支持 fixture、显式 runner 和 runtime factory 三种测试/运行边界；
- 当前生产类保持独立，便于微博链路观察和回滚。

限制：

- 类名、模块名、`source_name`、`data_source_key`、字段映射均绑定微博；
- JSONL 解析和平台字段映射没有分层；
- `_normalize_row()` 对 `note_id`、`note_url` 等候选字段已经出现跨平台字段名，但输出仍固定为微博；
- 评论判断在 `CollectorService`，而不是平台 normalizer 或统一内容类型协议中；
- Collector 对 `last_fetched_raw`、runtime profile cleanup 等运行态字段使用了隐式属性协议。

审计结论：**结构上可作为扩展起点，职责上需要拆分平台无关核心和微博策略。**

### 2.2 RuntimeFactory

当前 runtime 结构：

```text
MediaCrawlerRuntimeFactory
    |
    +-- config(trigger_type)
    |       +-- root
    |       +-- runtime path
    |       +-- profile path
    |       +-- Python executable
    |       +-- entry
    |       +-- timeout
    |       +-- login policy
    |       +-- real-run gate
    |
    +-- create_runner(trigger_type, batch_id)
            +-- profile readiness check
            +-- scheduler disposable profile
            +-- command factory
            +-- MediaCrawlerRunner
            +-- source lock
```

证据：

- `backend/app/collectors/mediacrawler_runtime.py:43-60`
- `backend/app/collectors/mediacrawler_runtime.py:141-198`
- `backend/app/collectors/mediacrawler_runtime.py:200-270`

可复用能力：

- manual 与 scheduler 使用同一个 Factory；
- scheduler 要求带 `batch_id`；
- scheduler 使用 disposable profile，不直接让浏览器写入持久模板；
- 真实运行通过 `real_run_gate` 显式控制；
- source lock 当前按 `source_key` 生成；
- profile readiness 为只读检查，应用层不负责偷偷创建登录态。

扩展风险：

- `source_key` 默认值仍是 `weibo_mediacrawler`；
- profile 目录目前只有 `manual/scheduler` 两级，未来多平台若共用同一 profile，可能造成 Cookie、Local Storage 和登录态串用；
- `login_type` 当前是 runtime 设置级策略，不是平台/数据源级显式策略；
- Factory 返回的 `MediaCrawlerRuntimeConfig` 没有平台字段和 artifact naming contract。

判定：**RuntimeFactory 的生命周期和隔离设计可以复用，但 profile、lock、artifact 命名需要平台维度化。**

### 2.3 Runner 创建流程

当前调用路径：

```text
Scheduler / Manual API
    -> CollectorService
    -> Registry
    -> _build_collector()
    -> MediaCrawlerRuntimeFactory(source_key=...)
    -> MediaCrawlerWeiboCollector
    -> _ensure_runtime(trigger_type, batch_id)
    -> create_runner()
    -> MediaCrawlerRunner.run()
    -> subprocess.run()
    -> native JSONL discovery
    -> raw JSONL preservation
    -> bounded JSONL
    -> collector normalization
```

证据：

- `backend/app/collectors/registry.py:158-172`
- `backend/app/collectors/media_crawler_weibo_collector.py:199-232`
- `backend/app/collectors/media_crawler_weibo_collector.py:272-308`
- `backend/app/collectors/mediacrawler_runner.py:297-527`

当前安全边界良好：

- 未提供 fixture、显式 command 或 command factory 时不会意外启动 MediaCrawler；
- `subprocess.run(..., shell=False)` 使用 argv；
- timeout、非零退出码、无输出、空 bounded output 都有明确异常；
- 原始产物和标准化产物同时保留；
- 日志对 token、cookie、password、browser data 做脱敏；
- 失败时默认保留 runtime profile，便于诊断。

当前平台耦合：

- Runner 的标准输出路径是 `output/weibo.jsonl`；
- native output discovery 默认查找 `weibo/jsonl`；
- raw path 是 `raw/weibo.jsonl`；
- Runner metrics 的 `collector` 值固定为 `mediacrawler`，但没有平台维度；
- command builder 对平台和 crawler type 做微博专用校验。

判定：**进程边界可复用，artifact contract 和 CLI contract 必须抽象。**

### 2.4 Registry 注册机制

当前 Registry 不是静态手工注册表，而是 DataSource 驱动的动态装配：

```text
data_sources.enabled
    -> enabled_sources()
    -> class_path
    -> import_class()
    -> parse config_json
    -> validate config
    -> split strategy keys
    -> instantiate collector
    -> attach scope_region_codes/data_source_key/source_config
```

证据：

- `backend/app/collectors/data_source_repository.py:19-41`
- `backend/app/collectors/registry.py:93-103`
- `backend/app/collectors/registry.py:141-172`
- `backend/app/collectors/registry.py:182-285`

现有能力：

- `class_path` 动态导入；
- `config_json` 解析失败不再静默回退；
- 装配失败进入 `ResolvedCollectors.failures`；
- `resolve_collectors_verbose()` 允许 `CollectorService` 写入失败的 `CollectorRun`；
- allowlist/exclude keys 由调用方控制；
- `source_config` 作为完整配置注入 collector，策略键不直接传给构造函数。

微博特化点：

- `_build_collector()` 只对 `data_source_key == "weibo_mediacrawler"` 注入 `MediaCrawlerRuntimeFactory`；
- Registry 只对微博类调用 MediaCrawler 专用配置校验；
- 新平台若继续沿用当前 generic import，而未加入统一识别，会被当成普通 Collector，失去 runtime/profile/gate 能力；
- `data_source_key` 是当前实际的插件身份，但平台类型没有独立的内部 registry。

判定：**注册机制已具备插件化骨架，但需要一个 MediaCrawler 专用平台 Registry，而不是继续增加微博字符串判断。**

### 2.5 DataSource `config_json` 设计

当前微博配置示例：

```json
{
  "collector": "mediacrawler",
  "platform": "weibo",
  "keywords": [],
  "max_items": 20,
  "collection_scope": "national"
}
```

证据：

- `backend/app/collectors/media_crawler_registration.py:14-24`
- `docs/Phase_MediaCrawler-Enable-2F-Production-Enable_Precheck.md:114-130`
- `backend/app/collectors/source_config.py:346-404`

设计优点：

- 业务配置已经放在 `DataSource.config_json`；
- `max_items`、`collection_scope`、`filter_mode`、`keyword_scope` 有统一读取入口；
- 配置验证发生在 API 和 Registry 两个边界；
- `.env`/settings 负责 runtime 路径、Python、登录默认值和 gate；
- 当前配置可以在不增加表字段的情况下表达数据源差异。

现有限制：

- 当前 validator 明确拒绝非微博平台；
- `MEDIACRAWLER_ALLOWED_KEYS` 位于 admin API，配置协议与平台实现分散；
- 缺少 config schema version；
- 缺少平台参数命名空间；
- 平台字段如果直接继续添加到顶层，未来会导致 whitelist 越来越宽；
- 不能把 Cookie、浏览器目录、密码、token 或任意命令行参数放进 `config_json`。

建议配置形态：

```json
{
  "schema_version": 1,
  "collector": "mediacrawler",
  "platform": "weibo",
  "crawler_type": "search",
  "keywords": [],
  "max_items": 20,
  "collection_scope": "national",
  "content_type": "post",
  "comments": {
    "enabled": false,
    "sub_comments": false
  },
  "platform_options": {
    "search_sort": "default"
  }
}
```

其中：

- `collector`、`platform`、`schema_version` 为通用必备键；
- `keywords`、`max_items`、`collection_scope` 为现有平台无关策略键；
- `content_type`、`comments` 为统一采集语义；
- `platform_options` 只能接受平台 Registry 白名单字段；
- 登录密钥、Cookie、profile 路径、Python 路径和 real-run gate 不进入 JSON；
- `field_map` 默认不开放给生产配置，避免把数据契约变成任意字符串解释器。

### 2.6 原始数据 normalization

当前微博 normalizer 将原始行映射为：

```text
content/text                -> content
title 或正文首句            -> title
mid/id/external_id/note_id  -> external_id
nickname/author             -> author
url/link/note_url           -> url
likes/like_count/...        -> engagement.likes
comments/comments_count     -> engagement.comments
reposts/repost_count/...    -> engagement.reposts
publish_time/created_at/... -> publish_time
固定                        -> source=weibo
固定                        -> source_type=weibo_post
```

证据：`backend/app/collectors/media_crawler_weibo_collector.py:380-416`

现有 normalizer 已经具备可复用的基础工具：

- 空值清洗；
- 首句标题回退；
- 互动数解析；
- 多种日期格式解析；
- UTC naive 统一；
- external id/url/content+publish_time 分层去重；
- JSONL 行级异常隔离。

但 `_normalize_row()` 不能直接作为多平台 normalizer：

- `source` 和 `source_type` 固定微博；
- 平台字段优先级不同；
- B 站互动统计通常嵌套在 `stat`；
- 抖音/快手可能使用 epoch seconds；
- 贴吧需要区分 thread/post/reply；
- 小红书的标题和正文语义不同；
- “评论是否作为 Opinion”不能由微博字符串判断。

判定：**应保留统一 `NormalizedItem` 语义，拆分平台字段提取器。**

### 2.7 Opinion 入库映射

当前 `CollectorService._process_collector()` 将标准化 item 映射到 `Opinion`：

```text
item.title           -> Opinion.title
item.content         -> Opinion.content
item.source          -> Opinion.source
item.url             -> Opinion.url
item.publish_time    -> Opinion.publish_time
item.source_type     -> Opinion.source_type
item.author          -> Opinion.author
item.engagement      -> Opinion.engagement
item.external_id     -> Opinion.external_id
```

随后复用：

- `OpinionRegionService`；
- `OpinionAdmissionService`；
- external id/url/title+publish_time 去重；
- `RuleFallbackProvider`；
- `RiskEngine`；
- `auto_aggregate_after_collect()`；
- 现有事件和预警链路。

证据：

- `backend/app/collectors/service.py:220-248`
- `backend/app/collectors/service.py:489-533`
- `backend/app/models/opinion.py:81-90`

这部分已经是较好的稳定边界。多平台接入不应让每个平台直接写数据库，也不应绕过 `CollectorService`。

需要统一的规则：

- `source` 是用户可见的平台来源；
- `source_type` 是内容种类，不是采集实现类；
- `external_id` 是平台原始稳定 ID；
- `engagement` 保留平台原始统计，但键名统一为 `likes/comments/reposts/views/shares`，缺失项为 `0` 或不写；
- 所有平台必须返回可审计 URL，无法生成时允许为空，但必须有 external id；
- comments/replies 默认不创建独立 Opinion，除非未来明确设计评论下钻模型。

### 2.8 CollectorRun 统计字段

当前 `CollectorRun` 已覆盖：

```text
batch_id
trigger_type
start_time / end_time
fetched_raw
upstream_total
upstream_returned
created
duplicate
analyzed
failed
acknowledged
unconfirmed
ack_status
comments_seen
comments_skipped
admission_filtered
status
error_msg
```

证据：`backend/app/models/collector_run.py:6-33`

这些字段足以覆盖第一轮多平台观测：

- 原始抓取量；
- bounded 输出量可存于 runtime metrics；
- 标准化后进入服务的数量可用 `fetched_raw`/返回项和 `created` 组合解释；
- 去重、准入过滤、分析失败；
- 评论识别和跳过；
- 运行状态和错误。

注意事项：

- `upstream_total`、`upstream_returned` 当前带有八爪鱼导出队列语义，不能在 MediaCrawler 平台上随意伪装成“平台总量”；
- MediaCrawler 平台建议将无对应意义的 upstream 字段保持 `NULL/0`；
- `comments_seen/comments_skipped` 可以作为统一内容类型统计，不应再命名为微博专用；
- 不能为了平台区分新增 `CollectorRun.platform`，平台可以由 `collector_name`、DataSource key 和当前 batch artifacts 追溯。

### 2.9 Profile isolation

当前隔离链路已经验证：

```text
persistent scheduler profile
    -> copy to runtime_profiles/<batch_id>
    -> MediaCrawler receives runtime profile
    -> successful normalization
    -> cleanup runtime profile

failure
    -> retain runtime profile for diagnosis
```

证据：

- `backend/app/collectors/mediacrawler_runtime.py:222-265`
- `backend/app/collectors/media_crawler_weibo_collector.py:300-308`
- `backend/tests/test_media_crawler_enable_2b_fix4.py:70-140`
- `docs/Phase_MediaCrawler-Enable-2E-Observation_Report.md:183-209`

当前结果：

- 持久 scheduler profile 在观察窗口内未被污染；
- runtime profile 使用 `batch_id`；
- 成功后清理；
- 失败后保留。

多平台扩展必须增加：

- 触发类型维度：manual/scheduler；
- 平台维度：weibo/xhs/douyin/kuaishou/bilibili/tieba；
- 可选账号/租户维度：未来如一平台多账号才引入；
- source lock 维度：至少使用 DataSource key，而不是只使用 platform；
- runtime artifact 维度：同一个 batch 不允许不同平台覆盖 `weibo.jsonl`。

推荐路径：

```text
runtime/mediacrawler/
  profiles/
    manual/
      weibo/
      xhs/
      douyin/
      kuaishou/
      bilibili/
      tieba/
    scheduler/
      weibo/
      xhs/
      douyin/
      kuaishou/
      bilibili/
      tieba/
  runs/<batch_id>/
    raw/<platform>.jsonl
    output/<platform>.jsonl
    config/<platform>.json
    metrics.json
    crawler.log
  runtime_profiles/<batch_id>/<platform>/
  locks/<data_source_key>.lock
```

为保护微博生产链路，当前 `weibo.jsonl` 路径可以在兼容阶段继续保留；平台化 Runner 再逐步切换到动态 artifact name。

## 3. 当前实现是否已经具备多平台扩展能力

### 3.1 分层判定

| 能力层 | 当前状态 | 结论 |
|---|---|---|
| 统一 Collector 接口 | 已有 | 可复用 |
| 统一 Service 入库链路 | 已有 | 可复用 |
| Opinion 社媒字段 | 已有 | 可复用 |
| CollectorRun 审计字段 | 已有 | 第一轮够用 |
| 外部进程边界 | 已有 | 可平台化 |
| profile isolation | 已有 | 需增加平台维度 |
| 动态 Registry | 已有 | 需增加 MediaCrawler platform registry |
| config_json | 已有 | 需版本化和平台白名单 |
| CLI command builder | 微博特化 | 必须抽象 |
| JSONL artifact 命名 | 微博特化 | 必须抽象 |
| normalization | 微博特化 | 必须拆分 |
| Service 特殊分支 | 微博/八爪鱼特化 | 需收敛为 capability protocol |

### 3.2 最终判断

**结论：部分具备。**

当前系统可以安全地继续扩展，但扩展前必须完成以下架构准备：

1. `MediaCrawlerPlatformCollector` 共享类；
2. 平台规格和 normalizer registry；
3. 平台化 command/artifact contract；
4. Registry 对所有 MediaCrawler collector 统一注入 runtime；
5. 将 MediaCrawler 专用 Service 分支从 `weibo_mediacrawler` 字符串判断改为能力协议；
6. 保留现有微博类路径和现有 DataSource 40 行为作为兼容入口。

## 4. 目标多平台架构

### 4.1 推荐目录结构

第一轮建议在现有目录下增量演进，避免一次性移动已在生产观察的微博文件：

```text
backend/app/collectors/
  base.py
  service.py
  registry.py
  source_config.py

  media_crawler/
    __init__.py
    contracts.py
    config.py
    platform_registry.py
    platform_collector.py
    command_builder.py
    runner.py
    runtime.py
    batch.py
    profile.py
    normalizers/
      __init__.py
      base.py
      weibo.py
      xiaohongshu.py
      douyin.py
      kuaishou.py
      bilibili.py
      tieba.py

  media_crawler_weibo_collector.py
    # 兼容薄壳：继承 MediaCrawlerPlatformCollector

  mediacrawler_runtime.py
    # 兼容导出或过渡代理
  mediacrawler_runner.py
    # 兼容导出或过渡代理
```

不建议立刻删除或重命名现有模块。原因是：

- `DataSource.id=40` 当前 `class_path` 指向微博类；
- 生产观察文档和 runtime fingerprint 已记录微博模块路径；
- 现有测试大量直接 import `MediaCrawlerWeiboCollector`；
- 先保留兼容路径可以降低生产回归范围。

### 4.2 类继承关系

```text
BaseCollector
    |
    +-- MediaCrawlerPlatformCollector
            |
            +-- MediaCrawlerWeiboCollector        # 兼容薄壳，保留现有 class_path
            +-- MediaCrawlerXhsCollector          # 可选薄壳
            +-- MediaCrawlerDouyinCollector       # 可选薄壳
            +-- MediaCrawlerKuaishouCollector     # 可选薄壳
            +-- MediaCrawlerBilibiliCollector     # 可选薄壳
            +-- MediaCrawlerTiebaCollector         # 可选薄壳
```

共享基类负责：

- 读取 `DataSourceConfig`；
- 解析有效关键词；
- 调用 runtime factory；
- 获取 run lock；
- 调用平台 command adapter；
- 读取/保留原始 JSONL；
- 调用平台 normalizer；
- 批次内去重；
- 暴露统一运行态 counters；
- 成功清理 runtime profile，失败保留；
- 返回 `CollectorService` 兼容的 `list[dict]`。

平台实现只负责：

- 平台 code；
- `PlatformSpec`；
- command 参数映射；
- native output discovery；
- normalizer；
- 平台内容类型和字段候选；
- 平台特定风险和错误分类。

### 4.3 统一数据契约

建议定义内部 `NormalizedItem`，对外仍返回普通 dict，避免直接改变 `CollectorService`：

```text
NormalizedItem
  title: str
  content: str
  source: str
  source_type: str
  url: str
  publish_time: datetime | None
  external_id: str
  author: str
  engagement: dict
  content_type: str | None
  is_comment: bool
  raw_platform: str
  normalization_warnings: list[str]
```

转换为现有 dict 时：

- `content_type` 可继续由 `OpinionAdmissionService` 生成；
- `is_comment` 映射为 `source_type` 或由 Service capability 判断；
- `raw_platform` 和 `normalization_warnings` 只进入日志/metrics，不新增数据库字段；
- `raw_platform` 必须与 `DataSource.config_json.platform` 一致，否则该行失败。

### 4.4 PlatformSpec

建议每个平台提供显式规格：

```text
PlatformSpec
  platform: weibo | xhs | douyin | kuaishou | bilibili | tieba
  cli_platform: wb | xhs | dy | ks | bili | tieba
  default_crawler_type: search
  default_content_type: post/note/video/thread
  artifact_name
  allowed_login_types
  allowed_options
  normalizer
  command_adapter
  supports_comments
  supports_sub_comments
```

平台 Registry 的职责：

- 根据 `platform` 查找 `PlatformSpec`；
- 校验平台参数；
- 返回 command adapter 和 normalizer；
- 拒绝未知平台；
- 不让 `config_json` 任意决定 Python module、shell command 或文件路径。

### 4.5 Registry 设计

建议分为两层：

```text
Application Registry
  data_sources.class_path -> collector class

MediaCrawler Platform Registry
  config_json.platform -> PlatformSpec
```

兼容装配规则：

1. 若 class_path 是现有 `MediaCrawlerWeiboCollector`，仍按现有逻辑装配；
2. 若 class_path 属于 `MediaCrawlerPlatformCollector` 家族，统一解析 `collector=mediacrawler`；
3. 通过 `issubclass()` 或明确 class capability 判断，而不是比较单个 data_source_key；
4. `source_key` 仍用于 DataSource 追踪、keyword cursor 和 lock；
5. `platform` 只用于平台行为选择；
6. 任何平台装配失败都进入现有 `ResolvedCollectors.failures`。

## 5. 是否需要数据库变化

### 5.1 不新增 `platform` 字段

不建议新增 `DataSource.platform`：

- `DataSource.key` 已经是稳定内部标识；
- 每个平台通常对应独立 DataSource 行；
- 平台是 Collector 配置语义，不是调度关系；
- `config_json.platform` 已可以表达平台；
- 新列会引入模型、迁移、API、前端和历史兼容成本。

推荐：

```text
DataSource.key  = douyin_mediacrawler
DataSource.type = social
config_json.platform = douyin
```

### 5.2 不新增 `collector_type` 字段

`CollectorRun` 当前已有：

- `collector_name`；
- `batch_id`；
- `trigger_type`；
- `status`；
- 统计和错误字段。

`CollectorService.collector_type` 是运行方式/兼容 API 返回语义，不应再与平台列重复。平台可通过：

```text
CollectorRun.collector_name
  -> DataSource.name
  -> DataSource.key
  -> config_json.platform
```

追溯。

### 5.3 不扩展 DataSource `source_type`

当前已经存在两个不同语义：

```text
DataSource.type
  = social / news_site / gov_site / search / rss

Opinion.source_type
  = weibo_post / weibo_comment / xhs_note / douyin_video / ...
```

不要在 DataSource 再引入同名或近义字段。否则会出现：

- 采集实现类型；
- 平台类型；
- 内容类型；
- 用户可见来源

四套相互重叠的命名。

### 5.4 不新增 `raw_data` 表

现有 runtime artifacts 已具备第一阶段原始数据审计能力：

```text
runtime/mediacrawler/runs/<batch_id>/raw/<platform>.jsonl
runtime/mediacrawler/runs/<batch_id>/output/<platform>.jsonl
runtime/mediacrawler/runs/<batch_id>/crawler.log
runtime/mediacrawler/runs/<batch_id>/metrics.json
```

第一轮多平台接入不需要把原始平台 JSON 全部写数据库。原因：

- 原始结构高度平台化；
- 写入数据库会放大存储和合规风险；
- 当前业务只需要标准化 Opinion；
- 批次产物已经能支持失败重放、字段审计和问题定位；
- 现有 `CollectorRun.batch_id` 已能关联运行结果。

只有在以下需求出现时，才重新评估 `raw_data` 存储：

- 需要跨服务器长期保留原始数据；
- 需要在线回放而不是文件回放；
- 需要原始字段检索；
- 需要多租户原始数据访问控制；
- 需要合规留存策略和自动归档。

### 5.5 数据库不变的前提

不新增数据库结构的前提是：

- `Opinion.source_type` 长度 32 足够容纳规范值；
- `Opinion.external_id` 长度 128 足够容纳各平台原始 ID；
- `Opinion.url` 长度 1024 足够容纳平台 URL；
- `Opinion.engagement` JSONB 允许平台差异；
- `CollectorRun` 当前状态和统计字段继续沿用；
- 原始文件生命周期、保留期和访问权限由 runtime 运维策略管理。

## 6. 六个平台接入设计

以下均为设计目标，不表示本阶段已接入或已执行真实采集。

### 6.1 微博

| 项目 | 设计 |
|---|---|
| config_json | `collector=mediacrawler`、`platform=weibo`、`crawler_type=search`、`keywords`、`max_items`、`collection_scope`、`comments.enabled=false` |
| CLI code | `wb` |
| 登录方式 | manual 可使用二维码或已准备的 profile；scheduler 使用持久 Cookie/profile，不允许交互式登录 |
| 标准字段 | `mid -> external_id`；`text/content -> content`；`nickname -> author`；`created_at/create_time -> publish_time`；`url -> url` |
| Opinion 映射 | `source=weibo`；`source_type=weibo_post`；评论默认只计数、不建 Opinion |
| 风险点 | 登录态过期、微博限流、搜索结果波动、关键词轮询造成样本偏差、评论与正文混合 |
| 测试方式 | 保留现有 fixture/adapter/runtime/profile isolation 测试；新增平台规格回归测试，确保 DataSource 40 class_path 和行为不变 |

微博是保护对象。任何平台化重构都必须先证明：

- `DataSource.id=40` 仍能由当前 class_path 装配；
- 当前 scheduler profile 不被修改；
- 现有 `CollectorRun` 统计口径不变；
- 现有回滚路径仍然有效。

### 6.2 小红书

| 项目 | 设计 |
|---|---|
| config_json | `platform=xhs`、`crawler_type=search`、`content_type=note`、`keywords`、`max_items`、`collection_scope`、`platform_options.search_sort` |
| CLI code | `xhs` |
| 登录方式 | scheduler 使用已登录 Cookie/profile；不允许在 scheduler 中依赖二维码或短信交互 |
| 标准字段 | `note_id -> external_id`；`note_url -> url`；`title/display_title -> title`；`desc/content -> content`；`nickname -> author`；`time/create_time -> publish_time` |
| Opinion 映射 | `source=xiaohongshu`；`source_type=xhs_note`；`engagement.likes/comments/reposts` |
| 风险点 | 笔记详情和搜索结果字段差异、图片笔记正文为空、登录态和风控、分享数可能不存在、时间字段格式不稳定 |
| 测试方式 | 文本笔记、无标题笔记、图片笔记、重复 note_id、缺失 URL、中文互动数和多时间格式 fixture；全部先走 mock runner |

小红书需将“标题缺失”视为正常情况，统一用正文首句生成标题，但必须在 metrics 记录 `title_fallback_count`。

### 6.3 抖音

| 项目 | 设计 |
|---|---|
| config_json | `platform=douyin`、`crawler_type=search`、`content_type=video`、`keywords`、`max_items`、`collection_scope`、`platform_options` |
| CLI code | `dy` |
| 登录方式 | scheduler 使用稳定 Cookie/profile；禁止将账号凭据写入 `config_json` |
| 标准字段 | `aweme_id/video_id -> external_id`；`desc/title -> content/title`；`author.nickname -> author`；`create_time` epoch 或字符串 -> `publish_time`；详情 URL -> `url` |
| Opinion 映射 | `source=douyin`；`source_type=douyin_video`；互动键统一为 likes/comments/shares/views |
| 风险点 | 签名/请求参数变化、动态接口、频率限制、视频描述为空或过短、时间戳单位秒/毫秒差异、短链与长链重复 |
| 测试方式 | epoch seconds/milliseconds fixture、短链和标准链接去重、无描述视频、作者缺失、嵌套统计字段、命令参数快照测试 |

抖音 normalizer 必须显式区分秒和毫秒，不能把所有整数直接交给通用日期解析。

### 6.4 快手

| 项目 | 设计 |
|---|---|
| config_json | `platform=kuaishou`、`crawler_type=search`、`content_type=video`、`keywords`、`max_items`、`collection_scope`、`platform_options` |
| CLI code | `ks` |
| 登录方式 | scheduler 使用独立快手 profile；不能与抖音或微博 profile 共用 |
| 标准字段 | `photo_id/video_id -> external_id`；`caption/title -> content/title`；`author_name/user_name -> author`；`timestamp/create_time -> publish_time`；详情 URL -> `url` |
| Opinion 映射 | `source=kuaishou`；`source_type=kuaishou_video`；互动统计统一为 likes/comments/shares/views |
| 风险点 | 字段命名和嵌套结构变化、短视频标题缺失、账号登录与验证码、地区/内容可见性、播放量可能为格式化字符串 |
| 测试方式 | nested author/stat fixture、中文单位解析、缺失标题回退、ID 优先去重、异常行隔离、profile 按平台隔离测试 |

快手和抖音可以共享“短视频内容”抽象，但不能共享字段路径和登录 profile。

### 6.5 B 站

| 项目 | 设计 |
|---|---|
| config_json | `platform=bilibili`、`crawler_type=search`、`content_type=video`、`keywords`、`max_items`、`collection_scope`、`platform_options` |
| CLI code | `bili` 或以当前 MediaCrawler 版本实际 CLI code 为准，由 PlatformSpec 固化 |
| 登录方式 | 搜索可先评估匿名；scheduler 若需要详情/评论则使用独立 Cookie/profile |
| 标准字段 | `bvid/aid -> external_id`；`title -> title`；`description -> content`；`owner.name -> author`；`pubdate -> publish_time`；`stat.view/like/reply/share -> engagement`；`arcurl -> url` |
| Opinion 映射 | `source=bilibili`；`source_type=bilibili_video` |
| 风险点 | 搜索结果与详情结果结构不同、BVID/AID 双 ID、播放量和点赞量层级嵌套、字幕/简介与正文语义不同、评论分页 |
| 测试方式 | BVID/AID 双 ID 去重、nested stat 映射、pubdate epoch、标题/简介为空、URL 生成、匿名模式和登录模式分开测试 |

B 站最适合首先只接视频正文，不把评论和弹幕混入 Opinion 主表。

### 6.6 贴吧

| 项目 | 设计 |
|---|---|
| config_json | `platform=tieba`、`crawler_type=search`、`content_type=thread`、`keywords`、`max_items`、`collection_scope`、`platform_options.forum` |
| CLI code | 以当前 MediaCrawler 平台 code 为准，由 PlatformSpec 管理 |
| 登录方式 | 先评估匿名搜索；需要更深详情时使用独立 scheduler profile |
| 标准字段 | `tid/pid -> external_id`；`title -> title`；`post_content/content -> content`；`author/user_name -> author`；`create_time -> publish_time`；帖子 URL -> `url` |
| Opinion 映射 | `source=tieba`；`source_type=tieba_thread`；回复默认只计数，不单独入库 |
| 风险点 | thread、post、reply 层级混合；同一主题多页重复；帖子标题和回复正文分离；论坛/吧名需要保留在 raw/log 或 content_type 语义中 |
| 测试方式 | tid/pid 去重、跨页重复、无标题回复、论坛字段、分页终止、时间格式和回复过滤测试 |

贴吧必须先确定“一个 Opinion 代表一个主题帖还是一个帖子回复”。第一轮建议只接主题帖，回复只计数。

## 7. 统一配置与安全边界

### 7.1 顶层配置白名单

推荐顶层白名单：

```text
schema_version
collector
platform
crawler_type
keywords
max_items
collection_scope
collection_mode
filter_mode
keyword_scope
content_type
comments
platform_options
```

禁止出现在 `config_json`：

```text
password
cookie
token
authorization
browser_data
profile_path
python_executable
entry
shell_command
command
```

### 7.2 登录配置

配置原则：

- login type 只能是枚举，不接受任意命令行；
- scheduler 不允许 `qrcode`、`phone`、`interactive`；
- profile 路径由 RuntimeFactory 根据 trigger + platform + source key 计算；
- credential 由部署环境或预置 profile 提供；
- 失败 profile 保留，但必须有保留期和访问权限；
- 日志只记录 login mode 和 profile fingerprint，不记录 Cookie 内容。

### 7.3 平台和 DataSource 的命名

建议稳定 key：

```text
weibo_mediacrawler
xhs_mediacrawler
douyin_mediacrawler
kuaishou_mediacrawler
bilibili_mediacrawler
tieba_mediacrawler
```

建议 platform enum：

```text
weibo
xhs
douyin
kuaishou
bilibili
tieba
```

建议 source_type：

```text
weibo_post
xhs_note
douyin_video
kuaishou_video
bilibili_video
tieba_thread
```

不要把 `mediacrawler` 放入 `Opinion.source_type`，因为它表示采集实现而不是内容种类。

## 8. 实施路线图

以下是后续实施设计，不是本阶段实施记录。

### Phase MediaCrawler-Platform-1：平台无关核心抽象

#### 目标

- 在不改变微博生产 DataSource 40 行为的前提下，抽出平台无关 Collector 核心；
- 建立 `PlatformSpec`、normalizer registry、平台化 artifact contract；
- 让 runtime/profile/lock 具备平台维度；
- 先只迁移微博到新核心，新增平台不进入生产。

#### 计划修改文件

新增或调整：

```text
backend/app/collectors/media_crawler/
backend/app/collectors/media_crawler_weibo_collector.py
backend/app/collectors/mediacrawler_runtime.py
backend/app/collectors/mediacrawler_runner.py
backend/app/collectors/mediacrawler_batch.py
backend/app/collectors/mediacrawler_command_builder.py
backend/app/collectors/registry.py
backend/app/collectors/source_config.py
backend/app/api/admin_data_sources.py
backend/app/collectors/service.py
backend/tests/test_media_crawler_adapter.py
backend/tests/test_media_crawler_2a.py
backend/tests/test_media_crawler_2d.py
```

不应修改：

```text
backend/app/models/data_source.py
backend/app/models/collector_run.py
backend/app/models/opinion.py
backend/app/core/scheduler.py
backend/alembic/versions/
```

#### 主要工作

- 新增 `MediaCrawlerPlatformCollector`；
- 让 `MediaCrawlerWeiboCollector` 变为兼容薄壳；
- 将 `normalize_keywords`、日期解析、互动数解析、JSONL 读取下沉到共享模块；
- 将微博字段映射放入 `normalizers/weibo.py`；
- command builder 从固定 `wb` 改为 PlatformSpec 驱动；
- artifact path 从固定微博文件名改为平台名，但对现有微博保留兼容路径；
- Registry 通过 MediaCrawler capability 统一注入 RuntimeFactory；
- 将 Service 中 `weibo_mediacrawler` 的 metrics 更新改为 capability 检查；
- 将关键词轮询 capability 化，避免所有平台都被迫使用微博轮询语义。

#### 风险

- 微博 class path 或构造参数变化导致 DataSource 40 装配失败；
- 旧测试依赖 `weibo.jsonl` 路径；
- Service 特殊分支迁移时可能改变 `CollectorRun` 统计；
- profile path 变化可能影响当前生产 profile。

#### 验收标准

- 不执行真实采集即可完成全部 fixture/unit/contract 测试；
- `DataSource.id=40` 的 class path 无需修改即可解析；
- 旧微博 JSONL fixture 的 normalized output 完全一致；
- `CollectorRun` 字段值和状态转换完全一致；
- Scheduler 不被修改，且其 allowlist 行为测试全部通过；
- manual/scheduler profile isolation 测试通过；
- 运行失败时 profile 保留、成功时 profile 清理；
- git diff 仅包含本阶段允许的代码和测试文件。

### Phase MediaCrawler-Platform-2：首批平台接入

#### 目标

- 接入小红书和 B 站，优先验证“不同内容模型”；
- 继续使用 fixture、mock subprocess 和隔离 profile；
- 不进入全量生产调度。

#### 计划修改文件

```text
backend/app/collectors/media_crawler/normalizers/xiaohongshu.py
backend/app/collectors/media_crawler/normalizers/bilibili.py
backend/app/collectors/media_crawler/platform_registry.py
backend/app/collectors/media_crawler/command_builder.py
backend/app/collectors/source_config.py
backend/app/api/admin_data_sources.py
backend/tests/test_media_crawler_platform_xhs.py
backend/tests/test_media_crawler_platform_bilibili.py
```

必要 fixture：

```text
backend/tests/fixtures/media_crawler/xhs.jsonl
backend/tests/fixtures/media_crawler/bilibili.jsonl
```

#### 风险

- 平台 CLI 参数可能与微博不一致；
- B 站字段嵌套和 ID 双轨；
- 小红书无标题/图片笔记导致正文质量不一致；
- 平台登录态与微博 profile 误复用；
- `source_type` 和去重策略选错导致跨平台误合并。

#### 验收标准

- 每个平台有独立 PlatformSpec 和 normalizer；
- 每个平台至少覆盖正常、缺字段、重复、异常行、日期和互动数 fixture；
- `source_type` 唯一且不与其他平台冲突；
- 同一平台重复记录按 external id 去重；
- 不同平台相同 external id 不被错误去重；
- profile、lock、artifact 均按 DataSource key 或 platform 隔离；
- `CollectorService`、`Opinion`、`CollectorRun` 没有新增平台专用分支；
- 不执行真实采集，不启用新的 DataSource。

### Phase MediaCrawler-Platform-3：短视频与贴吧接入及受控灰度

#### 目标

- 接入抖音、快手、贴吧；
- 建立平台级观测、失败分类、数据质量门槛；
- 仅在每个平台独立完成预审后进行单源受控灰度。

#### 计划修改文件

```text
backend/app/collectors/media_crawler/normalizers/douyin.py
backend/app/collectors/media_crawler/normalizers/kuaishou.py
backend/app/collectors/media_crawler/normalizers/tieba.py
backend/app/collectors/media_crawler/platform_registry.py
backend/app/collectors/mediacrawler_runtime.py
backend/app/collectors/mediacrawler_profile.py
backend/tests/test_media_crawler_platform_douyin.py
backend/tests/test_media_crawler_platform_kuaishou.py
backend/tests/test_media_crawler_platform_tieba.py
docs/Phase_MediaCrawler-Platform-*.md
```

#### 风险

- 短视频平台风控和签名变化；
- epoch 时间单位误判；
- 视频标题/描述质量低；
- 贴吧 thread/reply 混合导致 Opinion 膨胀；
- 多平台并发导致浏览器资源、profile 和锁竞争；
- 生产灰度出现平台间污染或 Scheduler 观察口径混淆。

#### 验收标准

- 每个平台独立通过 fixture、mock runner、command snapshot、normalizer contract、Service integration；
- 每个平台有独立 profile readiness 和 runtime profile cleanup 证据；
- 每个平台有独立 DataSource key 和禁用/回滚路径；
- `CollectorRun.status` 能区分 success/partial/warning/failed；
- 观察指标至少包括 fetched、created、duplicate、admission_filtered、failed、normalization warnings；
- 任何一个新平台失败不影响微博 `DataSource.id=40`；
- 灰度前后微博生产链路回归通过；
- 未经平台单独批准，不得将所有新平台一起加入 Scheduler allowlist。

## 9. 测试策略

### 9.1 静态与单元测试

- 配置 schema 校验；
- 未知 platform 拒绝；
- platform-specific options 白名单；
- login type 枚举和 scheduler 非交互约束；
- command argv 快照；
- artifact path 生成；
- profile path 生成；
- lock path 生成；
- 日期、互动数、ID、URL 解析；
- 标题回退；
- 评论/回复过滤；
- normalization warning 统计。

### 9.2 Fixture 测试

每个平台至少需要：

1. 正常记录；
2. 缺标题；
3. 缺正文；
4. 缺作者；
5. 缺 URL；
6. 缺 external id；
7. 日期为字符串；
8. 日期为 epoch；
9. 互动数为数字；
10. 互动数为中文单位；
11. 重复记录；
12. 非法 JSONL 行；
13. 评论/回复记录；
14. 平台字段嵌套结构。

### 9.3 Service 集成测试

使用 fake runner/fake DB 或独立测试库验证：

- 标准化 item 能进入现有 Opinion 映射；
- external id + source_type 去重；
- URL fallback 去重；
- admission filter；
- risk analysis；
- `CollectorRun` 统计；
- 单条分析失败不影响其他条目；
- collector exception 最终写 `status=failed`；
- 平台失败不影响同一批次其他平台。

### 9.4 运行隔离测试

- manual profile 和 scheduler profile 不相同；
- scheduler 使用 disposable profile；
- 成功后 disposable profile 清理；
- 失败后 disposable profile 保留；
- 原始 profile 文件 checksum 不变化；
- 两个平台不能共用同一个运行 profile；
- 两个 DataSource key 的 lock 不相互覆盖；
- batch artifact 不覆盖其他平台文件。

### 9.5 受控灰度测试

本阶段不执行。后续每个平台单独执行：

```text
fixture -> mock subprocess -> sandbox process -> read-only precheck
-> single DataSource canary -> observation -> rollback drill
```

不允许直接从微博生产成功推断其他平台可上线。

## 10. 主要架构风险与待决策项

### P0：微博生产兼容性

任何平台化修改都不能直接替换 DataSource 40 的 class path 或 production profile。建议保留 `MediaCrawlerWeiboCollector` 作为兼容类至少一个完整观察周期。

### P1：平台 profile 是否一平台一账号

当前设计按 platform 隔离。如果未来一个平台需要多个账号，不能继续把 profile 仅绑定 platform，应扩展为：

```text
trigger + platform + account_alias
```

本阶段不建议提前引入 account 表或数据库字段，可以先在部署 profile 目录和 DataSource key 中表达。

### P1：原始产物保留策略

当前 runtime raw JSONL 是文件审计方案，但尚未在本报告范围内定义长期留存、压缩、脱敏和清理任务。正式扩展前需要确定：

- 保留天数；
- 磁盘容量上限；
- 失败批次是否永久保留；
- 原始 Cookie/隐私字段是否需要二次脱敏；
- 谁可以读取 raw 目录。

### P1：平台 CLI 兼容性

MediaCrawler 上游平台参数、输出目录、字段名和登录行为可能变化。每个平台必须将：

- CLI code；
- crawler type；
- output discovery；
- login type；
- required fields

作为版本化 PlatformSpec，而不是散落在 normalizer 和 runner 的 if/else 中。

### P2：关键词轮询语义

当前微博已存在 `keyword_cursor`。未来不能默认所有平台都复用同一游标逻辑：

- 有的平台搜索接口按关键词分页；
- 有的平台每次返回固定热点集合；
- 有的平台更适合按关键词分批；
- 有的平台不允许高频切换关键词。

建议将 keyword rotation 作为可选 capability，由 PlatformSpec 声明。

### P2：评论和回复模型

第一轮多平台接入统一采用：

```text
正文/主题帖/视频 -> Opinion
评论/回复/子评论 -> 只计数或保留 raw，不创建 Opinion
```

只有在明确评论治理、事件关联和去重模型后，才扩展评论入库。

## 11. 建议的最终决策

1. **批准继续多平台扩展，但先实施 Platform-1 抽象，不直接复制微博类。**
2. **保持 `CollectorService`、`Scheduler`、`CollectorRun`、`Opinion` 不变。**
3. **保持 `DataSource.id=40` 和现有 `MediaCrawlerWeiboCollector` class path 兼容。**
4. **不新增数据库字段、不新增 raw_data 表。**
5. **以 `DataSource.key + config_json.platform + Opinion.source_type` 表达平台和内容类型。**
6. **以平台 Registry、Normalizer 和 Command Adapter 承载平台差异。**
7. **以 trigger/platform/source key 维度实现 profile、lock 和 artifact isolation。**
8. **每个平台独立测试、独立预审、独立灰度，不做一次性多平台上线。**

## 12. 最终状态

```text
ARCHITECTURE_PLAN_READY
```

本报告只完成架构审计和扩展方案设计，不代表任何代码、数据库、DataSource、Scheduler、环境变量或真实采集已经被修改或执行。
