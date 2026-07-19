# Agent 执行日志（claude_log.md）

> 记录 AI Coding Agent 每个 Phase 的实际操作、命令与产物，便于追溯。

## 2026-07-16 — Phase 0 项目初始化

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**操作**：

1. 建立任务清单（TaskCreate）：目录结构、部署配置、docs、README/agent.md。
2. 创建目录树：
   - `backend/app/{api,models,schemas,services,core,utils,collectors,db}`
   - `backend/{alembic/versions,tests,scripts}`
   - `frontend/src/{router,stores,api,views,components,assets,utils,types}`、`frontend/public`
   - `docs`
3. 写入部署与配置：
   - `docker-compose.yml`、`backend/Dockerfile`、`backend/requirements.txt`
   - `frontend/Dockerfile`、`frontend/nginx.conf`、`frontend/package.json`、`vite.config.ts`、`tsconfig*.json`、`index.html`
   - `.env.example`
4. 写入后端骨架：`app/main.py`（含 `/health`）、`core/config.py`、`core/security.py`、`db/session.py`、collectors 抽象与两个子类、services 两个占位、`tests/test_health.py`、alembic 配置。
5. 写入前端骨架：`main.ts`、`App.vue`、路由、store、api 客户端、类型、5 个页面占位、favicon。
6. 写入文档：`docs/agent.md`、`product_scope.md`、`architecture.md`、`decision_log.md`、`database.md`、`api.md`、`changelog.md`、`claude_log.md`。
7. 写入 `README.md`、`agent.md`。

**产物**：完整可运行骨架（Phase 1 起填充业务逻辑）。

**下一步**：等待用户指令进入 **Phase 1（Backend 基础工程）**。

## 2026-07-16 — Phase 1 Backend 基础工程

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**目标**：完成后端基础工程，使 FastAPI + PostgreSQL + SQLAlchemy + Alembic 完整运行。

**完成内容**：

1. **数据库连接**：SQLAlchemy 2.0 `create_engine`（`postgresql+psycopg://`），`SessionLocal` + `get_db` 依赖；驱动采用 psycopg v3（兼容 Python 3.12/3.13）。
2. **ORM 模型**（SQLAlchemy 2.0 风格 `Mapped`/`mapped_column`）：
   - `User`（admin，bcrypt）、`Region`（区域，含 131028 大厂回族自治县）、`Opinion`、`Keyword`、`Event`、`EventOpinion`（M2O + M2M 关联表）。
   - 所有 NOT NULL 列均由 ORM `default` 在写入时填充，库侧不设 `server_default`（避免 autogenerate 误报 diff）。
   - `Opinion.keywords` 用 TEXT 逗号分隔（不用 Array 类型，兼容 PostgreSQL）。
3. **Alembic 迁移**：手写初始迁移 `0001_initial.py`（与 ORM 一致），`env.py` 绑定 `Base.metadata` 与 `settings.database_url`，`compare_type=True`。
4. **初始化数据**：`scripts/init_db.py` 幂等写入 `admin/admin123`（bcrypt）与 region（131028, county），并保留 `Base.metadata.create_all` 安全网。
5. **基础配置**：`core/config.py`（Pydantic Settings，读 `.env`）、`core/security.py`（bcrypt 哈希 + 简单 JWT，无 OAuth/refresh/RBAC）。
6. **main.py** 仅保留 `/health`（业务 API 留待 Phase 2）。
7. **部署**：`docker-compose.yml` 三服务（postgres/backend/frontend）；`backend/Dockerfile` 启动顺序改为 `alembic upgrade head && python scripts/init_db.py && uvicorn`，保证容器启动即建表 + 种子；新增本地 `.env`（gitignore 已忽略）供 `docker-compose` 引用。

**验证（本地，本环境无 Docker）**：

- 下载并运行 PostgreSQL 16 Windows 二进制（端口 5433）做真实联调。
- `alembic upgrade head` → rc=0，创建 6 张业务表 + `alembic_version`（version=0001_initial）。
- `python scripts/init_db.py` → rc=0，写入 admin 与 region。
- `GET /health` → `{"status":"ok"}`。
- `psql` 核对：7 张表齐全，users/admin、regions/131028 存在。

**遇到的问题与决策**：

- 本环境无 Docker → 改用官方 PG16 Windows 二进制做真实数据库联调验证。
- 自带 venv 损坏 → 改用 `pip install --target=<deps>` + `PYTHONPATH`（Windows 用 `;` 分隔，非 `:`）。
- `psycopg2-binary` 无 Python 3.13 wheel → 改用 `psycopg[binary]` v3（与 `postgresql+psycopg://` 一致）。
- `alembic.ini` 含中文注释，本机 gbk 区域下读取报 `UnicodeDecodeError` → 改为 ASCII 注释。
- `alembic.ini` 的 `script_location = alembic` 相对 cwd 解析导致找不到脚本 → 改为 `%(here)s/alembic` 相对 ini 文件自身。
- `python -m alembic` 从含 `alembic/` 配置目录运行时，cwd 会前置并遮蔽真实 alembic 包 → 验证时从项目根目录运行（无 `alembic/` 文件夹）；生产用 `alembic` 控制台脚本（不前置 cwd，无遮蔽）。

**下一步**：等待用户指令进入 **Phase 2（业务 API / 认证 / AI Service / Collector / Event 聚合）**。

## 2026-07-16 — Phase 2A 认证系统 + 舆情基础 API

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**目标**：完成后端基础业务 API（JWT 登录 + 当前用户认证依赖 + Opinion 基础 CRUD 查询），仅 backend，不碰 frontend。

**完成内容**：

1. **Schemas（Pydantic v2，不直接返回 ORM）**
   - `app/schemas/user.py`：`LoginRequest`、`Token`、`UserOut`（`from_attributes=True`）。
   - `app/schemas/opinion.py`：`OpinionBase`、`OpinionCreate`、`OpinionOut`（完整舆情字段）、`OpinionListResponse`（items/total/page/size）。
2. **认证模块**
   - `app/core/security.py` 新增 `decode_access_token()`（JWT 校验，返回 sub）。
   - `app/core/dependencies.py`：`get_current_user()` —— 从 `Authorization: Bearer <token>` 读 JWT，校验（HS256 / secret_key），查 `User` 返回对象；缺失/非法返回 `401`。`HTTPBearer(auto_error=False)` 确保返回 401 而非 403。
   - `app/api/auth.py`：`POST /login`，JSON `{username,password}`，bcrypt 校验 + `create_access_token(subject=user.id)`，返回 `{access_token, token_type:"bearer"}`；错误凭据 `401 "Incorrect username or password"`。
3. **Opinion API（`app/api/opinions.py`，全部 `Depends(get_current_user)` 保护）**
   - `GET /opinions`：分页 `page`(默认1)/`size`(默认20，**最大100**)；过滤 `source`(精确)、`risk_level`、`keyword`(keywords/title/content ILIKE)。返回 `{items,total,page,size}`。
   - `GET /opinions/{id}`：完整舆情；不存在 `404 "Opinion not found"`。
   - `POST /opinions`：创建（供未来 Collector）；`region_id` 必须存在否则 `404 "Region not found"`；创建后默认 `risk_score=0`、`sentiment="neutral"`。
   - `DELETE /opinions/{id}`：删除（MVP 保留）；不存在 `404`。
4. **路由聚合 + 注册**
   - `app/api/__init__.py`：聚合 `auth_router` + `opinions_router`（`opinions_router` 以 `prefix="/opinions"` 挂载，避免空路径报错）。
   - `app/main.py`：`app.include_router(api_router, prefix="/api")`，保留 `/health`。最终路由：`POST /api/login`、`GET,POST /api/opinions`、`DELETE,GET /api/opinions/{id}`、`GET /health`。
5. **测试（`backend/tests/`）**：`conftest.py`（在导入 app 前注入 `DATABASE_URL` 指向本地临时 PG 测试库 `opinion_test`；`auth_headers` 夹具登录取 token）+ `test_auth_opinions.py`（登录成功 / 错误密码 401 / 列表需认证 / 带认证列表 / 创建默认 0+neutral / 详情 404 / 删除 / 错误 region 404）。

**验证（本地，临时 PostgreSQL 5433）**：

- 建测试库 `opinion_test` → `alembic upgrade head` → `init_db.py`（种子 admin + 131028）→ `pytest tests/ -v`：**9 passed**（含原有 health 测试）。
- `app.openapi()` 核对挂载路径：`POST /api/login`、`GET,POST /api/opinions`、`DELETE,GET /api/opinions/{opinion_id}`、`GET /health`。

**关键决策 / 踩坑**：

- `risk_level` 查询参数：**映射为 `opinions.sentiment` 精确匹配**（positive/negative/neutral）。因 `opinions` 表无 `risk_level` 列，按用户约束（禁止改动库结构 / Alembic）沿用情感字段表达风险等级；文档已说明。
- 详情响应文档提及的「研判建议/suggestion」：`opinions` 表当前**无** `suggestion` 列（属 AI 阶段），故响应模型仅含已存在字段，未新增列。
- **空路径 bug**：`list_opinions` 用 `""` 路径，在 `api_router.include_router(opinions_router)`（父路由无前缀）时报 `Prefix and path cannot be both empty`。修复：在聚合层以 `prefix="/opinions"` 挂载 `opinions_router`，最终路径正确。
- **conftest bug**：`@pytest.fixture` 未 `import pytest` → `NameError`。已补 `import pytest`。且 `DATABASE_URL` 必须在导入 `app` 前设置（settings 有 lru_cache）。
- 第三方告警：`python-jose` 内部 `datetime.utcnow()` 在新 Python 触发 DeprecationWarning（库内代码，非本项目）；暂不影响运行。
- 未触碰：数据库结构 / Alembic 迁移 / Docker 配置 / frontend / 项目目录结构；未实现 AI Service / DeepSeek / Collector / Event 聚合 / Dashboard。

**下一步**：等待用户指令进入 **Phase 2B（Dashboard 统计 API / 数据分析基础服务）**。

## 2026-07-16 — Phase 2B Dashboard 统计 API + 数据分析基础服务

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**目标**：完成后台驾驶舱统计接口（`GET /api/dashboard/stats`），统计逻辑下沉到 Service 层；仅 backend，不碰 frontend / 不引入新数据库 / 不改动库结构与 Alembic / 不实现 AI/Collector/Event。

**完成内容**：

1. **Schemas（Pydantic v2，不直接返回 dict/ORM）**
   - `app/schemas/dashboard.py`：`TrendItem`(date,count)、`KeywordItem`(word,count)、`DashboardStatsResponse`(total,today,high_risk,trend,keywords)。
2. **Service 层（统计逻辑唯一归属）**
   - `app/services/dashboard_service.py`：`get_dashboard_stats(db) -> dict`。常量 `HIGH_RISK_THRESHOLD=70`、`TREND_DAYS=7`、`TOP_KEYWORDS=10`。
   - 5 个聚合/批量查询（无 N+1）：`total=count(*)`；`today=count where cast(created_at,date)==current_date()`；`high_risk=count where risk_score>=70`；`trend` 近 7 日分组并补齐零值；`keywords` 取全表 `keywords` 字段逗号拆分后 `Counter.most_common(10)`。
3. **API 层**
   - `app/api/dashboard.py`：`GET /dashboard/stats`（`prefix="/dashboard"`，由 `api_router` 统一加 `/api` → `/api/dashboard/stats`），`Depends(get_current_user)` 鉴权，`response_model=DashboardStatsResponse`。router 只做鉴权 + 调 service + 序列化。
   - `app/api/__init__.py`：聚合新增 `dashboard_router`；`app/main.py` 不变（保留 `/health`，`/api` 前缀已含 login/opinions/dashboard）。
4. **测试（`backend/tests/test_dashboard.py`）**：`fresh_opinions` 夹具清空测试库 `opinions` 表（不触碰生产种子 admin/region）。覆盖：未登录 401 / 登录成功 / total 正确 / today 正确（据 created_at）/ high_risk 正确（risk_score>=70）/ keywords TOP 正确（逗号拆分）/ trend 近 7 日且零值补齐、末项为今日。

**验证（本地，临时 PostgreSQL 5433）**：

- 建测试库 `opinion_test` → `alembic upgrade head` → `init_db.py`（种子 admin + 131028）。
- `pytest tests/ -v`：**16 passed**（含 Phase2A 9 + health 1 + 本阶段 6）。
- `app.openapi()` 核对：`GET /api/dashboard/stats`、`POST /api/login`、`GET,POST /api/opinions`、`DELETE,GET /api/opinions/{opinion_id}`、`GET /health` 全部存在。

**关键决策 / 踩坑**：

- **时区风险（已实测排除）**：`opinions.created_at` 是 naive `DateTime` 列，但 ORM 默认值是**带时区的 `datetime.now(timezone.utc)`**。实测 psycopg v3 存入时**剥掉时区、以 UTC 墙钟存为 naive**（如 `2026-07-16 13:01:11`，tzinfo=None）；PG `current_date()` 也返回 `2026-07-16`。因此 `cast(created_at,date)==func.current_date()` 实测返回正确计数（`TODAY_COUNT 1`）。为彻底规避 Python 侧时区歧义，**today / trend 的日期口径全部使用数据库原生日期函数**（`current_date()` 与 `cast(... as date)`），不在 Python 侧构造带时区的 datetime 参与比较。
- **高风险口径**：`risk_score >= 70`（常量 `HIGH_RISK_THRESHOLD`）。**不使用 `sentiment` 表达风险**（与 Phase2A 的 `risk_level`→`sentiment` 映射是两回事：那是列表过滤，这里是风险分级，二者独立）。文档已说明。
- **关键词统计**：`opinions.keywords` 为 TEXT 逗号分隔（如 `消防,事故,投诉`）。`POST /api/opinions`（Phase2A）的请求体**不含 `keywords` 字段**，创建出的行 keywords 为空。故 `test_dashboard_keywords_top` 经 ORM 直接写入含 keywords 的行以验证聚合（dashboard 只读库，与写入方式无关）。
- **测试 `import pytest` 遗漏**：`test_dashboard.py` 初版用了 `@pytest.fixture` 却漏 `import pytest` → 收集期 `NameError`。已补 `import pytest`（同 Phase2A conftest 的坑，已记。后续新建测试文件务必先 `import pytest`）。
- **未触碰**：数据库结构 / Alembic 迁移 / Docker 配置 / frontend / 项目目录结构；未实现 AI Service / DeepSeek / Collector / RSS / Event 聚合 / 前端页面。保持 PostgreSQL only（无 Redis/ES/Mongo）。

**下一步**：等待用户指令进入 **Phase 2C（业务 API 扩展 / AI Service / Collector / Event 聚合 等）**。

## 2026-07-16 — Phase 2C-0 AI 分析基础设施准备（不接入模型）

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**目标**：为后续 AI 舆情分析建立基础架构（Opinion AI 状态字段 / Alembic 迁移 / AIService 目录与 Provider 模式 / DeepSeek 配置占位），**不调用 DeepSeek、不写真实 Prompt、不做摘要/情感/评分、不新增 API**；仅 backend，不改 frontend / 库结构（除本次新增字段的迁移）/ Docker。

**完成内容**：

1. **Opinion 模型增强**（`app/models/opinion.py`）：新增 `analysis_status`（VARCHAR(16)，默认 `pending`，NOT NULL）+ `analysis_time`（DATETIME，nullable）；经 `__table_args__` 的 `CheckConstraint` 约束取值 `pending/processing/completed/failed`（与迁移同名约束 `ck_opinions_analysis_status` 保持一致）。保留全部原有字段（risk_score/sentiment/summary/keywords 等）。
2. **Alembic 迁移**：新增手写 `0002_add_opinion_analysis_status.py`（`down_revision="0001_initial"`）。`upgrade`：以 `server_default='pending'` 安全加 NOT NULL 列（兼容已有行）+ 加 `analysis_time` + 建 CHECK 约束；`downgrade` 逆向删除。验证 `alembic upgrade head` 成功（head=0002），`\d opinions` 确认两列 + 约束存在。
3. **Schema 同步**（`app/schemas/opinion.py`）：`OpinionOut` 增加 `analysis_status`（默认 `pending`）与 `analysis_time`（Optional[datetime]=None），API 响应包含 AI 状态字段。
4. **AI Service 基础架构**（`app/services/ai/`）：
   - `providers/base.py`：`BaseAIProvider`（ABC，`analyze(text)` 抽象方法，统一输出结构）。
   - `providers/deepseek.py`：`DeepSeekProvider` —— **仅读配置**（api_key/base_url/model，来自 `settings`），`is_configured` 属性；`analyze` 显式 `raise NotImplementedError`，**未发起任何网络请求**。
   - `fallback.py`：`RuleFallbackProvider.analyze()` 返回 TODO 结构（summary/sentiment/risk_score/keywords 占位）。
   - `service.py`：`AIService` 统一管理 `DeepSeekProvider` + `RuleFallbackProvider`，`analyze(text)` 当前返回 Fallback 的 TODO 结果；业务统一经 `AIService.analyze()`，禁止直连 Provider。
   - 抽象/占位分层与 `docs/architecture.md` §5/§6 一致。
5. **配置**：`app/core/config.py` 已含 `deepseek_api_key` / `deepseek_base_url` / `deepseek_model`，本阶段不重复增加（任务要求）。
6. **测试**（`tests/test_ai_service.py`）：AIService 可实例化；Fallback 可调用且返回含必需键的 TODO dict；DeepSeek 缺配置时构造不报错（`is_configured=False`）；`DeepSeekProvider.analyze` 未实现抛 `NotImplementedError`；Opinion 新 AI 字段经 API 详情与 ORM 往返均可正常读取/写回。

**验证（本地，临时 PostgreSQL 5433）**：

- 重建 `opinion_test` → `alembic upgrade head`（0001+0002 全过，head=0002）→ `init_db.py`（种子 admin + 131028）。
- `psql \d opinions` 确认 `analysis_status`(not null, default 'pending')、`analysis_time`(nullable)、CHECK 约束 `ck_opinions_analysis_status` 均存在。
- `pytest tests/ -v`：**22 passed**（Phase2A 9 + Phase2B 6 + health 1 + 本阶段 6）。仅第三方 `python-jose` `datetime.utcnow()` DeprecationWarning。

**关键决策 / 踩坑**：

- **为什么当前不直接调用 DeepSeek**：本阶段目标仅为"基础架构准备"，任务明确禁止调用 API / 写 Prompt / 实现摘要/情感/评分。故 `DeepSeekProvider` 仅装配配置与接口，`AIService.analyze()` 默认走 `RuleFallbackProvider` 的 TODO 结果，保证接口契约与目录分层先行就位，真实调用与"优先 DeepSeek、失败降级 Fallback"的路由逻辑留到 Phase 2C-1。
- **Provider 模式 + 抽象基类**：`BaseAIProvider(ABC)` 统一 `analyze` 签名与输出结构，未来新增 Provider（如其它模型）只需继承实现，业务侧 `AIService` 不改动。
- **CHECK 约束**放在 ORM `__table_args__` 与迁移双侧一致：`0001` 手写迁移不含该约束、`0002` 补齐，ORM 经 `create_all`（init_db 安全网）也会建同名约束，两条路径终点一致，避免 `server_default`/`autogenerate` 误报。
- **`server_default='pending'`**：加 NOT NULL 列时对已有行安全（即便 opinions 表非空也不会因无默认值失败）；与 ORM 的 Python `default="pending"` 配合，新增/迁移两条路都稳定。
- **未触碰**：frontend / 既有 Alembic 迁移(0001) / Docker 配置 / 项目目录结构；未调用 DeepSeek、未实现 AI 摘要/情感/风险评分/Collector/RSS/Event 聚合；保持 PostgreSQL only（无 Redis/ES/Mongo）。Phase 0 遗留的 `app/services/ai_service.py` 占位桩未导入、未删除（保留不破坏既有目录结构）。
- **未新增 API**：AI 分析接口 `POST /api/analyze/{id}` 留待 Phase 2C-1（本阶段仅暴露 AIService 内部架构，不暴露 HTTP 接口）。

**下一步**：等待用户指令进入 **Phase 2C-1（AI 分析接口 / 真实 DeepSeek 调用与降级 / 情感·风险·摘要·关键词落地 / Opinion 分析状态流转）** 或 Phase 3（Collector / Event 聚合 / 前端）。

## 2026-07-16 — Phase 2C-1 单条舆情 AI 分析闭环（真实 DeepSeek + 规则降级）

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**目标**：打通单条舆情 AI 分析闭环——`POST /api/analyze/{id}` → `AIService` → DeepSeek API（OpenAI SDK 兼容）→ 结构化解析 → 写库 → 状态流转；无 Key / 异常自动降级 `RuleFallbackProvider`。仅 backend，不碰 frontend / 不引入新库 / 不改既有库结构（除新增 `analysis_suggestion` 迁移）。

**完成内容**：

1. **AI 结果 Schema（类型化领域对象）**（`app/schemas/ai.py`）：`AIAnalysisResult`（summary:str / sentiment:Literal[positive,negative,neutral] / risk_score:int 经 Pydantic v2 校验 `0<=x<=100` / keywords:list[str] / suggestion:str）。Provider 层与 `AIService` 均返回该类型（**不放 dict**）。
2. **Opinion 模型与 Schema 增强**：`app/models/opinion.py` 新增 `analysis_suggestion`（TEXT，nullable）；`app/schemas/opinion.py` 的 `OpinionOut` 增加 `analysis_suggestion: Optional[str]=None`（沿用既有 `analysis_status`/`analysis_time`）。
3. **Alembic 迁移 0003**：`0003_add_analysis_suggestion.py`（`down_revision="0002_add_opinion_analysis_status"`），`opinions` 加 `analysis_suggestion` TEXT nullable；`downgrade` 逆向可回滚。
4. **DeepSeekProvider 真实调用**（`app/services/ai/providers/deepseek.py`）：OpenAI SDK 兼容（`from openai import OpenAI`），配置全部来自 `settings`（api_key/base_url/model，**禁止硬编码**）。system prompt「公安互联网舆情分析专家」+ user prompt（标题/正文 + 强约束 JSON 结构）；`response_format={"type":"json_object"}`。**JSON 解析兼容 ```json 代码块**：`_strip_code_fence` 去围栏 → `json.loads` → `AIAnalysisResult.model_validate`；任何异常（未配置/网络/解析/校验）一律上抛，由 `AIService` 捕获降级。
5. **RuleFallbackProvider 真正落地规则分析**（`app/services/ai/fallback.py`，沿用既有路径，非 `providers/`）：内置 `DEFAULT_KEYWORDS`（`(词,权重)` 表）。`__init__(keywords=None)` 空则退回内置表（MVP 默认走内置）。`analyze(text)->AIAnalysisResult`：命中敏感词 `risk_score = 20 + Σ(10*weight)` 封顶 100；`risk>=70 → negative` 否则 `neutral`；`summary`/`suggestion` 模板；返回命中词列表。
6. **AIService 调度**（`app/services/ai/service.py`）：`analyze(title, content)->AIAnalysisResult`，内部拼 `text` 委托 `provider.analyze(text)`（保留 Phase 2C-0 的 `analyze(text)` 接口）。有 Key 先 `DeepSeekProvider`，未配置或任何异常降级 `RuleFallbackProvider`。**AIService 不直接查数据库**，敏感词经构造参数注入 `RuleFallbackProvider`。
7. **新增分析 API**（`app/api/analysis.py` + 注册 `app/api/__init__.py` 的 `api_router`，最终路径 `POST /api/analyze/{id}`）：`Depends(get_current_user)` 保护。流程：① `db.get(Opinion,id)`，不存在 `404 "Opinion not found"`；② 置 `analysis_status="processing"` 提交；③ 调 `AIService().analyze(title,content)`；④ 成功写 `summary/sentiment/risk_score/keywords(逗号拼接写入 TEXT)/analysis_suggestion` + `analysis_status="completed"` + `analysis_time=now(utc)`；失败 `analysis_status="failed"`（保留失败状态）并返 `500`。业务 API 不直接连 DeepSeek。
8. **keywords 种子化（仅数据）**（`scripts/init_db.py`）：幂等写入默认敏感词（含权重），使 `keywords` 表可被未来扩展读取；MVP fallback 仍用内置 `DEFAULT_KEYWORDS`（经构造参数注入）。不改表结构。
9. **测试**：新增 `tests/test_ai_analysis.py`（无 Key 自动 fallback 返 `AIAnalysisResult` 且 `risk_score>0`；含敏感词 fallback `risk>0/status=completed`；API 成功返 summary/risk_score/sentiment/analysis_suggestion 且 `status=completed`；异常模拟 → `status=failed` + `500`；DeepSeek 解析去代码块+校验、非法 JSON 上抛；鉴权 401 / 不存在 404）。重写 Phase 2C-0 旧测试 `test_ai_service.py` 两条为类型化断言（`AIAnalysisResult`）。

**验证（本地，临时 PostgreSQL 5433）**：

- `alembic upgrade head` → 0001+0002+0003 全过（head=0003）；`psql \d opinions` 确认 `analysis_suggestion` 列存在。
- `python scripts/init_db.py` → 种子 admin + 131028 + 敏感词。
- `pytest tests/ -q`：**31 passed**（auth 9 + dashboard 6 + health 1 + ai_service 6 + ai_analysis 9）。

**关键决策 / 踩坑**：

- **两处测试 bug 已修**：① `DeepSeekProvider(api_key="fake-key")` 误用构造参数——其 `__init__` 仅 `self`，Key 须构造后 `.api_key=` 赋值；已改为先构造再设属性。② `test_ai_analysis.py` 的假 OpenAI 工厂 `_make_fake_openai` 用嵌套类 `class _Msg: content = content` 引用外层函数参数，类体不形成闭包 → `NameError`；改为经 `__init__` 构造传参透传 `content`。
- **PostgreSQL 启动坑（本环境 Windows）**：直接 `postgres.exe` 拒绝以管理员(Administrator)身份运行（"Execution ... by a user with administrative permissions is not permitted"）。`runas /trustlevel:0x20000` 绕过却被 `0xC0000142`(STATUS_DLL_INIT_FAILED) 弄崩、`postmaster.pid` 残留致后续 `pg_ctl start` 报"another server might be running"。**正确做法**：用 `pg_ctl.exe start`（`-D` 用 `C:/...` 形式 + `MSYS_NO_PATHCONV=1` 防 MSYS 路经转换；`-l` 日志、`-o "-p 5433 -c listen_addresses=localhost"`，**文件重定向**而非 `| tail` 以免管道挂起），postgres 由 pg_ctl 正常派生监听并 detached。**切忌 kill 其后台任务**——会连坐杀掉子 postgres。清理顺序：`taskkill /F /IM postgres.exe` → 删 `postmaster.pid` → `pg_ctl start`。
- **连库主机**：`localhost` 在 Windows 下解析到 IPv6 `::1` 偶发握手挂起；统一用 `127.0.0.1`（`DATABASE_URL=postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5433/opinion_test`）。`conftest` 在导入 app 前注入 `DATABASE_URL`。
- **类型化设计（用户调整 1）**：`AIService` 与 Provider 均返回 `AIAnalysisResult` 不放 dict；API 层经 `OpinionOut` 序列化。旧 Phase 2C-0 依赖 dict 的两条测试已重写为类型化断言。
- **Fallback 加载（用户调整 2）**：`AIService` 不直连数据库；敏感词经构造参数注入 `RuleFallbackProvider`。MVP `keywords=None` → 内置 `DEFAULT_KEYWORDS`；`keywords` 表种子化作为未来扩展点。
- **沿用既有结构差异**：`fallback.py` 实际位于 `app/services/ai/fallback.py`（非 `providers/`），保留；`app/api/__init__.py` 注册（非 `init.py`）；Provider `analyze(text)` 单参数兼容，新增 `AIService.analyze(title,content)` 对外。原 Phase 2C-0 对 DeepSeek「未配置抛错」的旧测试已替换为「未配置抛 `RuntimeError`，由 AIService 捕获降级」的新断言。
- **未触碰**：frontend / 既有 Alembic 0001/0002 / Docker 配置 / 项目目录结构；未实现 Collector / RSS / Celery / Redis / 定时 / 批量 / Event 聚合 / 用户权限扩展；保持 PostgreSQL only。

**下一步**：等待用户指令进入 **Phase 3（Collector / Event 聚合 / 前端）** 或下一阶段。

## 2026-07-16 — Phase 3A Collector 数据采集层 + 自动入库闭环

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**目标**：让系统具备自动获取舆情数据能力——`Collector` 采集 → `Opinion` 入库 → 自动 `AIService` 分析 → 可统计。仅 backend，不碰 frontend / 不引入新数据库 / 不新增迁移 / 不改动库结构 / 不实现定时·Celery·Redis·Event 聚合·爬虫。

**完成内容**：

1. **Collector 骨架填充**（`app/collectors/`）：
   - `base.py`：`BaseCollector(ABC)`（沿用 Phase 0 既有 ABC，`fetch()->list[dict]`），保留。
   - `mock_collector.py`：`MockCollector` 生成 **50 条**大厂县舆情，分三档：正常 30（民生/城建/公共服务）、中风险 15（投诉/服务争议/环境问题）、高风险 5（火灾/事故/群体/死亡/谣言）。每条带**唯一 url**（`https://mock.dachang.gov/opinion/{i}`）作为去重主键；高风险项内置敏感词，保证无 DeepSeek Key 时 `RuleFallbackProvider` 也能产出 `negative` + `risk_score>=70` + 非空 `keywords`。
   - `rss_collector.py`：`RSSCollector` 仅完成**可扩展接口**。`feeds` 为空（或 `RSS_URLS` 环境变量未配置）→ **不加载 feedparser、不执行网络请求**，直接返回 `[]`；仅当源非空才**惰性 `import feedparser`** 并解析。本阶段不实现真实爬虫（Scrapy/Playwright 等禁止）。
   - `service.py`（**新建**）：`CollectorService.collect_and_analyze(db)` 实现完整闭环（见下方数据流）。
2. **CollectorService 复用 AIService**（按用户确认）：内部调用 `AIService.analyze(title, content)` 做分析 + 字段写回 + 状态流转；**不抽取**公共 `AIAnalysisHelper`（MVP 快速验证），但已在 `service.py` 标注 `TODO Phase 4: extract shared opinion analysis workflow`。**不修改** `app/api/analysis.py`（保持 Phase 2C-1 稳定）。
3. **去重策略**：以 `opinions.url` 为唯一判断；`url` 已存在则跳过不重复创建。`url` 为空时退回 `title + publish_time` 辅助判断（见 `_already_exists`）。
4. **失败隔离**：单条 AI 异常仅该 `Opinion` 置 `analysis_status="failed"`（**保留数据库记录**），其余数据正常 `completed`；计数 `failed = created - analyzed`。每条先 `commit()`（pending）再分析，确保失败记录不丢失。
5. **采集状态（内存，临时）**：模块级变量 `_COLLECTOR_STATUS = {"last_run": None, "total_collected": 0}`，重启丢失、不持久化；代码注释与 docs 均注明 **Phase 3A temporary implementation；Persistent collector task history is postponed；未来定时采集再设计 `collector_runs` 表**。
6. **Schemas（Pydantic v2）**：`app/schemas/collector.py` → `CollectorRunResponse`(success/created/analyzed/failed/message)、`CollectorStatusResponse`(last_run/total_collected)。
7. **API（`app/api/collector.py` + 注册 `app/api/__init__.py` 的 `api_router`，`prefix="/collector"` → `/api/collector/run`、`/api/collector/status`）**：均 `Depends(get_current_user)` 保护。`POST /run` 触发一次采集闭环；`GET /status` 返回内存状态。
8. **feedparser 依赖**：加入 `requirements.txt`（惰性导入；未配置 `RSS_URLS` 时不加载、不联网）。
9. **测试（`tests/test_collector.py`，6 项，真实 PG `opinion_test@127.0.0.1:5433`）**：① MockCollector ≥50 条且高风险项经 fallback 产出 negative/risk>=70/keywords 非空；② API 首次运行创建数据（created≥50，analyzed==created）；③ 二次运行 url 去重不重复插入（created==0）；④ AI 失败单条 failed 不影响其他（created=3/analyzed=2/failed=1，库内 1 failed + 2 completed 且记录保留）；⑤ API 无 token → 401；⑥ API 返回 created/analyzed 正确 + `/status` 结构与鉴权。

**验证（本地，临时 PostgreSQL 5433）**：

- `alembic heads` → 仍为 **0003_add_analysis_suggestion**（**未新增任何迁移**，DB 结构零改动）。
- `app.openapi()` 确认 `/api/collector/run`、`/api/collector/status` 均在路径表。
- `pytest tests/ -q`：**37 passed**（auth 9 + dashboard 6 + health 1 + ai_service 6 + ai_analysis 9 + collector 6）。

**关键决策 / 踩坑**：

- **Mock 数据量踩坑**：初版 `normal` 列表仅 29 条（应为 30），致 `MockCollector.fetch()` 返回 49，测试 `>=50` 失败；补 1 条至 30 → 总数 50 修复。
- **去重测试的 source 误区**：`MockCollector` 各条 `source` 是真实媒体名（政府网站/微博/…），**并非** `"mock"`；`CollectorService` 用 item 的 `source` 落库。`_clean_source(db,"mock")` 实际删除 0 行，使二次运行去重把所有已存在项跳过（created=0）。修复：测试改以 **url 前缀 `https://mock.dachang.gov/opinion/`** 识别 mock 舆情（清理/计数），与去重主键一致。
- **环境（本机）**：`PYTHONPATH` 被沙箱清理 → 在托管 Python 的 `Lib/site-packages` 写入 `zz_deps.pth` 指向 `envs/deps`（依赖隔离目录内），`python -m pytest` 正常。PG 经 `127.0.0.1:5433` 连通。
- **复用而非重构**：`CollectorService` 直接复用 `AIService.analyze`，未抽取公共逻辑、未改 `analysis.py`，并在 `service.py` 留 `TODO Phase 4` 提醒未来统一抽取，避免复制逻辑长期漂移。
- **状态临时化明确告知**：内存状态重启丢失，已在代码注释 + `api.md` §8.2 + `architecture.md` §2.1 三处注明 Phase 3A 临时、未来再设计 `collector_runs` 表。
- **未触碰**：frontend / 数据库结构 / Alembic 既有 0001~0003 / Docker 配置 / 项目目录结构；未实现定时任务 / Celery / Redis / Event 聚合 / 多租户 / 权限扩展 / 真实爬虫。保持 PostgreSQL only。

**下一步**：等待用户指令进入 **下一阶段（如 Event 聚合 / 前端 / 定时采集）**。

## 2026-07-16 — Phase 3B Government Website Collector（真实政府网站数据源）

**执行者**：AI Coding Agent（资深全栈 / 架构 / DevOps）

**目标**：将 Phase 3A 的 `MockCollector` 扩展为**真实数据源**——采集河北廊坊大厂回族自治县人民政府网站（`https://www.lfdc.gov.cn/`）。数据流：政府新闻网页采集 → HTML 解析 → `Opinion` 入库 → 自动 AI 分析。仅 backend，不碰 frontend / 不改库结构 / 不新增迁移 / 不引入 Redis·ES·队列·定时·爬虫框架。

**完成内容**：

1. **`government_collector.py`（新建）**：`GovernmentCollector(BaseCollector)`，`source_name="大厂县政府网站"`。
   - 常量：`BASE_URL="https://www.lfdc.gov.cn"`、`DEFAULT_UA`（浏览器 UA）、`MAX_ARTICLES=20`、`REQUEST_INTERVAL=0.3`、`TIMEOUT=10`、`_BODY_FALLBACK_CHARS=500`、`_CONTENT_SELECTORS`、`_ARTICLE_PATH_RE=re.compile(r"/\d+\.jhtml$")`。
   - `_get()`：防御式 GET（`response.encoding=apparent_encoding` 防乱码），失败/超时/HTTP 错误 → `None`。
   - `_parse_list()`：`soup.select("a[href*='.jhtml']")` → `urljoin` 转绝对 → `_ARTICLE_PATH_RE` 过滤导航/栏目链接仅留真实文章。
   - `_parse_detail()`：正文降级链 `div.content` → `article-content/text/TRS_Editor` → `Zoom/article_con` → `article` → 所有 `<p>` 拼接 → `body` 纯文本前 500 字。
   - `fetch()`：遍历 `urls`（来自 `settings.gov_news_urls` 或注入）→ 收集候选按 url 去重 → 取前 `MAX_ARTICLES` → 逐篇 `_get` 详情 + `time.sleep(0.3)` → 返回标准 dict（`source=source_name`，`publish_time=None`）。
2. **配置化（Pydantic Settings，禁用 os.getenv）**（`app/core/config.py`）：新增 `collector_type: str = "government"`、`gov_news_urls: List[str]`（默认 `jrdc.jhtml`/`gggs.jhtml`），并加 `@field_validator("gov_news_urls", mode="before")` 支持 `.env` 逗号分隔字符串。
3. **CollectorService 调整**（`app/collectors/service.py`）：新增 `resolve_collectors(collector_type)`（government→GovernmentCollector / mock→MockCollector / 其余按 government 兜底）；`CollectorService.__init__` 加 `collector_type` 参数（默认 `settings.collector_type`）与 `_uses_government()`；`CollectorRunResult` 加 `collector_type` 字段；`_COLLECTOR_STATUS` 加 `collector_type`。
4. **5 秒防抖（返回 429，不再 500）**：模块级 `_GOV_LAST_RUN_AT` + `THROTTLE_SECONDS=5.0` + `class CollectorThrottled`；`collect_and_analyze` 开头对 government 采集判防抖，不足阈值抛 `CollectorThrottled`；`reset_gov_throttle()` 供测试。`app/api/collector.py` 捕获 `CollectorThrottled` → `response.status_code=429` + `{success:false, message:"collector running too frequently", collector_type:"government"}`。
5. **API 字段（collector_type，刻意不加 source）**（`app/schemas/collector.py` + `app/api/collector.py`）：`CollectorRunResponse`/`CollectorStatusResponse` 加 `collector_type`；注释强调 `Opinion.source`（新闻来源）与 API `collector_type`（采集方式）勿混淆。
6. **依赖**：`requirements.txt` 新增 `requests==2.32.3`、`beautifulsoup4==4.12.3`。
7. **测试隔离**：`tests/conftest.py` 在 import app 前 `os.environ.setdefault("COLLECTOR_TYPE", "mock")`，保证测试默认走 mock、不联网。
8. **测试（`tests/test_government_collector.py`，8 项，全离线 mock HTML）**：栏目页解析、相对→绝对 URL、网络异常隔离（返回 []）、详情正文降级（content/Zoom/paragraphs 三种）、Service 集成、去重、API 返回 collector_type、配置切换（government/mock）。

**验证（本地，临时 PostgreSQL 5433）**：

- `alembic current` / `alembic heads` → 仍为 **0003_add_analysis_suggestion**（versions 仅 0001/0002/0003，**未新增任何迁移**，DB 结构零改动）。
- `app.openapi()`：`/api/collector/run`、`/api/collector/status` 在路径表；`CollectorRunResponse` 含 `collector_type` 且**无 `source`**，`CollectorStatusResponse` 含 `collector_type`。
- `pytest tests/ -q`：**45 passed**（既有 37 + 本阶段 8），8.79s。
- **429 防抖端到端**：run1=200（government，created=1），run2=429（`success=false`，`collector_type=government`，`message=collector running too frequently`）。
- **真实站点端到端烟测**（可访问）：`created=20, analyzed=20, failed=0`，全部 `completed`，`source=大厂县政府网站`，示例 `url=https://www.lfdc.gov.cn/xnyw/34542.jhtml`，`created≥10` 达标。

**关键决策 / 踩坑**：

- **主指令 vs 补充约束冲突（按更严格者执行）**：主指令 §七用 `os.getenv`、§8.3 API 加 `source`；补充约束禁止 `os.getenv`（改 Pydantic Settings）、API 加 `collector_type` 不加 `source`。差异分析阶段即指出并按补充约束落地，用户确认通过。
- **真实站点误抓导航链接**：初版返回 20 条含"走进大厂/新闻中心"等导航页（content_len≈52）。分析 JEECMS 站点发现文章 URL 形如 `/{栏目}/{数字id}.jhtml`、导航为单段 `/xxx.jhtml`；在 `_parse_list` 加 `_ARTICLE_PATH_RE=/\d+\.jhtml$` 过滤，修复后 20 条均为真实新闻（content_len 292-591）。
- **编码防乱码**：`response.encoding = response.apparent_encoding`，避免政府站 GBK/UTF-8 混用乱码。
- **依赖隔离**：环境内无 requests/bs4，`pip install --target=deps` 装入依赖隔离目录（zz_deps.pth 注入），不污染全局。
- **防抖不 500**：`CollectorThrottled` 专用异常在 API 层转 429，避免 RuntimeError 直接冒泡成 500。
- **未触碰**：数据库结构 / Alembic 既有 0001~0003 / Dashboard / AIService / analysis.py / RSSCollector / frontend；未引入 Redis / ES / 队列 / 定时 / 爬虫框架。保持 PostgreSQL only。

**下一步**：**已停止，等待下一阶段指令**（禁止自行进入 Phase 3C / Event 聚合 / 前端）。
