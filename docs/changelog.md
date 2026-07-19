# 变更日志（changelog.md）

## [0.1.0] - 2026-07-16

### Phase 0 - 项目初始化

- 创建项目目录结构（`backend/app` 分层、`frontend/src` 分层、`docs`）。
- 新增 `docker-compose.yml`（postgres / backend / frontend 三服务）。
- 新增部署配置：`backend/Dockerfile`、`backend/requirements.txt`、`frontend/Dockerfile`、`frontend/nginx.conf`、`frontend/package.json`、`vite.config.ts`、`tsconfig*.json`、`.env.example`。
- 新增文档体系：`docs/`（agent / product_scope / architecture / decision_log / database / api / changelog / claude_log）。
- 新增 `README.md` 与 `agent.md`。
- 后端 `main.py` 骨架，提供 `/health` 健康检查。
- 前端路由 / store / api / 类型 / 5 个页面骨架（占位）。

> 后续 Phase 将在此追加记录。

## [0.1.0] - 2026-07-16（补充 Phase 1）

### Phase 1 - Backend 基础工程

- **数据库连接**：SQLAlchemy 2.0 + psycopg v3 驱动（`postgresql+psycopg://`）。
- **ORM 模型**：User / Region / Opinion / Keyword / Event / EventOpinion（含 M2M 关联表）。
- **Alembic 手写初始迁移** `0001_initial`，`env.py` 绑定 metadata 与配置（`compare_type=True`）。
- **初始化脚本** `scripts/init_db.py`：幂等写入 `admin/admin123` 与 大厂回族自治县（131028）。
- **安全模块**：bcrypt 密码哈希 + 简单 JWT（无 OAuth / refresh token / RBAC）。
- **docker-compose 后端启动链**：`alembic upgrade head && init_db && uvicorn`，容器启动即建表 + 种子。
- **main.py** 仅保留 `/health`（业务 API 在 Phase 2 实现）。

## [0.1.0] - 2026-07-16（补充 Phase 2A）

### Phase 2A - 认证系统 + 舆情基础 API

- **Schemas（Pydantic v2）**：`app/schemas/user.py`（`LoginRequest`/`Token`/`UserOut`）、`app/schemas/opinion.py`（`OpinionBase`/`OpinionCreate`/`OpinionOut`/`OpinionListResponse`），统一经 Pydantic 序列化，不直接返回 ORM。
- **认证模块**：`core/security.py` 新增 `decode_access_token()`；新增 `core/dependencies.py` 的 `get_current_user()`（Bearer JWT 校验 → 查 User → 返回，缺失/非法 `401`）。
- **登录**：`app/api/auth.py` `POST /api/login`，bcrypt 校验 + 签发 HS256 JWT，返回 `{access_token, token_type:"bearer"}`；错误凭据 `401`。
- **Opinion 基础 CRUD**（`app/api/opinions.py`，全部 `Depends(get_current_user)` 保护）：
  - `GET /api/opinions`：分页（size 最大 100）+ `source`/`risk_level`→`sentiment`/`keyword` 过滤。
  - `GET /api/opinions/{id}`：完整舆情，404 `Opinion not found`。
  - `POST /api/opinions`：创建（供未来 Collector），默认 `risk_score=0`/`sentiment="neutral"`；`region_id` 不存在 `404 Region not found`。
  - `DELETE /api/opinions/{id}`：删除（MVP 保留），404 `Opinion not found`。
- **路由注册**：`app/api/__init__.py` 聚合，`main.py` 以 `prefix="/api"` 挂载，保留 `/health`。
- **测试**：`tests/conftest.py` + `tests/test_auth_opinions.py`，pytest **9 passed**（登录成功/失败、列表需认证、创建默认 0+neutral、详情 404、删除、错误 region 404）。
- **文档**：`docs/api.md` 增 login 与 opinions 接口；`docs/claude_log.md` 记 Phase 2A。

## [0.1.0] - 2026-07-16（Phase 2B）

### Phase 2B - Dashboard 统计 API + 数据分析基础服务

- **Schemas（Pydantic v2）**：`app/schemas/dashboard.py`（`TrendItem`/`KeywordItem`/`DashboardStatsResponse`），不直接返回 dict/ORM。
- **Service 层（统计逻辑唯一归属）**：`app/services/dashboard_service.py` 的 `get_dashboard_stats(db)`；常量 `HIGH_RISK_THRESHOLD=70`、`TREND_DAYS=7`、`TOP_KEYWORDS=10`。
  - `total=count(*)`；`today=count(created_at 当日)`；`high_risk=count(risk_score>=70)`；`trend` 近 7 日分组并补齐零值；`keywords` 取 `opinions.keywords` 逗号拆分后 `Counter.most_common(10)`。
  - 全部为聚合/批量查询，无 N+1；日期口径统一使用数据库原生日期函数（`current_date`/`cast(... as date)`），规避 Python 侧时区歧义。
- **API 层**：`app/api/dashboard.py` `GET /api/dashboard/stats`（`Depends(get_current_user)` 鉴权，`response_model=DashboardStatsResponse`），只做鉴权 + 调 service + 序列化，不直接写 SQL 聚合。
- **路由注册**：`app/api/__init__.py` 聚合新增 `dashboard_router`；`main.py` 保持 `/api` 前缀 + `/health` 不变。
- **测试**：`tests/test_dashboard.py`（`fresh_opinions` 夹具清空测试库 opinions 表，不触碰生产种子）；pytest **16 passed**（含 Phase2A 9 + health 1 + 本阶段 6）。
- **文档**：`docs/api.md` 更新 `GET /api/dashboard/stats`（请求方式/鉴权/返回示例/字段口径）；`docs/claude_log.md` 记 Phase 2B。

## [0.1.0] - 2026-07-16（Phase 2C-0）

### Phase 2C-0 - AI 分析基础设施准备（不接入模型）

- **Opinion 模型增强**：新增 `analysis_status`（VARCHAR(16)，默认 `pending`，CHECK 约束限定 pending/processing/completed/failed）与 `analysis_time`（TIMESTAMP nullable，记录分析完成时间）；保留全部原有字段（risk_score/sentiment/summary/keywords 等）。
- **Alembic 迁移**：新增手写迁移 `0002_add_opinion_analysis_status.py`（`down_revision=0001_initial`），`upgrade` 经 `server_default='pending'` 安全地加 NOT NULL 列 + 加 `analysis_time` + 建 CHECK 约束 `ck_opinions_analysis_status`；`downgrade` 逆向删除。已验证 `alembic upgrade head` 成功（head=0002）。
- **Schema 同步**：`app/schemas/opinion.py` 的 `OpinionOut` 增加 `analysis_status`(默认 pending) 与 `analysis_time`(Optional)，API 响应包含 AI 状态字段。
- **AI Service 基础架构**（`app/services/ai/`）：
  - `providers/base.py`：`BaseAIProvider`（ABC，`analyze` 抽象方法，统一输出结构）。
  - `providers/deepseek.py`：`DeepSeekProvider` —— **仅读取配置**（API Key / Base URL / Model），`is_configured` 属性；`analyze` 显式 `raise NotImplementedError`，**未发起任何调用**。
  - `fallback.py`：`RuleFallbackProvider` —— 返回 TODO 结构（summary/sentiment/risk_score/keywords 占位）。
  - `service.py`：`AIService` 统一管理 `DeepSeekProvider` + `RuleFallbackProvider`，`analyze(text)` 当前返回 Fallback 的 TODO 结果。
  - 业务代码统一经 `AIService.analyze()`，禁止直连 Provider。
- **配置**：`app/core/config.py` 已含 `deepseek_api_key` / `deepseek_base_url` / `deepseek_model`，本阶段不重复增加。
- **测试**：新增 `tests/test_ai_service.py`（AIService 可实例化 / Fallback 可调用 / DeepSeek 缺配置不报错 / DeepSeek.analyze 未实现抛 NotImplementedError / Opinion 新 AI 字段经 API 详情与 ORM 往返可读）。pytest **22 passed**（含 Phase2A 9 + Phase2B 6 + health 1 + 本阶段 6）。
- **未新增任何 API**：AI 分析接口（`POST /api/analyze/{id}`）留待 Phase 2C-1。
- **文档**：`docs/database.md`（Opinion AI 字段 + CHECK）、`docs/architecture.md`（§6 AI 分层架构）、`docs/api.md`（§4 注明延后）、`docs/claude_log.md` 记 Phase 2C-0。
- **约束遵守**：未修改 frontend / 数据库结构 / Alembic 既有迁移 / Docker 配置；未调用 DeepSeek、未实现 AI 摘要/情感/风险评分/Collector/Event 聚合；保持 PostgreSQL only。

## [0.1.0] - 2026-07-16（Phase 2C-1）

### Phase 2C-1 - 单条舆情 AI 分析闭环（真实 DeepSeek + 规则降级）

- **AI 结果 Schema（类型化领域对象）**：新增 `app/schemas/ai.py` 的 `AIAnalysisResult`（summary:str / sentiment:Literal[positive,negative,neutral] / risk_score:int 经 Pydantic v2 校验 0-100 / keywords:list[str] / suggestion:str）。Provider 层与 `AIService` 均返回该类型（不放 dict）；API 层经 `OpinionOut` 序列化。
- **Opinion 模型与 Schema 增强**：`app/models/opinion.py` 新增 `analysis_suggestion`（TEXT nullable）；`app/schemas/opinion.py` 的 `OpinionOut` 增加 `analysis_suggestion: Optional[str]=None`（沿用既有 analysis_status/analysis_time）。
- **Alembic 迁移 0003**：`0003_add_analysis_suggestion.py`（`down_revision="0002_add_opinion_analysis_status"`），`opinions` 加 `analysis_suggestion` TEXT nullable；`downgrade` 逆向可回滚。
- **DeepSeekProvider 真实调用**（`app/services/ai/providers/deepseek.py`）：OpenAI SDK 兼容（`from openai import OpenAI`），配置全部来自 `settings`（api_key/base_url/model，禁止硬编码）。system prompt「公安互联网舆情分析专家」+ user prompt（标题/正文 + 强约束 JSON 结构）；`response_format={"type":"json_object"}`。**JSON 解析兼容 ```json 代码块**：`_strip_code_fence` 去围栏 → `json.loads` → `AIAnalysisResult.model_validate`；任何异常（未配置/网络/解析/校验）一律上抛，由 `AIService` 捕获降级。
- **RuleFallbackProvider 真正落地规则分析**（`app/services/ai/fallback.py`，沿用既有路径）：内置 `DEFAULT_KEYWORDS`（`(词,权重)` 表）。`__init__(keywords=None)` 空则退回内置表（MVP 默认走内置）。`analyze(text)->AIAnalysisResult`：命中敏感词 `risk_score = 20 + Σ(10*weight)` 封顶 100；`risk>=70 → negative` 否则 `neutral`；`summary`/`suggestion` 模板；返回命中词列表。
- **AIService 调度**（`app/services/ai/service.py`）：`analyze(title, content)->AIAnalysisResult`，内部拼 `text` 委托 `provider.analyze(text)`（保留既有 `analyze(text)` 接口）。有 Key 先 `DeepSeekProvider`，未配置或任何异常降级 `RuleFallbackProvider`。**AIService 不直接查数据库**，敏感词经构造参数注入 `RuleFallbackProvider`。
- **新增分析 API**（`app/api/analysis.py` + 注册 `app/api/__init__.py` 的 `api_router`，最终路径 `POST /api/analyze/{id}`）：`Depends(get_current_user)` 保护。流程：① `db.get(Opinion,id)`，不存在 `404 "Opinion not found"`；② 置 `analysis_status="processing"` 提交；③ 调 `AIService().analyze(title,content)`；④ 成功写 `summary/sentiment/risk_score/keywords(逗号拼接)/analysis_suggestion` + `analysis_status="completed"` + `analysis_time=now(utc)`；失败 `analysis_status="failed"`（保留失败状态）并返 `500`。业务 API 不直接连 DeepSeek。
- **keywords 种子化（仅数据）**（`scripts/init_db.py`）：幂等写入默认敏感词（含权重），使 `keywords` 表可被未来扩展读取；MVP fallback 仍用内置 `DEFAULT_KEYWORDS`（经构造参数注入）。不改表结构。
- **测试**：新增 `tests/test_ai_analysis.py`（无 Key 自动 fallback 返 `AIAnalysisResult` 且 `risk_score>0`；含敏感词 fallback `risk>0/status=completed`；API 成功返 summary/risk_score/sentiment/analysis_suggestion 且 `status=completed`；异常模拟 → `status=failed` + `500`；DeepSeek 解析去代码块+校验、非法 JSON 上抛；鉴权 401 / 不存在 404）。重写 Phase 2C-0 旧测试 `test_ai_service.py` 两条为类型化断言（`AIAnalysisResult`）。pytest **31 passed**。
- **验证**：`alembic upgrade head` 0001+0002+0003 全过（head=0003）；`init_db.py` 种子 admin + 131028 + 敏感词；`psql \d opinions` 确认 `analysis_suggestion` 列存在。
- **文档**：`docs/database.md`（analysis_suggestion）、`docs/api.md`（§4 POST /api/analyze/{id} 完整请求/响应/错误 + AIAnalysisResult 领域对象）、`docs/architecture.md`（§5/§6 AI 调用边界与闭环）、`docs/claude_log.md`（DeepSeek 接入/Prompt/JSON 解析/Fallback/踩坑）、`docs/changelog.md`（本段）。
- **约束遵守**：未修改 frontend / 数据库结构（仅新增 analysis_suggestion 迁移）/ Alembic 既有 0001/0002 / Docker 配置；未实现 Collector / RSS / Celery / Redis / 定时 / 批量 / Event 聚合 / 用户权限扩展；保持 PostgreSQL only。仅做「单条手动触发 AI 分析」。

## [0.1.0] - 2026-07-16（Phase 3A）

### Phase 3A - Collector 数据采集层 + 自动入库闭环

- **Collector 骨架填充**（`app/collectors/`）：
  - `mock_collector.py`：`MockCollector` 生成 **50 条**大厂县舆情（正常 30 / 中风险 15 / 高风险 5），每条带唯一 `url`（`https://mock.dachang.gov/opinion/{i}`）作为去重主键；高风险项内置敏感词（火灾/事故/群体/死亡/谣言），保证无 DeepSeek Key 时 `RuleFallbackProvider` 也能产出 `negative` + `risk_score>=70` + 非空 `keywords`。
  - `rss_collector.py`：`RSSCollector` 仅完成**可扩展接口**；`feeds` 为空（或 `RSS_URLS` 环境变量未配置）→ **不加载 feedparser、不联网**，返回 `[]`；仅当源非空才**惰性 `import feedparser`** 并解析。本阶段不实现真实爬虫（Scrapy/Playwright 等禁止）。
  - `service.py`（新建）：`CollectorService.collect_and_analyze(db)` 实现闭环——`fetch()` → 按 `url` 去重（url 空则 `title+publish_time`）→ 建 `Opinion`(pending) → `AIService.analyze` → 写回 + 状态流转。
- **复用 AIService（不重构）**：`CollectorService` 直接调用 `AIService.analyze(title, content)`，与手动分析 API（`POST /api/analyze/{id}`）共用分析能力；未抽取公共 helper、未修改 `app/api/analysis.py`；已在 `service.py` 标注 `TODO Phase 4` 待统一抽取。
- **去重策略**：以 `opinions.url` 为唯一判断；已存在则跳过不重复创建；`url` 为空时退回 `title + publish_time` 辅助判断。
- **失败隔离**：单条 AI 异常仅该 `Opinion` 置 `analysis_status="failed"`（**保留数据库记录**），其余正常 `completed`；`failed = created - analyzed`。每条先 `commit()`（pending）再分析，确保失败记录不丢失。
- **采集状态（内存，临时）**：模块级变量 `_COLLECTOR_STATUS = {"last_run": None, "total_collected": 0}`，重启丢失、不持久化；代码注释与 docs 均注明 **Phase 3A temporary implementation；Persistent collector task history is postponed；未来定时采集再设计 `collector_runs` 表**。
- **Schemas（Pydantic v2）**：`app/schemas/collector.py` → `CollectorRunResponse`(success/created/analyzed/failed/message)、`CollectorStatusResponse`(last_run/total_collected)。
- **API（`app/api/collector.py` + 注册 `app/api/__init__.py` 的 `api_router`，`prefix="/collector"`）**：
  - `POST /api/collector/run`（Bearer JWT）：触发一次采集 + 自动 AI 分析闭环，返回 `created`/`analyzed`/`failed`。
  - `GET /api/collector/status`（Bearer JWT）：返回内存采集状态。
  - 均 `Depends(get_current_user)` 保护。
- **依赖**：`requirements.txt` 新增 `feedparser==6.0.11`（惰性导入，未配置 `RSS_URLS` 时不加载、不联网）。
- **测试**：新增 `tests/test_collector.py`（6 项，真实 PG `opinion_test`）：MockCollector ≥50 条且高风险项 fallback 产出 negative/risk≥70/keywords 非空；API 首次运行创建（created≥50，analyzed==created）；二次运行 url 去重不重复（created==0）；AI 失败单条 failed 不影响其他（created=3/analyzed=2/failed=1，库内记录保留）；API 无 token → 401；API 返回 created/analyzed 正确 + `/status` 结构与鉴权。pytest **37 passed**（含 Phase 2C-1 31 + 本阶段 6）。
- **约束遵守**：未修改 frontend / 数据库结构 / **Alembic 仍为 0003（无新迁移）** / Docker 配置 / 项目目录结构；未实现定时任务 / Celery / Redis / ES / Event 聚合 / 多租户 / 权限扩展 / 真实爬虫。保持 PostgreSQL only。仅做「手动触发一次采集 + 自动 AI 分析」。

## [0.1.0] - 2026-07-16（Phase 3B）

### Phase 3B - Government Website Collector（真实政府网站数据源）

- **`GovernmentCollector`（新建 `app/collectors/government_collector.py`）**：采集河北廊坊大厂回族自治县人民政府网站（`https://www.lfdc.gov.cn/`，JEECMS 站点），`source_name="大厂县政府网站"`。`requests`(Session + 浏览器 UA + `apparent_encoding` 防乱码) + `beautifulsoup4(html.parser)`：`_parse_list` 选 `a[href*='.jhtml']` → `urljoin` 转绝对 → `_ARTICLE_PATH_RE=/\d+\.jhtml$` 过滤导航链接仅留真实文章；`_parse_detail` 正文多级降级（`div.content`→`article-content/text/TRS_Editor`→`Zoom/article_con`→`article`→所有 `<p>`→`body` 前 500 字）。**反爬克制**：`MAX_ARTICLES=20`、`REQUEST_INTERVAL=0.3s`、`TIMEOUT=10`、不递归/不抓附件/不绕过反爬；网络失败/超时/HTTP 错误 → 返回 `[]`（不判失败）。
- **配置化（Pydantic Settings，禁用 os.getenv）**（`app/core/config.py`）：新增 `collector_type: str = "government"`、`gov_news_urls: List[str]`（默认 `jrdc.jhtml`/`gggs.jhtml`，`.env` 逗号分隔加载，`field_validator(mode="before")` 支持字符串）。三种采集器（mock/rss/government）均可独立使用。
- **CollectorService 配置化选择 + 5 秒防抖**（`app/collectors/service.py`）：新增 `resolve_collectors(collector_type)`（government/mock）、`CollectorService(collector_type=...)`、`_uses_government()`；`CollectorRunResult`/`_COLLECTOR_STATUS` 加 `collector_type`。新增 `_GOV_LAST_RUN_AT` + `THROTTLE_SECONDS=5.0` + `class CollectorThrottled` + `reset_gov_throttle()`：government 采集距上次不足 5 秒 → 抛 `CollectorThrottled`。
- **API 返回 collector_type（不加 source）**（`app/schemas/collector.py` + `app/api/collector.py`）：`CollectorRunResponse`/`CollectorStatusResponse` 加 `collector_type`；`POST /api/collector/run` 捕获 `CollectorThrottled` → **`429 Too Many Requests`** + `{success:false, message:"collector running too frequently", collector_type:"government"}`（**不再 500**）。注释强调 `Opinion.source`（新闻来源）与 API `collector_type`（采集方式）勿混淆。
- **依赖**：`requirements.txt` 新增 `requests==2.32.3`、`beautifulsoup4==4.12.3`。
- **测试隔离**：`tests/conftest.py` import app 前 `os.environ.setdefault("COLLECTOR_TYPE","mock")`（测试默认 mock、不联网）。
- **测试**：新增 `tests/test_government_collector.py`（8 项，全离线 mock HTML）：栏目页解析、相对→绝对 URL、网络异常隔离、详情正文三种降级、Service 集成、去重、API 返回 collector_type、配置切换。pytest **45 passed**（既有 37 + 本阶段 8）。
- **验证**：`alembic current`/`heads` 仍为 **0003（无新迁移）**；OpenAPI 确认 `CollectorRunResponse` 含 `collector_type` 且无 `source`；429 防抖端到端（run1=200 created=1 / run2=429）；真实站点烟测 `created=20, analyzed=20, failed=0` 全 `completed`、`source=大厂县政府网站`。
- **约束遵守**：未修改 frontend / 数据库结构 / **Alembic 仍为 0003（无新迁移）** / Docker 配置 / Dashboard / AIService / analysis.py / RSSCollector；未引入 Redis / ES / 队列 / 定时 / 爬虫框架。保持 PostgreSQL only。**已停止，等待下一阶段指令**（未进入 Phase 3C / Event / 前端）。

## [0.1.0] - 2026-07-16（Phase 3C-0）

### Phase 3C-0 - Event Aggregation Foundation（激活既有 Event 基础设施）

> 实施前修正：`events` / `event_opinions` 表已在 `0001_initial` 创建，`Event`/`EventOpinion` Model 已存在。本阶段**不是建表**，而是激活既有 Event 聚合链路（Opinion → EventAggregator → Event）。

- **新建聚合器**（`app/services/event/aggregator.py` + `__init__.py`）：`EventAggregator.aggregate(db) -> {"created","updated","linked"}`。规则聚合（可解释、无 AI / 无聚类 / 无图数据库）：
  - 读取最近 `event_window_days`(默认 7，新增 `settings.event_window_days`) 天内、`analysis_status="completed"`、`keywords` 非空、`created_at` 在窗口内的 Opinion；
  - 按 `region_id` 分组 → 组内 `keywords`（逗号分隔）两两交集做**连通分量聚类**（O(n²)，MVP <10000 可接受）；
  - 每组按 `keyword` 交集匹配既有 Event；无匹配 → 新建 Event（`title`=组内最高 `risk_score` 的 Opinion 标题、`keyword`=组内关键词去重逗号拼接、`risk_level`=max 映射 `>=70 high / >=40 medium / else low`、`opinion_count` / `first_time` / `last_time` 派生、`description`=最高 risk 的 `content[:200]`）；有匹配 → 显式追加关联并重算派生字段。
- **关联硬约束**：新增事件-舆情关联一律经 `EventOpinion(event_id=xxx, opinion_id=xxx)` **显式创建**；**不使用 `relationship.append()`**，不修改 `event_opinions` 表结构（无 `created_at` / 唯一约束）。`_link_all` 先查已关联 `opinion_id` 集合再跳过，保证幂等。
- **`status` 仅序列化层**：`Event` Model 无 `status` 列；API 响应固定返回 `"active"`。
- **Schemas（Pydantic v2）**（`app/schemas/event.py`）：`EventCreateResponse`(success/created/updated/linked)、`EventOut`(id/title/risk_level/opinion_count/status="active"/first_time/last_time)、`EventListResponse`(items/total/page/size)。
- **API（`app/api/events.py` + 注册 `app/api/__init__.py` 的 `api_router`，`prefix="/events"`）**：
  - `POST /api/events/aggregate`（Bearer JWT）：手动触发聚合，返回统计；
  - `GET /api/events`（Bearer JWT）：分页（`page=1,size=20,max=100`）、`id DESC`，每项 `status="active"`。
  - 均 `Depends(get_current_user)` 保护。
- **保留旧 `event_service.py`**：顶部标注 `[DEPRECATED]`，新逻辑统一走 `EventAggregator`，不删除。
- **配置**（Pydantic Settings，`app/core/config.py`）：新增 `event_window_days: int = 7`。
- **测试**：新增 `tests/test_events.py`（8 项，真实 PG `opinion_test`）：Event ORM 持久化、同 keyword→1 Event、异 keyword→2 Event、多 Opinion 关联同一 Event（经 `event_opinions` 验证）、`risk_level` 映射、重复执行幂等、API 聚合返回格式、API 列表分页。pytest **53 passed**（既有 45 + 本阶段 8）。
- **验证**：`alembic heads` 仍为 **0003_add_analysis_suggestion（无新迁移）**；`versions/` 仅 0001/0002/0003；OpenAPI 含 `/api/events`、`/api/events/aggregate`；真实站点烟测同 keyword 形成同一 Event、异 keyword 分离、幂等、分页正确。
- **约束遵守**：未修改 Opinion 表/Model / Collector / GovernmentCollector / AIService / Dashboard / frontend / 已有 migration（0001/0002/0003）；**未新增 migration**；`event_service.py` 仅标记 deprecated 不删；未引入 Redis / ES / MQ / Celery / 定时任务 / AI 聚类 / 图数据库 / 聚类算法 / AI embedding；不使用 `relationship.append()`。保持 PostgreSQL only。**已停止，等待下一阶段指令**（不进入下一阶段）。
