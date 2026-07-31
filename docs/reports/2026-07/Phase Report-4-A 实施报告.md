# Phase Report-4-A：报告模板最小可用能力 — 实施报告

> 日期：2026-07-31
> 阶段定位：在 Phase Report-2/3/4-0 基础上的最小可用（MVP）能力交付；完成后停止，不进入 Phase 4-B。
> 核心原则：模板 = `ReportExportRequest` 配置快照；零侵入生成链路（`/export`、`/generate`、PDF 逻辑、`report_records` 均不变）。

---

## 1. 概述与目标

**目标**：为报告导出提供"保存配置为模板 / 加载模板回填 / 编辑 / 删除"的最小可用能力，使运营人员无需每次手工重选时间范围、模块与参数。

**设计本质**（来自 Phase Report-4-0 架构审计结论）：
- 模板不是新一套报告引擎，而是**导出配置（`ReportExportRequest`）的快照**。
- `config_json` 仅存储导出相关字段（`name / time_field / range_type / range_days / start_date / end_date / modules`），**剔除** `delivery`、`recipients` 等与"导出配置"无关的字段。
- 生成链路完全复用既有 `/export`，模板不参与任何 PDF/聚合/风险计算逻辑。

**交付范围**：数据库表 + 权限 + Schema/Model + Service + API + 前端抽屉交互 + 测试。Dashboard 入口、邮件、定时、版本管理均**不在本阶段**。

---

## 2. 实施前确认清单（Phase Report-4-A-0 结论）

只读审计 5 项，全部确认通过：

| 项目 | 结论 | 处置 |
|------|------|------|
| 分支 | `main` | ✅ 在 main 上实施 |
| HEAD | `p28_anspire_provider` | ✅ 新迁移 `down_revision` 锚定 p28 |
| `report_records` 结构 | 无 `template_id` 列 | ✅ 不回填、不迁移历史 |
| RBAC | 无 `reports:manage` | ⚠️ 需新增（幂等迁移授予 admin） |
| `REPORT_MODULES` | 12 个 key 稳定（MODULE_MAP @ service L1070） | ✅ 模板 modules 校验以此为准 |

---

## 3. 数据库迁移

### 3.1 新增迁移 `p29_report_templates.py`
- `revision = "p29_report_templates"`，`down_revision = "p28_anspire_provider"`。
- 新建表 `report_templates`：

| 列 | 类型 | 约束 |
|----|------|------|
| id | integer | PK, 自增 |
| name | varchar(128) | NOT NULL |
| description | varchar(255) | NULL |
| owner_id | integer | FK→users.id, NOT NULL, 索引 |
| config_json | jsonb | NOT NULL, 默认 `{}` |
| is_public | boolean | NOT NULL, 默认 false |
| created_at | timestamp | NOT NULL, server 默认 now() |
| updated_at | timestamp | NOT NULL, server 默认 now() + onupdate |

- 新增权限 `reports:manage`（`resource=reports, action=manage, group=报告`），`ON CONFLICT (code) DO NOTHING` 幂等播种；并向 admin 角色授予，`ON CONFLICT (role_id, permission_id) DO NOTHING` 幂等。
- **保留** `reports:read / write / export`，**不删除** `reports:write`。
- `downgrade()` 幂等回滚（删表 + 删权限 + 自动解除关联）。

### 3.2 生产库实际状态（重要）
- 身份门禁 VERIFIED：目标库 `opinion_db@127.0.0.1:5432`，`system_identifier=7663057120701798896`，`opinions=932` 行，与预期生产基线一致。
- 生产 `alembic_version` 实际已处于 **`p29_history_geo_filtered`（单 head）**，即 p29_report_templates 与 p29_history_geo_filtered 均已落库。
- 说明：实施过程中曾遇 `alembic upgrade head` 报 "Multiple head revisions"，经核查为 `alembic/versions/__pycache__` 陈旧字节码导致的文件图误判；`alembic heads` 始终显示单一 head（`p29_history_geo_filtered`），迁移实际已成功应用。
- **附带提示**：`p29_history_geo_filtered` 属另一治理 phase（为 `opinions` 加 `geo_filtered` 列、为 `events.status` 增加 `'deprecated'` 合法值），已随 head 一并部署于生产。本 Phase 4-A 仅依赖 `p29_report_templates`；如该治理 phase 尚未到生产窗口，可单独 `alembic downgrade p29_history_geo_filtered` 回退（不影响本阶段模板能力）。

---

## 4. Schema 与 Model

### 4.1 Schema（`app/schemas/report.py`，仅新增，未改既有）
- `ReportTemplateConfig`：模板配置载体（`name / time_field / range_type / range_days / start_date / end_date / modules`）。
- `ReportTemplateCreate`：`name`(1–128) + `description?` + `is_public` + `config_json`。
- `ReportTemplateUpdate`：全字段可选。
- `ReportTemplateResponse`：含 `can_edit: bool`（owner 或超管为 true）。
- **`ReportExportRequest` 与 `ReportModuleDef` 未做任何修改**（契约不变）。

### 4.2 Model（`app/models/report_template.py`，新增）
- `ReportTemplate(Base)`，风格对齐 `ReportRecord`（server 端 `now()` 默认值 + `onupdate`）。
- 注册至 `app/models/__init__.py`（`__all__` 同步）。

---

## 5. Service 层（`app/services/report_template_service.py`，新增）

- `create_template / list_templates / update_template / delete_template`。
- `_validate_module_keys`：模板中的 module key 必须存在于 `MODULE_MAP`，否则返回 **400**（未知报告模块）。
- `can_edit_template`：仅 `owner_id == 当前用户` 或 `is_superuser_user(user)` 可改/删，否则 **403**。
- `list_templates`：返回"本人模板 + 公开模板（is_public）"。
- `_to_response`：对 `config_json` 做容错解析（缺字段回退默认），始终返回 `can_edit`。

---

## 6. API 层（`app/api/reports.py`，仅追加 4 端点）

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | `/api/reports/templates` | `reports:export` | 列表（本人+公开） |
| POST | `/api/reports/templates` | `reports:manage` | 创建（201） |
| PUT | `/api/reports/templates/{id}` | `reports:manage` | 更新 |
| DELETE | `/api/reports/templates/{id}` | `reports:manage` | 删除（204） |

- **`/export` 与 `/generate` 完全未改动**（导出契约、PDF 逻辑、风险模型零侵入）。
- 鉴权复用既有 `require_permission(perm)`（返回 `User`）；超管 `is_superuser_user` 判定。

---

## 7. 前端实现

### 7.1 `frontend/src/api/report.ts`
- 新增接口 `ReportTemplateConfig / ReportTemplateCreatePayload / ReportTemplateUpdatePayload / ReportTemplate` 及 `getTemplates / createTemplate / updateTemplate / deleteTemplate`。
- `generateReport`（即 `/export`）保持不变。

### 7.2 `frontend/src/components/report/ReportExportDrawer.vue`
- 顶部新增**模板下拉**：加载本人+公开模板、选择后回填表单（`applyConfigToForm`）。
- 页脚新增**"保存为模板"**：弹 dialog 录入 `name / description / is_public`，由 `buildConfigFromForm()` 生成模板配置（剔除 delivery/recipients）。
- 模板下拉中**删除按钮**：仅当 `can_edit=true` 可点。
- **`Dashboard.vue` 未改**；**未新增模板管理页**。

### 7.3 构建与部署
- `frontend` 构建成功，`index` bundle 已部署至 `backend/app/static/`（部署产物含"保存为模板"等模板 UI 文案，已核验）。

---

## 8. 测试情况

- 新增 `backend/tests/test_report_template_phase4a.py`，覆盖 ≥8 项（实际 10 项）：
  - admin 创建成功（201 + `can_edit` + `config_json` 回显）
  - 普通 viewer 创建 → **403**
  - 个人 + 公开模板列表隔离
  - 未知 module key → **400**
  - 用模板配置走 `/export` 生成 PDF（导出链路契约不变）
  - `/export` API 契约未变 / modules 结构兼容（12 模块）
  - viewer 访问 GET `/templates` → **403**
- 测试库 `opinion_test@5433` 应用 p29 迁移后，**共 38 项测试全部通过**（Phase 1/2/3 既有 28 项 + 本阶段 10 项），耗时约 269s，无失败。

---

## 9. 生产部署与验收（含事件说明）

### 9.1 部署前核验
- 身份门禁 `db_identity_check.py` → **VERIFIED**（932 opinions，system_identifier 匹配），确认连的是真实生产库。
- 生产 `report_templates` 表（8 字段齐全）、`reports:manage` 权限（已授予 admin）均就位。

### 9.2 运行服务恢复（事件透明记录）
> ⚠️ **本次操作中的一个意外（已恢复，根因已定位）**：原以为存在"一个 LISTENING、一个绑定失败的孤儿"两个独立 uvicorn 进程，遂 `taskkill` 清理所谓的孤儿（PID 39808）。实际上经 `Get-CimInstance` 核查，**两个同端口 uvicorn 是父子对**——39808 是在线服务 33800 的**父进程（supervisor）**，杀父级联杀子，导致 8000 端口约数分钟不可用。
> 恢复：用无空格模块串 `app. main:app`（点号形式，已验证斜杠 `app/main` 在 uvicorn 0.30.6 下失败）干净重启单实例 uvicorn，服务恢复。
> **经验沉淀**：同端口出现两个 uvicorn 多为父子对（父不绑端口、子是真正 LISTENING 的 worker），清理前必须先查 `ParentProcessId`，**绝不杀 LISTENING 进程及其父进程**。详见项目 MEMORY.md。

### 9.3 验收结果（恢复后实测）
- uvicorn PID **35924** LISTENING 于 `0.0.0.0:8000`，`Application startup complete.`。
- `GET /api/reports/templates` → **HTTP 401 `Not authenticated`**（证明路由已注册并受 `require_permission` 鉴权保护；非 404/SPA 兜底）。
- 日志显示真实业务流量恢复（`/api/alerts/unread` 200），服务健康。
- 注：401 仅证明路由在线且鉴权生效；带有效 JWT 的 200 行为已在测试库 38 项用例中验证（含 admin 创建/列出/导出）。

---

## 10. 约束遵守、范围边界与回滚

### 10.1 严格遵守的"禁止"项 ✅
- `/export`、`/generate`、PDF 逻辑、**未改动**。
- `report_records` 表**未改**、未加 `template_id`、未迁移历史。
- Dashboard 入口**未增加**；未实现邮件 / 定时 / 版本管理。
- **未改动** 风险模型、Event 聚合、`dashboard_service`。
- **未引入** Elasticsearch / Redis / Celery / 消息队列。
- `ReportExportRequest` / `ReportModuleDef` **未改**。

### 10.2 范围边界
- 模板仅为导出配置快照，不参与生成/聚合/风险计算。
- 生产 `p29_history_geo_filtered`（另一 phase）随 head 一并落库，属附带部署，可按需单独回退（见 3.2）。

### 10.3 回滚方案
- 代码：revert 相关文件（schemas/report.py 新增部分、models/report_template.py、services/report_template_service.py、api/reports.py 4 端点、前端 drawer）。
- 数据库：`alembic downgrade p29_report_templates`（幂等 `downgrade` 已提供，删除表与权限并自动解除关联；如已回退 geo_filtered 则先 `downgrade p28_anspire_provider`）。
- 前端：`frontend` 重新构建部署上一稳定 bundle。

### 10.4 后续（不在本阶段）
- Phase 4-B 及生产部署收口（如灰度、模板管理页、版本/分享）按原计划后续推进；本阶段已停止。
