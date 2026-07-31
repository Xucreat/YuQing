# RBAC-DB-INCIDENT-INVESTIGATION.md
# 数据库"数据消失"事故调查报告（只读调查）

> 调查模式：只读。全程未执行任何 alembic upgrade/downgrade、未执行任何 INSERT/UPDATE/DELETE、未启动采集器、未修改任何数据目录。
> 调查时间：2026-07-23 约 11:00–12:30 (GMT+8)
> 调查人：Senior Developer（高级开发工程师）

---

## 0. 一句话结论（先回答核心问题）

**原来的那套包含真实舆情数据、数据源和关键词配置的数据库，仍然完整存在，从未被删除或覆盖。**

它位于：`C:\Users\Administrator\Desktop\舆情监测系统\pgdata`
（PostgreSQL cluster `system_identifier = 7663057120701798896`）

"数据全部消失"是**假象**：本次会话中 PostgreSQL 被启动到了**错误的、陈旧的空克隆数据目录** `C:\Users\Administrator\Desktop\YQ\pgdata`，而前端/后端连接的正好是这个空库，于是看到空白。真实生产库从未被本次任何操作触碰。

---

## 1. 事故时间线

| 时间(GMT+8) | 事件 | 证据 |
|---|---|---|
| RBAC-1 审计时 | PostgreSQL 在 `127.0.0.1:5432` 运行，服务的是 **`舆情监测系统\pgdata`** | RBAC-1 报告：`alembic_version=kwlex01`、业务数据完整 |
| RBAC-1→RBAC-2 之间 | PostgreSQL 被停止（环境/会话重置，5432 不再监听） | RBAC-2 开始时 `127.0.0.1:5432` 连接超时 |
| RBAC-2 阶段1 | 我发现本地 PG16 二进制 `YQ\pgsql\pgsql\bin`，并找到 `YQ\pgdata` | `pgdata\PG_VERSION = 16` |
| RBAC-2 阶段1 | **我用 `pg_ctl -D YQ\pgdata` 启动了 PostgreSQL**（指向了陈旧克隆） | pg_controldata：YQ/pgdata `NextXID=1379`、迁移 `0003` |
| RBAC-2 阶段2 | 对 `YQ\pgdata` 执行 `alembic upgrade head`（应用 rbac10001） | 仅改动 YQ/pgdata 文件；创建的是**空**业务表 |
| RBAC-2 阶段3 | 启动后端 uvicorn(8000)，连 `127.0.0.1:5432` = `YQ/pgdata`（空库） | 用户看到"舆情/数据源/敏感词全消失" |
| 用户报告事故 | — | — |
| 只读调查 | 发现机器上存在多个 pgdata，对比 `system_identifier` | 见下 |

---

## 2. RBAC-1 审计时的数据库事实

- 连接目标：`127.0.0.1:5432`（DATABASE_URL 原值 `postgres:5432`，本机解析到 127.0.0.1）
- `alembic_version = kwlex01`
- 业务表（opinions / events / data_sources / keywords / roles …）均存在且有数据
- `roles` 表有 3 个角色：admin / analyst / viewer
- 该实例服务的真实数据目录 = **`舆情监测系统\pgdata`**（本次调查用 5433 只读实例核验，`alembic_version` 仍为 `kwlex01`，数据完整 —— 与 RBAC-1 完全一致）

---

## 3. 本次（RBAC-2）迁移前的数据库事实

- 启动 PG 前 `127.0.0.1:5432` 无监听（PG 已被停止）
- 我启动的 `YQ\pgdata` 实际状态：
  - `alembic_version = 0003_add_analysis_suggestion`（**不是** RBAC-1 见到的 kwlex01）
  - `users` 仅 4 列（id/username/password_hash/role），无 is_active / last_login / RBAC 列
  - `roles` 表**不存在**
  - 所有 RBAC 表（permissions / role_permissions / user_roles / user_login_logs / user_operation_logs）**不存在**
  - 业务表为早期空结构
- 结论：这个 `YQ\pgdata` 是一个**早期克隆**（initdb 后不久、业务数据尚未灌入时的拷贝）

---

## 4. PostgreSQL 实例变化

- RBAC-1 时：1 个 PG 实例在 5432，数据目录 = `舆情监测系统\pgdata`
- RBAC-2 时：原 5432 实例已停止；我新启动 1 个 PG 实例在 5432，数据目录 = `YQ\pgdata`（错误目录）
- 调查时：我又临时启动 1 个**只读** PG 实例在 **5433**，数据目录 = `舆情监测系统\pgdata`（仅用于 SELECT 核验，未写）
- 当前（调查结束时）：5432 实例已停止（连接挂起=无监听）；5433 只读实例仍在运行（持有真实库锁，需停止后才能做恢复）

---

## 5. PGDATA 变化

| 数据目录 | 是否本次变更的"活动目录" | 状态 |
|---|---|---|
| `舆情监测系统\pgdata` | RBAC-1 的活动目录；RBAC-2 误未使用 | **未被本次任何写操作触碰** |
| `YQ\pgdata` | RBAC-2 我错误启动的活动目录 | 被 `alembic upgrade head` 改写（空业务表 + RBAC 表） |
| `.local\crm-runtime\pgsql16-local-data` | 无关（CRM 运行时） | 未动 |
| `.workbuddy\tmp\pg\data` | 无关（工具临时库） | 未动 |

两个项目目录（`YQ` 与 `舆情监测系统`）是**同一套代码的副本/工作区**，其各自下的 `pgdata` 也同源（见第 6 节 system_identifier）。

---

## 6. 当前数据库身份（5433 只读实例，指向真实生产库）

```
current_database : opinion_db
current_user     : opinion_user
server           : 127.0.0.1 : 5433
version          : PostgreSQL 16.6, compiled by Visual C++ build 1942, 64-bit
system_identifier: 7663057120701798896
alembic_version  : kwlex01
databases        : postgres, opinion_db, opinion_test
pg_controldata   : cluster state = in production; latest checkpoint 2026/7/23 10:57:06
```

**关键：`YQ\pgdata` 与 `舆情监测系统\pgdata` 的 `system_identifier` 完全相同（`7663057120701798896`）**。
→ 说明两者是**同一个 cluster 的文件级拷贝**（initdb 时生成、全局唯一）。但已分叉：
- `舆情监测系统\pgdata`：`NextXID=12766`、checkpoint `10:57` → 事务多、数据全 → 活跃生产库
- `YQ\pgdata`：`NextXID=1379`、checkpoint `11:47`（我启动后写的）→ 事务少、业务表空 → 早期克隆

---

## 7. 原数据库是否仍存在

**是，完整存在。**

位置：`C:\Users\Administrator\Desktop\舆情监测系统\pgdata`
只读核验（端口 5433）得到的真实业务数据计数：

| 表 | 行数 | 说明 |
|---|---|---|
| opinions | **689** | 舆情数据（用户以为 429，实际更多，未丢失） |
| events | 122 | 事件 |
| event_opinions | 235 | 事件-舆情关联 |
| data_sources | **30** | 数据源（用户报"全部消失"，实际都在） |
| keywords | 46 | 关键词（含系统内置敏感词 + 自定义） |
| alert_records | 12 | 告警记录 |
| alert_rules | 2 | 告警规则 |
| collector_runs | 1672 | 采集运行记录 |
| roles | 3 | admin / analyst / viewer |
| users | 1 | admin |
| alembic_version | kwlex01 | 与 RBAC-1 完全一致 |

> 注：真实库中无独立 `sensitive_keywords` 表，系统内置敏感词应存于 `keywords` 表（46 行）中，前端连错库才"看不到"。

---

## 8. 数据是否真正删除的判断

**判断：未被删除、未被覆盖。属于"连错数据目录"导致的可见性假象。**

证据链：
1. 真实库 `system_identifier` 与错误库相同 → 同源拷贝，不是另一个被清空的库。
2. 真实库 `alembic_version=kwlex01`，**未应用 rbac10001** → 证明本次 `alembic upgrade head` 只跑在了 `YQ\pgdata`，从未触达真实库。
3. 真实库业务表行数正常（opinions 689、data_sources 30 等）→ 数据完好。
4. `YQ\pgdata` 的 `NextXID=1379` 极低 → 它是早期克隆，本次迁移只是往这个空克隆里建了空表。
5. 全程无任何 DROP/TRUNCATE/DELETE 针对真实库。

---

## 9. 所有候选数据库 / 数据目录

| 路径 | system_identifier | 角色 | 数据状态 |
|---|---|---|---|
| `C:\Users\Administrator\Desktop\舆情监测系统\pgdata` | 7663057120701798896 | **真实生产库** | kwlex01，数据完整（689 opinions 等） |
| `C:\Users\Administrator\Desktop\YQ\pgdata` | 7663057120701798896 | 早期克隆（被误启动） | rbac10001，业务表**空** |
| `C:\Users\Administrator\.local\crm-runtime\pgsql16-local-data` | 7641438358274420624 | CRM 运行时（无关） | 无关 |
| `C:\Users\Administrator\.workbuddy\tmp\pg\data` | （独立） | 工具临时库（无关） | 无关 |

> 未发现任何 `*.dump` / `*.backup` / `*.sql` / `*.tar` 备份文件（除部分事件快照见下）。
> 发现的快照：`backend/_migration_snapshots/event_snapshot_20260722T062906.json`（仅覆盖 events/event_opinions/propagation_nodes/alert_records，是局部快照，非完整备份，本次恢复也不需要它）。

---

## 10. 可恢复路径

> 以下为方案，需你授权后执行（当前处于禁止写库期）。

**方案 A（恢复数据可见性，最小改动）**
1. 停止当前 5432 实例（YQ/pgdata，已是空克隆，可弃）。
2. 停止 5433 只读实例（释放真实库锁）。
3. 用正确数据目录启动 PG：`pg_ctl -D "舆情监测系统\pgdata" -o "-p 5432"`。
4. 重启后端（连 5432）。
→ 业务数据（舆情/事件/数据源/关键词）立即回归。
⚠️ 但真实库当前是 `kwlex01`，而后端代码已含 RBAC 列（`is_superuser` 等），用户相关接口会 500。因此**仅恢复数据还不够**，需配合方案 B。

**方案 B（完整正确恢复，推荐）**
1. 停止 5433 只读实例，释放真实库。
2. 启动 PG 指向 `舆情监测系统\pgdata`（5432）。
3. 对该真实库执行 `alembic upgrade head`（应用 rbac10001）→ 在保留 689 opinions 等全部数据的前提下，加 RBAC 表/列 + 种子 26 权限 + 把旧 roles JSONB 迁进 role_permissions + 标记 admin 为超管。
4. 重启后端，做 RBAC-2 安全验收。
→ 这是 RBAC-2 本要做的事，只是应在**正确的数据目录**上做。

**方案 C（清理混淆）**
- 确认 `YQ\pgdata` 确为陈旧克隆后，可将其移走/删除（它只是空壳 + RBAC 空表，无业务价值），避免下次再误启动。
- 明确约定：本机生产数据目录固定为 `舆情监测系统\pgdata`，PG 启动脚本/后端 DATABASE_URL 必须指向它。

---

## 11. 当前禁止执行的操作（按你的指令，调查期间一律未做，后续也需你授权）

- ❌ 任何 alembic upgrade / downgrade（含对真实库）
- ❌ 任何 INSERT / UPDATE / DELETE / DROP / TRUNCATE
- ❌ 任何 init_db.py / seed 脚本
- ❌ 任何数据重建、回填、迁移
- ❌ 删除/覆盖/初始化任何 PostgreSQL data directory
- ❌ 启动采集器写入新数据
- ❌ 继续 RBAC 前端开发 / 安全验收 / 数据库修复

当前仅保留：5433 只读实例（持有真实库锁，用于核验）、只读查询、文件系统只读检查、本报告生成。

---

## 12. 下一步恢复方案（待你授权）

请确认采用哪条路径（推荐 **方案 B**）：

- [ ] **方案 B（推荐）**：在 `舆情监测系统\pgdata` 上 `alembic upgrade head` + 重启 PG/后端，恢复完整 RBAC 生产库
- [ ] **方案 A**：仅先把 PG 指回真实库恢复数据可见性（用户接口仍会 500，需再补 B）
- [ ] **方案 C**：先仅清理 `YQ\pgdata` 混淆（需你确认其为可弃克隆）
- [ ] 其他你指定的边界

在你明确授权前，我不会执行任何写库/迁移/重启数据目录操作。5433 只读实例可保持运行供你随时复核，或我可立即停掉它以释放真实库锁。

---

## 附：调查使用的只读命令（可复核）

- `Get-CimInstance Win32_Process` 读 PG 进程命令行
- `netstat -ano` 查 5432/5433 监听
- `find` 全盘搜 `PG_VERSION` / `postgres.exe` / 备份文件
- `pg_controldata` 对比 `system_identifier` 与集群状态（不启动服务）
- 端口 5433 启动 `default_transaction_read_only=on` 的临时实例，仅执行 `SELECT`
- 全程未调用 alembic、未调用任何写 SQL
