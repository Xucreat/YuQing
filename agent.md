# Agent 操作手册（根目录入口）

> 本文件为项目级 Agent 入口，详细规范见 [`docs/agent.md`](./docs/agent.md)。

我是本项目的 **AI Coding Agent**，同时承担资深后端、资深前端、系统架构与 DevOps 角色，负责交付 **大厂县公安互联网舆情监测研判平台 MVP**。

## 核心约束（速记）

1. **分阶段交付**：Phase 0 → 1 → 2 → 3 → 4，每阶段完成即停止等待指令，**禁止一次性生成全部代码**。
2. **技术栈固定**（Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic / Uvicorn；Vue3+TS+Vite+Element Plus+Pinia+Axios+ECharts；PostgreSQL 16；DeepSeek 经 AIService）。
3. **唯一数据库** PostgreSQL 16；禁止 Redis / ES / Mongo / MinIO / MySQL。
4. **禁止微服务**；docker-compose 仅 `postgres` / `backend` / `frontend`。
5. **禁止复杂多租户**；仅单 `admin`，无 OAuth / refresh / RBAC。
6. **AI 隔离 + 降级**：业务不直接调 DeepSeek，`AIService` 在 Key 缺失/失败时切换 `RuleBasedAnalyzer`。
7. **Collector 不直接写库**：`fetch()` → `Service` → `Database`。
8. **区域可扩展**：`regions` 用 `level` 支持 省→市→区县→街道→单位。
9. **代码分目录**，禁止全写 `main.py`。

## 当前进度

Phase 0 已完成（目录结构 / docker-compose / docs / README / agent.md）。
下一步：**等待用户指令进入 Phase 1（Backend 基础工程）**。
