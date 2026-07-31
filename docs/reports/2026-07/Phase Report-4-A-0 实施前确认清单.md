# Phase Report-4-A-0 实施前确认清单

> 严格只读审计结论。本文件仅确认现状，不修改任何代码/库/配置。实施前确认项全部无误，可进入 Phase 4-A 实施。

## 1. 当前分支状态
- 分支：`main`
- 最近提交：`3d6655a2 feat: 数据源健康度与事件态势感知(Phase8)、微博八爪鱼生产模式接入及前端体验优化`
- 工作区：613 个文件存在未提交改动（历史各 Phase 累积，含 Phase 2/3 的 report_service.py / reports.py / schemas/report.py / 前端文件）。本 Phase 仅在既有工作区增量新增 + 小改，不触碰无关文件。
- Git 身份门禁：当前生产库 `alembic current` = `p28_anspire_provider (head)`，`[DATABASE IDENTITY: VERIFIED]`（opinions≥100，真实生产库）。

## 2. Alembic head
- 实际 head：**`p28_anspire_provider`**（已用 `alembic heads` 确认）。
- 本 Phase 新增迁移：`p29_report_templates.py`，`down_revision = "p28_anspire_provider"`。
- 不动既有迁移；不重写历史。

## 3. report_records 结构（确认不改动）
```
report_records:
  id          Integer PK
  name        String(255) NOT NULL
  config_json JSONB NOT NULL
  status      String(16) server default 'success'
  created_by  Integer NULL
  created_at  DateTime server default now()
```
- **不新增 `template_id`**（Phase 4-A 只解决保存/加载，关联留待 4-B/C）。
- 保持 `report_records` 逻辑不变。

## 4. RBAC 当前状态
- 已播种权限：`reports:read`（查看报告）、`reports:write`（导出报告，兼容保留）、`reports:export`（导出 PDF，Phase 1 新增）。
- **`reports:manage`：全代码库不存在** → 本 Phase 在迁移中新增（resource=reports, action=manage），幂等 `INSERT ... WHERE NOT EXISTS`，并授予 `admin` 角色（与 p26 对 `reports:export` 的播种模式一致）。
- 权限播种在**迁移内以原始 SQL 完成**（非 init_db 覆盖式），保证幂等、可回滚。
- 判定来源：`role_permissions` 关联表；超管 = `is_superuser` 或 `role=='admin'`（见 `permissions.is_superuser_user`）。
- 校验依赖：`app.core.permissions.require_permission(perm)` 返回 `User`；`is_superuser_user(user)` 判定 admin。

## 5. REPORT_MODULES 当前 key（稳定，可序列化）
12 个，顺序即章节顺序，可作为模板 `modules` 顺序：
```
overview_kpi, trend, sentiment, top_risky, events,
source_dist, region_dist, keyword_dist,
risk_category, alert_summary, opinion_list, conclusion
```
- 校验可用：`MODULE_MAP = {m["key"]: m for m in REPORT_MODULES}`（report_service.py L1070）。
- 未知 key 在 Service 层校验 → 400。
- `params` 元数据（key/label/type/default/min/max）完备，模板 `config_json.modules[].params` 可直接回填表单。

## 确认结论
5 项全部无误。模板本质 = 一份 `ReportExportRequest` 配置快照（去 `delivery`/`recipients`），零重构生成链路。可进入 Phase 4-A 实施。
