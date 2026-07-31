# 数据库环境固定与恢复前检查 — 最终报告

> 生成时间：2026-07-23 12:35 (GMT+8)
> 阶段定位：**数据库环境纠正与固定**（非功能开发）
> 操作人身份：Senior Developer（高级开发工程师）
> 本阶段写操作：**仅启动 PostgreSQL 服务**（5432 指向真实库），未执行任何迁移 / seed / 业务写入 / 采集器启动。

---

## 一、本阶段实际执行的操作（全部留痕）

| 步骤 | 操作 | 性质 |
|---|---|---|
| 1 | 枚举 PG 进程 / 端口、目录存在性、PG_VERSION、`pg_controldata`（system_identifier / checkpoint） | 只读 |
| 1 | 确认 `.env` / `config.py` 的 `DATABASE_URL = 127.0.0.1:5432/opinion_db` | 只读 |
| 1 | 经 5433 只读实例 SELECT 真实库计数 | 只读 |
| 2 | 生成 `database-environment-baseline.md`（含迁移前硬性门禁） | 文档 |
| 4 | **停止** 5433 只读临时实例（释放真实库锁） | 停服（不改数据） |
| 4 | 按安全门禁核对清单，以 `舆情监测系统\pgdata` 在 **5432** 启动 PostgreSQL | 起服（不改数据） |
| 4 | 经 5432 只读 SELECT 验证连接 / 库名 / 计数 / `opinion_test` 存在 | 只读 |
| 4 | 确认后端进程已重连 5432 真实库（`/health=ok`、业务读接口可达） | 只读确认 |

---

## 二、最终报告：必须回答的 7 个问题

### 1. 当前 YQ 后端连接的到底是哪一个 PostgreSQL 数据目录？

**现已纠正为真实库。** 证据链：

- 5432 当前由 PID 74656 的 `postgres.exe` 服务，其 `-D` 参数为：
  `C:/Users/Administrator/Desktop/舆情监测系统/pgdata`
- 后端进程（PID 48656，uvicorn）已重新建立到 5432 的数据库连接
  （`netstat` 显示 `48656 ↔ 5432 ESTABLISHED`）。
- `SELECT current_database()` = `opinion_db`，`alembic_version` = `kwlex01`，
  业务计数与真实库一致（见第 2 问）。

> 事故期间（RBAC-2 阶段）曾误将 5432 指向 `YQ/pgdata`（早期空克隆），导致"数据消失"假象。**该错误连接现已不存在**——`YQ/pgdata` 当前不被任何 PG 实例使用。

### 2. 真实业务数据库是否完整？

**完整，无丢失。** 经 5432（真实库）只读计数：

| 表 | 行数 | 说明 |
|---|---|---|
| opinions | **697** | 事故时 689，+8 为既有采集器正常运行的增量，非丢失 |
| events | 122 | 一致 |
| event_opinions | 235 | 一致 |
| data_sources | 30 | 一致 |
| keywords | 46 | 含系统敏感词 / 监测词，一致 |
| alert_records | 12 | 一致 |
| alert_rules | 2 | 一致 |
| collector_runs | 1672 | 一致 |
| users | 1 | admin |
| roles | 3 | admin / analyst / viewer |

- `alembic_version = kwlex01`（**真实库从未被 rbac10001 迁移触碰**）。
- `opinion_test` 测试库存在。
- **结论：真实业务数据一行未少。**

### 3. 当前 5432 是否已经正确指向 `舆情监测系统\pgdata`？

**是。** 已验证：

- 5432 `LISTENING`（PID 74656），命令行 `-D "...\舆情监测系统\pgdata" -p 5432`。
- 连接 `opinion_db` 成功，`system_identifier = 7663057120701798896`（与真实库身份一致）。
- 业务计数正确，`kwlex01` 符合迁移前预期。

### 4. `YQ\pgdata` 是否仍存在？

**是，仍存在。** 它是早期空克隆（PG 16，`system_identifier` 与真实库相同 `7663057120701798896`，最新 checkpoint `2026/7/23 11:47:21`），当前**不被任何 PG 实例使用**。它就是事故根因（被误启动为 5432）。

### 5. 是否建议将 `YQ\pgdata` 移出项目目录以避免误用？

**强烈建议，但本阶段未执行（受"禁止移动/删除 pgdata"约束，需你单独授权）。**

建议方案（任一，等你拍板）：
- 重命名为 `C:\Users\Administrator\Desktop\YQ\pgdata.DO_NOT_USE.bak`；或
- 整体移出工作区，例如 `C:\Users\Administrator\_archive\pgdata_empty_clone`。

目的：从根因上消除"下次有人启动 PG 时又误指到空克隆"的风险。

### 6. 后续 RBAC 迁移应该在哪个数据库上执行？

**在 `舆情监测系统\pgdata`（即 `127.0.0.1:5432/opinion_db`）上执行。**

- 迁移命令：`alembic upgrade head`（应用 `rbac10001` 及其链上前置迁移）。
- 执行前**必须**通过 `database-environment-baseline.md §13` 的硬性门禁 A–F：
  - A. PGDATA == `舆情监测系统\pgdata`
  - B. 连接库 == `opinion_db`
  - C. system_identifier == `7663057120701798896`
  - D. alembic_version 迁移前 == `kwlex01`
  - E. 业务计数未意外归零（opinions≈697 等）
  - F. 当前**不是** `YQ\pgdata`
- 任一不满足立即中止。

### 7. 如何保证以后 Work Buddy 不会再次连接错误数据库？

多层防御：

1. **根因隔离**：将 `YQ\pgdata` 移走 / 重命名（见第 5 问），使"错误目录"从工作区消失。
2. **项目记忆固化**（已写入 `MEMORY.md`）：真实库 = `舆情监测系统\pgdata`，`system_identifier = 7663057120701798896`；`YQ/pgdata` 为禁用空克隆；PG 启动前必核对 PGDATA/端口/库名/system_identifier。
3. **启动前强制核对清单**（安全规则 #5）：每次启动 PG 前打印 PGDATA、端口、DATABASE_URL、库名、用户、alembic_version、system_identifier、关键表计数；任一不符即停止。
4. **可选增强**：在后端 `config.py` 或 PG 启动脚本中加入 `system_identifier` 启动断言——连接后执行身份比对，不符则拒绝启动。
5. **迁移门禁前置**：任何 `alembic upgrade/downgrade/seed/init_db/backfill` 前必先跑门禁 A–F（已文档化于基线报告 §13）。

---

## 三、禁令遵守确认（本阶段）

✅ 未执行 `alembic upgrade` / `alembic downgrade`
✅ 未执行 `init_db.py` / 任何 seed 脚本 / backfill
✅ 未执行 `INSERT` / `UPDATE` / `DELETE` / `DROP` / `TRUNCATE`
✅ 未执行 `initdb` / 创建或覆盖任何 pgdata
✅ 未删除、移动或覆盖任何 pgdata（含 `YQ/pgdata` 原样保留）
✅ 未由本次操作启动采集器

> 说明：环境中存在**既有** collector / backend 进程（PID 11348、48656）在运行并向真实库写入（opinions 689→697 即其增量）。这是系统既有行为，**非本次启动触发**，且数据只增不减、无丢失风险。

---

## 四、当前状态小结

| 项 | 状态 |
|---|---|
| 5432 → 真实库 `舆情监测系统\pgdata` | ✅ 已纠正并验证 |
| 后端已重连真实库（`/health=ok`） | ✅ |
| RBAC 迁移（alembic upgrade head） | ⏸ **未执行**，等待下一步授权 |
| `YQ/pgdata` 空克隆 | ⚠ 仍存在，建议移走（待授权） |
| 迁移前门禁 | ✅ 已写入 `database-environment-baseline.md §13` |

---

## 五、下一步（需你授权）

1. **（建议）移走 `YQ/pgdata`** 空克隆，根因隔离。
2. **执行 RBAC 迁移**：在通过门禁 A–F 后，`alembic upgrade head` 于真实库补齐 RBAC 表/列/权限种子。
3. 之后继续 RBAC-2 未完成的：后端安全验收、补齐 `test_rbac.py`、前端 RBAC 管理闭环、联调冒烟。

*本阶段到此停止，等待授权。*
