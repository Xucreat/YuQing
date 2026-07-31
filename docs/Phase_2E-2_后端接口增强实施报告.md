# Phase 2-E-2 事件运营闭环后端接口增强实施报告

> 阶段：后端接口增强实施（基于 Phase 2-E-1 设计冻结方案）
> 约束遵守：不新增表 / 不新增 migration / 不改 Event·Opinion 模型字段 / 不改风险评分 / 不改采集 / 不改聚合算法 / 不改 Alert 生成逻辑
> 验证方式：pytest（test_events.py + test_dashboard.py）+ git diff 范围核验

---

## 1. 修改文件清单

| 文件 | 改动性质 | 说明 |
|---|---|---|
| `backend/app/schemas/event.py` | 增量 | 新增 `EventStatistics`、`EventAlertOut`；`EventOut` 增 `source_count: Optional[int]`；`EventDetailResponse` 增 `statistics` + `alerts` |
| `backend/app/api/events.py` | 增量 | ① 状态机放宽 `deprecated` ② 详情补 statistics/alerts ③ 列表补批量 source_count ④ 新增 `GET /hot-topic/{keyword}` |
| `backend/tests/test_events.py` | 增量 | 新增 8 个 2-E-2 测试 + `clean_2e2` fixture + 辅助函数 |

**未触碰**（git diff 确认）：`models/`、`migration/`（alembic）、`collector/`、`risk/`、`alert_service.py`、`dashboard_service.py`、`dashboard.py`、前端。

---

## 2. 接口变化

### 2.1 `PATCH /api/events/{id}/status`（状态机放宽）
- 请求/响应结构**不变**（`EventStatusUpdate{status}` / `EventOut`），权限 `events:write` + `audit_write` + `EventAction` 不变。
- **新增放行**：`active → deprecated`、`verifying → deprecated`、`processing → deprecated`（即"忽略事件"）。
- **保留**：`deprecated → active` 恢复；所有既有流转（active→verifying→processing→resolved→closed）；非法跳转（如 active→resolved）仍 409。
- 实现：新增常量 `DEPRECATE_ALLOWED_FROM = {"active","verifying","processing"}`，guard 中对 `new_status == "deprecated"` 单独判定源状态是否在集合内。

### 2.2 `GET /api/events/{id}`（详情增强，additive）
- 原有字段（event/opinions/actions）**不变**。
- 新增 `statistics: EventStatistics`：
  - `opinion_count`：实际加载的关联舆情数
  - `source_count`：`COUNT(DISTINCT Opinion.source)`（Python 派生自已加载 opinions，无额外查询）
  - `latest_time`：`MAX(Opinion.created_at)`
  - `risk_distribution`：`{high, medium, low}`，按 `Opinion.risk_score` 分桶，**复用 `EventRiskService.level_from_score`**（≥70 high / ≥40 medium / 其余 low，与线上风险模型同源）
- 新增 `alerts: List[EventAlertOut]`：反查 `alert_records.event_id`，`title` 映射 `opinion_title`（AlertRecord 无 title 列），按 `created_at DESC`。

### 2.3 `GET /api/events`（列表增强，additive）
- `EventOut` 新增 `source_count: Optional[int]`。
- 批量计算：复用 `list_events` 已有的 `event_opinions` 字典（为影子风险一次性加载全部候选事件的关联舆情），派生 `len({o.source})`，**零额外查询、无 N+1**。

### 2.4 `GET /api/events/hot-topic/{keyword}`（新增只读接口）
- 权限：`get_current_user`（只读，无需 `events:write`）。
- 匹配：第一优先 `Event.topic_category == keyword`（`func.lower` 大小写不敏感）；第二优先经 `event_opinions` 关联 `Opinion`，`title/content ILIKE '%kw%'`。
- 合并去重；`topic_category` 命中优先，其后追加仅 ILIKE 命中；组内 `heat_score DESC, last_time DESC`。
- 返回 `EventListResponse`（复用 `_event_out`，risk_level/trend/heat 口径与列表一致）。未知关键词返回 `[]`，不 500。
- **路由注册顺序**：声明在 `/{event_id}` 之前（紧随 `/aggregate`），避免路径参数误捕。

---

## 3. 状态机变化

```
既有：  active → verifying → processing → resolved → closed
        deprecated → active（恢复）

新增：  active    → deprecated   ┐
        verifying → deprecated   ├─ 「忽略事件」（2-E-2 放行）
        processing→ deprecated   ┘

保留禁止：active→resolved、active→closed、resolved→deprecated 等 → 409
```

未新增 `ignored` 枚举；`deprecated` 即"忽略事件"语义。前端显示文案「已废弃→已忽略」留待 2-E-3。

---

## 4. 测试结果

### 4.1 Phase 2-E-2 新增测试（8 个，全绿）
| 测试 | 覆盖点 | 结果 |
|---|---|---|
| `test_list_source_count` | 列表 source_count 字段存在 + 与 SQL `COUNT(DISTINCT source)` 一致 | ✅ |
| `test_detail_statistics_and_alerts` | 详情返回 statistics（opinion/source/latest_time/risk_distribution）+ alerts（title 映射 opinion_title） | ✅ |
| `test_detail_no_alert_returns_empty` | 无告警时 `alerts == []` | ✅ |
| `test_risk_distribution_buckets` | 阈值 70/99→high、40/69→medium、0/39→low | ✅ |
| `test_status_transitions` | active→deprecated 200、deprecated→active 200、active→resolved 409 | ✅ |
| `test_status_verifying_processing_to_deprecated` | verifying/processing→deprecated 200 | ✅ |
| `test_hot_topic` | education 精确命中、中文「教育」ILIKE 命中、不存在→[] | ✅ |
| `test_status_change_requires_write` | 无 events:write 用户→403；admin→200 | ✅ |

### 4.2 回归
- `tests/test_dashboard.py`：**19/19 通过**（dashboard.stats 结构无变化）。
- `tests/test_events.py` 既有用例：4 个此前通过的用例**仍通过**（test_diff_keyword_two_events / test_multiple_linked_same_event / test_risk_level_mapping / test_idempotent_rerun）。

### 4.3 既存失败（与本次改动无关，改动前即失败）
4 个既存失败，根因均为历史演进遗留，非 2-E-2 引入：
- `test_event_orm_persist`：断言 `not hasattr(got,"status")`，但 Event 模型已新增 `status` 列（ stale 断言）。
- `test_api_aggregate` / `test_api_list_pagination`：aggregate API 已改为后台任务（返回 task_id），测试仍断言旧同步字段 `created/linked`，且 TestClient 无法等待后台完成导致列表 total=0。
- `test_same_keyword_one_event`：受测试库残余数据影响（aggregator 聚合全库 opinion，非仅测试注入）。

> 基线对照：改动前 `4 failed / 4 passed`；改动后 `4 failed / 12 passed`（events）+ `19 passed`（dashboard）。失败集完全相同，无新增失败、无回归。

---

## 5. 风险影响评估

| 维度 | 评估 |
|---|---|
| 接口契约 | EventOut/EventDetailResponse 仅 additive 新增字段；PATCH 请求/响应结构不变；hot-topic 为全新路由。现有消费方不受影响 |
| 状态机 | 仅放开 deprecated 作为目标态；既有流转与 409 拦截保留 |
| Dashboard | 未触碰 dashboard 代码；`event_count`（`status != 'deprecated'`）语义不变；19 个 dashboard 测试通过 |
| Alert | 未触碰 alert_service / alerts API / AlertRecord 模型；git diff 无 alert 文件 |
| 风险评分 / 采集 / 聚合 | 明确未触碰（git diff 确认无 models/migration/collector/risk） |
| 性能 | statistics 复用已加载 opinions（零额外查询）；列表 source_count 复用已有 event_opinions 字典（零额外查询）；hot-topic 按需用户动作，event_opinions 有 FK 索引 |
| 路由顺序 | hot-topic 注册在 /{event_id} 前，已验证路径参数无误捕 |
| 测试技术债 | test_events.py 4 个既存失败建议后续单独修复（非本阶段范围） |

---

## 6. 未完成项 / 后续

1. **生产部署验证**（属 Phase 2-E-6）：本次仅 pytest 验证；uvicorn 重启 + 生产库 live smoke（`/hot-topic/education`、`/events/{id}` statistics/alerts、`PATCH /status` deprecated）留待 2-E-6 验收。
2. **前端升级**（Phase 2-E-3）：Events.vue 状态文案「已废弃→已忽略」、卡片来源数量、EventDetail.vue statistics/alerts 面板、Dashboard hot-topic 联动。
3. **既存测试修复**：test_events.py 4 个既存失败（stale 断言 + aggregate 异步化）建议单独清理，不在本阶段范围。
4. **handling 摘要**：按 2-E-1 决策采用方案 A（不新增后端字段，前端从 `actions[0]` 派生），已落实——未新增 handler/resolution_note/updated_at。
