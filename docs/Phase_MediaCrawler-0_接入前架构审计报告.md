# Phase MediaCrawler-0 接入前架构审计报告

审计日期：2026-08-04  
项目：河北省舆情监测系统  
审计性质：只读架构审计  
审计结论：当前系统具备接入 MediaCrawler 微博帖子的主链路能力；第一阶段不需要重写 `CollectorService`、`Scheduler` 或 `Opinion` 模型，但需要新增 MediaCrawler 适配器/运行器，并处理专用 Collector 的 `config_json` 白名单、运行环境和登录态管理。

## 1. 审计范围

本次仅阅读以下内容，未启动采集任务、未调用微博接口、未安装 MediaCrawler、未执行 Alembic migration、未修改业务代码、数据库、配置、Dockerfile 或 docker-compose。

- `backend/app/collectors/`
- `backend/app/models/`
- `backend/app/api/admin_data_sources.py`
- `backend/app/core/scheduler.py`
- `backend/app/core/config.py`
- `backend/app/services/`
- `frontend/src/views/Sources.vue` 的 Git `HEAD` 基线及 `frontend/src/types/index.ts`
- `backend/alembic/versions/`
- `backend/Dockerfile`
- `docker-compose.yml`
- 现有 MediaCrawler 设计文档和八爪鱼微博实现
- 当前数据库的只读 `information_schema`、`alembic_version`、数据源和关键词统计

工作区存在用户已有改动和诊断产物。本次没有回滚或覆盖这些改动。其中 `frontend/src/views/Sources.vue` 当前工作区版本被 Git 识别为二进制文件，无法按源码可靠审阅；前端能力判断以可读的 Git `HEAD` 基线、API 和 TypeScript 类型为依据。

## 2. 当前架构事实

### 2.1 Collector 主架构

当前采集架构遵循：

```text
DataSource / Scheduler / Manual API
                |
                v
        registry.resolve_collectors()
                |
                v
        BaseCollector.fetch()
                |
                v
        CollectorService._process_collector()
                |
                +--> region resolve
                +--> 大厂语义过滤
                +--> OpinionAdmissionService
                +--> external_id / url / title+publish_time 去重
                +--> Opinion 入库
                +--> RuleFallbackProvider
                +--> RiskEngine
                +--> CollectorRun
                |
                v
        auto_aggregate_after_collect()
                |
                +--> Event 聚合/关联
                +--> Alert 评估链路
```

关键证据：

- `backend/app/collectors/base.py:9-18`：`BaseCollector` 抽象接口和“Collector 不直接操作数据库”的约束。
- `backend/app/collectors/registry.py:195-303`：从 `data_sources` 读取启用源，按 `class_path` 动态导入并实例化。
- `backend/app/collectors/service.py:264-341`：顺序采集总流程。
- `backend/app/collectors/service.py:384-727`：单个 Collector 的 `fetch -> 准入 -> 去重 -> Opinion -> 分析 -> CollectorRun` 闭环。
- `backend/app/api/collector.py:77-144`：手动采集后台任务和采集后自动聚合。
- `backend/app/core/scheduler.py:59-178`：定时采集、八爪鱼消费和采集后聚合。

### 2.2 当前数据库只读事实

当前数据库只读查询结果：

- `data_sources` 共 38 条，`enabled=true` 共 17 条。
- 当前不存在 `key='weibo_mediacrawler'` 的数据源。
- 当前存在 `key='weibo_octopus'` 的数据源，但处于 `enabled=false`，并被调度仓储显式排除。
- `opinions` 中已有 `source='weibo' AND source_type='weibo_post'` 数据 102 条。
- `keywords` 中启用监测词当前按类别统计为：`地域` 28 条、`主题` 14 条。
- `information_schema` 已存在 MediaCrawler 复用所需的 Opinion、DataSource、CollectorRun 字段。

### 2.3 Alembic 版本一致性风险

只读查询显示数据库 `alembic_version` 为 `p12_datasource_schedule`，但实际表中已经存在：

- `opinions.source_type/author/engagement/external_id`
- `collector_runs.batch_id/trigger_type/upstream_total/upstream_returned/acknowledged/unconfirmed/ack_status/duplicate`

这些列分别对应后续迁移文件中的能力。该事实说明当前环境的“迁移版本记录”和“实际 schema”存在不一致，可能来自历史手工迁移、分支头或部署流程。Phase MediaCrawler-0 不修复此问题，也不执行迁移；Phase MediaCrawler-1 进入部署前必须单独做 schema/version 对账。

## 3. Collector 扩展能力

### 3.1 BaseCollector 接口

`backend/app/collectors/base.py:9-18` 定义：

```python
class BaseCollector(ABC):
    source_name: str = "base"
    source_config: DataSourceConfig = EMPTY_CONFIG

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        ...
```

实际调用契约比抽象基类声明更宽：`backend/app/collectors/service.py:418-422` 会调用：

```python
collector.fetch(
    keywords=monitoring_kw,
    region_kw=region_kw,
    topic_kw=topic_kw,
)
```

因此 `MediaCrawlerWeiboCollector` 可以直接继承 `BaseCollector`，但必须实现实际兼容的签名：

```python
def fetch(
    self,
    keywords=None,
    region_kw=None,
    topic_kw=None,
) -> list[dict]:
    ...
```

如果只按 `BaseCollector.fetch(self)` 的窄声明实现，运行时会因未知关键字参数失败。这是现有接口声明与运行时契约之间的技术债。

### 3.2 fetch 返回结构

Collector 应返回标准化的 `list[dict]`，至少包括：

- `title`
- `content`
- `source`
- `url`
- `publish_time`

微博帖子还应包括：

- `source_type="weibo_post"`
- `external_id`
- `author`
- `engagement`

评论如被输出，应标为 `source_type="weibo_comment"`；当前 `CollectorService` 会在 `backend/app/collectors/service.py:463-468` 跳过评论，不创建 Opinion。

### 3.3 Registry 装配方式

`backend/app/collectors/registry.py:275-279` 的装配方式为：

1. 读取 `DataSource.class_path`；
2. `importlib.import_module()` 动态导入类；
3. 解析 `config_json`；
4. 剥离 `max_items/filter_mode/keyword_scope`；
5. 执行 `cls(**config)`；
6. 注入 `scope_region_codes`、`data_source_key` 和 `source_config`。

因此新增数据源通常只需新增 Collector 类并新增一行 `data_sources` 配置，不需要改 `registry.py`，也不需要在 `__init__.py` 中手工导出。

### 3.4 对 MediaCrawlerWeiboCollector 的判断

结论：**可以直接继承 `BaseCollector`，不建议继承 `WeiboOctopusCollector`。**

建议新增位置：

- `backend/app/collectors/media_crawler_weibo_collector.py`
- 可选：`backend/app/collectors/mediacrawler_runner.py`

原因：

- 八爪鱼 Collector 包含上游“未导出队列”和 `mark_exported` 确认语义，MediaCrawler 没有同等协议。
- `CollectorService` 已通过可选的 `ack_pending_export()` 协议兼容八爪鱼，MediaCrawler 不实现即可。
- MediaCrawler 的 subprocess、超时、JSONL、登录态和临时目录应与微博字段映射解耦。

### 3.5 最小新增代码位置

Phase MediaCrawler-1 的最小实现边界建议为：

1. 新增 `MediaCrawlerWeiboCollector`。
2. 新增独立 runner，负责 subprocess、超时、退出码、JSONL 读取和临时运行目录。
3. 新增 MediaCrawler 运行环境配置读取项。
4. 新增或登记 `weibo_mediacrawler` 数据源。
5. 必要时扩展 `admin_data_sources.py` 对该专用 Collector 的配置白名单。
6. 不修改 `CollectorService`、`scheduler.py`、`opinion.py` 的核心闭环。

## 4. DataSource 支持情况

### 4.1 字段能力矩阵

| 需求字段 | 当前实际字段 | 结论 |
|---|---|---|
| `source_type` | DataSource 没有该字段；DataSource 使用 `type` | 需区分概念，不新增字段即可用 `type='social'` |
| `class_path` | `data_sources.class_path` | 已支持 |
| `enabled` | `data_sources.enabled` | 已支持 |
| `schedule_interval_minutes` | `data_sources.schedule_interval_minutes` | 已支持，数据库最小值 5 |
| `config_json` | `data_sources.config_json` | 已支持，但专用 Collector 有白名单限制 |
| 区域范围 | `scope_region_codes` | 已支持 |
| 调度启停 | `schedule_enabled` | 已支持 |
| 下次调度 | `next_collect_time` | 已支持 |

模型证据：`backend/app/models/data_source.py:14-49`。  
迁移证据：

- `backend/alembic/versions/0004_phase3_datasource_region_parent.py:20-43`
- `backend/alembic/versions/p12_datasource_schedule.py:29-76`

### 4.2 `source_type` 与 `type` 的边界

当前 DataSource 模型没有 `source_type`，只有 `type`：

```text
DataSource.type = gov_site / news_site / search / rss / api / ...
Opinion.source_type = weibo_post / weibo_comment / ...
```

因此建议：

```text
DataSource.key         = weibo_mediacrawler
DataSource.type        = social
Opinion.source         = weibo
Opinion.source_type    = weibo_post
```

不建议为了 MediaCrawler 再给 DataSource 增加一个与 `type` 重复的 `source_type` 字段。

### 4.3 Admin Data Source API 现状

关键位置：

- `backend/app/api/admin_data_sources.py:59-67`：默认类型到 `GenericSiteCollector` 的映射。
- `backend/app/api/admin_data_sources.py:75-88`：Generic/专用 Collector 配置键白名单。
- `backend/app/api/admin_data_sources.py:409-456`：新增数据源校验。
- `backend/app/api/admin_data_sources.py:785-914`：启停、配置和调度字段更新。

当前 API 对专用 Collector 只允许：

- `max_items`
- `filter_mode`
- `keyword_scope`
- `collection_mode`

而 MediaCrawler 设计需要的：

- `crawler_type`
- `login_type`
- `full_text`
- `comments`
- 其他平台/运行参数

当前会被专用 Collector 白名单拒绝。结论是：**DataSource 表支持 `config_json`，但 Admin API 尚未支持 MediaCrawler 专用配置协议。**

第一阶段可选处理方式：

- 将敏感和执行参数全部放 `.env`，`config_json` 只保留已允许的策略键；
- 或在 Phase MediaCrawler-1 扩展专用 Collector 的配置白名单；
- 不把 Cookie、浏览器目录、Python 路径、密码写入 `config_json`。

### 4.4 是否需要数据库迁移

结论：**针对第一阶段微博帖子接入，不需要新增数据库迁移。**

原因：

- `weibo_mediacrawler` 是一条数据源记录，不是数据库枚举；
- `class_path`、`type`、`enabled`、`config_json` 已存在；
- 调度字段已存在；
- Opinion 社媒字段已存在；
- CollectorRun 批次与运行字段已存在。

仍需在 Phase MediaCrawler-1 通过种子、受控管理 API 或一次性数据源登记完成新行创建。Phase 0 不执行该写操作。

## 5. Scheduler 支持情况

### 5.1 当前调度模式

`backend/app/core/scheduler.py:239-281` 支持两种模式：

- `per_source`：每 `collector_tick_interval_seconds` 秒执行一次 tick，按数据源的 `next_collect_time` 判断到期源；
- `cron`：按全局 `collector_schedule_cron` 执行。

默认配置见 `backend/app/core/config.py:57-71`：

```text
collector_schedule_mode = per_source
collector_tick_interval_seconds = 60
collector_default_interval_minutes = 30
```

### 5.2 per_source 流程

`backend/app/collectors/data_source_repository.py:44-70` 查询：

```text
enabled = true
AND schedule_enabled = true
AND key != 'weibo_octopus'
AND (next_collect_time IS NULL OR next_collect_time <= now())
```

`backend/app/core/scheduler.py:90-146` 随后：

1. 查询到期数据源；
2. 按每行自身 `schedule_interval_minutes` 更新 `last_collect_time` 和 `next_collect_time`；
3. 将到期 key 集合合并为一次 `CollectorService.collect_and_analyze_concurrent()`；
4. 采集后执行自动事件聚合。

### 5.3 是否可以直接支持微博 60 分钟采集

结论：**可以，但前提是 `collector_schedule_mode='per_source'`。**

只需将新数据源配置为：

```text
enabled = true
schedule_enabled = true
schedule_interval_minutes = 60
```

`weibo_mediacrawler` 不在当前排除列表中，因此会被逐源 tick 自动发现。无需新增独立微博 Scheduler Job，也不建议第一阶段新增，以免形成两套调度逻辑。

限制：

- 若切换到 `cron` 模式，所有源由全局 cron 驱动，无法真正按源使用 60 分钟；
- claim 在采集前推进 `next_collect_time`，采集失败后会等下一个周期；
- `collector_tick` 设置 `max_instances=1`、`coalesce=True`，长任务会延迟后续 tick；
- 现有独立 `_run_weibo_consumer_job()` 只针对 `weibo_octopus`，不会调度 MediaCrawler。

## 6. Opinion 字段评估

### 6.1 当前字段

`backend/app/models/opinion.py:14-35` 已有：

- `source`
- `url`
- `publish_time`

`backend/app/models/opinion.py:81-85` 已有：

- `source_type`
- `author`
- `engagement`
- `external_id`

对应迁移为 `backend/alembic/versions/p13_weibo_fields.py:21-28`。

### 6.2 去重行为

`backend/app/collectors/service.py:227-259` 的优先级为：

1. `external_id`，如果有 `source_type` 则按 `external_id + source_type` 查询；
2. `url`；
3. `url=''` 时按 `title + publish_time`。

数据库层还有 `opinions.url` 的有效 URL 唯一索引，见 `backend/app/models/opinion.py:115-120`。

### 6.3 是否需要新增 `platform` 字段

结论：**第一阶段不需要新增 `platform` 字段。**

推荐映射：

```text
source = "weibo"
source_type = "weibo_post"
external_id = 微博 mid
```

理由：

- 当前 `source` 已承担来源平台标识；
- `source_type` 已承担微博帖子/评论细分；
- `external_id` 已承担平台外部 ID；
- 新增 `platform` 会与 `source` 形成重复语义。

未来多平台、帖子评论分表或互动快照场景可以重新评估 `platform`，但不属于第一阶段最小接入范围。

### 6.4 Opinion 结论

微博帖子不需要新增字段；MediaCrawler 只需输出当前 CollectorService 已识别的标准字段。需要保证 `source_type='weibo_post'`，否则会落入非微博的默认准入策略，绕过微博专用准入逻辑。

## 7. 八爪鱼微博现状

### 7.1 主实现

`backend/app/collectors/weibo_octopus_collector.py` 是当前可复用程度最高的微博适配器参考。

已有能力：

| 能力 | 现状 | 可复用判断 |
|---|---|---|
| 字段映射 | `DEFAULT_FIELD_MAP` 支持中英文候选字段，见 `:43-61` | 可复用映射思想和字段命名 |
| 标题降级 | `_first_sentence()`，见 `:67-73` | 可直接复用逻辑 |
| 互动数 | `_to_int()` 支持 `1.2万`、逗号和空值，见 `:76-90` | 可复用 |
| external_id | 优先字段，缺失时 URL 降级，见 `:385-388` | 可复用策略，但 MediaCrawler 应优先使用真实 mid |
| 批内去重 | `_post_dedup_key()`，见 `:344-355` | 可复用思想，最终仍交给 CollectorService |
| 关键词过滤 | `fetch()` 使用 `keywords`，见 `:227-231` | 可复用，但 MediaCrawler 应使用分组关键词策略 |
| 登录态 | 八爪鱼 token/API 凭据来自 settings，见 `:132-162` | 不能直接复用到 MediaCrawler |
| 上游确认 | 入库后 `ack_pending_export()`，见 `:299-321` | MediaCrawler 无队列时不需要 |
| 调度 | 独立每小时 15 分 Job，见 `scheduler.py:149-178, 274` | 不建议复制；MediaCrawler 使用 per_source |

### 7.2 旧 Playwright 微博实现

`backend/app/collectors/weibo_collector.py` 与 `backend/app/collectors/weibo/crawler.py` 保留了旧的 Playwright 直爬实现：

- `WeiboCollector` 构造 `WeiboCrawler`，见 `weibo_collector.py:16-23`；
- `WeiboCrawler` 使用 `sync_playwright()` 和 Chrome channel，见 `weibo/crawler.py:12-18`；
- Cookie 通过字符串解析注入，见 `weibo/crawler.py:23-30`；
- 通过页面文本解析结果，字段不完整，`publish_time` 被置为 `None`，见 `weibo_collector.py:24-39`；
- `app/collectors/__init__.py:17` 明确说明旧微博类已从运行流程移除，仅保留兼容。

结论：旧 Playwright 代码只能作为登录态和浏览器生命周期的历史参考，不能作为 MediaCrawler 生产接入实现直接复用。当前 backend 也没有为它提供统一 `close()` 生命周期调用。

### 7.3 八爪鱼能力的复用边界

建议复用：

- 标准字段映射；
- 标题缺省策略；
- `external_id` / URL / 标题时间的去重层级；
- `engagement` JSON 结构；
- 缺失字段的容错和运行日志；
- 帖子优先、评论不进入 Opinion 的业务约定。

不复用：

- 八爪鱼 token、任务 ID、导出确认；
- 八爪鱼独立小时 Job；
- `weibo_octopus` 的排除逻辑；
- 八爪鱼 API 响应结构。

## 8. MediaCrawler 推荐接入方式

### 8.1 推荐的逻辑边界

推荐保持：

```text
MediaCrawler
    -> JSONL / 标准输出
    -> MediaCrawlerWeiboCollector
    -> CollectorService
    -> Opinion / RiskEngine / Event / Alert
```

MediaCrawler 不直接：

- 操作 SQLAlchemy Session；
- 写 `opinions`；
- 执行风险分析；
- 创建 Event；
- 修改关键词；
- 创建独立 Scheduler Job。

### 8.2 方案 A 与方案 B

#### 方案 A：backend 内 subprocess

推荐 Phase MediaCrawler-1 采用该方案的隔离变体：

```text
backend container
  ├─ FastAPI 主环境
  └─ MediaCrawler 独立 venv / runner
```

具体要求：

- MediaCrawler 作为固定版本源码或子模块放在独立目录；
- 使用独立 Python venv，不把 MediaCrawler 依赖直接覆盖当前 backend 环境；
- 每批次使用独立运行目录；
- 使用 JSONL 文件作为边界；
- 使用 `subprocess.run/Popen` 配合超时、退出码和 stderr 处理；
- Cookie、浏览器目录、执行路径等敏感/运行配置走环境变量或受控挂载；
- 不使用共享的全局 `base_config.py` 作为并发任务配置。

优势：

- 对当前单体 backend 改动最小；
- 不新增服务间通信；
- 复用现有 `CollectorService` 和 per_source 调度；
- 符合当前 `docker-compose.yml` 的单 backend 架构。

代价：

- backend 镜像需要包含独立运行环境和浏览器依赖；
- 镜像体积增大；
- backend 进程仍承担 crawler 进程管理责任；
- 长任务、僵尸进程和临时目录清理需要实现。

#### 方案 B：独立 crawler container

长期扩展到多个平台、多账号、评论下钻和多 worker 时，独立容器的隔离性更好：

- 浏览器依赖与 API 镜像完全隔离；
- crawler 可独立扩缩容；
- 更适合任务租约、重试、死信、平台限速和资源配额。

但当前项目的 `docker-compose.yml:3-5` 明确采用 PostgreSQL + backend + frontend 的单体结构，并注明不拆微服务。方案 B 还需要新增服务、任务协议、结果传输、生命周期管理和部署改动。

### 8.3 当前项目的推荐结论

**Phase MediaCrawler-1 选择方案 A 的“backend 内 subprocess + 独立 venv + JSONL”版本。**

**方案 B 作为后续规模化演进方向，不作为第一阶段最小接入方式。**

## 9. 是否需要数据库迁移

### 9.1 第一阶段结论

不需要新增迁移，复用现有：

- `data_sources`
- `opinions`
- `collector_runs`

### 9.2 需要新增的数据源记录

建议数据源语义为：

```text
key                  = weibo_mediacrawler
name                 = 微博（MediaCrawler）
type                 = social
class_path           = app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
enabled              = false（验收前）
schedule_enabled     = true
schedule_interval_minutes = 60
scope_region_codes   = 按实际监测范围配置
```

其中 `name` 必须与 Collector 的 `source_name` 保持一致。原因是：

- `CollectorRun.collector_name` 写入的是 `collector.source_name`，见 `service.py:401-408`；
- Admin Data Source API 按 `collector_name == DataSource.name` 关联运行历史，见 `admin_data_sources.py:493-505`。

若名称不一致，采集可能成功，但数据源管理页面的最近运行、健康度和历史关联会缺失。

### 9.3 迁移风险

虽然第一阶段不需要新列，但部署前必须解决第 2.3 节的 Alembic 版本与实际 schema 不一致问题。该问题不应在 MediaCrawler 接入过程中顺手处理，必须作为独立的迁移基线审计项。

## 10. 推荐实施方案

### Phase MediaCrawler-1 最小实施包

1. 固定 MediaCrawler 版本和源码位置。
2. 新增 `MediaCrawlerWeiboCollector`。
3. 新增 runner：
   - 生成批次目录；
   - 生成临时配置；
   - 启动 subprocess；
   - 捕获 stdout/stderr；
   - 处理超时和非零退出码；
   - 读取 JSONL；
   - 标准化字段；
   - 清理临时文件。
4. 关键词：
   - 读取 `get_monitoring_keywords_grouped()` 的启用监测词；
   - 按 `keyword_scope` 和 `filter_mode` 选择地域/主题词；
   - 合并去重后传给 MediaCrawler；
   - 不把 `type='sensitive'` 风险词作为搜索词；
   - 不把所有关键词无上限地扩展成独立长任务。
5. 字段映射：
   - `source='weibo'`
   - `source_type='weibo_post'`
   - `external_id=mid`
   - `author=昵称`
   - `engagement={likes,comments,reposts}`
6. 数据源初始 `enabled=false`，先手动验收，再启用自动调度。
7. 调度使用 `per_source` + `schedule_interval_minutes=60`。
8. 复用 `POST /api/collector/run` 的 `data_source_ids` 单源手动采集能力。
9. 不新增独立微博 Scheduler Job。
10. 保留八爪鱼 `weibo_octopus` 数据源，不覆盖、不复用其排除和确认语义。

### Phase MediaCrawler-1 需要关注的配套代码

核心链路不需要改，但以下位置可能需要小范围配套调整：

- `backend/app/core/config.py`：MediaCrawler 根目录、Python 路径、超时时间、浏览器数据目录等环境变量。
- `backend/app/api/admin_data_sources.py`：允许 MediaCrawler 专用非敏感配置键，或明确限制配置全部来自环境变量。
- `backend/Dockerfile` 或独立 crawler 镜像：安装 MediaCrawler 独立运行环境和浏览器依赖。
- 数据源种子/登记流程：创建 `weibo_mediacrawler` 行。

## 11. 风险列表

### 11.1 登录态风险

- 当前项目仅有八爪鱼凭据和旧 `weibo_cookie` 配置，没有 MediaCrawler 登录态配置。
- Playwright 登录态可能依赖 Cookie、持久化浏览器目录、验证码或人工登录。
- 登录态过期、容器重建、目录权限和多任务并发覆盖都可能导致零数据或登录页输出。
- Cookie、浏览器用户目录和密码不得写入 `data_sources.config_json` 或日志。

### 11.2 微博风控风险

- 当前旧实现曾因 HTTP 访问出现 432，后来保留了 Playwright 方案；这说明微博访问结果受风控和页面策略影响。
- MediaCrawler 不能保证长期绕过风控。
- 搜索关键词过多、频率过高、账号固定、出口固定都可能增加封禁和验证码概率。
- 60 分钟频率只能作为初始保守值，不能视为风控保证。

### 11.3 Playwright 资源消耗

- 当前 `requirements.txt` 没有 Playwright；
- `backend/Dockerfile` 基于 `python:3.12-slim`，没有浏览器系统依赖安装；
- 浏览器进程、页面、上下文、缓存和临时文件会显著增加内存和磁盘占用；
- 不建议把 MediaCrawler 的依赖直接合并到 backend 主环境。

### 11.4 长任务阻塞风险

- `per_source` tick 默认每 60 秒检查一次；
- tick 使用 `max_instances=1` 和 `coalesce=True`；
- MediaCrawler 长时间运行时，后续 tick 会延迟或合并；
- claim 在采集前推进下次时间，失败后不会立即重试；
- 手动采集与定时采集仍可能产生同源并发，需在 Phase 1 设计运行锁或明确禁止重入；
- 超时必须由 runner 强制终止子进程，并保证 `CollectorRun` 最终落为 `failed`。

### 11.5 数据质量风险

- 搜索结果可能包含广告、娱乐、营销、同名词和非河北语境内容；
- `OpinionAdmissionService` 对 `weibo_post` 使用较严格的地域、公共事务、诉求和风险信号准入，见 `opinion_admission_service.py:99-228`；
- 如果忘记设置 `source_type='weibo_post'`，会走非微博默认准入策略；
- `external_id` 当前有索引但没有数据库层的 `(source_type, external_id)` 唯一约束，最终幂等仍依赖 Service 查询和数据库 URL 唯一约束；
- 微博正文、发布时间、作者昵称、互动数的字段结构可能随 MediaCrawler 版本或平台页面变化；
- 评论不能在第一阶段直接作为 Opinion 主体，否则会污染舆情主体、风险和事件数量。

### 11.6 关键词风险

- 当前启用监测词为 28 个地域词和 14 个主题词，直接逐词启动浏览器任务可能成本过高；
- `get_monitoring_keywords()` 在表没有 monitoring 记录时会回退 settings 配置，在表存在但全部停用时返回空列表，两种情况语义不同；
- `filter_mode` 和 `keyword_scope` 是采集策略，不是风险词库；
- “大厂”语义过滤是 CollectorService 后置语义过滤，不应误认为 MediaCrawler 搜索前置规则；
- 第一阶段应采用“启用的 monitoring 词 + 数据源策略”的 approved keyword 规则，不需要新增数据库字段，但需要限制批次数量和记录实际搜索词。

### 11.7 合规风险

- MediaCrawler 及其依赖的许可证、微博平台条款、账号授权、数据用途和个人信息处理边界必须在实施前确认；
- 不应把“可抓取”解释为“可任意存储、分析或传播”；
- Cookie、账号、个人信息、评论和互动数据应按最小化、权限控制和留存策略处理；
- 第一阶段只能宣称微博帖子采集与分析，不应宣称完整多平台、评论级、7×24 集群能力。

## 12. Phase MediaCrawler-1 实施建议

### 12.1 进入条件

建议在以下条件满足后进入：

1. 确认 MediaCrawler 版本、许可证和微博使用合规性；
2. 确认登录态保存方式和容器持久化目录；
3. 解决当前部署环境的 Alembic 版本/schema 对账问题；
4. 明确 `weibo_mediacrawler` 的区域范围和第一批 approved keywords；
5. 确认 60 分钟是初始频率，并设置超时上限；
6. 确认不采集评论或评论仅落原始文件、不进入 Opinion；
7. 先以 `enabled=false` 完成离线 fixture / JSONL 适配测试，再做受控真实验收。

### 12.2 第一阶段验收重点

- Collector 能被 registry 按 `class_path` 装配；
- `source_name` 与 DataSource `name` 一致；
- `fetch()` 返回标准字段；
- `source_type='weibo_post'`；
- `external_id`、`url`、`author`、`engagement` 正确映射；
- 重复 mid 不重复创建 Opinion；
- 登录失败、超时、非零退出码均写入 `CollectorRun(status='failed')`；
- `batch_id`、`trigger_type`、抓取数、入库数和错误原因可追溯；
- `schedule_interval_minutes=60` 在 per_source 模式生效；
- MediaCrawler 失败不会阻断其他数据源；
- 八爪鱼 `weibo_octopus` 仍保持独立、未被覆盖；
- 采集完成后事件聚合和预警链路仍可运行。

### 12.3 最终判断

| 审计问题 | 结论 |
|---|---|
| 当前 Collector 架构是否支持接入 | 支持标准 Collector 接入 |
| 最小新增代码位置 | `media_crawler_weibo_collector.py` + 独立 runner |
| 是否需要修改 CollectorService | 核心链路不需要 |
| 是否需要修改 Opinion 模型 | 不需要 |
| 是否需要新增字段 | 第一阶段不需要 |
| Scheduler 是否支持微博独立频率 | 支持，需使用 `per_source` |
| DataSource 是否支持社媒数据源 | 表结构支持；Admin API 配置白名单需补齐 |
| 八爪鱼能力是否可复用 | 字段映射、去重、容错可复用；token/ack/独立 Job 不复用 |
| 最合理接入方式 | backend 内 subprocess + 独立 venv + JSONL |
| 第一阶段主要风险 | 登录态、风控、Playwright资源、长任务、数据质量、合规 |

**是否建议进入 Phase MediaCrawler-1：建议进入，但以“先补齐运行环境和专用配置协议、先做离线 JSONL/fixture 验证、再做受控真实采集”为前置条件。**
