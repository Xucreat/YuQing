# MediaCrawler 微博接入与多平台扩展设计方案

**日期：** 2026-08-04  
**适用项目：** 河北省舆情监测系统  
**文档性质：** 实施设计方案  
**当前阶段：** 方案设计，尚未修改业务代码

## 1. 设计目标

在不破坏现有采集、入库、风险分析、事件聚合和前端功能的前提下，接入
`MediaCrawler` 的微博抓取能力，使微博成为当前系统可配置的数据源。

第一阶段目标：

1. 支持微博关键词搜索；
2. 支持用户配置数据源启停和采集频率；
3. 支持自动定时采集；
4. 支持管理员手动指定微博数据源采集；
5. 微博帖子进入现有 `CollectorService` 闭环；
6. 复用现有去重、关键词准入、风险分析、事件聚合和采集日志；
7. 保留八爪鱼数据源，不与新微博数据源互相覆盖。

后续阶段再扩展小红书、抖音、B站、知乎、贴吧、评论下钻和多 worker 集群。

## 2. 设计原则

### 2.1 保留现有业务闭环

`MediaCrawler` 只负责抓取和输出原始微博数据，不直接写入当前系统的
`opinions` 表，不直接执行风险分析。

```text
MediaCrawler
    -> 标准化适配器
    -> CollectorService
    -> 去重
    -> 准入判断
    -> Opinion 入库
    -> 规则风险分析
    -> 事件聚合 / 预警
```

### 2.2 采集策略由当前系统控制

MediaCrawler 不使用自己的固定关键词和定时任务。采集任务的关键词、数据源
启停、采集频率、区域范围和最大采集量由当前系统控制。

### 2.3 MediaCrawler 运行环境隔离

MediaCrawler 使用独立 Python 虚拟环境，但可以先与现有 backend 运行在同一
Docker 容器内，通过 `subprocess` 调用。这样既不引入额外服务，又避免与当前
FastAPI/Pydantic/httpx 依赖互相污染。

### 2.4 先帖子、后评论

第一阶段只把微博帖子接入现有 `Opinion` 表。评论不直接创建 Opinion，避免
评论噪声污染现有舆情主体。

评论下钻作为第二阶段独立数据模型和分析流程实现。

## 3. 当前系统可复用能力

当前项目已经具备以下接入基础：

| 能力 | 当前实现 |
|---|---|
| 采集器抽象 | `backend/app/collectors/base.py` |
| 数据源装配 | `backend/app/collectors/registry.py` |
| 数据源配置 | `data_sources` 表 |
| 自动调度 | `backend/app/core/scheduler.py` |
| 手动采集 | `POST /api/collector/run` |
| 统一入库 | `backend/app/collectors/service.py` |
| 帖子去重 | `external_id` / `url` / `title + publish_time` |
| 风险分析 | `RuleFallbackProvider` + `RiskEngine` |
| 事件聚合 | `auto_aggregate_after_collect` |
| 采集日志 | `collector_runs` |
| 微博字段 | `source_type`、`author`、`engagement`、`external_id` |

因此，第一阶段不需要重写 CollectorService、Scheduler 或 Opinion 模型。

## 4. 总体架构

```text
┌──────────────────────────────────────────────────────────┐
│ 当前舆情监测系统 backend                                  │
│                                                          │
│  DataSource / Keywords / Scheduler / Manual API          │
│                         │                                │
│                         ▼                                │
│             MediaCrawlerWeiboCollector                   │
│                         │                                │
│          临时配置 + subprocess 启动 MediaCrawler          │
│                         │                                │
│                   JSONL 输出文件                         │
│                         │                                │
│                         ▼                                │
│             微博字段标准化 / 本批次去重                    │
│                         │                                │
│                         ▼                                │
│                  CollectorService                       │
│                         │                                │
│        Opinion / 风险分析 / 事件 / 预警 / 日志             │
└──────────────────────────────────────────────────────────┘
```

## 5. MediaCrawler 接入方式

### 5.1 代码组织

建议将 MediaCrawler 作为 Git 子模块放在：

```text
backend/vendor/MediaCrawler
```

新增文件：

```text
backend/app/collectors/media_crawler_weibo_collector.py
backend/app/collectors/mediacrawler_runner.py
```

不建议把 MediaCrawler 的全部源码复制到 `app/collectors` 下，也不建议让
MediaCrawler 直接操作当前系统的 SQLAlchemy Session。

### 5.2 运行方式

适配器为每一次采集创建独立运行目录：

```text
runtime/mediacrawler/
└── runs/
    └── <batch_id>/
        ├── config/
        ├── output/
        │   └── weibo.jsonl
        └── crawler.log
```

运行时传入：

- 当前系统的地域关键词；
- 当前系统的主题关键词；
- 数据源配置中的最大采集量；
- 登录方式；
- 是否抓取全文；
- 是否抓取评论；
- 当前批次目录。

禁止修改一个所有任务共享的 `base_config.py`。这样可以避免手动采集和定时
采集并发时互相覆盖关键词和平台配置。

### 5.3 输出协议

MediaCrawler 与当前系统之间统一使用 JSONL：

```json
{
  "platform": "weibo",
  "external_id": "微博mid",
  "content": "微博正文",
  "title": "微博正文首句",
  "url": "https://weibo.com/...",
  "publish_time": "2026-08-04 10:30:00",
  "author": "账号昵称",
  "engagement": {
    "likes": 10,
    "comments": 3,
    "reposts": 1
  },
  "source_keyword": "廊坊"
}
```

如果当前 MediaCrawler 版本已有可用 JSON 输出，则优先复用；如果输出字段
不完整，仅在微博 Store 增加一个 JSONL 导出补丁，不修改微博请求和解析逻辑。

## 6. 采集器适配器设计

新增：

```python
class MediaCrawlerWeiboCollector(BaseCollector):
    source_name = "微博（MediaCrawler）"
    data_source_key = "weibo_mediacrawler"

    def fetch(
        self,
        keywords=None,
        region_kw=None,
        topic_kw=None,
    ) -> list[dict]:
        ...
```

适配器职责：

1. 合并和清洗当前系统传入的关键词；
2. 生成本批次 MediaCrawler 配置；
3. 启动子进程；
4. 处理超时、非零退出码和登录失败；
5. 读取 JSONL；
6. 映射成当前 `CollectorService` 所需字段；
7. 使用 `external_id` 做批次内去重；
8. 返回标准化 `list[dict]`。

适配器不负责：

- 写数据库；
- 创建调度任务；
- 执行 AI；
- 创建事件；
- 修改用户关键词；
- 确认微博评论为独立舆情。

## 7. 标准字段映射

| MediaCrawler 字段 | 当前系统字段 |
|---|---|
| 微博 ID / mid | `external_id` |
| 正文 | `content` |
| 正文首句 | `title` |
| 微博链接 | `url` |
| 发布时间 | `publish_time` |
| 用户昵称 | `author` |
| 点赞、评论、转发 | `engagement` |
| 平台 | `source="weibo"` |
| 内容类型 | `source_type="weibo_post"` |

如果微博没有明确标题，则使用正文首句作为标题，保持与现有八爪鱼适配器一致。

## 8. 数据源配置

新增数据源：

```text
key: weibo_mediacrawler
name: 微博（MediaCrawler）
type: social
class_path: app.collectors.media_crawler_weibo_collector.MediaCrawlerWeiboCollector
enabled: false
schedule_enabled: true
schedule_interval_minutes: 60
scope_region_codes: 131000
```

建议初始保持 `enabled=false`，通过手动测试验收后再启用。

`config_json` 示例：

```json
{
  "max_items": 30,
  "crawler_type": "search",
  "login_type": "cookie",
  "full_text": false,
  "comments": false,
  "collection_mode": "regional",
  "filter_mode": "region_or_topic",
  "keyword_scope": "region_topic"
}
```

Cookie、浏览器目录和执行路径不放入 `config_json`，统一放在 `.env`：

```env
MEDIA_CRAWLER_ROOT=/app/vendor/MediaCrawler
MEDIA_CRAWLER_PYTHON=/opt/mediacrawler-venv/bin/python
MEDIA_CRAWLER_TIMEOUT_SECONDS=1800
MEDIA_CRAWLER_BROWSER_DATA=/app/runtime/mediacrawler
```

## 9. 自动定时采集适配

当前 `per_source` 调度流程保持不变：

```text
collector tick
    -> 查询 enabled=true 且 schedule_enabled=true 的到期数据源
    -> claim next_collect_time
    -> include_data_source_keys={"weibo_mediacrawler"}
    -> CollectorService.collect_and_analyze_concurrent()
```

微博数据源的采集频率由：

```text
data_sources.schedule_interval_minutes
```

控制。建议初始配置为 60 分钟，观察稳定性后再调整。

不建议第一阶段新增独立微博 scheduler job，以免产生两套调度逻辑。

## 10. 手动采集适配

复用现有接口：

```http
POST /api/collector/run
```

请求体：

```json
{
  "data_source_ids": [微博数据源ID]
}
```

执行结果继续通过当前任务接口查询：

```text
GET /api/tasks/{task_id}
```

采集结果会继续写入：

- `collector_runs`
- `opinions`
- 事件和预警相关表

## 11. Docker 运行环境

建议在 backend 容器内使用独立虚拟环境：

```dockerfile
RUN python -m venv /opt/mediacrawler-venv \
    && /opt/mediacrawler-venv/bin/pip install \
       -r /app/vendor/MediaCrawler/requirements.txt \
    && /opt/mediacrawler-venv/bin/playwright install chromium
```

不建议直接把 MediaCrawler 的依赖全部合并到当前 backend Python 环境，避免
FastAPI、Pydantic、httpx、SQLAlchemy 版本互相覆盖。

浏览器登录态建议挂载目录：

```yaml
volumes:
  - ./runtime/mediacrawler:/app/runtime/mediacrawler
```

首次登录可使用非无头模式，登录成功后后续定时任务使用已保存登录态。

## 12. 评论下钻扩展设计

第一阶段评论不进入 `opinions`。

第二阶段新增：

```text
social_posts
social_comments
```

或至少新增：

```text
weibo_comments
```

评论表建议字段：

```text
id
platform
post_external_id
comment_external_id
author
content
publish_time
like_count
parent_comment_id
sentiment
risk_score
created_at
```

评论分析结果不直接作为独立事件主体，而是作为微博帖子的反馈聚合：

```text
微博帖子
    ├─ 评论数量
    ├─ 负面评论比例
    ├─ 主要诉求
    ├─ 高风险评论
    └─ 舆情趋势
```

## 13. 多平台扩展设计

每个平台独立成为一个 `data_sources` 数据源：

```text
weibo_mediacrawler
xhs_mediacrawler
douyin_mediacrawler
bilibili_mediacrawler
zhihu_mediacrawler
tieba_mediacrawler
```

各平台适配器只负责输出统一字段：

```text
platform
external_id
title
content
url
publish_time
author
engagement
source_keyword
```

帖子、视频、笔记等内容统一进入社媒内容标准化层，再决定进入现有
`Opinion` 或后续的 `social_posts` 表。

## 14. 后续 7×24 任务集群设计

当平台数量达到 5 个以上，建议将当前 APScheduler 采集任务升级为：

```text
APScheduler
    -> Redis / PostgreSQL 任务队列
    -> crawler worker
        ├─ Weibo worker
        ├─ XHS worker
        ├─ Douyin worker
        └─ Comment worker
    -> AI analysis worker
```

需要补充：

- 任务租约；
- 超时回收；
- 失败重试；
- 平台级并发限制；
- 登录态健康检查；
- 代理和出口管理；
- 死信任务；
- 运行监控；
- 数据源健康度；
- 采集质量指标。

第一阶段不引入任务队列，避免扩大改动范围。

## 15. 实施阶段

### Phase 1：微博帖子接入

- MediaCrawler 子模块；
- 独立运行环境；
- JSONL 输出；
- `MediaCrawlerWeiboCollector`；
- 数据源配置；
- 自动采集；
- 手动采集；
- `collector_runs` 验收。

### Phase 2：稳定性增强

- 登录态检查；
- 采集超时；
- 失败重试；
- 输出文件清理；
- 平台级限速；
- 采集健康度展示。

### Phase 3：评论下钻

- 评论表；
- 帖子评论关联；
- 评论情感和风险分析；
- 评论聚合指标；
- 高风险评论预警。

### Phase 4：多平台扩展

- 小红书；
- 抖音；
- B站；
- 知乎；
- 贴吧；
- 其他平台。

### Phase 5：采集集群

- Redis/任务队列；
- 多 worker；
- 多账号；
- 多浏览器实例；
- 容错和监控；
- 7×24运行。

## 16. 第一阶段验收标准

### 功能验收

1. 数据源管理中可以看到微博（MediaCrawler）；
2. 禁用数据源时不参与自动采集；
3. 修改采集频率后按新频率执行；
4. 手动指定微博数据源可以单独采集；
5. 微博帖子成功进入 `opinions`；
6. `source_type=weibo_post`；
7. `author`、`engagement`、`external_id` 正确写入；
8. 重复采集不会重复入库；
9. 采集失败会在 `collector_runs` 中记录；
10. 采集完成后自动执行事件聚合。

### 运维验收

1. MediaCrawler 登录态可以持久化；
2. 单次超时不会阻塞 FastAPI；
3. MediaCrawler 进程异常会被记录；
4. 临时配置不会互相覆盖；
5. 子模块版本可固定和回滚；
6. 八爪鱼数据源仍可独立运行。

## 17. 风险与限制

1. MediaCrawler 不能保证永久绕过微博风控；
2. 登录态、验证码、页面结构变化会导致采集失败；
3. 采集频率不能过高；
4. MediaCrawler 当前许可证和实际使用场景需要进行合规确认；
5. 第一阶段只能宣称“微博自动采集与分析”，不能宣称完整的“10+平台
   7×24 评论级集群监控”；
6. 评论数据量大后必须与帖子数据分表，不能全部写入 `opinions`。

## 18. 最终建议

先实施 Phase 1，不改现有核心业务链路：

```text
MediaCrawler
    -> JSONL
    -> MediaCrawlerWeiboCollector
    -> 现有 CollectorService
```

该方案能够同时满足：

- 用户配置数据源；
- 自动定时采集；
- 管理员手动采集；
- 现有舆情入库；
- 风险分析；
- 事件聚合；
- 采集日志审计。

在微博稳定运行并积累真实采集数据后，再决定是否进入评论下钻、多平台和
任务集群阶段。
