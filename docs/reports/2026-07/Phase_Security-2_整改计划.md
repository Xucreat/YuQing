# Phase Security-2：整改计划

- 生成时间：2026-07-31
- 前置依据：Phase A / B / C / D / E / F / G 七份只读审计报告
- **当前状态：计划稿，尚未实施任何修改。等待确认后方可进入整改阶段。**

> 本计划严格遵守任务书三条最高原则：
> 1. **先审计后修改** —— 审计已完成，本文件为整改设计，实施前需确认；
> 2. **禁止破坏现有 RBAC 模型** —— 不删表、不改 User→Role→Permission 关系、不引入新框架/Redis、不改 JWT、不改 admin 超管逻辑；
> 3. **不影响业务逻辑** —— 不触碰采集、风险评分、事件聚合、预警计算、AI 业务逻辑。

---

## 一、问题总表

| 编号 | 等级 | 问题 | 建议立即修复 |
|---|---|---|---|
| SEC2-01 | **HIGH** | 传播链重建接口无写权限校验，viewer 可越权 | ✅ **是** |
| SEC2-05 | MEDIUM | 用户/角色变更审计缺少「修改前」值 | ✅ **是**（任务书 Phase G 硬性要求） |
| SEC2-04 | MEDIUM | 13 项孤儿权限，管理职责无法下放 | ⚠️ 视需求决定（见 §4） |
| SEC2-03 | MEDIUM | admin 数据授权残缺，依赖代码短路 | ⛔ 否（改动面大，建议单独立项） |
| SEC2-02 | MEDIUM | 26 个 GET 未强制 `:read` 权限 | ⛔ 否（架构级决策，建议单独立项） |
| SEC2-06 | LOW | `reports:write` 与 `reports:export` 语义重复 | ⛔ 否（涉及数据清理，风险>收益） |
| SEC2-07 | LOW | 舆情批量删除按钮 `disabled` 而非隐藏 | ✅ 是（一行改动，零风险） |
| SEC2-08 | LOW | 5 项权限码前后端均未引用 | ⛔ 否（保留为规划预留） |

**建议本轮实施：SEC2-01、SEC2-05、SEC2-07（共 3 项）。**
其余 5 项记录在案，不在本轮变更范围内。

---

## 二、SEC2-01｜HIGH｜传播链重建接口缺少写权限校验

### 2.1 问题描述
`POST /api/propagation/rebuild/{event_id}` 仅有 `Depends(get_current_user)`，无任何细粒度权限校验。
该接口会删除并重算 `propagation_nodes`，属明确的写操作。

前端 `Propagation.vue` L40「构建传播链」按钮同样无门控，而 `/propagation` 路由门槛为 `propagation:read`（viewer 持有）。
→ **viewer 可完整走通越权链路。**

### 2.2 影响范围
| 项 | 说明 |
|---|---|
| 受影响角色 | `viewer`（不应有任何写能力）、`analyst`（本就可写事件，影响较小） |
| 数据影响 | `propagation_nodes` 表被删除重建；不影响 `opinions` / `events` / 风险评分 |
| 业务影响 | 无（传播图重算是幂等的派生计算） |

### 2.3 修改方案

**后端** —— `backend/app/api/propagation.py`

```python
# 现状
@router.post("/rebuild/{event_id}")
def rebuild_propagation(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

# 整改后（新增一行依赖，其余不动）
from app.core.permissions import require_permission

@router.post("/rebuild/{event_id}")
def rebuild_propagation(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_permission("events:write")),
):
```

**权限码选型说明**：传播链依附于事件，重算属事件级写操作，复用既有 `events:write` 最贴切，
且 `analyst` 已持有该权限 —— **不新增权限码、不改动任何角色授权数据**，仅收紧 `viewer`。

**前端** —— `frontend/src/views/Propagation.vue`

```vue
<!-- 现状 L40 -->
<el-button type="warning" size="small" :loading="rebuilding" @click="handleRebuild">构建传播链</el-button>

<!-- 整改后 -->
<el-button v-if="canRebuild" type="warning" size="small" :loading="rebuilding" @click="handleRebuild">构建传播链</el-button>
```

```ts
// script setup 中新增
import { usePermission } from '@/composables/usePermission'
const { hasPermission } = usePermission()
const canRebuild = computed(() => hasPermission('events:write'))
```

### 2.4 涉及文件
| 文件 | 改动 |
|---|---|
| `backend/app/api/propagation.py` | +2 行（import + 依赖参数） |
| `frontend/src/views/Propagation.vue` | +3 行（composable + computed + v-if） |

### 2.5 数据影响
**无。** 不涉及任何数据库写入、迁移或权限数据变更。

### 2.6 验证方式
- `viewer` 调用 `POST /api/propagation/rebuild/1` → 期望 **403**；
- `analyst` / `admin` 调用 → 期望 **200**；
- `viewer` 登录前端 `/propagation` → 期望看不到「构建传播链」按钮；
- 前端需重新构建并部署（`vite build` → `backend/_d.py`）。

### 2.7 建议
✅ **立即修复。** 这是本次审计唯一确认可被实际利用的越权点，改动面 5 行，零业务影响。

---

## 三、SEC2-05｜MEDIUM｜审计日志缺少「修改前」值

### 3.1 问题描述
任务书 Phase G 明确要求操作日志记录「修改前 / 修改后内容」。
现状 `update_user`（users.py L235）与 `update_role`（L410）的 `details` 仅为
`{"changes": body.model_dump(exclude_unset=True)}`，即只有修改后的提交体。

**后果**：若发生越权提权（如把 viewer 改为 admin），日志中只能看到「改成了 admin」，
**无法还原原始角色**，追责与回滚均受阻。

### 3.2 影响范围
| 项 | 说明 |
|---|---|
| 受影响接口 | `PUT /api/users/{user_id}`、`PUT /api/roles/{role_id}` |
| 数据影响 | 仅 `user_operation_logs.details_json` 的内容结构变化，**不改表结构** |
| 历史数据 | 不受影响（旧记录保持 `changes` 键） |

### 3.3 修改方案

**`backend/app/api/users.py` —— `update_user`（约 L235）**

```python
# 在应用变更「之前」抓取快照
before = {
    "username": user.username,
    "display_name": user.display_name,
    "email": user.email,
    "role": user.role,
    "is_active": user.is_active,
    "is_superuser": user.is_superuser,
}

# ... 原有变更应用逻辑保持不变 ...

changes = body.model_dump(exclude_unset=True, mode="json")
log_operation(
    db, action="UPDATE", operator=current_user, request=request,
    resource_type="user", resource_id=str(user.id), target_user_id=user.id,
    details={
        "before": {k: before[k] for k in changes if k in before},
        "after": changes,
    },
)
```

**`backend/app/api/users.py` —— `update_role`（约 L410）**

```python
before = {
    "name": role.name,
    "display_name": role.display_name,
    "description": role.description,
    "permission_codes": sorted(p.code for p in role.permissions),
}

# ... 原有变更应用逻辑保持不变 ...

changes = body.model_dump(exclude_unset=True, mode="json")
log_operation(
    db, action="ROLE_UPDATE", operator=current_user, request=request,
    resource_type="role", resource_id=str(role.id),
    details={"before": before, "after": changes},
)
```

**前端兼容** —— `frontend/src/views/OperationLogs.vue`
详情展示需同时兼容两种结构：旧记录 `details.changes`，新记录 `details.before` / `details.after`。

### 3.4 涉及文件
| 文件 | 改动 |
|---|---|
| `backend/app/api/users.py` | 2 处函数各 +8～10 行 |
| `frontend/src/views/OperationLogs.vue` | 详情渲染兼容分支（约 +10 行） |

### 3.5 数据影响
| 项 | 影响 |
|---|---|
| 数据库表结构 | ❌ 不变（`details_json` 为 JSON 字段） |
| Alembic 迁移 | ❌ 不需要 |
| RBAC 模型 | ❌ 不变 |
| 业务逻辑 | ❌ 不变 |
| 历史日志 | ❌ 不受影响 |

### 3.6 验证方式
- admin 将用户 A 从 `viewer` 改为 `analyst`；
- 查询 `user_operation_logs` 最新记录，`details_json` 应含
  `{"before": {"role": "viewer"}, "after": {"role": "analyst"}}`；
- 用户 A 重新登录后 `/auth/me` 返回的 `permissions` 应变为 analyst 权限集。
（此即任务书 Phase H 的验证内容。）

### 3.7 建议
✅ **立即修复。** 任务书 Phase G 硬性要求，且不改表结构、不影响业务。

---

## 四、SEC2-04｜MEDIUM｜13 项孤儿权限（需业务确认）

### 4.1 问题描述
以下 13 项权限未授予任何角色，仅超管短路可用：

`audit_logs:read`、`collectors:read`、`collectors:write`、`keywords:delete`、`login_logs:read`、
`permissions:read`、`roles:delete`、`roles:read`、`roles:write`、`sources:write`、
`users:activate`、`users:read`、`users:write`

### 4.2 两种处置路径

| 方案 | 动作 | 适用前提 | 风险 |
|---|---|---|---|
| **A. 维持现状** | 不做任何改动，仅在文档中说明「管理职责集中于超管」 | 当前 3 用户小规模部署，无下放需求 | 无 |
| **B. 新增管理员角色** | 新建 `sysadmin` 角色并授予用户/角色/审计类权限 | 确有职责分离需求 | 需通过角色管理 UI 操作，**不应由脚本直接写库** |

### 4.3 建议
⚠️ **不在本轮自动修复。** 这属于「业务授权策略」而非「安全漏洞」——
当前无任何角色需要这些权限，强行授予反而扩大攻击面。
若确需下放，应由管理员通过 `角色管理` 界面创建角色并勾选权限（该路径已具备完整审计日志）。

**请确认：是否需要新增管理类角色？** 若需要，请指明角色名与应含权限。

---

## 五、SEC2-07｜LOW｜舆情批量删除按钮未隐藏

### 5.1 修改方案
`frontend/src/views/Opinions.vue` L87：

```vue
<!-- 现状 -->
<button class="btn btn-danger" :disabled="!canDelete" @click="batchDelete">删除</button>

<!-- 整改后（与其它页面风格统一） -->
<button v-if="canDelete" class="btn btn-danger" @click="batchDelete">删除</button>
```

### 5.2 涉及文件 / 数据影响
| 文件 | 改动 | 数据影响 |
|---|---|---|
| `frontend/src/views/Opinions.vue` | 1 行 | 无 |

### 5.3 建议
✅ **可一并修复。** 一行改动，零风险，仅统一 UI 行为。
（注：后端 `require_admin` 已保证无越权，此项纯属体验一致性。）

---

## 六、暂不修复项及理由

| 编号 | 理由 |
|---|---|
| **SEC2-02**（26 个 GET 未强制 `:read`） | 需为约 26 个接口逐一添加 `require_permission`，改动面大且可能影响现有前端调用。属**架构级决策**，建议单独立项评估，本轮不动。 |
| **SEC2-03**（admin 数据授权残缺） | 任务书明令「禁止改动 admin 超管逻辑」。补齐 admin 的 27 条授权需直接写 `role_permissions` 表，属数据变更。当前短路机制工作正常，且 `Roles.vue` 已有 `!isAdminRole` 守卫防止误编辑。建议单独立项。 |
| **SEC2-06**（`reports:write` 冗余） | 删除权限码需同时清理 `role_permissions` 中 analyst 的授权记录，属数据变更，风险大于收益。建议保留并在权限目录中标注「已废弃」。 |
| **SEC2-08**（5 项死权限） | 属规划预留（`ai:manage`）与能力重叠（`collectors:*`、`keywords:delete`、`sources:write`）。删除会破坏权限目录的向前兼容，建议保留。 |

---

## 七、整改实施顺序（待确认后执行）

1. **后端改动**
   - `app/api/propagation.py` 增加 `require_permission("events:write")`（SEC2-01）
   - `app/api/users.py` 的 `update_user` / `update_role` 补 before 快照（SEC2-05）
2. **重启 uvicorn** 并以「受保护新路由返回 401 `Not authenticated`」方式验证新代码已加载
3. **前端改动**
   - `Propagation.vue` 增加 `v-if="canRebuild"`（SEC2-01）
   - `Opinions.vue` 改 `disabled` → `v-if`（SEC2-07）
   - `OperationLogs.vue` 兼容 before/after 结构（SEC2-05）
4. **前端构建并部署**（`vite build` → `backend/_d.py`）
5. **测试扩展（Phase 10）**：`tests/test_rbac_hardening.py` 改为从数据库动态读取角色，
   新增 propagation rebuild 的三角色断言
6. **Phase H 验证**：模拟 admin 将用户 A 由 viewer 改为 analyst，核验日志 before/after 与 `/auth/me` 刷新
7. **产出 Phase 13 最终实施报告**

---

## 八、确认清单（请逐项确认后我再动手）

| # | 事项 | 待确认 |
|---|---|---|
| 1 | 修复 SEC2-01：`propagation.py` + `Propagation.vue` 加 `events:write` 门控 | ☐ 同意 / ☐ 改用其它权限码 / ☐ 暂缓 |
| 2 | 修复 SEC2-05：`users.py` 两处补 before 快照 + `OperationLogs.vue` 兼容 | ☐ 同意 / ☐ 暂缓 |
| 3 | 修复 SEC2-07：`Opinions.vue` 删除按钮改 `v-if` | ☐ 同意 / ☐ 暂缓 |
| 4 | SEC2-04：是否新增管理类角色（如 `sysadmin`）？ | ☐ 不需要 / ☐ 需要（请指定角色名与权限） |
| 5 | SEC2-02 / SEC2-03 / SEC2-06 / SEC2-08 本轮不处理 | ☐ 认可 / ☐ 需纳入本轮 |
| 6 | Phase 10 测试改造：`test_rbac_hardening.py` 改为动态读取角色 | ☐ 同意 / ☐ 暂缓 |
| 7 | 前端需重新构建部署（会短暂替换 `backend/app/static`） | ☐ 同意 / ☐ 仅改后端 |

---

**在收到确认前，本项目不会有任何代码、数据库或权限数据的改动。**
