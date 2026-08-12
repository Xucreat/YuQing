# YQ 基线冻结报告

冻结时间：2026-08-11（Asia/Shanghai）

## 当前版本

- 分支：`main`
- 最近提交：`8908961ca660a896e7c887fdf60bfc485c3af861`（fix: 外网数据源列表请求 size 超后端上限(le=100)致 422）
- 工作区：存在大量既有未跟踪审计、构建和运行时文件；本阶段未回滚、覆盖或删除这些文件。
- 后端依赖：FastAPI 0.115.0、Uvicorn 0.30.6、SQLAlchemy 2.0.35、Pydantic 2.9.2、psycopg >=3.1.19、bcrypt 4.2.0、APScheduler 3.10.4（详见 `backend/requirements.txt`）。
- 前端依赖：Vue 3.5.12、Vite 5.4.10、TypeScript 5.6.3、Element Plus 2.8.4、Pinia 2.2.4（详见 `frontend/package.json`）。

## 启动方式

- 数据库：本机 PostgreSQL 16，`127.0.0.1:5432`，数据目录已验证为 `C:\Users\Administrator\Desktop\舆情监测系统\pgdata`。
- 后端：`C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`。
- 当前后端入口：`http://127.0.0.1:8000`。
- 前端发布静态资源由后端提供；Vite 开发端口 5173 当前未监听。项目定义的容器端口仍为 8080（见 `docker-compose.yml`）。
- `/health`：HTTP 200，响应为 `status=ok`、`collector_discovery=db_driven`、`collector_discovery_error=null`。

## 数据库只读备份

- 备份目录：`C:\Users\Administrator\Desktop\YQ\runtime\baseline_20260811_095157\`
- 主备份：`opinion_db.dump`，custom format，2,406,953 bytes，`pg_dump` exit 0。
- 全局对象：`globals.sql`，382 bytes，`pg_dumpall --globals-only --no-role-passwords` exit 0。
- 恢复方式：在隔离 PostgreSQL 实例创建同名数据库和角色后，使用 `pg_restore --clean --if-exists --no-owner --no-privileges --dbname=<target> opinion_db.dump`，再按需执行 `globals.sql`。本阶段未执行恢复，也未修改原数据库。

## 数据库和页面基线

冻结时只读统计：

| 指标 | 数量 |
|---|---:|
| users | 3 |
| roles | 4 |
| permissions | 56 |
| data_sources | 55 |
| enabled_data_sources | 15 |
| foreign_opinions | 40 |
| foreign_events | 0 |
| foreign_alerts | 1 |
| foreign_alert_rules | 1 |

浏览器使用 Codex in-app Browser，在 2026-08-11 以当前本地测试账号完成登录，并确认以下页面可打开：

- `/login`、`/dashboard`、`/opinions`、`/events`、`/alerts`、`/system/users`、`/foreign`
- 页面标题、核心表格/统计区域和导航均可见；未执行业务写操作、采集、告警评估、外部通知或生产 CRUD。
- 截图：`C:\Users\Administrator\Desktop\YQ\audit-evidence\next-phase\baseline-dashboard.png`、`baseline-opinions.png`、`baseline-events.png`、`baseline-alerts.png`、`baseline-users.png`、`baseline-foreign.png`。
- 启动/健康证据：`C:\Users\Administrator\Desktop\YQ\backend\uvicorn_8000_current.out.log`、`C:\Users\Administrator\Desktop\YQ\backend\uvicorn_8000_current.err.log`。

## 基线构建和测试

- `frontend`: `npm run build` 成功，构建产物写入既有 `frontend/dist`。
- 后端 `tests/test_health.py` 运行失败：当前 `/health` 已增加 collector discovery 字段，而测试仍断言旧的仅 `{"status":"ok"}` 响应；这是测试契约滞后，不是生产健康检查失败。
- 全量 `pytest -q` 及 `--collect-only -q` 在本机命令窗口内未在 124 秒内完成，进程已停止；后续阶段将按模块拆分执行并记录结果。
- 测试数据库夹具指向独立的 `localhost:5433/opinion_test`，未指向上述生产数据库。

## 已知缺陷和影响分析

1. README 的 `admin/admin123` 默认密码已过期；当前数据库使用环境中配置的本地测试凭据。不得把该凭据写入报告或代码。
2. `frontend/src/views/ForeignWorkspace.vue` 当前显示并使用硬编码批准源 `57-60`，需要改为后端批准/启用外网源集合。
3. `backend/app/api/foreign.py` 的当前用户改密接口尚未实现；`UserPasswordReset` 尚无旧密码、确认密码和前端入口的完整流程。
4. 外网采集接口、告警领域 API 和调度代码已有大量能力，但需要验证/收口权限、全量与指定采集边界、调度状态以及统一预警中心入口。
5. 外网事件数量为 0；外网事件型告警的真实浏览器端到端路径无法在当前数据上证明。

## 国内/外网链路状态

- 国内链路：Dashboard、舆情列表、事件中心、国内预警中心和用户管理均完成只读页面加载；本阶段未改变国内数据或采集行为。
- 外网链路：外网 Dashboard 可加载，40 篇外网文章、0 个事件、1 条告警、1 条规则可见；风险统计显示仍有待处理项。当前自动调度和外网写操作未执行。

## 后续阶段回归指标

每个阶段至少对比：`/health` 响应、前端 build、users/roles/permissions、enabled data sources、foreign opinions/events/alerts/rules 数量、国内核心页面加载、外网采集任务状态、审计日志新增记录，以及桌面/移动端关键页面截图。

## 阶段零结论

数据库备份、前后端运行、健康检查、登录和核心页面加载、基线报告与截图均已完成。已知测试契约和全量测试耗时问题已记录。允许进入下一阶段；所有后续写入均必须使用隔离测试数据或可回滚的测试夹具。
