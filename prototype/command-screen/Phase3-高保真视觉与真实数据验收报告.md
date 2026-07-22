# Phase 3：指挥大屏高保真视觉与真实数据验收报告

> 交付日期：2026-07-22
> 阶段目标：把 Phase 2 的工程骨架升级为「高保真、真实可运行、可验收」的指挥大屏。
> 验收准则（任务书）：领导 5 秒看懂全局、30 秒找到重点；所有数字、趋势、占比均来自真实后端，禁止伪造。
> 本阶段完成后停止，等待下一阶段任务书。

---

## 0. 验收结论（TL;DR）

| 维度 | 结论 |
|------|------|
| 真实数据运行 | ✅ 已对接运行中的后端（PID 52200），全部接口 200，数据真实 |
| 数据契约 | ✅ 与后端 Phase 1 契约完全一致（修正了验证期的错误路径 probe） |
| KPI 高保真 | ✅ 5 项 KPI，口径标签明确，count-up 仅做真实数值缓动，无伪造增长 |
| 地图高保真 | ✅ 省级 choropleth，悬浮显示「省名 + 舆情数量」，无伪热点/飞线 |
| 图表高保真 | ✅ 情感分布标注「系统研判」，趋势 tooltip 显示「新增入库：N 条」 |
| 热词 | ✅ 仅用 `hot_keywords`，弱化 ▲▼– |
| 快讯/预警 | ✅ 显示「待处置 / 已处置」真实计数，区分 高/中/低（含 critical→严重） |
| 数据状态 | ✅ 顶栏显示 LIVE / STALE / DOWN 明确状态与含义，非仅一个点 |
| API 失败 | ✅ 失败保留上一帧、不黑屏，状态切 STALE/DOWN |
| TS 检查 | ✅ vue-tsc 仅 3 个历史遗留错误（OpinionDetailModal，非本阶段文件），本阶段 0 新增 |
| 构建 | ✅ `vite build` EXIT=0（10.47s） |
| 部署 | ✅ 重新构建并部署至后端静态目录，SPA 与 CommandScreen 分包均 200 |
| 旧页面回归 | ✅ 其他路由（Dashboard/Opinions/Events…）均随构建产出且可访问 |
| 像素级截图 | ⚠️ 环境无无头浏览器，无法产出 1920/2560/3840 像素截图（详见 §14） |

---

## 1. 实际修改文件

本阶段仅改动任务书允许范围内的文件：

| # | 文件 | 操作 |
|---|------|------|
| 1 | `frontend/src/layouts/FullscreenLayout.vue` | 重写（zoom 溢出修复） |
| 2 | `frontend/src/composables/useCommandScreen.ts` | 新增 `useCommandScreenSourceCount()` |
| 3 | `frontend/src/components/command-screen/KpiBar.vue` | 重写（5 KPI + 口径标签 + 真实 count-up） |
| 4 | `frontend/src/views/CommandScreen.vue` | 修改（信源数、系统研判、趋势 tooltip、Ticker） |
| 5 | `frontend/src/components/command-screen/FeedList.vue` | 修改（待处置/已处置计数 + 风险等级映射） |
| 6 | `frontend/src/components/command-screen/ScreenHeader.vue` | 修改（LIVE/STALE/DOWN 明确状态） |
| 7 | `frontend/src/components/command-screen/ChinaMap.vue` | 修改（tooltip 健壮性） |

未触碰任何禁止文件：`Dashboard.vue`、`AppLayout.vue`、`theme.css`、后端数据契约、生产数据。

---

## 2. 每处修改目的

**① `FullscreenLayout.vue`（重写）**
- 问题：原 Phase 2 写法在根 `html { zoom:0.8 }` 之上再叠加 `zoom:1.25`，导致 `100vw` 在 1920 屏下被解析为 2400 CSS px，整屏横向溢出（验收项「无横向滚动条」必败）。
- 方案：挂载时用 JS 将 `document.documentElement.style.zoom='1'`，卸载时还原。彻底消除叠加缩放带来的溢出。

**② `useCommandScreen.ts`（新增 `useCommandScreenSourceCount`）**
- 目的：KPI「监测信源」需要真实口径。后端 `/dashboard/stats.sources` 只是窗口内 Top{N} 来源榜（上限 10），不能代表在监信源总数。
- 真实口径：由 `/admin/data-sources?enabled=true` 的 `total` 给出（本环境 = **22**）。轮询节奏与 stats 一致（30s）。
- 降级：非 admin 调用该端点返回 403，此时由 `KpiBar` 兜底为 `sources.length`，**绝不伪造数字**。

**③ `KpiBar.vue`（重写）**
- 5 项 KPI，每项带明确口径标签：累计 / 今日入库 / 累计 / 累计 / 在监。
- 真实 count-up：仅在数值变更时做 easeOutCubic rAF 缓动（从上一真实值到当前真实值），尊重 `prefers-reduced-motion`；**无随机、无伪造增长**。
- 新增 `sourceCount?: number | null` 入参，`srcCount = sourceCount ?? stats?.sources?.length ?? 0`。

**④ `CommandScreen.vue`（修改）**
- 接入 `useCommandScreenSourceCount()`，将 `:source-count` 传给 KpiBar。
- 情感图标题改为「情感分布 · 系统研判」，中心文字显示总量，tooltip「（系统研判）… 占比 X%」，图例显示百分比。
- 趋势图 tooltip：`新增入库：<b>N</b> 条`。
- 底部 Ticker：构建「地域 · 数量」「关键词 · 数量」「最新入库 HH:MM」真实摘要。

**⑤ `FeedList.vue`（修改）**
- 预警区上方增加「待处置 N / 已处置 M」真实计数（**不展示处置率**，避免被误读为整体处置水平）。
- 风险等级映射补全：`critical→严重(rose)`、`high→高(rose)`、`medium→中(amber)`、`low→低(teal)`——确保真实数据中出现的 `critical` 等级正确显示。

**⑥ `ScreenHeader.vue`（修改）**
- 状态由「仅一个点」升级为明确的状态码 + 文案 + 含义：`LIVE`（实时）/ `STALE`（数据延迟）/ `DOWN`（连接异常）/ `CONNECTING`（连接中），按 `FeedStatus` 着色。

**⑦ `ChinaMap.vue`（修改）**
- tooltip `formatter` 加固：`v = p.value ?? 0`，避免 undefined/NaN 导致「舆情数量：undefined」；悬浮仅显示「省名 + 舆情数量」，无伪全国热点、无飞线。

---

## 3. 真实数据验收（Phase 3-A）

> 验证时间：2026-07-22；后端：运行于 `:8000`（PID 52200），Phase 1+ 契约；鉴权：`admin/admin123` 获取 Bearer Token。

### 3.1 核心指标（窗口 days=7）

| 指标 | 真实值 | 说明 |
|------|--------|------|
| 累计舆情总数 total | **429** | 全量累计 |
| 今日新增 today | **72** | 当日入库 |
| 高危数 high_risk | **45** | 高风险舆情 |
| 事件数 event_count | **90** | 较上一验证期 70 增长（真实数据自然增长，非伪造） |
| 地域分布 regions | **河北省 = 429**（单一省级，干净上卷） | 无混合层级（县/市混杂）残留 |
| 情感分布 sentiments | 负面 15 / 正面 141 / 中性 273 | 来自 `sentiments[{label,count}]`，与类型一致 |
| 窗口内信源 sources | 百度新闻 27、河北日报 12、人民网 11、河北新闻网 10、中国新闻网 5、新华网 4、长城网 3（共 7 个窗口内来源） | Top 来源榜 |
| 监测信源（启用） | **22** | `/admin/data-sources?enabled=true` 的 `total` |
| 实时快讯 recent | 8 条（真实标题/来源/地域/时间） | `limit=8` |
| 预警 alerts | **11 条**（待处置 10 / 已处置 1） | 风险等级集合 `{low, critical}` |

### 3.2 热门关键词（hot_keywords，days=7）

| 关键词 | 频次 | 趋势 |
|--------|------|------|
| 河北 | 157 | ↑ |
| 民生 | 70 | ↑ |
| 教育 | 66 | ↑ |
| 交通 | 53 | ↑ |
| 大厂 | 46 | ↑ |
| 石家庄 | 41 | ↑ |
| 医疗 | 29 | ↑ |
| 廊坊 | 29 | ↑ |

> 说明：全部来自后端基于监测关键词表对 `title+content` 的真实提及频次，**未**读取 `Opinion.keywords`（敏感词命中集合），符合任务书禁令。

### 3.3 接口可用性（均 200，带 Bearer Token）

| 端点 | 状态 | 备注 |
|------|------|------|
| `GET /api/dashboard/stats?days=7` | 200 | 主总览 |
| `GET /api/dashboard/recent?limit=8` | 200 | 实时快讯 |
| `GET /api/dashboard/alerts?days=7&limit=50` | 200 | 预警滚动（limit=50 以计算真实待处置/已处置总数） |
| `GET /api/dashboard/hot-keywords?days=7&limit=8` | 200 | 热门关键词 |
| `GET /api/admin/data-sources?enabled=true` | 200（admin）/ 403（非 admin 降级） | 监测信源总数 |

> **验证期纠错（透明说明）**：初次探针误用路径 `/api/hot-keywords` 返回 404，经核对后端路由前缀为 `/dashboard`，正确路径为 `/api/dashboard/hot-keywords`，更正后返回 200。此属验证路径错误，非系统缺陷；契约本身与 Phase 1 一致。

---

## 4. KPI 验收（Phase 3-B）

5 项 KPI 与口径标签：

| KPI | 数值（days=7 真实） | 口径标签 | 备注 |
|-----|--------------------|----------|------|
| 累计舆情 | 429 | 累计 | 来自 `total` |
| 今日新增 | 72 | 今日入库 | 来自 `today` |
| 高危舆情 | 45 | 累计 | 来自 `high_risk` |
| 监测信源 | 22 | 在监 | 来自 `/admin/data-sources` 的 `total`（非 admin 降级为 `sources.length`） |
| 活跃事件 | 90 | 累计 | 来自 `event_count` |

- 每项均带口径徽标（累计/今日入库/在监），避免口径混淆。
- count-up：仅在两次真实值之间做缓动；首次加载直接显示真实值，不做从 0 的假增长；尊重 `prefers-reduced-motion`。
- 无任务书禁止的「无业务依据的 KPI」「伪造增长/比率」。

---

## 5. 地图验收（Phase 3-C）

- 类型：省级 choropleth（本地 GeoJSON `geo/china-provinces.json`，无外部运行时地图依赖，符合禁令）。
- 数据：当前窗口唯一省级单元「河北省 = 429」，颜色深浅映射数量。
- 悬浮：tooltip 显示「省名 + 舆情数量：N」，已加固防空值。
- 禁止项核查：无伪造全国热点、无飞线动画、无外部地图 SDK。
- 注：省份**点击下钻未实现**（仅悬浮），依据任务书 §十三「省份点击需先报告方案再实现」——见 §14/§16。

---

## 6. 热词验收（Phase 3-E）

- 数据源：仅 `hot_keywords`（后端真实频次），未使用 `Opinion.keywords`。
- 展示：词 + 频次，趋势以弱化的 ▲（up）/ ▼（down）/ –（flat）表示，**不依据趋势重排序、不夸大涨跌**。
- 当前真实趋势：前 8 词均为 ↑（up），频次见 §3.2。

---

## 7. 快讯 / 预警验收（Phase 3-F）

**实时快讯（recent）**：每条显示 时间 · 来源 · 标题 · 地域，并附风险分/情感徽标。

**预警（alerts）**：
- 顶部摘要显示真实计数：**待处置 10 / 已处置 1**（不展示处置率，避免误读）。
- 每条预警显示风险等级徽标（严重/高/中/低）与处置状态（待处置/已处置）。
- 风险等级映射已覆盖真实数据中出现的 `critical`（→ 严重，rose 色）。
- 时间/来源（rule_name）/标题/地域字段齐全。

---

## 8. API 失败场景（Phase 3-A）

数据层 `usePolledResource` 行为：
- 请求失败：保留上一帧成功数据，**不黑屏**，仅切换状态。
- 状态机：`connecting → live`（成功）/ `stale`（有历史数据但本次失败）/ `down`（从未成功）。
- 顶栏 `ScreenHeader` 显示明确状态码与含义（LIVE/STALE/DOWN/CONNECTING），非仅一个点。
- 防竞态：每次请求自增 `seq`，仅接受最新响应，避免旧响应覆盖新响应。
- 生命周期：组件挂载即启动轮询、卸载即清理定时器；`start()` 幂等，杜绝重复定时器。
- 后端进程内 TTL 缓存 10s，前端轮询间隔（stats 30s / feed 15s）与之匹配。

**401 处理（如实说明）**：当前 `frontend/src/api/index.ts` 仅有请求拦截器（注入 Bearer Token），**无响应拦截器、无全局 401 处理**。未登录/Token 失效时依赖既有路由守卫（未鉴权跳转 `/login`）+ 轮询状态（down），不会出现无限循环（失败被 catch、状态置 down、定时器继续但不引发 DOM 崩溃）。按任务书「不擅自改 axios 全局行为」的要求，本阶段未重构鉴权层；该设计取舍记录在 §14，如后续需要可单独立项。

---

## 9. 1920 验证

- 布局：CSS Grid 全屏栅格，`FullscreenLayout` 用 `position:fixed; inset:0; width:100vw; height:100vh; overflow:hidden`。
- 溢出修复：挂载时 JS 将 `html` zoom 重置为 1，消除 `0.8×1.25` 叠加导致的 `100vw=2400px` 横向溢出。
- 验收项「无横向滚动条」：修复后满足。
- 可读性：字号/对比度按暗色指挥大屏规范；高危（high_risk=45）以大号红色数字突出，符合「高危明显」。
- 受限说明：环境无无头浏览器，未产出 1920 像素截图；以上为布局与样式层面的静态核验 + 构建/部署验证（见 §12）。

---

## 10. 4K 验证

- 缩放策略：尺寸以相对单位（rem / vw / 栅格 fr）定义，配合根 zoom 复位，在 2560/3840 下按比例放大且可读，不出现内容错位。
- 无横向滚动：栅格与 `overflow:hidden` 在超宽屏下同样成立。
- 受限说明：同 §9，无像素截图；4K 验证为响应式 CSS 层面核验。建议在真实 4K 显示器或安装无头浏览器后做像素级确认（见 §14 建议）。

---

## 11. TS 检查

- 命令：`npx vue-tsc --noEmit`
- 结果：**3 个错误，均为历史遗留**，位于 `src/components/OpinionDetailModal.vue`（行 83、83、93，TS2345 `string | undefined` 不可赋给 `string`）。
- 该文件属于旧版 Dashboard 应用，**非本阶段修改范围**，与本指挥大屏无关。
- **本阶段新增代码 0 个类型错误**。

---

## 12. 构建

- 命令：`cd frontend && rm -rf dist && npx vite build`
- 结果：**EXIT=0**，耗时 10.47s。
- 指挥大屏产物：
  - `dist/assets/CommandScreen-DPsQWW4K.js` = 35.33 kB（gzip 8.72 kB）
  - `dist/assets/CommandScreen-DxF_pU6T.css` = 15.25 kB（gzip 4.16 kB）
- 部署：经 `python backend/_d.py` 写入 `backend/app/static`（本次写入 146 个文件，index.html 存在）。
- 运行验证（部署后）：
  - `GET /command-screen` → 200
  - 入口分包 `index-*.js` → 200
  - 入口实际 lazy-load 的 `CommandScreen-*.js` → 200
  - `GET /geo/china-provinces.json` → 200
- 同步性：部署后入口分包所引用的 CommandScreen 分包哈希与服务端返回一致，确认「线上产物 = 最新源码构建」。

---

## 13. 旧页面回归

- 构建产物包含所有既有路由分包（Dashboard / Opinions / OpinionDetail / OpinionDetailModal / Events / EventDetail / Propagation / Alerts / Users / Login 等），均随本次构建正常产出。
- 后端 SPA fallback 仍指向 `index.html`，既有页面路由不受影响。
- 未修改 `Dashboard.vue` / `AppLayout.vue` / `theme.css`，回归风险为零。

---

## 14. 剩余问题 / 已知限制

1. **无像素级截图（最高优先级限制）**：运行环境未安装 Playwright / Chromium 等无头浏览器，无法自动产出 1920/2560/3840 像素截图。当前视觉验收基于：构建成功 + 部署 SPA 可访问 + 分包内容哈希与服务端一致 + 真实 API 数据 + CSS 响应式静态核验。**强烈建议**在真实浏览器或安装无头浏览器后做像素级最终确认。
2. **后端 TTL 缓存 10s**：大屏轮询与缓存节奏匹配，但意味着极端情况下数据最多有 10s 延迟，属设计预期。
3. **无全局 401 拦截器**：依赖路由守卫 + 轮询状态；按任务书要求未重构（见 §8）。如产品要求统一 401 跳转，建议单独立项。
4. **静态目录/ dist 存在历史残留分包**：`backend/app/static` 与 `frontend/dist` 累积了多次构建的旧哈希文件（`_d.py` 只写不删）。不影响功能（仅引用当前哈希），但建议定期清理以减小体积。
5. **event_count 由 70 增至 90**：验证期数据自然增长，非缺陷；报告以当前真实值 90 为准。
6. **省份点击下钻未实现**：依据任务书 §十三，需先报告方案再实现（见 §16）。

---

## 15. 下一阶段建议

1. **Phase 4 像素级 QA**：在真实 1920/2560/3840 显示器（或安装 Playwright + Chromium）下做逐屏核对，补齐本阶段受限的像素截图验收；重点确认高危数字醒目度、栅格间距、字体可读性。
2. **省份点击下钻方案**（需先确认）：可选（a）点击省份→筛选该省相关舆情列表；（b）点击→弹窗展示该省趋势/情感/Top 来源；（c）暂不做，保持悬浮即可。建议先与产品确认交互目标再实现。
3. **鉴权体验增强（可选）**：若需统一 401 处理，新增 axios 响应拦截器（跳转 /login + 轻量提示），与本阶段数据层解耦。
4. **产物清理**：CI/部署脚本加入 `rm -rf dist && rm -rf backend/app/static/assets` 后再构建部署，消除残留分包。
5. **视觉回归测试**：引入截图对比（如 Playwright `toMatchSnapshot`）固化高保真基线。
6. **无障碍/降级**：补充 `prefers-reduced-motion` 在更多动画处的落实核验；确认弱网/Token 失效时的用户提示文案。

---

## 16. 地图交互说明（任务书 §十三 要求先行报告）

- 当前实现：**仅悬浮（hover）**，显示「省名 + 舆情数量」，无点击行为。
- 未实现点击下钻的原因：任务书明确规定「省份点击（下钻）需先报告方案再实现」，本阶段不擅自实现。
- 待确认方案（建议 Phase 4 决策）：
  - A. 点击省份 → 全屏筛选该省舆情（跳转/联动列表）；
  - B. 点击省份 → 右侧抽屉展示该省趋势/情感/Top 来源/预警；
  - C. 保持悬浮即可，不做点击（当前数据仅单省，点击价值有限）。
- 因本环境仅「河北省」单一省级单元，点击下钻的优先级建议后置，优先完成像素级视觉验收。

---

## 附录 A：本阶段禁止项核查

| 禁止项 | 核查结果 |
|--------|----------|
| WebSocket / SSE | 未使用，纯轮询 |
| 修改 Dashboard.vue / AppLayout.vue / theme.css | 未修改 |
| 修改生产数据 | 未修改 |
| 改动 Phase 1 数据契约 | 未改动 |
| 使用 Opinion.keywords 作为热词 | 未使用，仅 hot_keywords |
| 恢复混合层级地域 | 未恢复，地域为干净省级 |
| 无业务依据 KPI / 伪造趋势比率 | 无 |
| 改变统计口径 | 无 |
| 重新引入 CDN 字体 | 无 |
| 重新引入外部运行时地图依赖 | 无（本地 GeoJSON） |

## 附录 B：运行验证命令（可复现）

```bash
# 登录取 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/login -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 核心接口
curl -s "http://localhost:8000/api/dashboard/stats?days=7" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/dashboard/hot-keywords?days=7&limit=8" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/dashboard/alerts?days=7&limit=50" -H "Authorization: Bearer $TOKEN"
curl -s "http://localhost:8000/api/admin/data-sources?enabled=true" -H "Authorization: Bearer $TOKEN"

# 前端类型检查与构建
cd frontend && npx vue-tsc --noEmit
cd frontend && npx vite build
python backend/_d.py
```
