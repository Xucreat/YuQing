# Phase 5：系统级工程成熟度盘点与下一阶段优先级审计报告

> 审计日期：2026-07-23
> 审计模式：**只读**（未修改任何代码 / 配置 / 数据库 / 迁移 / 前端）
> 审计基线：以**当前真实代码与运行状态**为准，不假设旧文档准确
> 唯一执行的极小验证：用 node 读取 4 个前端文件，以排除一处误报（见 §6）

---

## 〇、一页结论（TL;DR）

当前系统**已经不是 MVP**。认证/权限、采集装配、采集日志批次链路、前端权限工程四条主线均达到**接近企业级**的成熟度。系统真正的短板集中在**「进程内状态的可恢复性」**与**「一处生产安全默认值」**，而非架构本身。

- **必须现在做（P0）**：`SECRET_KEY` 仍是默认 `change-me-in-production` → JWT 可被伪造。**改配置即可，非重构。**
- **建议尽快做（P1）**：① 卡死在 `running` 的采集记录无回收；② `opinions.url` 无数据库唯一约束（重叠触发下有重复入库竞态）；③ 后台任务状态仅存内存（重启即丢、且不回收）；④ 操作审计只覆盖用户管理。
- **可暂缓（P2）**：前端 lint/类型检查/测试脚本缺失、构建产物残留、CORS 全开、`_debug_static` 暴露、naive datetime。
- **达阈值再考虑**：采集日志全表聚合 + 无归档（`collector_runs` 超约 10 万行或 p95 延迟 > 500ms 时再治理）。
- **绝对不要做**：引入 Celery/Redis/Kafka/K8s/微服务/CQRS/DDD 重写、重写 9 个专用采集器、DB 分片、为「统一」而统一。当前规模**没有任何**证据支撑这些。
- **不要**重新审计 RBAC-1、**不要**自动开启 RBAC-3。

---

## 一、系统基线确认（以真实代码为准）

| 领域 | 真实状态 | 证据 |
|---|---|---|
| 后端框架 | FastAPI + SQLAlchemy 2.0 + APScheduler；单进程 | `app/main.py`、`app/core/scheduler.py` |
| 路由装配 | `api_router`(`/api`) + `admin_ds_router`(`/admin/data-sources`) + `collector_router`(`/collector`) | `app/api/__init__.py`、各路由文件 |
| 采集装配 | 表驱动（`data_sources` 表→回退默认源），config 校验，专用/通用分离，装配失败写 `CollectorRun(failed)` 可见 | `collectors/service.py:197-206`、`api/admin_data_sources.py:96-113` |
| 采集批次链路 | 采集前生成 `batch_id`，写入 `Task.batch_id`，贯穿每条 `CollectorRun`；日志按 batch 聚合 | `api/collector.py:60-66`、`models/collector_run.py:12`、`api/admin_data_sources.py:484-517` |
| RBAC | 全栈闭环（后端 9/9、前端权限入口统一、401/403 分离），**已完成，不再重审** | 前端 `router/index.ts`、`composables/usePermission.ts` |
| 前端 401 兜底 | **旧「token 过期静默空屏」已修复**：全局 response 拦截器，清 token + 跳登录，并发只跳一次 | `frontend/src/api/index.ts:30-59` |
| 生产库门禁 | `db_identity.py` 业务指纹门禁（opinions≥100=真实库） | `app/core/db_identity.py` |
| 迁移 | alembic 11 个版本文件在 `backend/alembic/versions/` | 见下 |

迁移文件（存在且成链）：`0001_initial` → `0002` → `0003` → `0004` → `0005` → `527069a609a0_p0_collector_runs` → `c0769f234982_p1_fulltext_keywords_hebei_sources` → `collrunbatch001` → `kwlex01` → `p2_rbac` → `rbac10001`。

---

## 二、已达企业级成熟度的部分（不要动，不要"优化"）

这些设计**已经正确且规模匹配**，重构它们是纯负收益：

1. **采集器表驱动装配 + 装配失败可见化**。装配失败的源不会被静默丢弃，而是落一条 `CollectorRun(status=failed, error_msg=...)`，在采集日志与逐源历史中可见（`service.py:246-266`）。这是很好的可观测性设计。
2. **单条 AI 分析失败隔离**。某条分析异常只置该条 `analysis_status=failed` 并保留记录，不影响批次其余数据（`service.py:330-352`）。
3. **前端权限工程**。统一 `usePermission` 入口、路由守卫、401 并发安全兜底、403/401 语义分离（`api/index.ts`、`router/index.ts:101-120`）。旧记录中的「静默空屏」问题**已实际修复**。
4. **生产库身份门禁**。`db_identity.py` 以业务指纹区分真实库/空克隆库，是防误写生产的关键防线，跨会话价值极高。
5. **连接健壮性**。`create_engine(..., pool_pre_ping=True)` 处理陈旧连接；DeepSeek 客户端配了 `timeout` + `max_retries`（`config.py:35-37`）。
6. **DB 会话不跨线程**。并发采集每线程 `session_factory()` 新建会话、`finally` 关闭（`service.py:424-429`），符合 SQLAlchemy 线程模型。

> **判定**：以上属"简单但稳定/规模足够"的合理设计，**归入可接受**，不列为缺陷。

---

## 三、问题清单（分级 + 证据 + 影响 + 建议）

### 🔴 P0 —— 必须现在解决

#### P0-1　生产密钥仍是公开默认值（JWT 可伪造）
- **证据**：`.env` 中 `SECRET_KEY=change-me-in-production`（与 `config.py:40` 默认值完全一致，未覆盖）；同时 `INIT_ADMIN_PASSWORD=admin123`（`config.py:46`）。
- **影响**：JWT 用众所周知的默认密钥签名，任何了解该代码的人都可**伪造任意用户（含 admin）令牌**，RBAC 形同虚设。这是企业级部署的硬性阻断项。
- **补充（正面）**：`.env` **已被 `.gitignore` 忽略**（`git ls-files .env` 无匹配），DeepSeek key 未泄漏进 Git — 这点没问题。
- **建议**：轮换为强随机 `SECRET_KEY`（如 `python -c "import secrets;print(secrets.token_urlsafe(48))"`）、修改初始管理员口令。**纯配置/运维动作，不涉及任何代码重构**，成本极低、收益极高。

---

### 🟠 P1 —— 建议尽快解决（随数据/任务/并发增长必然暴露）

#### P1-1　采集记录会永久卡死在 `running`（可靠性 + 可观测性真缺陷）
- **证据**：`_process_collector` 先 `CollectorRun(status="running")` 提交（`service.py:284-292`），随后 `collector.fetch()`（`service.py:294`）可能抛异常。并发路径中异常在 `as_completed` 循环被 catch 并 log（`service.py:437-441`），但**该 `CollectorRun` 行永远停留在 `running`，无任何代码将其置为 failed**。全仓无对孤儿 run 的对账/清扫逻辑。
- **影响**：任一采集器抛错、或进程被 kill，采集日志的批次状态就永久显示「运行中」（`admin_data_sources.py:530-537` 的 `_batch_status` 见 running 即判 running），运维无法区分「真在跑」与「已崩」。这是采集失败无法定位的直接来源。
- **建议（右尺寸）**：① 在 `_process_collector` 用 `try/except` 包住 fetch/分析，异常时把该 run 置 `failed` 并写 `error_msg`；② 启动时 + 定时做一次「僵尸对账」：把 `start_time` 早于阈值仍 `running` 的记录标记为 `failed(超时/中断)`。**无需引入任何中间件。**

#### P1-2　`opinions.url` 无数据库唯一约束（重叠触发下重复入库竞态）
- **证据**：去重完全依赖实例级 `self._write_lock`（`service.py:128`）+ 进程内查询（`_already_exists`, `service.py:164-183`），`opinions` 表无 url 唯一索引。每次触发 `run_collector` / 定时任务都 `new CollectorService()`（`api/collector.py:99`、`scheduler.py:18`），**各自持有不同的锁**。
- **影响**：手动采集（并发）与定时采集（顺序）时间上重叠时，两个实例的锁互不互斥 → 同一 url 可被两次判「不存在」→ **重复入库**。窗口虽窄，但属数据一致性正确性问题，且随采集频率提高而增大。
- **建议（右尺寸）**：给 `opinions.url` 加**部分唯一索引**（`WHERE url <> ''`），插入用 `ON CONFLICT DO NOTHING` 兜底。一条迁移解决，**这不是过度工程，是把正确性下沉到数据库**。

#### P1-3　后台任务与采集状态仅存内存（重启即丢 + 无回收）
- **证据**：`task_manager._tasks`（`task_manager.py:31`）、`_COLLECTOR_STATUS`、`_GOV_LAST_RUN_AT`（`service.py:52-61`）均为模块级内存。`_tasks` 从不淘汰（`get_task` 只读、无 TTL 清理）。
- **影响**：① 进程重启 → 进行中的 task 丢失，前端轮询 `GET /api/tasks/{id}` 拿到 404、进度条断裂；② `_tasks` 无限增长 → 长期运行的慢速内存泄漏；③ 防抖时间戳重启丢失（影响很小）。
- **说明（避免夸大）**：`CollectorRun` 本身已持久化（采集结果不丢），丢失的只是「实时进度/任务包装态」。单进程 + 重启不频繁的当下，属**可控**，但企业化多次发布/重启场景会反复被用户感知。
- **建议（右尺寸）**：给 `_tasks` 加**上限 + 完成后 TTL 淘汰**（立即可做、防泄漏）；进度可恢复性可选做——**用一张轻量 `tasks` 表持久化**（与已持久化的 `collector_runs` 对齐），或明确接受「重启期间的进行中任务不可恢复」并在前端友好提示。**不要为此上 Celery/Redis。**

#### P1-4　操作审计只覆盖用户管理（企业级审计不完整）
- **证据**：`log_operation(` 仅在 `api/users.py` 被调用（全仓 grep 命中 `audit_service.py` 定义 + `users.py` 调用）。数据源增删改（`admin_data_sources.py` 的 POST/PATCH）、关键词变更、手动触发采集、预警规则变更、报告生成**均未写操作审计**。
- **影响**："关键操作没有审计"对企业合规是硬需求，当前仅用户管理满足，数据源/采集/预警这些高价值写操作留白。
- **建议**：在上述写接口补 `log_operation`（服务已现成，成本低）。注意 `log_operation` 只 `db.add` 不 commit（`audit_service.py:79-95`），补点时需确保随业务事务一并提交。

---

### 🟡 P2 —— 可暂缓（不影响当前可靠性，属可维护性/卫生）

| 编号 | 问题 | 证据 | 建议 |
|---|---|---|---|
| P2-1 | 前端无 lint/类型检查/测试脚本；`build` 不跑 `vue-tsc` | `frontend/package.json` scripts 仅 dev/build/preview | 后续把 `vue-tsc --noEmit` 前置到 build，或进 CI |
| P2-2 | 构建产物污染源码树（`dist.old_*`、`.dist_trash/`、`vite.config.js.timestamp-*.mjs`） | 前端目录残留 | 清理 + `.gitignore` 覆盖（清理走 rename 走安全门限） |
| P2-3 | 生产构建 `minify:false` | `vite.config.js` | 现为规避 OOM 的**有意取舍**，可接受；内存充裕后再开 minify |
| P2-4 | CORS 全开 `allow_origins=["*"]` | `main.py:28-34` | 生产同源静态托管，无需全开；收紧为白名单 |
| P2-5 | `_debug_static` 调试端点暴露 | `main.py:36-40` | 生产环境下关闭或加权限 |
| P2-6 | `DateTime` 列未带时区，却写入 tz-aware UTC | `models/collector_run.py:15-16` 等 | 统一 naive/aware 口径，避免比较歧义 |
| P2-7 | 前端个别静默吞错 | `Propagation.vue`、`command-screen/ScreenHeader.vue` 等 | 低频降级场景，酌情补提示 |

---

### ⏳ 达阈值再考虑（现在做 = 过度工程）

#### T-1　采集日志全表聚合 + `collector_runs` 无归档
- **证据**：`collection_logs` 每次请求都对 `collector_runs` **全表 group by**，再在 Python 侧筛选/分页（`admin_data_sources.py:500-577`）；无任何保留期/归档。
- **量级测算**：约 22 源 × 每 30 分钟 1 次 ≈ 每天约 1000 行 ≈ 每年约 36 万行。当前百级批次下**逻辑清晰、性能足够**（代码注释也如实说明这一点）。
- **触发阈值**：当 `collector_runs` **超过约 10 万行**，或该接口 **p95 延迟 > 500ms** 时，再做：把聚合下推到 SQL 分页 + 建索引 + 加保留期归档。**现在不动。**

---

## 四、下一阶段优先级路线图

```
现在（1 个动作，运维即可）        P0-1  轮换 SECRET_KEY + 初始管理员口令
        │
下一阶段（可靠性收口，均为小改）   P1-1  running 僵尸记录 try/except + 启动对账
        │                        P1-2  opinions.url 部分唯一索引 + ON CONFLICT
        │                        P1-3  _tasks 上限/TTL（防泄漏）；持久化可选
        │                        P1-4  数据源/关键词/采集/预警 补操作审计
        │
再下一阶段（卫生 & 可维护性）      P2-1..P2-7  CI 类型检查/测试、清构建残留、收 CORS…
        │
仅当命中阈值                      T-1  采集日志 SQL 分页 + 索引 + 归档
                                 （collector_runs > 10 万行 或 p95 > 500ms）
```

**建议的最小下一阶段（"可靠性收口"）**：只做 P0-1 + P1-1 + P1-2 + P1-4。这四项都属**小改/加约束/补调用**，不触碰架构、不动 9 个专用采集器、不引入任何新组件，却能把「采集失败可定位、数据不重复、关键操作可审计、令牌不可伪造」四个企业级底线补齐。P1-3 的持久化部分可作为可选项，视发布/重启频率决定。

---

## 五、绝对不要做（现在没有任何证据支撑）

- ❌ Celery / RabbitMQ / Kafka / Redis 全面引入 —— 当前单进程 `ThreadPoolExecutor` 完全够用；任务可恢复性用一张小表即可，不需要 broker。
- ❌ 微服务拆分 / Kubernetes / 服务网格 —— 无规模瓶颈证据。
- ❌ CQRS / Event Sourcing / 全面 DDD 重写 —— 与当前问题无关。
- ❌ 重写 9 个专用采集器 / 为"统一"再抽象一层 —— 明确违反既定约束，纯负收益。
- ❌ 数据库分片 / 全面缓存层 —— 数据量级（十万行/年）远未到。
- ❌ 重新审计 RBAC-1、自动开启 RBAC-3 —— 已闭环，无新工程问题。

---

## 六、审计过程中排除的一处误报（纪律记录）

自动化广度探查曾把 6 个前端源文件（含 `types/index.ts`、`AppLayout.vue`、`Users.vue`、`DataManage.vue`）判为「二进制损坏、构建必失败」。

**这是误报，已排除**：用 node 直接读取，4 个文件均为正常明文（`AppLayout.vue` 正常 `<template>`、`Users.vue` 19275 字符、`DataManage.vue` 2698 字符）。根因是 node_modules 侧的**虚拟化压缩 fs**——node 读明文，而 `file`/Git Bash 等非 node 进程读到的是压缩字节，从而误判乱码（此陷阱已在项目长期记忆中记载）。

> 保留此记录，是为了践行本阶段纪律：**不为"看起来更企业级"而制造并不存在的问题**。真实构建链路以 node / `npx vite build` 为准，历史构建均成功。

---

## 七、成熟度评级总览

| 维度 | 评级 | 说明 |
|---|---|---|
| 认证与权限（RBAC） | 🟢 企业级 | 全栈闭环，已验收 |
| 前端权限/异常工程 | 🟢 接近企业级 | 401 兜底完善；错误提示不统一（P2） |
| 采集装配与配置校验 | 🟢 接近企业级 | 表驱动 + 失败可见 |
| 采集批次/日志链路 | 🟡 基本可用 | 链路完整，但 running 僵尸无回收（P1-1）、全表聚合待阈值治理（T-1） |
| 任务/状态可恢复性 | 🟠 原型级 | 纯内存态，重启即丢、无回收（P1-3） |
| 数据一致性 | 🟡 基本可用 | 缺 url 唯一约束，重叠触发有重复风险（P1-2） |
| 审计与可追溯 | 🟡 部分达成 | 仅用户管理有操作审计（P1-4） |
| 生产安全基线 | 🔴 阻断 | 默认 SECRET_KEY（P0-1，改配置即可解决） |
| 工程卫生（CI/构建） | 🟡 待补 | 无 lint/类型/测试脚本、构建残留（P2） |

---

*本报告为只读审计产物，未对系统做任何变更。所有结论均附真实代码证据；任何后续修改需另行确认后在独立阶段执行。*
