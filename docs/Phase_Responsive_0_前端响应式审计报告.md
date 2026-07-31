# Phase Responsive 0：前端响应式审计报告

## 0. 审计边界与方法

- 审计对象：`frontend/src`（Vue 组件、页面级 scoped CSS、全局 CSS、ECharts 封装）。重点页面为 Dashboard、Opinions、Events、Alerts、Propagation、DataManage 及 `/command-screen`。
- 方式：只读静态审计，结合模板、脚本、CSS、路由和组件调用关系检查；未启动浏览器验收，未修改业务代码、样式、组件结构，未安装依赖。
- 静态统计（`frontend/src`，包含图标/控件等非风险尺寸）：固定 `px` 尺寸声明 268 处；`min-width` 声明 59 处；`position:absolute` 19 处；`overflow:hidden` 40 处；含 `scale/translate` 的 transform 27 处。统计用于定位热点，不等同于缺陷数。

## 1. 当前响应式能力评级

**总体评级：C（部分具备，需专项改造后才能承诺平板/手机基础访问）。**

| 场景 | 现状 | 评级 |
|---|---|---|
| PC 1920×1080、1440×900、1366×768 | 主布局使用 flex，主区有 `min-width:0`，Dashboard 有 1100/760/480 断点；宽表可横向滚动。1366 宽度下内容会明显变窄但基本可用。 | B |
| 平板（约 768–1180） | 820 以下隐藏侧栏；Dashboard 会单列化；大屏地理面板在 1180 以下上下堆叠。但 Propagation 的 `el-col :span="8/16"` 没有平板/手机堆叠断点，Alerts/部分数据页筛选仍依赖固定宽度。 | C |
| 手机（约 320–767） | 主区 padding 已收窄，Dashboard 卡片可单列；但隐藏侧栏后没有替代导航，Propagation 仍保持左右列，Alerts 固定宽弹窗/筛选存在溢出风险，部分表格只能依赖组件默认滚动。 | D |
| 指挥大屏 | 独立 fixed 全屏容器，BaseChart/ChinaMap 通过 `useEcharts` 监听 window resize 和 ResizeObserver；布局会在 1180 以下调整，但根容器 `overflow:hidden`，小屏不是常规后台访问形态。 | B（大屏场景） |

## 2. 主要问题与风险清单

### P0（阻断级）

**未发现 P0。** 当前未见会导致所有终端无法启动、页面完全白屏或所有 ECharts 实例初始化失败的共性问题；风险主要集中在特定页面的平板/手机可用性。

### P1（应在响应式改造第一批处理）

1. **移动端无导航入口。** `AppLayout` 在 `max-width:820px` 直接 `display:none` 侧栏，仅保留 `router-view`；没有抽屉、底部导航或菜单按钮。用户可通过直达 URL 访问，但无法在手机上完成模块切换。见 `frontend/src/components/AppLayout.vue:681-684`。
2. **Propagation 移动端列布局不适配。** 页面固定使用 `el-col :span="8"` 与 `:span="16"`，没有 breakpoint 下改为 24/24；同时 `.propagation`、`.prop-layout`、`.detail-panel` 组合使用 `height:100%`、`max-height:calc(100vh - 140px)` 和 `overflow:hidden`，窄屏下左侧事件列表和右侧详情可能被压缩或裁切。见 `frontend/src/views/Propagation.vue:1-37,244-258`。
3. **Opinions/Events 表格总宽度远超手机视口。** Opinions 表格 `min-width:1686px`，Events `min-width:1520px`，列头还包含大量固定宽度；虽有横向滚动容器（Opinions `tbl-scroll`、Events `table-card`），但移动端可视区域只剩窄条，需明确 sticky 列、滚动提示或移动端字段裁剪策略。见 `frontend/src/views/Opinions.vue:94-111,574-589`、`frontend/src/views/Events.vue:111-124,596-598`。
4. **Alerts 固定宽弹窗与筛选控件存在手机溢出风险。** 规则/处置弹窗写死 `600px/480px`，记录筛选的两个 `el-select` 写死 `160px` 并叠加左 margin；没有移动断点下的 `width:calc(100vw - …)`、纵向表单或 filter flex-wrap 规则。见 `frontend/src/views/Alerts.vue:43-61,116-160`。
5. **DataManage 子页移动端策略不一致。** 聚合页 `.segmented` 是 `inline-flex` 且按钮有 20px 水平 padding；Keywords 表格卡片使用 `overflow:hidden` 而非横向滚动；Sources 子页虽有 `overflow-x:auto`，但表格 `min-width:1430px`。见 `frontend/src/views/DataManage.vue:94-118`、`frontend/src/views/Keywords.vue:321-322`、`frontend/src/views/Sources.vue:700-704`。

### P2（应在第二批处理）

1. **主布局存在固定侧栏与最大内容宽度。** `.sidebar` 为 fixed `246px`（收起 `78px`），`.main` 为 `margin-left:246px`、`max-width:1440px`、水平 padding `44px`；PC 缩放总体稳定，但 1366/平板可用内容宽度被侧栏和 padding 挤压，且 820px 才隐藏侧栏，过渡区间较窄。见 `frontend/src/components/AppLayout.vue:332-350,616-628,681-684`。
2. **Dashboard 图表和滚动区使用固定高度。** 图表盒为 200/220px，1100 以下部分改为 240px；滚动区在 200/220/240px 间切换，依赖 `overflow:hidden` 和绝对定位渐变遮罩。数据或字体增大时可能出现内容被裁切。见 `frontend/src/views/Dashboard.vue:538-555,586-599`。
3. **Dashboard 移动端态势条仍可能横向超出。** 760px 以下仅给 `.situation` 加 `flex-wrap`，内部 `.sit-kpis` 未 wrap；5 个 `min-width:54px` 指标加间距在 320px 视口上可能超过内容宽度。见 `frontend/src/views/Dashboard.vue:495-504,594-596`。
4. **Propagation 图表固定高度。** `.graph-box` 320px、`.mini-chart` 200px；图表能 resize，但容器高度不随手机内容流式增长。见 `frontend/src/views/Propagation.vue:269-271`。
5. **页面级绝对定位/隐藏溢出需建立白名单。** 主要风险点包括 Dashboard 滚动渐变遮罩、Events 风险菜单、Events 处置右栏、Opinions 搜索清除按钮、全屏大屏根容器。它们当前多为局部实现，但在响应式重排时容易遮挡或裁切。见 `frontend/src/views/Dashboard.vue:552-555`、`frontend/src/views/Events.vue:564-576,665-676`、`frontend/src/layouts/FullscreenLayout.vue:35-42`。
6. **Element Plus 全局 token 未提供移动断点覆盖。** `el-card__header/body` 固定 20/24px padding，`el-menu-item` 固定 44px 高度；`el-dialog` 仅统一圆角，没有全局 `max-width` 或移动边距策略。见 `frontend/src/styles/theme.css:130-142,236-266`。

### P3（低风险/维护性问题，发布优先级低于 P2）

1. 组件中存在大量图标、分隔线、按钮等合理的固定小尺寸；不应将这些尺寸机械改为百分比。
2. `theme.css` 的 `html { zoom:1.0; }` 只是明确取消旧缩放方案，未发现页面级 `transform:scale(...)` 适配；现有 transform 主要用于动画/交互，不构成整体缩放方案。
3. `Alerts.vue` 的 `.alerts { height:100% }` 和多个页面 `min-height:100%` 依赖父级高度，建议后续用内容流布局验收，避免在不同浏览器中出现高度未解析或空白区。

## 3. 分范围审计结果

### 3.1 全局布局（App、Layout、Sidebar、Header、Main）

- `App.vue` 将 `html/body/#app` 设为 `height:100%`；常规页面由 `AppLayout` 承载，全屏页面由 `FullscreenLayout` 承载，边界清晰。见 `frontend/src/App.vue:24-33`。
- `AppLayout` 使用 flex shell，侧栏 fixed、主区 `flex:1; min-width:0`，这是 PC 缩放的正确基础。主区没有固定 height，常规内容可自然向下滚动。
- 侧栏自身有 `overflow-y:auto`，可容纳长菜单；但 820px 以下整个侧栏隐藏且无替代导航，是移动可用性的核心缺口。
- Header 使用 `justify-content:space-between`，未设置 `flex-wrap`；标题较长或右侧采集按钮同时显示时，在中等宽度可能发生挤压。
- 主区 `max-width:1440px` 适合大屏阅读，但不是流式最大宽度策略；需确认是否希望 1920px 上留白，或改为 `width:min(100%,1440px)` 并统一 box-sizing。

### 3.2 页面级

| 页面 | 已有能力 | 主要风险 |
|---|---|---|
| Dashboard | 5 KPI 网格；1100 以下单列 widget、760/480 调整 KPI；图表容器宽度 100%。 | 固定图表/滚动高度；`.sit-kpis` 不换行；移动端长标题使用 ellipsis，信息可读性下降。 |
| Opinions | 过滤工具栏 `flex-wrap`；`tbl-scroll overflow-x:auto`；详情网格 1100 以下单列。 | 表格 `min-width:1686px`；table-card 自身 `overflow:hidden`；移动端主要只能横向浏览，筛选控件仍有多个 `min-width`。 |
| Events | 工具栏 `flex-wrap`；表格卡片 `overflow-x:auto`；处置弹窗在 860 以下改为纵向。 | 表格 `min-width:1520px`；搜索框 `min-width:264px`；风险菜单/处置右栏使用 absolute/fixed width，手机需重点验收。 |
| Alerts | `el-table` 使用 `min-width`/`width` 列定义，Element Plus 默认表格 wrapper 可滚动；表单字段多使用 100% 宽。 | 业务层没有显式 table overflow wrapper；筛选控件不成组换行；600/480px dialog 可能超出手机；`.alerts height:100%` 缺少内容流兜底。 |
| Propagation | 左右列表/详情使用 flex，列表内部 `overflow-y:auto`；图表 resize 已实现。 | `el-col` 没有响应式 span；根/布局/详情多处 `overflow:hidden`；固定 320/200px 图表高度；手机最易出现遮挡。 |
| DataManage | 通过 tab 聚合 Keywords、Sources、CollectionLog、BochaLeadReview；Sources 有横向表滚动。 | 聚合 tab 未做窄屏滚动/折行；Keywords 卡片 `overflow:hidden`；Sources 表格最小宽 1430px；各子页响应式能力不一致。 |
| 指挥大屏 | 独立 `position:fixed; inset:0`，不受后台侧栏/max-width 影响；1180 以下地理区域上下堆叠。 | 根容器 `width/height:100vw/100vh` + `overflow:hidden`，任何子布局超出都会直接裁切；这是大屏专用页面，不应作为手机后台替代入口。 |

### 3.3 ECharts

| 图表来源 | 初始化与 resize | 结论 |
|---|---|---|
| Dashboard | `echarts.init` 4 个实例；`window.resize` 统一调用 4 次 `chart.resize()`；卸载时移除监听并 dispose。见 `frontend/src/views/Dashboard.vue:330-390`。 | 有 resize，但没有 `ResizeObserver`，容器因侧栏折叠、字体变化或布局重排而改变尺寸时不一定立即刷新；容器固定高度。 |
| Propagation | SVG 实例手动 init；`window.resize` 调用 `chart.resize()`；卸载移除监听并 dispose。见 `frontend/src/views/Propagation.vue:184-238`。 | 有 resize/清理；没有容器观察；固定高度和 `overflow:hidden` 是主要风险。 |
| CommandScreen BaseChart | `useEcharts` 统一负责 init、window resize、`ResizeObserver`、dispose；容器 `width/height:100%`。见 `frontend/src/composables/useEcharts.ts:31-119`、`frontend/src/components/command-screen/BaseChart.vue:50-52`。 | 当前实现最完整。 |
| CommandScreen ChinaMap | 使用同一 `useEcharts`；地图容器宽高 100%，由父级 grid/flex 提供尺寸。见 `frontend/src/components/command-screen/ChinaMap.vue:80-103,475-476`。 | resize 链路完整，但父级 overflow hidden 仍可能裁切。 |

未发现其他页面调用 `echarts.init`；`rg` 结果仅覆盖上述四类实例（Dashboard 4 个、Propagation 1 个、BaseChart/ChinaMap 通过封装）。

### 3.4 CSS 与布局模式统计解读

- **固定宽/高**：268 处声明中绝大多数是图标、按钮、标签和表格列；高风险集中在侧栏 246/78px、表格 1686/1520px、Propagation 图表 320/200px、Dashboard 图表 200–240px、弹窗 600/480px。
- **`min-width`**：59 处；可接受的 `min-width:0` 较多，但页面级最小宽度集中在表格和筛选控件，应建立移动断点覆盖。
- **`position:absolute`**：19 处；主要是通知菜单、筛选菜单、滚动遮罩、时间线装饰和大屏浮层，没有发现用 absolute 搭建整页主布局的情况。
- **`transform`**：未发现整体页面缩放；27 处主要是动画/hover/菜单过渡。`html zoom` 为 1.0。
- **`overflow:hidden`**：40 处；局部卡片裁切可接受，但 Propagation 根布局、Fullscreen 根容器、Dashboard 滚动区和表格卡片需在每个断点验证。

## 4. Element Plus 适配结论

| 组件 | 当前使用 | 审计结论与建议 |
|---|---|---|
| `el-table` | Alerts、系统日志、Bocha 等；列大量 `width/min-width`。 | 组件本身支持横向滚动，但业务层应统一提供 `max-width:100%; overflow-x:auto` 容器，并检查 fixed/right 列与移动端触摸滚动。 |
| `el-card` | 全局圆角、header/body 固定 padding；Propagation 存在嵌套卡片。 | PC 合理；小屏应降低 padding，且避免在固定高度父容器内继续 `overflow:hidden`。 |
| `el-dialog` | Alerts/Keywords/Sources 等使用像素宽度。 | 需要统一 `width:min(…, calc(100vw - 24px))`、`max-height:calc(100vh - 24px)` 和 body 滚动规则；Alerts 是优先改造点。 |
| `el-form` | Alerts 使用 label-width 88/100px；Report/搜索页已有部分 top label。 | 手机应切换 `label-position="top"` 或在窄屏降低 label width，避免表单行被挤压。 |
| `el-menu` | 全局主题有样式覆盖，但当前后台导航主要是自定义 `router-link`，不是 `el-menu`。 | 主题覆盖不是当前侧栏风险来源；后续若改用 `el-menu`，需同步提供折叠/抽屉策略。 |

## 5. 推荐改造方案（后续实施，不属于本阶段）

1. 建立统一断点：`<=1180` 平板、`<=820` 手机导航、`<=600` 小屏；集中定义 gutter、card padding、dialog width，避免页面各自写阈值。
2. 先补移动导航：保留当前侧栏逻辑，增加手机菜单按钮/抽屉，确保登录后所有模块可切换。
3. 统一页面容器：主内容使用 `box-sizing:border-box; width:100%; min-width:0`；表格统一外层滚动容器，保留必要的最小列宽，不强行把复杂表格改成卡片。
4. Propagation 在平板/手机将左右 `el-col` 切换为 24/24，根布局改为内容流或可控的 `min-height`，只在列表/时间线内部滚动；图表高度改为 `clamp()` 或断点变量。
5. Alerts/DataManage/Keywords 优先补 filter wrap、tab 横向滚动、dialog `max-width` 和表单 top-label。
6. ECharts 保持统一封装：Dashboard/Propagation 迁移到 `useEcharts`，或至少增加 `ResizeObserver`，避免只监听 window resize；所有图表在容器显示/隐藏后调用一次 resize。
7. 对 `overflow:hidden` 建立逐项清单：确认是装饰裁切还是业务内容容器；业务内容默认 `overflow:auto`，装饰层才允许 hidden。
8. 完成浏览器验收矩阵：1920×1080、1440×900、1366×768、1180×820、1024×768、768×1024、390×844、320×568；覆盖侧栏折叠、表格横滑、弹窗、图表切换和大屏进入/退出。

## 6. 修改文件清单（建议的后续实施范围）

本阶段没有修改以下文件。后续按优先级建议：

- **P1**：`frontend/src/components/AppLayout.vue`（手机导航与主区断点）；`frontend/src/views/Propagation.vue`（列堆叠、滚动边界、图表尺寸）；`frontend/src/views/Alerts.vue`（筛选换行、dialog/form 响应式）；`frontend/src/views/Opinions.vue`、`frontend/src/views/Events.vue`（统一表格滚动和移动端工具栏）。
- **P1/P2**：`frontend/src/views/DataManage.vue`、`frontend/src/views/Keywords.vue`、`frontend/src/views/Sources.vue`（tab、表格和筛选）；`frontend/src/styles/theme.css`（Element Plus 移动 token/dialog/table 规则）。
- **P2**：`frontend/src/views/Dashboard.vue`、`frontend/src/composables/useEcharts.ts`、`frontend/src/views/Propagation.vue`（图表统一封装/ResizeObserver、固定高度变量化）。
- **P2（大屏单独验收）**：`frontend/src/layouts/FullscreenLayout.vue`、`frontend/src/styles/command-screen.css` 及 `frontend/src/components/command-screen/*`，仅处理小屏裁切和可用最小尺寸，不改变大屏视觉设计。

## 7. 不建议修改区域

- 不建议把所有固定 `px`（图标、按钮、状态点、表格关键列）机械改成百分比；这些是可读性和交互命中区域的稳定尺寸。
- 不建议用全局 `transform:scale` 或重新引入 `html zoom` 解决响应式；这会影响点击坐标、字体渲染和 ECharts 像素计算。
- 不建议在本阶段重做手机 App、改变后台信息架构、把复杂表格全部改为卡片或改动后端数据契约。
- 不建议删除大屏的 fixed 全屏容器、暗色主题和动效；大屏应保持独立场景，仅补充尺寸边界和裁切验收。
- 不建议直接改动 `frontend/dist*` 或 `backend/app/static/assets*` 生成物；代码和构建流程确认后再按发布流程重新生成。

## 8. 结论

当前系统已经具备 PC 端的基本流式布局、部分页面断点和完整的大屏 ECharts resize 链路，不能认定为“无响应式能力”。但移动端仍属于“可直达、不可完整导航/不可稳定操作”的状态；Propagation、Alerts、超宽表格和 DataManage 是前置改造的主要阻塞点。建议先完成 P1 项，再进行上述八尺寸验收，之后再评估是否需要更细的视觉压缩。
