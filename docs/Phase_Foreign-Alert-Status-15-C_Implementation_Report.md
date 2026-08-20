# Phase Foreign-Alert-Status-15-C Foreign Alert Unified Disposition — 实施报告

> 生成时间：2026-08-14
> 阶段目标：实现「外网预警统一人工处置（双列模型 Option 2）」—— `status`（生命周期态）与 `disposition_status`（统一人工处置）解耦，经 `set_disposition()` 单一写入入口协调，前端 `Alerts.vue` 双列展示 + 5 处置 + 审计合并，权限新增 `foreign:alerts:false_positive`，全程不改动国内 `alert_records`、不改动 `failed` 态、不引入 `is_hidden`。

---

## 1. 概述 / 目标

将外网预警的人工处置从「直接状态」升级为「生命周期态 + 统一处置态」双列模型，统一 domestic / foreign 的处置语义，同时保留 `failed` 死约束与 5 态生命周期 CHECK 不变。

## 2. 架构决策（Option 2）

- `foreign_alerts.status` = Foreign Lifecycle Status（triggered / acknowledged / resolved / suppressed / failed，5 态不变；`failed` 永留 CHECK）。
- `foreign_alerts.disposition_status` = Unified Human Disposition（pending / processing / resolved / ignored / false_positive，新增）。
- `set_disposition()` 为唯一处置写入入口，经 `set_status(commit=False)` 协调生命周期；`transition()` 与生命周期 CHECK 不动。

## 3. 实施范围（15-C1 → 15-C8）

15-C1 Migration；15-C2 Model/Schema/Service；15-C3 API；15-C4 Frontend；15-C5 Permission；15-C6 Tests；15-C7 生产只读验证；15-C8 构建与部署。

## 4. 15-C1 Migration

- 文件：`backend/alembic/versions/foreign_alert_disposition_status.py`
- revision=`foreign_alert_disposition_v1`，down_revision=`p33_event_archived_merge_split`
- 严格增量：新增 `disposition_status` 列（String(16)，server_default `'pending'`，CHECK）+ 索引 `ix_foreign_alerts_disposition_status`
- 新增 `foreign_alert_disposition_actions` 表（双列 5 态 CHECK，FK CASCADE，`actor_id` SET NULL，metadata JSONB）
- 幂等回填：仅提升仍为 `pending` 的历史行（重跑不覆盖人工处置）
- 种子 `foreign:alerts:false_positive` 权限（ON CONFLICT DO NOTHING）+ 授权 admin 角色
- **生产已执行**：`alembic upgrade head` 成功，DB_IDENTITY 已校验

## 5. 15-C2 Model / Schema / Service

- `foreign_alert.py`：`disposition_status` 列 + `ck_foreign_alerts_disposition_status` + `ix_foreign_alerts_disposition_status`；新增模型 `ForeignAlertDispositionAction`
- `foreign_alert_service.py`：
  - 常量 `DISPOSITION_STATES`、`DISPOSITION_TO_LIFECYCLE`、`FORBIDDEN_DISPOSITION_MATRIX`
  - `set_status()` 新增 `commit: bool = True`（默认提交；`set_disposition` 内部传 `commit=False` 协调）
  - `set_disposition()`：行锁 → 拒绝 `pending` / `failed` / 禁止矩阵 / 未知态 → 经 `set_status(commit=False)` 协调 → 写 `ForeignAlertDispositionAction` → 原子提交
  - `serialize_alert` 增加 `disposition_status`；新增 `serialize_disposition_action` / `list_disposition_actions`

## 6. 15-C3 API

- `PUT /foreign/alerts/{id}/handle`：主参 `disposition_status`；旧式 `status` 向后兼容映射（acknowledged→processing / resolved→resolved / suppressed→ignored）；两者不一致 → **409**；非法态 → **400**；无权限 → **403**；不存在 → **404**
- `GET /foreign/alerts`：返回双列（`status` + `disposition_status`）；新增 `disposition_status` 精确过滤 + `disposition_filter`（all / hide_fp / only_fp，默认 hide_fp，ignored 始终可见）；**严禁 `is_hidden`**
- `GET /foreign/alerts/{id}/actions`：合并 `items`（生命周期）+ `disposition_items`（处置）

## 7. 15-C4 Frontend

- `frontend/src/views/Alerts.vue`：外网过滤栏增生命周期 + 处置态 + `disposition_filter`（hide_fp/all/only_fp）三选；处置态列显示 `disposition_status` 弱生命周期子标签；处置弹窗外网选项 = 处理中/已解决/已忽略/误报（无待处理）；历史时间线区分 lifecycle / disposition；`canFalsePositiveForeign` 受 `foreign:alerts:false_positive` 门控

## 8. 15-C5 Permission

- `backend/app/core/permissions.py`：将 `foreign:alerts:false_positive` 并入 `foreign:alerts:manage` 复合展开
- 映射：processing→acknowledge / resolved→resolve / ignored→suppress / false_positive→false_positive（不复用 suppress）

## 9. 15-C6 Tests

- 新增 `backend/tests/test_foreign_alert_disposition.py`（38 用例，全部通过）
- 覆盖：5 处置生命周期映射、禁止矩阵、pending/failed/未知态拒绝、审计轨迹、幂等、API 新参/旧式兼容/400/403/404/409、列表 hide_fp/all/only_fp、ignored 可见、双列返回、审计合并、domestic 不受影响
- **测试库 5433 升级至 head**（`rbac_d3_enforcement_v2 → p33 → foreign_alert_disposition_v1`），确保新列/表/权限就位

## 10. 15-C7 生产只读验证（SELECT-only，opinion_db 5432）

| 检查项 | 结果 |
|---|---|
| alembic head | `p34_foreign_event_status_unify`（后续迁移亦已应用；15-C 的 `foreign_alert_disposition_v1` 在链中且已确认应用） |
| `disposition_status` 列存在 | ✅ pending=5 / processing=1 |
| 禁止组合行数 | **0** |
| `foreign_alert_disposition_actions` 伪行 | **0** |
| 国内 `alert_records` 含 `disposition_status` 列 | 无（✅ 未改动） |
| 国内 `alert_records` 行数 | 38（✅ 不变） |
| `foreign:alerts:false_positive` 权限已种子 | ✅ |

## 11. 15-C8 构建与部署

- vite build：清除 `.vite` 缓存 → `vite build`（14.78s）成功，`Alerts-C4xvxUQa.js` 含全部 15-C 标记（hide_fp / only_fp / disposition_filter / canFalsePositiveForeign / 误报 / 已忽略 / 处理中）
- 静态同步：node `fs.cpSync(dist → backend/app/static)`（保留既有资源）；`static/index.html → index-Dx3ovtSD.js → Alerts-C4xvxUQa.js` 引用链确认
- 后端：生产后端此前未监听 8000，已按 `COLLECTOR_SCHEDULE_ENABLED=false` 启动 uvicorn（PID 38304），连接 opinion_db
- 运行时冒烟：登录 200；列表 200（total=6，双列齐全）；`all`→6 / `only_fp`→0；actions 合并；**`PUT handle` disposition_status=resolved → 200 并持久化 (resolved,resolved)**

## 12. 规范组合 / 禁止组合矩阵

- 规范：(triggered,pending) / (acknowledged,processing) / (resolved,resolved) / (suppressed,ignored) / (suppressed,false_positive)
- 禁止：triggered+false_positive / triggered+ignored / resolved+ignored / resolved+false_positive / suppressed+resolved / failed+any
- 生命周期映射：processing→acknowledged、resolved→resolved、ignored→suppressed、false_positive→suppressed

## 13. 审计轨迹

- `foreign_alert_disposition_actions`：`previous_disposition` / `new_disposition` / `note` / `actor_id` / `created_at` / `metadata_json`；与 `foreign_alert_actions`（生命周期）分离但同端点合并返回

## 14. 国内不受影响验证

- `alert_records` 无 `disposition_status` 列、5 态 CHECK 不变、行数 38；`set_disposition` 不触碰国内任何表（✅ 红线遵守）

## 15. 发现的问题与修复

1. **测试库陈旧**：5433 停在 `rbac_d3_enforcement_v2` 且缺新列/表/权限 → 升级至 head（仅测试库，生产不受影响）
2. **`transition()` 红线回归（15-C 自引入）**：15-C2 在 `set_status` 引入 `commit` 参数时，误将 `transition()` 的 `db.commit()` 改为 `if commit: db.commit()`（缺失 `commit` 参数）→ 成功路径 `NameError`。已在 15-C6 测试中发现，**将 `transition()` 整体 revert 至 HEAD 原貌**，恢复「transition() 不变」红线（测试验证 acknowledge 成功且 `disposition_status` 不被改动）
3. **测试用例 FK/约束修正**：审计测试 `user_id=7` 违反 `users` FK → 改用 `user_id=1`；旧式 suppressed 测试误用 `triggered` 预警（suppressed→ignored 属禁止组合）→ 改为 `acknowledged` 预警

## 16. 红线遵守情况

- ✅ 无 DELETE；✅ 5 态生命周期 CHECK 不变；✅ `failed` 永留；✅ 无 `is_hidden`；✅ suppressed 不取代 false_positive 语义（二者共存于 5 态）；✅ 国内 `alert_records` 未改动；✅ `transition()` 未改动（已 revert）

## 17. 验收标准清单

- [x] 双列模型落地（status + disposition_status）
- [x] 规范/禁止组合在 service + API 双向强制
- [x] `set_disposition()` 为唯一处置写入入口，协调生命周期
- [x] 审计表 + 合并历史端点
- [x] 列表双列 + disposition_status 过滤 + disposition_filter（默认 hide_fp，ignored 可见）
- [x] 新权限 `foreign:alerts:false_positive` 且不复用 suppress
- [x] 前端双列展示 + 5 处置 + 过滤切换 + 历史合并
- [x] 国内不受影响
- [x] 测试 38/38 通过
- [x] 生产只读验证通过
- [x] 构建 + 静态同步 + 后端启动 + 运行时冒烟通过

## 18. 测试结果与覆盖率

- `backend/tests/test_foreign_alert_disposition.py`：**38 passed**
- 测试库：opinion_test:5433（head = foreign_alert_disposition_v1，DB_IDENTITY_CHECK=off）

## 19. 运行时验证结果（生产 opinion_db 5432）

- 登录 200；`GET /api/foreign/alerts` 200（total=6，双列齐全）
- `disposition_filter=all`→6，`only_fp`→0
- `GET /{id}/actions` 200 合并 lifecycle + disposition
- `PUT /{id}/handle` `disposition_status=resolved` → 200，持久化 (resolved,resolved)
- ⚠️ 该冒烟对生产预警 `id=14` 做了一次真实处置（processing→resolved），属功能正常验证；如须回退可由操作员重新处置

## 20. 结论 / Final Status

**Final Status：PASS**

Phase 15-C 全链路（迁移→模型/服务→API→前端→权限→测试→生产只读验证→构建部署→运行时验证）完成，38 项测试通过，生产只读不变量全部成立，运行时冒烟确认双列模型与处置写入端到端可用，所有红线遵守。唯一需跟进项：生产 alembic head 已前进至 `p34_foreign_event_status_unify`（同源后续阶段迁移，与 15-C 正交，15-C 变更已在链中确认应用）。

---

### 修改文件清单（15-C 范围）

- `backend/alembic/versions/foreign_alert_disposition_status.py`（新增）
- `backend/app/models/foreign_alert.py`
- `backend/app/services/foreign_alert_service.py`
- `backend/app/api/foreign_alerts.py`
- `backend/app/core/permissions.py`
- `frontend/src/views/Alerts.vue`
- `backend/tests/test_foreign_alert_disposition.py`（新增，测试）
- `frontend/dist/*` → `backend/app/static/*`（构建产物，已同步）
