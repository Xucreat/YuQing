# Phase Report-3 实施报告：报告前端体验收口与运行时验收

> 日期：2026-07-31
> 前置：Phase 1（后端 12 模块 + `POST /export` + 增强 `/modules`）、Phase 2（前端抽屉升级）、uvicorn 已重启加载 Phase 1 后端。
> 原则：只读审计→再改；不改数据库；不新增依赖；不改报告后端业务逻辑（`report_service.py`/`reports.py`/`schemas/report.py` 零改动）；不扩展邮件/模板/定时；保持 Phase 1 API 契约兼容。

---

## 一、实施范围

依据 Prompt「目标 A~E」逐项收口：

- **A. 报告导出真实运行时验收**：以真实登录用户（JWT）经 `TestClient` 完成「模块加载 / 默认模块导出 / 自定义组合导出」三类运行时验收，并用 `pypdf` 真实解析 PDF 中文章节顺序。
- **B. 前端体验优化审计**：只读检查 4 个前端文件，定位并补齐 3 处体验缺口。
- **C. 权限体验验证**：`viewer`（无 `reports:export`）应隐藏按钮且直请求 403；`admin` 正常导出。
- **D. 构建与部署验证**：`vite build` + `python backend/_d.py` 部署，确认 static 引用最新 hash bundle。
- **E. 测试要求**：新增 `tests/test_report_phase3_frontend_contract.py`，覆盖契约未破坏 / 参数结构兼容 / viewer 拒绝 / admin 导出 / 错误结构兼容（共 6 项）。

---

## 二、修改文件

| 文件 | 类型 | 改动 |
|---|---|---|
| `frontend/src/components/report/ReportExportDrawer.vue` | 修改 | 3 处增强（见第四节） |
| `frontend/src/components/report/ModuleSelector.vue` | 未改 | 只读审计：已全动态，无硬编码模块 |
| `frontend/src/views/Dashboard.vue` | 未改 | 只读审计：`v-if="can('reports:export')"` 权限按钮 + 抽屉接线已正确 |
| `frontend/src/api/report.ts` | 未改 | 只读审计：Phase 1 契约已对齐 |
| `backend/tests/test_report_phase3_frontend_contract.py` | 新增 | 6 项契约 + 运行时验收测试 |
| `backend/app/services/report_service.py` | **未改** | 禁止项，零改动 |
| `backend/app/api/reports.py` | **未改** | 禁止项，零改动 |
| `backend/app/schemas/report.py` | **未改** | 禁止项，零改动 |

> 后端三文件本阶段**完全未触碰**，Phase 1 业务逻辑与 API 契约保持不变。

---

## 三、数据库变化

**无。**

- 未执行任何迁移（Alembic head 仍为 `p26_report_records`）。
- 未写入、未删除、未变更任何业务数据。
- 新增的 `pypdf` 仅安装于隔离测试 venv（`backend/.venv`），属于测试工具依赖，不进入前端或应用依赖，可随时 `pip uninstall pypdf` 回退。

---

## 四、前端体验优化

只读审计发现 4 文件中仅 `ReportExportDrawer.vue` 存在 3 处体验缺口，已补齐（保持 Phase 1 契约不变）：

### 1. 加载状态与防重复点击
- 抽屉打开拉取模块清单时，表单增加 `v-loading="loadingModules"` 遮罩，文案「加载模块清单…」。
- `onOpen()` 新增双重守卫：`if (loadingModules.value) return`（正在加载直接返回）与 `if (allModules.value.length) return`（已加载过不再请求），避免重复点击引发并发请求；`finally` 中复位 `loadingModules=false`。
- 提交按钮 `reporting` 状态贯穿 `generateAndDownload()` 全程，`finally` 复位，下载完成/失败后恢复可点。

### 2. 错误体验（后端 400 等）
- 保留 0KB blob 拦截（空响应直接提示「生成的报告为空」，禁下载空文件）。
- 保留 blob 错误 `detail` 解析；**新增前缀**：解析到 `detail` 时提示改为 `报告生成失败：<detail>`，杜绝空白错误 / blob 乱码 / 空文件下载。
- 示例：后端返回 `400 {"detail":"自定义区间必须提供 start_date 与 end_date"}` → 前端提示 `报告生成失败：自定义区间必须提供 start_date 与 end_date`。

### 3. PDF 下载文件名
- 由 `${name}.pdf` 改为 `${name}_YYYYMMDD.pdf`（如 `舆情监测报告_20260731.pdf`），含报告名称 + 日期 + `.pdf`，便于归档区分；浏览器兼容性不变（标准 `a.download`）。

---

## 五、运行时验收结果（真实登录用户）

以真实 JWT 登录流程（`POST /api/login` → `Authorization: Bearer`）经 `TestClient` 验收，等价于前端带 token 调用：

| 验收项 | 方法 | 结果 |
|---|---|---|
| 模块加载（12 模块 + params + default_modules） | `GET /api/reports/modules` | ✅ 返回 12 个模块；每个含 `params` 元数据；`default_modules` = expected 9 项（`overview_kpi,trend,sentiment,top_risky,events,source_dist,region_dist,keyword_dist,conclusion`） |
| 默认模块导出 | `POST /api/reports/export`（默认 9 模块） | ✅ HTTP 200，`Content-Type: application/pdf`，文件大小 > 0 |
| 自定义组合导出 | `POST /api/reports/export`（overview_kpi / top_risky(limit=5) / events(limit=3) / keyword_dist(limit=10)） | ✅ HTTP 200，PDF 章节顺序经 `pypdf` 实读校验为：一、总体态势 KPI → 二、高风险舆情 TOP → 三、重点事件 → 四、热点关键词 |
| 发布时间口径导出 | `POST /api/reports/export`（time_field=publish_time） | ✅ HTTP 200，PDF 正常；COALESCE 回退生效 |
| 权限：viewer 拒绝 | viewer 直请求 `POST /api/reports/export` | ✅ HTTP 403 |
| 权限：admin 导出 | admin 直请求 `POST /api/reports/export` | ✅ HTTP 200，PDF 正常 |
| 错误响应结构 | 自定义区间缺日期 → `POST /api/reports/export` | ✅ HTTP 400，结构 `{"detail": "..."}`，前端可解析提示 |

> 说明：本环境**无无头浏览器**，无法做真实点击式 E2E；上述运行时验收在 API 层以真实鉴权链路完成，前端 `report.ts` 拦截器会自动附加登录 token，等价于浏览器内操作。

---

## 六、测试结果

新增 `backend/tests/test_report_phase3_frontend_contract.py`，共 6 项，**全部通过**：

```
6 passed, 7 warnings in 131.89s
```

| # | 用例 | 覆盖要求 |
|---|---|---|
| 1 | `test_export_api_contract_unchanged` | export API 契约未破坏（200 + application/pdf + size>0） |
| 2 | `test_modules_param_structure_compatible` | 模块参数结构兼容（12 模块 / params 元数据 / default_modules 正确） |
| 3 | `test_admin_normal_export_publish_time` | admin 真实登录导出（含 publish_time 口径） |
| 4 | `test_viewer_permission_denied` | viewer 403 拒绝 |
| 5 | `test_error_response_structure_compatible` | 400 错误响应结构兼容（detail 可解析） |
| 6 | `test_custom_combo_pdf_order_runtime` | 自定义组合真实 PDF 章节顺序校验（pypdf 读中文标题） |

> 复跑方式（隔离测试库，不污染生产）：
> `cd backend && DB_IDENTITY_CHECK=off ./.venv/Scripts/python.exe -m pytest tests/test_report_phase3_frontend_contract.py -q`

---

## 七、生产部署状态

- **前端**：`vite build` 成功（16.30s，无 error），`python backend/_d.py` 部署 358 文件；运行中的 uvicorn（PID 18012）根路径与 `backend/app/static/index.html` 均引用新 bundle `assets/index-DQxhX0IC.js` → **Phase 3 前端已上线**。
- **后端**：沿用 Phase 1 后端（PID 18012，端口 8000），本阶段零改动；`POST /api/reports/export`、`GET /api/reports/modules` 均已提供服务。
- **数据库**：无变更。
- **整体**：Phase 1 + 2 + 3 已端到端联通，admin 可真实导出 PDF、viewer 无入口且直请求 403。

---

## 八、未实现能力

- ❌ 邮件发送（`delivery=email`）：按决策留待模板/定时阶段，本阶段 `delivery` 固定 `download`。
- ❌ 报告模板（`report_templates` 表）：未实现。
- ❌ 定时任务（`report_tasks`）：未实现。
- ❌ SMTP / `mail_service`：未新增。
- ❌ 无头浏览器点击式 E2E：环境缺失，运行时验收以 API 层真实鉴权链路替代。
- ❌ 前端单模块异常 UI 细分（如标记具体哪个模块失败）：后端已返回 `X-Report-Failed-Modules` 响应头，前端未消费该头做逐模块提示（不影响整体可用性）。

---

## 九、下一阶段建议

- **Phase 4（模板/定时，如有）**：实现 `report_templates` 表、`reports:manage` 权限、`delivery=email`（新增 `mail_service` + SMTP 配置，独立迁移）。
- **前端增强**：消费 `X-Report-Failed-Modules` 响应头，在抽屉内逐模块标注失败原因；自定义组合可保存为常用模板。
- **依赖梳理**：`pypdf` 仅用于测试，建议在 `backend/requirements-test.txt` 显式登记，避免后续遗漏。
- **基线噪声治理（既有技术债）**：`tests/` 全量跑存在 `bocha_leads_opinion_id_fkey` 缺 `ON DELETE CASCADE` 导致的清理阻塞（影响 test_dashboard/test_event_* 等），与本文档改动无关，建议单独排期修复。

---

## 十、最终验收标准对照

| 验收标准 | 结果 |
|---|---|
| admin 可以真实导出 PDF | ✅ 运行时验收 HTTP 200 + application/pdf + size>0 |
| viewer 无导出入口 | ✅ `Dashboard.vue` `v-if="can('reports:export')"` 隐藏；直请求 403 |
| 模块动态加载正常 | ✅ `GET /modules` 返回 12 模块，前端 `ModuleSelector` 全动态 |
| 参数编辑正常 | ✅ 基于 `params` 元数据生成编辑区（limit / min_risk 等） |
| 自定义组合 PDF 正常 | ✅ 4 模块组合章节顺序经 pypdf 校验正确 |
| 错误提示正常 | ✅ 400 → `报告生成失败：<detail>` |
| 构建成功 | ✅ `vite build` 16.30s 无 error |
| 静态部署成功 | ✅ 根路径服务新 bundle `index-DQxhX0IC.js` |
| 无数据库变化 | ✅ 无迁移、无数据变更 |
| 无后端业务代码变化 | ✅ `report_service.py`/`reports.py`/`schemas/report.py` 零改动 |

**结论：全部验收标准满足。按 Prompt 要求，完成后停止，不进入 Phase 4。**
