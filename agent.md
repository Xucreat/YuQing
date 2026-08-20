# Agent 操作手册（YQ 舆情监测系统）

> 本文件是项目级 Agent 操作规则入口，不替代代码、配置、数据库和运行结果。用户最新指令优先；实际代码/配置/数据库/运行结果是当前事实源；本文件负责稳定规则；基线报告和 memory 负责记录带日期的当前状态与历史证据。旧版 Phase 0-4 手册（`docs/agent.md`）仅作历史参考。

## 项目路径与定位

- 项目根：`C:\Users\Administrator\Desktop\YQ`
- 定位：公安互联网舆情监测研判平台，覆盖「数据采集 → 入库 → AI 分析 → 风险判断 → 事件聚合 → 预警处置 → 前端展示」完整闭环。
- 当前范围：国内（廊坊/河北，监测区域已切湖北咸宁通山）+ 外网（RSS / 多语言）。
- 技术栈固定（禁止更换）：后端 Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 / Uvicorn；前端 Vue3 + TypeScript + Vite + Element Plus + Pinia + Axios + ECharts；唯一数据库 PostgreSQL 16（禁止 Redis / ES / Mongo / MinIO / MySQL）；AI 统一经 `AIService`（DeepSeek + 规则降级），另接 Bocha / Anspire / Grok 搜索辅助、百度翻译；采集：政府网站 / 新闻 / RSS / 八爪鱼(微博) / MediaCrawler(微博+小红书)。

## Agent 协作

- 主 agent 负责判断范围、执行简单任务、协调子 agent 并最终验收；只有适合并行、独立审查或长时间运行的任务才分配子 agent。
- 按 S0-S3 风险分级分配：S0/S1 由主 agent 或轻量处理；S2 用 high；S3（安全/数据/架构关键判断）才用 xhigh/ultra；机械、重复任务不默认 ultra。
- 若当前环境无子 agent 工具，直接执行并在总结中说明限制。

## 工作规则

- 所有回复使用简体中文。
- **禁止过度设计与兜底设计**：必须采用明确、完整、可长期维护的方案，不得用临时方案、绕行实现或兜底逻辑替代。
- **分阶段交付**：高风险任务或用户明确要求分阶段时，阶段完成后暂停并汇报；普通小任务直接完成修改、验证和总结。
- 每个会话总结控制在几句话内，说明完成内容、验证结果和未解决事项，避免冗长废话。
- 临时文件写入 `tmp/`；运行日志、数据库备份和恢复材料写入 `runtime/`；验收截图、测试结果和审计证据写入 `audit-evidence/`；正式报告写入 `docs/`。已有历史产物不得擅自删除、清空、覆盖或整理性移动。
- 常规文本编辑用精确补丁，不做无必要的整文件覆盖；恢复或生成前端静态产物等确需整批替换时，必须先确认范围、保留现有脏改动并做差异/完整性校验。中文内容注意文件编码，编辑前先确认，避免乱码。
- 修复问题遵循证据链：收到问题 → 复现并判断实际问题 → 修复 → 用同一复现路径回归 → 输出证据；首次定位设置 15-20 分钟软检查点，到点先报告当前假设/证据并升级协作或风险级别（S3 安全或数据事故不得因时间盒停止必要复现与取证）。
- 每次任务结束后的最终答复默认面向用户（开发工程师），结论先行：说明改了什么、根因、实际验证结果、仍未解决事项和建议下一步；可保留必要的技术要点（关键文件、命令、证据），但避免冗长堆砌，确需展开的细节放简短附录。最后一段必须用一句话概括真实完成情况，避免看不出「到底修好了什么、还差什么」。
- 仅在形成架构约定、记录事故根因、确认用户长期偏好、产生重要验收证据或出现未解决阻塞时追加 `.workbuddy/memory/YYYY-MM-DD.md`；普通小任务不制造记忆噪声。

## 开发流程与风险分级（S0-S3）

- 每项任务先标注 S0-S3，按影响面取最高级；语义触发器优先于文件数量，不确定时升一级。先列出任务文件白名单，修改和提交均不得超出白名单。
- 安全底线不受 S0-S3、快速门禁或用户快捷要求豁免：秘密不入库或写入 Agent 文档；破坏性 Git 操作须明确授权；DB 写入先备份并确认目标（可丢弃、可重建的隔离测试库可用重建或事务回滚证据替代物理备份，持久共享/生产库仍须备份并验证恢复）；认证、权限、网络暴露和生产配置须在真实对应环境验证。
- **S0（只读/无行为变化）**：代码浏览、文档、诊断、只读调研。验证以事实核对、必要的查询和 `git diff --check` 为主；不跑重门禁、不创建提交。
- 语义触发器：`auth/role/permission/session/tenant`、路由守卫、DB/PII 写入、导入/导出、`env/secret/port/listener/TLS`、部署/基础设施、不可逆操作、共享后端路由、返回受保护数据的新 endpoint、可能造成容量/DoS 风险的性能改动——均至少 S3；客户数据只读展示可 S2，任何创建/更新/批量导入导出或权限隔离均至少 S3。
- **S1（局部低风险）**：仅限未命中上述触发器的机械/样式/文案/测试变更；单文件不等于低风险。运行相关 lint、单测或类型检查，并做 `git diff --check`；按需跑一个相关 smoke。
- **S2（跨模块或可见行为）**：未命中 S3 触发器的跨文件功能、共享组件、普通路由/API 契约、性能或浏览器可见问题。必须跑快速门禁、受影响模块的 typecheck/build 或对应 pytest，以及对应浏览器/接口验证；涉及共享入口、回归风险或发布前再跑完整门禁。
- **S3（高风险/高爆炸半径）**：命中任一语义触发器或不可逆/跨域核心流程；先备份并确认目标环境，优先 staging/隔离副本，生产操作须明确审批且不以直接改生产为默认；可选独立 worktree/分支，必须完整门禁、领域测试、真实环境证据和回滚/恢复路径。关键安全判断须指定复核人并记录结论。
- **快速门禁**：`git diff --check`、任务文件白名单核对、受影响模块的最小测试（lint/typecheck/单测/相关 smoke）和必要的浏览器或接口复现。S1/S2 默认使用；S0 仅在有文件变更时检查。
- **完整门禁**：受影响领域全量测试、构建和关键 E2E/安全检查。S3 必须触发；S2 在共享入口、回归风险、准备合并/发布或用户明确要求时触发。若门禁所需服务、数据库、浏览器、凭据、依赖或配置等环境前置条件不具备，须在对应服务器做等价检查并留下命令、环境、时间和结果证据；缺失则标记「未验证」并阻断，不能用静态检查冒充通过。

## 环境与数据库铁律

- 生产库数据目录在项目同级目录 `C:\Users\Administrator\Desktop\舆情监测系统\pgdata`（PG16）；`YQ\pgdata.archive-early-clone` 是空克隆，勿误连。路径和端口变化时以服务状态、连接检查和当前配置为准。
- **写库前必须跑** `backend/scripts/db_identity_check.py`（opinions≥100 = VERIFIED，空库 = ABORT）；隔离测试库必须显式指定目标连接，只有在确认是可丢弃测试库后才允许按测试脚本要求关闭身份门禁，并在证据中记录。
- 测试库 `127.0.0.1:5433/opinion_test`；生产库 `127.0.0.1:5432/opinion_db`；认证信息只从项目根目录 `.env` 读取，不在 Agent 文档、总结或命令输出中复制凭据。
- 连接 URL 必须 `127.0.0.1`，不可 `localhost`（PG 只听 IPv4，localhost 解析到 ::1 会握手挂起）。
- 时区 Asia/Shanghai：应用写 `utcnow()` 进 naive 列 → 存本地时间；日期比较用数据库原生 `current_date()` / `cast(... as date)`，不要在 Python 侧构造带时区 datetime 参与比较；外网时间同样避免 aware/naive 混减。
- Alembic：revision id >32 字符会因 varchar(32) 失败，需 ALTER 为 VARCHAR(64)。
- 采集状态：`collector_runs` 以数据源运行记录为基础，当前支持同一采集触发共享 `batch_id`，并含 `trigger_type`、`error_msg` 等字段；字段契约以模型和 Alembic 迁移为准，不凭历史记忆假定表结构。

## 运行与部署铁律

- uvicorn 必须 `--host 0.0.0.0 --port 8000`（支持局域网 192.168.10.90:8000）。
- **重启铁律**：任何重启/部署一律调用 `backend/scripts/restart_backend.ps1`，**绝不可裸命令写 `--host 127.0.0.1`**（会覆盖 LAN 绑定致拒连）。
- 前端部署：`cd frontend` → `vite build`（OOM 用 `node --max-old-space-size=1400 node_modules/vite/bin/vite.js build`，构建前停 uvicorn）→ 用 python 把 dist 拷到 `backend/app/static` 并扫 null 字节 → git flush index.html。vite build 前 `rm -rf frontend/node_modules/.vite frontend/node_modules/.cache`。
- node 虚拟化 fs 陷阱：node 写 chunk 会产生 null 字节致前端崩溃，部署后必须扫描。
- PostgreSQL 服务名 `PostgreSQL_YQ`；uvicorn 计划任务 `YQ_Uvicorn_LAN`（AtStartup/SYSTEM）。查：`Get-Service PostgreSQL_YQ` / `Get-ScheduledTask -TaskName YQ_Uvicorn_LAN`。
- 网络默认拒绝，仅暴露受控接口并配置最小 ACL/白名单、防火墙、认证和 TLS；`0.0.0.0` 仅限受控内网。发现已知默认弱凭据（弱 SECRET_KEY / 空 INIT_ADMIN_PASSWORD）必须拒绝启动（`core/config.py` 已内置校验）。
- 环境变量落到项目根目录 `.env`（`backend/.env` 不作为配置来源）；`COLLECTOR_SCHEDULE_ENABLED` 默认 True，外网采集 `foreign_collection_schedule_enabled` 默认 False（opt-in）。
- SPA 中间件：带扩展名的缺失静态资源必须返回 404 不 fallback；`/openapi.json` 被拦截返 404。

## 脏工作区、Git 红线与变更边界

- 以首次写入前的 `git status --short` / `git diff` 为基线；只 stage 白名单内且由本任务产生的文件；提交前扫描 staged 内容中的 secret/凭据/PII/敏感文件，发现即停止提交。
- 脏工作区与目标冲突时可选独立 worktree/分支，不自动创建；不还原、不格式化、不覆盖无关改动。
- **红线（Agent 默认禁止）**：`git checkout / restore / reset --hard / clean -fd / stash / rebase`。除非用户明确授权且已保留必要证据，否则不得执行可能改变或丢弃未提交工作区内容的 Git 操作。
- 当前工作区保护项（截至 2026-08-19）：15-C、`_chk.js`、未提交核心源码/迁移和 `docs/Reimplementation_Audit_20260815.md` 中列出的恢复证据，均不得擅自删除、覆盖或用历史版本替换。实际保护对象和清单必须先以当前 `git status`、文件校验和最新审计报告复核。
- 15-C、Phase 0.5、`_FORBIDDEN_DOMESTIC_TRANSITIONS` 等属于带日期的恢复/迁移现场规则，不是永久架构约束；若任务触及相关文件，先读取对应审计报告并重新确认用户口径。

## 外部信息与联网

- 先用仓库代码、锁文件、现有测试和项目文档解决问题；不为稳定的本地事实或泛化知识联网搜索。
- 仅在外部事实可能变化、依赖/平台版本与兼容性、公开安全漏洞/公告、法律合规要求，或用户明确要求查证时联网；记录关键来源和查询日期，避免把搜索结果当作本地实现证据。

## Git 规则

- 不提交 `.env*`、密钥、数据库 dump、SQL、SQLite / DB 文件、日志、`node_modules/`、`dist/`、报告目录或运行缓存。
- 用户明确要求时才允许重写历史或执行破坏性 Git 操作。
- 每次提交只包含同一类变更；只提交本任务白名单内已验证的同类改动；read-only 调研或无实质变更不创建空提交。

## 当前页面范围

- 驾驶舱：`/dashboard`（浅色）
- 舆情：`/opinions`、`/opinion/:id`
- 事件：`/events`、`/event/:id`；外网事件详情 `/foreign/event/:id`
- 外网工作台：`/foreign`（关键词/数据源/采集日志/舆情列表/事件/预警）
- 预警中心：`/alerts`（国内 + 外网双轨）
- 数据管理：`/data`（关键词/数据源/采集 tab；旧 `/keywords`、`/sources` 重定向至此）
- AI 检索：`/ai-search`（web / ai / anspire）
- 传播分析：`/propagation`
- 系统管理：`/system`（users / roles / login-logs / operation-logs 子页）
- 指挥大屏：`/command-screen`（深色，独立全屏布局）

## 代码库定位指南

### Repo map

- 后端 `backend/`：入口 `app/main.py`（挂载 `/api` + SPA 静态服务 + 缓存策略）；路由聚合 `app/api/__init__.py`（`api_router` 统一 `prefix="/api"`）；路由层 `app/api/*.py`；业务逻辑 `app/services/*.py`（含 `event/`、`ai/` 子包）；ORM `app/models/*.py`；Pydantic `app/schemas/*.py`；采集 `app/collectors/*.py`（`registry.py` 实时读 DB `config_json`，60s TTL）；核心 `app/core/*.py`（config / dependencies / permissions / rbac_d1 / scheduler / task_manager / security）；DB `app/db/*.py`；常量 `app/constants/region.py`；静态产物 `app/static/`。
- 前端 `frontend/`：入口 `src/main.ts`；路由 `src/router/index.ts`；请求层 `src/api/index.ts`（`baseURL=/api`，401/403 全局拦截）；视图 `src/views/*.vue`（外网 `views/foreign/*.vue`）；组件 `src/components/*.vue`（`command-screen/`、`report/` 子目录）；状态 `src/stores/*`；组合式 `src/composables/*`（usePermission / useEcharts / useCollectionActions 等）；类型 `src/types/*`；样式 `src/styles/*`。
- 构建配置 `frontend/vite.config.js`（`@` 别名→src，`/api` 代理→127.0.0.1:8000）；依赖 `frontend/package.json`、`backend/requirements.txt`。
- Alembic 迁移 `backend/alembic/versions/`（0001~0005 + 命名迁移）；配置 `backend/alembic.ini`。
- 脚本 `backend/scripts/`（init_db / db_identity_check / restart_backend.ps1 及运维验证脚本）。

### How to locate code

- 页面入口：URL → `frontend/src/router/index.ts` → view 组件 → `src/api/*` / axios 调用 → 后端路由。
- 前端接口：先搜 `rg -n "endpoint|/api|api\." frontend/src/api frontend/src/views`，再回后端 `backend/app/api/`。
- 后端接口：先看 `backend/app/api/__init__.py` 的挂载前缀，再定位 `backend/app/api/<module>.py`；领域业务下沉 `backend/app/services/<module>_service.py`。
- 采集源：`app/collectors/registry.py:resolve_collectors` 实时读 `data_sources.config_json`，新增/排查数据源从这里入手。
- 权限：后端 `app/core/rbac_d1.py` + `app/core/permissions.py`；前端 `src/composables/usePermission.ts`；路由 meta 的 `permission` / `module`。
- 中文标题不稳定时，同时搜 URL、tab key、接口路径、组件名、领域英文名。

### Search policy

- 默认用 `rg` / `rg --files`，限制目录和关键词，排除 `node_modules` / `pgsql` 等大目录，避免全仓漫读。
- 从真实入口反推：URL → router → view → api → backend route → service → model。
- 源码与浏览器不一致时，优先检查运行时缓存、Vite 构建产物、uvicorn 重启、路由守卫、本地偏好缓存。
- 数据、权限、登录、性能问题必须确认真实容器、数据库、端口、登录态和浏览器可见结果。

### Change policy

- 若用户最新指令限制只改某些文件，以最新限制为准；不要为常规流程扩大改动范围。
- 前端页面改动优先 page-local 或组件-local；外网专题用 `foreign/` 前缀组件 + `foreign-ui.css`。
- 分页统一用 `<Pager>`；来源/关键词/采集日志等列表页用 apple-dialog/apple-modal 弹窗（外网页自带非 scoped 样式）。
- 路由/入口/菜单变更要同时检查 router、布局（AppLayout/FullscreenLayout）、权限 meta、重定向映射、负向不可达路径。
- 后端国内/外网写入分别走各自领域 service（opinion_* / foreign_*），不得回退到通用 CRUD；Collector 不直接写库（`fetch()` → Service → Database）。

### Validation policy

- 最小通用检查：`git diff --check` + 白名单核对（排除既有脏改动后确认新增文件仅含任务白名单）。
- 后端：pytest（测试默认 mock 采集、连 `127.0.0.1:5433`）；改共享路由/领域逻辑跑对应领域测试；数据变更必须 `db_identity_check.py` 确认目标库。
- 前端：本地 `npm run dev` 联调（`/api` 代理）；发布 `npm run build` 后核对 dist 无 null 字节、入口 index.html 已 flush。
- 页面/UI/权限/性能需浏览器可见验证（局域网 192.168.10.90:8000 或本地 127.0.0.1:8000）；RBAC 权限需正/负向用例（401/403/会话/隔离）。
- 任何未运行、跳过、环境不具备或仅静态检查的项目都标注「未验证」，不得表述为通过，并在总结中说明原因。

### Known conventions

- `keywords` 表是采集过滤 + 预警匹配的唯一权威源；无 AND，`matches_region_topic` 地域优先短路 OR；`fetched_raw` = fetch 返回量（已过关键词过滤）。
- 外网三态分离：`rule_risk`（effective 唯一来源）/ `latest_ai_risk`（completed 才有效）/ `display_risk`（仅展示）；AI 不改 effective_risk、不自动建 alert、未人工确认不进正式事件/预警、不改国内逻辑。
- 15-C 双轨：`foreign_alerts.status` + `disposition_status` 组合约束；处置 API `PUT /foreign/alerts/{id}/handle`。
- 采集按钮：①顶栏「采集数据」POST /collector/run（仅 superuser）；②外网「采集外网 RSS」POST /foreign/collect + source_ids；③「采集全部已启用外网源」POST /foreign/collect + all_sources:true。
- 时区/naive 列、127.0.0.1、编码、Alembic revision 长度等陷阱见「环境与数据库铁律」。
- 工作日志以当天 `.workbuddy/memory/YYYY-MM-DD.md` 为 append-only 过程记录；它用于追溯决策和证据，不替代当前代码、配置、数据库和运行结果。

### Suggested agent workflow

1. 明确范围：确认在 `C:\Users\Administrator\Desktop\YQ`，读取用户最新限制，先跑 `git status --short` 建基线。
2. 轻量定位：用 router / api 聚合 / registry / services 快速建立路径；标注任务 S0-S3 并列文件白名单。
3. 复现或确认：页面问题用浏览器，接口问题用实际容器/端口/DB，数据问题先备份并跑 `db_identity_check.py` 确认目标库。
4. 修改：只改必要文件，沿用现有 patterns；避开无关 dirty 文件。
5. 验证：按风险选择 `git diff --check`、局部 smoke、pytest、typecheck/build、浏览器截图/DOM/network 证据。
6. 收尾：确认 `git diff --name-only` 只含白名单，按同类变更提交；报告 status 摘要、改动文件、验证证据、未执行项；仅在满足记忆写入条件时更新 `.workbuddy/memory/`。
