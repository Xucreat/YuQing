# Phase Security-3-B RBAC权限语义收口实施报告

> 完成时间：2026-07-31 18:10 | 阶段：修复+测试+部署

---

## 1. 修改文件列表

### 前端（1 个文件）

| 文件 | 修改内容 |
|---|---|
| `frontend/src/views/Dashboard.vue` L62-66 | SEC3-05：导出按钮容器加 `v-if="can('reports:read') || can('reports:export')"`，无权限时隐藏整块 sit-action 区域 |

### 后端（2 个文件）

| 文件 | 修改内容 |
|---|---|
| `backend/alembic/versions/sec3b_perm_semantic.py` | 新增 Alembic 迁移（5 权限删除 + 3 description 修改 + 1 授权移除） |
| `backend/tests/test_rbac_hardening.py` | 新增 8 个 SEC3-B 测试用例（546→610 行） |

### 数据库（通过迁移，无手动修改）

| 操作 | 详情 |
|---|---|
| DELETE permissions | id=10(keywords:delete), 17(collectors:read), 18(collectors:write), 22(dashboard:read), 24(reports:write) |
| UPDATE permissions | id=12 description: "删除/编辑舆情"→"编辑舆情"; id=19: "查看数据源"→"查看数据源状态（管理操作仅管理员）"; id=20: "管理数据源"→"管理员管理数据源" |
| DELETE role_permissions | analyst(role_id=2)→sources:write(permission_id=20); analyst→dashboard:read(22); analyst→reports:write(24); viewer→dashboard:read(22) |

---

## 2. Alembic 迁移版本

| 字段 | 值 |
|---|---|
| revision | `sec3b_perm_semantic` |
| down_revision | `p31_rbac_ai_perms` |
| 升级 | ✅ 测试库 + 生产库均成功 |
| 回滚 | ✅ 测试库回滚验证：31 perms→26→31，27 grants→23→27 |

---

## 3. 权限变化前后对比表

### 权限码变更

| 权限码 | 前 description | 后 description | 前状态 | 后状态 |
|---|---|---|---|---|
| opinions:write | 删除/编辑舆情 | **编辑舆情** | 存在(id=12) | 存在(id=12) |
| sources:read | 查看数据源 | **查看数据源状态（管理操作仅管理员）** | 存在(id=19) | 存在(id=19) |
| sources:write | 管理数据源 | **管理员管理数据源** | 存在(id=20) | 存在(id=20) |
| keywords:delete | 删除关键词 | — | 存在(id=10) | **已删除** |
| reports:write | 导出PDF报告 | — | 存在(id=24) | **已删除** |
| collectors:read | 查看采集任务 | — | 存在(id=17) | **已删除** |
| collectors:write | 启停采集任务 | — | 存在(id=18) | **已删除** |
| dashboard:read | 查看数据总览 | — | 存在(id=22) | **已删除** |

### 角色授权变更

| 角色 | 移除的授权 | 保留的授权 |
|---|---|---|
| analyst | sources:write, dashboard:read, reports:write | 14 个有效授权（opinions:read/write, keywords:read/write, events:read/write, alerts:read/write, propagation:read, reports:read/export/manage, sources:read, ai:search/analyze） |
| viewer | dashboard:read | 5 个有效授权（opinions:read, events:read, alerts:read, propagation:read, reports:read） |

### 权限总数变化

| 指标 | 前 | 后 |
|---|---|---|
| permissions 总数 | 31 | **26** |
| role_permissions 总数 | 28 | **23** |
| analyst 有效授权 | 17 | **14** |
| viewer 有效授权 | 6 | **5** |

---

## 4. 测试结果

### 后端 RBAC 测试（78 passed，0 failed）

| 类别 | 数量 | 说明 |
|---|---|---|
| Phase RBAC-1/2 原有测试 | 70 | 全通过 |
| Phase SEC3-B 新增测试 | 8 | 全通过 |

SEC3-B 测试明细：

| 测试 | 结果 | 说明 |
|---|---|---|
| test_sec3b_orphan_perms_removed | ✅ | 5 个孤儿权限码已从 DB 删除 |
| test_sec3b_analyst_no_sources_write | ✅ | analyst 不再持有 sources:write |
| test_sec3b_analyst_no_dashboard_read | ✅ | dashboard:read 权限码已删除 |
| test_sec3b_analyst_can_edit_but_not_delete_opinions | ✅ | opinions:write → PATCH 200(404)/DELETE 403 |
| test_sec3b_analyst_can_delete_keywords_via_write | ✅ | keywords:write 涵盖 DELETE(404而非403) |
| test_sec3b_analyst_can_export_reports | ✅ | reports:export 可访问模板列表 |
| test_sec3b_analyst_cannot_manage_data_sources | ✅ | sources:read GET 通过/POST 403 |
| test_sec3b_permission_descriptions_correct | ✅ | 3 个 description 已修正 |

### 前端冒烟

| 检查 | 结果 |
|---|---|
| SPA 页面加载 | ✅ / → 200 |
| propagation rebuild 401 | ✅ 新路由已加载 |

---

## 5. 遗留问题

| 问题 | 等级 | 说明 |
|---|---|---|
| 28 个 GET 接口仍为 LOGIN_ONLY | MEDIUM | Phase Security-2 SEC2-02 已确认维持现状。读权限码仅前端路由守卫，后端不强制 |
| 角色 "111" 非系统角色+0 用户 | LOW | 仍存在（需人工清理） |
| ai:manage 预留权限 | LOW | 保留（无后端引用） |
| Reports 模板列表 GET 用 reports:export | LOW | SEC3-11：查看模板需导出权限（业务合理：模板在导出抽屉中选择） |
| Dashboard.vue 坐标区数据来自 /api/dashboard/*（LOGIN_ONLY） | INFO | 不受 reports:read 影响；reports:read 仅保护 /api/reports/overview 和 /api/reports/modules |

---

## 6. 各 SEC3 项修复确认

| 编号 | 修复方案 | 代码改 | DB改 | 测试 |
|---|---|---|---|---|
| SEC3-01 | opinions:write description → "编辑舆情"；删除按钮/后端保持 ADMIN 独占 | 无 | ✅ description | ✅ |
| SEC3-02 | analyst 移除 sources:write；sources:read/write description 修正；前端保持 isSuperuser | 无 | ✅ 移除+修改 | ✅ |
| SEC3-03 | 删除 keywords:delete 孤儿权限 | 无 | ✅ DELETE | ✅ |
| SEC3-04 | 删除 reports:write 孤儿权限 | 无 | ✅ DELETE | ✅ |
| SEC3-05 | Dashboard.vue sit-action 区加 `can('reports:read') || can('reports:export')` 门控 | ✅ | 无 | ✅（前端构建） |
| SEC3-06 | 删除 collectors:read/write 孤儿权限 | 无 | ✅ DELETE | ✅ |
| SEC3-07 | 删除 dashboard:read 孤儿权限 | 无 | ✅ DELETE | ✅ |

---

> 实施完毕。未修改采集逻辑、业务模型、JWT 结构、RBAC 架构。
