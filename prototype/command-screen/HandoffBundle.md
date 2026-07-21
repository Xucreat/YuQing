# HandoffBundle — 指挥大屏（Command Screen）

## 交付物清单
| 文件 | 用途 |
|------|------|
| `index.html` | 高保真原型（单文件，双击可预览；自包含，离线可用） |
| `DesignBrief.md` | 设计需求文档（产品定位/目标/数据依据） |
| `DesignSystem.md` | 设计系统 Token + 组件规范（DesignSystemManifest） |
| `Wireframes.md` | 低保真线框 3 变体（A 已选定） |
| `QAReport.md` | 五道质量检查汇总（可交付） |

> 本次仅做设计与原型，**未修改项目任何源码**。

## 开发者接入说明（接真实数据）
后端**无 WebSocket/SSE，只能轮询**（已审查确认）。原型内 `setInterval` 即轮询样板，把 mock 替换为：

```js
// 实时跳动层（10–15s）
const stats = await fetch('/api/dashboard/stats?days=7').then(r=>r.json());
const recent = await fetch('/api/dashboard/recent?limit=8').then(r=>r.json());
const alerts = await fetch('/api/alerts/records?handled=false').then(r=>r.json());
// 中频层（30–60s）
const ov = await fetch('/api/reports/overview?days=7').then(r=>r.json());
const prop = await fetch('/api/propagation/graph/{event_id}').then(r=>r.json());
```
字段映射（与审查一致）：
- KPI：total / today / high_risk / `alerts.length`(未处置) / event_count
- 风险环：`ov.risk_rate`；负面：`ov.negative_rate`
- 地区条：`stats.regions`（TOP10）
- 情感环：`stats.sentiments`（pos/mid/neg 归一）
- 传播图：`prop.nodes/links` + `max_depth/distinct_sources/negative_ratio`
- 快讯流：`recent`；预警：`alerts`（按 risk_level 着色）
- 采集心跳：`/api/collector/status`

## 集成到前端（Vue3 项目）
- 新建路由 `#/command-screen` → `CommandScreen.vue`，复用本原型视觉。
- 图表：本原型用原生 SVG/CSS 实现（零依赖、离线可用），可直接移植；若需与现有 ECharts 体系统一，可把地区条/情感环/传播图替换为 `echarts` + `echarts-wordcloud`（Dashboard.vue 已有样板）。
- 字体：Google Fonts（Chakra Petch / Sora / JetBrains Mono），需联网；离线降级为 system-ui/monospace，已在 CSS 配置 fallback。

## 已知 P2 微调（可选，不影响交付）
- 饼图内微标签 9px → 11px；正文行高显式 1.5。
- 小屏(<1280px)已做单列兜底，大屏场景无需处理。

## 实时策略提示
若未来要"真·实时"，需后端补 WebSocket/SSE（目前缺失）。轮询 10–30s 对指挥大屏已足够。
