# Phase Responsive-1：前端基础响应式改造实施报告

## 1. 实施范围

本阶段按 Phase Responsive-0 审计报告执行，未修改后端、数据库、接口、路由信息架构或指挥大屏设计，未引入新依赖。现有工作区中与本阶段无关的改动保持不变。

## 2. 修改文件

- `frontend/src/components/AppLayout.vue`
- `frontend/src/views/Propagation.vue`
- `frontend/src/views/Alerts.vue`
- `frontend/src/views/Opinions.vue`
- `frontend/src/views/Events.vue`
- `frontend/src/views/DataManage.vue`
- `frontend/src/views/Keywords.vue`
- `frontend/src/views/Sources.vue`

## 3. 修改内容

### AppLayout 移动导航

- 将原有桌面导航抽为单一 `menuItems` computed 数据源；桌面侧栏和移动抽屉共同使用该数据，系统管理仍复用原有 `hasSystemPerm` 判断。
- `<=820px` 隐藏 fixed Sidebar，显示顶部“菜单”按钮。
- 新增 fixed 遮罩 + drawer 导航，支持点击遮罩、关闭按钮、路由项关闭；路由变化时自动关闭抽屉。
- 桌面侧栏宽度、收起状态、权限逻辑和导航路径保持不变。

### Propagation 响应式

- `el-col` 增加 `xs/sm/md/lg/xl` 响应式 span：小屏/平板为 24/24，`lg` 及以上保持 8/16。
- `<=1199px` 时根容器改为内容流，取消 `height:100%`、`max-height` 和根级 `overflow:hidden` 的裁切组合。
- 平板/手机事件列表改为有界纵向滚动，详情面板恢复自然高度；图表高度在 1199px、600px 以下分别收窄。
- `>=1200px` 未改变原有 PC 高度、列比例和滚动行为。

### Alerts 响应式

- 规则/处置 Dialog 宽度改为 `min(固定设计宽度, calc(100vw - 24px))`。
- 筛选卡片 body 使用 flex-wrap，移除筛选控件间依赖 inline margin 的布局。
- `<=600px` 时 select、日期选择器、刷新按钮占满可用宽度，误报开关独占一行。
- `<=600px` 时规则/处置表单切换为纵向 label，内容区取消固定左边距。

### Opinions / Events 表格

- 保留 Opinions `min-width:1686px`、Events `min-width:1520px` 的数据完整性策略。
- 增加 `max-width/min-width:0`、触摸滚动、`overscroll-behavior-x:contain` 和纵向 overflow 约束。
- 页面根容器在 `<=820px` 禁止自身横向溢出，横向滚动限定在表格容器内；未改为卡片布局。

### DataManage / Keywords / Sources

- DataManage tab 条带增加窄屏横向滚动，按钮不压缩。
- Keywords 表格卡片改为横向滚动，设置 760px 最小内容宽度，避免 `overflow:hidden` 裁切列内容；小屏筛选控件改为全宽。
- Sources 表格容器增加最大宽度、最小宽度和触摸滚动边界，保留原 `min-width:1430px`；小屏筛选控件改为全宽。

## 4. 构建与静态检查

- `npm run build`：通过，Vite 完成 2349 个模块转换和生产构建。
- `git diff --check`：通过，无空白错误。
- `npx vue-tsc --noEmit`：未通过，但错误均为既有业务类型问题，涉及 `OpinionDetailModal.vue`、`BochaLeadReview.vue`、`CollectionLog.vue`、`Sources.vue` 的原有类型定义；本阶段改动文件未新增该类错误。

## 5. 测试尺寸与结果

### 已完成的浏览器检查

使用本地构建预览页面，在以下尺寸检查登录页的页面横向滚动指标；7 个尺寸均未出现 `documentElement.scrollWidth > innerWidth`：

| 类型 | 尺寸 | 横向溢出 |
|---|---:|---|
| PC | 1920×1080 | 未发现 |
| PC | 1440×900 | 未发现 |
| PC | 1366×768 | 未发现 |
| 平板 | 1024×768 | 未发现 |
| 平板 | 768×1024 | 未发现 |
| 手机 | 390×844 | 未发现 |
| 手机 | 320×568 | 未发现 |

截图目录：`docs/phase-responsive-1-screenshots/`

- `login-1920x1080.png`
- `login-1440x900.png`
- `login-1366x768.png`
- `login-1024x768.png`
- `login-768x1024.png`
- `login-390x844.png`
- `login-320x568.png`

### 未完成的登录后验收

本地预览页可正常加载，但当前运行后端拒绝仓库文档记录的 `admin/admin123`，因此无法进入登录后页面完成以下交互验收：

- 手机抽屉导航打开、关闭及模块切换；
- Dashboard/Propagation ECharts 实际渲染和 resize；
- Opinions/Events 表格横向滚动；
- Alerts Dialog 打开、表单纵向排列；
- DataManage tab 和 Sources/Keywords 表格滚动。

这不是本阶段前端改造导致的登录失败；失败发生在改造前端页面之外的认证数据状态。未绕过认证，也未修改后端或数据库。

## 6. 未解决问题

1. 需要提供当前运行环境的有效测试账号，或在不修改生产数据的测试环境完成登录后验收。
2. `vue-tsc` 的既有类型错误尚未治理，本阶段未扩大范围处理。
3. 登录后页面的真实数据量、空数据、弹窗长文本和 ECharts 容器 resize 仍需在有效会话下复测。
4. 大屏页面未修改；本阶段未对 `/command-screen` 的小屏视觉策略做改变，仅保留原有独立全屏行为。

## 7. 结论

基础响应式改造已完成，生产构建通过，代码层已覆盖审计报告中的 P1 范围：移动端导航、Propagation 纵向布局、Alerts 视口适配、两张超宽业务表和 DataManage 子页滚动边界。登录后交互验收受当前认证环境阻塞，不能在本报告中宣称已完成，需在下一次具备有效测试账号后补验。
