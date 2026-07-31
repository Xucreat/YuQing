# RBAC-2B 数据库迁移与安全验收报告

**阶段**：RBAC-2B（真实数据库迁移与后端 RBAC 安全验收）
**日期**：2026-07-23
**执行人**：Senior Developer（高级开发工程师）
**唯一真实数据库**：`C:\Users\Administrator\Desktop\舆情监测系统\pgdata` → `opinion_db` @ `127.0.0.1:5432`
**system_identifier**：`7663057120701798896`
**归档克隆目录**：`C:\Users\Administrator\Desktop\YQ\pgdata.archive-early-clone`（已隔离，本次未触碰）

---

## 1. 迁移前数据库身份（Phase 1 安全门禁）

执行 `alembic upgrade head` 之前，先运行门禁脚本 `backend/scripts/db_identity_check.py`：

| 检查项 | 要求 | 实际 | 结果 |
|---|---|---|---|
| data identity | VERIFIED | VERIFIED | ✅ |
| database | opinion_db | opinion_db | ✅ |
| system_identifier | 7663057120701798896 | 7663057120701798896 | ✅ |
| alembic_version | kwlex01 | kwlex01 | ✅ |
| opinions | ≥ 100 | 705 | ✅ |
| 业务表与基线一致 | 仅允许正常增量 | 仅正常采集增量 | ✅ |

**结论：所有安全条件通过，允许执行迁移。**

---

## 2. 迁移前业务数据基线（Phase 2，kwlex01 状态，只读）

### 2.1 业务表精确行数

| 表 | 行数 |
|---|---|
| opinions | 711 |
| events | 123 |
| data_sources | 30 |
| keywords | 46 |
| event_opinions | 237 |
| alert_records | 12 |
| alert_rules | 2 |
| collector_runs | 1694 |
| users | 1 |
| roles | 3 |

### 2.2 表结构（迁移前，kwlex01）

**users 列**：`id, username, password_hash, role, created_at, is_active, last_login`
（注：`is_superuser / display_name / email / last_login_ip / updated_at` 此时尚不存在，由 rbac10001 新增）

**roles 列**：`id, name, display_name, permissions(JSONB), created_at`

### 2.3 roles.permissions JSONB 内容（迁移前）

| role | code | name | permissions(JSONB) |
|---|---|---|---|
| 1 | — | admin | `["*"]`（通配） |
| 2 | — | analyst | `["alerts:read","alerts:write","dashboard:read","events:read","events:write","keywords:read","keywords:write","opinions:read","opinions:write","propagation:read","reports:read","reports:write","sources:read"]`（13 个） |
| 3 | — | viewer | `["dashboard:read","events:read","opinions:read","reports:read"]`（4 个） |

> 17 个去重权限码全部落在 rbac10001 的 26 种子权限码集合内，无越界码。

### 2.4 admin 用户（迁移前）

`{id:1, username:"admin", role:"admin", is_active:true, last_login:<时间戳>, password_hash:<已置>}`（密码哈希脱敏）

---

## 3. 迁移执行结果（Phase 3）

```text
$ alembic upgrade head
[DB IDENTITY] VERIFIED  system_identifier=7663057120701798896  db=opinion_db
Running upgrade kwlex01 -> rbac10001
```

- **迁移命令**：`alembic upgrade head`
- **版本变化**：`kwlex01` → `rbac10001`
- **退出码**：`0`
- **事务性**：Alembic 使用 transactional DDL，任何失败会自动回滚（本次成功，无回滚）
- **使用的迁移文件**：`backend/alembic/versions/rbac10001.py`（RBAC-2A 阶段已修复版）

迁移实际落地内容：

1. users 新增 RBAC 字段：`is_superuser`、`display_name`、`email`、`last_login_ip`、`updated_at`
2. roles 规范化：`code`、`is_system`、`is_enabled`、`description`、`updated_at`（原 `permissions` JSONB 列被移除）
3. 新建表：`permissions`、`role_permissions`、`user_roles`、`user_login_logs`、`user_operation_logs`
4. 种子化 26 个权限（见第 7 节）
5. 旧 roles.permissions JSONB 权限迁移至 `role_permissions`（admin 的 `["*"]` 无对应 `*` 权限码 → 0 条显式授权，按设计走 `is_superuser` 旁路）
6. admin 标记为超级管理员（`is_superuser=true`）
7. analyst（13）/viewer（4）权限正确迁移
8. `keywords:write` 等历史权限码保留（见第 7 节列表）

---

## 4. Alembic 版本变化

| 项目 | 迁移前 | 迁移后 |
|---|---|---|
| alembic_version | `kwlex01` | `rbac10001` |

---

## 5. 迁移后业务数据对比（Phase 4，rbac10001 状态，只读）

| 表 | 迁移前 | 迁移后 | 变化 | 判定 |
|---|---|---|---|---|
| opinions | 711 | 718 | +7 | B. 正常采集增量 |
| events | 123 | 128 | +5 | B. 正常采集增量 |
| data_sources | 30 | 30 | 0 | 无变化 |
| keywords | 46 | 46 | 0 | 无变化 |
| event_opinions | 237 | 243 | +6 | B. 正常采集增量 |
| alert_records | 12 | 12 | 0 | 无变化 |
| alert_rules | 2 | 2 | 0 | 无变化 |
| collector_runs | 1694 | 1703 | +9 | B. 正常采集增量（采集器持续运行） |
| users | 1 | 1 | 0 | 无变化 |
| roles | 3 | 3 | 0 | 无变化 |

**判定结论**：
- 所有正向增量（opinions/events/event_opinions/collector_runs）与 `collector_runs +9` 相互印证，属**正常采集增量（B）**。
- 无负值、无丢失，迁移**未导致任何业务数据异常变化（A 不成立）**。
- 无外部异常原因（C 不成立）。

---

## 6. RBAC 表创建结果（Phase 5）

| 新表 | 行数 | 说明 |
|---|---|---|
| permissions | 26 | 种子权限目录 |
| role_permissions | 17 | analyst 13 + viewer 4 + admin 0（按设计） |
| user_roles | 0 | 预留多对多表，当前未使用（保留单 `role` 字段） |
| user_login_logs | 3 | 由本次验收中的登录调用写入（预期内） |
| user_operation_logs | 0 | 暂无操作日志（预期内） |

---

## 7. 26 个权限种子结果

`permissions` 表共 26 条，`permissions_count = 26`：

```text
alerts:read, alerts:write, audit_logs:read, collectors:read, collectors:write,
dashboard:read, events:read, events:write, keywords:delete, keywords:read,
keywords:write, login_logs:read, opinions:read, opinions:write, permissions:read,
propagation:read, reports:read, reports:write, roles:delete, roles:read,
roles:write, sources:read, sources:write, users:activate, users:read, users:write
```

✅ `keywords:write`、`keywords:read`、`keywords:delete` 等历史码全部保留。

---

## 8. 角色权限迁移结果

| 角色 | code | is_system | is_enabled | 迁移后 role_permissions | 来源 |
|---|---|---|---|---|---|
| 管理员 | admin | true | true | **0 条**（按设计） | 旧 `["*"]` 无 `*` 码 → 走 `is_superuser` 旁路 |
| 分析员 | analyst | true | true | 13 条 | 旧 JSONB 13 码全部有效 |
| 观察员 | viewer | true | true | 4 条 | 旧 JSONB 4 码全部有效 |

**analyst 13 码**：`alerts:read, alerts:write, dashboard:read, events:read, events:write, keywords:read, keywords:write, opinions:read, opinions:write, propagation:read, reports:read, reports:write, sources:read`

**viewer 4 码**：`dashboard:read, events:read, opinions:read, reports:read`

- **孤儿 role_permissions**：`0`（无指向不存在权限的授权行）
- **非法分配码**：`[]`（所有已分配 code 均存在于 26 种子集合）
- **旧 JSONB 权限迁移正确**：analyst/viewer 全部命中；admin 走超管旁路（见第 9 节）

---

## 9. admin 超管状态

迁移后 admin 用户：

```json
{
  "id": 1,
  "username": "admin",
  "role": "admin",
  "is_active": true,
  "is_superuser": true,
  "display_name": null,
  "email": null,
  "last_login_ip": "127.0.0.1",
  "updated_at": null
}
```

- ✅ `is_superuser = true`
- ✅ `is_active = true`
- ✅ 登录接口返回 `permissions = ["*"]`（经 `is_superuser OR role=='admin'` 旁路获得全权限）
- ✅ 即使 `role_permissions` 为 0 条，admin 仍通过 `is_superuser` 获得全部权限（满足验收要求）

---

## 10. 后端安全验收结果（Phase 6）

后端重启（仅迁移+数据验证通过后）于 `:8000`，启动无报错。逐项验收：

| # | 验收项 | 方法 | 结果 |
|---|---|---|---|
| 1 | /health | GET | **200** ✅ |
| 2 | admin 登录 | POST /api/login | **200**，`access_token` 已返回 ✅ |
| 3 | 返回 role / permissions | 登录响应 | `role=admin`，`permissions=["*"]` ✅ |
| 4 | admin 权限正确 | 登录响应 | 超管全权限，正确 ✅ |
| 5 | GET /api/users | 鉴权 GET | **200** ✅ |
| 6 | GET /api/roles | 鉴权 GET | **200**（3 角色）✅ |
| 7 | GET /api/permissions | 鉴权 GET | **200**（26 权限）✅ |
| 8 | GET /api/login-logs | 鉴权 GET | **200** ✅ |
| 9 | GET /api/operation-logs | 鉴权 GET | **200** ✅ |
| 10 | 业务接口 | GET | 全部 **200** ✅ |
| 10a | /api/keywords | | **200** ✅ |
| 10b | /api/opinions | | **200** ✅ |
| 10c | /api/events | | **200** ✅ |
| 10d | /api/admin/data-sources | | **200** ✅ |
| 10e | /api/dashboard/stats | | **200** ✅ |

> 备注：`/api/sources` 返回 404，原因是该路由不存在（真实数据源接口为 `/api/admin/data-sources`，已 200）。非缺陷。

---

## 11. 失败项及其性质

### 11.1 失败项：`GET /api/roles` 初始 500（已修复）

- **现象**：迁移后首次验收 `GET /api/roles` 返回 **500**。
- **根因**：`rbac10001` 为 `roles` 新增 `description` 列，定义为 **nullable**；当前 3 个角色该列均为 `NULL`。而序列化 schema `RoleOut.description` 原为 `str`（非可选，默认 `""`），`_serialize_role` 调用 `RoleOut.model_validate(role)` 时 Pydantic 拒绝 `None` → `ValidationError` → 500。
- **性质**：**序列化层类型与数据库列可空性不一致**（schema 类型对齐问题），**非业务逻辑变更、非权限模型修改、非数据问题**。
- **修复**（最小改动，1 行）：`backend/app/schemas/user.py` 中 `RoleOut.description` 由 `str = ""` 改为 `Optional[str] = None`，与 nullable 列对齐。
- **重启后端后复验**：`GET /api/roles` → **200**，返回 3 个角色且结构完整（含 `permissions`、`user_count`、`created_at`、`updated_at`）。
- **影响范围**：仅影响响应序列化，不触碰数据库、迁移、业务权限逻辑。

### 11.2 其余项

无其它失败项。所有安全门禁、数据完整性、RBAC 结构、后端验收项均通过。

---

## 12. 未完成事项

| 事项 | 状态 | 说明 |
|---|---|---|
| 前端 RBAC 管理闭环（Roles.vue / Users.vue / 路由守卫 / 401 处理） | 未做 | 属 Phase 7 明确禁止范围，等待下一步授权 |
| 修改 AppLayout / 路由 / 业务权限模型 / 风险评分 / 采集器 / 关键词逻辑 / 大屏 | 未做 | 本阶段禁止 |
| 后端 RBAC 单元测试（test_rbac.py） | 未做 | 用户要求"数据库迁移成功后可单独进行，不与迁移过程混在一起"，留待后续 |
| `roles.description` 填充默认值 | 未做 | 当前为 NULL（已通过 `Optional[str]` 兼容）；如需展示文案，建议后续单独迁移填充，不阻塞本阶段 |
| 临时验证脚本清理 | 待清理 | `backend/scripts/_rbac2b_accept.py` 与 `_rbac2b_verify.py` 为本次一次性只读验证辅助脚本，可删 |

---

## 总体结论

✅ **RBAC 迁移成功**：`kwlex01 → rbac10001`，真实库 `舆情监测系统\pgdata` 数据安全无丢失。
✅ **数据完整性通过**：业务表仅见正常采集增量，无迁移导致的异常变化。
✅ **RBAC 结构正确**：26 权限、3 角色、0 孤儿授权、admin 超管旁路正确。
✅ **后端安全验收全绿**：`/health`、登录、RBAC 与日志接口、全部既有业务接口均 200。
⚠️ **1 个非阻塞缺陷已修复**：`/api/roles` 序列化类型对齐（1 行改动），重启后验收通过。
⏸️ **前端与单测按 Phase 7 范围留待下一步**，本阶段不自动续作。

---

*报告结束。下一步建议：确认是否进入前端 RBAC 闭环开发与后端 RBAC 单元测试。*
