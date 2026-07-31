# Phase 2-E-4 Dashboard 热点主题联动实施报告

> 阶段：Dashboard 热点主题 → 事件运营联动（基于 2-E-2 后端 hot-topic 接口 + 2-E-3 前端升级）
> 约束遵守：不改后端/数据库/模型/迁移/采集/风险/告警/RBAC；不新增页面/表/字段/状态枚举；仅改 frontend/* + docs/*
> 验证：vite build + vue-tsc --noEmit + 生产库端到端 4 Case

---

## 1. 修改文件清单

| 文件 | 修改 |
|---|---|
| `frontend/src/utils/event.ts` | 新增 `EVENT_TOPIC_LABELS`(枚举值↔中文) + `topicValueFromLabel(label)` 反查 |
| `frontend/src/api/events.ts` | **新建**；封装 `getEventsByHotTopic(keyword)` → `GET /api/events/hot-topic/{keyword}` |
| `frontend/src/views/Dashboard.vue` | 词云点击 `wordcloudChart?.on('click')`（仅 hot 模式）→ 热点主题事件抽屉（el-drawer）；事件列表展示标题/风险/状态/热度/来源/时间；点击跳 `/event/{id}`；空/失败处理；懒加载 |
| `docs/Phase_2E-4_...md` | 本报告 |

**Git diff 范围确认**：仅 `frontend/*` + `docs/*`。**未触碰** `models/`、`migration/`、`collector/`、`risk/`、`alert/`、`dashboard_service.py`、后端任何文件。

---

## 2. 实现说明

### 点击入口
- Dashboard 词云组件 `wordcloudChart` 在 `onMounted` 注册 `click` 事件：
  ```ts
  wordcloudChart?.on("click", (params: any) => {
    if (wordMode.value !== "hot") return   // 仅热点主题模式生效，风险模式忽略
    const name = params?.name
    if (name) openHotTopic(name)
  })
  ```
- echarts-wordcloud 点击返回 `params.name` = 被点击词（中文主题词，如「教育」）。

### API 调用
- 新建 `api/events.ts`，复用 `@/api` 默认 axios 实例（继承 token 拦截器/401/403 兜底，未新增请求库）：
  ```ts
  export async function getEventsByHotTopic(keyword: string): Promise<EventListResponse> {
    const { data } = await api.get(`/events/hot-topic/${encodeURI(keyword)}`)
    return data
  }
  ```
- 懒加载：仅在用户点击词云主题词时触发请求；**页面初始化/刷新 Dashboard 不请求 hot-topic**。

### keyword 转换
- `HotKeyword.keyword` 是中文词（如「教育」）。`openHotTopic` 调 `topicValueFromLabel(keyword)` 转为枚举值（`教育`→`education`），优先命中后端第一优先 `topic_category` 精确匹配。
- 未命中映射时（如非主题词）原样传中文，由后端 ILIKE 兜底。

### 展示方式
- 新增 `el-drawer`（rtl，480px），标题「{主题词} 相关事件」。
- 事件卡片字段：标题 / 风险等级(pill) / 处置状态(pill) / 热度 / 来源数量 / 最新时间。
- 加载中 `v-loading`；空数据「暂无相关事件」；失败「加载失败，请稍后重试」。

### 路由跳转
- 点击事件卡片 → `goEventDetail(id)` → `router.push('/event/${id}')` → EventDetail.vue（`/event/:id` 路由，权限 `events:read`）。

---

## 3. 类型变化

- **未新增事件类型**：复用 2-E-3 已定义的 `EventItem`（含 `source_count?`）与 `EventListResponse`。
- `utils/event.ts` 新增 `EVENT_TOPIC_LABELS: Record<string,string>` 与 `topicValueFromLabel(label: string): string`（纯工具函数，无 schema 变化）。
- `api/events.ts` 返回类型 `EventListResponse`（已存在）。

---

## 4. 验证结果

### npm run build
```
vite build ✓ built in 15.63s
dist/assets/Dashboard-BYYXUAmc.js  113.98 kB │ gzip: 26.66 kB
```
部署：`python backend/_d.py` → 42 文件同步至 `backend/app/static`。
线上校验：`index.html → index-Ql1eedM2.js`；Dashboard 块含 `events/hot-topic`、`hot-topic`、`topicValueFromLabel`、`相关事件`、`暂无相关事件`、`加载失败，请稍后重试`。✅

### vue-tsc --noEmit
- **本次新增错误：0**（Dashboard.vue / api/events.ts / utils/event.ts / types 全部零错误）。
- 既存错误 9 个，分布在 4 个无关文件（OpinionDetailModal/BochaLeadReview/CollectionLog/Sources），与 2-E-3 阶段完全一致，非本次引入。

### 手工验证（生产库 opinion_db 端到端，mint JWT 实测）
| Case | 操作 | 结果 |
|---|---|---|
| 1 | 点击「教育」→ `GET /events/hot-topic/education` | HTTP 200，返回 **9 个**教育主题事件（topic=education，含热度/标题） ✅ |
| 2 | 不存在主题 `zZzNotExist` | HTTP 200，items=0/total=0 → 前端显示「暂无相关事件」 ✅ |
| 3 | 点击事件 → 跳 `/event/532` | `GET /events/532` HTTP 200，statistics 在线（source_count=1, risk_dist={high:0,medium:0,low:3}），路由存在可跳转 ✅ |
| 4 | 旧 Dashboard 功能 | build 成功 + vue-tsc 无新增错误 + Dashboard 仅 additive 抽屉/点击，KPI/图表/词云/快讯/预警原逻辑无回归 ✅ |

> 后端 2-E-2 代码已在线（hot-topic 返回 200 真实数据，详情返回 statistics/alerts），故端到端可实测。

---

## 5. 风险说明

| 项 | 说明 |
|---|---|
| 未修改后端 | 仅前端改动 + 1 个新前端 API 封装文件；后端 hot-topic 接口逻辑未触碰 |
| 未修改数据库 | 无 migration、无新表/字段/枚举 |
| 未影响事件流程 | 事件聚合/风险评分/预警/采集/RBAC 全部未触碰 |
| 未影响 Dashboard 原逻辑 | KPI/趋势图/来源图/地理图/快讯/预警滚动/风险词云模式均保持；仅 hot 模式新增点击→抽屉，risk 模式点击被 `wordMode !== 'hot'` 守卫忽略 |
| hot-topic 列表 source_count | hot-topic 接口复用 `_event_out`（不计算 source_count），抽屉中来源数量显示「-」；事件详情页 statistics.source_count 有真实值。属 2-E-2 设计既定行为，非缺陷 |
| 无头浏览器缺失 | 本环境无 headless 浏览器，点击交互通过「代码审查 + 构建 + 类型检查 + 生产端点实测 + 静态资源文案校验」五级验证覆盖 |

---

## 6. 未完成项

- **Phase 2-E-5/2-E-6**：测试与验收报告（本阶段任务范围仅至 2-E-4）。
- 既存 4 文件的 pre-existing 类型错误建议后续单独清理（非本阶段范围）。
