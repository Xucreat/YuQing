# API 设计（api.md）

> 基础前缀：`/api`。鉴权：Bearer JWT（仅 admin）。生产由前端 nginx 反代。

## 1. 登录

`POST /api/login`（**全站唯一公开接口，无需鉴权**）

请求：
```json
{ "username": "admin", "password": "admin123" }
```

响应（简单 JWT）：
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

- 用户名或密码错误返回 `401 { "detail": "Incorrect username or password" }`。
- 成功后在其它 `/api` 接口的 `Authorization: Bearer <token>` 中携带。
- 约束：仅支持一个 admin 用户；无 OAuth、无 refresh token、无 RBAC。

- 该接口**无需鉴权**（全站唯一公开接口）。
- 用户名或密码错误返回 `401 { "detail": "Incorrect username or password" }`。
- 成功后其它 `/api` 接口在 `Authorization: Bearer <token>` 中携带。

## 2. 舆情列表

`GET /api/opinions`（**需 Bearer JWT**）

查询参数：`page`(默认1)、`size`(默认20，最大100)、`source`、`risk_level`、`keyword`。

- `source`：来源精确匹配。
- `risk_level`：**映射到 `opinions.sentiment` 精确匹配**（positive/negative/neutral）。
  因 `opinions` 表无 `risk_level` 列（按约束不改动库结构），沿用情感字段表达风险等级。
- `keyword`：对 `keywords`/`title`/`content` 做模糊匹配（ILIKE）。

响应：
```json
{
  "total": 120,
  "page": 1,
  "size": 20,
  "items": [ { "id": 1, "title": "...", "source": "...", "publish_time": "...", "risk_score": 70, "sentiment": "negative", "keywords": "消防,事故" } ]
}
```

## 3. 舆情详情

`GET /api/opinions/{id}`（**需 Bearer JWT**）

响应：完整 `opinions` 行（id/title/content/source/url/publish_time/region_id/risk_score/sentiment/summary/keywords/created_at）。

不存在：`404 { "detail": "Opinion not found" }`。

## 3.1 创建舆情

`POST /api/opinions`（**需 Bearer JWT**，供未来 Collector 写入）

请求体：`title`、`content`、`source`、`url`、`publish_time`(可空)、`region_id`。
`region_id` 必须存在，否则 `404 { "detail": "Region not found" }`。

创建后服务端填充：`risk_score=0`、`sentiment="neutral"`（AI 阶段再更新）。

## 3.2 删除舆情

`DELETE /api/opinions/{id}`（**需 Bearer JWT**，MVP 保留）

成功：`200 { "detail": "Opinion deleted", "id": <id> }`；不存在：`404 { "detail": "Opinion not found" }`。

## 4. AI 分析（Phase 2C-1 已实现）

### 4.1 单条舆情 AI 分析

`POST /api/analyze/{id}`（**需 Bearer JWT**）

对指定舆情触发 **单条 AI 分析闭环**，更新并返回完整 `Opinion`。

流程：
1. 查询 `Opinion`，不存在 → `404 { "detail": "Opinion not found" }`
2. 置 `analysis_status="processing"` 并提交
3. 调用 `AIService.analyze(title, content)`（内部：有 Key 先 `DeepSeekProvider`，未配置/异常自动降级 `RuleFallbackProvider`）
4. 成功：`summary`/`sentiment`/`risk_score`/`keywords`(逗号拼接写入 TEXT)/`analysis_suggestion` 写库，`analysis_status="completed"`、`analysis_time=now()`；返回 `200` + 完整 `OpinionOut`
5. 失败：`analysis_status="failed"`（保留失败状态），返回 `500 { "detail": "AI 分析失败，请稍后重试" }`

请求：无请求体（`{id}` 为路径参数，整数）。

响应（成功，`200`）：
```json
{
  "id": 1,
  "title": "某小区发生火灾",
  "content": "某小区发生火灾，群众质疑消防响应速度",
  "summary": "舆情摘要……",
  "sentiment": "negative",
  "risk_score": 80,
  "keywords": "火灾,消防",
  "analysis_suggestion": "建议关注事件发展趋势，加强相关部门信息核查……",
  "analysis_status": "completed",
  "analysis_time": "2026-07-16T06:00:00Z"
}
```

错误：
- `401`：未携带/无效 Bearer Token。
- `404`：`Opinion not found`（舆情不存在）。
- `500`：AI 调用失败，`analysis_status` 置为 `failed`（结果仍可从详情接口查到）。

> 约束（本阶段）：仅「手动触发单条分析」。不做批量 / 定时 / Celery / Redis / Collector / 自动采集 / Event 聚合。业务 API **不直接调用** DeepSeek，统一经 `AIService` 调度。

### 4.2 AI 结果 Schema（类型化领域对象）

`app/schemas/ai.py` 定义 `AIAnalysisResult`：
- `summary: str`
- `sentiment: Literal["positive","negative","neutral"]`
- `risk_score: int`（Pydantic v2 校验 `0 <= risk_score <= 100`）
- `keywords: list[str]`
- `suggestion: str`

Provider 层与 `AIService` 均返回 `AIAnalysisResult`（不放 dict）；API 层通过 `OpinionOut` 序列化输出。

> 状态：Phase 2C-0 仅完成 AI 基础设施——`AIService` 目录与 Provider 模式、`DeepSeekProvider` 配置占位、`RuleFallbackProvider` 降级骨架——**尚未暴露任何 AI 分析接口**，也未调用 DeepSeek。Phase 2C-1 打通真实 DeepSeek 调用 + 规则降级 + 状态流转闭环。

## 5. Dashboard 统计（Phase 2B 已实现）

`GET /api/dashboard/stats`（**需 Bearer JWT**）

请求方式：`GET`；鉴权：Bearer；无请求体/查询参数。

响应（驾驶舱统计总览）：
```json
{
  "total": 100,
  "today": 10,
  "high_risk": 5,
  "trend": [ { "date": "2026-07-10", "count": 5 } ],
  "keywords": [ { "word": "消防", "count": 30 } ]
}
```

字段说明：

- `total`：全部舆情数量（`count(opinions.id)`）。
- `today`：**今日新增**，依据 `created_at`（非 `publish_time`）。
- `high_risk`：高风险数量，口径 `risk_score >= 70`（常量 `HIGH_RISK_THRESHOLD`，集中在 `dashboard_service.py`，便于调整；**不**使用 `sentiment`）。
- `trend`：最近 7 日趋势，按日期分组（`cast(created_at,date)`），**无数据日期补齐 `count=0`**；长度恒为 7。
- `keywords`：`opinions.keywords`（TEXT，逗号分隔如 `消防,事故`）拆分后统计的 **TOP 10**（最多 10 条）。

> 注：原规划文档中的 `today_new` / `event_count` / `trend_7d` / `top_keywords` 为早期占位字段名，**实际实现以本节字段名为准**（`today` / `high_risk` / `trend` / `keywords`）。`event_count` 与 AI 相关统计属后续 Phase（2C）。

统计逻辑集中在 `app/services/dashboard_service.py`，API 层（`app/api/dashboard.py`）只做鉴权 + 调用 + 序列化，不直接写 SQL 聚合。日期口径统一使用数据库原生日期函数（`current_date` / `cast(... as date)`），规避 Python 侧时区与 naive TIMESTAMP 列的歧义。

## 6. 事件聚合 API（Phase 3C-0 已实现）

> 基础前缀 `/api`，全部接口 **需 Bearer JWT**（与 Collector 同源鉴权）。
> 仅「手动触发一次聚合」+「事件列表查询」。不做定时 / Celery / Redis / MQ / AI 聚类 / 前端。

### 6.1 手动触发聚合

`POST /api/events/aggregate`（**需 Bearer JWT**）

执行一次规则聚合：读取最近 `event_window_days`(默认 7) 天内、`analysis_status="completed"` 且 `keywords` 非空的 Opinion → 按 `region_id` 分组 → 组内 `keywords` 交集做连通分量聚类（O(n²)，MVP 数据量可接受）→ 每组匹配既有 Event（按 `keyword` 交集）或新建 → 显式 `EventOpinion(event_id, opinion_id)` 关联。

请求：无请求体。

响应（`200`）：
```json
{
  "success": true,
  "created": 3,
  "updated": 1,
  "linked": 12
}
```

字段说明：
- `created`：本次**新建** Event 数。
- `updated`：本次被**追加关联**的既有 Event 数（至少新增 1 条关联才计入）。
- `linked`：本次**新建** `event_opinions` 关联行数（幂等：重复执行返回 0）。

### 6.2 事件列表（分页）

`GET /api/events`（**需 Bearer JWT**）

查询参数：`page`(默认 1)、`size`(默认 20，**最大 100**)。排序：`id DESC`。

响应（`200`）：
```json
{
  "items": [
    {
      "id": 1,
      "title": "某小区火灾舆情",
      "risk_level": "high",
      "opinion_count": 14,
      "status": "active",
      "first_time": "2026-07-10T08:00:00Z",
      "last_time": "2026-07-15T20:00:00Z"
    }
  ],
  "total": 30,
  "page": 1,
  "size": 20
}
```

字段说明：
- `status`：**固定返回 `"active"`**，仅存在于 API 序列化层（Event Model 无 `status` 列）。
- `title`：该 Event 下 `risk_score` 最高的 Opinion 标题。
- `risk_level`：`max(opinion.risk_score)` 映射：`>=70→high` / `>=40→medium` / 否则 `low`。
- `opinion_count`：关联舆情数（经 `event_opinions` 实时统计）。
- 事件关联经 `event_opinions` 表；新增关联一律显式创建，不修改关联表结构（无 `created_at`/唯一约束）。

错误：
- `401`：未携带/无效 Bearer Token。

## 7. 健康检查

`GET /health`

```json
{ "status": "ok" }
```

## 8. Collector 采集接口（Phase 3A + Phase 3B 政府网站真实采集）

> 基础前缀 `/api`，全部接口 **需 Bearer JWT**。
> 仅「手动触发一次采集」；不做定时 / Celery / Redis / 前端。事件聚合为独立接口，见 §6。

### 8.1 触发采集 + 自动 AI 分析

`POST /api/collector/run`（**需 Bearer JWT**）

一次执行完整闭环：`Collector.fetch()` → 按 `url` 去重 → 新建 `Opinion`(pending) → `AIService.analyze` → 写回字段 + 状态流转(completed/failed)。

请求：无请求体。

响应（`200`）：
```json
{
  "success": true,
  "created": 20,
  "analyzed": 20,
  "failed": 0,
  "message": "采集完成",
  "collector_type": "government"
}
```

字段说明：
- `created`：本次**实际新增** `Opinion` 数量（去重后）。
- `analyzed`：AI 分析成功（`completed`）数量。
- `failed`：`created - analyzed`；失败记录**保留在数据库**，`analysis_status="failed"`（单条失败不影响其余数据）。
- `collector_type`：本次**采集方式**（`government` / `mock`）。⚠️ 表示采集方式，**与 `Opinion.source`（新闻来源，如"大厂县政府网站"）是两个不同概念，勿混淆**；本接口刻意**不**返回 `source` 字段。

#### 8.1.1 政府采集 5 秒防抖（`429 Too Many Requests`）

当采集方式为 `government` 时，服务端启用 **5 秒防抖**（`THROTTLE_SECONDS=5.0`，模块级内存时间戳）：距上次成功政府采集不足 5 秒再次触发，返回 `429`（**不再抛 500**）：

```json
{
  "success": false,
  "message": "collector running too frequently",
  "collector_type": "government"
}
```

`mock` 采集方式不触发防抖。

### 8.2 查询采集状态（内存，重启丢失）

`GET /api/collector/status`（**需 Bearer JWT**）

```json
{ "last_run": "2026-07-16T06:00:00Z", "total_collected": 20, "collector_type": "government" }
```

- `last_run`：最近一次采集时间（无则 `null`）。
- `total_collected`：本进程内累计采集数。
- `collector_type`：最近一次采集方式（`government` / `mock`，无则 `null`）。
- ⚠️ **Phase 3A 临时实现**：状态存**模块级内存变量**，重启丢失、不持久化；未来若增加定时采集，再设计 `collector_runs` 表。

### 8.3 Collector 数据源

采集方式由 `settings.collector_type`（Pydantic Settings，默认 `government`；测试默认 `mock`）决定，`resolve_collectors()` 据此选用采集器；三种采集器均可独立使用。

- `GovernmentCollector`（**Phase 3B 真实数据源**）：采集河北廊坊大厂回族自治县人民政府网站（`https://www.lfdc.gov.cn/`，JEECMS 站点）。栏目 URL 由 `settings.gov_news_urls`（Pydantic Settings，`.env` 逗号分隔加载，默认 `jrdc.jhtml`/`gggs.jhtml`）配置。`requests` + `beautifulsoup4(html.parser)` 解析：列表页选 `a[href*='.jhtml']`，用 `_ARTICLE_PATH_RE=/\d+\.jhtml$` 过滤导航链接仅留真实文章；正文多级降级（`div.content`→…→所有 `<p>`→`body` 前 500 字）。`source="大厂县政府网站"`。**反爬克制**：单次 `MAX_ARTICLES=20` 篇、请求间隔 `REQUEST_INTERVAL=0.3s`、`TIMEOUT=10`、不递归/不抓附件/不绕过反爬；网络失败/超时/HTTP 错误 → 返回 `[]`（不判失败）。
- `MockCollector`：生成 ≥50 条围绕大厂县的演示舆情（正常/中风险/高风险三档），离线可演示。其 `url` 唯一，作为去重主键。高风险项内置敏感词（火灾/事故/群体/死亡/谣言），保证无 DeepSeek Key 时 `RuleFallbackProvider` 也能产出 `negative` + `risk_score>=70` + 非空 `keywords`。
- `RSSCollector`：**可扩展接口**。仅当配置 `RSS_URLS`（环境变量，逗号分隔）非空时才惰性导入 `feedparser` 并解析；未配置/为空时**不加载 feedparser、不执行网络请求**，直接返回 `[]`。本阶段不实现真实爬虫（Scrapy/Playwright 等禁止）。

### 8.4 去重与失败隔离

- **去重**：以 `opinions.url` 为唯一判断；`url` 已存在则跳过不重复创建。`url` 为空时退回 `title + publish_time` 辅助判断。
- **失败隔离**：单条 AI 异常仅该 `Opinion` 置 `failed`（记录保留），其余数据正常 `completed`；`failed = created - analyzed`。

错误：
- `401`：未携带/无效 Bearer Token。
- `429`：政府采集触发过于频繁（5 秒防抖，见 8.1.1）。
