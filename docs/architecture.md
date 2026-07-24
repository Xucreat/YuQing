# 架构设计（architecture.md）

## 1. 总体架构

```
                  ┌─────────────────────────────────────┐
                  │            Frontend (Vue3)           │
                  │  nginx 静态托管 + /api 反向代理       │
                  │  Login / Dashboard / Opinions /      │
                  │  OpinionDetail / Events (ECharts)     │
                  └───────────────┬─────────────────────┘
                                  │  HTTPS /api
                  ┌───────────────▼─────────────────────┐
                  │            Backend (FastAPI)          │
                  │  api/  routers                        │
                  │  services/  (ai_service, event...)   │
                  │  collectors/ (base,mock,rss,gov)     │
                  │  core/ (config, security)            │
                  │  models/ schemas/ utils/ db/         │
                  └───────┬───────────────────┬──────────┘
                          │                   │
                  ┌───────▼──────┐    ┌───────▼────────┐
                  │ PostgreSQL 16 │    │  DeepSeek API   │
                  │ (唯一数据库)   │    │ (经 AIService) │
                  └──────────────┘    └────────────────┘
```

- 部署形态：**Docker Compose 三服务**（`postgres` / `backend` / `frontend`），无微服务。
- 前端生产构建由 nginx 托管，并将 `/api` 反向代理到 backend 容器。

## 2. 数据流闭环

```
Collector.fetch()  --(标准化 dict)-->
  Service (入库/AI分析/事件聚合)  --(ORM)-->
    PostgreSQL
      │
      ▼
  FastAPI API  --(JSON)-->
    Vue3 前端展示
```

- **Collector 不直接操作数据库**：采集 → Service → Database。
- **AI 隔离**：业务经 `AIService.analyze()` 调用，内部决定 DeepSeek 或规则降级。

## 2.1 Collector 数据流（Phase 3A 闭环 + Phase 3B 政府网站真实采集）

```
Source (MockCollector / RSSCollector / GovernmentCollector)
   │  fetch() -> list[dict]  (标准化：title/content/source/url/publish_time)
   ▼
CollectorService.collect_and_analyze(db)
   │  ⓪ 政府采集 5 秒防抖：距上次不足 THROTTLE_SECONDS → CollectorThrottled(→ API 429)
   │  ① 按 url 去重（url 空则 title+publish_time）-> 跳过已存在
   │  ② 新建 Opinion(pending, risk_score=0, sentiment=neutral)
   ▼
Opinion  ──(AIService.analyze)──▶  AI  (DeepSeek / RuleFallback 降级)
   │                                          │
   │  ③ 写回 summary/sentiment/risk_score/keywords/analysis_suggestion
   ▼                                          │
PostgreSQL  ◀── 状态流转 completed / failed ─┘
```

### GovernmentCollector（Phase 3B 真实数据源）

```
gov_news_urls (Pydantic Settings，从 .env 逗号分隔加载)
   │  例：https://www.lfdc.gov.cn/jrdc.jhtml, .../gggs.jhtml
   ▼
GovernmentCollector.fetch()
   │  ① requests.Session + 浏览器 UA，_get() 防御式 GET（失败/超时/HTTP 错误 → None → 返回 []）
   │  ② _parse_list()：BeautifulSoup 选 a[href*='.jhtml']，urljoin 转绝对 URL
   │        _ARTICLE_PATH_RE = /\d+\.jhtml$ 过滤导航/栏目链接，仅留真实文章
   │  ③ 按 url 去重候选 → 取前 MAX_ARTICLES=20 篇
   │  ④ 逐篇 _get 详情，每次 time.sleep(REQUEST_INTERVAL=0.3) 控速
   │        _parse_detail()：正文降级链
   │          div.content → article-content/text/TRS_Editor → Zoom/article_con
   │          → article → 所有 <p> 拼接 → body 纯文本前 500 字
   ▼
list[dict]  source="大厂县政府网站"，publish_time=None（列表页无稳定时间）
```

- **复用 AIService**：`CollectorService` 与手动分析 API（`POST /api/analyze/{id}`）共用 `AIService.analyze(title, content)`；MVP 不抽取公共 helper，但已在 `collectors/service.py` 标注 `TODO Phase 4` 待抽取。
- **失败隔离**：单条 AI 异常仅该 `Opinion` 置 `failed`（记录保留），不影响其余。
- **状态内存化**：采集运行计数（`last_run`/`total_collected`/`collector_type`）存模块级变量，重启丢失（Phase 3A 临时；未来定时采集再设计 `collector_runs` 表）。
- **采集方式配置化（Phase 3B）**：`settings.collector_type`（默认 `government`）决定 `resolve_collectors()` 选用 `GovernmentCollector` 还是 `MockCollector`；测试默认 `mock`（`conftest` 注入 `COLLECTOR_TYPE=mock`）。三种采集器（mock/rss/government）均可独立实例化并存。
- **概念区分**：`Opinion.source` 表示**新闻来源**（"大厂县政府网站"）；API 返回的 `collector_type` 表示**采集方式**（government/mock），两者不可混淆。
- **反爬克制**：单次 ≤ `MAX_ARTICLES=20` 篇、请求间隔 `REQUEST_INTERVAL=0.3s`、不递归、不抓附件、不绕过反爬；网站不可访问不判失败（返回空列表）。

### Collector 去重与数据完整性约束（Phase 7 加固，**纵深防御**）

- **采集层去重（软约束）**：`CollectorService` 按 `url` 去重（url 空则 `title+publish_time`），已存在则跳过不重复创建（`app/collectors/service.py`）。
- **数据库层兜底（硬约束）**：`opinions` 表建有**部分唯一索引** `ix_opinions_url_unique`（`url<>''` 时唯一，空串允许多条），由 Alembic 迁移 `p6urluniq01` 创建；任何绕过采集层的同 url 重复插入都会被 DB 拒绝。
- **事件关联唯一**：`event_opinions` 表建有**唯一约束** `uq_event_opinions_event_opinion`（`event_id`, `opinion_id`），由迁移 `p7evtuniq01` 创建；防止同一舆情被重复挂载到同一事件而产生传播树失真。
- **存量清理纪律**：历史重复数据由一次性脚本 `backend/cleanup_duplicate_opinions.sql` 在**单事务内**执行，删除前对所有相关表做 SELECT 验证（url 重复 / eo 重复 / FK 悬空 / 删除集残留 全为 0 才 COMMIT）；清理前须 `pg_dump` 备份。禁止为让迁移通过而自动删除业务数据。

### EventAggregator（Phase 3C-0 事件聚合基础层）

```
Opinion (analysis_status=completed, keywords 非空, created_at ∈ 近 event_window_days=7 天)
   │  ① 按 region_id 分组
   ▼
组内两两比较 keywords（逗号分隔）→ 有任一交集则归并（连通分量，O(n²)）
   │  ② 每组 = 一个事件候选
   ▼
对每组检查既有 Event（按 keyword 交集匹配）
   ├─ 无匹配 → 新建 Event（title=最高 risk 的 Opinion.title）
   │            keyword=组内 keywords 去重逗号拼接
   │            risk_level=max(risk_score) 映射（>=70 high / >=40 medium / else low）
   │            opinion_count / first_time / last_time 由组内派生
   │            description=最高 risk 的 Opinion.content[:200]
   └─ 有匹配 → 显式追加 EventOpinion(event_id, opinion_id)（已关联跳过）
               重算 opinion_count / last_time / risk_level / keyword(并集)
   ▼
返回 { "created": N, "updated": N, "linked": N }
   │
   ▼
PostgreSQL（events / event_opinions 既有表，无新迁移）
```

- **激活既有基础设施，不新建表**：`events` / `event_opinions` 已在 `0001_initial` 创建；本阶段**不新增 Alembic 迁移**、不修改 0001/0002/0003。
- **关联方式（硬约束）**：新增事件-舆情关联一律经 `EventOpinion(event_id=xxx, opinion_id=xxx)` **显式创建**；**不使用 `relationship.append()`**，不修改 `event_opinions` 表结构（无 `created_at` / 唯一约束）。
- **`status` 仅序列化层**：`Event` Model 无 `status` 列；API 响应固定返回 `"active"`。
- **幂等**：同一 Opinion 重复执行不重复创建 Event、不重复插入关联（`_link_all` 先查已关联 `opinion_id` 集合再跳过）。
- **旧 `event_service.py` 保留但标记 `[DEPRECATED]`**，新聚合逻辑统一位于 `app/services/event/aggregator.py`（`EventAggregator`）。
- **约束遵守**：无 Redis / ES / MQ / Celery / 定时任务 / AI 聚类；无图数据库、聚类算法、AI embedding；不改 Opinion / Collector / AIService / Dashboard / frontend。

## 3. 后端分层

| 目录 | 职责 |
| --- | --- |
| `app/main.py` | 应用入口、路由挂载、`/health` |
| `app/api/` | HTTP 路由层（登录、舆情、Dashboard、Event、Analyze） |
| `app/models/` | SQLAlchemy 模型（users/regions/opinions/keywords/events/event_opinions） |
| `app/schemas/` | Pydantic 请求/响应模型 |
| `app/services/` | 业务逻辑：`ai_service.py`、`event/aggregator.py`（Phase 3C-0 事件聚合）、`event_service.py`（已废弃，保留兼容） |
| `app/collectors/` | 采集抽象：`base.py`、`mock_collector.py`、`rss_collector.py`、`government_collector.py`（Phase 3B 真实政府网站）、`service.py`（采集闭环 + 5 秒防抖 + 配置化选择） |
| `app/core/` | 配置 `config.py`、安全 `security.py`、调度 `scheduler.py`（Phase 7 跨进程单例锁） |
| `app/db/` | 引擎、会话、Base |
| `app/utils/` | 通用工具 |

## 4. 区域层级（可扩展）

`regions` 表以 `code` + `level` 描述行政层级，未来扩展：

```
省 (province)
  └─ 市 (city)
       └─ 区县 (county)   ← 当前试点：大厂回族自治县 131028
            └─ 街道 (street)
                 └─ 单位 (unit)
```

## 5. AI 调用边界（Phase 2C-1 落地）

```
业务代码 / API 层
   │  （禁止直连 DeepSeek）
   ▼
AIService.analyze(title, content)     # 拼为 text 委托给 provider.analyze(text)
   │
   ├─ DeepSeekProvider   （DEEPSEEK_API_KEY 配置且调用成功 → 结构化 JSON）
   │       └─ OpenAI SDK 兼容：system/user Prompt + response_format=json_object
   │           → 去 ```json 代码块 → json.loads → AIAnalysisResult.model_validate
   │
   └─ RuleFallbackProvider （降级：未配置 / 调用或解析异常时）
           └─ 敏感词权重算 risk_score（默认 20，命中 +10*weight，封顶 100）
```

- **类型化**：Provider 层与 `AIService` 均返回 `AIAnalysisResult`（`app/schemas/ai.py`），不放 dict；API 层经 `OpinionOut` 序列化。
- **调度归属**：`AIService` 负责 Provider 选择 + 异常 + Fallback；**不直接查数据库**，敏感词经构造参数注入 `RuleFallbackProvider`（MVP 默认 `None` → 内置 `DEFAULT_KEYWORDS`）。
- 输出（`AIAnalysisResult`）：
```json
{
  "summary": "舆情摘要",
  "sentiment": "positive|negative|neutral",
  "risk_score": 0,
  "keywords": [],
  "suggestion": "研判建议"
}
```

## 6. AI 分析架构（Phase 2C-1 闭环）

```
Opinion
   ▼
POST /api/analyze/{id}      （Bearer JWT）
   ▼
AIService.analyze(title, content)
   ├─ DeepSeekProvider   （配置时优先；失败上抛 → 降级）
   └─ RuleFallbackProvider（降级兜底）
   ▼
更新 Opinion（summary/sentiment/risk_score/keywords/analysis_suggestion
            + analysis_status=completed / analysis_time=now；失败置 failed）
   ▼
返回完整 OpinionOut
```

- `app/services/ai/`：
  - `service.py` → `AIService`（调度 + Fallback）
  - `providers/base.py` → `BaseAIProvider`（ABC，`analyze(text)`）
  - `providers/deepseek.py` → `DeepSeekProvider`（OpenAI SDK 真实调用）
  - `fallback.py` → `RuleFallbackProvider`（规则分析）
- `app/api/analysis.py` → `POST /api/analyze/{id}`，装配在 `app/api/__init__.py` 的 `api_router`（前缀 `/api`）。
- 状态流转：`pending` →(开始)→ `processing` →(成功)→ `completed` / (失败)→ `failed`。
- Phase 2C-0 仅为基础设施：Provider 模式与占位；2C-1 打通真实 DeepSeek + 规则降级 + 状态闭环。

## 7. 采集调度单例与数据完整性（Phase 7）

### 7.1 调度单例（根因治理：杜绝"定时采集触发两次"）

- **根因**：多后端实例（如 :8000 与 :8011 同时运行）各自启动 APScheduler，导致每个整半点采集作业被触发两次，同文章被各实例各插一遍 → 重复舆情。
- **机制**：`app/core/scheduler.py` 在 `start_scheduler()` 时通过 `pg_try_advisory_lock(<key>)` 竞争 **PostgreSQL 会话级咨询锁**（key 由 `sha1("opinion-platform-scheduler-singleton")` 派生）。
  - 抢到锁的进程 → 正常启动采集/预警调度器；
  - 未抢到锁的进程 → 打印 `本进程未获得 scheduler 单例锁…跳过启动采集/预警调度器`，**其余功能（API、手动采集）不受影响**；
  - 锁随会话保持，进程退出/崩溃后由 PG 自动释放；`stop_scheduler()` 显式 `pg_advisory_unlock`。
- **验证**：pg_locks 中 advisory lock 恰好 1 个持有者；未持锁实例日志明确"跳过"；锁生效后每整半点仅 1 个采集批次。

### 7.2 数据库约束（纵深防御）

| 约束 | 类型 | 迁移 | 作用 |
| --- | --- | --- | --- |
| `ix_opinions_url_unique` | 部分唯一索引（`url<>''` 唯一） | `p6urluniq01` | 阻挡同 url 舆情重复入库 |
| `uq_event_opinions_event_opinion` | 唯一约束（`event_id`, `opinion_id`） | `p7evtuniq01` | 阻挡同一事件重复挂载同一舆情 |

### 7.3 运维纪律

- 生产库修改前**必须** `pg_dump` 备份（见 `backup/`）。
- 清理/迁移均在受控事务或 Alembic 内执行，禁止直接 `DELETE` 未验证数据。
- 调度单例依赖单实例部署；多实例环境下由 advisory lock 抑制双触发，但**推荐单实例**以消除资源浪费与理论竞态窗口。
