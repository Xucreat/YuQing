# Phase Security-2-A：全角色 RBAC 资产盘点报告

- 生成时间：2026-07-31
- 阶段属性：**只读审计（Read-Only）**，未做任何修改
- 数据来源：生产库 `opinion_db`（SELECT）

> 本报告由只读审计脚本自动生成，全过程未修改任何代码、数据库记录或权限数据。
> 数据来源：生产库 `opinion_db@127.0.0.1:5432`（仅 SELECT）+ FastAPI 路由内省 + 前端源码静态扫描。

---

## 一、总体资产概览

| 指标 | 数量 |
|---|---|
| 角色总数 | 3 |
| 权限总数 | 31 |
| 角色-权限授权记录 | 25 |
| 用户总数 | 3 |
| 具备主角色的用户 | 3 |
| `is_superuser=true` 的用户 | 1 |

> 角色列表为**动态读取**自 `roles` 表，非硬编码。任务书示例中提到的 `observer` 角色在生产库中**不存在**，系统实际仅有 `admin` / `analyst` / `viewer` 三个角色。

---

## 二、角色清单与用户归属

| 角色 ID | 角色名 | 描述 | 用户数 | 用户列表 | 直接授权权限数 |
|---|---|---|---|---|---|
| 1 | `admin` | （空） | 1 | admin | 4 |
| 2 | `analyst` | （空） | 1 | 测试 | 16 |
| 3 | `viewer` | （空） | 1 | 观察测试 | 5 |

> ⚠️ **重点**：`admin` 角色在 `role_permissions` 中仅有 4 条直接授权，其“全能”能力来自代码层`is_superuser or role=='admin' → ["*"]` 的短路判断（详见风险 SEC2-03）。

---

## 三、权限目录（按分组）

### AI能力（3 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `ai:analyze` | AI研判 | 对单条舆情触发 AI 研判分析 |
| `ai:manage` | AI配置管理 | 管理 AI 服务配置（预留） |
| `ai:search` | AI检索 | 使用 AI 检索（Web/AI/Anspire）并保存线索 |

### 事件管理（2 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `events:read` | 查看事件 | 查看事件中心 |
| `events:write` | 管理事件 | 聚合/编辑事件 |

### 传播溯源（1 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `propagation:read` | 查看传播 | 查看传播路径 |

### 关键词管理（3 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `keywords:delete` | 删除关键词 | 删除关键词 |
| `keywords:read` | 查看关键词 | 查看监测/敏感词 |
| `keywords:write` | 管理关键词 | 增删改关键词 |

### 审计（2 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `audit_logs:read` | 查看操作日志 | 查看操作审计日志 |
| `login_logs:read` | 查看登录日志 | 查看登录日志 |

### 报告（4 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `reports:export` | 导出报告 | 导出PDF报告 |
| `reports:manage` | 管理报告模板 | 管理报告模板（保存/编辑/删除） |
| `reports:read` | 查看报告 | 查看分析报告 |
| `reports:write` | 导出报告 | 导出PDF报告 |

### 数据源（2 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `sources:read` | 查看数据源 | 查看数据源 |
| `sources:write` | 管理数据源 | 管理数据源 |

### 权限管理（1 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `permissions:read` | 查看权限 | 查看权限目录 |

### 用户管理（3 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `users:activate` | 启用/停用用户 | 启用或停用用户 |
| `users:read` | 查看用户 | 查看用户列表与详情 |
| `users:write` | 管理用户 | 创建/编辑用户 |

### 舆情管理（2 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `opinions:read` | 查看舆情 | 查看舆情列表/详情 |
| `opinions:write` | 管理舆情 | 删除/编辑舆情 |

### 角色管理（3 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `roles:delete` | 删除角色 | 删除非系统角色 |
| `roles:read` | 查看角色 | 查看角色列表 |
| `roles:write` | 管理角色 | 创建/编辑/分配权限 |

### 采集管理（2 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `collectors:read` | 查看采集 | 查看采集任务 |
| `collectors:write` | 管理采集 | 启停采集任务 |

### 预警管理（2 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `alerts:read` | 查看预警 | 查看预警规则与记录 |
| `alerts:write` | 管理预警 | 配置/评估预警 |

### 驾驶舱（1 项）

| 权限码 | 名称 | 说明 |
|---|---|---|
| `dashboard:read` | 查看驾驶舱 | 查看数据总览 |

---

## 四、各角色权限明细

### 角色 `admin`（用户 1 人：admin）

**数据库直接授权（4 项）**：`ai:analyze`、`ai:manage`、`ai:search`、`reports:manage`

**实际生效权限**：`*`（全部 31 项）—— 由超管短路提供，非数据授权。

### 角色 `analyst`（用户 1 人：测试）

**直接授权（16 项）**：`ai:analyze`、`ai:search`、`alerts:read`、`alerts:write`、`dashboard:read`、`events:read`、`events:write`、`keywords:read`、`keywords:write`、`opinions:read`、`opinions:write`、`propagation:read`、`reports:export`、`reports:read`、`reports:write`、`sources:read`

**未持有（15 项）**：`ai:manage`、`audit_logs:read`、`collectors:read`、`collectors:write`、`keywords:delete`、`login_logs:read`、`permissions:read`、`reports:manage`、`roles:delete`、`roles:read`、`roles:write`、`sources:write`、`users:activate`、`users:read`、`users:write`

### 角色 `viewer`（用户 1 人：观察测试）

**直接授权（5 项）**：`alerts:read`、`dashboard:read`、`events:read`、`opinions:read`、`propagation:read`

**未持有（26 项）**：`ai:analyze`、`ai:manage`、`ai:search`、`alerts:write`、`audit_logs:read`、`collectors:read`、`collectors:write`、`events:write`、`keywords:delete`、`keywords:read`、`keywords:write`、`login_logs:read`、`opinions:write`、`permissions:read`、`reports:export`、`reports:manage`、`reports:read`、`reports:write`、`roles:delete`、`roles:read`、`roles:write`、`sources:read`、`sources:write`、`users:activate`、`users:read`、`users:write`

---

## 五、角色-权限矩阵（自动生成）

图例：`●` = 已授权 ｜ `○` = 未授权 ｜ `*` = 超管短路生效（非数据授权）

| 权限码 | 分组 | `admin` | `analyst` | `viewer` |
|---|---|---|---|---|
| `ai:analyze` | AI能力 | ● | ● | ○ |
| `ai:manage` | AI能力 | ● | ○ | ○ |
| `ai:search` | AI能力 | ● | ● | ○ |
| `alerts:read` | 预警管理 | `*` | ● | ● |
| `alerts:write` | 预警管理 | `*` | ● | ○ |
| `audit_logs:read` | 审计 | `*` | ○ | ○ |
| `collectors:read` | 采集管理 | `*` | ○ | ○ |
| `collectors:write` | 采集管理 | `*` | ○ | ○ |
| `dashboard:read` | 驾驶舱 | `*` | ● | ● |
| `events:read` | 事件管理 | `*` | ● | ● |
| `events:write` | 事件管理 | `*` | ● | ○ |
| `keywords:delete` | 关键词管理 | `*` | ○ | ○ |
| `keywords:read` | 关键词管理 | `*` | ● | ○ |
| `keywords:write` | 关键词管理 | `*` | ● | ○ |
| `login_logs:read` | 审计 | `*` | ○ | ○ |
| `opinions:read` | 舆情管理 | `*` | ● | ● |
| `opinions:write` | 舆情管理 | `*` | ● | ○ |
| `permissions:read` | 权限管理 | `*` | ○ | ○ |
| `propagation:read` | 传播溯源 | `*` | ● | ● |
| `reports:export` | 报告 | `*` | ● | ○ |
| `reports:manage` | 报告 | ● | ○ | ○ |
| `reports:read` | 报告 | `*` | ● | ○ |
| `reports:write` | 报告 | `*` | ● | ○ |
| `roles:delete` | 角色管理 | `*` | ○ | ○ |
| `roles:read` | 角色管理 | `*` | ○ | ○ |
| `roles:write` | 角色管理 | `*` | ○ | ○ |
| `sources:read` | 数据源 | `*` | ● | ○ |
| `sources:write` | 数据源 | `*` | ○ | ○ |
| `users:activate` | 用户管理 | `*` | ○ | ○ |
| `users:read` | 用户管理 | `*` | ○ | ○ |
| `users:write` | 用户管理 | `*` | ○ | ○ |

**列小计（数据库直接授权数）**：`admin` = 4 ｜ `analyst` = 16 ｜ `viewer` = 5

---

## 六、数据库权限健康检查（Phase 11）

| 检查项 | 结果 | 判定 |
|---|---|---|
| 孤儿权限（未授予任何角色） | 13 项 | ⚠️ 见下方清单 |
| 孤儿授权（指向不存在的角色/权限） | 0 条 | ✅ 通过 |
| 无角色用户 | 0 人 | ✅ 通过 |
| 重复权限码 | 0 组 | ✅ 通过 |

### 孤儿权限清单（13 项）

| 权限码 | 名称 | 分组 | 说明 |
|---|---|---|---|
| `audit_logs:read` | 查看操作日志 | 审计 | 仅超管短路可用，无角色持有 |
| `collectors:read` | 查看采集 | 采集管理 | 仅超管短路可用，无角色持有 |
| `collectors:write` | 管理采集 | 采集管理 | 仅超管短路可用，无角色持有 |
| `keywords:delete` | 删除关键词 | 关键词管理 | 仅超管短路可用，无角色持有 |
| `login_logs:read` | 查看登录日志 | 审计 | 仅超管短路可用，无角色持有 |
| `permissions:read` | 查看权限 | 权限管理 | 仅超管短路可用，无角色持有 |
| `roles:delete` | 删除角色 | 角色管理 | 仅超管短路可用，无角色持有 |
| `roles:read` | 查看角色 | 角色管理 | 仅超管短路可用，无角色持有 |
| `roles:write` | 管理角色 | 角色管理 | 仅超管短路可用，无角色持有 |
| `sources:write` | 管理数据源 | 数据源 | 仅超管短路可用，无角色持有 |
| `users:activate` | 启用/停用用户 | 用户管理 | 仅超管短路可用，无角色持有 |
| `users:read` | 查看用户 | 用户管理 | 仅超管短路可用，无角色持有 |
| `users:write` | 管理用户 | 用户管理 | 仅超管短路可用，无角色持有 |

> 这 13 项集中在 **用户管理 / 角色管理 / 权限管理 / 审计 / 采集管理 / 数据源写入**，说明系统管理类职责目前**完全无法下放**给非超管角色（风险 SEC2-04）。

---

## 七、阶段结论

1. 角色资产已全量盘点，共 **3 个角色 / 31 项权限 / 25 条授权 / 3 个用户**，矩阵已自动生成。
2. 未发现孤儿授权、无角色用户、重复权限码 —— 数据完整性良好。
3. 两项结构性问题需在 Phase B 深入分析：**admin 授权残缺依赖代码短路（SEC2-03）** 与 **13 项孤儿权限（SEC2-04）**。
4. 本阶段**未做任何修改**。
