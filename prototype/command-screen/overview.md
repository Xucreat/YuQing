# 指挥大屏 · 设计交付总览

## 做了什么
在不修改项目源码的前提下，为舆情监测平台设计了一块**科幻深色、全屏、实时刷新**的「指挥大屏」页，并完成可预览的高保真原型。

## 关键结论（来自项目只读审查）
- 平台是舆情监测指挥系统，后端有完整全局态接口（`/api/dashboard/stats`、`/reports/overview`、`/alerts/records`、`/events`、`/propagation/graph`、`/collector/status`）。
- **后端无 WebSocket/SSE，实时只能轮询**——这是大屏接入的核心约束，已在原型与文档中落实轮询节奏。
- 前端已有 `Dashboard.vue` 驾驶舱页，但**无独立大屏页**，本设计为新增页留出位置。

## 设计决策
- 方向：基于「数据终端」美学定制为科幻指挥中枢（HUD 青签名色 + 切角面板 + 网格背景 + 扫描线）。
- 布局：**A 中央战场三栏**（左 24% 指标/情感，中 52% 风险环+地区态势+传播图，右 24% 实时快讯+预警），顶栏 + 底字幕。
- 字体：Chakra Petch / Sora / JetBrains Mono（避开 Inter/Roboto/系统字体）。
- 图表用原生 SVG/CSS 实现，**零依赖、离线可开**，规避 CDN 风险。

## 质量
- 五道 QA 全部通过：AI 味 0/10、可访问性 5/5、层级节奏 4/4、交互状态 0 缺失。
- 修复项：对比度 Token 提亮（`#5B6B86`→`#8699B5` 过 WCAG AA）、列表改 `<ul><li>`、加 `aria-live`、按钮补 active/disabled 与 44px 目标、清理野生间距值。

## 交付文件
`prototype/command-screen/` 下：`index.html`、`DesignBrief.md`、`DesignSystem.md`、`Wireframes.md`、`QAReport.md`、`HandoffBundle.md`。

## 下一步
- 确认是否将 `index.html` 视觉移植为前端 `CommandScreen.vue`（接真实轮询接口）。
- 可选：把 SVG 图表换为项目既有的 ECharts 以统一技术栈。
