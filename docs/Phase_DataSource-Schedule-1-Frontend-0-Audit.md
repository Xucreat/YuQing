# Phase DataSource-Schedule-1-Frontend-0
# 数据源调度配置前端改造 —— 实施前只读审计报告

> 阶段：`Phase DataSource-Schedule-1-Frontend-0`（只读审计）
> 项目：`C:\Users\Administrator\Desktop\YQ`（舆情监测平台 / FastAPI 后端 + Vue3 前端）
> 审计日期：2026-08-03
> 关联后端：`Phase DataSource-Schedule-1-A`（p12 已迁移、per_source scheduler 已上线、新 API 已生效）
> 审计边界：✅ 阅读 / ✅ 搜索 / ✅ 分析 / ✅ 输出报告；❌ 未修改任何 Vue/TS/API/样式/组件/依赖文件；❌ 未 npm install。
> 执行命令（仅基线）：`node --max-old-space-size=1400 node_modules/vite/bin/vite.js build`（= `npm run build` 的等价防 OOM 形式）。

---

## 1. 前端架构概览（Frontend Architecture Overview）

| 维度 | 现状 |
| --- | --- |
| 框架 | Vue 3.5.12（`<script setup lang="ts">`） |
| 语言 | TypeScript 5.6.3（`vue-tsc` 为 devDependency，但 `build` 脚本仅 `vite build`，**不含类型检查**） |
| 构建 | Vite 5.4.10（`vite.config.js`：`@`→`src`，dev proxy `/api`→`http://localhost:8000`，`minify:false`、`modulePreload:false`、`emptyOutDir:true`） |
| UI 库 | Element Plus 2.8.4 + 自定义 scoped CSS（Apple 风格卡片） |
| 状态管理 | Pinia 2.2.4（`@/stores`，用于 `useAuthStore` 鉴权态）；**数据源列表状态为组件内 `ref/reactive`，无独立 store** |
| HTTP | 单一 Axios 实例 `api`（默认导出自 `@/api`，`baseURL:'/api'`，含 401 登出 / 403 权限提示拦截器） |
| 路由 | `vue-router` 4.4.5；数据源管理页路由为 `/data`（`DataManage.vue`），含 `tab=sources` 直达 |
| 权限 | `usePermission()` 组合式：`isSuperuser`（`auth.isSuperuser || role==='admin'`）、`hasPermission`、`hasModulePermission` 等 |

**关键澄清（消除潜在歧义）**：
- `Sources.vue` **不是孤儿文件**。虽然路由表未直接 import 它，但 `DataManage.vue`（即 `/data` 路由组件）的「数据源管理」tab 通过 `import SourcesView from '@/views/Sources.vue'` 将其作为 `<SourcesView>` 渲染。即：`/sources` → `/data?tab=sources` → `DataManage.vue` → `Sources.vue`。
- 因此 **`Sources.vue` 就是当前生产环境"数据源管理"页的真实组件**，用户指定的审计对象完全正确，无需路由改造即可承载调度配置 UI。

---

## 2. Sources.vue 结构分析

文件：`frontend/src/views/Sources.vue`（891 行，模板/脚本/样式单文件）。
> ⚠️ 该文件在磁盘上为 node 虚拟化写入态，Read 工具报"binary file"。本次审计通过 `node` 读取明文（`first4 = 3c 74 65 6d` = `<tem`，确为合法 Vue 源码）。结构分析基于 node 读取的明文。

### 2.1 页面结构
- **`<template>`**（行 1–~300）：`.ds-page` 根容器（`v-loading`）。
  - **`.toolbar`**（筛选工具栏）：左侧 `.filters`（`el-select` 区域/启用状态、`el-input` 搜索、刷新按钮）；右侧 `.toolbar-right`（`共 N 个数据源` 提示 + `v-if="isSuperuser"` 的「+ 新建采集源」按钮）。
  - **`.source-table-card` + `<table class="tbl">`**：数据源管理主表格。
  - **`.pager`**：`Pager` 分页组件。
  - **3 个 `el-dialog`**：① 查看历史（采集历史）② 配置（`config_json` 文本域）③ 新建采集源（表单）。
- **`<script setup lang="ts">`**（行 ~388–~870）：`ref/reactive` 局部状态；`api.get/post/patch` 内联调用；`usePermission().isSuperuser`；`onMounted(reload)`。
- **`<style scoped>`**（行 ~791–891）：Apple 风格（白卡、`border-radius:18px`、浅阴影、`#1d1d1f` 文字、`#86868b` 次要色），自定义 class（`.ds-page/.toolbar/.tbl/.pill/.card` 等），**未重度依赖 element-plus 主题变量**。

### 2.2 当前表格列（11 列）
| # | 列名 | 字段 | 备注 |
| --- | --- | --- | --- |
| 1 | 名称 | `s.name` / `s.key` / `s.type` | 含专用/通用型标签 `s.collector_kind` |
| 2 | 区域 | `s.scope_display` | pill |
| 3 | 关键词策略 | `s.keyword_mode` / `s.keyword_description` / `s.effective_keywords` | pill + 描述 |
| 4 | 启用 | `s.enabled` | `v-if="isSuperuser"` 用 `el-switch`，否则只读文本 |
| 5 | 优先级 | `s.priority` | `v-if="isSuperuser"` 用 `el-input-number`，否则文本 |
| 6 | 健康状态 | `s.health_summary.health_status` | pill + 原因 |
| 7 | 最近状态 | `s.latest_run_status` | pill |
| 8 | 最近抓取 / 新增 | `qualityFor(s).latest_fetched_raw / latest_created` | 指标数字 |
| 9 | 采集质量 | `s` 质量 `empty_fetch_risk` | pill + 提示 |
| 10 | 最近运行时间 | `s.latest_run_at` | `formatTime()` |
| 11 | 操作 | — | 「查看历史」「配置」（`v-if="isSuperuser"`） |

**新增字段插入位置建议**：在**第 10 列「最近运行时间」之后、第 11 列「操作」之前**插入 4 列：
- 自动采集（`schedule_enabled`）
- 采集周期（`schedule_interval_minutes`）
- 下一次采集（`next_collect_time`）
- 最近采集（`last_collect_time`）

### 2.3 当前编辑弹窗结构
- **配置弹窗**（`configVisible`）：仅编辑 `config_json`（文本域）；专用型采集器显示"无需填写"提示。保存 → `api.patch('/admin/data-sources/'+id, { config_json })`。
- **新建采集源弹窗**（`createVisible`）：`name/key/type/scope_region_codes/priority/enabled/config_json`；「测试连接」「保存」。
- **查看历史弹窗**（`historyVisible`）：只读采集运行记录。

**新增调度编辑落点建议**：
- 方案 A（推荐，低侵入）：在「操作」列新增「调度」按钮（`v-if="isSuperuser"`），打开**独立调度弹窗**，含 `schedule_enabled`（`el-switch`）+ `schedule_interval_minutes`（`el-input-number :min="5"`，对应后端 `CHECK(>=5)`）。保存 → `api.patch('/admin/data-sources/'+id, { schedule_enabled, schedule_interval_minutes })`。
- 方案 B：将调度字段并入现有「配置」弹窗（作为新分区）。侵入现有弹窗，不推荐。

### 2.4 当前状态管理
- 全为组件内 `ref/reactive`：`sources/page/size/loading/filter*/qualityBySourceId/history*/config*/create*` 等。
- 无 Pinia store 承载数据源列表；鉴权态取自 `useAuthStore`（经 `usePermission`）。
- 乐观更新模式已建立：`onToggle` / `onPriority` 先改本地值、失败回滚 + `ElMessage` 提示 —— 调度保存应复用同一模式。

### 2.5 修改入口汇总（实施阶段落点）
| 改动 | 文件位置 | 方式 |
| --- | --- | --- |
| 表格 +4 列 | `<thead>` / `<tbody>`（第 10–11 列间） | 模板插入 |
| 单源「调度」按钮 + 弹窗 | 「操作」列 + 新增 `<el-dialog>` | 模板 + 脚本 |
| 顶部「统一采集频率设置」 | `.toolbar-right`（新建按钮 + 弹窗） | 模板 + 脚本 |
| 保存逻辑 | `script` 新增 `saveSchedule` / `saveBatch` | 脚本 |
| 类型扩展 | `types/index.ts` | 类型声明 |
| API 调用 | 内联 `api.patch/post`（或薄封装） | 脚本 |

---

## 3. DataSource 类型分析

文件：`frontend/src/types/index.ts`（注意：中文注释为 GBK 误码 mojibake，但代码/ASCII 完好，编译不受影响；编辑时需保留 ASCII 代码、谨慎处理注释）。

### 3.1 当前 `DataSourceItem`（行 417–439）
```ts
export interface DataSourceItem {
  id: number
  key: string
  name: string
  type: string
  enabled: boolean
  priority: number
  scope_region_codes: string | null
  region_codes: string[]
  region_names: string[]
  scope_display: string
  config_json: string | null
  last_run_at: string | null
  last_status: string | null
  latest_run_status: string | null
  latest_run_at: string | null
  updated_at: string | null
  keyword_mode: 'global_region' | 'source_keywords' | 'no_filter' | 'full_collection' | 'unknown'
  keyword_source: string
  effective_keywords: string[]
  keyword_description: string
  health_summary?: DataSourceHealthSummary
}
```
**结论**：`DataSourceItem` **不含**任何 `schedule_*` 字段。列表接口（`GET /api/admin/data-sources`）后端已回传 4 个新字段，但前端类型未声明 → 当前以 `s.schedule_enabled` 等访问会因 TS 类型缺失报错（若开启严格检查）。

### 3.2 新增字段位置建议
在 `DataSourceItem` 内追加（建议 optional，兼容历史/未返回场景）：
```ts
  // —— Phase DataSource-Schedule-1：数据源级采集调度 ——
  schedule_enabled?: boolean
  schedule_interval_minutes?: number
  next_collect_time?: string | null
  last_collect_time?: string | null
```
> 放置位置：紧跟 `config_json` / 运行时间字段之后（语义相邻），或置于 `health_summary?` 之前均可。

### 3.3 新增类型（建议）
```ts
// GET /api/admin/data-sources/schedule/summary
export interface DataSourceScheduleSummary {
  mode: 'uniform' | 'mixed'
  interval_minutes?: number
  distribution?: Record<string, number>
  enabled_auto_count?: number
}

// POST /api/admin/data-sources/schedule/batch
export interface DataSourceScheduleBatchRequest {
  scope: 'all' | 'enabled_only'
  schedule_enabled: boolean
  interval_minutes: number   // 后端 CHECK >=5
}
export interface DataSourceScheduleBatchResponse {
  affected_count: number
}
```

---

## 4. API 接入分析

### 4.1 现有 API 位置
- **统一客户端**：`frontend/src/api/index.ts` 默认导出 `api`（Axios 实例）。**未定义** `getDataSources/updateDataSource/runCollector` 等具名函数 —— Sources.vue 内为**内联 URL 调用**：
  - 列表：`api.get('/admin/data-sources', { params })`
  - 质量：`api.get('/admin/data-sources/quality', { params:{days:7} })`
  - 切换启用：`api.patch('/admin/data-sources/'+id, { enabled })`
  - 改优先级：`api.patch('/admin/data-sources/'+id, { priority })`
  - 历史：`api.get('/admin/data-sources/'+id+'/runs', { params })`
  - 保存配置：`api.patch('/admin/data-sources/'+id, { config_json })`
  - 测试/新建：`api.post('/admin/data-sources/test' | '')`
- 拦截器已统一处理 401（登出）/ 403（`__permissionDenied` 标记 + 全局提示），调用处无需重复处理权限文案。

### 4.2 新增接口建议位置
保持与现有**内联调用**风格一致，直接在 Sources.vue 内调用（推荐，零新增文件）；或按团队偏好在 `api/index.ts` 增加薄封装（可读性更佳）：
```ts
// 可选薄封装（非必须）
export async function getScheduleSummary() {
  return api.get<DataSourceScheduleSummary>('/admin/data-sources/schedule/summary')
}
export async function batchUpdateSchedule(payload: DataSourceScheduleBatchRequest) {
  return api.post<DataSourceScheduleBatchResponse>('/admin/data-sources/schedule/batch', payload)
}
```
| 后端端点 | 前端调用点 | 说明 |
| --- | --- | --- |
| `GET /admin/data-sources/schedule/summary` | 顶部设置弹窗「当前默认」展示（可选） | 返回 `{mode, interval_minutes\|distribution, enabled_auto_count}` |
| `POST /admin/data-sources/schedule/batch` | 顶部「统一采集频率设置」弹窗保存 | body `{scope, schedule_enabled, interval_minutes}` → `{affected_count}` |
| `PATCH /admin/data-sources/{id}`（已存在） | 单源「调度」弹窗保存 | 复用现有 patch，body 增加 `schedule_enabled` + `schedule_interval_minutes` |
| `POST /collector/run`（后端已存在） | 如后续需「立即采集」按钮可调用 | 非本阶段必需 |

**request/response 类型**：需新增 `DataSourceScheduleSummary` / `DataSourceScheduleBatchRequest` / `DataSourceScheduleBatchResponse`（见 §3.3）。

---

## 5. 权限分析

### 5.1 当前 admin 判断方式
- `usePermission()` 返回 `isSuperuser`（computed：`auth.isSuperuser || role==='admin'`）。
- Sources.vue 内**所有写操作控件**（`el-switch` 启用、`el-input-number` 优先级、「配置」「新建采集源」按钮）均以 `v-if="isSuperuser"` 门控。
- 页面级（tab）可见性在 `DataManage.vue` 用 `hasPermission('sources:read')` 控制。
- 后端：`PATCH /admin/data-sources/{id}` 需 `sources:write`/`require_admin`；读接口已加 `sources:read`。

### 5.2 新增调度编辑应复用什么
- **推荐复用 `isSuperuser`**（与现有全部写控件一致，零新权限体系，最低风险）。
- 若希望更贴合后端 `sources:write` 语义，可改用 `hasPermission('sources:write')`（组合式已具备），但需评估"非超管但持 sources:write 的角色"当前被 `isSuperuser` 隐藏的现状差异。
- **结论**：本阶段不新建权限体系；单源「调度」按钮、顶部「统一采集频率设置」按钮均加 `v-if="isSuperuser"`，与现有「配置」按钮同口径。

---

## 6. 前端实施方案建议（仅设计，未修改）

> 以下为 `Phase DataSource-Schedule-1-Frontend-1` 的落点设计，不含任何代码变更。

1. **表格 +4 列**：`<thead>` 第 10 列后插入「自动采集 / 采集周期 / 下一次采集 / 最近采集」；`<tbody>` 对应 `<td>`：
   - 自动采集：`schedule_enabled` → `el-switch`（`v-if="isSuperuser"` 可切换，否则 pill 只读）
   - 采集周期：`schedule_interval_minutes` → `X 分钟`
   - 下一次采集/最近采集：`next_collect_time` / `last_collect_time` → `formatTime()`（复用现成函数）
2. **单源调度弹窗**：「操作」列新增「调度」按钮 → 独立 `<el-dialog>`，含 `el-switch(schedule_enabled)` + `el-input-number(schedule_interval_minutes, :min="5")`，保存调 `api.patch(..., {schedule_enabled, schedule_interval_minutes})`；乐观更新 + 回滚 + `ElMessage`（复用 `onToggle` 模式）。
3. **顶部统一设置区**：`.toolbar-right` 新增「统一采集频率设置」按钮（`v-if="isSuperuser"`）→ 弹窗含 `scope`(`all`|`enabled_only` 单选) + `schedule_enabled` + `interval_minutes`(默认 30, :min="5")；保存调 `api.post('/admin/data-sources/schedule/batch', {...})`，成功提示 `affected_count`。
4. **类型扩展**：`types/index.ts` 的 `DataSourceItem` 增 4 字段（optional）；新增 `DataSourceScheduleSummary` / `DataSourceScheduleBatchRequest` / `DataSourceScheduleBatchResponse`。
5. **API 扩展**：内联调用（§4.2）或薄封装；PATCH 已支持，无需后端改动。
6. **next_collect_time 重算**：后端在 PATCH `interval` 时自动重算（已验证），前端仅做展示，不本地计算。

---

## 7. 风险列表

| ID | 风险 | 级别 | 说明 / 缓解 |
| --- | --- | --- | --- |
| **R1** | Sources.vue 复杂度 | 中 | 单文件 891 行，改动分散在 template/script/style。缓解：改动局部化（新增列/1 弹窗/1 按钮），复用既有 `formatTime`/`pill`/`el-switch` 模式，不膨胀现有「配置」弹窗。 |
| **R2** | 权限显示 | 低 | 前端用 `isSuperuser` 门控，但后端按 `sources:write` 鉴权；若未来存在"非超管但持 sources:write"角色，前端会隐藏其可用控件。缓解：本阶段复用 `isSuperuser`（与现状一致），不新建体系；差异已记录。 |
| **R3** | API 字段兼容 | 中 | ① 新字段在 `DataSourceItem` 必须声明（否则严格 TS 报错）；建议 optional 以兼容旧响应。② `interval_minutes < 5` 触发后端 422（`CHECK>=5`）→ 前端 `el-input-number :min="5"` 防御。③ PATCH 须仅发送 `schedule_*` 字段（不覆盖 `enabled`/`config_json`）。 |
| **R4** | **Vue 文件修改编码（高危）** | **高** | **`Sources.vue` 与 `DataManage.vue` 在磁盘上为 node 虚拟化写入态：Read 工具报"binary file"、Grep 无匹配**。必须用 `node` 读取/写入（node 见明文），**绝不能用 Read/Write 工具直接改这两个 .vue（会损坏/失败）**。另 `types/index.ts` 中文注释为 GBK mojibake，编辑时保持 ASCII 代码不变。实施阶段建议：用 node 管道读取 → 编辑 → node 写回，或 `git show HEAD:file` 取干净版本对照。 |
| **R5** | 构建回归 | 中 | 基线构建成功（14.4s），但产物含两个 ~2.7MB `index-*.js`（未压缩，`minify:false` 所致，疑似既有双入口 chunk）；新增 UI 体量小，影响可控。缓解：实施后用**相同命令**（`node --max-old-space-size=1400 .../vite.js build`）复测；注意 `npm run build` 直跑易 OOM，须带内存参数；`build` 脚本不含 `vue-tsc`，类型错误不会阻断构建。 |

---

## 8. 下一阶段建议（Phase DataSource-Schedule-1-Frontend-1 实施计划）

等待授权后执行，建议步骤：

1. **安全读取源码**：用 `node -e "process.stdout.write(require('fs').readFileSync('src/views/Sources.vue','utf8'))"` 取得明文工作副本（**禁止 Read 工具直接读**）。
2. **类型**：`types/index.ts` 扩展 `DataSourceItem`（+4 optional 字段）并新增 `DataSourceScheduleSummary` / `DataSourceScheduleBatchRequest` / `DataSourceScheduleBatchResponse`。
3. **API**：Sources.vue 内联调用 `api.patch(..., {schedule_enabled, schedule_interval_minutes})` 与 `api.post('/admin/data-sources/schedule/batch', {...})`；如需展示当前默认可加 `api.get('/admin/data-sources/schedule/summary')`（可选）。
4. **Sources.vue 模板**：
   - `<thead>/<tbody>` 第 10–11 列间插入 4 列；
   - 「操作」列加「调度」按钮（`v-if="isSuperuser"`）→ 单源调度弹窗；
   - `.toolbar-right` 加「统一采集频率设置」按钮（`v-if="isSuperuser"`）→ 批量弹窗。
5. **Sources.vue 脚本**：新增 `scheduleDialogVisible/scheduleDraft/batchDialogVisible/batchDraft` 与 `openSchedule/saveSchedule/openBatch/saveBatch`，复用 `onToggle` 乐观更新+回滚模式；`el-input-number :min="5"` 防御。
6. **权限**：新控件复用 `isSuperuser`。
7. **构建 + 部署**（需授权）：`node --max-old-space-size=1400 node_modules/vite/bin/vite.js build` → 复测无回归 → `python backend/_d.py` 部署到 `backend/static`（部署需单独授权，**本审计未执行**）。
8. **验证**：dev 代理 `/api`→`:8000`，以 admin 登录进 `/data?tab=sources`，确认 4 列显示、单源调度保存后 `next_collect_time` 重算、批量设置返回 `affected_count` 正确。

---

## 完成标准核对

- ✅ **未修改任何代码**（仅读取、搜索、分析；构建为允许的基线记录，未改动源文件）
- ✅ **审计报告生成**（`docs/Phase_DataSource-Schedule-1-Frontend-0-Audit.md`）
- ✅ **build baseline 记录**（命令、14.4s 成功、产物清单、双 index chunk 现象）
- ✅ **明确实施修改点**（§2.5 落点表 + §6 设计 + §8 计划）
- ✅ **等待下一步授权**（停止，待确认进入 Frontend-1）

> 构建基线产物位于 `frontend/dist/`（构建生成物，非源码修改）。生产运行实例（uvicorn PID 48624）全程未重启、未受影响。
