# Phase 2-E-0 事件运营闭环改造前审计报告

> 审计性质：**实施前只读审计**。仅阅读源码、执行 `SELECT` 统计，未修改任何代码 / 数据库 / 配置。
> 审计时间：2026-07-31
> 数据库：`opinion_db`（生产库，:5432）
> 交付物：`docs/Phase_2E-0_事件运营闭环改造前审计报告.md`

---

## 0. 审计范围与文件清单

| 类别 | 文件 |
|---|---|
| 后端模型 | `backend/app/models/event.py`、`opinion.py`、`alert.py`、`event_action.py`、`event_opinion.py` |
| 后端服务 | `backend/app/services/event/aggregator.py`、`alert_service.py`、`dashboard_service.py` |
| 后端 API | `backend/app/api/events.py`、`alerts.py` |
| 前端页面 | `frontend/src/views/Events.vue`、`EventDetail.vue`、`Alerts.vue` |
| 前端类型 | `frontend/src/types/index.ts`、`utils/event.ts` |
| 数据库 | `events`、`opinions`、`event_opinions`、`alert_records`、`event_actions` |

---

## 1. 核心结论（先讲重点）

**事件运营闭环能力 80%+ 在现状中已存在**。任务多处"新增"实为"已具备"，必须避免重复建设。关键事实：

1. **事件列表/详情/处置弹窗/操作记录时间线均已实现**，前端 `Events.vue` + `EventDetail.vue` 已是完整的"事件运营中心"骨架。
2. **事件状态更新接口 `PATCH /events/{id}/status` 已存在**，且是**状态机式流转**（非任意赋值）+ `events:write` 权限 + `audit_write` 写操作日志。
3. **事件操作记录机制已存在**：`event_actions` 表（含 `user_id`/`action_type`/`content`/`old_status`/`new_status`/`created_at`）+ `audit_write` 写入 `user_operation_logs`。
4. **Alert 与 Event 双向链路数据已具备**：`alert_records.event_id` 由 `sync_alert_events` 回填；`event_opinions` 提供事件↔舆情反查。
5. **关键偏差**：任务设想的 `status` 枚举为 `pending/processing/resolved/ignored`，但 **Event 实际枚举是 `active/verifying/processing/resolved/closed/deprecated`**。"忽略事件"在当前语义下对应 `deprecated`，且**当前状态机不允许从 `active` 直接置 `deprecated`**，这是 Phase 2-E-3 必须解决的点。
6. **热点主题→事件**：`Event.topic_category` 已含 `education` 等 11 类主题；结合 `EventOpinion` 做只读反查完全可行，无需重新计算。

---

## 2. 后端模型审计

### 2.1 Event（`models/event.py`）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| title | str(512) | 事件标题（聚合器统一格式生成） |
| description | Text | 描述 |
| keyword | str(256) | 合并关键词 |
| risk_level | str(32) | **注意：API 层实际由 risk_score 派生展示，非读取此列** |
| region_id | int FK→regions (index) | 影响地区 |
| status | str(32) | **实际枚举见 §4** |
| risk_score | int 0-100 | |
| topic_category | str(32) | 11 类主题（含 education），见 §7 |
| heat_score | int 0-100 | 热度 |
| trend | str(32) | rising/stable/falling/unknown |
| opinion_count | int | 关联舆情数（聚合器维护） |
| first_time / last_time | datetime | 首/末舆情时间 |

- 关系：`opinions` 经 `event_opinions` 多对多（`lazy="selectin"`）。
- **无 `updated_at` / `handler` / `resolution_note` 列**（任务 2-E-1 推荐字段中这三项的对应物不存在）。

### 2.2 Opinion（`models/opinion.py`）关键字段
`id, title, content, source, region_id, risk_score, keywords, created_at, publish_time, event_state, analysis_status` … 与 Event 经 `event_opinions` 多对多。用于聚合与反查。

### 2.3 AlertRecord（`models/alert.py`）
- 已有 `event_id`(FK events, index)、`event_title`、`status`(pending/processing/resolved/ignored/false_positive)、`handled_by`(FK users)、`handled_at`、`handle_note`、`handled`(bool)。
- **结论：Alert 自身已具备完整处置字段，且可关联 Event。**

### 2.4 EventOpinion（`models/event_opinion.py`）
- `event_id` + `opinion_id` + 唯一约束。**纯链接表，无 `created_at`**。反查：`SELECT opinion_id FROM event_opinions WHERE event_id=?` 或反向。

### 2.5 EventAction（`models/event_action.py`）—— **操作记录复用点**
- `event_id, user_id, action_type(status_change/note/assign/resolve), content, old_status, new_status, created_at`。
- **结论：任务要求的"操作记录/处置记录"机制已存在，必须复用，禁止重建。**

---

## 3. 事件聚合方式审计（`services/event/aggregator.py`）

- **自动聚合**：`EventAggregator.aggregate(db, incremental/rebuild/dry_run)`。
  - 采集后触发：`auto_aggregate_after_collect()`（增量，异常安全）。
  - 手动触发：`POST /events/aggregate`（后台任务，前端轮询 `task_id`）。
- **相似/成员判定**（`_merge_condition`）：`同 region_id` + `时间窗(event_window_days)` + 满足任一：
  1. 共享高区分度信号（非通用词 / ai_keywords）；
  2. 共享通用词 且 文本相似度 ≥ `event_low_merge_text_threshold`；
  3. 文本相似度 ≥ `event_text_similarity_threshold`（纯文本合并）。
  - 文本相似度 = 字符 2-gram 余弦（纯 Python，无新依赖）。
- **反链式（防伪聚合）**：星型聚类，新成员仅对其 representative 做直接判定；事件延续窗口 `event_continuation_days`。
- **人工调整**：`PATCH /events/{id}/status`（状态流转）、`POST /events/{id}/actions`（备注）、`DELETE`。聚合器**不写 `status`**。
- **安全**：PG advisory lock 防并发双物化；`dry_run=True` 回滚写操作（只读验证用）；增量幂等。

---

## 4. 事件状态审计（关键偏差）

**实际枚举（CHECK 约束）**：`active / verifying / processing / resolved / closed / deprecated`。

**状态机**（`api/events.py` `NEXT_EVENT_STATUS`）：
```
active → verifying → processing → resolved → closed
deprecated → active   (软废弃可恢复)
```

| 任务设想（2-E-1） | 现状 | 差异说明 |
|---|---|---|
| pending | — | 不存在；最接近 `active`(关注中) |
| processing | processing ✅ | 一致 |
| resolved | resolved ✅ | 一致 |
| ignored | deprecated(已废弃) | 语义接近，但**状态机不允许 active/processing 直接→deprecated** |

**影响**：任务 2-E-3 的"忽略事件"按钮，若映射为 `deprecated`，需**放开状态机允许从活跃态直接置 deprecated**（或新增独立 `ignored` 值——但任务要求"已有类似字段不重复增加"，故建议复用 `deprecated`）。

---

## 5. Alert 与 Event 关系审计

- **正向 Alert→Event**：`alert_records.event_id` 由 `AlertService.sync_alert_events()` 按 `opinion_id → event_opinions.event_id` 回填（见 `alert_service.py:150`）。
- **反向 Event→Alert**：`SELECT * FROM alert_records WHERE event_id = ?` 即可；**当前事件接口未返回 alerts**。
- **前端**：`Alerts.vue` 已展示"关联事件"列（`<router-link :to="'/event/'+row.event_id">`），双向展示已通一端。

---

## 6. 前端能力审计

### 6.1 Events.vue（列表 / 运营中心）—— 已较完整
- ✅ 筛选：标题搜索、风险(现行+影子)、主题、处置状态、趋势、地区 ID、热度区间。
- ✅ 行展示：主题 / 影子风险 / 研判分 / 热度 / 趋势 / 关联舆情数 / 处置状态 / 首末时间。
- ✅ 点击行 → `/event/{id}` 详情；"处置"弹窗含状态机按钮 + 备注 + 处置记录时间线。
- ✅ RBAC：`canUpdateEvent = hasPermission('events:write')`，无权限仅只读。
- 🟡 缺：来源数量(`source_count`)、`alert_count` 未展示。

### 6.2 EventDetail.vue（详情）—— 已较完整
- ✅ 基本信息 + 态势条(主题/状态/风险/热度/趋势) + 描述。
- ✅ "事件态势"面板(`/events/{id}/situation`)：来源 N 个、时间窗、影子风险、风险因子。
- ✅ **关联舆情列表**：完整表格（标题/来源/情感/风险分/分析状态/发布时间），可点开舆情详情弹窗。
- ✅ 处置弹窗 + **处置记录时间线**（复用 `event.actions`）。
- 🟡 缺：alerts 列表、`statistics` 结构化块、风险变化时间序列图。

### 6.3 Alerts.vue
- ✅ 已展示"关联事件"列 + 跳转。

### 6.4 types/index.ts
- `EventItem` 含 `opinion_count`，**无 `source_count` / `alert_count`**。

---

## 7. 数据库现状统计（生产 `opinion_db`，2026-07-31）

| 指标 | 值 |
|---|---|
| events 总量 | 162 |
| ├ active | 150 |
| └ deprecated | 12 |
| （verifying/processing/resolved/closed） | 0（当前无流转中事件） |
| topic_category 分布 | other 45 / safety 36 / gov_service 28 / livelihood 14 / market 11 / healthcare 9 / **education 9** / traffic 4 / public_emergency 4 / social_security 2（environment 0） |
| opinion_count | min 1 / max 10 / avg 2.2 / 0 条=0（每个事件均≥1 关联舆情） |
| event_opinions | 362 links / 161 events / 362 opinions（每舆情仅属 1 事件，无跨事件重叠） |
| alert_records | 9 条；已关联事件 6 / 未关联 3；status 全部 pending |
| event_actions | 16 条 / 涉及 3 个事件 |
| opinions | 934 |

**结论**：数据规模小，结构健康；`event_opinions` 无跨事件重叠 → 热点主题→事件反查结果清晰、无歧义。

---

## 8. 任务设想 vs 现状 偏差对照表（最重要）

| Phase 子项 | 任务设想 | 现状 | 处置建议 |
|---|---|---|---|
| 2-E-1 status 枚举 | pending/processing/resolved/ignored | active/verifying/processing/resolved/closed/deprecated | 🟡 复用 `deprecated`=忽略；放开状态机允许活跃态→deprecated |
| 2-E-1 操作日志 | 需建 operation_logs | `event_actions` + `audit_write` 已存在 | ✅ 直接复用 |
| 2-E-1 handler/resolution_note/updated_at | 建议新增 | 无对应列 | 🟡 决策：handler/note 复用 `event_actions`；`updated_at` 可选单列 |
| 2-E-2.1 列表运营字段 | id/title/risk_level/status/opinion_count/latest_time/region | **已基本具备**（另含 heat/trend/topic/region_name/影子风险） | 🟡 增量加 `alert_count`（可选） |
| 2-E-2.2 详情接口 | event/opinions/alerts/statistics | 已有 event/opinions/actions；**缺 alerts 与 statistics** | 🟡 增量加 `alerts[]` + `statistics{}` |
| 2-E-2.3 状态更新 | 新增 PATCH /status | **已存在**，状态机式+审计 | ✅ 扩展"忽略"可达性 + 允许 `note` 随状态变更 |
| 2-E-3 前端升级 | 状态筛选/卡片字段/详情抽屉/状态操作 | **大部分已实现** | 🟡 补 source_count/alerts/statistics 展示 + 绑 hot-topic |
| 2-E-4 热点→事件 | 新增 GET /events/hot-topic/{keyword} | 无 | ❌ 需新增（只读聚合，复用 EventOpinion） |
| RBAC | events:write 或 admin | `require_permission("events:write")` **admin 自动通过**(permissions.py:71) | ✅ 无需改 |

---

## 9. 改造范围建议（最小增量，复用优先）

**复用优先（禁止重建）**：
- 状态枚举 → 现有 6 态（用 `deprecated` 承载"忽略"）。
- 操作记录 → `event_actions` + `audit_write`。
- 列表/详情已有字段 → 不重复返回。
- 热点反查 → `event_opinions`（不重新计算）。
- RBAC → `events:write`（admin 自动放行）。

**需增量（Phase 2-E-2）**：
1. **列表 `alert_count`**（可选）：`LEFT JOIN alert_records` 计数，向后兼容（新增字段，不改旧字段）。
2. **详情 `alerts[]` + `statistics{}`**：
   - `alerts`：`SELECT alert_records WHERE event_id=?`（反向链路，只读）。
   - `statistics`：`{ opinion_count, source_count, latest_time, risk_distribution }` —— 由关联 opinions 聚合；`source_count` = distinct `source`；`risk_distribution` = 按 `risk_level` 计数；`latest_time` = `last_time`。**不新增存储，仅查询聚合**。
3. **状态更新增强**：扩展 `EventStatusUpdate` 加可选 `note` → 状态变更同时写一条 `note` 类型 `EventAction`；放开状态机允许 `active/processing → deprecated`（"忽略"）。
4. **热点主题→事件（2-E-4）**：新增 `GET /api/events/hot-topic/{keyword}`（只读）：定位包含该关键词的 opinions（`title ILIKE` 或 `EventOpinion` 关联），反查其所属 events，按 `opinion_count`/`last_time` 排序返回。复用 `EventOpinion`，零新依赖。

**字段新增决策（2-E-1，待确认）**：
- `handler` / `resolution_note`：**建议不新增列**，直接复用 `event_actions`（已有 `user_id`/`content`）。
- `updated_at`（最后处置时间）：**可选单列**，价值在于列表可按"最后处置时间"排序/展示；若不加，可用 `last_time`（舆情时间）近似。倾向**不加**，避免多余迁移。

---

## 10. 风险评估

| 维度 | 评估 |
|---|---|
| 风险评分模型 | ✅ 不触碰（仅读 opinion 聚合，不改 risk_score/risk_level 计算） |
| 采集链路 | ✅ 不触碰（聚合器接口不变，仅反向读 EventOpinion） |
| 预警生成逻辑 | ✅ 不触碰（仅反向读 `alert_records.event_id`，不改生成） |
| 事件聚合算法 | ✅ 不触碰（Phase 2-E 只读复用，不改 `_merge_condition`） |
| 接口契约 | 🟡 `EventOut`/`EventDetailResponse` 为**增量加字段**（向后兼容）；新增 `hot-topic` 为独立路径，不影响既有 |
| Dashboard | 🟡 `event_count = count(events) WHERE status != 'deprecated'`；若引入 `ignored` 需同步排除——**建议复用 `deprecated` 规避** |
| RBAC | ✅ 复用 `events:write`，admin 自动通过，无新增风险 |
| 基础设施 | ✅ 仍 FastAPI+Vue3+PostgreSQL，无 ES/Redis/MQ/Celery |

---

## 11. 待确认决策（暂停点）

进入 Phase 2-E-1 设计前，需你确认：

1. **状态枚举策略**：复用 `deprecated` 承载"忽略"（推荐，零新增枚举），还是新增独立 `ignored` 值？
2. **是否新增 `updated_at` 单列**：用于"最后处置时间"展示（倾向不加，复用 `last_time`/event_actions.created_at）。
3. **`statistics.source_count` 口径**：distinct `opinion.source`（推荐）还是 distinct `opinion.region_id`？
4. **hot-topic 匹配口径**：`topic_category` 精确匹配（如 education）→ 简单直接；还是 keyword 文本匹配（命中 monitoring 主题词的舆情→反查事件）→ 更贴合 Phase HotWord-1B 的"热点主题"语义？建议**两者都支持**：优先 `topic_category` 精确匹配，回退 keyword 文本反查。

> 以上确认后，将进入 Phase 2-E-1（模型/接口设计）→ 2-E-2（后端增强）→ 2-E-3（前端升级）→ 2-E-4（热点关联）→ 2-E-5（测试）→ 2-E-6（验收报告）。
> **本阶段严格只读，未改动任何代码/数据库/配置。**
