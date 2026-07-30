# 《Phase BrightData-0 接入前架构审计报告》

审计日期：2026-07-30  
审计阶段：Phase BrightData-0 亮数据接入前架构审计  
审计方式：代码与文档只读检查

## 1. 审计范围

本次仅检查当前仓库中的采集器、数据源管理、统一入库链路、去重模型、任务运行记录、调度器、地域准入与密钥管理边界，并参考亮数据官方产品/API 文档。

本阶段未执行以下操作：

- 未修改代码、数据库、配置文件或前端页面
- 未新增依赖、环境变量或数据库迁移
- 未创建 `BrightDataCollector`
- 未执行生产采集
- 未调用真实亮数据 API

工作区在审计开始前已有大量用户未提交改动，本报告只读分析这些现状，不对其进行回滚或整理。

## 2. 当前采集架构

当前主链路如下：

```text
DataSource(enabled, class_path, config_json, scope_region_codes)
                    |
                    v
          Collector Registry
       import_class(class_path)
                    |
                    v
          BaseCollector.fetch()
                    |
                    v
             CollectorService
     去重 -> 地域准入 -> Opinion 入库
                    |
                    v
          RuleFallback / RiskEngine
                    |
                    v
             Event Aggregation
                    |
                    v
                 Alert
```

关键观察：

1. `BaseCollector` 的核心契约是实现 `fetch()` 并返回标准化字典列表。[base.py](C:/Users/Administrator/Desktop/YQ/backend/app/collectors/base.py:10)
2. Registry 使用 `class_path` 动态导入类，优先读取 `data_sources`，失败时才回退到内置默认源。[registry.py](C:/Users/Administrator/Desktop/YQ/backend/app/collectors/registry.py:163)
3. `CollectorService` 统一执行 `fetch -> 去重 -> Opinion -> 规则风险分析 -> CollectorRun`，单个采集器异常不会中断后续数据源。[service.py](C:/Users/Administrator/Desktop/YQ/backend/app/collectors/service.py:299)
4. 定时任务目前由 APScheduler 管理，主采集任务默认每 30 分钟执行一次；八爪鱼微博另有独立小时任务。[scheduler.py](C:/Users/Administrator/Desktop/YQ/backend/app/core/scheduler.py:31)

## 3. 亮数据接入可行性结论

| 项目 | 结论 |
|-|-|
| 技术可行性 | 高，约 8/10。亮数据可封装为新的 `BaseCollector` 实现 |
| 架构匹配度 | 高。同步模式可直接复用现有 `CollectorService` |
| 最小改造范围 | 新增专用采集器、非敏感配置映射、数据源记录、测试与日志 |
| 改造风险 | 中等。主要风险在异步任务、字段映射、增量语义、地域准入和费用控制 |
| 推荐程度 | 推荐作为补充型数据源，不建议替换稳定的本地/政府新闻采集器 |
| 第一阶段建议 | 先做同步或采集器内部“触发后轮询”的 POC，不引入 webhook、消息队列或 Redis |

亮数据官方资料显示，其 Web Scraper API 支持预构建 scraper、JavaScript 渲染、代理/反机器人处理、批量输入以及 JSON/NDJSON/CSV 等输出；异步接口返回 `snapshot_id`，可通过进度接口查询并下载结果。

参考：

- [亮数据网页爬虫工具](https://www.bright.cn/products/web-scraper)
- [Scraper async requests](https://docs.brightdata.com/api-reference/rest-api/scraper/asynchronous-requests)
- [Monitor progress](https://docs.brightdata.com/api-reference/scrapers/management-apis/monitor-progress)
- [Download snapshot](https://docs.brightdata.com/api-reference/scrapers/delivery-apis/download-snapshot)

## 4. 推荐接入方案

### 4.1 新增 `BrightDataCollector`

推荐新增：

```text
backend/app/collectors/brightdata_collector.py
```

其职责仅包括：

- 调用亮数据 REST API
- 处理同步响应，或在 `fetch()` 内完成受控的异步轮询
- 将供应商字段映射为系统标准字段
- 暴露必要的抓取统计信息和错误日志
- 不直接操作数据库

建议输出至少包含：

```text
title
content
url
publish_time
source
author
external_id
source_type
engagement（如有）
```

### 4.2 复用现有链路

以下组件可以直接复用，不需要为亮数据另建分析链路：

- `CollectorService`
- `Opinion`
- `OpinionRegionService`
- `OpinionAdmissionService`
- `RiskEngine`
- 事件聚合
- 预警评估

`CollectorService` 已在入库前完成统一字段读取和准入处理。[service.py](C:/Users/Administrator/Desktop/YQ/backend/app/collectors/service.py:394)

### 4.3 Registry 是否需要修改

核心 Registry 不需要修改。Registry 已支持通过数据库中的 `class_path` 动态导入，因此理论上只需：

```text
新增 BrightDataCollector 类
        +
新增 data_sources 记录
```

但是，当前数据源管理 API 对“专用型采集器”要求 `config_json` 为空；非空配置会被拒绝。[admin_data_sources.py](C:/Users/Administrator/Desktop/YQ/backend/app/api/admin_data_sources.py:582)

因此有两种落地选择：

- POC：亮数据的 dataset、输入 URL、字段映射均由环境变量或固定测试配置提供，数据源记录使用空配置。
- 正式接入：对专用采集器增加受控的非敏感配置白名单，或增加亮数据专用配置模型；不应把 API Key 放在 `config_json`。

## 5. 数据源管理审计

### 5.1 当前模型是否可以表达亮数据

`DataSource` 已有以下字段：

```text
key
name
type
class_path
enabled
priority
scope_region_codes
config_json
last_run_at / last_status / last_error
```

因此数据库层面可以表达：

```json
{
  "key": "brightdata_news",
  "type": "brightdata",
  "class_path": "app.collectors.brightdata_collector.BrightDataCollector",
  "config_json": {
    "dataset_id": "非敏感标识",
    "params": "非敏感请求参数"
  }
}
```

`type` 是字符串而非严格枚举，`brightdata` 可以作为新的类型值；真正的装配依据是 `class_path`。[data_source.py](C:/Users/Administrator/Desktop/YQ/backend/app/models/data_source.py:14)

### 5.2 config_json 与 API Key 风险

当前数据源序列化结果包含 `config_json`，管理接口和前端会读取它。[admin_data_sources.py](C:/Users/Administrator/Desktop/YQ/backend/app/api/admin_data_sources.py:216)

结论：

- API Key 不能存入 `config_json`
- API Key 不能写入数据库备份、任务结果、普通业务日志
- API Key 应只从运行环境读取，例如 `BRIGHTDATA_API_KEY`
- webhook 鉴权密钥应使用独立环境变量，例如 `BRIGHTDATA_WEBHOOK_SECRET`
- 日志中只能记录 dataset、snapshot、状态码和耗时，不能记录完整请求头或响应原文

## 6. CollectorService 链路审计

亮数据返回的新闻、搜索结果、社交内容均可以进入当前链路，但必须在采集器中完成字段映射。

| 亮数据语义 | Opinion / 系统字段 | 处理建议 |
|-|-|-|
| 标题、headline、name | `title` | 多候选字段，缺失时从正文生成短标题 |
| 正文、description、text | `content` | 必须保证非空；纯摘要应标记来源类型 |
| 页面地址、post URL | `url` | 保留规范化后的最终 URL |
| 发布时间 | `publish_time` | 统一时区和日期解析；无法解析时允许为空 |
| 作者、账号 | `author` | 可选 |
| 平台 ID、帖子 ID | `external_id` | 优先用于幂等去重 |
| 点赞、评论、转发 | `engagement` | 使用 JSONB，当前模型已支持 |
| 平台/内容类别 | `source_type` | 例如 `brightdata_news`、`social_post` |

统一入库代码会把这些字段写入 `Opinion`，然后继续风险评分和事件聚合。[service.py](C:/Users/Administrator/Desktop/YQ/backend/app/collectors/service.py:453)

当前 `Opinion` 已支持 `source_type`、`author`、`engagement`、`external_id`，因此同步 POC 不需要新增 Opinion 字段。[opinion.py](C:/Users/Administrator/Desktop/YQ/backend/app/models/opinion.py:94)

## 7. 去重机制审计

当前去重优先级大致为：

```text
(source_type, external_id)
        -> url
        -> title + publish_time（url 为空时）
```

代码位于 [service.py](C:/Users/Administrator/Desktop/YQ/backend/app/collectors/service.py:448)。数据库对非空 URL 还有唯一索引。[opinion.py](C:/Users/Administrator/Desktop/YQ/backend/app/models/opinion.py:128)

适用性判断：

- 新闻文章：基本适用，文章通常是新 URL
- 社交帖子：有稳定平台 ID 时适用
- 搜索结果：需保留稳定结果 ID 或规范 URL
- 主页、商品页、机构页：不完全适用，同一个 URL 内容更新可能被判定为重复

隐藏风险是“同 URL 内容更新”不会生成新的 Opinion。亮数据抓取的是页面当前状态，而不是天然的事件流；对动态页面必须在 POC 中验证增量语义。

建议：

- 第一阶段保留现有去重逻辑，不做全局去重重构
- POC 只选择有稳定文章/帖子 ID 的数据集
- 生产阶段再按 Bright Data 数据集类型增加内容哈希、版本号或来源级去重策略

## 8. CollectorRun 与任务状态审计

### 8.1 同步模式

当前链路可以直接支持：

```text
请求亮数据
    -> fetch() 返回记录
    -> CollectorService 入库
    -> CollectorRun 记录结果
```

`CollectorRun` 已记录开始/结束时间、抓取数、入库数、重复数、失败数、状态和错误信息。[collector_run.py](C:/Users/Administrator/Desktop/YQ/backend/app/models/collector_run.py:6)

同步 POC 不需要新增模型。

### 8.2 异步模式

亮数据异步模式是：

```text
trigger
    -> snapshot_id
    -> progress(starting/running/ready/failed)
    -> download snapshot
    -> 本地标准化入库
```

当前系统没有 `snapshot_id`、供应商任务状态、原始快照位置或 webhook 接收路由。当前也没有专门的外部任务表。

判断：

- 第一阶段：不新增模型，采集器内部受控轮询即可
- 生产阶段：建议增加 `collector_jobs` 或等价任务表，至少保存 `snapshot_id`、数据源、触发时间、状态、重试次数、结果位置和错误原因
- 不建议把 `snapshot_id` 塞入 `error_msg` 或其他业务字段

亮数据 webhook 要求公网 HTTPS 地址，并要求较快返回 200；当前应用路由均以 `/api` 统一挂载，未发现现成的第三方 webhook 入口。[main.py](C:/Users/Administrator/Desktop/YQ/backend/app/main.py:66)

## 9. 调度体系审计

当前主采集器由 `collector_main` 按 `collector_schedule_cron` 执行，默认每 30 分钟一次。[scheduler.py](C:/Users/Administrator/Desktop/YQ/backend/app/core/scheduler.py:153)

建议判断：

- 低频新闻/网页源：可以先复用每 30 分钟主任务
- 单 URL 或少量 URL：同步请求可以直接放入采集器
- 大批量异步任务：不应让 `fetch()` 长时间等待，避免阻塞同一批次其他数据源
- 需要独立频率、配额或并发限制时，再增加亮数据独立 schedule

第一阶段不必立即新增独立调度器；通过 `enabled`、`priority` 和一个专用数据源完成 POC 即可。生产阶段再按供应商配额设置来源级 cron、最大并发和每日预算。

## 10. 地域过滤兼容性审计

系统目标区域是河北廊坊及大厂。当前 `OpinionRegionService` 对全国源要求正文出现明确廊坊地域命中；有 `scope_region_codes` 的来源则可以使用来源范围作为默认区域。

亮数据可能返回全国范围的新闻、搜索或社交数据，存在两类风险：

- 过度过滤：全国内容未出现“大厂”等别名，但实际与目标事件相关，导致漏检
- 过度接纳：正文出现廊坊作为背景信息，但主体并非廊坊事件，导致误检

建议为 Bright Data 数据源显式增加来源级策略（设计字段，不在本阶段实施）：

```text
local_only       仅接收明确廊坊/大厂地域命中
national_filter  全国抓取后按地域词、主题词二次过滤
manual_mapping   按 scraper/站点配置地域映射
```

POC 应优先使用 `scope_region_codes=131028` 或明确的廊坊来源，不要一开始接入全国搜索结果全集。

## 11. 安全审计

必须采用以下边界：

```text
BRIGHTDATA_API_KEY       仅运行环境
BRIGHTDATA_WEBHOOK_SECRET 仅运行环境
dataset_id / URL / field_map 可作为非敏感配置
```

需要防护：

- 数据源接口返回 `config_json` 导致密钥前端泄露
- 异常日志打印 Authorization、完整请求 URL 或响应体
- webhook 未鉴权导致伪造采集结果
- webhook 重试造成重复入库
- Bright Data 侧处理公共网页数据可能涉及跨境传输、个人信息和目标站点条款，需在正式采购前完成合规审查

## 12. 最小实施范围

### 必须修改

- 新增 `BrightDataCollector` 专用类
- 增加亮数据响应到 Opinion 标准字段的映射
- 增加 API 超时、重试、状态码和配额错误日志
- 增加一个非敏感亮数据源配置
- 增加针对字段映射、异常、去重和地域准入的单元测试
- 将 API Key 放入环境变量，不进入数据库和前端

### 可选修改

- 对专用采集器开放受控的非敏感 `config_json`
- 增加来源级 schedule、预算和最大并发配置
- 增加内容哈希或来源级去重策略
- 增加原始响应落盘/对象存储能力

### 暂不建议

- 第一阶段引入 webhook
- 第一阶段新增消息队列、Redis、Celery、ES
- 为亮数据单独复制一套风险、事件或预警链路
- 用亮数据替换当前稳定的政府/新闻采集器
- 将完整原始 JSON 长期写入 `Opinion.content`

## 13. MVP POC 方案

第一阶段限定为单数据集、少量 URL、同步或采集器内部轮询：

```text
Bright Data API
      |
      v
BrightDataCollector.fetch()
      |
      v
CollectorService
      |
      v
Opinion -> Risk -> Event -> Alert
```

POC 输入：

- 选择一个亮数据已有 scraper 的目标站点
- 只配置 10～100 个测试 URL 或小规模参数
- 使用环境变量注入 API Key
- 输出仅保留系统需要的标准字段

POC 验收指标：

- API/任务成功率
- 标题、正文、URL、发布时间完整率
- 稳定外部 ID 覆盖率
- 重复率和同 URL 更新识别情况
- 地域准入通过率及误收/漏收样本
- 单条有效 Opinion 成本
- P95 抓取耗时是否低于当前调度窗口

第一阶段明确不引入：

- webhook
- 新任务系统
- 消息队列
- Redis
- ES

## 14. 后续生产增强建议

当 POC 证明目标数据集稳定且成本可接受后，再考虑：

- 异步 trigger 与 snapshot 生命周期管理
- `collector_jobs` 外部任务模型
- 公网 HTTPS webhook 与请求头鉴权
- webhook 快速确认、重试和幂等入队
- 原始快照对象存储与回放
- 来源级限流、预算、并发和熔断
- 供应商 SLA、配额和账单监控

这些是生产化增强，不是当前接入前审计阶段的必要条件。

## 15. 风险清单

| 风险 | 等级 | 说明 | 建议 |
|-|-|-|-|
| 成本风险 | 中 | 按请求/记录计费，重复抓取和大批量任务会快速放大成本 | POC 记录有效 Opinion 成本，设置每日预算和上限 |
| 数据质量风险 | 中 | 不同 scraper 字段结构不同，正文可能为空或只有摘要 | 建立字段完整率和样本验收门槛 |
| 字段映射风险 | 中 | title/content/date/id 字段名称不统一 | 配置化映射，缺失字段要有明确降级规则 |
| 地域过滤风险 | 高 | 全国结果与廊坊目标区域不天然一致 | 使用来源级地域策略和人工抽样复核 |
| 增量/去重风险 | 高 | 同 URL 更新可能被现有唯一索引判为重复 | POC 优先选择稳定帖子/文章 ID，生产再做版本化 |
| 第三方依赖风险 | 中 | API、数据集、配额、价格和可用性受供应商影响 | 保留现有采集器作为主链路和降级来源 |
| 异步交付风险 | 中 | snapshot 延迟、webhook 重试、大响应体可能导致任务积压 | 生产阶段增加 collector_jobs 和原始快照回放 |
| 安全/合规风险 | 高 | API Key、公共网页个人信息及跨境传输需要控制 | 密钥只放环境变量，正式采购前完成合规审查 |

## 16. 最终建议

结论：当前系统支持亮数据接入，且同步 POC 可以复用现有 CollectorService、Opinion、Risk、Event、Alert 全部主链路；Registry 核心无需修改。

建议进入 **Phase BrightData-1 开发**，但范围严格限定为：

1. 一个 `BrightDataCollector`
2. 一个已验证的亮数据 scraper/dataset
3. 少量测试输入
4. 标准字段映射、异常日志和单元测试
5. 环境变量密钥管理

Phase BrightData-1 不应包含 webhook、消息队列、Redis、ES 或全局去重重构。只有在 POC 证明数据质量、增量语义和成本满足要求后，才进入异步生产化设计。

