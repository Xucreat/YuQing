# Phase Report-2-P0 时间口径审计报告

- 审计时间：2026-07-30 22:05 ~ 22:10（Asia/Shanghai）
- 审计范围：只读。**未修改任何代码、数据库、配置**
- 数据库身份门禁：`backend/scripts/db_identity_check.py` → **[DATABASE IDENTITY: VERIFIED]，退出码 0**
  - Host/Port/DB：`127.0.0.1:5432 / opinion_db`
  - system_identifier：`7663057120701798896`（与期望一致）
  - opinions 行数：904（≥100 阈值）

> ⚠️ 本次审计发现 **1 项 P0 级架构冲突**（Phase 2 时区转换设计与实际存储口径相反），已单独输出《阻塞问题审计报告》。**Phase 1 之后的实施暂停，等待确认。**

---

## 一、后端现状审计

### 1.1 Alembic 迁移

| 项 | 值 |
|---|---|
| 当前 head（代码 + 生产库一致） | `p26_report_records` |
| 链路尾部 | `p24_bazhou_dynamic_source` → `p25_bocha_ai_search` → `p26_report_records` |
| report 相关 migration | 仅 `p26_report_records.py`（Phase Report-1.1 产出） |
| `p26` 内容 | 建 `report_records` 表；播种 `reports:export` 权限；授权 analyst |
| 生产库已存在的 report/task/template 表 | 仅 `report_records`（4 行）。**无** `report_templates`、**无** `report_tasks` |

### 1.2 `report_service.py` 当前结构

已在 Phase Report-1 完成第一轮模块化，**并非"固定 6 章节硬编码"**，现状为：

```
legacy（保留）        : build_overview(db, days) / render_pdf(data) / _grid_style()
配置对象              : @dataclass ReportConfig(report_name, time_field, start_date, end_date, days, module_keys)
时间辅助              : _time_column() / _window_clause() / _resolve_window()
取数函数 _m_*         : 6 个
渲染函数 _r_*         : 6 个
注册表 REPORT_MODULES : 6 项，结构 {key, title, description, data_fn, render_fn}
派生                  : MODULE_MAP / DEFAULT_MODULE_KEYS
编排                  : build_report(db, cfg) / render_report_pdf(report)
```

**与 Phase 1 目标的差距**：

| 目标要求 | 现状 | 差距 |
|---|---|---|
| 12 个模块 | 6 个 | 缺 8 个；且现有 `distribution` 需拆为 `source_dist`/`region_dist`/`keyword_dist` |
| 注册项含 `name` | 用的是 `title` | 字段命名不一致 |
| 注册项含 `default_enabled` | 无 | 需新增（现在全量默认开启） |
| 注册项含 `params` | 无 | 需新增（如 TOP N、明细条数上限） |
| 章节自动编号 | ✅ 已有（`f"{i}、{title}"`） | 无 |
| 用户顺序决定章节顺序 | ✅ 已有（按 `module_keys` 迭代） | 无 |
| **单模块失败隔离** | ❌ **无 try/except，任一模块抛错整份 PDF 失败** | **必须补** |

现有 12 模块所需数据字段**全部已存在**，无需新增业务列：

| 模块 | 依赖字段 | 是否就绪 |
|---|---|---|
| overview_kpi / trend / sentiment / top_risky | opinions.* | ✅ |
| events | events.title/risk_level/opinion_count/first_time | ✅ |
| source_dist | opinions.source | ✅ |
| region_dist | opinions.region_id + regions（`_rollup_provinces`） | ✅ |
| keyword_dist | opinions.keywords（TEXT 逗号分隔） | ✅ |
| risk_category | opinions.risk_category（Phase2-B.2 已加） | ✅ |
| alert_summary | alert_records.status/risk_level/handled_at | ✅ |
| opinion_list | opinions.* | ✅ |
| conclusion | 由前序模块结果派生，无需查库 | ✅ |

### 1.3 `reports.py` 当前接口

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| GET | `/api/reports/overview` | `reports:read` | Legacy JSON |
| GET | `/api/reports/overview/pdf` | `reports:export` | Legacy PDF，**需保留** |
| GET | `/api/reports/modules` | `reports:read` | 返回 `{modules[{key,title,description}], default_modules[]}` |
| POST | `/api/reports/generate` | `reports:export` | **Phase Report-1.1 刚上线，前端 Drawer 正在使用** |

两个导出端点均写 `user_operation_logs`（审计）+ `report_records`（成功/失败）。

**与 Phase 1 目标的差距**：目标要求新增 `POST /api/reports/export`。现存 `POST /api/reports/generate` 语义完全重叠且已被前端调用。建议见"五、建议"。

### 1.4 `dashboard_service.py` 时间过滤逻辑

- **完全硬编码 `Opinion.created_at`**，全文 17 处 `cast(Opinion.created_at, Date)`，无 `publish_time` 分支。
- 窗口计算统一为：`today = db.scalar(select(func.current_date()))` → `window_start = today - timedelta(days=days-1)`，即**闭区间 [today-days+1, today] 的"日期"比较**，不涉及 datetime 边界。
- 口径分三类且**刻意不统一**（文件头注释明确说明）：
  - 累计指标：`total`、`event_count`（不受 days 影响）
  - 当日指标：`today`（`cast(created_at,Date) == current_date()`）
  - 窗口指标：`trend`、`sentiments`、`sources`、`regions`、`keywords`、`risk_distribution`、`alert_stats`
- 存在 `dash:*` 内存缓存 key（`get_dashboard_stats` / `get_kpi_trends` / `get_hot_keywords` / `get_risk_distribution`）。**新增 time_field / start_date / end_date 后缓存 key 必须纳入这些维度，否则会串数据。**

### 1.5 Opinion 时间字段

| 字段 | 模型定义 | 库列类型 | 可空 | 默认 |
|---|---|---|---|---|
| `created_at` | `DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)` | `timestamp without time zone` | 否 | 应用层默认 |
| `publish_time` | `DateTime, nullable=True` | `timestamp without time zone` | **是** | 无（采集器解析） |
| `analysis_time` | `DateTime, nullable=True` | `timestamp without time zone` | 是 | 无 |

---

## 二、时间口径判定（核心结论）

### 2.1 `publish_time` 空值比例

执行 SQL（只读）：

```sql
SELECT count(*) total,
       count(*) FILTER (WHERE publish_time IS NULL) null_publish
FROM opinions;
```

结果：

| total | null_publish | **NULL 占比** |
|---:|---:|---:|
| 904 | 207 | **22.90 %** |

> `analysis_time` NULL 占比 0.00%（904/904 已分析）。

### 2.2 判定

**22.90 % ≥ 5 % → 命中路线 B。**

### ✅ 采纳口径：`COALESCE(publish_time, created_at)`

发布时间口径下，`publish_time` 为空的记录**回退到 `created_at`**，而不是被丢弃。

判定依据补充：

- 若走路线 A（严格过滤 NULL），发布时间口径会**直接丢失 22.9 % 的舆情**，KPI 总量与采集时间口径差出近四分之一，报告可信度不可接受。
- 数据侧无反证：`publish_time > created_at`（未来发布时间）**0 条**，说明现有 publish_time 无脏数据倒挂。
- `publish_time` 分布范围 `2013-06-26 ~ 2026-07-30`，其中早于 `created_at - 90d` 的有 **23 条**（历史存档类内容）。这类记录在"近 N 天发布时间"窗口下自然落窗外，属**预期行为**，不是缺陷。

### 2.3 实施约束（Phase 1 / Phase 2 共同遵守）

1. 发布时间口径的时间列统一定义为
   `COALESCE(opinions.publish_time, opinions.created_at)`；采集时间口径仍为 `opinions.created_at`。
2. 该表达式需同时用于 **过滤（WHERE）**、**分组（GROUP BY 日期）**、**排序**、**明细展示列**，避免"过滤用 A、展示用 B"的口径撕裂。
3. PDF 报告页眉必须打印口径标签：`发布时间(缺失回退采集时间)` / `采集时间`，让阅读者可追溯。
4. `COALESCE(publish_time, created_at)` 无法命中单列索引。当前 904 行、预期年内 <10 万行，全表扫描代价可忽略；**本阶段不建表达式索引**，留作后续观测项。

---

## 三、RBAC 权限现状

### 3.1 reports 相关权限（permissions 表）

| id | code | name | resource | action | group |
|---:|---|---|---|---|---|
| 23 | `reports:read` | 查看报告 | reports | read | 报告 |
| 24 | `reports:write` | 导出报告 | reports | write | 报告 |
| 27 | `reports:export` | 导出报告 | reports | export | 报告 |

- ✅ `reports:read` 存在
- ✅ `reports:export` 存在（p26 播种）
- ❌ `reports:manage` **不存在**（Phase 4 需新增）
- ⚠️ **历史遗留**：`reports:write`（id=24）与 `reports:export` 语义重复，**当前无任何代码引用**，仅授予了 analyst。属技术债，本阶段**不删除**（避免动既有权限数据），仅登记。

> `permissions` 表实际列为 `code / name / resource / action / description / group / created_at`，**没有 `module` 列**——后续写迁移播种权限时按此结构。

### 3.2 角色

| id | name | display_name | code | is_system |
|---:|---|---|---|---|
| 1 | admin | 管理员 | admin | true |
| 2 | analyst | 分析员 | analyst | true |
| 3 | viewer | 观察员 | viewer | true |

### 3.3 角色 × reports 权限矩阵

| 角色 | reports:read | reports:write(遗留) | reports:export | reports:manage |
|---|:---:|:---:|:---:|:---:|
| **admin** | （超管走 `*` 通配，不落表） | — | （`*`） | （`*`） |
| **analyst** | ✅ | ✅ | ✅ | ❌ 待新增 |
| **viewer** | ✅ | ❌ | ❌ | ❌ |

- admin 在 `get_user_permissions` 中直接返回 `["*"]`，**不依赖 role_permissions 行**，因此矩阵中 admin 无显式记录属正常。
- Phase 4 新增 `reports:manage` 后，按目标需授予 **admin（隐式已有 `*`）+ analyst（需显式插入 1 行）**。

---

## 四、其余架构现状（供后续 Phase 评估）

| 项 | 现状 | 对后续 Phase 的影响 |
|---|---|---|
| 调度器 | `app/core/scheduler.py`，APScheduler，已注册 3 个 job：`collector_main`(cron)、`weibo_consumer`(cron)、`alert_eval`(IntervalTrigger) | Phase 6 新增 `report_dispatch`(IntervalTrigger 1min) **模式一致，可行** |
| 多实例 | uvicorn 8000 / 8011 均调 `start_scheduler()`，靠 `pg_try_advisory_lock` 保证单实例调度 | Phase 6 的 `FOR UPDATE SKIP LOCKED` 与之叠加，双保险，无冲突 |
| SMTP 配置 | `config.py` 中**无任何 SMTP_\* 项**，无 `REPORT_STORAGE_DIR` | Phase 5 全部新增，无冲突 |
| 邮件能力 | 系统当前**无**任何邮件发送代码 | Phase 5 从零建 `mail_service.py`（仅 smtplib/email 标准库） |
| 前端报告相关文件 | `frontend/src/api/report.ts`、`components/report/ReportExportDrawer.vue`、`components/report/ModuleSelector.vue` **均已存在**（Phase Report-1.1 产出） | Phase 3 由"新建"降级为"**增量改造**"，需保持现有调用不回归 |
| 重量组件 | 无 ES / Redis / MQ / Celery / MinIO | 全流程不引入，符合约束 |

---

## 五、Phase 1 前的待确认建议

| # | 问题 | 建议方案 |
|---|---|---|
| 1 | `POST /api/reports/export` vs 现存 `POST /api/reports/generate` | 新增 `/export` 作为**正式入口**（支持 `range_type`、`delivery`、`modules` 带参数），`/generate` 保留为**薄适配层**转调新逻辑（旧前端与旧脚本不回归），并在 OpenAPI 标注 deprecated |
| 2 | 现有 `distribution` 模块 key 被拆成 3 个 | 保留 `distribution` 为**隐藏兼容别名**（不出现在 `/modules` 列表，但请求里出现时自动展开为 `source_dist,region_dist,keyword_dist`），避免已保存的前端本地配置与 `report_records` 历史配置解析失败 |
| 3 | 注册表字段 `title` vs 目标的 `name` | 注册表内部统一改 `name`，`/modules` 响应**同时返回 `name` 和 `title`（同值）** 一个版本周期，前端切换后再删 `title` |
| 4 | `reports:write` 遗留权限 | 本阶段不动，仅在最终验收报告的"技术债"章节登记 |
| 5 | Phase 2 时区转换 | **见《阻塞问题审计报告》——设计与实际存储相反，必须先确认** |

---

## 六、审计结论

| 检查项 | 结论 |
|---|---|
| 数据库身份门禁 | ✅ VERIFIED（退出码 0） |
| alembic head | ✅ `p26_report_records`，代码与生产库一致 |
| 12 模块数据可行性 | ✅ 全部字段就绪，无需新增业务列 |
| 时间口径判定 | ✅ **路线 B：`COALESCE(publish_time, created_at)`**（NULL 22.90%） |
| 权限现状 | ✅ `reports:read`/`reports:export` 已有；`reports:manage` 待 Phase 4 新增 |
| 单模块失败隔离 | ⚠️ 现无，Phase 1 必须补 |
| 前端文件 | ⚠️ 已存在，Phase 3 改为增量改造 |
| **时区口径** | 🔴 **阻塞：实际为 Asia/Shanghai naive 存储，与 Phase 2「数据库 UTC」描述相反。见《阻塞问题审计报告》** |

**Phase 0 完成。本阶段零修改。**
