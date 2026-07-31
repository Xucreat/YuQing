# Phase 2-E-1 事件运营闭环设计方案（设计冻结）

> 阶段性质：**设计冻结 / 仅输出方案**，本阶段不修改任何代码、数据库、配置、迁移、前端、接口。
> 设计基线：依赖 `Phase_2E-0_事件运营闭环改造前审计报告.md` 的只读审计结论。
> 核心原则：**优先复用已有能力，禁止重复建设**。现有 80%+ 事件运营能力已具备，本阶段仅做最小增量。

---

## 1. 当前能力复用分析

| 需求（来自 2E-1 指令） | 现状（已具备，直接复用） | 缺口 / 增量 |
|---|---|---|
| 事件状态枚举（含「忽略」） | `Event.status` 枚举：`active/verifying/processing/resolved/closed/deprecated`；`deprecated`=已废弃，即「忽略事件」语义 | **状态机流转需放开**：当前 `active/verifying/processing → deprecated` 被拦截（见 §4） |
| 最后处置人员 / 时间 / 说明 | `event_actions` 表已有 `user_id, action_type, content, old_status, new_status, created_at, event_id`；详情接口已返回 `actions` 列表（含 `username`） | 无需新字段；前端可从 `actions[0]` 派生，或后端补一个轻量 `handling` 摘要（可选，见 §3） |
| 事件详情 + 关联舆情 | `GET /api/events/{id}` 已返回 `opinions`、`total_opinions`、`actions` | 缺 `statistics`、`alerts` 两个**附加**子对象 |
| 事件状态更新（写操作日志） | `PATCH /api/events/{id}/status` 已存在，状态机式流转 + `events:write` 权限 + `audit_write` 写 `user_operation_logs` | 仅放宽 `deprecated` 作为目标态 |
| Alert ↔ Event 双向关联 | `alert_records.event_id` 已由 `sync_alert_events` 回填；`Alerts.vue` 已展示「关联事件」跳转 | 详情接口**反查** alerts 尚缺（只读聚合即可） |
| 操作记录存储 | `event_actions` + `audit_write`（写 `user_operation_logs`） | 直接复用，不改 |
| RBAC（events:write 或 admin） | `require_permission("events:write")` 对 superuser/admin 自动放行 | 直接复用，不改 |
| 热点主题 → 事件 | `Event.topic_category` 枚举（含 `education` 等）已存在；`event_opinions` 关联已存在 | 新增**只读** `GET /api/events/hot-topic/{keyword}` 聚合接口 |

**结论**：本阶段**不需要新增任何数据库表/列、不需要 migration、不需要改 Event 聚合算法、不需要改风险评分/预警/采集**。所有增量均为"已有模型的派生展示 + 一处状态机放行 + 一个只读聚合接口"。

---

## 2. 新增 / 增强接口设计

### 2.1 放宽状态机（修改 `PATCH /api/events/{id}/status` 的校验逻辑）
- 路由、权限、请求体 `EventStatusUpdate{status}` **不变**。
- 仅修改 `api/events.py:update_event_status` 中的流转 guard（详见 §4）。

### 2.2 增强 `GET /api/events/{id}`（详情）
- 响应 `EventDetailResponse` **新增两个附加字段**（additive，不破坏现有字段）：
  - `statistics: EventStatistics`（§3 定义）
  - `alerts: List[EventAlertOut]`（§3 定义）
- 计算逻辑在 handler 内只读聚合，不落库。

### 2.3 增强 `GET /api/events`（列表）
- 响应 `EventOut` **新增可选字段** `source_count: Optional[int]`（additive）。
- `list_events` 对当前分页的 events 做**一次** `GROUP BY` 批量计算 `source_count`（复用既有 event_opinions 批量取数模式，避免 N+1）。

### 2.4 新增只读接口 `GET /api/events/hot-topic/{keyword}`
- 用途：热点主题 → 相关事件（配合 Phase HotWord-1B 的「热点主题」模式）。
- 权限：`get_current_user`（只读，无需 `events:write`）。
- 参数：`keyword: str`（path）。可接受**主题枚举值**（如 `education`）**或中文主题词**（如 `教育`）。
- 匹配策略（§5 SQL）：
  1. **第一优先** `Event.topic_category == keyword`（大小写不敏感精确匹配，命中枚举值场景）。
  2. **第二优先** 经 `event_opinions` 关联 `Opinion`，`title ILIKE '%kw%' OR content ILIKE '%kw%'`（命中中文词场景）。
  3. 取并集、去重；排序 `heat_score DESC, last_time DESC`。
- 返回：`List[EventOut]`（复用 `_event_out`，保证 `risk_level/trend/heat` 口径与列表一致）。
- **路由注册顺序约束**：该路由必须在 `GET /{event_id}` 之前声明，否则路径 `hot-topic/xxx` 会被 `/{event_id}` 拦截（详见 §7 风险）。

---

## 3. Response Schema 变化（additive，向后兼容）

```python
# schemas/event.py 新增
class EventStatistics(BaseModel):
    opinion_count: int = 0            # 复用 event.opinion_count
    source_count: int = 0             # COUNT(DISTINCT Opinion.source)
    latest_time: Optional[datetime] = None   # MAX(Opinion.created_at)
    risk_distribution: dict = {"high": 0, "medium": 0, "low": 0}
    #   按 Opinion.risk_score 分桶（与风险模型一致）：
    #   >=70 -> high, >=40 -> medium, 其余 -> low

class EventAlertOut(BaseModel):
    id: int
    title: str                        # 映射 AlertRecord.opinion_title
    risk_level: str                   # AlertRecord.risk_level
    status: str                       # AlertRecord.status
    created_at: datetime

class EventHandlingOut(BaseModel):    # 可选轻量摘要（从 event_actions 派生）
    last_handler_id: Optional[int] = None
    last_handler_name: Optional[str] = None
    last_action_time: Optional[datetime] = None
    last_note: Optional[str] = None
```

变更点：
- `EventOut` 增加 `source_count: Optional[int] = None`（列表/详情通用）。
- `EventDetailResponse` 增加：
  - `statistics: EventStatistics`
  - `alerts: List[EventAlertOut] = []`
  - `handling: Optional[EventHandlingOut] = None`（可选；若前端直接从 `actions` 派生则**可不加**，以严守"禁止新增无必要字段"——见 §8 决策点）
- `hot-topic` 接口返回 `List[EventOut]`（复用现有 schema，零新增）。

> 兼容性说明：`EventDetailResponse`/`EventOut` 为**新增字段**，现有消费方（前端 `Events.vue`/`EventDetail.vue`、既有测试）仅做"字段存在性"断言或忽略未知字段，不会因 additive 字段报错。但 2-E-2 实施时需确认 `test_event_detail` 是否做了严格键集断言（参考 1A 审计发现的 `set(body.keys())==` 技术债），若有则一并放宽。

---

## 4. 状态机变化（最小增量）

现状流转（`api/events.py:60` `NEXT_EVENT_STATUS`）：
```
active → verifying → processing → resolved → closed
deprecated → active   # 恢复能力已具备
```
**缺口**：没有任何状态将 `deprecated` 作为 next，故 `active/verifying/processing → deprecated` 当前会触发 `409 Conflict`。

设计（仅放开「忽略」终点，其余一律不动）：

```python
# 新增常量（与 NEXT_EVENT_STATUS 并列）
DEPRECATE_ALLOWED_FROM = {"active", "verifying", "processing"}

# 修改 update_event_status 的 guard（约 api/events.py:251-257）
if new_status == old_status:
    return _event_out(db, event)
if new_status == "deprecated":
    # 允许各活跃态直接「忽略」；非活跃态（resolved/closed/deprecated）不允许再置 deprecated
    if old_status not in DEPRECATE_ALLOWED_FROM:
        raise HTTPException(409, "Invalid event status transition: ...")
elif new_status != "active" and NEXT_EVENT_STATUS.get(old_status) != new_status:
    raise HTTPException(409, "Invalid event status transition: ...")
# new_status == "active"：保持既有恢复逻辑（deprecated→active 等）
```

变更影响面：
- ✅ 新增：`active→deprecated`、`verifying→deprecated`、`processing→deprecated`（即"忽略事件"）。
- ✅ 保留：`deprecated→active` 恢复能力。
- ✅ 保留：所有既有流转（`active→verifying` 等）与 409 拦截（`active→resolved` 等非法跳转仍 409）。
- ⚠️ 注意：`dashboard.event_count` 当前为 `COUNT(events) WHERE status != 'deprecated'`（见 2E-0 审计）。一旦业务开始将事件置 `deprecated`，大屏事件总数会相应下降——这是预期行为，但需在 2-E-6 验收时显式确认语义。
- 显示文案：`EVENT_STATUS_LABELS["deprecated"]` 现为 `"已废弃"`；建议前端在 2-E-3 将其显示为「已忽略」以贴合"忽略事件"语义（后端枚举值 `deprecated` 与 `audit_write` 记录保持不变，避免契约/审计断裂）。

---

## 5. SQL 查询方案（全部只读，不落库）

### 5.1 事件 statistics（详情接口内执行）
```sql
SELECT
  COUNT(DISTINCT o.source)                                   AS source_count,
  MAX(o.created_at)                                          AS latest_time,
  COUNT(*) FILTER (WHERE o.risk_score >= 70)                 AS high,
  COUNT(*) FILTER (WHERE o.risk_score >= 40 AND o.risk_score < 70) AS medium,
  COUNT(*) FILTER (WHERE o.risk_score < 40)                  AS low
FROM event_opinions eo
JOIN opinions o ON o.id = eo.opinion_id
WHERE eo.event_id = :event_id;
```
- `opinion_count` 直接复用 `event.opinion_count`（与列表口径一致）。
- `risk_distribution` 分桶阈值**必须与线上风险模型一致**（≥70 high / ≥40 medium / 其余 low）。实施时优先复用现有 `risk_level` 映射函数（如 `EventRiskService.level_from_score` 或风险模型中的同一映射），避免两处阈值漂移。

### 5.2 列表批量 source_count（避免 N+1）
对当前页 events 的 id 集合 `ids`：
```sql
SELECT eo.event_id, COUNT(DISTINCT o.source) AS source_count
FROM event_opinions eo
JOIN opinions o ON o.id = eo.opinion_id
WHERE eo.event_id = ANY(:ids)
GROUP BY eo.event_id;
```
映射回 `EventOut.source_count`。复刻 `list_events` 现有"批量取 event_opinions"的模式。

### 5.3 Alert 反查（详情接口内执行）
```sql
SELECT id, opinion_title, risk_level, status, created_at
FROM alert_records
WHERE event_id = :event_id
ORDER BY created_at DESC;
```
- `title` 字段映射 `AlertRecord.opinion_title`（该表无 `title` 列，仅有 `opinion_title`/`event_title`；以触发该告警的舆情标题作为展示标题最贴合语义）。

### 5.4 hot-topic 聚合
```sql
-- 第一优先：topic_category 精确匹配（命中枚举值 education 等）
SELECT e.id FROM events e WHERE lower(e.topic_category) = lower(:kw);

-- 第二优先：经 event_opinions 关联 Opinion 文本匹配（命中中文词 教育 等）
SELECT DISTINCT e.id
FROM events e
JOIN event_opinions eo ON eo.event_id = e.id
JOIN opinions o        ON o.id = eo.opinion_id
WHERE o.title ILIKE '%' || :kw || '%'
   OR o.content ILIKE '%' || :kw || '%';
```
- 两结果集在 Python 中合并去重：优先展示 `topic_category` 命中的事件，其后追加仅 ILIKE 命中的事件；组内均按 `heat_score DESC, last_time DESC`。
- `keyword` 入参已通过 path 参数绑定，ILIKE 模式经占位符传递，无注入风险（与 `list_events` 现有 `ilike` 用法一致）。

---

## 6. 前端展示变化（2-E-3 / 2-E-4 的设计预案，本阶段不实施）

> 本节仅描述目标形态，供 2-E-3/2-E-4 实施参考；本阶段（2E-1）**不写前端**。

### 6.1 Events.vue（事件运营中心升级）
- **状态筛选**：现有筛选项已含 `deprecated`（显示「已废弃」）→ 改为显示「已忽略」。新增快捷分组：全部 / 待处理(active+verifying) / 处理中(processing) / 已解决(resolved+closed) / 已忽略(deprecated)。
- **事件卡片增强**：在现有主题/风险/热度/趋势/关联舆情数/处置状态基础上，新增显示 `source_count`（来源数量）。`latest_time` 已展示。
- **权限**：`events:write` 用户可见「开始处理 / 完成处理 / 忽略事件」操作；普通用户只读（沿用现有 RBAC 控制）。

### 6.2 EventDetail.vue（详情抽屉）
- 新增「事件态势」补充面板：来源数量（`statistics.source_count`）、风险分布徽标（`risk_distribution` high/medium/low）、最新舆情时间（`statistics.latest_time`）。
- 新增「关联预警」区块：列表展示 `alerts`（标题/风险/状态/时间），点击跳转预警详情。
- 「处置记录」已存在（时间线）；可从 `actions[0]` 派生最后处置人/时间/说明，无需新接口。

### 6.3 HotWord-1B × 2-E-4 联动
- `Dashboard.vue` 热点主题模式（`wordMode=hot`）下，点击词云中的主题词（如「教育」）→ 调用 `GET /api/events/hot-topic/{keyword}` → 弹出抽屉/侧栏展示近期相关事件（`EventOut` 列表），或 `router.push('/events?topic=education')` 复用列表筛选。
- 关键词传参策略：若前端持有枚举值（education）直接传；若持有中文词（教育）则传中文，由后端 ILIKE 兜底（见 §5.4）。建议在 `utils/event.ts` 的 `EVENT_TOPIC_LABELS` 反向映射，前端统一传枚举值以保证第一优先命中。

---

## 7. 风险影响评估

| 维度 | 影响 | 等级 |
|---|---|---|
| 接口契约 | `EventOut`/`EventDetailResponse` 仅 additive 新增字段；`PATCH /status` 请求/响应结构不变；`hot-topic` 为全新增量路由 | 低 |
| 状态机 | 仅放开 `deprecated` 作为目标态，所有既有流转与 409 拦截保留 | 低 |
| 大屏 `event_count` | 置 `deprecated` 后大屏事件总数下降（预期行为） | 中（需验收确认语义） |
| Dashboard / Alerts / Collector | 不涉及这些模块代码，零回归 | 无 |
| 风险评分 / 预警生成 / 采集 / 聚合算法 | 明确不触碰（指令硬约束） | 无 |
| 数据库 | 无 migration、无新表/列、无数据写入（statistics/alerts/handling 全为只读派生） | 无 |
| 性能 | 详情 +1 次 GROUP BY（O(1) 查询）；列表 +1 次批量 GROUP BY（复用既有模式）；hot-topic 为按需用户动作，`event_opinions` 已有 FK 索引 | 低 |
| 路由顺序 | `hot-topic/{keyword}` 若注册在 `/{event_id}` 之后，会被误判为 event_id（int 转换 422） | 中（实施时必须在前注册） |
| 测试严格键集 | 若 `test_event_detail` 对响应做 `set(keys())==` 严格断言，新增字段会导致失败（同类 1A 技术债） | 中（2-E-2 排查并放宽） |

---

## 8. 待确认决策点（设计冻结前的开放项）

1. **`handling` 摘要是否新增后端字段**：
   - 方案 A（推荐，最贴合"禁止新增无必要字段"）：**不新增**，`EventDetail` 前端直接从现有 `actions[0]` 派生最后处置人/时间/说明。
   - 方案 B：后端补 `handling: EventHandlingOut` 便利字段。
   - → 建议采用 **方案 A**。
2. **`deprecated` 前端显示文案**：后端枚举与审计记录保持不变，仅前端显示「已忽略」（建议 2-E-3 落实）。
3. **hot-topic 传参规范**：建议前端统一传 `topic_category` 枚举值（education 等），由 `utils/event.ts` 的标签映射反查，保证第一优先命中、避免 ILIKE 全表模糊。
4. **statistics 的 `risk_distribution` 阈值来源**：实施时复用现有 risk→level 映射函数，禁止另写一份阈值。

---

## 9. 测试计划（2-E-5 实施时执行）

### 后端
- **列表运营字段**：`GET /api/events` 返回项含 `source_count`；分页内各事件 source_count 正确（与直接 SQL 核对）。
- **状态更新（放宽）**：
  - `active→deprecated` / `verifying→deprecated` / `processing→deprecated` → 200，状态变更并记录 `event_actions` + `user_operation_logs`。
  - `deprecated→active` → 200（恢复能力保留）。
  - `active→verifying` / `verifying→processing` 等既有流转 → 200 不变。
  - `active→resolved`（非法跳转） → 409（既有拦截保留）。
  - 无 `events:write` 权限用户 → 403。
- **事件详情**：
  - 返回 `statistics`（`opinion_count/source_count/latest_time/risk_distribution` 正确）。
  - 返回 `alerts`（含该 event_id 的 alert_records；字段映射正确）。
  - 无关联 alert 时 `alerts == []` 不 500。
- **hot-topic**：
  - `keyword=education` → 返回 `topic_category=education` 的事件列表。
  - `keyword=教育`（中文）→ 经 ILIKE 返回相关事件（或前端改传 education 后第一优先命中）。
  - 不存在的 keyword → `[]` 不 500。
  - 排序校验：`heat_score DESC, last_time DESC`。
- **回归**：`GET /api/dashboard/stats` 结构/数值不变；`/api/alerts` 不受影响；采集链路不调用本阶段任何代码。

### 前端
- `npm run build` 成功。
- `vue-tsc --noEmit` 通过（`Dashboard.vue`/`Events.vue`/`EventDetail.vue` 类型正确；既有 4 个无关文件的 pre-existing 类型错误超出范围）。

---

## 10. 实施范围清单（供 2-E-2 起执行，本阶段不落地）

| 层 | 文件 | 改动 |
|---|---|---|
| 后端 | `app/api/events.py` | ① 放宽 `update_event_status` 状态机 guard（新增 `DEPRECATE_ALLOWED_FROM`）② 详情接口补 `statistics`/`alerts`（可选 `handling`）③ 列表 `EventOut` 补 `source_count` 批量计算 ④ **新增 `GET /hot-topic/{keyword}` 且注册在 `/{event_id}` 之前** |
| 后端 | `app/schemas/event.py` | 新增 `EventStatistics` / `EventAlertOut`（可选 `EventHandlingOut`）；`EventOut` 增 `source_count`；`EventDetailResponse` 增 `statistics`/`alerts` |
| 前端 | `views/Events.vue` | 状态筛选文案「已废弃→已忽略」；卡片增来源数量 |
| 前端 | `views/EventDetail.vue` | 增 statistics 面板 + 关联预警区块 |
| 前端 | `views/Dashboard.vue` | 热点主题词点击 → hot-topic 关联事件（2-E-4） |
| DB | — | **无 migration / 无新表 / 无新列** |
| 测试 | `tests/test_events.py`（或对应） | 按 §9 新增/调整 |

> 本阶段产出仅此设计文档。等待确认后，方进入 Phase 2-E-2（后端接口增强实施）。
