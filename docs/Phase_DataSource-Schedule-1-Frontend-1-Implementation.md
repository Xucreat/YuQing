# Phase DataSource-Schedule-1-Frontend-1 实施报告

> 数据源调度配置前端改造 —— 实施前只读审计（Phase Frontend-0）已通过，本阶段按「检查 → 最小修改 → 验证 → 报告」执行。
> 严格遵守：不改后端、不改数据库、不新增权限体系、不改变现有数据源管理逻辑、不引入新依赖、不改 Collector/Scheduler/API 契约。

## 1. 修改文件清单

| 文件 | 修改方式 | 安全约束 | 说明 |
| --- | --- | --- | --- |
| `frontend/src/views/Sources.vue` | **node 脚本读取 + 字符串替换 + writeFileSync 写回** | ⚠️ 禁止普通 Read/Write 工具（node 虚拟化写入态） | 表格 4 列 + 单源调度弹窗 + 批量调度弹窗 + 对应 script 逻辑（9 处精确替换，全部命中 1 次） |
| `frontend/src/types/index.ts` | Edit 工具（普通，文件为明文非虚拟态） | 保持 ASCII 结构，未处理中文乱码注释 | 扩展 `DataSourceItem` + 新增 3 个调度类型 |

**未触碰**：`router/`、`DataManage.vue`、`api` 后端文件、`permission` 文件、`nginx`、build 配置、`Collector`/`Scheduler`/`API 契约`。

> 说明：`Sources.vue` 当前在 git 中呈虚拟态（committed blob 即已为 node 虚拟字节），因此 `git diff` 对该文件表现为 binary。本阶段通过 **node 源码引用核验** + 受控脚本（仅改动这两个文件）保证修改范围可控；其余被禁文件均未在任何命令中触及。

## 2. 实现功能

### 2.1 四字段展示（表格新增 4 列）
插入位置：原「最近运行时间」列与「操作」列之间。列宽沿用 Apple 风格 `width` 设定。

| 列名 | 字段 | 展示逻辑 |
| --- | --- | --- |
| 自动采集 | `schedule_enabled` | admin（`isSuperuser`）：`el-switch` 行内开关，乐观更新 + 回滚；非 admin：只读展示 `自动`/`手动` |
| 采集周期 | `schedule_interval_minutes` | `{{ value }} 分钟`，空值显示 `—` |
| 下一次采集 | `next_collect_time` | 复用 `formatTime()`，空值 `—` |
| 最近采集 | `last_collect_time` | 复用 `formatTime()`，空值 `—` |

表头（`<thead>`）、表体（`<tbody>` 行）、空行 `colspan`（11 → 15）同步更新。

### 2.2 单源调度编辑（操作列「调度」按钮）
- 操作列新增「调度」按钮，`v-if="isSuperuser"`（复用既有权限，不新建）。
- 打开新 `el-dialog`（`v-model="scheduleVisible"`），含：
  - 自动采集：`el-switch`（`scheduleDraft.schedule_enabled`）
  - 采集周期：`el-input-number` `:min="5"` `:max="1440"`
- 保存调用 `PATCH /api/admin/data-sources/{id}`，body **仅** `{ schedule_enabled, schedule_interval_minutes }`（**不发送** `enabled` / `priority` / `config_json`）。
- 成功后乐观更新当前列表行对应字段并关闭弹窗；失败走 `ElMessage.error` 既有错误处理风格。
- 参考既有 `onToggle` 模式实现行内 switch 的乐观更新 + 回滚（`onScheduleEnabled`）。

### 2.3 批量调度设置（顶部 toolbar-right）
- toolbar-right 新增「统一采集频率设置」按钮，`v-if="isSuperuser"`。
- 打开新 `el-dialog`（`v-model="batchVisible"`），含：
  - 范围：`el-select`（all / enabled_only）
  - 自动采集：`el-switch`
  - 采集周期：`el-input-number` `:min="5"` `:max="1440"`
- 保存调用 `POST /api/admin/data-sources/schedule/batch`，body `{ scope, schedule_enabled, interval_minutes }`。
- 成功：显示 `affected_count`（`已更新 N 个数据源`）并 `reload()`；失败：`ElMessage.error`。

## 3. API 调用验证

| 调用 | 端点 | 方式 | 请求体 | 验证 |
| --- | --- | --- | --- | --- |
| 列表（已有，展示新字段） | `GET /api/admin/data-sources` | `api.get` | — | 4 字段由响应直接渲染（类型已扩展） |
| 单源保存 | `PATCH /api/admin/data-sources/{id}` | `api.patch` | `{ schedule_enabled, schedule_interval_minutes }` | ✅ 源码核验 body 仅含 2 字段 |
| 批量保存 | `POST /api/admin/data-sources/schedule/batch` | `api.post<DataSourceScheduleBatchResponse>` | `{ scope, schedule_enabled, interval_minutes }` | ✅ 端点路径 + 字段源码核验通过 |
| 摘要（已存在，未在本阶段调用） | `GET /api/admin/data-sources/schedule/summary` | — | — | 类型 `DataSourceScheduleSummary` 已预留，按需可接入 |

**源码引用核验**（node 读取 Sources.vue 全文）：
- 4 字段 `schedule_enabled` / `schedule_interval_minutes` / `next_collect_time` / `last_collect_time` 均正确引用 ✅
- 4 个新表格列、2 个新弹窗（`scheduleVisible` / `batchVisible`）、5 个新函数（`onScheduleEnabled` / `openSchedule` / `saveSchedule` / `openBatchSchedule` / `saveBatchSchedule`）均存在 ✅
- 批量路径 `'/admin/data-sources/schedule/batch'`、两个 PATCH 调用均在位 ✅
- 两个 `el-input-number` 均 `:min="5"`（与后端 `CHECK(>=5)` 对应）✅
- `saveSchedule` PATCH body 仅 `schedule_enabled` + `schedule_interval_minutes` ✅

**构建产物核验**（node 扫描 `dist/assets`）：`index-Cgz9cTLJ.js` 含 `schedule/batch` / `affected_count` / `data-sources/schedule` ✅ —— 改动已打进生产 bundle。

## 4. 权限控制说明

- 沿用既有 `usePermission().isSuperuser`（`superuser` 或 `role==='admin'`）作为所有编辑控件的显示门禁。
- 新增的「调度」按钮、「统一采集频率设置」按钮、表格内 `el-switch` 均 `v-if="isSuperuser"`，与既有「配置」「新建」按钮同口径。
- **未引入任何新权限标识 / 角色 / 路由守卫**，完全复用现有体系。

## 5. 构建结果

- 命令（按约束，未用 `npm run build`）：
  `node --max-old-space-size=1400 node_modules/vite/bin/vite.js build`
- 结果：**✅ 成功**，`exit_code=0`，耗时 **15.69s**。
- warning：仅存在既有的「大 chunk」提示（`index` chunk ≈ 2.7MB，属应用既有体量，**非本次改动新增**）；本次新增代码量极小，未触发任何新的 warning / error。
- 说明：本阶段首轮后台构建因 PowerShell 未 `cd` 到 frontend 目录导致 `Could not resolve entry module "index.html"`（属执行路径错误，非代码错误）；修正工作目录后重新构建通过。

## 6. 风险说明

- **R1（Sources.vue 复杂度）**：文件已 891 → ~980 行，单文件承载表格/3 弹窗/新建弹窗。本次仅做增量插入，未重构，风险可控；后续若继续膨胀建议拆分弹窗组件。
- **R2（权限显示）**：新增控件已统一 `v-if="isSuperuser"`，非 admin 看到只读文本（自动/手动/`—`），与现有「启用」列只读展示一致。
- **R3（API 字段兼容）**：`DataSourceItem` 4 字段均定义为 **optional**；后端缺失时前端以 `—`/默认展示，不会因字段缺失报错。`schedule_interval_minutes` 前端 `:min="5"` 与后端 `CHECK(>=5)` 对齐，避免越界被拒。
- **R4（Vue 文件编码/虚拟化）**：`Sources.vue` 为 node 虚拟态，本阶段**全程使用 node 脚本读写**，未触发 IDE 格式化或编码转换，文件字节态保持一致（git 仍呈虚拟 diff，属历史遗留，非本次引入）。
- **R5（构建回归）**：构建通过、产物含新代码，无回归。注意 `dist/` 为构建产物，部署需下一阶段授权。

## 7. 未执行事项（明确记录）

- ❌ **未运行 `backend/_d.py`**（前端静态产物未部署到生产后端托管目录）。
- ❌ **未部署生产静态文件**（生产前端部署需下一阶段授权）。
- ❌ **未修改后端**（API 契约、Collector、Scheduler 均未触碰）。
- ❌ **未修改数据库**（无迁移、无数据写入；4 字段由已上线的 p12 迁移提供）。
- ❌ 未改动 `router` / `DataManage.vue` / `permission` / `nginx` / build 配置 / 任何依赖。

---

### 完成标准核对
✅ 修改仅限 `Sources.vue` + `types/index.ts`
✅ 四字段展示 / 单源调度 / 批量调度 均实现并源码核验
✅ API 调用方式正确（PATCH 仅 2 字段、POST batch 路径与字段正确）
✅ 构建成功（15.69s，exit 0，无新增 warning）
✅ 权限复用 `isSuperuser`，未新增体系
✅ 未部署、未改后端、未改数据库、未运行 `_d.py`

**本阶段已停止，等待下一步授权（前端部署 / 进入其他阶段）。**
