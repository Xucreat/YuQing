# 下一阶段实施前检查

## 已实现能力

- JWT 登录、角色/权限目录、后端 `require_permission`、用户/角色/审计日志已存在。
- 管理员可通过 `/api/users/{user_id}/reset-password` 重置其他用户密码。
- 外网数据源增删改、启停、RSS 测试、采集运行记录、风险分析、事件候选/事件和独立外网告警 API 已存在。
- `ForeignWorkspace.vue` 已提供外网 Dashboard、文章、事件、告警、规则和手动采集入口。
- `CollectorRun` 已包含 batch、触发方式、抓取/新增/重复/失败和错误摘要字段；scheduler 已有 PostgreSQL advisory lock。

## 本阶段需要修改的文件

- `backend/app/schemas/user.py`、`backend/app/api/users.py`、`backend/app/core/security.py`（当前用户改密流程）。
- `backend/alembic/versions/foreign_source_5h_next_phase.py`（采集动作权限目录）。
- `backend/app/api/foreign.py`、`backend/app/services/foreign_collection_service.py`、`backend/app/core/task_manager.py`（采集权限、批准/启用源选择、并发和审计）。
- `backend/app/core/scheduler.py`、外网调度服务/API（仅启用且 schedule_enabled 的外网源和状态观测）。
- `frontend/src/components/AppLayout.vue`、`frontend/src/views/ForeignWorkspace.vue`、统一预警页面及 API 类型（密码入口、采集权限、外网预警 tab/入口）。
- 对应 `backend/tests/` 测试和 `NEXT_PHASE_DELIVERY_REPORT.md` / `audit-evidence/next-phase/` 证据。

## 可能影响的国内功能

- 用户认证 token 清理只影响改密后当前会话；管理员重置其他用户保持原接口不变。
- 外网采集必须继续使用 `scope='foreign'`、`is_foreign=true`，不得进入国内 collector 或国内表。
- 统一预警页面只能聚合展示外网 API，外网接口失败时国内预警 tab 必须独立可用。
- scheduler 过滤只添加外网分支，不改变现有国内 `DataSource` 选择和轮询行为。

## 新增测试

- 当前用户改密：成功、旧密码错误、过短、不一致、重复、未登录、审计不含密码、新密码重新登录。
- 采集权限与边界：指定/全量权限、停用/国内/重复/空源拒绝、403、任务失败恢复和重复点击保护。
- 批准源集合来自后端，不依赖前端硬编码；自动调度只选择 enabled + schedule_enabled 外网源。
- 统一预警页面：外网 API 失败不阻断国内 tab，外网规则/告警权限和筛选保持现有语义。
