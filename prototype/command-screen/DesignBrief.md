# DesignBrief — 指挥大屏（Command Screen）

> 本文档是后续所有设计产物的基线。基于项目只读审查（未修改任何代码）产出。

## 1. 产品定位
- **所属系统**：舆情监测指挥平台（FastAPI 后端 + Vue3/ECharts 前端）。
- **本页角色**：独立的「指挥大屏」全屏页，挂在 `#/command-screen`（或 `/command-screen`），用于**大屏/LED 墙展示**，不承载复杂交互，只做"一屏看懂全局态"。
- **与现有 Dashboard.vue 的区别**：Dashboard 是给操作员用的驾驶舱（有筛选、可点击下钻）；本页是给**指挥者/参观者**看的"态势墙"，强调氛围、可读性、实时跳动感，弱化操作。

## 2. 目标用户
- 指挥中心值守人员、领导参观、值班大屏轮播。
- 观看距离 2–5 米，屏幕常为 1920×1080 / 2K / 4K 横屏。

## 3. 页面唯一目标
**在一屏之内，让观看者无需操作就能感知：当前舆情总量、风险水位、是否有未处置高危预警、实时舆情流与传播态势。** 任何会让人"看不懂"或"找不到重点"的设计都是失败。

## 4. 输出格式与精度
- 交付：高保真 HTML/CSS 原型（单文件可双击打开预览，内嵌模拟数据 + 轮询刷新演示逻辑）。
- 精度：可直接作为前端实现的视觉基线；标注设计 Token 与组件规范。
- 不修改项目源码；原型为独立演示产物。

## 5. 现有品牌 / 数据依据（来自审查）
全局态数据接口（真实存在，可直接对接）：
- `GET /api/dashboard/stats?days=7` → `total / today / high_risk / event_count / trend[] / keywords[] / sources[] / sentiments[] / regions[]`
- `GET /api/reports/overview?days=7` → `risk_rate / negative_rate / top_risky[] / events[]`
- `GET /api/alerts/records?handled=false` → 未处置预警（risk_level: low/medium/high/critical）
- `GET /api/events` → 事件列表（risk_level / opinion_count / status）
- `GET /api/propagation/graph/{event_id}` → 传播树（max_depth / distinct_sources / negative_ratio / sentiment_summary）
- `GET /api/collector/status` → 采集心跳（last_run / total_collected）

实时策略（关键约束）：**后端无 WebSocket/SSE，只能用轮询**。
- 实时跳动层（10–15s）：today、high_risk、未处置预警数、实时快讯流、预警滚动。
- 中频层（30–60s）：情感/风险分布、热点词云、地区分布、传播态势。

## 6. 风格基调（用户明确要求）
- 科幻感（Sci-Fi / HUD）、深色系、全屏、实时刷新、展示全局态。
- 不使用紫/蓝紫渐变、不使用三列 icon 卡片套路、不用 emoji 当 icon、不堆砌无意义占位。

## 7. 选定方向
基于「美学启动套件 · 数据终端」做科幻指挥中枢定制（见 DesignSystemManifest）。
- 主色：HUD 青（cyan）作为签名色，琥珀/红作为风险告警色，绿作为健康态。
- 签名元素：切角面板（notched corner）+ 细发光描边 + 背景网格 + 扫描线 + 等宽字体数据读数。

## 8. 待用户确认
- 布局结构方向（见 Wireframes.md 的 A/B/C 三方案，需选定其一进入高保真）。
