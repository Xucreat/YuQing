# 舆情指挥大屏 · 原型交付文档

> 原型文件：`prototype/command-screen/index.html`（独立 HTML，未改动项目任何代码）
> 风格：深空蓝青 · 科幻指挥风 / 全屏深色 / 实时刷新
> 日期：2026-07-21

---

## 一、DesignBrief（需求基线）

| 项 | 内容 |
|----|------|
| 产品 | 舆情分析系统（backend FastAPI + frontend Vue3）的"指挥大屏"页 |
| 目标用户 | 指挥中心值班人员、舆情研判负责人、现场大屏投屏 |
| 页面唯一目标 | 一屏总览全局舆情态势，实时感知高危/预警/热点地域 |
| 输出格式 | 高保真 HTML 原型（可直接双击预览，亦可作为真实页前端蓝本） |
| 精度 | 像素级高保真 + 真实数据字段映射 + 预留真实接口 |
| 风格约束 | 科幻感、深色系（用户明确指定）；子风格：深空蓝青 |
| 真实接口 | 复用既有 `dashboard` 模块：`/dashboard/stats`、`/dashboard/recent`、`/dashboard/alerts` |

> 注：用户在 DesignBrief 明确要求"深色系 + 科幻感"，故未触发强禁止清单中的默认审美规避（属有意识选择）。

---

## 二、DesignSystemManifest（设计系统）

### 配色（hex + oklch 双标注）
| Token | hex | oklch | 用途 |
|-------|-----|------|------|
| --bg-abyss | `#04070f` | `12% 0.02 250` | 页面底色（近黑深空） |
| --panel | `#0a1424` | `16% 0.03 240` | 面板底 |
| --panel-edge | `#16324f` | `24% 0.05 240` | 面板描边/网格 |
| --cyan | `#38e1ff` | `85% 0.14 200` | 主强调（辉光青） |
| --blue | `#4f8bff` | `66% 0.17 255` | 次强调（中性情感/链接） |
| --teal | `#2ee6a6` | `78% 0.16 170` | 正面情感 / 事件 |
| --rose | `#ff5d7a` | `68% 0.20 18` | 负面情感 / 严重预警 |
| --amber | `#ffc24b` | `83% 0.14 80` | 中危 / 监测信源 |
| --ink | `#e8f4ff` | `96% 0.02 230` | 主文本 |
| --ink-2 | `#9db4cc` | `72% 0.04 240` | 次文本 |
| --ink-3 | `#7e93a9` | `64% 0.04 240` | 辅助文本（已提亮至 AA） |

### 字体
- Display / 数字：`Rajdhani`（700/600）—— 科技感压缩无衬线
- 正文 / 中文：`Noto Sans SC`（400/500/700）
- 等宽 / 时钟 / 编码：`Share Tech Mono`
- 规避默认字体（Inter/Roboto/Arial/system）✅

### 间距标尺
4 / 8 / 12 / 14 / 16 / 18 / 24 / 32（px）。圆角：面板 10px、卡片 8px、徽标胶囊 999px。

### 组件规范
| 组件 | 变体 | 状态 |
|------|------|------|
| KPI 卡 | total/today/high_risk/event_count/sources（5 色条） | default / 数字 count-up / sparkline 更新 |
| 面板 Panel | 带四角装饰 + 标题条 | default（无交互，纯展示） |
| 情感环图 | donut | hover 高亮扇区 |
| 来源条形 | 横向 bar | hover 高亮 |
| 地图 | choropleth + effectScatter 涟漪 | hover 区域高亮；离线降级为榜单视图 |
| 地域榜单 | rank bar | 宽度过渡动画 |
| 实时快讯 / 预警 | feed item | default / fresh（新到高亮 slidein） |
| 徽标 Badge | pos/neg/neu/risk/crit/handled/pending | — |
| 底部滚动 | ticker | 无缝滚动（reduced-motion 下停止） |

---

## 三、线框（布局探索）

选定方案（指挥中心视觉重心在地图）：
```
┌───────────────────────────────────────────────────────────────┐
│ 舆情指挥中枢        🕐 时钟              ● 实时链路 · 延迟 ms    │ 顶栏
├──────────┬──────────┬──────────┬──────────┬───────────────────┤
│ 舆情总量 │ 今日新增 │ 高危舆情 │ 事件总数 │ 监测信源(路)        │ KPI 条(5)
├──────────┴──────────┴──────────┴──────────┴───────────────────┤
│ 情感分布   │          地域舆情热力(地图)          │ 地域榜单TOP  │
│ (donut)   │          + 热点涟漪效果散点          │ (rank bars) │
├──────────┤                                  ├─────────────┤
│ 来源分布   │──────────────────────────────────│ 实时快讯    │
│ (hbar)    │  近 7 日传播趋势 (area)            │ (feed)      │
│           │                                  ├─────────────┤
│           │                                  │ 预警滚动    │
│           │                                  │ (feed)      │
├──────────┴──────────────────────────────────┴─────────────┤
│ 实时解码: #关键词 声量 …  #地域 舆情 …  (底部滚动)             │ ticker
└───────────────────────────────────────────────────────────────┘
```
信息优先级：第一眼=地图热力+KPI；第二眼=趋势/榜单；第三眼=双 feed / ticker。
淘汰方案：A) 三栏等宽（地图不突出）；B) 上下分屏（竖屏利用率低）。

---

## 四、数据映射（真实字段 → 面板）

| 面板 | 数据源 | 字段 |
|------|--------|------|
| KPI·舆情总量 | `/dashboard/stats` | `total` |
| KPI·今日新增 | 同上 | `today` |
| KPI·高危舆情 | 同上 | `high_risk` (risk≥70) |
| KPI·事件总数 | 同上 | `event_count` |
| KPI·监测信源 | 同上 | `sources.length` |
| 情感分布 | 同上 | `sentiments[]` (label/count) |
| 来源分布 | 同上 | `sources[]` |
| 地域热力 + 榜单 | 同上 | `regions[]` (region_name/count) |
| 传播趋势 | 同上 | `trend[]` (date/count) |
| 实时快讯 | `/dashboard/recent` | id/title/source/sentiment/risk_score/region_name/created_at |
| 预警滚动 | `/dashboard/alerts` | id/rule_name/risk_level/opinion_title/trigger_reason/handled/created_at |
| 底部滚动 | 同上 | `keywords[]` + `regions[]` |

情感枚举 `positive/negative/neutral` → 正面/中性/负面；风险 `low/medium/high/critical` → 低/中/高/严重。

---

## 五、实时刷新与真实接口（已预留）

原型数据层 `index.html` 内已写好对接骨架，无需改项目代码即可演示：

- `API_BASE = ''` —— 留空用内置 mock 演化数据（双击即看）；填 `'http://localhost:8000'` 即轮询真实 `/dashboard/*`（需后端开启 CORS）。
- `WS_URL = ''` —— 留空不启用；填 `'ws://localhost:8000/ws/dashboard'` 即走 WebSocket 主动推送。已写好 `connectWS()` 骨架（按 `type: stats|recent|alert` 增量推送），取消 `boot()` 末尾注释即可启用。
- 轮询 `POLL_MS = 3000`；数字 count-up 动画、feed 高亮 slidein、地图涟漪实时刷新。
- 接口失败时自动回退 mock，保证大屏持续运行（顶栏状态显"模拟态"）。

---

## 六、QAReport（五道检查）

### 1. AI 味检测 —— 0/10 命中 ✅
无紫色渐变、无三列 icon 卡、非奶油底、近黑底但多强调色（非单色酸性绿/朱红）、非报纸零圆角、非默认字体、无 emoji、无 lorem、无 stock 图、非千篇一律 admin dashboard（指挥中心专属布局）。

### 2. 可访问性审查
- 对比度：主/次文本达标；辅助灰已提亮至 `--ink-3:#7e93a9`（≈5.6:1，AA）；危急徽标改深字（≈6:1）。✅
- 语义化：`<header>/<main>/<footer>` 地标齐备，`<h1>` 唯一。✅
- 键盘/动效：无交互控件（只读大屏），已加 `prefers-reduced-motion` 降级。✅
- 表单：不适用。

### 3. 层级与节奏
字号梯度 42→26→16→13→11（相邻比≥1.2）；色彩 60:30:10（深底+青+语义点缀）；地图为核心视觉重心。✅（P2：feed 行高可微调）

### 4. 交互状态
原型为只读展示，无 button/link/input，状态矩阵 N/A。✅（建议后续加钻取交互时补齐 hover/active/focus/disabled）

### 5. 终检汇总
- 过渡动画：rank 条 `.8s` 略长（建议 0.3–0.5s，P2）；其余微交互 OK。
- 反馈即时性：数字/feed 即时动画 + 3s 轮询。✅
- 悬停目标 ≥44px：无点击目标，N/A。
- **交付判定：可以交付**（无 P0；P1 已全部修复；P2 为可选优化）。

---

## 七、后续接入建议（给开发）
1. 真实页建议用 ECharts + 项目现有 `echarts` 依赖，复用本原型图表 option。
2. 后端补一个 WebSocket 端点推送 `stats/recent/alert` 增量，前端替换 `connectWS()` 占位。
3. 地域名匹配：本原型用 `stripSuffix` 对齐 DataV GeoJSON；真实数据若存全名（如"广东省"）可直接匹配。
4. 大屏适配：原型用 `100vw/100vh` 流体栅格；投 4K 时可整体 `transform: scale()` 或改 `:root` 间距标尺。
