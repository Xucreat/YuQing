# Phase Security-3-B 实施前只读确认

> 生成时间：2026-07-31 17:56 | 仅只读确认，未做任何修改

---

## 1. permissions 表当前数据（31 条）

| id | code | name | description | group |
|---|---|---|---|---|
| 1 | users:read | 查看用户 | 查看用户列表与详情 | 用户管理 |
| 2 | users:write | 管理用户 | 创建/编辑用户 | 用户管理 |
| 3 | users:activate | 启用/停用用户 | 启用或停用用户 | 用户管理 |
| 4 | roles:read | 查看角色 | 查看角色列表 | 角色管理 |
| 5 | roles:write | 管理角色 | 创建/编辑/分配权限 | 角色管理 |
| 6 | roles:delete | 删除角色 | 删除非系统角色 | 角色管理 |
| 7 | permissions:read | 查看权限 | 查看权限目录 | 权限管理 |
| 8 | keywords:read | 查看关键词 | 查看监测/敏感词 | 关键词管理 |
| 9 | keywords:write | 管理关键词 | 增删改关键词 | 关键词管理 |
| 10 | keywords:delete | 删除关键词 | 删除关键词 | 关键词管理 |
| 11 | opinions:read | 查看舆情 | 查看舆情列表/详情 | 舆情管理 |
| 12 | opinions:write | 管理舆情 | **删除/编辑舆情** | 舆情管理 |
| 13 | events:read | 查看事件 | 查看事件中心 | 事件管理 |
| 14 | events:write | 管理事件 | 聚合/编辑事件 | 事件管理 |
| 15 | alerts:read | 查看预警 | 查看预警规则与记录 | 预警管理 |
| 16 | alerts:write | 管理预警 | 配置/评估预警 | 预警管理 |
| 17 | collectors:read | 查看采集 | 查看采集任务 | 采集管理 |
| 18 | collectors:write | 管理采集 | 启停采集任务 | 采集管理 |
| 19 | sources:read | 查看数据源 | **查看数据源** | 数据源 |
| 20 | sources:write | 管理数据源 | **管理数据源** | 数据源 |
| 21 | propagation:read | 查看传播 | 查看传播路径 | 传播溯源 |
| 22 | dashboard:read | 查看驾驶舱 | 查看数据总览 | 驾驶舱 |
| 23 | reports:read | 查看报告 | 查看分析报告 | 报告 |
| 24 | reports:write | 导出报告 | **导出PDF报告** | 报告 |
| 25 | audit_logs:read | 查看操作日志 | 查看操作审计日志 | 审计 |
| 26 | login_logs:read | 查看登录日志 | 查看登录日志 | 审计 |
| 27 | reports:export | 导出报告 | **导出PDF报告** | 报告 |
| 28 | reports:manage | 管理报告模板 | 管理报告模板（保存/编辑/删除） | 报告 |
| 29 | ai:search | AI检索 | 使用 AI 检索（Web/AI/Anspire）并保存线索 | AI能力 |
| 30 | ai:analyze | AI研判 | 对单条舆情触发 AI 研判分析 | AI能力 |
| 31 | ai:manage | AI配置管理 | 管理 AI 服务配置（预留） | AI能力 |

> **加粗项**为本次需修改的 description 或需禁用的权限码。

---

## 2. role_permissions 当前关系（28 条）

| role | perm_code |
|---|---|
| 111 | opinions:read |
| admin | ai:analyze |
| admin | ai:manage |
| admin | ai:search |
| admin | reports:manage |
| analyst | ai:analyze |
| analyst | ai:search |
| analyst | alerts:read |
| analyst | alerts:write |
| analyst | **dashboard:read** |
| analyst | events:read |
| analyst | events:write |
| analyst | keywords:read |
| analyst | keywords:write |
| analyst | opinions:read |
| analyst | opinions:write |
| analyst | propagation:read |
| analyst | reports:export |
| analyst | reports:manage |
| analyst | reports:read |
| analyst | **reports:write** |
| analyst | sources:read |
| analyst | **sources:write** |
| viewer | alerts:read |
| viewer | **dashboard:read** |
| viewer | events:read |
| viewer | opinions:read |
| viewer | propagation:read |

> **加粗项**为本次需删除的授权关系。

---

## 3. 关键前端文件权限控制现状

### Opinions.vue（L291）
```
const canDelete = computed(() => isSuperuser.value)  // 删除按钮仅超管可见
const canEditOpinion = computed(() => hasPermission('opinions:write'))  // 编辑按钮
```

### DataManage.vue（L16/26/36/50-52）
```
数据源/日志/博察 tab: v-if="isSuperuser"  // 前端锁死超管
注释："后端实际使用 require_admin，与 sources:read/write 种子权限不一致"
```

### Keywords.vue（L156）
```
const canWriteKeyword = computed(() => hasPermission("keywords:write"))  // 新增/编辑/删除统一走此码
```

### Dashboard.vue（L63/163/169）
```
导出按钮: v-if="can('reports:export')"  // reports:export 门控
import { usePermission } from "@/composables/usePermission"
const { can } = usePermission()
```

### ReportExportDrawer.vue（L204-207）
```
canManageTemplate = computed(() => hasPermission('reports:manage'))  // 模板管理门控
```

---

## 4. 关键后端文件权限现状

### opinions.py
- DELETE `/api/opinions/{id}` → `require_admin`
- DELETE `/api/opinions/batch` → `require_admin`
- PATCH → `require_permission("opinions:write")`

### admin_data_sources.py
- GET 列表 → `require_permission("sources:read")`
- POST/PATCH 写 → `require_admin`

### keywords.py
- DELETE `/api/keywords/{id}` → `require_permission("keywords:write")`（非 keywords:delete）

### reports.py
- overview/modules → `require_permission("reports:read")`
- export/generate/templates GET → `require_permission("reports:export")`
- templates CRUD → `require_permission("reports:manage")`

---

## 确认完毕。等待实施指令。
