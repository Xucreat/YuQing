# Agent 操作手册（agent.md）

> 本文档定义「AI Coding Agent」在本项目中的角色、目标、技术栈与开发规则。
> 所有 Phase 的执行者都应以本手册为约束。

## 1. 角色

- 资深后端工程师
- 资深前端工程师
- 系统架构师
- DevOps 工程师

身份统一为：**AI Coding Agent**，负责交付可运行、可维护、可扩展的 MVP。

## 2. 项目目标

构建 **大厂县公安互联网舆情监测研判平台 MVP**。

- 试点区域：河北省廊坊市 **大厂回族自治县**（region code `131028`）。
- 跑通完整闭环：
  - 数据采集 → 数据入库 → AI 分析 → 风险判断 → 事件聚合 → 前端展示
- 优先级：**MVP 优先、可演示、可维护、可扩展**。

## 3. 强制技术栈（禁止更换）

| 层 | 技术 |
| --- | --- |
| 后端语言 | Python 3.12 |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.0 |
| 迁移 | Alembic |
| 校验 | Pydantic |
| 服务器 | Uvicorn |
| 前端 | Vue3（Composition API）+ TypeScript + Vite |
| UI | Element Plus |
| 状态 | Pinia |
| HTTP | Axios |
| 图表 | ECharts |
| 数据库 | PostgreSQL 16（**唯一**） |
| AI | DeepSeek API（封装 `AIService`） |
| 部署 | Docker Compose（postgres + backend + frontend） |

## 4. 开发规则（必须遵守）

1. **分阶段执行**：严禁一次性生成全部代码。必须按 Phase 0 → 1 → 2 → 3 → 4 顺序，每阶段完成后停止等待指令。
2. **禁止更换技术栈**（见上表）。
3. **单一数据库**：仅 PostgreSQL 16。禁止 Redis / Elasticsearch / MongoDB / MinIO / MySQL。
4. **禁止微服务拆分**：docker-compose 仅含 `postgres`、`backend`、`frontend` 三个服务。
5. **禁止复杂多租户**：仅支持单个 `admin` 用户；不做 OAuth、refresh token、RBAC。
6. **AI 隔离**：业务代码禁止直接调用 DeepSeek；必须通过 `services/ai_service.py` 的 `AIService`。
7. **AI 降级**：`DEEPSEEK_API_KEY` 缺失或调用失败时，自动切换 `RuleBasedAnalyzer`，保证离线演示。
8. **Collector 不直接写库**：`Collector.fetch()` → `Service` → `Database`。
9. **区域可扩展**：`regions` 表按 `level`（省→市→区县→街道→单位）设计，保留未来扩展。
10. **代码分目录**：禁止把所有代码写在 `main.py`。

## 5. 验收标准（最终）

- [ ] `docker-compose up` 可以启动
- [ ] localhost 打开登录页
- [ ] `admin / admin123` 登录成功
- [ ] Dashboard 有数据
- [ ] MockCollector 生成 30 条以上数据
- [ ] 舆情列表分页筛选正常
- [ ] 详情页显示 AI 分析
- [ ] DeepSeek 失败时自动降级
- [ ] 至少生成 3 个事件
- [ ] 文档完整

## 6. Phase 计划

| Phase | 范围 | 状态 |
| --- | --- | --- |
| 0 | 项目初始化：目录结构 / docker-compose / docs / README / agent.md | ✅ 完成 |
| 1 | Backend 基础工程：FastAPI / PG / SQLAlchemy / Alembic / Models / Migration / 初始化数据 | ⏳ 待执行 |
| 2 | 业务接口：登录 / 舆情 API / Dashboard / Event / AI Service / Collector | ⏳ 待执行 |
| 3 | Frontend：登录 / Dashboard / 舆情列表 / 详情 / 事件中心 | ⏳ 待执行 |
| 4 | 联调：`docker-compose up` 前后端运行、测试 | ⏳ 待执行 |
