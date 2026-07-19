# 大厂县公安互联网舆情监测研判平台 MVP

> 试点区域：**河北省廊坊市大厂回族自治县**（region code `131028`）
> 目标：跑通「数据采集 → 入库 → AI 分析 → 风险判断 → 事件聚合 → 前端展示」闭环。
> MVP 优先、可演示、可维护、可扩展；保留省→市→区县→街道→单位扩展能力，禁止复杂多租户。

---

## 技术栈（强制，禁止更换）

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic / Uvicorn |
| 前端 | Vue3 (Composition API) / TypeScript / Vite / Element Plus / Pinia / Axios / ECharts |
| 数据库 | PostgreSQL 16（**唯一**，无 Redis/ES/Mongo/MinIO/MySQL） |
| AI | DeepSeek API（封装 `AIService`，失败自动降级规则引擎） |
| 部署 | Docker Compose（postgres + backend + frontend，无微服务） |

---

## 目录结构

```
.
├── docker-compose.yml        # 三服务编排
├── .env.example             # 环境变量样例
├── README.md
├── agent.md                 # Agent 操作手册
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini / alembic/
│   ├── app/
│   │   ├── main.py         # 入口 + /health
│   │   ├── api/            # 路由层（Phase 2）
│   │   ├── models/         # SQLAlchemy 模型（Phase 1）
│   │   ├── schemas/        # Pydantic 模型（Phase 1）
│   │   ├── services/       # ai_service.py / event_service.py
│   │   ├── collectors/     # base / mock / rss
│   │   ├── core/           # config / security
│   │   ├── db/             # 引擎 / 会话 / Base
│   │   └── utils/
│   └── tests/
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf          # 生产反代 /api -> backend
│   ├── package.json / vite.config.ts / tsconfig*.json
│   └── src/
│       ├── main.ts / App.vue
│       ├── router/ stores/ api/ utils/ types/
│       └── views/          # Login / Dashboard / Opinions / OpinionDetail / Events
└── docs/
    ├── agent.md  product_scope.md  architecture.md
    ├── decision_log.md  database.md  api.md
    └── changelog.md  claude_log.md
```

---

## 快速开始

```bash
# 1. 准备环境变量
cp .env.example .env
#   按需填写 DEEPSEEK_API_KEY（不填则自动降级规则引擎，离线可演示）

# 2. 启动（Phase 1~4 完成后）
docker-compose up -d

# 3. 访问
#   前端： http://localhost:8080  （默认路由 /login）
#   后端： http://localhost:8000/health
#   登录： admin / admin123
```

### 本地开发（未容器化时）

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm install
npm run dev   # http://localhost:5173 （已配置 /api 代理到 8000）
```

---

## 开发阶段（按 Phase 执行）

| Phase | 范围 | 状态 |
| --- | --- | --- |
| 0 | 项目初始化：目录结构 / docker-compose / docs / README / agent.md | ✅ 完成 |
| 1 | Backend 基础工程：FastAPI / PG / SQLAlchemy / Alembic / Models / Migration / 初始化数据 | ⏳ 待执行 |
| 2 | 业务接口：登录 / 舆情 API / Dashboard / Event / AI Service / Collector | ⏳ 待执行 |
| 3 | Frontend：登录 / Dashboard / 舆情列表 / 详情 / 事件中心 | ⏳ 待执行 |
| 4 | 联调：`docker-compose up` 前后端运行、pytest / npm run build | ⏳ 待执行 |

详细规范见 [`docs/`](./docs)。

---

## 最终验收标准

- [ ] `docker-compose up` 可启动
- [ ] localhost 打开登录页
- [ ] `admin / admin123` 登录成功
- [ ] Dashboard 有数据
- [ ] MockCollector 生成 30 条以上数据
- [ ] 舆情列表分页筛选正常
- [ ] 详情页显示 AI 分析
- [ ] DeepSeek 失败时自动降级
- [ ] 至少生成 3 个事件
- [ ] 文档完整
