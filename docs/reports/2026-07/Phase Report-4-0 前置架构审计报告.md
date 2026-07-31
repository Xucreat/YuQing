# Phase Report-4-0 前置架构审计报告（报告模板与运营化能力）

> 日期：2026-07-31
> 性质：**实施前只读审计**。未修改任何源码、数据库、配置、依赖；未启动任何写入；未调整权限数据；未改前端。
> 范围：评估 `report_templates` / `reports:manage` / 模板保存·复用·导出 / 后续邮件·定时挂载点是否值得现在实现、如何设计。

---

## 1. 当前报告系统架构现状

### 1.1 模块注册体系（稳定、可序列化）
`backend/app/services/report_service.py` 中 `REPORT_MODULES` 为 **有序 list（12 项）**，结构：

```python
{
  "key": "top_risky",            # 稳定字符串标识
  "name": "高风险舆情 TOP",
  "title": "高风险舆情 TOP",
  "description": "...",
  "data_fn": _m_top_risky,       # 仅后端内部引用
  "render_fn": _r_top_risky,     # 仅后端内部引用
  "default_enabled": True,
  "params": [{"key":"limit","label":"展示条数","type":"int","default":10,"min":1,"max":50}],
}
```

- **key 稳定**：12 个 key（`overview_kpi/trend/sentiment/top_risky/events/source_dist/region_dist/keyword_dist/risk_category/alert_summary/opinion_list/conclusion`）为字符串常量，不随内部函数改名而变。
- **顺序可序列化**：list 顺序 = 章节顺序，JSON 序列化后顺序保持。
- **params 元数据足够支持模板**：每项 param 含 `key/label/type/default/min/max`，前端据以渲染表单。模板只需存 `{key, params:{limit:5}}` 即可完整回填。
- 配套：`MODULE_MAP`（key→模块）、`DEFAULT_MODULE_KEYS`（9 项默认）、`ALL_MODULE_KEYS`、`MODULE_ALIASES`（`distribution`→三项展开）、`expand_module_keys()`（别展开+去重）。
- `ReportConfig.module_params: Dict[str, Dict[str, Any]]` = `{"top_risky": {"limit": 5}}`，**直接 JSON 可序列化**。

### 1.2 导出入口与配置契约
- `POST /api/reports/export`（正式入口，`reports:export` 权限）请求体 `ReportExportRequest`：
  `name, time_field(created_at|publish_time), range_type(last_n_days|custom), range_days, start_date, end_date, modules(List[Union[str,{key,params}]]), delivery('download'|'email'), recipients`。
- `_do_export()` 将 `payload.model_dump()` 整体存入 `report_records.config_json` → **导出配置已天然落盘为可复现快照**。
- `POST /api/reports/generate` 标 `deprecated`，薄适配层转调 `_do_export`，保持不变。
- `GET /api/reports/modules`（`reports:read`）返回 `ReportModuleDef[]`（含 `params` 元数据）+ `default_modules`。

### 1.3 审计表 `report_records`
字段：`id, name, config_json(JSONB), status(success|failed), created_by, created_at`。**无 `template_id`**；但 `config_json` 已自包含完整导出配置，历史记录可独立复现。

### 1.4 RBAC 现状
- `Permission`：`code` 唯一（`resource:action`）。已播种：`reports:read`、`reports:write`（legacy）、`reports:export`（Phase 1.1 / p26 迁移）。
- **`reports:manage`：全代码库无任何定义（不存在，未播种）**。
- 角色：`viewer` = `reports:read` 仅；`analyst` = `reports:read`+`reports:write`+`reports:export`；`admin`/超级用户 = `["*"]`。
- 权限判定权威来源 = `role_permissions` 关联表（`Permission`/`Role`/`User` 经 `role_permissions`/`user_roles` 多对多）。

### 1.5 前端现状
- `report.ts`：仅有 `getReportModules()`→`/reports/modules`、`generateReport()`→`/reports/export`。**无模板 API**。
- `ReportExportDrawer.vue`：表单状态 `reportName / reportTimeField / reportRangeMode / reportPresetDays / reportCustomRange / selectedModules / moduleParams` —— **全部可由 `ReportExportRequest` 直接映射，天然适合“保存/加载模板”回填**。
- `Dashboard.vue`：单一按钮 `v-if="can('reports:export')"` 打开抽屉；**无模板管理入口**。

---

## 2. 模板能力需求分析

**收益**
- 重复导出提效：管理员固化“周报/日报”固定模块组合与参数，免每次重选。
- 运营能力：统一口径模板，保证不同人导出结果一致。
- **Phase 5（邮件/定时）前置基础**：定时任务本质上 = 一个模板 + cron + 收件人。

**成本**
- 数据模型：`report_templates` 表 + 1 个 Alembic 迁移。
- 权限：新增 `reports:manage`（迁移播种）+ 角色授权。
- 前端：保存/加载/删除 UI + 调用新 API。
- API：4 个 CRUD 端点 + 测试。
- 测试：CRUD + 权限 + 回填一致性 + 模块失效降级。

**结论**：**值得现在实现最小可用版（Phase 4-A）**。理由：① 导出配置已 100% 可序列化（ReportConfig/ExportRequest），模板无需任何 schema 重构；② 最重的工作（模块注册表、params 元数据、顺序、COALESCE、时间口径）已完成；③ 属**纯增量变更**（新表，不动既有逻辑、不动 `report_records`、不动 export API），风险低；④ 直接解锁 Phase 5。

---

## 3. 数据库设计建议

### 3.1 新增 `report_templates`（建议表结构）
沿用 `report_records.config_json` 的同一序列化范式，最一致、改动最小：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | Integer PK | 主键 |
| name | String(128) | 模板名称（唯一约束建议加 owner 维度） |
| description | String(255) | 说明 |
| owner_id | Integer FK→users.id | 创建人；用于“个人模板” |
| config_json | JSONB | **完整导出配置**（= ReportExportRequest 去掉 delivery/recipients），含 time_field / range / modules（含 params） |
| is_public | Boolean | 是否管理员发布的全局模板（可见给所有 `reports:export` 用户） |
| created_at / updated_at | DateTime | 时间戳 |

> 与 Prompt 建议字段的对应：`modules_json` → `config_json.modules`；`default_time_field` → `config_json.time_field`；`default_range_config` → `config_json.range_*`。**推荐用单一 `config_json` 而非拆分三列**，理由：与 `_do_export` 已落库的 `config_json` 完全一致，回填/复用零转换；避免字段冗余与不同步。
>
> 可选补充：若需“使用次数”统计，加 `use_count Integer default 0`（Phase 4-B）。

### 3.2 `report_records` 关联（可选、推荐但非必须）
- 加可空列 `template_id Integer FK→report_templates.id`（**不设 ON DELETE CASCADE**，模板删除后审计记录保留）。用于“追溯本次导出来自哪个模板 / 一键用同模板重生成”。
- 历史 `report_records`（Phase 1~3）`template_id` 为 NULL，零影响。

### 3.3 迁移原则
- 新建迁移（如 `p27_report_templates`），**仅 ADD**，不 ALTER 现存表；`reports:manage` 权限幂等插入（参考 p26 写法）；将 `reports:manage` 授予 `admin`/超管角色（参考 p26 授予 analyst 的写法）。
- 不触动 `p26_report_records` 既有结构。

---

## 4. API 设计建议

**原则（Prompt 明确要求）：保持 `POST /api/reports/export` 不变；新增独立模板 API。**

新增 4 个端点（前缀 `/api/reports`，统一 `Depends(get_current_user)`）：

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/templates` | `reports:export`（或 `reports:manage`） | 列出当前用户可见模板 = 个人（owner_id=me）+ 全局（is_public=true） |
| POST | `/templates` | `reports:manage` | 保存当前抽屉配置为新模板，`config_json` = 抽屉状态序列化 |
| PUT | `/templates/{id}` | `reports:manage`（owner 或超管） | 更新模板 |
| DELETE | `/templates/{id}` | `reports:manage`（owner 或超管） | 删除模板（硬删即可；若加 is_public 用软删更稳） |

**关键决策：模板“使用”不新增导出端点。**
- 前端“用模板导出” = 加载模板 `config_json` 回填抽屉 → 用户点导出 → 仍走既有 `POST /api/reports/export`。
- 这样 export API 契约零变化，Phase 3 全部测试继续有效。
- （可选增强 Phase 4-B：新增 `POST /api/reports/templates/{id}/export` 直接按模板导出，但属非必需，且会扩展 export 入口；建议搁置。）

**Schema 新增（仅后端，不影响 export）：**
- `ReportTemplateCreate`：`name, description, config_json, is_public`
- `ReportTemplateUpdate`：`name?, description?, config_json?, is_public?`
- `ReportTemplateResponse`：`id, name, description, owner_id, owner_name, config_json, is_public, created_at, updated_at, can_edit(bool)`

---

## 5. 前端交互建议

### 5.1 当前表单状态适合回填（已确认）
`ReportExportDrawer.vue` 的 `reportName/reportTimeField/reportRangeMode/reportPresetDays/reportCustomRange/selectedModules/moduleParams` 与 `ReportExportRequest` 1:1 对应。
- **保存模板**：抽屉内新增“保存为模板”按钮 → 收集当前状态 → `POST /templates`。
- **加载模板**：抽屉内新增“模板”下拉/列表 → 选中 → 将 `config_json` 回填上述状态。
- **删除模板**：列表项旁删除（仅自己/超管可见可删）。

### 5.2 入口位置建议（决策点）
- **Phase 4-A（推荐）**：模板能力**内嵌于导出抽屉内**（下拉+保存按钮），不在 Dashboard 新增独立入口。改动最小、契合“导出时才需模板”的动线。
- **Phase 4-B**：在 Dashboard 新增“模板管理”独立入口（`v-if="can('reports:manage')"`），做增删改查/预览/可见性管理。

### 5.3 前端 API（`report.ts` 扩展，不破坏现有）
新增：`getTemplates()`→`/templates`、`createTemplate(payload)`→`POST`、`updateTemplate(id,payload)`→`PUT`、`deleteTemplate(id)`→`DELETE`。现有 `getReportModules`/`generateReport` 不变。

---

## 6. 权限设计建议

### 方案 A：继续复用 `reports:export`
- 模板保存/加载/删除均用 `reports:export` 鉴权。
- 优点：零新增权限、零迁移。缺点：与“导出”语义混用；无法区分“能用模板”与“能管理模板”；与 Phase 1 既定决策（`reports:manage 留到模板/定时阶段`）相悖。

### 方案 B（推荐）：新增 `reports:manage`
- `reports:manage` 用于模板**创建/更新/删除**；`reports:export` 仍仅用于**使用/导出**；`GET /templates` 可见性可用 `reports:export`（会导出的人才能看到可用模板）。
- 理由：① 与 Phase 1 决策完全一致（“reports:manage 留到模板/定时阶段”）——现在正是该阶段；② 权限语义清晰，便于后续 Phase 5 定时任务复用同一 `reports:manage`；③ `viewer` 仍无 `reports:export`→无模板入口，权限隔离链不破。
- **实施**：新迁移幂等插入 `('reports:manage','管理报告模板','reports','manage','报告','保存/编辑/删除报告模板')`；授予 `admin`/超管角色（参考 p26 给 analyst 授 `reports:export` 的写法）。现有 `reports:write` 保留不动（技术债登记，如既往）。

**推荐：方案 B。**

---

## 7. 是否进入 Phase 4 实施

**建议：进入，但仅实施 Phase 4-A（最小可用模板能力）。** 风险低、纯增量、价值明确、解锁 Phase 5。Phase 4-B/C 留待确认后再分阶段。

---

## 8. 推荐实施范围

### Phase 4-A（最小可用，建议本次实施）
1. 迁移 `p27_report_templates`：建 `report_templates` 表（含 `config_json`/`is_public`/`owner_id`）；幂等插入 `reports:manage` 并授予超管；可选加 `report_records.template_id`（可空）。
2. Schema：新增 `ReportTemplateCreate/Update/Response`。
3. API：新增 `GET/POST/PUT/DELETE /api/reports/templates`（权限见 §6 方案 B）。
4. 服务层：模板 CRUD（校验 config_json 中 modules 均为已知 key，借用 `expand_module_keys`/`MODULE_MAP`）。
5. 前端：抽屉内“保存为模板”+“模板加载”下拉（内嵌，不新增 Dashboard 入口）；`report.ts` 加 4 个函数。
6. 测试：模板 CRUD、权限（viewer 无 manage→403 / analyst 有 export 可见 / 超管可删）、回填后导出与直接导出 PDF 字节一致、模块失效降级。

### Phase 4-B（增强，待确认）
- 独立“模板管理”入口（Dashboard，`reports:manage`）；个人 vs 全局模板可见性；重命名/软删；使用次数；模板预览。

### Phase 4-C（邮件/定时前置，待确认，仅挂载点不实现能力）
- `report_records.template_id` 关联（已在 4-A 可选）；新增 `report_tasks` 表（`template_id` FK + cron + recipients + enabled）**仅建表与挂载点**，不实现调度器/邮件；export 支持按 `template_id` 直接导出（可选）。为 Phase 5 铺路。

---

## 9. 不建议现在实现的能力

- ❌ 邮件发送（`delivery=email`）：本阶段仍固定 `download`；SMTP/`mail_service` 留 Phase 5。
- ❌ 定时调度器：仅建 `report_tasks` 挂载点（4-C），不实现 cron 执行。
- ❌ 模板“共享给指定角色/用户”的细粒度 ACL：4-A 仅做“个人 + 全局(is_public)”两级，足够；细粒度留后续。
- ❌ 模板版本历史：不实现。
- ❌ 改动 `report_records` 既有字段或 `export` API 契约：保持兼容。
- ❌ 改动 `dashboard_service`、风险模型、Event 聚合：红线不动。

---

## 10. 风险检查与缓解

| 风险 | 说明 | 缓解 |
|---|---|---|
| 模板 JSON 绑定模块内部实现 | 模板存 `{key, params}`，若未来 `data_fn`/`render_fn` 改名不影响（key 稳定）；但若 **key 被删除/改名** | 加载时 `_do_export` 已对未知 key 返回 400；建议新增 `normalize_template()`：渲染前用 `MODULE_MAP` 校验，丢弃未知 key、对 params 按当前元数据 clamp(min/max)，记日志；**历史 `report_records` 不受影响**（其 config_json 为独立快照） |
| 历史模板在模块删除后 | 同上 | 优雅降级：丢未知模块、保留已知，提示用户“模板含已停用模块” |
| 普通用户可见性 | 是否所有人看全部模板？ | 采用“个人(owner_id=me) + 全局(is_public)”两级；非 owner 仅可使用不可编辑/删除全局模板 |
| report_records 关联 | 是否关联 template_id | 推荐可空 `template_id`（无 CASCADE），仅作追溯；历史记录 NULL，零影响 |
| 权限扩散 | 误给 viewer 模板管理能力 | 严格按方案 B：`reports:manage` 仅授超管；viewer 无 `reports:export`→无模板入口 |

---

## 结论

- 当前架构**已具备模板化所需的全部前置能力**（可序列化模块注册表、params 元数据、顺序、配置快照落库），实现模板是**低风险纯增量**工作。
- **`reports:manage` 当前不存在**，需本次新增（方案 B）。
- **建议进入 Phase 4-A**：新增 `report_templates` 表 + 4 个模板 CRUD 端点 + 抽屉内保存/加载 + `reports:manage` 权限；保持 `export` API 与 `report_records` 既有结构不变。
- **不进入代码修改阶段**（按 Prompt 要求）。等待确认后，再给出 Phase 4-A 的确认清单与实施。

---

*审计依据文件（均仅读取）：*
- `backend/app/services/report_service.py`（`REPORT_MODULES` L945、`ReportConfig` L335、`MODULE_MAP`/`DEFAULT_MODULE_KEYS` L1070、`expand_module_keys` L1082）
- `backend/app/api/reports.py`（全文；`_do_export` L142、`/export` L225）
- `backend/app/schemas/report.py`（全文；`ReportExportRequest` L116、`ReportModuleDef` L73）
- `backend/app/models/report_record.py`、`user.py`、`role.py`、`permission.py`
- 权限播种：`alembic/versions/rbac10001.py`、`p2_rbac.py`、`p26_report_records.py`
- 前端：`frontend/src/api/report.ts`、`components/report/ReportExportDrawer.vue`、`views/Dashboard.vue`
