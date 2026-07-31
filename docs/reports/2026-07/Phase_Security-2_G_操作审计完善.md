# Phase Security-2-G：操作审计完善报告

- 生成时间：2026-07-31
- 检查对象：`app/models/audit.py`、`app/services/audit_service.py`、`app/api/users.py`

> 本报告由只读审计脚本自动生成，全过程未修改任何代码、数据库记录或权限数据。
> 数据来源：生产库 `opinion_db@127.0.0.1:5432`（仅 SELECT）+ FastAPI 路由内省 + 前端源码静态扫描。

---

## 一、审计模型现状

### 1.1 表结构

| 模型类 | 表名 | 用途 |
|---|---|---|
| `LoginLog` | `user_login_logs` | 登录/登出审计 |
| `OperationLog` | `user_operation_logs` | 操作审计 |

> 注意：`OperationLog.__tablename__` 为 `user_operation_logs`（非 `operation_logs`）。

### 1.2 `user_operation_logs` 字段

| 字段 | 含义 | 任务书要求 | 满足 |
|---|---|---|---|
| `operator_user_id` | 操作人 ID | 操作人 | ✅ |
| `operator_username_snapshot` | 操作人用户名快照 | 操作人 | ✅ |
| `target_user_id` | 被操作用户 ID | 被操作对象 | ✅ |
| `resource_type` / `resource_id` | 资源类型与 ID | 被操作对象 | ✅ |
| `created_at` | 操作时间 | 操作时间 | ✅ |
| `action` | 操作类型 | 操作类型 | ✅ |
| `request_method` / `request_path` | 请求方法与路径 | — | ✅ 附加 |
| `ip_address` / `user_agent` | 来源 IP 与 UA | — | ✅ 附加 |
| `result` / `error_message` | 结果与错误 | — | ✅ 附加 |
| `details_json` | 变更明细 | **修改前 / 修改后** | ⚠️ **仅记录修改后** |

---

## 二、审计埋点覆盖情况

### 2.1 用户管理（`app/api/users.py`）

| 操作 | 接口 | 行号 | `action` | 记录内容 | 判定 |
|---|---|---|---|---|---|
| 创建用户 | `POST /api/users` | L157 | `CREATE` | username、role 等 | ✅ 完整 |
| 修改用户 | `PUT /api/users/{id}` | L235 | `UPDATE` | `{"changes": <提交体>}` | ⚠️ **无修改前值** |
| 删除用户 | `DELETE /api/users/{id}` | L262 | `DELETE` | username | ✅ 完整 |
| 重置密码 | `POST /api/users/{id}/reset-password` | L285 | `PASSWORD_RESET` | username | ✅ 完整 |
| 启用用户 | `POST /api/users/{id}/activate` | L307 | `ENABLE` | target_user_id | ✅ 完整 |
| 停用用户 | `POST /api/users/{id}/deactivate` | L328 | `DISABLE` | target_user_id | ✅ 完整 |

### 2.2 角色与权限管理（`app/api/users.py`）

| 操作 | 接口 | 行号 | `action` | 记录内容 | 判定 |
|---|---|---|---|---|---|
| 创建角色 | `POST /api/roles` | L379 | `ROLE_CREATE` | name、code、权限列表 | ✅ 完整 |
| 修改角色/调整权限 | `PUT /api/roles/{id}` | L410 | `ROLE_UPDATE` | `{"changes": <提交体>}`（含 permission_codes） | ⚠️ **无修改前值** |
| 删除角色 | `DELETE /api/roles/{id}` | L436 | `ROLE_DELETE` | name | ✅ 完整 |

> **用户角色变更**（如 viewer → analyst）走 `PUT /api/users/{id}`，`action=UPDATE`，`details.changes` 中包含 `role` 新值 —— 变更**有记录**，但**看不到原角色**。

### 2.3 其它模块埋点分布

| 模块 | `log_operation` 调用次数 |
|---|---|
| `app/api/users.py` | 10 |
| `app/api/reports.py` | 5 |
| `app/api/collector.py` | 3 |
| `app/api/opinions.py` | 2 |
| `app/services/audit_service.py`（`audit_write` 上下文管理器，用于数据源） | 2 |

> 任务书 Phase G 只要求「用户管理 + 权限管理」可追溯，业务模块（events/alerts/keywords）无审计埋点**不属于本阶段缺口**，仅作现状记录。

---

## 三、任务书要求逐条核对

| # | 要求 | 现状 | 判定 |
|---|---|---|---|
| 1 | 用户创建有记录 | `CREATE` | ✅ |
| 2 | 用户修改有记录 | `UPDATE` | ✅ |
| 3 | 用户禁用有记录 | `DISABLE`（另有 `ENABLE`） | ✅ |
| 4 | 角色变更有记录 | `UPDATE`（用户主角色）/ `ROLE_UPDATE`（角色定义） | ✅ |
| 5 | 权限调整有记录 | `ROLE_UPDATE`（含 `permission_codes`） | ✅ |
| 6 | 用户-角色关联变更有记录 | `UPDATE` 中的 `role` 字段 | ✅ |
| 7 | 记录操作人 | `operator_user_id` + 用户名快照 | ✅ |
| 8 | 记录被操作对象 | `target_user_id` + `resource_type/id` | ✅ |
| 9 | 记录操作时间 | `created_at` | ✅ |
| 10 | 记录操作类型 | `action` | ✅ |
| 11 | **记录修改前 / 修改后内容** | 仅 `changes`（修改后） | ⛔ **未满足** |

---

## 四、缺口与最小化修复建议（仅建议，未实施）

### SEC2-05｜MEDIUM｜审计缺少变更前值

**问题**：`update_user`（L235）与 `update_role`（L410）的 `details` 仅含提交体。

**最小化修复方案**（不改表结构、不改 RBAC 模型、不影响业务逻辑）：

```python
# app/api/users.py —— update_user，在应用变更 *之前* 抓取快照
before = {"username": user.username, "display_name": user.display_name,
          "email": user.email, "role": user.role,
          "is_active": user.is_active, "is_superuser": user.is_superuser}
# ... 应用变更 ...
changes = body.model_dump(exclude_unset=True, mode="json")
log_operation(
    db, action="UPDATE", operator=current_user, request=request,
    resource_type="user", resource_id=str(user.id), target_user_id=user.id,
    details={"before": {k: before[k] for k in changes if k in before},
             "after": changes},
)
```
```python
# app/api/users.py —— update_role，同理
before = {"name": role.name, "display_name": role.display_name,
          "description": role.description,
          "permission_codes": sorted(p.code for p in role.permissions)}
# ... 应用变更 ...
log_operation(
    db, action="ROLE_UPDATE", operator=current_user, request=request,
    resource_type="role", resource_id=str(role.id),
    details={"before": before, "after": changes},
)
```

**变更影响评估**：

| 项 | 影响 |
|---|---|
| 数据库表结构 | ❌ 不变（`details_json` 为 JSON 字段，向下兼容） |
| RBAC 模型 | ❌ 不变 |
| 业务逻辑 | ❌ 不变 |
| 现有日志数据 | ❌ 不受影响（旧记录仍为 `changes` 键，前端需兼容两种结构） |
| 前端 `OperationLogs.vue` | ⚠️ 需兼容 `details.changes` 与 `details.before/after` 两种格式 |

---

## 五、阶段结论

1. 审计模型 `user_operation_logs` 字段设计完备，**11 项要求中满足 10 项**。
2. 用户管理 6 类操作、角色权限管理 3 类操作**全部有埋点**，无遗漏。
3. **唯一缺口**：变更前值未记录（SEC2-05，MEDIUM），已给出不改表结构的最小化修复方案。
4. 本阶段**未做任何修改**。
