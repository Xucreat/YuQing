# RBAC-2A：数据库环境固定与迁移前安全门禁 — 实施报告

> 阶段目标：隔离错误克隆数据目录、建立数据库身份安全门禁、增强启动可见性。
> **本阶段未执行任何迁移、seed、写业务数据、DROP/TRUNCATE 或采集器写入。**

---

## 1. 代码工作区

- `C:\Users\Administrator\Desktop\YQ` —— 当前代码开发工作区（仅代码，不含生产数据）。

## 2. 唯一真实数据库目录

- `C:\Users\Administrator\Desktop\舆情监测系统\pgdata` —— 唯一真实 PostgreSQL 数据目录。
- PostgreSQL 16，监听 `127.0.0.1:5432`，数据库 `opinion_db`。
- `system_identifier = 7663057120701798896`。

## 3. 错误克隆目录的隔离结果

- 原错误目录 `C:\Users\Administrator\Desktop\YQ\pgdata`（早期空克隆，曾被误启动并执行过 RBAC 迁移）已**重命名隔离**：
  - 新名称：`C:\Users\Administrator\Desktop\YQ\pgdata.archive-early-clone`
  - 操作性质：**仅重命名**，未删除、未覆盖、未初始化、未修改其中数据（PG_VERSION=16 完好）。
- 隔离前已确认：无任何 PostgreSQL 进程占用 `YQ\pgdata`（当前无 PG 进程使用该目录）。
- 隔离后确认：`YQ` 工作区内**不再存在名为 `pgdata` 的 PostgreSQL 数据目录**。
- 该归档目录**保留不删**（符合“禁止删除”要求），仅作事故留证与潜在回溯。

## 4. PostgreSQL 当前实际 data_directory

- 通过 PowerShell 干净 PATH（`PG_BIN;C:\Windows\System32;C:\Windows\System32\wbem`）启动的实例，
  其 `data_directory` 物理路径为 `C:\Users\Administrator\Desktop\舆情监测系统\pgdata`。
- ⚠️ **重要环境约束**：本环境中 `data_directory` **无法通过 SQL 读取**。
  原因：数据目录路径含中文（`舆情监测系统`），以 GBK 字节存储，而服务器编码为 UTF8，
  PG 在 `SHOW data_directory` 转换时抛 `invalid byte sequence for encoding UTF8`，
  任何 `client_encoding` 均无法绕过（已实测 GBK / GB18030 / GB2312 均失败）。
  因此门禁对 `data_directory` 采“尽力而为”策略：可读且不匹配才中止；不可读时退化为业务指纹校验。

## 5. system_identifier

- `7663057120701798896`（与预期基线一致，VERIFIED）。
- ⚠️ 注意：克隆库 `pgdata.archive-early-clone` 与真实库**共享同一 `system_identifier`**
  （文件级拷贝，initdb 时生成后不变）。故 `system_identifier` 只能检测“完全不同的 cluster”，
  **不能在克隆/真实之间区分**。本环境真正区分二者的是业务指纹（见第 9 节）。

## 6. DATABASE_URL

```
postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_db
```
- Host: `127.0.0.1`，Port: `5432`，Database: `opinion_db`，User: `opinion_user`。

## 7. alembic_version（当前真实库）

- `kwlex01`（RBAC 迁移 `rbac10001` 尚未在真实库应用 —— 符合本阶段“不执行迁移”的边界）。
- 通过 `alembic current`（只读）验证，门禁触发并打印 VERIFIED 后返回 `kwlex01`。

## 8. 业务表行数（只读核验，全部完整）

| 表 | 行数 | 表 | 行数 |
|---|---|---|---|
| opinions | **697** | alert_records | 12 |
| events | 123 | alert_rules | 2 |
| event_opinions | 237 | collector_runs | 1681 |
| data_sources | **30** | users | 1 |
| keywords | **46** | roles | 3 |

- RBAC 新表（`permissions` / `role_permissions` / `user_roles` / `user_login_logs` / `user_operation_logs`）
  在真实库**当前均不存在**（符合预期，迁移前状态）。
- `roles` 表已存在（来自早期 `p2_rbac` 迁移，仍为 JSONB `permissions` 旧结构，尚未被 `rbac10001` 规范化）。
- 数据相较事故期（689→697 等）为正常采集增量，**无丢失**。

## 9. 新增的安全门禁（位置与机制）

### 新增文件

| 文件 | 作用 |
|---|---|
| `backend/app/core/db_identity.py` | 核心门禁：预期身份基线 + `verify_database_identity()` + `assert_identity_for_migration()` + `print_safety_block()` |
| `backend/scripts/db_identity_check.py` | CLI 检查：`python scripts/db_identity_check.py`，退出码 0=VERIFIED / 2=MISMATCH / 3=连接失败 |
| `backend/scripts/pg_start_safe.py` | 安全启动脚本：data_directory **固定为预期基线**（不接受外部目录覆盖），启动前打印安全块、启动后再次校验身份 |

### 已接入的现有流程

- `backend/alembic/env.py`：`run_migrations_online()` 开头调用 `assert_identity_for_migration()`。
  **任何 `alembic upgrade/downgrade` 在执行前都会先校验身份，不匹配立即以退出码 2 中止。**
  （已用 `alembic current` 只读验证：门禁触发、打印 `[DATABASE IDENTITY: VERIFIED]`。）
- `backend/scripts/init_db.py`：`__main__` 入口在写库前调用 `assert_identity_for_migration()`。
- `backend/tests/conftest.py`：测试库 `opinion_test` 是独立 cluster（system_identifier 不同），
  为避免误伤，设置 `DB_IDENTITY_CHECK=off`（已知安全场景显式关闭）。

### 门禁判定逻辑（环境修正版）

按强度分层，任一“检测到不匹配”即中止：

1. **system_identifier**（强信号，可检测完全不同 cluster）—— 不匹配 → ABORT。
2. **data_directory**（尽力而为）—— 若 SQL 可读且不匹配 → ABORT；本环境不可读时降级为警告。
3. **业务指纹**（本环境真正可靠的不同iator）—— 当连接库 == 预期库 `opinion_db` 时，
   校验 `opinions` 行数 ≥ `EXPECTED_MIN_OPINIONS`（默认 100）。
   克隆/空库 opinions≈0 → 触发 ABORT，从根本上防止误连空克隆。

> 为什么业务指纹是本环境的关键：克隆库与真实库 `system_identifier` 相同、且 `data_directory`
> 不可读，只有业务数据量能稳定区分两者（真实 697 vs 克隆 0）。

### 开关与可覆盖配置（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DB_IDENTITY_CHECK` | `on` | 设 `off` 整体关闭门禁（测试等已知安全场景） |
| `EXPECTED_PG_SYSTEM_IDENTIFIER` | `7663057120701798896` | 预期 system_identifier |
| `EXPECTED_PG_DATA_DIRECTORY` | `舆情监测系统\pgdata` | 预期 data_directory |
| `EXPECTED_PG_DATABASE` | `opinion_db` | 预期数据库名 |
| `EXPECTED_MIN_OPINIONS` | `100` | 业务指纹阈值 |

## 10. 如何使用安全门禁

### (a) 迁移前快速自检（推荐每次执行前）
```bash
cd backend
PYTHONPATH=. .venv/Scripts/python.exe scripts/db_identity_check.py
# 输出 [DATABASE SAFETY CHECK] 块 + [DATABASE IDENTITY: VERIFIED]  (退出码 0)
# 或 [DATABASE IDENTITY: MISMATCH — ABORTED]                        (退出码 2)
```

### (b) 启动 PostgreSQL（仅限预期数据目录）
```bash
cd backend
PYTHONPATH=. .venv/Scripts/python.exe scripts/pg_start_safe.py --port 5432
# 脚本将 data_directory 固定为预期基线，启动前打印安全块、启动后再次校验身份。
# 绝不会接受指向 YQ\pgdata.archive-early-clone 等其它目录的参数。
```
> 注意：本机曾出现 `pg_ctl` 在 Git-Bash 污染 PATH 下因 DLL 冲突崩溃（0xC0000142）。
> 已验证可靠的启动方式是 **PowerShell 干净 PATH**（见报告末尾“启动约定”）。

### (c) 执行 Alembic 迁移（自动触发门禁）
```bash
cd backend
PYTHONPATH=. .venv/Scripts/python.exe -m alembic upgrade head
# run_migrations_online 会自动先调用 assert_identity_for_migration()：
#   身份不符 → 打印 MISMATCH 并以退出码 2 中止，绝不写库。
#   身份符合 → 打印 VERIFIED，继续执行迁移。
```

### (d) 执行 seed / init_db（自动触发门禁）
```bash
cd backend
PYTHONPATH=. .venv/Scripts/python.exe scripts/init_db.py
# __main__ 入口先调用 assert_identity_for_migration()，身份不符即中止。
```

## 11. 后续 RBAC 迁移的前置条件（门禁 A–F）

在执行 `alembic upgrade head`（将 `rbac10001` 落到真实库）之前，必须全部满足：

- **A. PGDATA == `C:\Users\Administrator\Desktop\舆情监测系统\pgdata`** —— 已固定（克隆已隔离重命名，启动脚本硬编码此目录）。
- **B. 当前连接数据库 == `opinion_db`** —— 已满足（DATABASE_URL 指向它）。
- **C. system_identifier 与真实库一致（7663057120701798896）** —— 已满足。
- **D. alembic_version 与预期一致（`kwlex01`，迁移前）** —— 当前真实库即 `kwlex01`，满足。
- **E. 关键业务数据数量与迁移前预期一致（opinions≈697 / data_sources=30 / keywords=46 等）** —— 已满足。
- **F. 当前不是 `YQ\pgdata`** —— 已满足（`YQ\pgdata` 已不存在，仅余 `pgdata.archive-early-clone` 归档且未运行）。

门禁会自动校验 A/C/E（B/D 由 DATABASE_URL 与版本链保证）。此外需复用 RBAC-1 报告中
已修复的迁移脚本（`rbac10001.py` 已将 `uq_roles_code` 唯一约束移到数据迁移之后，避免空 code 冲突）。

## 12. 本阶段禁止操作执行情况

- ❌ 未执行 `alembic upgrade/downgrade`；
- ❌ 未执行 `init_db.py` / seed；
- ❌ 未执行任何 INSERT/UPDATE/DELETE/DROP/TRUNCATE；
- ❌ 未做数据迁移 / 重建 / 回填；
- ❌ 未启动采集器产生新数据；
- ❌ 未删除真实数据库目录；
- ❌ 未删除 `YQ\pgdata.archive-early-clone`。

仅执行：只读核查、进程/端口检查、身份检查、目录重命名隔离、门禁代码新增与只读 `alembic current` 验证。

## 13. 启动约定（避免再次 DLL 崩溃）

- **优先用 PowerShell 干净 PATH 启动**：
  ```powershell
  $env:PATH = "C:\Users\Administrator\Desktop\YQ\pgsql\pgsql\bin;C:\Windows\System32;C:\Windows\System32\wbem"
  & "C:\Users\Administrator\Desktop\YQ\pgsql\pgsql\bin\pg_ctl.exe" -D "C:\Users\Administrator\Desktop\舆情监测系统\pgdata" -l "C:\Users\Administrator\Desktop\舆情监测系统\pg_start_safe.log" start
  ```
- 禁止从 Git-Bash 直接 `pg_ctl`（其 MSYS DLL 会导致 postgres 子进程 0xC0000142 崩溃）。
- `pg_start_safe.py` 已在子进程层面设置干净 PATH，但建议仍从干净 shell 调用。

---

## 结论

- 错误克隆目录已安全隔离，工作区不再含可被误启的 `pgdata`。
- 真实库身份已基线化并 VERIFIED（system_identifier / alembic=kwlex01 / opinions=697）。
- 数据库身份安全门禁已落地：可复用模块 + CLI + Alembic 自动拦截 + init_db 拦截 + 安全启动脚本，
  且针对本环境“克隆库共享 system_identifier、data_directory 不可读”的特点，以业务指纹作为可靠兜底。
- **下一步（需单独授权）**：在真实库执行 `alembic upgrade head` 完成 RBAC 迁移，并继续 RBAC-2 后端验收、测试与前端闭环。
