# Phase Security-2：全角色 RBAC 安全审计与权限治理 · 实施报告

- **系统**：廊坊市全域舆情监测系统
- **阶段**：Phase Security-2
- **报告日期**：2026-07-31
- **执行方式**：只读审计 → 生成报告 → 风险确认 → 实施整改 → 测试验证 → 交付
- **数据来源**：生产库 `opinion_db@127.0.0.1:5432`（**全程仅 SELECT**）、`backend/app` 源码、`frontend/src` 源码、FastAPI 运行时路由自省
- **最终状态**：✅ 已完成。业务写接口权限覆盖率 **100%**，前端操作门控覆盖率 **100%**，权限变更审计前后值 **100%** 落库

---

## 一、执行摘要

本阶段对系统全部 **3 个角色 / 31 项权限 / 101 条 API 路由 / 30 个前端文件（138 处操作入口）** 做了端到端 RBAC 安全审计，共识别 **8 项风险**（1 HIGH / 4 MEDIUM / 3 LOW）。

经与业务方确认后，本轮实施 **3 项整改**（SEC2-01 / SEC2-05 / SEC2-07），其余 5 项因涉及架构级决策或数据变更，明确列为**单独立项**，不在本轮动手。

| 关键指标 | 整改前 | 整改后 |
|---|---|---|
| 业务写接口（POST/PUT/PATCH/DELETE）权限覆盖率 | 46/47 = **97.9%** | 47/47 = **100%** ✅ |
| 前端敏感操作门控覆盖率 | 23/24 = **95.8%** | 24/24 = **100%** ✅ |
| 前端路由权限门控覆盖率 | 13/13 = **100%** | 13/13 = **100%** ✅ |
| 用户/角色变更审计含「修改前」值 | 0% | **100%** ✅ |
| 数据库权限完整性（悬挂外键/孤儿用户角色） | 0 异常 | 0 异常 ✅ |
| RBAC 自动化测试用例数 | 58 | **70**（+12 全角色动态用例） |

**红线遵守情况：**

| 约束 | 遵守情况 |
|---|---|
| 先审计后修改，不跳过审计阶段 | ✅ Phase A–G + 11 + 12 全部只读完成并出具报告后才动手 |
| 不破坏现有 RBAC 模型（User→Role→Permission） | ✅ 未删表、未改关联模型、未引入新框架 |
| 不引入 Redis / 不改 JWT 结构 / 不改 admin 超管逻辑 | ✅ 零改动 |
| 不影响采集 / 风险评分 / 事件聚合 / 预警计算 / AI 业务逻辑 | ✅ 本轮全部改动仅位于权限校验与审计日志层 |

---

## 二、审计范围与方法

### 2.1 审计对象

| 维度 | 范围 | 方法 |
|---|---|---|
| 角色与权限数据 | `roles` / `permissions` / `role_permissions` / `user_roles` / `users` | SQLAlchemy `text()` 只读 SELECT，直连生产库 |
| API 权限 | FastAPI `app.main:app` 全部 101 条 `/api` 路由 | 运行时导入 app，递归遍历 `route.dependant`，从 `require_permission` 闭包 cell 中提取权限码 |
| 前端权限 | `frontend/src` 30 个文件、138 处 `@click` / `router.push` / Dialog 入口 | 静态扫描 + **逐文件人工复核**（含 node 明文读取） |
| 操作审计 | `user_operation_logs`（模型 `OperationLog`） | 模型字段核对 + 生产数据统计 + 调用点全量 grep |

### 2.2 关键方法说明

- **API 权限自省不靠 grep**：`require_permission("x")` 返回的是闭包 `checker`，源码 grep 会漏掉 router 级 `dependencies=[...]` 的继承关系。本次改用 FastAPI 运行时依赖树遍历，覆盖 router 级与 endpoint 级两种挂载方式，结果与实际鉴权行为完全一致。
- **前端扫描必须人工复核**：初次正则启发式扫描（`@click` 向上回溯 4 行找 `v-if`）报出 46 处「无门控」，逐一复核后 **45 处为误报**——它们由容器级 `v-if="isSuperuser"`（`DataManage.vue`）、`v-if/v-else` 分支（`Keywords.vue`）、块级 `v-if="canUpdateEvent"`（`Events.vue`）或路由级 `meta.permission` 兜底。真实缺口只有 1 处。
- **Windows 文件虚拟化规避**：部分前端 `.vue` 文件经原生读取会呈现乱码字节，本次统一使用 `node -e "fs.readFileSync(f,'utf8')"` 读取明文，确保审计基于真实源码而非损坏视图。

---

## 三、角色清单与权限矩阵（生产实况）

### 3.1 角色总览

| ID | 角色名 | 编码 | 显示名 | 系统角色 | 启用 | 用户数 | 授权条数 |
|---|---|---|---|---|---|---|---|
| 1 | `admin` | admin | 管理员 | ✅ | ✅ | 1 | 4（+ 代码级 `*` 短路） |
| 2 | `analyst` | analyst | 分析员 | ✅ | ✅ | 1 | 16 |
| 3 | `viewer` | viewer | 观察员 | ✅ | ✅ | 1 | 5 |

- 用户总数 **3**，超级管理员 **1**（`is_superuser=true`）
- 权限目录共 **31** 项，`role_permissions` 授权 **25** 条

### 3.2 角色—权限矩阵

| 权限码 | admin | analyst | viewer |
|---|:--:|:--:|:--:|
| ai:analyze | ✅ | ✅ | — |
| ai:manage | ✅ | — | — |
| ai:search | ✅ | ✅ | — |
| alerts:read | *（超管短路）* | ✅ | ✅ |
| alerts:write | *（超管短路）* | ✅ | — |
| dashboard:read | *（超管短路）* | ✅ | ✅ |
| events:read | *（超管短路）* | ✅ | ✅ |
| events:write | *（超管短路）* | ✅ | — |
| keywords:read | *（超管短路）* | ✅ | — |
| keywords:write | *（超管短路）* | ✅ | — |
| opinions:read | *（超管短路）* | ✅ | ✅ |
| opinions:write | *（超管短路）* | ✅ | — |
| propagation:read | *（超管短路）* | ✅ | ✅ |
| reports:export | *（超管短路）* | ✅ | — |
| reports:manage | ✅ | — | — |
| reports:read | *（超管短路）* | ✅ | — |
| reports:write | *（超管短路）* | ✅ | — |
| sources:read | *（超管短路）* | ✅ | — |
| **孤儿权限（13 项）** | — | — | — |
| audit_logs:read / login_logs:read / permissions:read | 无角色持有 | | |
| roles:read / roles:write / roles:delete | 无角色持有 | | |
| users:read / users:write / users:activate | 无角色持有 | | |
| collectors:read / collectors:write / keywords:delete / sources:write | 无角色持有 | | |

> **关于 admin 的 4 条显式授权**：`admin` 在 `role_permissions` 中仅有 4 条记录，其余权限依靠 `is_superuser_user()` 短路（`get_user_permissions` 对超管直接返回 `["*"]`）。这是既有设计，任务书明令禁止改动超管逻辑，本轮不动（详见 SEC2-03）。

---

## 四、发现的问题清单

| 编号 | 风险等级 | 类型 | 问题描述 | 本轮处理 |
|---|---|---|---|---|
| **SEC2-01** | 🔴 **HIGH** | 越权 | `POST /api/propagation/rebuild/{event_id}` 是写操作（重建传播链、写 `propagation_nodes`），但仅要求登录，**viewer 可越权触发**；前端按钮亦无门控 | ✅ **已修复** |
| **SEC2-02** | 🟡 MEDIUM | 覆盖不足 | 26 个 GET 接口未强制 `:read` 权限，`alerts/dashboard/events/opinions/propagation:read` 5 项权限实际只由前端路由守卫兜底，后端未强校验 | ⛔ 架构级决策，单独立项 |
| **SEC2-03** | 🟡 MEDIUM | 数据缺陷 | `admin` 角色 `role_permissions` 仅 4 条，授权数据残缺，完全依赖代码短路；若未来关闭短路会瞬间失权 | ⛔ 涉及超管逻辑，禁改，单独立项 |
| **SEC2-04** | 🟡 MEDIUM | 职责下放受阻 | 13 项孤儿权限（用户/角色/权限/审计管理类）无任何角色持有，管理职责无法下放给非超管 | ⛔ 业务方确认**维持现状** |
| **SEC2-05** | 🟡 MEDIUM | 审计缺陷 | `update_user` / `update_role` 审计日志只记 `changes`（提交值），**无「修改前」值**，无法回溯权限变更前后差异，不满足 Phase G 硬性要求 | ✅ **已修复** |
| **SEC2-06** | 🟢 LOW | 冗余 | `reports:write` 与 `reports:export` 语义重复，analyst 同时持有 | ⛔ 涉及数据清理，风险 > 收益 |
| **SEC2-07** | 🟢 LOW | UI 门控 | `Opinions.vue` 批量删除按钮使用 `:disabled="!canDelete"` 而非 `v-if`，无权限用户仍可见按钮（后端已拦截，仅体验/信息暴露问题） | ✅ **已修复** |
| **SEC2-08** | 🟢 LOW | 死权限 | `ai:manage`、`collectors:read/write`、`keywords:delete`、`reports:write`、`sources:write` 共 6 项前后端均未引用 | ⛔ 规划预留，保留 |

**职责冲突专项结论**：`analyst` 与 `viewer` 均**未持有**任何 `users:*` / `roles:*` / `permissions:*` / `audit_logs:*` / `login_logs:*` 权限，**不存在职责冲突（无 HIGH 项）**。该结论已固化为自动化断言（见 §8）。

---

## 五、本轮整改内容

### 5.1 SEC2-01｜传播链重建接口补 `events:write` 门控

**后端** `backend/app/api/propagation.py`

```python
+ from app.core.permissions import require_permission

  @propagation_router.post("/rebuild/{event_id}", response_model=PropagationRebuildResponse)
- def rebuild(event_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
+ def rebuild(
+     event_id: int,
+     db: Session = Depends(get_db),
+     _u: User = Depends(require_permission("events:write")),
+ ):
+     """重建事件传播链（写操作，需 events:write 权限）。"""
```

**前端** `frontend/src/views/Propagation.vue`

```diff
- <el-button type="warning" size="small" :loading="rebuilding" @click="handleRebuild">构建传播链</el-button>
+ <el-button v-if="canRebuild" type="warning" size="small" :loading="rebuilding" @click="handleRebuild">构建传播链</el-button>

+ const { hasPermission } = usePermission()
+ const canRebuild = computed(() => hasPermission('events:write'))

  async function handleRebuild() {
+   if (!canRebuild.value) { ElMessage.warning('无权限执行该操作'); return }
```

- **权限码选择**：`events:write`（业务方确认）。传播链依附于事件，与「手动聚合 / 事件处置 / 事件删除」同属事件写操作，语义一致，且 analyst 已持有该权限、viewer 未持有，符合预期分权。
- **未新增权限码**，未改动权限目录，向后兼容。

**运行时验证**：

```
['GET']  /api/propagation/events            -> LOGIN_ONLY
['POST'] /api/propagation/rebuild/{event_id} -> ['events:write']   ✅
['GET']  /api/propagation/graph/{event_id}   -> LOGIN_ONLY
```

### 5.2 SEC2-05｜权限变更审计补「修改前 / 修改后」快照

**后端** `backend/app/api/users.py` — 新增 3 个纯函数辅助（无副作用）：

```python
_USER_AUDIT_FIELDS = ("display_name", "email", "role", "is_superuser", "is_active")
_ROLE_AUDIT_FIELDS = ("display_name", "description", "is_enabled")

def _user_audit_snapshot(user) -> dict   # 含附加角色 id 列表，不含密码
def _role_audit_snapshot(role) -> dict   # 含权限码集合
def _diff_snapshot(before, after) -> list[str]  # 实际变化字段
```

改造 4 个写入点：

| 接口 | action | 新增字段 |
|---|---|---|
| `PUT /api/users/{id}` | `UPDATE` | `before` / `after` / `changed_fields` / `password_changed`，且 `changes.password` 强制脱敏为 `***` |
| `DELETE /api/users/{id}` | `DELETE` | `before`（删除前完整快照）/ `after: null` |
| `PUT /api/roles/{id}` | `ROLE_UPDATE` | `before` / `after` / `changed_fields` / **`permissions_added`** / **`permissions_removed`** |
| `DELETE /api/roles/{id}` | `ROLE_DELETE` | `before`（含被删角色权限集）/ `after: null` |

**安全保证**：快照字段白名单固定，**永不包含 `password` / `password_hash`**；密码变更仅落 `password_changed: true` 布尔标记。该约束已由测试 `test_user_password_reset_not_logged_in_plaintext` 守护。

**前端** `frontend/src/views/OperationLogs.vue` — 详情列由裸 JSON 字符串改为「摘要 + 悬浮完整 JSON」：

```
role: "viewer" → "analyst"        （用户角色变更）
+权限 events:write                 （角色权限新增）
密码已重置                          （密码变更标记）
```

无法解析或旧格式日志自动回退为原始 JSON 展示，**向后兼容历史 257 条日志**。

### 5.3 SEC2-07｜舆情批量删除按钮改为隐藏

**前端** `frontend/src/views/Opinions.vue`

```diff
- <button class="btn btn-danger" :disabled="!canDelete" @click="batchDelete">删除</button>
+ <button v-if="canDelete" class="btn btn-danger" @click="batchDelete">删除</button>
```

`canDelete = computed(() => isSuperuser.value)`，逻辑不变，仅从「置灰」改为「隐藏」，与项目其余页面（`Events.vue` / `Keywords.vue`）门控风格统一。

### 5.4 改动文件清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `backend/app/api/propagation.py` | 后端 | SEC2-01：新增 `require_permission("events:write")` |
| `backend/app/api/users.py` | 后端 | SEC2-05：新增 3 个快照辅助函数，改造 4 个审计写入点 |
| `frontend/src/views/Propagation.vue` | 前端 | SEC2-01：按钮 `v-if` + 函数守卫 |
| `frontend/src/views/Opinions.vue` | 前端 | SEC2-07：`:disabled` → `v-if` |
| `frontend/src/views/OperationLogs.vue` | 前端 | SEC2-05：详情列摘要渲染 + 悬浮完整 JSON |
| `backend/tests/test_rbac_hardening.py` | 测试 | Phase 10 + Phase H：新增 12 个用例 |

**未改动**：任何数据库表结构、任何权限数据、`app/core/permissions.py`、JWT/登录逻辑、采集/风险/事件/预警/AI 任何业务代码。**无 Alembic 迁移**。

---

## 六、API 权限覆盖率（整改后）

运行时自省 `app.main:app`，统计 `/api` 前缀全部路由：

| 指标 | 数值 |
|---|---|
| API 路由总数 | 101 |
| 写操作（POST/PUT/PATCH/DELETE） | 49 |
| 其中受 `require_permission` / `require_admin` 保护 | **47** |
| 未受保护的写操作 | 2 → `POST /api/login`、`POST /api/logout` |
| **业务写接口覆盖率** | **47/47 = 100%** ✅ |
| 读操作（GET） | 52 |
| 其中受权限门控 | 26（50.0%，其余为登录态门控，详见 SEC2-02） |
| 完全无鉴权的路由 | 1 → `POST /api/login`（登录端点，设计如此） |

> `POST /api/login`（无鉴权）与 `POST /api/logout`（登录态）属于鉴权体系入口/出口，不适用权限校验，不计入缺口。**整改后业务写接口零缺口。**

复核脚本：`backend/_sec2_recheck.py`（只读，可随时重跑），输出 `backend/_sec2_recheck.json`。

---

## 七、前端权限覆盖率（整改后）

| 指标 | 数值 |
|---|---|
| 扫描文件 | 30（23 个 view + 7 个 component） |
| 操作入口 | 138 |
| 需权限管控的敏感操作 | 24 |
| 已门控 | **24（100%）** ✅ |
| 带 `meta.permission` 的路由 | 13 |
| `beforeEach` 守卫覆盖 | **13/13 = 100%** ✅ |

**门控实现方式分布**（均为合规实现）：

| 方式 | 示例 | 数量 |
|---|---|---|
| 按钮级 `v-if="canXxx"` | `Events.vue`、`Propagation.vue`（本轮新增）、`Opinions.vue`（本轮改造） | 主流 |
| 容器级 `v-if="isSuperuser"` | `DataManage.vue` 的 数据源 / 采集日志 / 博查线索 三个 Tab | 3 个 Tab（含 10 处操作） |
| 分支级 `v-if / v-else` | `Keywords.vue` 编辑、删除 | 2 |
| 路由级 `meta.permission` | `/ai-search*`、`/users`、`/roles`、`/login-logs`、`/operation-logs` 等 | 13 |

**重要说明**：前端门控只是体验层，**真正的安全边界始终是后端 `require_permission`**。§6 已确认业务写接口后端 100% 覆盖，前端门控为纵深防御的第二层。

---

## 八、测试结果

测试文件：`backend/tests/test_rbac_hardening.py`（307 行 → 546 行，新增 12 个用例）

执行命令（**仅隔离测试库，模块级护栏拦截生产库**）：

```bash
DATABASE_URL='postgresql+psycopg://opinion_user:opinion_pass@127.0.0.1:5432/opinion_test' \
DB_IDENTITY_CHECK=off \
./.venv/Scripts/python.exe -m pytest tests/test_rbac_hardening.py -v
```

**结果：`70 passed`（原 58 + 新增 12），0 失败，0 跳过。**

### 8.1 Phase 10｜全角色动态测试（角色不写死）

角色列表由 `_db_roles()` 在测试收集期**实时从 `roles` 表读取**（仅取 `is_enabled=true` 且非 admin），未来新增角色**自动纳入覆盖，无需改测试代码**。

| 用例 | 参数化 | 断言内容 | 结果 |
|---|---|---|---|
| `test_role_permissions_match_db` | analyst / viewer | `/api/auth/me` 返回权限集 **完全等于** 数据库 `role_permissions`；非超管不得含 `*` | ✅ PASSED ×2 |
| `test_role_no_privileged_admin_permissions` | analyst / viewer | 非超管角色不得持有 `users:write`/`users:activate`/`roles:write`/`roles:delete`/`permissions:write` —— **职责冲突守门** | ✅ PASSED ×2 |
| `test_propagation_rebuild_requires_events_write` | analyst / viewer | **SEC2-01 回归**：有 `events:write` → 非 403；无 → 403 `Permission denied` | ✅ PASSED ×2 |
| `test_propagation_rebuild_admin_not_forbidden` | — | 超管不被 RBAC 拦截（事件不存在返回 404） | ✅ PASSED |
| `test_role_cannot_touch_user_management` | analyst / viewer | 6 个管理接口（users/roles/operation-logs/login-logs 读写）全部 403 | ✅ PASSED ×2 |

### 8.2 Phase H｜权限变更审计验证

| 用例 | 场景 | 断言内容 | 结果 |
|---|---|---|---|
| `test_user_role_change_audited_with_before_after` | 管理员将用户 **viewer → analyst** | 日志 `resource_type=user`、`result=success`、操作人快照正确；`details.before.role=="viewer"`、`details.after.role=="analyst"`、`changed_fields` 含 `role`；**变更后重新登录 `/auth/me` 立即拥有 `ai:search`（权限实时生效）** | ✅ PASSED |
| `test_user_password_reset_not_logged_in_plaintext` | 管理员重置密码 | 日志原文**不含密码明文**；`password_changed==true`；`changes.password=="***"` | ✅ PASSED |
| `test_role_permission_change_audited_with_diff` | 临时角色权限 `[events:read]` → `[events:read, events:write]` | `before.permissions`/`after.permissions` 正确；`permissions_added==["events:write"]`、`permissions_removed==[]` | ✅ PASSED |

> 三个审计用例均在**隔离测试库**创建临时用户/角色并在 `finally` 中清理，不残留数据。

---

## 九、数据库权限健康检查（Phase 11，只读）

直连生产库 `opinion_db`，全部为 SELECT：

| 检查项 | 结果 | 判定 |
|---|---|---|
| `role_permissions` 悬挂 role_id（指向不存在角色） | 0 | ✅ |
| `user_roles` 悬挂 role_id | 0 | ✅ |
| `users.role` 指向不存在的角色名 | 0 | ✅ |
| 用户总数 / 超管数 | 3 / 1 | ✅ 存在唯一超管，`_superuser_count` 保护生效 |
| 权限目录总数 | 31 | ✅ |
| 授权记录总数 | 25 | ✅ |
| 孤儿权限（无任何角色持有） | 13 | ⚠️ SEC2-04，业务确认维持现状 |
| 停用角色 | 0 | ✅ |
| `user_operation_logs` 记录数 | 257 | ✅ 表活跃，含 `UPDATE`(41) / `ROLE_UPDATE`(14) / `ROLE_CREATE`(1) / `ROLE_DELETE`(1) / `CREATE`(9) / `DELETE`(1) / `ENABLE`(1) / `DISABLE`(1) |

**结论：数据库权限数据完整性零异常。** 唯一非致命项是 13 项孤儿权限（管理类权限未下放），业务方已确认维持现状。

复核脚本：`backend/_sec2_db_recheck.py`（只读，可随时重跑），输出 `backend/_sec2_db_recheck.json`。

---

## 十、部署与上线验证

| 步骤 | 命令 | 结果 |
|---|---|---|
| 前端构建 | `node --max-old-space-size=1400 node_modules/vite/bin/vite.js build`（cwd=frontend） | ✅ `built in 12.91s`，`Propagation`/`Opinions`/`OperationLogs` chunk 均重新生成 |
| 静态部署 | `backend/_d.py` | ✅ `Wrote 42 files`，`index.html exists: True` |
| 后端重启 | 锁定 LISTENING PID(29992) → 确认其父为 31888 → `taskkill /PID 31888 /T /F` → 单实例重启 | ✅ 进程树干净停止，端口释放后重新监听（新 PID 40988） |

**上线冒烟验证：**

| 探测 | 期望 | 实际 |
|---|---|---|
| `GET /health` | 200 | ✅ 200 |
| `GET /`（SPA） | 200 | ✅ 200 |
| `POST /api/propagation/rebuild/999999`（未鉴权） | 401 JSON `Not authenticated`（证明新路由已加载，未被 SPA catch-all 兜走） | ✅ `401 {"detail":"Not authenticated"}` |
| `GET /api/users`（未鉴权） | 401 | ✅ 401 |
| `GET /api/operation-logs`（未鉴权） | 401 | ✅ 401 |

生产服务已正常恢复，无停机遗留。

---

## 十一、遗留风险与后续建议

### 11.1 本轮明确不处理的 5 项（已获业务确认）

| 编号 | 等级 | 不处理原因 | 建议后续动作 |
|---|---|---|---|
| **SEC2-02** | MEDIUM | 需为约 26 个 GET 接口逐一加 `require_permission`，改动面大且可能影响现有前端调用，属**架构级决策** | 单独立项。建议分批推进：先补 `dashboard:read` / `opinions:read` / `events:read`，每批配套回归测试 |
| **SEC2-03** | MEDIUM | 任务书明令禁改 admin 超管逻辑；补齐 27 条授权需直写 `role_permissions`，属数据变更 | 单独立项。若未来要移除代码短路，**必须先补齐 admin 授权数据并验证，再关短路**，顺序不可颠倒 |
| **SEC2-04** | MEDIUM | 业务方确认**维持现状**，暂无下放管理职责的需求 | 待出现「非超管需管理用户」的真实诉求时，新建 `sysadmin` 角色并授予 13 项孤儿权限 |
| **SEC2-06** | LOW | 删除 `reports:write` 需同步清理 analyst 授权记录，属数据变更，风险 > 收益 | 建议在权限目录中标注「已废弃」，新代码不再引用 |
| **SEC2-08** | LOW | 6 项死权限属规划预留（`ai:manage`）与能力重叠（`collectors:*` / `keywords:delete` / `sources:write`） | 保留，避免破坏权限目录向前兼容 |

### 11.2 长期建议

1. **把权限断言纳入 CI**：`test_rbac_hardening.py` 已具备「角色从 DB 动态读取」能力，建议接入流水线，任何新增角色或改授权都会自动被 §8.1 的两条守门用例校验（权限集一致性 + 无管理类高危权限）。
2. **新增写接口的强制检查项**：建议在代码评审清单中加入一条——「新增 POST/PUT/PATCH/DELETE 路由必须挂 `require_permission` 或 `require_admin`」，并可用 `backend/_sec2_recheck.py` 一键复核（当前基线：业务写接口 100%）。
3. **审计日志保留策略**：`user_operation_logs` 已 257 条且新增了 before/after 快照，单条体积增大。建议规划归档策略（如按季度冷备），避免长期膨胀。
4. **前端门控风格统一**：本轮已把 `Opinions.vue` 从 `:disabled` 统一为 `v-if`。建议后续新页面一律使用 `v-if`，与 `Events.vue` / `Keywords.vue` / `Propagation.vue` 保持一致。

---

## 附：本阶段全部交付物

| 序号 | 文档 | 阶段 |
|---|---|---|
| 1 | `Phase_Security-2_A_RBAC资产盘点报告.md` | Phase A |
| 2 | `Phase_Security-2_B_角色权限风险分析报告.md` | Phase B |
| 3 | `Phase_Security-2_C_API权限覆盖报告.md` | Phase C |
| 4 | `Phase_Security-2_D_前端权限覆盖报告.md` | Phase D |
| 5 | `Phase_Security-2_E_权限链路一致性报告.md` | Phase E |
| 6 | `Phase_Security-2_F_覆盖率报告.md` | Phase F |
| 7 | `Phase_Security-2_G_操作审计完善.md` | Phase G |
| 8 | `Phase_Security-2_整改计划.md` | Phase 12 |
| 9 | **`Phase_Security-2_全角色RBAC安全审计与权限治理实施报告.md`**（本文档） | Phase 13 |

复核工具（只读，可重复执行）：`backend/_sec2_recheck.py`、`backend/_sec2_db_recheck.py`

---

**报告结束。**
