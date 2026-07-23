# 数据库环境基线报告（Phase RBAC 环境固定）

> 生成时间：2026-07-23 12:27 (GMT+8)
> 执行模式：**只读检查**。本阶段未执行任何 `alembic upgrade/downgrade`、`init_db`、seed、`INSERT/UPDATE/DELETE`、`DROP/TRUNCATE`、`initdb`、新 pgdata 创建或采集器写入。
> 操作人身份：Senior Developer（高级开发工程师）

---

## 1. 代码工作区

```
C:\Users\Administrator\Desktop\YQ
```

后端代码、前端代码、迁移脚本、Alembic 配置均在此目录。

## 2. 真实业务数据库目录（唯一权威数据源）

```
C:\Users\Administrator\Desktop\舆情监测系统\pgdata
```

> **严禁**将 `C:\Users\Administrator\Desktop\YQ\pgdata` 作为任何 PostgreSQL 实例的数据目录。

## 3. 当前 PostgreSQL 进程（只读枚举）

仅发现 **1 个** PostgreSQL 实例：

| PID | 启动时间 | 命令行（关键片段） | 说明 |
|---|---|---|---|
| 25020 | 2026-07-23 12:13:38 | `postgres.exe -D "C:/Users/Administrator/Desktop/舆情监测系统/pgdata" -p 5433 -c default_transaction_read_only=on -c max_connections=10` | 事故阶段遗留的**只读临时实例**，指向真实库 |
| 79636 / 34664 / 17396 / 30220 / 30132 | 12:13:38 | `postgres.exe --forkaux / --forkbgworker` | 上述实例的辅助进程 |

- 无 Windows PostgreSQL 服务。
- 无 docker 容器。
- **5432 端口当前无任何监听进程。**

## 4. 端口监听状态

| 端口 | 状态 | 绑定进程 |
|---|---|---|
| 127.0.0.1:5432 | **无监听** | — |
| 127.0.0.1:5433 | LISTENING | PID 25020（真实库只读实例） |

## 5. DATABASE_URL（连接目标）

```
postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db
```

- 后端 `app/core/config.py` 默认 `host=postgres`（docker 服务名）；
- 项目根 `.env` 覆盖为 `127.0.0.1:5432`。
- **结论**：后端代码期望连接 `127.0.0.1:5432/opinion_db`，而当前 5432 未运行 → 这正是此前"数据消失"假象的直接原因（之前曾误把 5432 指向空克隆 `YQ/pgdata`）。

## 6. 数据库名 / 用户 / 测试库

- 业务库：`opinion_db`
- 测试库：`opinion_test`（已存在）
- 数据库用户：`opinion_user`

## 7. system_identifier（集群身份，最关键证据）

| 数据目录 | system_identifier |
|---|---|
| `YQ\pgdata` | `7663057120701798896` |
| `舆情监测系统\pgdata` | `7663057120701798896` |

**结论**：两者是**同一 cluster 的文件级拷贝**（system_identifier 在 initdb 时生成、全局唯一）。但已分叉：

- `YQ\pgdata`：最新 checkpoint `2026/7/23 11:47:21`，early empty clone（仅早期结构）。
- `舆情监测系统\pgdata`：最新 checkpoint `2026/7/23 12:18:39`，活跃真实库。

## 8. 两个数据目录对比

| 项 | `YQ\pgdata`（陈旧克隆） | `舆情监测系统\pgdata`（真实库） |
|---|---|---|
| PG_VERSION | 16 | 16 |
| system_identifier | 7663057120701798896 | 7663057120701798896 |
| cluster state | in production | in production |
| latest checkpoint | 2026/7/23 11:47:21 | 2026/7/23 12:18:39 |
| 当前是否被 PG 实例使用 | 否 | 是（5433 只读实例） |
| 业务数据 | 空（早期克隆） | **完整** |

## 9. alembic_version（真实库，经 5433 只读 SELECT）

```
kwlex01
```

> 真实库**从未应用 `rbac10001`**。这与"事故迁移只改了 `YQ/pgdata`、未触碰真实库"完全一致。

## 10. 关键业务表行数（真实库，5433 只读 SELECT）

| 表 | 行数 |
|---|---|
| opinions（舆情） | 689 |
| events（事件） | 122 |
| event_opinions | 235 |
| data_sources（数据源） | 30 |
| keywords（含系统敏感词/监测词） | 46 |
| alert_records | 12 |
| alert_rules | 2 |
| collector_runs | 1672 |
| users | 1 |
| roles | 3 |

> 与事故前 RBAC-1 审计时记录完全一致，**真实业务数据完整无丢失**。

## 11. 是否存在多个 PostgreSQL 实例

- 当前**仅 1 个**运行中的 PG 实例（5433 只读，指向真实库）。
- 磁盘上存在 **2 个** Postgres 数据目录（`YQ\pgdata` 陈旧克隆 + `舆情监测系统\pgdata` 真实库），但只有一个被服务。

## 12. 是否存在错误数据目录风险

**是，存在明确风险：**

- `YQ\pgdata` 是早期空克隆，一旦被误启动为 5432，后端会连到空库，重现"数据消失"假象。
- 此前事故即因误启动 `YQ/pgdata` 导致。
- 风险等级：**高**，必须物理隔离或重命名该目录（见最终报告建议）。

## 13. 迁移前硬性门禁（MANDATORY GATE）

未来任何 `alembic upgrade` / `alembic downgrade` / 数据迁移 / 数据重建 / `seed` / `init_db` / `backfill` **执行前**，必须逐项确认；**任一不满足立即中止，禁止继续**：

| 门禁项 | 预期值 |
|---|---|
| A. PGDATA | `C:\Users\Administrator\Desktop\舆情监测系统\pgdata` |
| B. 连接数据库 | `opinion_db` |
| C. system_identifier | `7663057120701798896`（与真实库一致） |
| D. alembic_version（迁移前） | `kwlex01` |
| E. 关键业务数据数量 | opinions≈689、data_sources≈30、events≈122、keywords≈46 等**未意外归零** |
| F. 当前不是 `YQ\pgdata` | 必须排除 |

**启动 PG 前的标准核对清单（每次必打印）：**
1. PGDATA 绝对路径
2. PostgreSQL 监听端口
3. DATABASE_URL
4. 当前数据库名
5. 当前数据库用户
6. alembic_version
7. system_identifier
8. 关键业务表行数

若数据库连接失败：**禁止**通过启动其他 pgdata 来"尝试恢复"；必须停止并报告。

## 14. 本阶段已执行的只读操作

- 进程 / 端口枚举（PowerShell `Get-CimInstance Win32_Process` + `netstat`）
- 目录存在性检查（`ls`）
- PG_VERSION 读取（`cat`）
- `pg_controldata` 读取 system_identifier / cluster state / checkpoint（只读，不启动服务）
- `.env` / `config.py` 连接目标确认（grep）
- 5433 只读实例 SELECT 计数（仅 SELECT，无写入）

## 15. 本阶段未执行（禁令遵守确认）

✅ 未执行：`alembic upgrade` / `alembic downgrade` / `init_db.py` / 任何 seed 脚本
✅ 未执行：`INSERT` / `UPDATE` / `DELETE` / `DROP` / `TRUNCATE`
✅ 未执行：`initdb` / 创建或覆盖任何 pgdata
✅ 未启动采集器写入新数据
✅ 未删除、移动或覆盖任何 pgdata

---

*下一步（需授权）：本阶段第四步将停止 5433 只读实例，改用真实库目录在 5432 启动 PostgreSQL，使后端正确连接真实业务数据。RBAC 迁移（alembic upgrade head）仍**暂不执行**，留待后续授权阶段。*
