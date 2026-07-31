# Phase Security-2-B：角色权限风险分析报告

- 生成时间：2026-07-31
- 阶段属性：**只读审计**，未做任何修改
- 分析对象：`admin` / `analyst` / `viewer` 共 3 个角色

> 本报告由只读审计脚本自动生成，全过程未修改任何代码、数据库记录或权限数据。
> 数据来源：生产库 `opinion_db@127.0.0.1:5432`（仅 SELECT）+ FastAPI 路由内省 + 前端源码静态扫描。

---

## 一、风险判定口径

| 等级 | 判定标准 |
|---|---|
| **HIGH** | 存在可被实际利用的越权路径：低权角色可执行本不应执行的写/管理操作 |
| **MEDIUM** | 权限模型与实现不一致、防护仅在前端、或管理职责无法正确下放，存在演进风险 |
| **LOW** | 权限冗余、命名重复、UI 体验问题，无实际越权后果 |

> 任务书特别关注的「职责冲突（普通分析员持有用户/角色/权限/系统配置管理权）」经核查：
> `analyst` **未持有** `users:*` / `roles:*` / `permissions:read` / `audit_logs:read` 中任何一项 —— **无职责冲突**。

---

## 二、逐角色风险分析

### 2.1 角色 `admin`（1 人：admin）

| 维度 | 结论 | 等级 |
|---|---|---|
| 越权风险 | 设计上即为最高权限，`*` 覆盖全部 31 项。`is_superuser=true`，符合预期 | — |
| 权限冗余 | 数据库仅授权 4 项，与实际生效的 31 项严重不符 | **MEDIUM**(SEC2-03) |
| 职责冲突 | 超管集全部职责于一身，当前系统仅 3 用户，属可接受的小规模部署形态 | LOW |

**详述（SEC2-03）**：`role_permissions` 中 admin 仅持有 `ai:analyze`、`ai:manage`、`ai:search`、`reports:manage`。其“全能”完全依赖 `app/core/permissions.py` 中 `is_superuser or role=='admin'` → `["*"]` 的短路返回。

- **现状是安全的**（短路存在，admin 正常工作）；
- **风险在演进**：任何以数据为准重建权限、或收敛短路逻辑的改动，都会让 admin 立刻掉到 4 项权限；
- **次生问题**：角色管理页展示 admin 角色时，勾选状态只反映那 4 项，与真实能力不符，易误导管理员。

> 注：本阶段**不建议**修改超管短路逻辑（任务书明令禁止改动 admin 超管逻辑）。合规的处理方式是「补齐 admin 角色的数据授权，使数据与短路结果一致」或「在 UI 上明确标注 admin 为超管、权限不可编辑」。经核查 `Roles.vue` 已有 `!isAdminRole` 守卫（admin 角色权限不可编辑），UI 侧已部分缓解。

### 2.2 角色 `analyst`（1 人：测试）

**持有权限（16 项）**：`ai:analyze`、`ai:search`、`alerts:read`、`alerts:write`、`dashboard:read`、`events:read`、`events:write`、`keywords:read`、`keywords:write`、`opinions:read`、`opinions:write`、`propagation:read`、`reports:export`、`reports:read`、`reports:write`、`sources:read`

| 维度 | 结论 | 等级 |
|---|---|---|
| 越权风险 | 未持有任何用户/角色/权限/审计类权限；写权限限于业务域（事件、预警、关键词、舆情） | LOW |
| 越权风险（实际可利用） | 可调用 `POST /api/propagation/rebuild/{event_id}`（后端无权限校验） | **HIGH**(SEC2-01) |
| 权限冗余 | `reports:write` 与 `reports:export` 语义完全重复，且 `reports:write` 后端未引用 | LOW(SEC2-06) |
| 职责冲突 | **无**。未触及用户管理、角色管理、系统配置 | ✅ |

**权限合理性逐项复核**：

| 权限 | 是否合理 | 说明 |
|---|---|---|
| `events:read` / `events:write` | ✅ | 分析员核心职责：事件研判与处置 |
| `opinions:read` / `opinions:write` | ✅ | 舆情编辑（批量删除仍需 admin） |
| `alerts:read` / `alerts:write` | ✅ | 预警规则配置与处置 |
| `keywords:read` / `keywords:write` | ✅ | 监测词维护 |
| `ai:search` / `ai:analyze` | ✅ | AI 检索与研判 |
| `dashboard:read` / `propagation:read` | ✅ | 只读查看 |
| `reports:read` / `reports:export` | ✅ | 出报告 |
| `reports:write` | ⚠️ 冗余 | 与 `reports:export` 同义，后端未使用 |
| `sources:read` | ✅ | 只读查看数据源与采集情况，不含写 |

> `analyst` **未持有** `reports:manage`（模板管理）、`sources:write`、`collectors:*`、`opinions` 批量删除，职责边界划分清晰、符合最小权限原则。

### 2.3 角色 `viewer`（1 人：观察测试）

**持有权限（5 项）**：`alerts:read`、`dashboard:read`、`events:read`、`opinions:read`、`propagation:read`

| 维度 | 结论 | 等级 |
|---|---|---|
| 越权风险 | 名义上纯只读（5 项均为 `:read`） | — |
| 越权风险（实际可利用） | 持有 `propagation:read` → 可进入传播页 → 「构建传播链」按钮无门控 → 后端无校验，**可发起写操作** | **HIGH**(SEC2-01) |
| 越权风险（服务端读校验） | 所有 `:read` 后端未强制，viewer 绕过前端可读取 keywords / sources / collector status 等未授权数据 | **MEDIUM**(SEC2-02) |
| 权限冗余 | 无 | ✅ |
| 职责冲突 | 无 | ✅ |

**viewer 越权链路（SEC2-01 完整复现路径）**：

```
viewer 登录
  └─ 路由 /propagation  meta.permission = 'propagation:read'  → viewer 持有 → 放行
      └─ Propagation.vue L40 <el-button @click="handleRebuild">构建传播链</el-button>
          （无 v-if / 无 :disabled 门控）
          └─ POST /api/propagation/rebuild/{event_id}
              后端仅 Depends(get_current_user) → 通过
                  └─ 删除并重算 propagation_nodes ✔ 写操作成功
```

这是本次审计中**唯一确认可被实际利用的服务端越权点**。

---

## 三、跨角色横向对比

| 能力域 | admin | analyst | viewer | 判定 |
|---|---|---|---|---|
| 用户管理 | `*` | ✗ | ✗ | ✅ 无冲突 |
| 角色/权限管理 | `*` | ✗ | ✗ | ✅ 无冲突 |
| 审计日志 | `*` | ✗ | ✗ | ✅ 无冲突 |
| 数据源写入 / 采集触发 | `*` | ✗ | ✗ | ✅ 无冲突 |
| 事件 / 预警 / 关键词 写 | `*` | ✓ | ✗ | ✅ 合理 |
| 舆情批量删除 | `*` | ✗ | ✗ | ✅ 合理 |
| AI 检索 / 研判 | `*` | ✓ | ✗ | ✅ 合理 |
| **传播链重建（写）** | ✓ | ✓ | **✓（越权）** | ⛔ SEC2-01 |
| 只读数据（服务端强制） | — | — | — | ⚠️ SEC2-02 全域未强制 |

---

## 四、风险汇总

| 编号 | 风险等级 | 问题摘要 | 影响 |
|---|---|---|---|
| SEC2-01 | **HIGH** | 传播链重建接口缺少写权限校验 | viewer（只读观察员）可对生产事件传播图发起重算，造成数据抖动与计算资源占用；违反最小权限原则。… |
| SEC2-02 | **MEDIUM** | 所有 `:read` 类权限在服务端未强制，仅前端拦截 | 绕过前端直接调用 API 即可读取本不应可见的数据。当前 3 个角色读权限差异小，实际暴露面有限；但一旦新增“受限读”角色，模型即失效。… |
| SEC2-03 | **MEDIUM** | admin 角色的数据库授权残缺，实际权限依赖代码短路 | 模型与实现不一致。若未来收敛短路逻辑或以数据驱动方式重建权限，admin 将瞬间失去 27 项权限导致系统不可用；同时角色管理页对 admin 角色显示的权限集… |
| SEC2-04 | **MEDIUM** | 13 个权限为“孤儿权限”，未授予任何角色 | 除超管外无人可执行用户管理、角色管理、审计日志查看、采集管理、数据源写入等操作，职责无法下放；同时这些权限码在权限目录中可见，管理员可能误以为可分配生效。… |
| SEC2-06 | **LOW** | `reports:write` 与 `reports:export` 语义重复 | 权限目录冗余，授权界面易混淆；`reports:write` 属未被后端引用的死权限。… |

### 完整风险明细

#### SEC2-01｜HIGH｜传播链重建接口缺少写权限校验

- **描述**：`POST /api/propagation/rebuild/{event_id}` 仅 `Depends(get_current_user)`，无 `require_permission` / `require_admin`。该接口会删除并重算 `propagation_nodes` 数据，属重计算型写操作。任意已登录用户（含 viewer）均可调用。
- **证据**：app/api/propagation.py；API 内省 kind=login；前端 Propagation.vue L40 按钮无门控，而 /propagation 路由门槛仅 `propagation:read`（viewer 持有）。
- **影响**：viewer（只读观察员）可对生产事件传播图发起重算，造成数据抖动与计算资源占用；违反最小权限原则。
- **所属阶段**：C / D / E

#### SEC2-02｜MEDIUM｜所有 `:read` 类权限在服务端未强制，仅前端拦截

- **描述**：26 个 GET 路由（events / opinions / alerts / dashboard / propagation / collector status / sources 等）只要求登录态，服务端不校验对应的 `events:read` / `opinions:read` / `alerts:read` / `dashboard:read` / `propagation:read`。
- **证据**：API 内省：read 类路由中 kind=login 共 26 个；而前端 router meta.permission 已对这些页面设门槛。
- **影响**：绕过前端直接调用 API 即可读取本不应可见的数据。当前 3 个角色读权限差异小，实际暴露面有限；但一旦新增“受限读”角色，模型即失效。
- **所属阶段**：C / E

#### SEC2-03｜MEDIUM｜admin 角色的数据库授权残缺，实际权限依赖代码短路

- **描述**：`role_permissions` 中 admin 仅被授予 4 项（ai:analyze / ai:manage / ai:search / reports:manage）。admin 之所以“全能”，来自 `is_superuser or role=='admin'` → 返回 `["*"]` 的硬编码短路，而非数据授权。
- **证据**：DB: role_perms['admin'] 长度=4；app/core/permissions.py 超管短路逻辑。
- **影响**：模型与实现不一致。若未来收敛短路逻辑或以数据驱动方式重建权限，admin 将瞬间失去 27 项权限导致系统不可用；同时角色管理页对 admin 角色显示的权限集合与真实生效集合不符，易误导管理员。
- **所属阶段**：A / B / E

#### SEC2-04｜MEDIUM｜13 个权限为“孤儿权限”，未授予任何角色

- **描述**：audit_logs:read、collectors:read、collectors:write、keywords:delete、login_logs:read、permissions:read、roles:delete、roles:read、roles:write、sources:write、users:activate、users:read、users:write 共 13 项在 `role_permissions` 中无任何角色持有，仅超管短路可用。
- **证据**：DB health.orphan_permissions（13 项）。
- **影响**：除超管外无人可执行用户管理、角色管理、审计日志查看、采集管理、数据源写入等操作，职责无法下放；同时这些权限码在权限目录中可见，管理员可能误以为可分配生效。
- **所属阶段**：A / B / E / F

#### SEC2-05｜MEDIUM｜用户/角色变更审计仅记录变更后值，缺少变更前值

- **描述**：`update_user`（users.py L235）与 `update_role`（L410）的 `details` 均为 `{"changes": body.model_dump(exclude_unset=True)}`，即仅提交内容（after），未快照修改前的原值（before）。
- **证据**：app/api/users.py L235-238、L410-412。
- **影响**：不满足任务书 Phase G「修改前 / 修改后」要求。发生越权提权（如把 viewer 改成 admin）后，无法从日志还原原始角色，追责与回滚困难。
- **所属阶段**：G

#### SEC2-06｜LOW｜`reports:write` 与 `reports:export` 语义重复

- **描述**：两者 description 完全一致（均为“导出PDF报告”），analyst 同时持有两者；后端实际只使用 `reports:export`。
- **证据**：DB permissions id=24/27；API 内省中 reports 相关路由使用 reports:read / reports:export / reports:manage。
- **影响**：权限目录冗余，授权界面易混淆；`reports:write` 属未被后端引用的死权限。
- **所属阶段**：B / E

#### SEC2-07｜LOW｜批量删除舆情按钮仅 disabled、未隐藏

- **描述**：Opinions.vue L87 `:disabled="!canDelete"`，无权限用户仍可见“删除”按钮（灰态）。
- **证据**：frontend/src/views/Opinions.vue L87。
- **影响**：仅 UI 体验层问题。后端 `PATCH/DELETE /api/opinions/batch` 为 `require_admin`，无实际越权风险。
- **所属阶段**：D

#### SEC2-08｜LOW｜5 个权限码后端与前端均未引用（死权限）

- **描述**：`ai:manage`、`collectors:read`、`collectors:write`、`keywords:delete`、`sources:write` 在 `permissions` 表中存在，但后端无路由引用、前端无门控引用。其能力实际由 `require_admin`、`keywords:write`、`sources:read` 承担。
- **证据**：权限码集合与 API 内省引用集合、前端门控集合三者求差。
- **影响**：权限目录与实际能力不对应，属规划预留/历史残留，无安全风险，但影响可维护性与授权界面准确性（管理员勾选后不生效）。
- **所属阶段**：E / F

---

## 五、阶段结论

1. **无职责冲突**：`analyst` / `viewer` 均未持有用户、角色、权限、审计、系统配置类权限。
2. **1 项 HIGH**：SEC2-01 传播链重建接口缺少写权限校验，viewer 可实际越权。
3. **3 项 MEDIUM**：SEC2-02（读权限服务端未强制）、SEC2-03（admin 数据授权残缺）、SEC2-04（13 项孤儿权限）。
4. **3 项 LOW**：SEC2-06 / SEC2-07 / SEC2-08，均为冗余或 UI 体验问题。
5. 本阶段**未做任何修改**。
