# 指挥大屏 Phase 1：后端数据契约修正报告

> 配套《集成前审计报告》。本报告记录对 `backend/` 的实际改动与验证结果。
> 严格遵守原则：**未修改任何生产业务数据、未实现 WebSocket、未开始 Vue 大屏、接口向后兼容**。

---

## 1. 修改文件清单

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `backend/app/core/cache.py` | **新增** | 轻量级进程内 TTL 缓存（dashboard 轮询减负用） |
| `backend/app/services/dashboard_service.py` | 重写 | 重定数据契约、`regions` 省级上卷、新增 `hot_keywords`、接入缓存 |
| `backend/app/schemas/dashboard.py` | 修改 | 新增 `HotKeywordItem` / `HotKeywordsResponse`；`DashboardStatsResponse` 增加 `hot_keywords` 字段与口径注释 |
| `backend/app/api/dashboard.py` | 重写 | `days` 校验放宽到 1..90；新增 `GET /hot-keywords`；recent/alerts 改走 service 层（含缓存） |
| `backend/tests/conftest.py` | 微调 | `os.environ["DATABASE_URL"]=` 改为 `setdefault(...)`，允许环境变量覆盖测试库地址（对原 5433 环境零破坏） |
| `backend/tests/test_dashboard.py` | 重写 | 修正陈旧断言 + 16 个测试（rollup / hot_keywords / days 窗口 / days 校验 / 缓存） |

> 未改动 `Opinion` 模型、`regions` 表、任何业务数据；`keywords` / `sources` / `sentiments` 等字段均保留。

---

## 2. 每个文件的修改目的

- **cache.py**：项目原本无缓存基础设施（仅 PostgreSQL，无 Redis）。dashboard 大屏预计 15–30s 轮询，若每次都聚合全表代价高。提供极简、无外部依赖的进程内 TTL 缓存（默认 10s，低于轮询间隔）。
- **dashboard_service.py**：核心改动载体。把原本「全量统计 + 仅 trend 用 days」修正为明确的三类口径（累计 / 当日 / 窗口）；实现 `regions` 省级上卷；新增 `hot_keywords` 真实数据源；四类端点统一接入缓存。
- **schemas/dashboard.py**：把契约固化成类型。`hot_keywords` 与旧 `keywords` 在数据契约层面彻底分离，前端可明确区分「指挥大屏热门词」与「旧页敏感词词云」。
- **api/dashboard.py**：`days` 从 `ge=7,le=30` 放宽为 `ge=1,le=90`（满足 days=1 验证需求，对旧调用向后兼容）；新增 `/hot-keywords` 端点；recent/alerts 逻辑下沉到 service 层以便缓存与单测。
- **conftest.py**：仅把硬赋值改为 `setdefault`，使本机无 5433 实例时可指向同实例的 `opinion_test`，原 CI/开发环境行为不变。
- **test_dashboard.py**：原 `test_dashboard_login_success` 断言的 key 集合（5 个）已落后于实际返回（9 个），更新为完整集合；新增省级上卷、热门词、窗口语义、days 校验、缓存命中/隔离/过期等测试。

---

## 3. 最终 API 契约

### 3.1 `GET /api/dashboard/stats?days={1..90, 默认 7}`
返回 `DashboardStatsResponse`：

```jsonc
{
  "total": 429,          // 累计：系统全部舆情
  "today": 72,           // 当日：今日（created_at）新增
  "high_risk": 45,       // 累计：risk_score>=70 的高危舆情总量
  "event_count": 70,     // 累计：事件总量
  "trend": [             // 窗口：近 days 日每日增量（空日补齐 0）
    { "date": "2026-07-16", "count": 11 }, ...
  ],
  "sentiments": [        // 窗口：窗口内情感分布
    { "label": "negative", "count": 15 },
    { "label": "positive", "count": 141 },
    { "label": "neutral",  "count": 273 }
  ],
  "sources": [           // 窗口：窗口内来源 Top（默认 10）
    { "source": "百度新闻", "count": 97 }, ...
  ],
  "regions": [           // 窗口 + 省级上卷：仅省级地域
    { "region_id": 2, "region_name": "河北省", "count": 429 }
  ],
  "keywords": [          // [兼容字段] 全量，来自 opinions.keywords（敏感词命中集合），旧 Dashboard 词云用
    { "word": "事故", "count": 18 }, ...
  ],
  "hot_keywords": [      // 窗口：指挥大屏「热门关键词」（监测词表 × 真实提及频次）
    { "keyword": "河北", "count": 157, "trend": "up" }, ...
  ]
}
```

### 3.2 `GET /api/dashboard/recent?limit={1..50, 默认 8}`
实时快讯（不变，仅逻辑下沉到 service 层并加缓存）。

### 3.3 `GET /api/dashboard/alerts?limit={1..50, 默认 8}`
预警滚动（不变，同上）。

### 3.4 `GET /api/dashboard/hot-keywords?days={1..90,默认7}&limit={1..50,默认10}`  ← **新增**
```jsonc
{
  "items": [
    { "keyword": "河北", "count": 157, "trend": "up" },
    { "keyword": "民生", "count": 70,  "trend": "up" }
  ],
  "days": 7
}
```
- 空数据返回稳定结构 `{ "items": [], "days": 7 }`，不会 500。
- `trend` 为 `up`/`down`/`flat` 真实对比（当前窗口 vs 紧邻前一等长窗口），非伪造；无可比数据时按 cur 给出稳妥判定。

---

## 4. 每个统计字段的时间口径

| 字段 | 口径类别 | 是否受 `days` 影响 | 说明 |
| --- | --- | --- | --- |
| `total` | 累计 | 否 | `count(opinions.id)` 全量 |
| `event_count` | 累计 | 否 | `count(events.id)` 全量 |
| `high_risk` | 累计 | 否 | `risk_score >= 70` 全量（业务语义=系统高危态势） |
| `today` | 当日 | 否 | `cast(created_at,Date)=current_date` |
| `trend` | 窗口 | 是 | 近 `days` 日每日增量 |
| `sentiments` | 窗口 | 是 | 窗口内情感分布 |
| `sources` | 窗口 | 是 | 窗口内来源 Top |
| `regions` | 窗口 | 是 | 窗口内 + 省级上卷 |
| `keywords` | 兼容（全量） | 否 | 来自 `opinions.keywords`，旧页用 |
| `hot_keywords` | 窗口 | 是 | 监测词表 × 窗口内真实提及频次 |

> 刻意**没有**把所有字段统一成 `days` 窗口——累计/当日/窗口三类指标语义互斥，强行统一会丢失 KPI 含义。

---

## 5. 热门关键词（hot_keywords）算法说明

**数据源**：监测关键词表 `keywords`（经 `app/services/keyword_service.get_monitoring_keywords` 获取，带 60s 进程缓存；表空时回退 `settings.collector_keywords`）。**不读取 `Opinion.keywords`**（那是规则命中的敏感词集合，语义不符，审计已确认）。

**统计口径**：
1. 取监测词集合 `K`（如 河北/石家庄/消防/食品安全…）。
2. 取时间窗口 `[window_start, now]`，并向前取等长前一窗口 `[prev_start, window_start)` 用于趋势。
3. 对每条 `k ∈ K`，在窗口内 `title + content` 上做 **ILIKE 匹配**（大小写不敏感，覆盖英文关键词；中文无大小写问题）。
4. **去重到「每条舆情最多计 1 次」**：同一条舆情即使多次出现该词也只 +1，避免同一文档内重复出现导致严重重复计数。
5. 计数结果：`cur` = 当前窗口提及条数；`prev` = 前一等长窗口提及条数。
6. `trend = up/down/flat`（`cur>prev`→up，反之 down，相等 flat），为真实对比。
7. 仅保留 `cur>0` 的词，按 `count` 倒序取 `limit`。

**规范化与鲁棒性**：
- 英文大小写：ILIKE 处理。
- 空格：匹配模式下对关键词去除空格（`func.replace(col,' ','')`），处理「配置了带空格的词」与正文的常见差异。
- LIKE 通配符：对 `%`/`_` 转义并指定 `ESCAPE '\'`，避免监测词含特殊字符破坏 SQL。
- 空数据：词表为空或窗口内无任何提及 → 返回 `{"items":[],"days":N}`，不 500。

**已知限制（已文档化，非阻塞）**：子串匹配可能把「和平」误命中「和平里」等；未做分词/NLP（遵循「不引入大型 NLP 依赖」原则）。对监测词表场景可接受。

---

## 6. 地域省级上卷算法说明

**问题**：`opinions.region_id` 实际落在 省/市/县 三级混用（真实库抽样：省 170 / 市 75 / 县 184），地图 choropleth 只接受省名。

**算法**（`_province_code` + `_rollup_provinces`，纯靠行政区划 code 前缀，不依赖 `parent_code`）：
- 省级 code 由 GB/T 2260 前缀推导：`code[:2] + "0000"`。
  - 省 `130000` → `130000`；市 `130100` → `130000`；县 `131028` → `130000`。
- 先构建 `{规范化省级code: (省级region_id, 省名)}` 映射（兼容省 code 写成 2 位或 6 位）。
- 对每个 `opinion.region_id`，取其 region 的 code 推导省级 code → 查映射得到省名与省 region_id。
- 无法识别归属的 region：**记录 `logger.warning` 并归入「未知地区」(region_id=0)**，绝不静默丢弃（计数保留）。
- 输出仅含省级，按 count 倒序；不再出现市/县名。

**验证结论（真实库）**：
- `days=7` → `regions=[('河北省', 429)]`（全部 429 条混级数据归并为河北省）。
- 非省级名称集合为空（无 廊坊市 / 大厂回族自治县）。
- **未写死「河北省」**：算法对 `code[:2]+"0000"` 通用，未来新增广东省（`440000`）等会自动按前缀归并。

---

## 7. 缓存实现说明及多 worker 限制

**实现**：`backend/app/core/cache.py`，进程内字典 `{key:(写入时间戳,值)}`，默认 TTL 10s。
- 四类端点使用不同 key 前缀，互不污染：`dash:stats:{days}`、`dash:recent:{limit}`、`dash:alerts:{limit}`、`dash:hot:{days}:{limit}`。
- 不同 `days`/`limit` 自然形成不同 key，不会串缓存。
- 缓存值为纯数据（dict/list），跨请求安全复用。

**为何不引入 Redis**：项目当前仅依赖 PostgreSQL，无 Redis 基础设施；进程内缓存零新增依赖、足够覆盖 15–30s 轮询的减负需求。

**多 worker 限制（已在代码注释明确）**：
- 每个 uvicorn worker 各自持有一份缓存，互不共享。N 个 worker 各自有各自命中，整体命中率随 worker 数线性下降，但**数据正确性不受影响**（每次过期都会重新查库）。
- 若未来部署多 worker 且希望统一缓存，应改为 Redis 等共享缓存（代码已留 TODO 说明）。
- **不缓存用户私有权限数据**：dashboard 接口返回全局聚合数据，与登录用户无关，所有已认证用户结果一致，跨用户复用安全。

---

## 8. 测试结果

### 8.1 测试环境说明
- 原测试库 `localhost:5433/opinion_test` 在本机未运行。为能在本地执行测试，**在同实例 5432 新建独立库 `opinion_test`（与生产 `opinion_db` 完全隔离，未触碰任何生产数据）**，并用 `scripts/init_db.py` 播种 admin / regions / keywords / data_sources。
- `conftest.py` 改为 `setdefault`，本机通过环境变量 `DATABASE_URL=...5432/opinion_test` 指向该库；原 5433 环境行为不变。

### 8.2 dashboard 测试（本次改动相关，全部通过）
```
16 passed  (tests/test_dashboard.py)
```
覆盖：鉴权 401、累计/当日/窗口口径、省级上卷（混级→仅省）、hot_keywords 真实计数与空数据稳定、days 校验（0/91→422，1/90→200）、sentiments/sources 窗口化、缓存命中/按 days 隔离/按端点隔离/过期重算。

### 8.3 全量后端测试
- dashboard 相关 **16 passed**。
- 其余 `test_ai_*` / `test_collector` / `test_government_collector` / `test_events` 存在失败与错误（共 12 failed + 7 errors）。**经核查这些模块均不 import 任何 dashboard 代码**，失败源于：① 环境无 DeepSeek API Key；② collector registry 既有 bug（`读取 data_sources 失败，回退默认源`）；③ 测试库 seeding（data_sources/regions 存在）与这些测试的历史假设冲突。**均与本次 dashboard 改动无关，非回归**。

---

## 9. 真实数据库（opinion_db）只读验证结果

> 仅执行 SELECT，未写入/修改任何生产数据。

| 验证项 | 结果 |
| --- | --- |
| 省级上卷 | `regions=[('河北省',429)]`；非省级名称集合为空 ✅ |
| 混级全归并 | days=1→72、days=7→429、days=30→429（窗口正确）✅ |
| 热门词 ≠ 敏感词 | hot: 河北157/民生70/教育66…；兼容 keywords: 事故18/舆情14/群体14…（数据源明显不同）✅ |
| 热门词真实频次 | 10 条均 `count>0`，`trend∈{up,down,flat}` ✅ |
| 空数据稳定 | 测试库无舆情时 `/hot-keywords` 返回 `{"items":[],"days":7}` ✅ |
| days 窗口差异 | days=1 hot(河北30) vs days=30 hot(河北157) 明显不同 ✅ |
| 非法 days | `?days=0`/`?days=91` → 422（pytest 已覆盖）✅ |
| 缓存 key 隔离 | `['dash:alerts:8','dash:hot:30:10','dash:hot:7:10','dash:recent:8','dash:stats:30','dash:stats:7']` 互不串 ✅ |

---

## 10. 进入前端 Vue 大屏开发前，需你拍板的产品决策

1. **`high_risk` 是否保持全量？** 当前按业务语义定为「系统高危态势（累计全量）」。若你希望它随 `days` 窗口变化（如「近 7 日新增高危」），需现在确认，否则前端 KPI 口径会与直觉不符。
2. **旧 Dashboard.vue 的语义联动**：现有页用 `riskRate = high_risk/total`、`negative% = neg/total`，其中 `high_risk`/`total` 是累计，而新的 `neg`(sentiments) 已改为窗口化 → 百分比会变成「窗口负向 / 累计总量」。是否同步把旧页相关口径统一为窗口，或在 Vue 大屏里重新设计？建议在大屏里用独立的窗口化口径，旧页可择期修。
3. **`regions` 现在只返回省级**：旧 Dashboard 的地域条形图将只显示「河北省」。是否接受旧页地域维度降级为省级（推荐，统一口径），还是要旧页保留市/县级（那需要新增一个不下卷的兼容端点）。
4. **`hot_keywords` 的 `trend` 展示**：当前趋势是基于「当前窗口 vs 紧邻前一等长窗口」的真实对比。数据若集中在最近几天，历史窗口可能为 0 导致普遍 `up`。前端是否要展示 trend，或用别的方式呈现。
5. **地图 GeoJSON 资源**：前端仍需中国省级 GeoJSON（项目内无本地资源，原型从 DataV CDN 取）。内网大屏部署前需把 GeoJSON vendoring 到 `public/`，避免外网依赖——这属于前端/Vue 阶段工作。
6. **轮询间隔与缓存 TTL**：当前后端缓存 10s、建议前端轮询 15–30s。是否需要可配置（如放 `settings` 或环境变量）以便后续调优？

---

## 附：本次未做（按你的要求）
- 未实现 WebSocket / SSE（实时方案仍建议优化轮询，详见审计报告 F 节）。
- 未开始 Vue 大屏页面。
- 未修改任何生产业务数据（仅新建独立的 `opinion_test` 测试库）。
