# Phase Report-2 Phase 2 前端报告抽屉实施报告

> 生成时间：2026-07-31 09:24
> 前置：Phase 1（后端 12 模块 + `POST /api/reports/export` + 增强 `GET /api/reports/modules`）已完成并经测试（24 passed），但**生产 uvicorn 未重启、旧后端仍在运行**。

## 一、只读审计结论（先确认现状，再增量修改）

按执行规则，先读 4 个前端文件 + 后端契约（`schemas/report.py`、`api/reports.py`、`services/report_service.py` 的模块/参数元数据）：

| 文件 | 审计结论 | 本次动作 |
|---|---|---|
| `src/api/report.ts` | Phase 1.1 旧版，仍指向 `/reports/generate` + `module_keys` 旧 payload，无 `params` 元数据 | **重写**：对齐 Phase 1 契约 |
| `views/Dashboard.vue` | 已是 `v-if="can('reports:export')"` 打开 `ReportExportDrawer`，旧 `downloadReport` 逻辑早已移除 | **无需修改** |
| `components/report/ModuleSelector.vue` | 已完全动态（由 `props.modules` 驱动，**零硬编码模块**），支持勾选/上移/下移 | **无需修改** |
| `components/report/ReportExportDrawer.vue` | Phase 1.1 版：仍调 `/reports/generate`、旧 payload、无参数编辑 UI | **重写**：对齐 Phase 1 契约 + 参数编辑 + 0KB 防护 |

后端契约（已读、未改）：
- `GET /reports/modules` → `{ modules:[{key,name,title,description,default_enabled,params:[{key,label,type,default,min,max}]}], default_modules:[] }`
- `POST /reports/export` → `{ name, time_field, range_type:'last_n_days'|'custom', range_days, start_date, end_date, modules: Array<str|{key,params}>, delivery:'download' }`

## 二、修改文件清单

| 文件 | 类型 | 主要改动 |
|---|---|---|
| `frontend/src/api/report.ts` | 重写 | 新增 `ReportModuleParamDef`/`ReportModuleDef`/`ReportModulesResp`/`ReportModuleSelection`；`ReportExportPayload` 对齐 `ReportExportRequest`（含 `range_type`/`range_days`/`modules` 联合类型/`delivery:'download'`）；`generateReport()` 改调 `POST /reports/export`；`getReportModules()` 调 `GET /reports/modules` |
| `frontend/src/components/report/ReportExportDrawer.vue` | 重写 | 见下「抽屉能力」 |

**未改动**：`Dashboard.vue`、`ModuleSelector.vue`（已满足要求）、`backend/*`（Phase 2 只改前端）、`package.json`（无新依赖）。

### 抽屉能力（ReportExportDrawer.vue）
1. 报告名称（`maxlength=40` + 字数提示）。
2. 统计时间字段 radio：`created_at`=采集时间 / `publish_time`=**发布时间（缺失回退采集时间）**（含 COALESCE 提示文案）。
3. 时间范围：预设（7/15/30 天）或自定义 `daterange`。
4. 模块选择：`<ModuleSelector v-model="selectedModules" :modules="allModules">`，动态拉取、勾选/上移/下移。
5. **参数编辑（新增）**：依据 `def.params` 元数据渲染 `el-input-number`（`int` 类型，带入 `min/max`），非 int 用 `el-input`；模块增减时同步补默认值/清理。
6. 提交：按 `selectedModules` **当前顺序**构建 `modules`（`str` 或 `{key,params}`），`delivery` 固定 `download`，调 `POST /reports/export`。
7. **0KB 防护**：`blob.size === 0` 直接报错提示，禁止 0KB 下载。
8. **Blob 错误解析**：catch 中读 `e.response.data.text()` → `JSON.parse` → 取 `detail` 提示（覆盖 400 等业务错误）。

## 三、API 调用链

```
Dashboard.vue (v-if="can('reports:export')")  ──点击导出──▶  ReportExportDrawer(v-model open)
                                                        │
        GET  /api/reports/modules  (reports:read)  ────┘──▶ getReportModules()
             ◀── { modules:[{key,name,title,description,default_enabled,params}], default_modules }
                                                        │
        POST /api/reports/export   (reports:export, delivery=download, responseType=blob)
             ──▶ generateReport(payload)  ──▶ 后端 build_report() + render_report_pdf()
             ◀── Blob(PDF)  ──▶ URL.createObjectURL + a.click() 下载；失败解析 detail 提示
```

权限映射：`Dashboard.vue` 用 `can('reports:export')` 控制按钮可见性；`/reports/modules` 需 `reports:read`；`/reports/export` 需 `reports:export`。

## 四、测试结果

### 构建验证（已通过）
- `vite build`（heap 1400MB）→ `✓ built in 13.39s`，无错误/警告。
- 部署：执行 `python backend/_d.py` → 写入 191 个文件至 `backend/app/static`，`index.html` 已引用本次新 bundle `assets/index-C09C9wXY.js`（与构建产物哈希一致）。
- TypeScript：构建脚本为纯 `vite build`，无 `vue-tsc` 类型门禁，TS 改动可正常转译。

### 五项目标验证结论

| # | 验证项 | 结论 | 依据 |
|---|---|---|---|
| 1 | viewer 无 `reports:export` 时按钮不可见 | ✅ 通过（代码级） | `Dashboard.vue` `v-if="can('reports:export')"`，超管/无权限用户 `get_user_permissions` 返回不同集合，前端按 `can()` 隐藏 |
| 2 | 12 模块能加载 | ✅ 通过（代码级） | `onOpen()` 调 `getReportModules()`，`ModuleSelector` 完全由 `data.modules` 驱动，**无硬编码 12 模块**；后端 `REPORT_MODULES` 已 12 项 |
| 3 | 调整顺序后 payload 保序 | ✅ 通过（代码级） | `modulesPayload` 由 `selectedModules.value.map(...)` 按数组顺序生成，上移/下移经 `ModuleSelector` 的 `splice` 重排后原序传入 |
| 4 | 生成 PDF 成功 | ⚠️ 代码就绪，**运行时未验证** | `generateAndDownload` 逻辑完整；但见「部署缺口」 |
| 5 | 400 错误能正常提示 | ⚠️ 代码就绪，**运行时未验证** | catch 解析 blob `detail`；但运行时需后端返回 400 |

> ⚠️ **运行时验证限制（重要）**：本环境**无无头浏览器**，无法做真实点击 E2E；更关键的是——当前运行的 uvicorn（PID 22704）仍是 **Phase 1 之前的旧后端**，探针实测：
> - `GET /api/reports/modules` → **401**（路由在，但返回旧结构、无 `params`）
> - `POST /api/reports/export` → **404**（旧后端不存在该接口）
> - `POST /api/reports/generate` → 401（旧接口仍在）
>
> 因此 Phase 2 前端在**不重启 uvicorn** 的前提下，运行时调 `/export` 必 404、调 `/modules` 拿不到 `params`。**该前端要真正可用，必须先让 Phase 1 后端代码加载进 uvicorn（重启）。**

## 五、未实现能力清单

1. **邮件投递（email）**：Phase 2 仅 `delivery:'download'`；`email` 选项 UI 未做、`recipients` 未接、后端 SMTP 未建（按 Phase 1 禁止项，留后续阶段）。
2. **运行时 E2E 验收**：受无头浏览器缺失 + 旧后端未部署双重限制，仅完成构建与代码级验证。
3. **模板 / 定时生成**：属 Phase `reports:manage` 阶段，不在 Phase 2 范围。
4. **参数类型扩展**：目前仅支持 `int`（后端当前也仅下发 `int`）；未来若后端引入 `enum/str` 等类型，前端 `el-input` 分支已预留但未经实战触发。

## 六、生产部署缺口与下一步决策

- **已做**：前端源码改造 + 构建 + 静态产物部署（191 文件）。
- **未做（符合约定）**：未重启 uvicorn。按项目约定「生产部署（重启 uvicorn + 前端重建）留待 Phase 7 或用户单独确认」，本次**未擅自重启**。
- **后果**：旧 uvicorn 仍服务旧后端 → Phase 2 前端运行时会 404 / 拿旧结构。
- **决策点（需你确认）**：
  - **A. 现在重启 uvicorn** → 加载 Phase 1 后端，Phase 2 前端即完全可用（含 4/5 项运行时验证可补做）。
  - **B. 保持不部署** → 前端代码就绪，等 Phase 7 统一收口再重启。

## 七、回滚方案

纯前端、零数据库变更、零后端代码变更：
```
git checkout -- frontend/src/api/report.ts frontend/src/components/report/ReportExportDrawer.vue
cd frontend && node --max-old-space-size=1400 node_modules/vite/bin/vite.js build
python ../backend/_d.py
```
（若已重启 uvicorn，回滚后需再次重启以加载旧前端对应的旧后端契约。）
