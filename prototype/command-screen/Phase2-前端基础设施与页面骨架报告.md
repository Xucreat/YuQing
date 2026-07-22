# Phase 2 交付报告：指挥大屏前端基础设施与页面骨架

> 阶段目标：在**不改后端数据契约、不实现 WebSocket/SSE、不大改旧 Dashboard.vue** 的前提下，
> 搭建指挥大屏所需的前端基础设施（全屏布局、独立路由、暗色主题作用域、ECharts 封装、地图本地化、
> 轮询数据层）与页面骨架（三栏 + 地图 + 图表 + 信息流 + 底部滚动条）。
> 本阶段交付后即停止，**不追求 100% 视觉细节**。

产出时间：2026-07-22 ｜ 状态：✅ 已完成并通过类型检查与生产构建

---

## 1. 新增 / 修改文件清单

### 新增（19 个）

| 文件 | 作用 |
| --- | --- |
| `frontend/src/layouts/FullscreenLayout.vue` | 全屏布局容器（无侧边栏、无 1440 限宽、抵消 `html zoom:0.8`） |
| `frontend/src/views/CommandScreen.vue` | 大屏主页面（三栏 grid + 数据层装配 + 各图表 option） |
| `frontend/src/composables/useEcharts.ts` | ECharts 生命周期封装（init/dispose/resize/ResizeObserver）+ `registerMapOnce` |
| `frontend/src/composables/useCommandScreen.ts` | 轮询数据层（`usePolledResource` + stats/recent/alerts/feed 包装 + 刷新常量） |
| `frontend/src/types/command-screen.ts` | 大屏专属类型（复用后端 `DashboardStats`，仅补 `hot_keywords` 等） |
| `frontend/src/styles/command-screen.css` | `.command-screen` 作用域暗色主题变量与基础组件样式 |
| `frontend/src/components/command-screen/ScreenPanel.vue` | 通用面板（标题 + 徽标 + 插槽） |
| `frontend/src/components/command-screen/BaseChart.vue` | 图表容器（消费 `useEcharts`，watch option → setOption） |
| `frontend/src/components/command-screen/ScreenHeader.vue` | 顶部栏（标题 + 状态灯 + 实时时钟） |
| `frontend/src/components/command-screen/KpiBar.vue` | 5 张 KPI 卡（total/today/high_risk/event_count/sources） |
| `frontend/src/components/command-screen/ChinaMap.vue` | 中国省级 choropleth 地图（仅消费后端 `regions`） |
| `frontend/src/components/command-screen/FeedList.vue` | 信息流列表（recent / alert 两种 kind） |
| `frontend/src/components/command-screen/HotKeywordList.vue` | 热词榜（按 count 排序，trend 弱化为 ▲▼–） |
| `frontend/src/components/command-screen/ScreenTicker.vue` | 底部无限滚动字幕条 |
| `frontend/public/geo/china-provinces.json` | 中国省级 GeoJSON（本地化，34 省 + 南海诸岛，582KB） |
| `frontend/public/geo/README.md` | GeoJSON 来源 / 许可证 / 合规说明 |
| `prototype/command-screen/Phase2-前端基础设施与页面骨架报告.md` | 本交付文档 |

### 修改（2 个，均为**最小侵入**）

| 文件 | 改动 | 是否影响旧页面 |
| --- | --- | --- |
| `frontend/src/App.vue` | 增加 `isFullscreen` 分支：`route.meta.layout==='fullscreen'` 时用 FullscreenLayout，否则维持原 AppLayout / router-view | 否（旧分支逻辑不变） |
| `frontend/src/router/index.ts` | 新增 `/command-screen` 路由（懒加载 + `meta:{requiresAuth:true, layout:'fullscreen'}`）；复用现有 `beforeEach` 守卫 | 否（仅追加一条路由） |

> **AppLayout.vue、theme.css、Dashboard.vue 未做任何改动。**

---

## 2. 路由与布局设计

- **路由**：`/command-screen`，懒加载 `CommandScreen.vue`，`meta = { requiresAuth: true, layout: 'fullscreen' }`。
- **鉴权复用**：现有 `router.beforeEach` 已按 `meta.requiresAuth` + localStorage token 判断，未登录自动跳 `/login`。**未新增角色限制**，与既有权限体系一致。
- **布局切换**：`App.vue` 通过 `route.meta.layout === 'fullscreen'` 决定挂载 `FullscreenLayout`（内含 `<router-view/>`）还是既有 `AppLayout`。旧页面走原分支，零回归风险。
- **FullscreenLayout 关键实现**：
  - `position: fixed; inset: 0; width: 100vw; height: 100vh; overflow: hidden`。
  - `zoom: 1.25` 抵消 theme.css 全局 `html { zoom: 0.8 }`（0.8 × 1.25 = 1.0），保证大屏按真实视口 1:1 铺满。
  - 无侧边栏、无 `max-width:1440px`、无 admin padding。
  - 16:9 / 1920×1080 / 4K 下稳定（内部用百分比 grid + ECharts ResizeObserver 自适应）。

---

## 3. 暗色主题作用域设计

- 独立文件 `styles/command-screen.css`，所有变量与样式收敛到 **`.command-screen` 作用域**，**不改 theme.css**，不污染既有浅色主题。
- 色板（深空蓝黑）：`--screen-bg:#060b16`、主色 `--screen-primary:#22d3ee`（青）、语义色 rose/amber/teal/violet、多级墨色文本 `--screen-ink-1..4`、边框 / 辉光 / 圆角。
- **字体**：使用本地 / 系统字体栈（`"PingFang SC","Microsoft YaHei",...` + 等宽栈），**不引入 Google Fonts / 任何 CDN 字体**。
- 附带 `.cs-panel`/`.cs-panel-title`/`.cs-badge`/`.cs-dot` 状态点、暗色滚动条、`prefers-reduced-motion` 降级。

---

## 4. ECharts composable 设计

- 已确认项目使用 **ECharts 5.5.1**，旧 Dashboard.vue 采用 `import * as echarts` 全量导入。为保持一致且**不重构旧页面**，`useEcharts` 同样全量导入（最小封装，不引入 tree-shaking 基建）。
- `useEcharts(target?, options?)` 返回 `{ el, chart, init, setOption, resize, showLoading, hideLoading, dispose }`：
  - `onMounted` 自动 init，`onBeforeUnmount` 自动 dispose（防泄漏）。
  - 监听 `window.resize` + `ResizeObserver`，用 `requestAnimationFrame` 批处理，避免抖动。
  - `chart` 用 `shallowRef`，避免深响应式代理 ECharts 实例。
- 额外导出 `registerMapOnce(name, geoJson)`（幂等注册地图，避免重复注册）与 `echarts` 本体。

---

## 5. API 数据层设计

- 文件 `composables/useCommandScreen.ts`，复用既有 `@/api`（axios 单例，baseURL `/api`，自动携带 Bearer token）。**不重复定义后端类型**。
- 核心 `usePolledResource<T>(fetcher, intervalMs)` 返回 `{ data, loading, error, status, refresh, start, stop }`：
  - `data` 用 `shallowRef`，**失败时保留上一次成功数据**（不黑屏）。
  - `status`：`connecting | live | stale | down`，页面据此显示状态而非白屏。
  - **竞态防护**：seq 自增号，回调里 `if (mySeq !== seq || stopped) return` 丢弃过期响应。
  - **幂等 start()**：先清旧定时器再设新的，杜绝重复定时器。
  - `onMounted(start)` / `onBeforeUnmount(stop)`，重新进入页面自动重新拉取。
- 包装器：`useCommandScreenStats(days=7)`、`useCommandScreenRecent(limit=8)`、`useCommandScreenAlerts(limit=8)`、`useCommandScreenFeed()`。

---

## 6. 刷新策略实现

集中为前端常量 `REFRESH_INTERVALS`（`useCommandScreen.ts`），符合产品确认口径：

| 数据 | 前端轮询间隔 | 备注 |
| --- | --- | --- |
| stats（KPI/图表/地图/热词） | 30s | 对应 `/dashboard/stats?days=` |
| recent（最新舆情流） | 15s | 对应 `/dashboard/recent` |
| alerts（预警流） | 15s | 对应 `/dashboard/alerts` |
| 后端缓存 TTL | 10s | Phase 1 已实现的进程内 TTL 缓存 |

所有定时器在 `onBeforeUnmount` 清理；`start()` 幂等；无竞态、无重复定时器。

---

## 7. GeoJSON 来源与许可证

- **来源**：DataV.GeoAtlas（阿里云公共数据可视化服务）
  `https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json`
- **下载日期**：2026-07-22 ｜ **文件**：`frontend/public/geo/china-provinces.json`（582KB，35 features = 34 省级 + 南海诸岛）
- **许可 / 合规**：DataV.GeoAtlas 数据免费用于可视化；已在 `public/geo/README.md` 记录来源、下载命令、
  以及**对外发布需遵守《地图管理条例》**的合规提醒（内部大屏使用无阻塞）。
- **省名匹配**：GeoJSON 使用官方全称（如「河北省」），已校验与后端 `regions.region_name` 一致；
  **前端不做任何城市→省份映射**（省级上卷完全由 Phase 1 后端完成）。
- **无外部依赖**：不使用 DataV 组件 / CDN，运行时不请求任何外部地图资源，全部本地 `public/` 托管。

---

## 8. TypeScript 检查结果

- 命令：`npx vue-tsc --noEmit`
- **本阶段新增文件：0 类型错误。**
- 仅存在 **3 个既有错误**，均位于 `src/components/OpinionDetailModal.vue`（本阶段未改动）：
  - `OpinionDetailModal.vue(83,57 / 83,99 / 93,66): TS2345` — `string | undefined` 不可赋给 `string`（历史遗留，非本次引入）。

---

## 9. build 结果

- 命令：`npx vite build`，**EXIT=0**，2299 modules transformed。
- 大屏产物：`CommandScreen-*.css` 13.49kB、`CommandScreen-*.js` 30.01kB。
- 生产构建正常产出大屏与全部旧页面 chunk。

---

## 10. 旧页面回归结果

- 构建产物中同时存在 **Dashboard / Alerts / Events / Opinions / OpinionDetail / OpinionDetailModal / Propagation / Users / Login / EventDetail** 等旧页面 chunk，全部构建成功。
- **AppLayout.vue、theme.css、Dashboard.vue 零改动**；App.vue / router 仅追加分支与路由，旧页面路径逻辑不变。
- 结论：**无回归**。

---

## 11. 当前仍未完成的页面视觉模块（本阶段有意留白）

按「仅骨架、不追求 100% 视觉」的约束，以下为占位/基础态，后续阶段打磨：

1. KPI 卡的动效（数字滚动 / 环形进度）、同环比标识。
2. 地图的省份高亮联动（点击省份筛选右侧信息流）、飞线 / 散点叠加。
3. 图表精细视觉：渐变/发光调优、tooltip 定制、图例交互、空数据插画。
4. 信息流的进入动画、风险等级配色系统化、条目点击进详情。
5. 底部 Ticker 的分类图标、优先级配色。
6. 整体的加载骨架屏、断线重连的可视化提示细节。
7. 大屏适配的响应式断点微调（超宽/竖屏兜底）。

## 12. 下一阶段建议

- **Phase 3（视觉高保真）**：按 DesignSystem.md 打磨上述视觉模块；将图表 option 抽为可复用 preset。
- **实时性增强（可选）**：在轮询稳定后，评估 SSE（比 WebSocket 更轻，契合只读大屏）替换 recent/alerts 轮询；需后端新增端点，**本阶段明确不做**。
- **性能**：若首屏 ECharts 全量导入体积敏感，再评估按需引入（当前与旧页面一致，暂不动）。
- **地图交互**：省份点击联动信息流筛选，需后端支持按 region 过滤（新增查询参数）。
- **可观测**：为数据层增加简单埋点（拉取耗时/失败率），辅助后续 SSE 决策。

---

## 附：验证快照

- 类型检查：`npx vue-tsc --noEmit` → 仅 3 个既有 OpinionDetailModal 错误。
- 生产构建：`npx vite build` → EXIT=0，CommandScreen + 全部旧页面 chunk 产出。
- 文件核验：19 新增 + 2 修改 全部落盘；`public/geo/china-provinces.json` 校验含「河北省」、features=35。
