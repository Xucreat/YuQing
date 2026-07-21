# DesignSystemManifest — 指挥大屏（科幻深色 / Command Screen）

> 基于「美学启动套件 · 数据终端」定制为科幻指挥中枢。所有高保真产物必须严格遵循本文件。

## 1. 配色（oklch + hex 双标注）
深色基底，冷调 HUD 青为签名色，风险语义色分级。

| Token | 用途 | HEX | OKLCH |
|---|---|---|---|
| `--bg-void` | 全屏底（近黑偏蓝） | `#05070D` | `oklch(13% 0.018 255)` |
| `--bg-panel` | 面板底 | `#0A0F1A` | `oklch(16% 0.025 250)` |
| `--bg-panel-2` | 面板内分层 | `#0E1626` | `oklch(19% 0.03 248)` |
| `--bg-elev` | 浮起元素（tooltip/弹层） | `#121C30` | `oklch(23% 0.035 245)` |
| `--border-glow` | 面板发光描边 | `rgba(45,226,230,0.20)` | — |
| `--border-soft` | 次级分隔线 | `rgba(120,170,230,0.10)` | — |
| `--grid-line` | 背景网格 | `rgba(110,160,220,0.06)` | — |
| `--accent-cyan` | 签名主色（HUD 青） | `#2DE2E6` | `oklch(82% 0.13 195)` |
| `--accent-cyan-dim` | 主色暗态/描边 | `#1A9DA8` | `oklch(60% 0.09 195)` |
| `--accent-amber` | 警告（中风险） | `#FFB440` | `oklch(78% 0.14 75)` |
| `--accent-red` | 高危/严重（critical） | `#FF4D6D` | `oklch(66% 0.21 18)` |
| `--accent-green` | 健康/正向 | `#3DDC97` | `oklch(76% 0.16 160)` |
| `--text-hi` | 主文字/读数 | `#EAF2FF` | `oklch(95% 0.02 240)` |
| `--text-mid` | 次级文字 | `#9FB3D1` | `oklch(72% 0.03 240)` |
| `--text-lo` | 标签/弱信息 | `#8699B5` | `oklch(62% 0.035 245)` |

色彩权重：背景占 70%+，青色仅用于边框/关键读数/激活态（面积 <8%），红/琥珀只出现在告警条目（面积 <5%）。**不出现紫/蓝紫渐变**。

## 2. 字体配对（避开 Inter/Roboto/Arial/系统字体）
- **Display（标题/HUD 数字）**：`Chakra Petch`（Angular techno，HUD 感，仍清晰）。fallback：`"Chakra Petch", "Sora", sans-serif`。
- **Body（说明文字）**：`Sora`（几何无衬线，干净）。fallback：`"Sora", system-ui, sans-serif`。
- **Mono（数据读数/时间/ID）**：`JetBrains Mono`（等宽，读数稳定）。fallback：`"JetBrains Mono", ui-monospace, monospace`。
- 引入：Google Fonts `@import`。原型内置 fallback 链，离线时降级为 system-ui/monospace 不破版。

### 字号梯度（基于 16px 基准，比例 ≈ 1.25）
| Token | 值 | 用途 |
|---|---|---|
| `--fs-hero` | 56px / 700 | KPI 主读数 |
| `--fs-xl` | 32px / 600 | 区块大数 |
| `--fs-lg` | 22px / 600 | 面板标题 |
| `--fs-md` | 16px / 500 | 正文/列表 |
| `--fs-sm` | 13px / 500 | 标签/轴标（大写字母 + 字距） |
| `--fs-xs` | 11px / 500 | 角标/时间戳（Mono） |

## 3. 间距标尺（4px 基准）
`--sp-1:4px --sp-2:8px --sp-3:12px --sp-4:16px --sp-5:24px --sp-6:32px --sp-7:48px --sp-8:64px`
面板内边距统一 `--sp-4`（16px），区块间距 `--sp-5`（24px）。

## 4. 圆角 / 阴影 / 切角（签名）
- 面板圆角：`--radius: 4px`（克制，不圆润）。
- **签名切角**：面板右上/左下用 `clip-path` 切掉 14px 角，形成 HUD 框感（见组件）。
- 阴影：`--shadow-panel: 0 0 0 1px var(--border-glow), 0 8px 30px rgba(0,0,0,0.55)`。
- 发光：激活/关键元素 `box-shadow: 0 0 12px rgba(45,226,230,0.35)`。
- 背景：全屏 `--bg-void` + 固定网格（`linear-gradient` 画 40px 网格）+ 顶部到底部的极弱青色径向辉光 + 一条缓慢下移的扫描线（CSS animation，尊重 `prefers-reduced-motion`）。

## 5. 组件清单与状态规范
所有组件遵循切角面板 + 发光描边；状态至少覆盖 default / hover / 关键态。

### C1 — KPI 卡（HeroStat）
- 用途：today / high_risk / 未处置预警 / 总舆情 等大数。
- 结构：`[角标标签] [Hero 读数(Mono)] [同比/趋势微标]`。
- 变体：default / `is-critical`（红发光，读数红）/ `is-warn`（琥珀）/ `is-live`（带脉冲点）。
- 状态：default（青描边）、hover（描边变亮 + 轻微上浮）、`is-critical`（红脉冲动画）。

### C2 — 风险水位环（RiskGauge）
- 用途：risk_rate / negative_rate 环形进度。
- 变体：default / critical(>70%) / safe(<30%)。状态：加载中（环转动）、完成。

### C3 — 趋势折线（TrendLine，ECharts）
- 用途：trend[] 近 N 日舆情量。状态：loading（骨架）、data、hover（tooltip 高亮）。

### C4 — 地区分布条（RegionBars）
- 用途：regions[] TOP10 横向条形，条头带省名。状态：default、hover（高亮该条 + 显示计数）。

### C5 — 情感/风险分布（SentimentDonut，ECharts）
- 用途：sentiments[] 正/中/负 + risk 分层。状态：default、hover（扇区外扩）。

### C6 — 热点词云（KeywordCloud，echarts-wordcloud）
- 用途：keywords[] TOP10，字号映射 count，色映射风险。状态：default、hover（放大）。

### C7 — 实时快讯流（LiveFeed）
- 用途：`/dashboard/recent` 滚动列表。每条：`[时间 Mono][风险点][摘要][来源]`。
- 状态：default、new（进入时左侧滑入 + 顶部高亮条 1.2s 后消退）、hover（行底色微亮）。

### C8 — 预警滚动（AlertScroll）
- 用途：`/alerts/records?handled=false`。按 risk_level 着色（critical=红 / high=橙 / medium=琥珀 / low=青）。
- 状态：default、critical（红脉冲）、hover（展开 trigger_reason）。

### C9 — 传播态势（PropagationTree，ECharts graph）
- 用途：`/propagation/graph/{id}`。节点大小=传播量，颜色=risk。
- 状态：default、hover（节点高亮 + 邻居）。

### C10 — 状态条 / 时钟（StatusBar）
- 用途：顶栏系统名 + 实时时钟（Mono）+ 采集心跳（collector/status）+ 连接态（轮询中/已连接）。
- 状态：online（绿点）、syncing（青点呼吸）、offline（红点）。

### C11 — 滚动字幕（Ticker）
- 用途：底部跑马灯，汇总关键事件标题。状态：default（匀速滚动）、paused（hover 暂停）。

## 6. 交互状态全局规则
- 所有可聚焦元素：focus 可见环 `outline: 2px solid var(--accent-cyan); outline-offset:2px`。
- 悬停目标 ≥ 44px。
- 过渡动画统一 0.2–0.3s `ease`。
- `prefers-reduced-motion: reduce` 时：关闭扫描线/脉冲/跑马灯，数据仍刷新但无动效。
- 实时刷新：原型用 `setInterval` 模拟轮询（10–30s 节奏），并预留 `fetch('/api/...')` 接入注释。

## 7. 响应式
- 主目标：横屏大屏（≥1920×1080）。用 `clamp()` + `vw` 让字号/间距随屏自适应。
- 降级：<1280px 时右侧栏堆叠到下方；<768px 单列竖向滚动（大屏场景少见，仅兜底）。
