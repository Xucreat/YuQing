# Phase DataSource-Schedule-1-A：生产部署前只读检查（Precheck）

> 生成时间：2026-08-03 14:19 (GMT+8)
> 目标：确认生产部署前的数据库与服务状态，作为 alembic upgrade head 的前置安全依据。
> 本文件仅记录只读探测结果，未对任何库/服务/代码做写操作。

---

## 1. 数据库状态（opinion_db @ 127.0.0.1:5432）

### 1.1 身份安全门禁（DB_IDENTITY_CHECK 未设置 → 默认 on）
| 检查项 | 实际 | 期望 | 结果 |
|---|---|---|---|
| system_identifier | 7663057120701798896 | 7663057120701798896 | ✅ 匹配 |
| database | opinion_db | opinion_db | ✅ 匹配 |
| opinions 行数 | 1015 | ≥ 100 | ✅ 通过（非空库/克隆库） |
| data_directory | 本环境不可读（中文路径编码冲突） | — | ⚠️ 退化为业务指纹校验，已通过 |

**结论：`DATABASE IDENTITY: VERIFIED`** —— 迁移可安全执行。

### 1.2 Alembic 版本
- **当前 revision**：`sec3b_perm_semantic`
- **当前 head**：`p12_datasource_schedule`
- 结论：生产库恰好落后一个迁移（p12），`alembic upgrade head` 将精确施加 p12，无分支冲突。

### 1.3 data_sources 表结构（迁移前）
- 行数：38
- 当前列（14 个）：
  `id, key, name, type, class_path, enabled, priority, scope_region_codes, config_json, last_run_at, last_status, last_error, created_at, updated_at`
- **4 个新列确认不存在（迁移前基线）**：
  - `schedule_enabled` ❌ 不存在
  - `schedule_interval_minutes` ❌ 不存在
  - `next_collect_time` ❌ 不存在
  - `last_collect_time` ❌ 不存在
- **CHECK 约束**：当前无（迁移后将新增 `ck_data_sources_schedule_interval_min`）

---

## 2. 服务状态

### 2.1 uvicorn 进程拓扑（端口 8000）
| 角色 | PID | 父 PID | 名称 | 创建时间 |
|---|---|---|---|---|
| LISTENING（worker） | **44348** | 39116 | python.exe | 2026-08-03 11:20:38 |
| supervisor（启动器） | **39116** | 42576 | python.exe (`-m uvicorn app.main:app --host 0.0.0.0 --port 8000`) | 2026-08-03 11:20:38 |

- 端口 8000 仅 44348 一个进程 LISTENING，父子对（非双实例）。
- 重启策略：杀父进程 **39116**（`taskkill /PID 39116 /T /F`）将级联终止子 44348，再干净启动单实例。

### 2.2 scheduler 启动状态
- 当前 uvicorn 自 11:20:38 起未重启 → **尚未加载新的 `per_source` collector_tick 逻辑**。
- 依 `.env`：`COLLECTOR_SCHEDULE_CRON=*/30 * * * *`，当前实际运行的是旧 cron 调度模式。
- scheduler 运行于 uvicorn 进程内（APScheduler AsyncIOScheduler），无独立进程；重启后随新代码加载 `collector_tick`。

### 2.3 风险提示（前置）
- 当前运行的 worker 是 11:20 旧代码；部署必须重启才能加载 p12 的 scheduler/API 变更。
- 重启会造成约 10–20s API 中断（父子对整对停止 → 新实例启动）。

---

## 3. 进入下一步的前置结论
- ✅ 数据库身份校验通过，迁移安全。
- ✅ 迁移目标唯一（p12），无 DAG 冲突。
- ✅ 4 新列当前缺失，迁移后将补齐 —— 与迁移设计一致。
- ✅ 服务进程拓扑清晰，重启目标明确（父 39116）。

下一步：执行 `alembic upgrade head`（仅 p12），随后做迁移后只读验证。
