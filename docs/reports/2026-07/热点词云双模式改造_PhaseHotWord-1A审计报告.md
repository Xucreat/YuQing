# Phase HotWord-1A：热点词云双模式改造 · 实施前只读审计报告

- 审计时间：2026-07-31
- 审计范围：驾驶舱「热点词云」全链路（后端 API / Service / 数据源 / 前端渲染 / 数据现状）
- 审计性质：**只读**。未修改任何代码、数据库、配置；数据库仅执行 SELECT 聚合查询。
- 生产库：`postgresql://opinion_user@127.0.0.1:5432/opinion_db`

---

## 0. 结论速览（先看这里）

| 编号 | 结论 | 影响 |
|---|---|---|
| C-1 | **模式2 的后端逻辑已存在且已上线**：`get_hot_keywords()` 即「monitoring 关键词 + 时间窗口」统计，且 `/dashboard/stats` 已在 `hot_keywords` 字段中一并返回 | 后端可近似零改造，改造重心在前端 |
| C-2 | 模式1（现状）**没有时间窗口**，全量统计，与卡片顶部 7/14/30 天切换器语义冲突 | 用户切天数词云不变，属既有体感缺陷 |
| C-3 | 模式1 数据覆盖率极低：**861 条有效舆情中仅 109 条（12.7%）** 的 `keywords` 字段非空 | 词云仅代表 1/8 样本 |
| C-4 | 模式1 TOP1 是 `群体`（43 次），但该词 `weight=0`（语境词非危害词） | 「风险关键词」语义被稀释 |
| C-5 | 若模式2 直接用现成 `hot_keywords`，**地域词会霸榜**（`廊坊` 297 断层第一） | 必须按 `category='主题'` 过滤，否则「热点主题」退化成「地域榜」 |
| C-6 | 两种模式字段名不一致：模式1 `{word,count}` vs 模式2 `{keyword,count,trend}` | 前端需做归一化适配层 |
| C-7 | 前端 `DashboardStats` 类型未声明 `hot_keywords`（只在 `command-screen.ts` 里声明） | 需补类型，否则 TS 报错 |

---

## 一、后端审计

### 1.1 Dashboard API 层

**文件路径**：`backend/app/api/dashboard.py`

路由挂载：`dashboard_router = APIRouter(prefix="/dashboard", ...)`，由 main 以 `prefix="/api"` 挂载 → 实际路径 `/api/dashboard/*`。
鉴权：路由级 `dependencies=[Depends(get_current_user)]`，**仅校验登录，无 `require_permission` 细粒度权限**。

与词云相关的两个端点：

| 端点 | 函数名 | 行号 | 参数 | response_model |
|---|---|---|---|---|
| `GET /api/dashboard/stats` | `dashboard_stats` | L38-55 | `days: int = 7`（ge=1, le=90） | `DashboardStatsResponse` |
| `GET /api/dashboard/hot-keywords` | `dashboard_hot_keywords` | L78-89 | `days: int = 7`、`limit: int = 10`（le=50） | `HotKeywordsResponse` |

> 注：`hot-keywords` 端点的 docstring 明确写着「基于监测关键词表对窗口内 title+content 的真实提及频次，**不读取 Opinion.keywords**」——这正是 HotWord-1 模式2 想要的口径。

### 1.2 Service 层

**文件路径**：`backend/app/services/dashboard_service.py`

关键常量（L48-52）：
```python
HIGH_RISK_THRESHOLD = 70
TOP_KEYWORDS = 10          # ← 词云 TOP N 硬编码在此
TOP_SOURCES = 10
```

#### (A) 模式1 现状逻辑：`get_dashboard_stats()` 内的 keywords 段（L363-381）

```python
# keywords：[兼容字段] 全量，来自 opinions.keywords（敏感词命中集合）
raw_keywords = (
    db.execute(
        select(Opinion.keywords).where(Opinion.geo_filtered.isnot(True))
    ).scalars().all()
)
counter: Counter = Counter()
for raw in raw_keywords:
    for kw in (raw or "").split(","):
        kw = kw.strip()
        if kw:
            counter[kw] += 1
keywords = [
    {"word": word, "count": count}
    for word, count in counter.most_common(TOP_KEYWORDS)
]
```

口径确认：

| 维度 | 实际情况 |
|---|---|
| 数据来源 | `opinions.keywords`（逗号分隔字符串） |
| 时间窗口 | **无**，全量历史（`days` 参数对本字段完全无效） |
| 过滤条件 | 仅 `geo_filtered IS NOT TRUE`（Phase X-History-1B 地域污染排除） |
| 计数方式 | Python 侧 `Counter`，按「出现该词的舆情条数」累加（每条舆情内同词只出现一次，天然去重） |
| 排序/截断 | `most_common(10)`，已按 count 降序 |
| 输出结构 | `[{"word": str, "count": int}]` |

⚠️ **对原始需求描述的一处修正**：文档称候选词是「keywords 表 `type='sensitive'`」，实际并非运行时读取词表，而是**读取历史写入的快照**。`opinions.keywords` 由采集时的 `RuleFallbackProvider.analyze()` 落库（`backend/app/services/ai/fallback.py` L72-127，`keywords=hits`），hits 包含所有命中词、**不论 weight 是否为 0**。因此：
- 词库后续停用/删除某敏感词，历史词云**不会回溯变化**；
- `weight=0` 的语境词（群体/维权/投诉/舆情）同样会进入词云。

#### (B) 模式2 已存在的逻辑：`get_hot_keywords()`（L562-636）

```python
def get_hot_keywords(db: Session, days: int = 7, limit: int = 10) -> dict:
    keywords = get_monitoring_keywords(db)          # ← monitoring 词表
    if not keywords:
        return {"items": [], "days": days}          # 空数据稳定返回，不 500
    today_date = db.scalar(select(func.current_date()))
    window_start = today_date - timedelta(days=days - 1)
    prev_start   = window_start - timedelta(days=days)
    sub = select(func.unnest(pg_array(list(keywords))).label("kw")).subquery()
    pattern = func.concat("%", _like_escape(sub.c.kw), "%")
    # JOIN opinions ON (title ILIKE pattern OR content ILIKE pattern)
    # 窗口内计 cur，前一等长窗口计 prev → trend = up/down/flat
```

口径确认：

| 维度 | 实际情况 |
|---|---|
| 候选词源 | `keyword_service.get_monitoring_keywords()` → `keywords` 表 `type='monitoring' AND is_enabled=true`（60s TTL 进程缓存；表内无 monitoring 记录时回退 `settings.collector_keywords`） |
| 匹配字段 | `Opinion.title` OR `Opinion.content`，`ILIKE '%kw%'`，已转义 `%` `_`（`_like_escape`） |
| 时间窗口 | `created_at::date >= current_date - (days-1)`，**有窗口** |
| 去重 | SQL JOIN 后 `count(case ...)` 按 Opinion.id 计数，每条舆情最多计 1 次 |
| 过滤条件 | `geo_filtered IS NOT TRUE` |
| trend | 当前窗口 cur vs 紧邻前一等长窗口 prev，真实对比 |
| 输出结构 | `{"items": [{"keyword": str, "count": int, "trend": "up"/"down"/"flat"}], "days": int}` |

**并且**：`get_dashboard_stats()` L384、L397 已经调用它并把结果塞进 `hot_keywords` 字段：
```python
hot_keywords = get_hot_keywords(db, days=days, limit=TOP_KEYWORDS)
...
"hot_keywords": hot_keywords["items"],
```
→ **一次 `/dashboard/stats` 请求已同时携带两种模式的数据**，前端切模式可零额外请求。

#### (C) 缓存

`backend/app/core/cache.py`，进程内 TTL 字典，`DEFAULT_TTL = 10.0` 秒。
- stats key：`dash:stats:{days}`
- hot key：`dash:hot:{days}:{limit}`

若模式2 新增 `category` 参数，**必须把它拼进 cache key**，否则会串缓存（cache.py 模块 docstring L11 已明确此约束）。

### 1.3 当前返回 JSON 结构

**`GET /api/dashboard/stats?days=7`**（Schema：`backend/app/schemas/dashboard.py` L152-177）

```json
{
  "total": 861,
  "today": 0,
  "high_risk": 0,
  "event_count": 0,
  "trend": [{ "date": "2026-07-25", "count": 12 }],
  "sentiments": [{ "label": "neutral", "count": 800 }],
  "sources": [{ "source": "廊坊市政府", "count": 120 }],
  "regions": [{ "region_id": 1, "region_name": "河北省", "count": 861 }],
  "region_detail": [{ "region_id": 23, "region_name": "霸州市", "count": 28 }],

  "keywords": [
    { "word": "群体", "count": 43 },
    { "word": "事故", "count": 18 }
  ],

  "hot_keywords": [
    { "keyword": "廊坊", "count": 297, "trend": "up" },
    { "keyword": "教育", "count": 182, "trend": "flat" }
  ]
}
```

**`GET /api/dashboard/hot-keywords?days=7&limit=10`**（Schema L107-124）
```json
{
  "items": [{ "keyword": "教育", "count": 182, "trend": "up" }],
  "days": 7
}
```

### 1.4 keywords 字段结构对比（改造关键）

| | 模式1 `stats.keywords` | 模式2 `stats.hot_keywords` / `hot-keywords.items` |
|---|---|---|
| Pydantic 模型 | `KeywordItem`（L19-23） | `HotKeywordItem`（L107-117） |
| 词字段名 | **`word`** | **`keyword`** |
| 计数字段 | `count` | `count` |
| 额外字段 | 无 | `trend` |

→ 前端必须写归一化函数（如 `toCloudData(list) -> {name, value}`），不能直接复用同一渲染分支。

---

## 二、前端审计

### 2.1 组件位置

**文件**：`frontend/src/views/Dashboard.vue`

- 模板 L132-136：
```html
<!-- 热点词云（移至地理分布左侧，等高对齐） -->
<article class="card widget widget-word">
  <header class="w-head"><h3 class="w-title">热点词云</h3></header>
  <div ref="wordcloudRef" class="chart-box"></div>
</article>
```
  → header 内目前**只有标题、无任何控件**，是模式切换器的天然插入点。

- 渲染函数 `renderWordCloud()` L296-308：
```js
if (!wordcloudChart || !stats.keywords?.length) return
const max = stats.keywords[0]?.count || 1
const data = stats.keywords.slice(0, 30).map((kw) => ({
  name: kw.word, value: kw.count,
  textStyle: { color: `hsl(${(kw.count/max)*210+200}, 70%, ${60-(kw.count/max)*30}%)` },
}))
wordcloudChart.setOption({ series: [{ type: "wordCloud", ... , data }] })
```
  - 依赖 `echarts-wordcloud`（L155 已 import）。
  - `slice(0, 30)` **实际无效**：后端 `TOP_KEYWORDS=10` 固定只给 10 条。
  - `max` 取 `[0]`，隐含依赖后端已降序（当前成立）。
  - **空数据直接 return，不清空画布** → 切模式若新数据为空，会残留旧词云。这是改造必须处理的缺陷。

### 2.2 数据加载

`loadData()` L337-350：单次 `api.get("/dashboard/stats", { params: { days: trendDays.value } })` → `Object.assign(stats, res.data)` → 依次 render。
天数切换器 `trendDays` + `segOptions`（L177-182，7/14/30 天）为整页共享。

### 2.3 可复用资产

- `frontend/src/components/SegmentedControl.vue`：已在 Dashboard 使用，props 为 `modelValue` + `options:{label,value}[]`，**可直接复用作模式切换器**，视觉风格自动一致。
- `frontend/src/components/command-screen/HotKeywordList.vue`：指挥大屏已有的 hot_keywords 列表消费样例，可参考其 trend 展示。

### 2.4 类型定义问题

- `frontend/src/types/index.ts` L176-191 `DashboardStats` **未声明 `hot_keywords`**（只有一个废弃的 `top_keywords?`）。
- `frontend/src/types/command-screen.ts` L17-35 已定义 `HotKeyword` / `CommandScreenStats`。
- → 改造时应在 `types/index.ts` 的 `DashboardStats` 补 `hot_keywords?: HotKeyword[]`，或 Dashboard.vue 改用 `CommandScreenStats`。

⚠️ **注意**：`types/index.ts` 内多处中文注释已是历史乱码（L132-134、L187 等，node 虚拟化遗留）。改动该文件时**只做最小行编辑，切勿整文件重写**，否则会扩散乱码。

---

## 三、数据现状实测（生产库，只读）

### 3.1 关键词表

| type | is_enabled | 数量 |
|---|---|---|
| monitoring | true | **30** |
| monitoring | false | 12 |
| sensitive | true | **17** |

monitoring 按 category：

| category | is_enabled | 数量 |
|---|---|---|
| 主题 | true | **14** |
| 地域 | true | 16 |
| 地域 | false | 12 |

- 主题词（14）：消防、安全生产、安全事故、民生、投诉、环保、征地、拆迁、食品安全、教育、医疗、交通、城管、舆情
- 地域词（16）：廊坊、大厂、大厂回族自治县、三河、香河、固安、广阳区、安次区、霸州市、永清县、大城县、文安县、文安、霸州、广阳、安次
- 敏感词（17，括号内为 weight）：火灾(8)、爆炸(9)、事故(6)、伤亡(9)、死亡(8)、冲突(7)、群体(0)、上访(8)、维权(0)、投诉(0)、谣言(8)、诈骗(8)、腐败(7)、贪污(7)、涉警(8)、舆情(0)、赌博(7)

### 3.2 舆情表

| 指标 | 值 |
|---|---|
| 总量 | 934 |
| 有效（`geo_filtered IS NOT TRUE`） | **861** |
| 近 7 天 | 768 |
| 近 30 天 | 861（**全部数据都在 30 天内**，廊坊切换后重建） |
| `keywords` 字段非空 | **109 / 861 = 12.7%** |
| `content` 为空 | 0 条，平均长度 712 字符 |

### 3.3 模式1 实测 TOP（当前线上词云内容）

| 词 | 计数 | weight |
|---|---|---|
| 群体 | 43 | **0** |
| 事故 | 18 | 6 |
| 火灾 | 14 | 8 |
| 投诉 | 12 | **0** |
| 伤亡 | 10 | 9 |
| 腐败 | 9 | 7 |
| 死亡 | 8 | 8 |
| 维权 | 8 | **0** |
| 冲突 | 8 | 7 |
| 诈骗 | 5 | 8 |

> TOP1「群体」weight=0，是纯语境词，说明模式1 的「风险」语义偏弱，改造后应在文案上明确其为「敏感词命中统计」。

### 3.4 模式2 预演

**(a) 若直接用现成 `hot_keywords`（全部 30 个 monitoring 词，7天）**：

| 廊坊 | 教育 | 民生 | 交通 | 医疗 | 三河 | 消防 | 大厂 | 香河 | 霸州 | 固安 | 环保 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 297 | 182 | 128 | 114 | 84 | 47 | 46 | 31 | 31 | 28 | 26 | 21 |

→ TOP10 中 **5 个是地域词**，「廊坊」以 297 断层霸榜。作为「热点主题」不可接受。

**(b) 仅 `category='主题'`（14 词，7天）**：

| 词 | 7天 | 30天 |
|---|---|---|
| 教育 | 182 | 205 |
| 民生 | 128 | 165 |
| 交通 | 114 | 122 |
| 医疗 | 84 | 94 |
| 消防 | 46 | 52 |
| 环保 | 21 | 24 |
| 安全生产 | 16 | 19 |
| 城管 | 14 | 14 |
| 投诉 | 9 | 12 |
| 安全事故 | 4 | 5 |
| 食品安全 | 3 | 5 |
| 舆情 | 3 | 3 |
| 拆迁 | 2 | 2 |
| 征地 | 1 | 1 |

→ 语义合理、词云形态健康（有梯度、无断层霸榜）。**这是模式2 应采用的口径。**
→ 但候选池只有 14 词，TOP10 几乎等于全量，词云视觉略单薄；建议 limit 设为 12-14 或全量展示。

---

## 四、改造范围界定（供 HotWord-1B 实施参考，本阶段不执行）

### 后端（工作量小）

| 项 | 是否必须 | 说明 |
|---|---|---|
| 新增 `category` 过滤参数到 `get_hot_keywords()` | **是** | 否则地域词霸榜（C-5）。建议签名 `get_hot_keywords(db, days, limit, category: str \| None = None)`，透传到 `get_monitoring_keywords` 之后做 Python 侧过滤，或改用 `get_monitoring_keywords_grouped()`（`keyword_service.py` L77 已存在，返回 `{category: [word]}`，**可直接复用，零新增查询**） |
| cache key 加入 category | **是** | `dash:hot:{days}:{limit}:{category}`，否则串缓存 |
| `/dashboard/hot-keywords` 增加 `category` Query | 是 | 若前端走独立端点 |
| `stats.hot_keywords` 是否改为主题过滤 | **需决策** | 该字段指挥大屏 `CommandScreen.vue` 也在消费，**改动会影响大屏**。建议：stats 内保持原样不动，模式2 走独立端点 `/dashboard/hot-keywords?category=主题`，零回归 |
| 新建表 / 迁移 | 否 | 无需 alembic 迁移 |

### 前端（工作量主要在此）

| 项 | 文件 | 说明 |
|---|---|---|
| 词云卡片 header 加模式切换 | `Dashboard.vue` L132-136 | 复用 `SegmentedControl`，`options=[{label:'风险关键词',value:'risk'},{label:'热点主题',value:'topic'}]` |
| `renderWordCloud()` 分支化 | `Dashboard.vue` L296-308 | 按 mode 取 `stats.keywords`(word) 或 topic 数据(keyword)，加归一化映射 |
| **修复空数据不清画布** | 同上 | 改为 `if (!data.length) { chart.clear(); return }`，否则切模式残留旧词云 |
| 模式2 数据获取 | `Dashboard.vue` `loadData()` | 建议懒加载：首次切到模式2 才请求 `/dashboard/hot-keywords`，并随 `trendDays` watch 重取 |
| 类型补齐 | `types/index.ts` L176-191 | 补 `hot_keywords?: HotKeyword[]`；**最小行编辑，勿整文件重写（乱码风险）** |
| 卡片标题文案 | `Dashboard.vue` L134 | 「热点词云」保留为卡片名，模式名区分语义 |
| 模式选择持久化 | 可选 | localStorage 或不持久化 |

### 不需要改动

- 数据库 schema / alembic 迁移
- `keyword_service.py`（`get_monitoring_keywords_grouped` 已够用）
- 采集链路、`RuleFallbackProvider`
- 指挥大屏 `CommandScreen.vue`（前提：不动 `stats.hot_keywords` 口径）

---

## 五、风险与遗留问题

| 级别 | 问题 | 建议 |
|---|---|---|
| 🔴 高 | 模式2 若不按 category 过滤，「廊坊」297 霸榜，产品语义崩塌 | 强制 `category='主题'` |
| 🔴 高 | 改 `stats.hot_keywords` 口径会连带影响指挥大屏 | 模式2 走独立端点，不动 stats |
| 🟡 中 | 模式1 无时间窗口，与 7/14/30 天切换器语义冲突（C-2） | 本期可保持不变（需求要求"逻辑不变"），但建议在卡片加 tooltip 注明「全量统计」；或列为 HotWord-2 议题 |
| 🟡 中 | 模式1 覆盖率仅 12.7%，TOP1 是 weight=0 语境词 | 文案改为「敏感词命中」更诚实 |
| 🟡 中 | 前端空数据不清画布，切模式会残留 | 实施时必修 |
| 🟢 低 | `opinions` 无 `created_at` 索引，未装 `pg_trgm`；模式2 是 30 词 × 861 行的 ILIKE 交叉连接 | 当前数据量下无性能问题；数据量破 10 万行后需加 GIN/pg_trgm 索引 |
| 🟢 低 | 主题候选词仅 14 个，词云偏稀疏 | 可建议业务侧扩充主题词库 |
| 🟢 低 | `types/index.ts` 存在历史乱码注释 | 编辑时严格最小化 diff |

---

## 六、审计合规声明

本阶段全程只读：
- 代码：仅 Read / Grep，无 Edit / Write 到任何 `backend/` `frontend/` 文件。
- 数据库：仅 `SELECT`（聚合与 pg_indexes / pg_extension 元数据查询），无 INSERT / UPDATE / DELETE / DDL。
- 配置：仅读取 `.env` 中 `DATABASE_URL`，未修改。
- 服务：未重启 uvicorn，未触发采集。
