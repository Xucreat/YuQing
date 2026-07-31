# Phase HotWord-1A：热点词云双模式改造前只读审计报告

- 审计时间：2026-07-31
- 审计范围：驾驶舱「热点词云」组件全链路（后端 API / 服务层 / 数据库 / 采集写入 / 前端渲染 / 性能）
- 审计性质：**只读审计**。本次未修改任何代码、数据库、配置、迁移；数据库仅执行 `SELECT` / `information_schema` / `EXPLAIN ANALYZE` 只读语句。
- 生产库：`postgresql://opinion_user@127.0.0.1:5432/opinion_db`（PG 16）

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| 现有「热点词云」本质 | **风险敏感词命中云**（全量历史，无时间窗口），命名与语义不符 |
| 数据覆盖率 | 934 条舆情中仅 **111 条**（11.9%）有 `keywords` 值 → 词云实际只反映 1/9 的数据 |
| 是否可复用现有时间窗口 | ✅ 可以。`days`（7/14/30）已在 Dashboard 顶部 `SegmentedControl` 存在并透传 `/dashboard/stats?days=` |
| 模式 B 是否已有现成实现 | ✅ **已有 90% 现成能力**：`get_hot_keywords()` + `GET /api/dashboard/hot-keywords` 已实现「monitoring 词 + 时间窗口 + title/content 匹配 + 每条去重」 |
| 模式 B 主要缺口 | 现有 `get_hot_keywords` **未按 category 过滤**，地域词会压制主题词（廊坊 297 vs 教育 182），需增加 `category` 维度筛选 |
| 是否需要数据库迁移 | ❌ **不需要**。keywords 表已有 `category` 字段且已按「地域/主题」分好 |
| 是否影响风险模型/预警/事件/采集 | ❌ 全部不影响（纯只读聚合层改造） |
| 性能 | 当前 934 条 73.8ms 可接受；**10 万级需加 pg_trgm GIN 索引**，100 万级需预计算 |

---

## 一、后端审计

### 1.1 Dashboard 数据接口

| 项 | 内容 |
|---|---|
| 路由文件 | `backend/app/api/dashboard.py` |
| 挂载前缀 | `APIRouter(prefix="/dashboard")`，由 main 以 `prefix="/api"` 挂载 → `/api/dashboard/*` |
| 鉴权 | 路由级 `dependencies=[Depends(get_current_user)]` |
| 词云取数端点 | `GET /api/dashboard/stats`，函数 `dashboard_stats()`（第 38–55 行） |
| 参数 | `days: int = Query(default=7, ge=1, le=90)` |
| 响应模型 | `DashboardStatsResponse`（`backend/app/schemas/dashboard.py:152`） |
| 词云消费字段 | `keywords: List[KeywordItem]` |

已存在的兄弟端点（与本次改造高度相关）：

| 端点 | 服务函数 | 语义 |
|---|---|---|
| `GET /api/dashboard/hot-keywords?days=&limit=` | `get_hot_keywords()` | **monitoring 关键词 + 时间窗口 + title/content 真实提及**（指挥大屏专用，驾驶舱当前未使用） |
| `GET /api/dashboard/risk-distribution` | `get_risk_distribution()` | 风险分布 |
| `GET /api/dashboard/alert-stats` | `get_alert_stats()` | 告警运营 |

### 1.2 当前返回 JSON 结构

`GET /api/dashboard/stats?days=7` 实际返回（顶层 11 个字段）：

```json
{
  "total": 934,
  "today": 0,
  "high_risk": 0,
  "event_count": 0,
  "trend":         [{ "date": "2026-07-25", "count": 12 }],
  "keywords":      [{ "word": "群体", "count": 43 }],
  "sources":       [{ "source": "百度新闻", "count": 100 }],
  "sentiments":    [{ "label": "neutral", "count": 800 }],
  "regions":       [{ "region_id": 1, "region_name": "河北省", "count": 861 }],
  "region_detail": [{ "region_id": 23, "region_name": "霸州市", "count": 21 }],
  "hot_keywords":  [{ "keyword": "廊坊", "count": 297, "trend": "up" }]
}
```

`keywords` 字段结构（Pydantic `KeywordItem`）：

```python
class KeywordItem(BaseModel):
    word: str
    count: int
```

### 1.3 「keywords 能否扩展为嵌套结构」结论

目标形态：

```json
{ "keywords": { "risk": [], "hot": [] } }
```

**技术上可行，但强烈不建议在 `stats.keywords` 上做破坏性变形。** 理由：

| # | 阻断点 | 说明 |
|---|---|---|
| 1 | 报告导出直接消费 | `backend/app/services/report_service.py:148` → `"top_keywords": stats["keywords"][:TOP_KEYWORDS]`。改成 dict 会让 PDF/报告模块直接崩溃或产出空表 |
| 2 | 前端旧类型 | `frontend/src/types/index.ts:182` `keywords: KeywordCount[]`；`CommandScreenStats extends DashboardStats`，指挥大屏也继承此字段 |
| 3 | 契约测试 | `backend/tests/test_dashboard.py:82` 使用 `assert set(body.keys()) == {...}` **严格键集断言**（且已缺 `region_detail`，本身已是待修复的脆弱断言）。任何顶层字段增删都会命中它 |
| 4 | 文档化契约 | `dashboard_service.py` 模块 docstring 与 schema docstring 已把 `keywords` 明确标注为「兼容字段，保留」 |

✅ **推荐替代方案（向后兼容、零破坏）**：

- **方案 A（首选）**：`keywords` 原样保留（模式 A 数据源），模式 B 走**独立端点** `GET /api/dashboard/hot-keywords?days=&limit=&category=主题`，前端切换模式时按需拉取。改动最小，可复用已上线的 `get_hot_keywords`。
- **方案 B（次选）**：`stats` 顶层**新增** `topic_keywords: List[HotKeywordItem] = []`，与 `keywords` 并存（等同 `hot_keywords` 的先例）。缺点：`stats` 单次响应必然多算一次全表 ILIKE，浪费（用户未必切模式）。

---

## 2. `dashboard_service.py` 审计

文件：`backend/app/services/dashboard_service.py`

### 2.1 当前词云查询逻辑（第 363–381 行）

```python
raw_keywords = (
    db.execute(select(Opinion.keywords).where(Opinion.geo_filtered.isnot(True)))
      .scalars().all()
)
counter = Counter()
for raw in raw_keywords:
    for kw in (raw or "").split(","):
        kw = kw.strip()
        if kw:
            counter[kw] += 1
keywords = [{"word": w, "count": c} for w, c in counter.most_common(TOP_KEYWORDS)]
```

逐项确认：

| 审计项 | 结论 |
|---|---|
| 查询模型 | `Opinion`，仅取 `Opinion.keywords` 单列 |
| 查询条件 | 仅 `Opinion.geo_filtered IS NOT TRUE` |
| **时间范围** | ❌ **无任何时间过滤** —— 全量历史。`days` 参数对本字段完全无效 |
| 是否过滤 `geo_filtered` | ✅ 是（Phase X-History-1B 口径） |
| 是否过滤 region | ❌ 否。无 `region_id` 约束（依赖上游采集期的地域准入） |
| 是否存在 `TOP_KEYWORDS` 常量 | ✅ 存在，`dashboard_service.py:49`，`TOP_KEYWORDS = 10` |
| 排序方式 | Python 内存 `Counter.most_common(10)`，按舆情条数降序（非 SQL 排序） |
| 统计口径 | 按「包含该关键词的舆情条数」计数（同一条舆情内同词只写一次，天然去重） |
| 缓存 | 整个 `stats` 走 `cache_get/cache_set`，key=`dash:stats:{days}`，TTL 10s（`app/core/cache.py`） |

### 2.2 「风险关键词云 = 什么数据 + 什么规则 + 什么排序」

> **数据**：`opinions.keywords`（逗号分隔字符串），由采集流水线 `RuleFallbackProvider.analyze()` 写入的**敏感词命中集合**，候选池 = `keywords` 表 `type='sensitive' AND is_enabled` 的 17 个词（表空时回退内置 `DEFAULT_KEYWORDS`）。
> **规则**：全量历史 + `geo_filtered IS NOT TRUE`，按逗号切分后计数，一条舆情对一个词只贡献 1。
> **排序**：Python `Counter.most_common(TOP_KEYWORDS=10)`，count 降序，同 count 顺序不稳定（依赖插入序）。

生产库实测当前词云内容（模拟同口径 SQL）：

| 词 | 计数 | 词 | 计数 |
|---|---|---|---|
| 群体 | 43 | 死亡 | 8 |
| 事故 | 18 | 维权 | 8 |
| 火灾 | 14 | 冲突 | 8 |
| 投诉 | 12 | 诈骗 | 5 |
| 伤亡 | 10 | 舆情 | 3 |
| 腐败 | 9 | 谣言 | 3 |

⚠️ **发现 1（语义污染）**：排名第一的「群体」是 `weight=0` 的**语境词**（同类还有 投诉/维权/舆情，均 weight=0）。`RuleFallbackProvider.analyze()` 的命中收集（`fallback.py:75-77`）**不看 weight**，只要 `word in text` 就进 `hits`，因此零权重语境词会污染词云头部。而风险评分侧（Phase1）已明确「weight=0 退出评分」——**两边口径不一致**。

⚠️ **发现 2（覆盖率极低）**：`opinions` 共 934 条，`keywords` 非空的只有 **111 条（11.9%）**。即当前词云仅反映约 1/9 数据，且不含时间维度，越往后越"冻结"在历史。

---

## 3. 时间窗口链路审计

| 层 | 现状 |
|---|---|
| 前端时间选择组件 | ✅ 已有。`Dashboard.vue:75` `<SegmentedControl v-model="trendDays" :options="segOptions" />`，位于「舆情趋势」卡片头部；`segOptions = [7天, 14天, 30天]`，`trendDays = ref(7)` |
| 前端请求参数 | `Dashboard.vue:341` `api.get("/dashboard/stats", { params: { days: trendDays.value } })`；`watch(trendDays, loadData)` 全量重载 |
| 后端接收参数 | `days: int = Query(default=7, ge=1, le=90)`（`api/dashboard.py:42`） |
| 参数命名 | 统一为 **`days`**。系统内**不存在** `start_time` / `end_time` / `range` 形式的 Dashboard 参数（`report_service` 另有自己的 ws/we 时间口径，与 Dashboard 无关） |
| 受 days 影响的字段 | `trend` / `sentiments` / `sources` / `regions` / `region_detail` / `hot_keywords` |
| 不受 days 影响 | `total` / `today` / `high_risk` / `event_count` / **`keywords`（词云）** |
| 窗口计算方式 | `window_start = current_date - (days-1)`，按 `cast(Opinion.created_at, Date)` 过滤（注意：用 `created_at` 而非 `publish_time`） |

✅ **结论：热点主题词云可以完全复用现有时间窗口**，前端无需新增时间控件，`days` 直接透传即可。唯一要注意：目前 `SegmentedControl` 语义上挂在「舆情趋势」卡片头，视觉上是趋势图的局部控件，但实际是**全局 days**。若模式 B 词云也随它变化，建议在词云卡片副标题标注「近 N 天」以消除歧义。

---

## 二、数据库审计

### 1. `keywords` 表结构（`information_schema.columns` 实测）

| 字段 | 类型 | 可空 | 默认 |
|---|---|---|---|
| id | integer | NO | `nextval('keywords_id_seq')` |
| word | varchar(128) | NO | — |
| weight | integer | NO | — |
| category | varchar(64) | NO | — |
| type | varchar(16) | NO | `'monitoring'` |
| source | varchar(16) | NO | `'custom'` |
| is_enabled | boolean | NO | `true` |
| created_at | timestamp | YES | — |
| updated_at | timestamp | YES | — |
| severity_weight | integer | NO | `0` |
| rule_config | jsonb | YES | — |

约束：`UNIQUE (word, type)`（`uq_keywords_word_type`）；`word` 有索引。

### 数量统计（实测）

```
type        | total | enabled
------------+-------+---------
monitoring  |    42 |      30
sensitive   |    17 |      17
```

- **sensitive：17 条（全部启用）**
- **monitoring：42 条，启用 30 条**
  - `category='主题'`：14 条，**全部启用**
  - `category='地域'`：28 条，启用 16 条 / 停用 12 条（停用的是河北其他地市：河北/石家庄/唐山/保定/邯郸/秦皇岛/邢台/沧州/衡水/张家口/承德/雄安）

### 2. monitoring 关键词质量检查

**主题类（14 条，全部启用）——质量良好，天然适合作为热点主题：**

| 词 | weight | 词 | weight |
|---|---|---|---|
| 消防 | 6 | 食品安全 | 4 |
| 安全生产 | 6 | 教育 | 3 |
| 安全事故 | 5 | 医疗 | 3 |
| 民生 | 5 | 交通 | 3 |
| 投诉 | 4 | 城管 | 3 |
| 环保 | 4 | 舆情 | 3 |
| 征地 | 4 | | |
| 拆迁 | 4 | | |

覆盖了用户列举的业务主题：**环保 ✅ / 交通 ✅ / 教育 ✅ / 医疗 ✅ / 民生 ✅ / 城管 ✅**。
用户举例中的「道路 / 学校 / 物业 / 工资」**当前词库没有**——是否补词属产品侧决策，本阶段不动。

**⛔ 不适合作为热点主题展示的词：**

| 词 | 问题 |
|---|---|
| **舆情** | 元词/自指词。系统自身领域词，几乎所有政务稿件都可能出现，展示无信息量。建议模式 B 展示时排除或降权 |
| **地域类 28 词全体** | 若不做 category 过滤直接混入，将完全压制主题词（见下方实测） |

**地域词压制效应实测**（近 7 天，全部启用 monitoring 词）：

```
廊坊 297 | 教育 182 | 民生 128 | 交通 114 | 医疗 84 | 三河 47 | 消防 46
香河 31 | 大厂 31 | 霸州 28 | 固安 26 | 环保 21 | 霸州市 21 | 文安 19 | 广阳 17
```

TOP15 中 9 个是地域词，且 #1「廊坊」(297) 是全域监测目标本身——**毫无热点信息量**。

**仅主题词（category='主题'）近 7 天实测——这才是模式 B 应有的形态：**

| 主题 | 命中舆情数 | 主题 | 命中舆情数 |
|---|---|---|---|
| 教育 | 182 | 投诉 | 9 |
| 民生 | 128 | 安全事故 | 4 |
| 交通 | 114 | 食品安全 | 3 |
| 医疗 | 84 | 舆情 | 3 |
| 消防 | 46 | 拆迁 | 2 |
| 环保 | 21 | 征地 | 1 |
| 安全生产 | 16 | | |
| 城管 | 14 | | |

14 个主题词全部有非零命中，分布有层次，**产品可用性明显优于当前风险词云**。

---

## 三、采集链路审计

### `Opinion.keywords` 生成逻辑

写入点唯一：`backend/app/collectors/service.py:553`

```python
analysis = ai.analyze(f"标题：{opinion.title}\n正文：{opinion.content}")
...
opinion.keywords = ",".join(analysis.keywords)
```

其中 `ai = RuleFallbackProvider(keywords=get_sensitive_keywords(db))`（`service.py:448`）。

`RuleFallbackProvider.analyze()`（`app/services/ai/fallback.py:72-127`）：

```python
hits = []
for word, _weight in self.keywords:      # ← 不看 weight
    if word and word in text:
        hits.append(word)
...
return AIAnalysisResult(..., keywords=hits, ...)
```

链路小结：

| 项 | 结论 |
|---|---|
| 候选池 | `keyword_service.get_sensitive_keywords(db)` → `type='sensitive' AND is_enabled`（17 词），为空回退内置 `DEFAULT_KEYWORDS` |
| 匹配方式 | Python 子串 `in`（大小写敏感），对 `标题+正文` 拼接文本 |
| weight 作用 | 只影响 `risk_score`，**不影响 keywords 命中集合**（零权重语境词照样入列） |
| 存储形式 | 逗号分隔纯文本，无长度上限约束 |
| `ai_keywords` 字段 | 独立字段，仅由 `app/api/analysis.py:90`（手动重新分析接口）写入，**Dashboard 词云不消费** |
| 失败路径 | 分析异常 → `analysis_status='failed'`，`keywords` 保持 NULL（这是 88% 空值的主因之一） |

### 两种模式的数据源选型建议

| 模式 | 是否复用 `Opinion.keywords` | 理由 |
|---|---|---|
| **模式 A 风险关键词** | ✅ **继续复用** | 语义正确（就是敏感词命中）、零改动、零回归；且 `report_service` 也依赖同口径 |
| **模式 B 热点主题** | ⛔ **必须绕过 `Opinion.keywords`** | ① `Opinion.keywords` 只存 sensitive 命中，物理上不含 monitoring 主题词；② 88% 为空；③ 历史数据是用旧词表算的，改词表不回溯。**应直接对 `Opinion.title` + `Opinion.content` 做 ILIKE 匹配**——与已上线的 `get_hot_keywords()` 完全同款 |

---

## 四、前端审计

### 1. 文件与组件位置

| 项 | 值 |
|---|---|
| Vue 文件 | `frontend/src/views/Dashboard.vue` |
| 卡片模板 | 第 132–136 行，`<article class="card widget widget-word">`，标题 `热点词云` |
| 图表容器 | `<div ref="wordcloudRef" class="chart-box">`（`.widget-word` = `grid-column: span 4`，`.chart-box` 高 200px） |
| 布局位置 | 组件网格第二行，位于「实时快讯」与「地理分布」之间 |

### 2. 当前实现

| 项 | 实现 |
|---|---|
| 图表库 | `echarts` + `echarts-wordcloud`（`import "echarts-wordcloud"`，第 155 行） |
| 实例 | `let wordcloudChart: echarts.ECharts \| null`（第 233 行），`onMounted` 中 `echarts.init(wordcloudRef.value)`（第 381 行），`onBeforeUnmount` 中 dispose（第 395 行） |
| 渲染函数 | `renderWordCloud()`（第 296–308 行） |
| 数据来源 | `stats.keywords`（`DashboardStats.keywords: KeywordCount[]`），`.slice(0, 30)` —— 但后端只给 10 条，`slice(30)` 是死代码 |
| 映射 | `{ name: kw.word, value: kw.count, textStyle: { color: hsl(...) } }`，颜色按 `count/max` 线性插值 |
| ECharts 配置 | `type: "wordCloud"`, `shape: "circle"`, `sizeRange: [14,42]`, `rotationRange: [-30,30]`, `gridSize: 8`, `layoutAnimation: true` |
| 是否绑定 stats | ✅ 是。`loadData()` 内 `Object.assign(stats, statsRes.data)` → `await nextTick()` → `renderWordCloud()` |
| 刷新机制 | ① `watch(trendDays)` → `loadData()`；② `window.addEventListener("data-refresh", loadData)` 全局刷新事件；③ `handleResize` 中 `wordcloudChart?.resize()`。**注意：`loadFeeds` 30s 定时器只刷快讯/预警，不刷词云** |
| 空数据 | `if (!wordcloudChart \|\| !stats.keywords?.length) return` —— 空数据时**保留上一次画面**，不清空、无空态提示（切模式时会残留旧词，需处理） |

### 3. 改造可行性评估

可行性 **高**。切换控件有现成先例：`SegmentedControl`（`frontend/src/components/SegmentedControl.vue`）已在「舆情趋势」卡片头使用，可原样复制到词云卡片头。

预计修改文件清单：

| 层 | 文件 | 改动内容 | 量级 |
|---|---|---|---|
| 前端 | `frontend/src/views/Dashboard.vue` | 卡片头加 `SegmentedControl`（风险关键词/热点主题）；新增 `wordMode` ref + `topicKeywords` ref；`renderWordCloud()` 按模式选数据源；`watch(wordMode)` 按需拉取；空态兜底 | 中（约 +40 行） |
| 前端 | `frontend/src/types/index.ts` | 新增 `TopicKeywordItem`（或直接复用 `types/command-screen.ts` 已有的 `HotKeyword`/`HotKeywordsResponse`） | 极小 |
| 后端 | `backend/app/services/dashboard_service.py` | `get_hot_keywords()` 增加可选 `category: str \| None = None` 参数（默认 None = 现有行为，向后兼容）；缓存 key 补 category | 小（约 +8 行） |
| 后端 | `backend/app/api/dashboard.py` | `/hot-keywords` 增加 `category: str \| None = Query(None)` | 极小（+2 行） |
| 后端 | `backend/app/schemas/dashboard.py` | 无需改（复用 `HotKeywordsResponse`） | 0 |
| 数据库 | — | **无改动、无迁移** | 0 |
| 测试 | `backend/tests/test_dashboard.py` | 新增 category 过滤用例；顺带修复 `set(body.keys())` 严格断言缺 `region_detail` 的既有问题 | 小 |

---

## 五、性能评估

技术栈约束：PostgreSQL 16 + FastAPI + SQLAlchemy，**无 ES、无 Redis、无 MQ**（本阶段红线，不引入）。

### 当前实测（生产库，934 条 opinions）

`EXPLAIN (ANALYZE, BUFFERS)` 模式 B 同款查询（14 个主题词 × 近 7 天）：

```
Execution Time: 73.772 ms
Planning Time:   1.147 ms
-> Nested Loop  (actual rows=627)
     Join Filter: (title ILIKE '%kw%' OR content ILIKE '%kw%')
     Rows Removed by Join Filter: 10125
   -> Seq Scan on opinions  (rows=768)   Buffers: shared hit=129
   -> Materialize (keywords, rows=14)
Buffers: shared hit=13044
```

数据画像：`opinions` 表 2848 kB，`content` 平均 659 字符 / 最长 17514 字符。

### 复杂度与扩展性

算法复杂度 = **O(窗口内舆情数 × 启用关键词数)** 的全文子串扫描（`%kw%` 前置通配符，**B-tree 索引完全无法使用**，只能 Seq Scan + 逐行 ILIKE）。

| Opinion 规模（窗口内） | 预估单次耗时 | 是否可直接查库 | 建议 |
|---|---|---|---|
| **1 万** | ~0.8 s | ✅ 可以（有 10s TTL 缓存兜底） | 现有 `cache_set(key, data)` TTL 10s 足够；建议词云专用 key TTL 提到 60s |
| **10 万** | ~8 s | ⚠️ 勉强，首次请求会明显卡顿 | **必须加 pg_trgm GIN 索引**（已确认 `pg_trgm` 在本机 `pg_available_extensions` 中可用，尚未安装）：`CREATE EXTENSION pg_trgm; CREATE INDEX ... USING gin (title gin_trgm_ops); ... (content gin_trgm_ops)`。ILIKE `%kw%` 可走 GIN，预计降到百毫秒级 |
| **100 万** | ~80 s | ⛔ 不可接受 | 需**预计算**：新增 `opinion_topic_hits(opinion_id, keyword_id, created_at)` 关联表，在采集写入时同步落地（O(1) 摊销），词云查询变成纯 `GROUP BY` 聚合 + 索引扫描 |

现有索引（`opinions`）：`pkey(id)` / `ix_opinions_region_id` / `ix_opinions_url_unique`（部分唯一） / `ix_opinions_source_type` / `ix_opinions_external_id`。
**没有 `created_at` 索引**，且窗口过滤写成 `cast(created_at, Date) >= ...`（对列做函数运算）→ 即使加了普通 B-tree 也用不上，需**表达式索引** `((created_at)::date)` 或改写为 `created_at >= window_start::timestamp`。

### 缓存现状

`app/core/cache.py`：进程内 dict，`DEFAULT_TTL = 10.0s`，多 worker 各自持有一份（不共享）。当前部署为单实例 uvicorn，命中率良好。**模式 B 建议独立缓存 key**（如 `dash:hot:{days}:{limit}:{category}`），避免与现有 `dash:hot:{days}:{limit}` 串味。

---

## 六、审计结论汇总

### 1. 当前热点词云现状

**数据来源**
`opinions.keywords`（逗号分隔文本）← 采集流水线 `collectors/service.py:553` ← `RuleFallbackProvider.analyze()` 的敏感词命中集合 ← 候选池 `keywords` 表 `type='sensitive' AND is_enabled`（17 词，为空回退内置 `DEFAULT_KEYWORDS`）。

**统计规则**
`SELECT keywords FROM opinions WHERE geo_filtered IS NOT TRUE` → 全量历史、**无时间窗口** → Python `Counter` 逗号切分计数 → `most_common(TOP_KEYWORDS=10)` → 前端 ECharts wordCloud 渲染（前端再 `slice(0,30)`，实际只有 10 条）。

**存在问题**

| # | 问题 | 影响 |
|---|---|---|
| P1 | **名实不符**：叫「热点词云」，实为「风险敏感词命中云」 | 用户认知误导 |
| P2 | **无时间维度**：全量历史，`days` 切换 7/14/30 时词云纹丝不动 | 与驾驶舱「近 N 天」语义冲突，无法反映"当下热点" |
| P3 | **覆盖率 11.9%**：934 条中仅 111 条有值 | 词云只代表 1/9 数据，样本偏差大 |
| P4 | **零权重语境词污染头部**：TOP1「群体」(43) 是 `weight=0` 的语境词，同类还有 投诉/维权/舆情 | 与风险评分「weight=0 退出评分」口径不一致 |
| P5 | **词库变更不回溯**：`keywords` 是采集时快照，事后调整 sensitive 词表不影响历史 | 词云长期"冻结"在历史词表 |
| P6 | **空数据不清屏**：`renderWordCloud` 遇空直接 `return`，保留上一帧 | 双模式切换时会看到旧模式残影 |

### 2. 双模式改造方案建议

**模式 A — 风险关键词（保持现状，零改动）**

- 数据源：`Opinion.keywords`
- 候选池：`keywords.type='sensitive'`
- 口径：全量历史 + `geo_filtered IS NOT TRUE`
- 排序：`Counter.most_common(10)`
- 前端字段：`stats.keywords[].{word,count}`
- **改造动作：无。完全不动后端与数据契约。**
- （可选低风险优化，建议放到 1C 而非 1B）：卡片副标题标注「累计 · 敏感词命中」，消除时间歧义。

**模式 B — 热点主题（新增）**

- 数据源：`Opinion.title` + `Opinion.content`（**绕过 `Opinion.keywords`**）
- 候选池：`keywords.type='monitoring' AND is_enabled AND category='主题'`（14 词）
- 时间窗口：复用 `days`（`created_at::date >= current_date - (days-1)`）
- 过滤：`geo_filtered IS NOT TRUE`（与全站口径一致）
- 匹配：`title ILIKE '%kw%' OR content ILIKE '%kw%'`，`%`/`_` 已由 `_like_escape()` 转义
- 去重：**每条舆情对每个词最多计 1 次**（`get_hot_keywords` 已实现）
- 排序：count 降序 TOP 10
- 附加：`trend`（当前窗口 vs 前一等长窗口，up/down/flat）已现成，可直接用于 tooltip
- **实现路径：复用现有 `get_hot_keywords()`，仅新增可选 `category` 参数**，不写新查询、不新建端点。

两模式对比（近 7 天实测）：

| 模式 A（现状 TOP5） | 模式 B（主题 TOP5） |
|---|---|
| 群体 43 / 事故 18 / 火灾 14 / 投诉 12 / 伤亡 10 | 教育 182 / 民生 128 / 交通 114 / 医疗 84 / 消防 46 |
| 风险视角，样本 111 条 | 议题视角，样本 768 条 |

### 3. 修改范围评估

**后端（3 个文件，均为向后兼容增量）**

1. `backend/app/services/dashboard_service.py`
   - `get_hot_keywords(db, days, limit, category: str | None = None)` —— 新增可选参数；`category` 为 None 时行为与现在**完全一致**（指挥大屏零影响）
   - 词表获取需新增按 category 取词的能力：优先复用 `keyword_service.get_monitoring_keywords_grouped(db)`（**已存在**，返回 `{category: [word,...]}`），避免新增 DB 查询函数
   - 缓存 key 追加 category 段
2. `backend/app/api/dashboard.py`
   - `/hot-keywords` 新增 `category: str | None = Query(default=None, max_length=64)`
3. `backend/app/schemas/dashboard.py`
   - **无需改动**（`HotKeywordsResponse` 直接复用）

**前端（2 个文件）**

1. `frontend/src/views/Dashboard.vue`（主改动）
2. `frontend/src/types/index.ts`（或直接从 `@/types/command-screen` 复用 `HotKeyword`）

**数据库**

- 表结构：**无改动**
- 数据：**无改动**（`category='主题'` 的 14 条已就绪且全部启用）
- **是否需要迁移：❌ 不需要，不新建 alembic revision**

**测试**

- `backend/tests/test_dashboard.py`：新增 category 过滤用例；顺手修复 `set(body.keys())` 断言（现已缺 `region_detail`，属既有技术债）

### 4. 风险评估

| 维度 | 是否受影响 | 说明 |
|---|---|---|
| **风险模型（RiskEngine / risk_score / risk_factors / risk_category）** | ❌ 否 | 本改造全程只读聚合，不进入 `collectors/service.py` 分析写回路径，不触碰 `risk_engine.py` |
| **预警（alert_rules / alert_records / alert_service）** | ❌ 否 | 预警走 `get_monitoring_keywords()` 扁平接口，本改造只**新增**分组读取路径，不改扁平接口 |
| **事件聚合（Event / event_opinions / 聚合器）** | ❌ 否 | 无任何交集 |
| **采集链路（Collector / CollectorService / 地域前置过滤）** | ❌ 否 | 不改 `service.py`、不改 `get_monitoring_keywords_grouped` 的返回契约（只读复用） |
| **指挥大屏 `hot_keywords`** | ⚠️ 需守护 | `category=None` 必须保持默认行为完全一致，否则大屏热词会被主题词过滤掉。**必须有回归测试断言** |
| **报告导出 `report_service`** | ❌ 否 | 只要不动 `stats.keywords` 的结构（推荐方案 A 即不动） |
| **DB 写入** | ❌ 否 | 全程只读 SELECT |
| **性能** | ⚠️ 低 | 模式 B 为**按需拉取**（用户点切换才请求），不加重默认 `/stats` 负担；当前数据量 74ms + TTL 缓存 |
| **前端回归** | ⚠️ 低 | 需注意切模式时 ECharts 空数据残影（P6），必须显式 `clear()` 或渲染空态 |

**唯一中等风险点**：`get_hot_keywords` 的默认行为兼容性。缓解措施：`category` 默认 `None` + 单测断言「不传 category 时返回结果与改造前完全一致」。

### 5. 实施建议：Phase HotWord-1B 步骤

> 前提：1B 开始前需产品侧确认两项决策 —— ①「舆情」这个主题词是否在模式 B 中排除；② 模式 B 是否需要一并展示 `trend` 箭头。

**Step 1 — 后端服务层（约 10 行）**
在 `dashboard_service.get_hot_keywords()` 增加 `category: str | None = None`：
- `category is None` → 沿用 `get_monitoring_keywords(db)`（行为 100% 不变）
- `category` 非空 → 取 `get_monitoring_keywords_grouped(db).get(category, [])`
- 缓存 key 改为 `f"dash:hot:{days}:{limit}:{category or '_all'}"`

**Step 2 — 后端 API（约 2 行）**
`/api/dashboard/hot-keywords` 增加 `category: str | None = Query(None, max_length=64)` 并透传。

**Step 3 — 后端测试（必须先于前端）**
- 回归：不传 `category` 时结果与基线一致（守护指挥大屏）
- 新增：`category=主题` 只返回主题词、不含地域词
- 新增：`category=不存在的分类` 返回稳定空结构 `{"items": [], "days": N}`，不 500
- 修复：`test_dashboard.py:82` 的严格键集断言补 `region_detail`

**Step 4 — 前端类型**
从 `@/types/command-screen` 复用 `HotKeyword` / `HotKeywordsResponse`，避免重复定义。

**Step 5 — 前端组件（Dashboard.vue）**
1. 卡片头加切换：`<SegmentedControl v-model="wordMode" :options="[{label:'风险关键词',value:'risk'},{label:'热点主题',value:'hot'}]" />`
2. 新增 `const topicKeywords = ref<HotKeyword[]>([])` + `loadTopicKeywords()`（调 `/dashboard/hot-keywords?days=&limit=30&category=主题`）
3. `renderWordCloud()` 内按 `wordMode` 选数据源，并统一映射为 `{name, value}`
4. `watch(wordMode)`：切到 `hot` 且未加载过 → 懒加载；切回 `risk` → 直接用 `stats.keywords`
5. `watch(trendDays)`：若当前是 `hot` 模式，需一并重拉主题词
6. **空态处理**：数据为空时 `wordcloudChart.clear()` + 显示「暂无数据」，杜绝残影
7. 卡片标题动态化：`风险关键词（累计）` / `热点主题（近 N 天）`

**Step 6 — 构建与部署（按项目既定流程）**
`cd frontend` → `node --max-old-space-size=1400 node_modules/vite/bin/vite.js build` → `python backend/_d.py`；后端改动需重启 uvicorn，并用「受保护路由返回 401 JSON」验证新代码已加载。

**Step 7 — 验收清单**
- [ ] 指挥大屏热词无变化（回归）
- [ ] 报告导出 PDF 的 `top_keywords` 无变化（回归）
- [ ] 驾驶舱词云默认进入「风险关键词」，与改造前像素级一致
- [ ] 切到「热点主题」显示 14 个主题词，7/14/30 天切换数值随之变化
- [ ] 两模式来回切换无残影、无报错

**建议放入后续 Phase（1C，不在 1B 范围）**
- 修复 P4：`RuleFallbackProvider` 命中集合是否应剔除 `weight=0` 语境词（涉及采集写入，需独立评估回归面）
- 修复 P3：`analysis_status='failed'` 导致 keywords 为空的补偿机制
- 性能预埋：`pg_trgm` 扩展 + GIN 索引（数据量到 5 万量级前完成）

---

## 附录：本次审计执行的只读操作清单

| # | 操作 | 类型 |
|---|---|---|
| 1 | `information_schema.columns` 查 keywords 表结构 | 只读 |
| 2 | `SELECT type, count(*) ... GROUP BY type` | 只读 |
| 3 | `SELECT type,category,is_enabled,word,weight FROM keywords` | 只读 |
| 4 | `SELECT count(*) ... FROM opinions`（含 keywords 覆盖率、时间跨度） | 只读 |
| 5 | `pg_indexes` / `pg_total_relation_size` / `pg_available_extensions` | 只读 |
| 6 | 模式 A / 模式 B 口径模拟聚合查询 | 只读 |
| 7 | `EXPLAIN (ANALYZE, BUFFERS)` 模式 B 查询 | 只读（ANALYZE 执行 SELECT，无写入） |
| 8 | 源码阅读：`api/dashboard.py`、`schemas/dashboard.py`、`services/dashboard_service.py`、`services/keyword_service.py`、`services/ai/fallback.py`、`services/report_service.py`、`collectors/service.py`、`models/keyword.py`、`core/cache.py`、`views/Dashboard.vue`、`types/index.ts`、`types/command-screen.ts`、`tests/test_dashboard.py` | 只读 |

**未执行任何 INSERT / UPDATE / DELETE / DDL / alembic 操作；未修改任何代码或配置文件。**
