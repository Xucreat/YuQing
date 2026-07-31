# Phase 2-E-3 前端事件运营中心升级实施报告

> 阶段：前端升级（基于 Phase 2-E-2 后端接口增强）
> 约束遵守：不改后端接口 / 不改数据库 / 不改 Event 状态枚举 / 不新增页面 / 不重构已有事件流程 / Dashboard 联动留到 2-E-4
> 验证：vite build + vue-tsc --noEmit + 线上静态资源文案校验

---

## 1. 修改文件清单

| 文件 | 改动 |
|---|---|
| `frontend/src/types/index.ts` | 新增 `EventRiskDistribution`、`EventStatistics`、`EventAlert`、`EventDetail`；`EventItem` 增 `source_count?` |
| `frontend/src/utils/event.ts` | `EVENT_STATUS_OPTIONS` 增 `deprecated`(已忽略)；`eventStatusPill` 增 `deprecated` |
| `frontend/src/views/Events.vue` | deprecated 文案→已忽略；表格增「来源数」列；运营状态快捷筛选 chips(5 组，前端过滤)；`canChangeStatus` 放开 deprecated；处置按钮文案「忽略事件」 |
| `frontend/src/views/EventDetail.vue` | 本地接口增 statistics/alerts；新增「运营统计」面板 + 「关联预警」卡片；`canChangeStatus` 放开 deprecated；按钮文案「忽略事件」 |

**未触碰**：后端、数据库、Event 模型、状态枚举、其它页面。

---

## 2. UI 变化

### Events.vue（事件运营中心）
- **状态文案**：deprecated 由原回退值"deprecated" → 显示「已忽略」（`eventStatusLabel`/`eventStatusPill` 统一）。
- **来源数列**：表格在「关联舆情」后新增「来源数」列，显示 `row.source_count ?? '-'`；表 min-width 1520→1610px，空行 colspan 12→13。
- **运营状态快捷筛选**：表格上方新增 5 个 chip——全部 / 待关注(active+verifying) / 处理中(processing) / 已解决(resolved+closed) / 已忽略(deprecated)。**纯前端过滤当前页**（`displayedRows` computed），不改 API、不重构既有 status `<select>`。
- **处置弹窗**：状态按钮区新增「忽略事件」按钮（deprecated 项，文案为动作语「忽略事件」而非状态语「已忽略」）；`canChangeStatus` 对齐后端 `DEPRECATE_ALLOWED_FROM`，active/verifying/processing 可直接忽略。

### EventDetail.vue（事件详情）
- **运营统计面板**：新增（读 `event.statistics`，`v-if` 守卫），展示关联舆情数 / 来源数量 / 最新时间 / 风险分布（高/中/低三色 pill）。
- **关联预警卡片**：新增（读 `event.alerts`），表格展示标题 / 风险等级 / 状态 / 时间；无数据显「暂无关联预警」。
- **处置弹窗**：同 Events.vue，新增「忽略事件」按钮 + `canChangeStatus` 放开。
- **处置记录**：继续使用 `actions`（操作人/状态变化/备注/时间），未新增 handling 字段。

---

## 3. API 字段接入

| 字段 | 来源 | 接入位置 |
|---|---|---|
| `source_count` | `GET /events` 列表（2-E-2） | Events.vue 表格「来源数」列 |
| `statistics` | `GET /events/{id}` 详情（2-E-2） | EventDetail.vue 运营统计面板 |
| `statistics.risk_distribution` | 同上 | EventDetail.vue 高/中/低 pill |
| `alerts` | `GET /events/{id}` 详情（2-E-2） | EventDetail.vue 关联预警卡片 |

全部 optional 接入：字段缺失时不报错、不渲染对应面板（`v-if`/`?.` 守卫），保证向后兼容。

---

## 4. 构建结果

```
vite build ✓ built in 18.84s
dist/assets/Events-CqpcYIUz.js     41.57 kB │ gzip: 8.64 kB
dist/assets/EventDetail-f-o51kgq.js 28.23 kB │ gzip: 6.16 kB
```
部署：`python backend/_d.py` → 42 文件同步至 `backend/app/static`。
线上校验：`index.html → index-DnAKLHQv.js`（新入口）；Events 块含「已忽略/待关注/忽略事件/来源数」；EventDetail 块含「运营统计/关联预警/暂无关联预警/忽略事件」。✅

---

## 5. 类型检查结果

`vue-tsc --noEmit`：**Events.vue / EventDetail.vue / utils/event.ts / types/index.ts 零类型错误**。

既存错误（与本次无关，HotWord-1B 阶段已记录，超出范围未处理）：
- `OpinionDetailModal.vue`（3 处 string|undefined）
- `BochaLeadReview.vue`（1 处类型不匹配）
- `CollectionLog.vue`（2 处 running_count 不存在）
- `Sources.vue`（3 处属性不存在）

---

## 6. 风险与说明

| 项 | 说明 |
|---|---|
| 快捷筛选分页 | chips 为前端过滤，仅作用于当前页（受服务端分页限制）；精确单状态筛选仍可用既有 status `<select>`（走 API） |
| 后端联动 | 运营统计/关联预警面板依赖 2-E-2 后端返回的 `statistics`/`alerts`。当前生产 uvicorn 尚未重启加载 2-E-2 代码，面板会因字段缺失而不渲染（`v-if` 守卫，不报错）。待 2-E-6 部署后端后即正常填充 |
| 状态机一致性 | 前端 `canChangeStatus` 与后端 `DEPRECATE_ALLOWED_FROM` 完全对齐，不会出现前端放行而后端 409 的情况 |
| 兼容性 | 所有新字段 optional；旧后端返回无 source_count/statistics/alerts 时页面不崩 |

---

## 7. 未完成项（Phase 2-E-4）

- **Dashboard 热点词联动**：热点主题模式点击词云主题词 → 调 `GET /api/events/hot-topic/{keyword}` → 展示相关事件（属 2-E-4，本阶段按约束未做）。
- **生产后端部署**：2-E-2 后端代码需重启 uvicorn 方可使 statistics/alerts/hot-topic 接口生效（属 2-E-6 验收）。
- **既存类型错误**：4 个无关文件的 pre-existing 类型错误建议后续单独清理。
