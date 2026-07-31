# Phase Report-2-Phase1 模块化报告实施报告

- 实施时间：2026-07-30 22:16 ~ 22:32
- 实施范围：后端报告模块化重构（A~E 五项），**零数据库变更、零前端变更**
- 生产库身份门禁：`backend/scripts/db_identity_check.py` → **VERIFIED（exit 0）**
  - `opinion_db @127.0.0.1:5432`，system_identifier `7663057120701798896`，alembic `p26_report_records`，opinions 904 行
- 结论：**Phase 1 全部完成，测试 24/24 通过，生产库只读真实渲染 12/12 模块无失败**

---

## 一、修改文件清单

| 文件 | 类型 | 变更量 | 说明 |
|---|---|---:|---|
| `backend/app/services/report_service.py` | 改造 | +942 / −? | 时间口径统一、模块注册表扩展至 12、失败隔离、别名展开、章节编号 |
| `backend/app/api/reports.py` | 改造 | +245 | 新增 `POST /reports/export`；`/generate` 转薄适配层并标 deprecated；`/modules` 契约扩展 |
| `backend/app/schemas/report.py` | 改造 | +82 | 新增 `ReportExportRequest` / `ReportModuleSelection` / `ReportModuleParamDef`；`ReportModuleDef` 扩展 |
| `backend/tests/test_report_phase2_p1.py` | 新增 | 19 用例 | Phase 1 全部 8 项测试要求 + 契约/参数/别名补充用例 |

合计 3 个源文件改造 + 1 个测试文件新增，**1239 插入 / 30 删除**。

**未修改（明确遵守禁止事项）**：
- `backend/app/services/dashboard_service.py` —— 零改动，默认查询逻辑与 17 处 `created_at` 口径原样保留
- 任何模型 / 迁移 / 权限播种 / `.env` / `config.py`
- 任何前端文件（Phase 3 范围）
- 旧接口 `/reports/overview`、`/reports/overview/pdf`、`/reports/generate` 均保留可用
- `reports:write` 保留未删（技术债已登记）

---

## 二、数据库变化

**无。本阶段零数据库变更。**

| 项 | 状态 |
|---|---|
| 新增迁移文件 | 无 |
| alembic head | `p26_report_records`（保持不变，代码与生产库一致） |
| 新增表 / 字段 | 无（12 个模块全部复用既有列：`risk_category`、`alert_records.status/risk_level`、`opinions.keywords` 等） |
| 新增权限 | 无（`reports:manage` 按决策留到 Phase 4） |
| 业务数据写入 | 无。仅 `report_records` 在导出时按既有逻辑追加审计行（Phase Report-1.1 已有行为，未改语义） |

生产库本阶段**未执行任何 DDL/DML**，全部验证为只读 SELECT。

---

## 三、API 变化

### 1. `GET /api/reports/modules`（权限 `reports:read`，契约向后兼容扩展）

响应结构由 `{key,title,description}` 扩展为：

```json
{
  "modules": [
    {"key":"overview_kpi","name":"总体态势 KPI","title":"总体态势",
     "description":"...","default_enabled":true,"params":[]},
    {"key":"opinion_list","name":"舆情明细清单","title":"舆情明细清单",
     "description":"...","default_enabled":false,
     "params":[{"key":"limit","label":"展示条数","type":"int","default":50,"min":1,"max":200},
               {"key":"min_risk","label":"最低风险分","type":"int","default":0,"min":0,"max":100}]}
  ],
  "default_modules": ["overview_kpi","trend","sentiment","top_risky","events",
                      "source_dist","region_dist","keyword_dist","conclusion"]
}
```

- **只增字段不改字段**，Phase Report-1.1 已上线前端（读 `key/title/description`）零破坏
- `distribution` **不在清单中展示**

### 2. `POST /api/reports/export`（新增，权限 `reports:export`）

```json
{
  "name": "舆情监测报告",
  "time_field": "created_at | publish_time",
  "range_type": "last_n_days | custom",
  "range_days": 7,
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "modules": ["overview_kpi", {"key":"top_risky","params":{"limit":5}}],
  "delivery": "download"
}
```

- `modules` 同时支持「纯 key 字符串」与「带参数对象」两种写法，**提交顺序即 PDF 章节顺序**
- `delivery != download` → 400「当前仅支持 delivery=download，邮件投递尚未开放」（Phase 5 挂载点）
- `range_type=custom` 且缺 `start_date`/`end_date` → 400
- 空模块 → 400；未知模块 → 400
- 响应：`application/pdf`，`Content-Disposition` 同时带 ASCII 与 RFC5987 UTF-8 文件名
- **新增响应头 `X-Report-Failed-Modules`**：存在被隔离的失败模块时返回其 key 列表（供 Phase 3 前端提示），不影响下载本身

### 3. `POST /api/reports/generate`（保留，标记 `deprecated=True`）

- 不删除、不破坏、签名与响应完全不变
- 内部改为调用与 `/export` 完全相同的 `_do_export()` 执行体
- 审计 `details.entry = "generate(deprecated)"`，便于统计旧入口调用量以决定下线时机

### 4. `GET /api/reports/overview` / `overview/pdf`（Legacy，零改动）

---

## 四、Phase 1 实施范围逐项对照

### A. 模块注册表增强 ✅

未重写，增量扩展为：

```
{key, name, title, description, data_fn, render_fn, default_enabled, params}
```

`title` 保留原值；`data_fn` 签名由 `(db, ws, we, col)` 增量为 `(db, ws, we, col, params=None)`（带默认值，向后兼容）。

### B. 12 个模块 ✅

| # | key | 名称 | 默认启用 | 参数 | 数据来源 |
|---:|---|---|:--:|---|---|
| 1 | `overview_kpi` | 总体态势 KPI | ✅ | — | opinions / events |
| 2 | `trend` | 舆情趋势 | ✅ | — | opinions 按日 |
| 3 | `sentiment` | 情感分布 | ✅ | — | opinions.sentiment |
| 4 | `top_risky` | 高风险舆情 TOP | ✅ | limit 1–50 | opinions + regions |
| 5 | `events` | 重点事件 | ✅ | limit 1–50 | events |
| 6 | `source_dist` | 来源分布 | ✅ | limit 1–30 | opinions.source（含占比） |
| 7 | `region_dist` | 地区分布 | ✅ | limit 1–30 | 省级上卷（复用 `_rollup_provinces`） |
| 8 | `keyword_dist` | 热点关键词 | ✅ | limit 1–50 | opinions.keywords |
| 9 | `risk_category` | 风险分类分布 | ⬜ | — | opinions.risk_category（NULL→未分类） |
| 10 | `alert_summary` | 预警处置概览 | ⬜ | — | alert_records（状态分布 + 闭环率） |
| 11 | `opinion_list` | 舆情明细清单 | ⬜ | limit 1–200 / min_risk 0–100 | opinions + regions |
| 12 | `conclusion` | 结论建议 | ✅ | — | 窗口统计自动成文（无外部模型） |

- 原 `distribution` 已按 6/7/8 拆分，**未新增任何业务表 / 业务字段**
- 章节序号自动生成并中文化（一、二、…十二、）

### C. 单模块失败隔离 ✅

双层隔离：

1. **取数层**（`build_report`）：每模块独立 `try/except` → `logger.exception` → **`db.rollback()`**（关键：PG 语句失败后事务进入 aborted 状态，不回滚会导致后续所有模块连锁失败）→ 该模块标 `error`，其余继续
2. **渲染层**（`render_report_pdf`）：渲染写入**独立子 flow**，成功后才并入主 flow；失败则替换为红色「该模块生成失败」段落，避免半成品 platypus 元素污染 `doc.build`

`meta.failed_modules` 汇总失败 key；API 层记入审计 `details.failed_modules`、`report_records.config_json.failed_modules` 与响应头。**任何单模块异常都不会返回 500。**

### D. 时间服务重构 ✅

```python
TIME_FIELD_LABELS = {
    "created_at":   "采集时间",
    "publish_time": "发布时间（缺失回退采集时间）",
}

def _time_column(time_field):
    if time_field == "publish_time":
        return func.coalesce(Opinion.publish_time, Opinion.created_at)
    return Opinion.created_at

def _time_filter(col, ws, we):           # 本地日期语义，无任何时区转换
    return and_(cast(col, Date) >= ws, cast(col, Date) <= we)
```

- 过滤 / 排序 / 分组 / 展示**全部统一走 `_time_column`**（`opinion_list` 的 `order_by(col.desc())`、`trend` 的 `group_by(cast(col,Date))` 亦同）
- 保留 `_window_clause` 作为等价别名，Phase Report-1 内部调用零改动
- `build_report(time_field, start_date, end_date, days, module_params)` 全部支持；默认 `created_at` + 近 N 天，**默认行为完全不变**
- PDF 页眉展示当前口径：`统计口径：发布时间（缺失回退采集时间） | 统计区间：2026-07-01 ~ 2026-07-30 | 生成时间：…`

**缓存污染防护**：报告链路（`build_report` 及 12 个 `_m_*`）**不经过任何缓存**，直接 SELECT，因此不存在 `dash:*` 缓存 key 串数据风险。`dashboard_service` 的缓存与默认逻辑本阶段零改动；其 `time_field/start_date/end_date` 参数化与缓存 key 扩展属 Phase 2 范围。

### E. 新接口 ✅

见「三、API 变化」。

---

## 五、测试结果

### 5.1 Phase 1 新增测试（`tests/test_report_phase2_p1.py`，19 用例）

```
DATABASE_URL=...:5433/opinion_test  DB_IDENTITY_CHECK=off  pytest -v
19 passed in 2.35s
```

时间口径样本（本地 naive 直写，测试结束按 id 精确删除，不动既有数据）：

| 样本 | created_at | publish_time | 采集口径归属 | 发布口径归属 |
|---|---|---|---|---|
| A | T 03:00 | **NULL** | T | **T（回退 created_at）** |
| B | T 12:00 | Y 23:30 | T | **Y（用 publish_time）** |
| C | T 23:30 | T 07:00 | T | T |

| # | 测试要求 | 用例 | 结果 |
|---:|---|---|:--:|
| 1 | created_at 过滤正确 | `test_created_at_filter_and_early_morning_local_attribution` | ✅ |
| 2 | publish_time 有值时使用 publish_time | `test_publish_time_used_when_present_and_fallback_when_null`（B 落 Y 不落 T） | ✅ |
| 3 | publish_time NULL 回退 created_at | 同上（A 落 T）+ `test_no_null_publish_time_data_is_dropped`（宽窗口计数 == 全表行数，零丢失） | ✅ |
| 4 | **00:00–08:00 本地归属正确** | A(03:00)、C 发布(07:00) 均归属当日；并**显式反证**「若误做 −8h UTC 转换会被划到前一日」 | ✅ |
| 5 | 模块任意组合生成 PDF | `test_all_modules_pdf`(12/12)、`test_subset_and_reordered_modules_pdf`（乱序=提交序）、`test_module_params_applied` | ✅ |
| 6 | 单模块异常不导致整体失败 | `test_data_fn_failure_isolated`、`test_render_fn_failure_isolated`、`test_export_api_not_500_when_module_fails`（200 + `X-Report-Failed-Modules: trend`） | ✅ |
| 7 | 旧 `/reports/generate` 仍可用 | `test_legacy_generate_still_works`（含历史 `distribution` key，自动展开） | ✅ |
| 8 | viewer 调 export → 403 | `test_viewer_export_forbidden`（同时验证 `/modules` 仍 200） | ✅ |
| + | 注册表 12 项字段完备 / 别名展开保序去重 / `/modules` 契约 / custom 区间校验 / 空与未知模块 400 / email 拒绝 | 6 条补充用例 | ✅ |

### 5.2 回归测试

```
pytest tests/test_report_export.py tests/test_report_phase2_p1.py
24 passed in 2.79s
```

Phase Report-1.1 的 5 条旧用例**全部保持通过**（其中 `distribution` 用例现走别名展开路径，验证了历史 `config_json` 可复现）。

### 5.3 全量套件基线说明

`pytest tests/` → 299 passed / 37 failed / 62 errors。失败**全部为既有基线噪声，与本次改动无关**：

- 主因 `bocha_leads_opinion_id_fkey` 外键阻塞 opinions 清理（源自 p25 bocha 特性，缺 ON DELETE CASCADE），影响 `test_dashboard` / `test_event_*` / `test_events_aggregator_v2` 等
- 证据：① 报告相关测试 0 失败；② `test_dashboard.py` 单独运行同样报错，与执行顺序无关；③ 按字母序 `test_dashboard` 早于 `test_report_*` 执行；④ 本次仅改 3 个 report 源文件，未触碰任何被影响模块

> 建议登记为独立技术债（测试库外键级联缺失），不在 Phase Report-2 范围内处理。

### 5.4 生产库真实数据只读验证（未写库）

门禁 VERIFIED 后，直接调用 `build_report + render_report_pdf`（纯 SELECT）：

| 口径 | 区间 | 失败模块 | total | high_risk | 风险率 | PDF |
|---|---|---|---:|---:|---:|---:|
| 采集时间 | 2026-07-01 ~ 07-30 | **无** | 904 | 32 | 3.5% | 323,351 B |
| 发布时间（缺失回退采集时间） | 同上 | **无** | 827 | 22 | 2.7% | 330,337 B |

- 12/12 模块全部成功，`failed_modules = []`
- 风险分类：其他 846 / 安全事故 41 / 政治敏感 9 / 社会治安 8
- 预警概览：9 条全部待处置，闭环率 0.0%
- 结论建议自动成文正常
- 两种口径差 77 条 = 发布时间落在 7/1 之前的历史存档（Phase 0 已预判），**非 NULL 丢弃**（宽窗口计数 == 全表 904，已由测试断言）

样例产物：`_phase2_p1_sample_created_at.pdf`、`_phase2_p1_sample_publish_time.pdf`

---

## 六、与 Phase 0 决策的对应关系

| Phase 0 决策 | 落地位置 | 状态 |
|---|---|:--:|
| **方案 A**：本地时间语义，不做「本地日期 → UTC」转换 | `_time_filter()` 仅用 `cast(col, Date)` 比较；全链路无 `timezone`/`astimezone`/`utcoffset` 调用 | ✅ |
| 与 `dashboard_service` 现有 `cast(Date)` 口径一致 | 同源写法；`_rollup_provinces` 直接复用 | ✅ |
| 不修改时间字段类型 / 不迁移历史数据 | 零 DDL、零 DML | ✅ |
| **`COALESCE(publish_time, created_at)`**（NULL 占比 22.90% ≥ 5%） | `_time_column("publish_time")` | ✅ |
| 禁止严格过滤 / 丢弃无发布时间数据 | 由 `test_no_null_publish_time_data_is_dropped` 断言全表零丢失 | ✅ |
| 发布口径标记「发布时间（缺失回退采集时间）」、采集标记「采集时间」，PDF 展示口径 | `TIME_FIELD_LABELS` + PDF 页眉副标题 | ✅ |
| `POST /reports/export` 为正式入口，`/generate` 转薄适配层并 deprecated | `_do_export()` 共用执行体 | ✅ |
| `distribution` 不展示但请求自动展开为三项 | `MODULE_ALIASES` + `expand_module_keys()`（保序去重） | ✅ |
| `reports:read` 看清单、`reports:export` 导出；`reports:manage` 留到 Phase 4；`reports:write` 不删 | 权限装饰器未变，无权限播种 | ✅ |
| P0 阻塞（时区口径相反）已澄清 | 按方案 A 实施，00:00–08:00 归属由测试**正向 + 反证**双重覆盖 | ✅ 已解除 |

---

## 七、未实现能力清单（后续阶段）

| 能力 | 计划阶段 | 当前状态 / 预留挂载点 |
|---|---|---|
| `dashboard_service` 时间字段参数化（`_time_col`/`_time_filter` + 缓存 key 纳入 time_field/start/end） | **Phase 2** | 本阶段零改动；报告链路不走缓存，无污染风险 |
| 前端报告抽屉（`ReportExportDrawer` 接 `/export`、参数表单、Blob 错误解析、模块勾选排序） | **Phase 3** | 后端契约已就绪；`params` 元数据已可驱动表单；现有前端仍走 `/generate`，不受影响 |
| 报告模板 `report_templates` + `reports:manage` | **Phase 4** | 未建表、未建权限 |
| 邮件能力（`mail_service.py`、SMTP\_\* 配置、`delivery=email`、`/reports/mail-test`） | **Phase 5** | `ReportExportRequest.delivery/recipients` 字段已预留；`delivery=email` 当前显式 400 |
| 定时报告 `report_tasks` + `report_dispatch`（IntervalTrigger 1min + FOR UPDATE SKIP LOCKED） | **Phase 6** | 未实现 |
| 报告文件落盘 `REPORT_STORAGE_DIR` / 历史报告下载 | Phase 5–6 | 未实现，`report_records` 仍不存 PDF |
| 遗留 `reports:write` 权限清理 | 待定 | 按决策保留，技术债已登记（无任何代码引用） |
| 测试库 `bocha_leads` 外键级联缺失 | 待定 | 新发现技术债，非本阶段范围 |

---

## 八、生产影响与回滚

**当前生产影响：零。** 后端源码已更新但**未重启 uvicorn**，线上仍运行改造前代码；数据库无任何变更；前端产物未重建。

按执行规则，生产部署（重启 uvicorn + 前端构建）留待 Phase 7 统一收口，或在你确认后单独执行。

**回滚方案（若需要）**：

```bash
git checkout -- backend/app/services/report_service.py \
                backend/app/api/reports.py \
                backend/app/schemas/report.py
rm backend/tests/test_report_phase2_p1.py
# 无需回滚数据库（本阶段零 DDL/DML），无需 alembic downgrade
```

回滚粒度为纯代码级，风险极低。
