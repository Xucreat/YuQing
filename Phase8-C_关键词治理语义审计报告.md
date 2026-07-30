# Phase8-C 关键词治理语义审计报告

> 审计日期：2026-07-29  
> 审计方式：代码、前端实现及生产数据库只读核验  
> 审计边界：未修改代码、数据库、关键词、数据源配置、采集策略、RiskEngine、Alert 或 Event

## 1. 审计范围

本次审计沿以下真实调用链展开：

1. `keywords` 表及关键词管理 API；
2. `keyword_service.py` 的扁平、分组、敏感词和严重度词读取；
3. `CollectorService` 对 `keywords / region_kw / topic_kw` 的注入；
4. `backend/app/collectors/` 下全部具体采集器；
5. `data_sources.config_json` 的当前生产配置；
6. `AlertService`、规则分析、RiskEngine 和 Dashboard 对关键词的读取；
7. 前端关键词管理页与数据源管理页的可解释能力。

### 1.1 当前生产快照

- monitoring + 地域：28 条，其中 16 条启用、12 条停用；
- monitoring + 主题：14 条，全部启用；
- sensitive：17 条，全部启用；
- data_sources：37 条，其中专用型 11 条、Generic 26 条；
- 当前启用：专用型 5 条、Generic 11 条；
- 26 条 Generic 均存在 `keywords` 字段：23 条非空、3 条为空字符串，不存在字段缺失记录；
- 11 条当前启用的 Generic 全部使用非空数据源独立关键词。

### 1.2 背景与当前代码不一致

审计背景称国家级源仍保持 Option C（`region_or_topic`），但当前代码中的新华网、人民网、中国新闻网均只使用 `region_kw`，`topic_kw` 仅保留接口兼容，不再参与过滤。

因此，当前生产代码的真实语义已经不是 Option C。报告后续均以当前代码为准；本审计不判断是否应恢复或再次切换策略。

---

## 2. 当前真实行为

### 2.1 关键词读取链路

`CollectorService` 每次采集运行读取两套结果：

- `monitoring_kw = get_monitoring_keywords(db)`：所有启用 monitoring 词的扁平列表；
- `grouped = get_monitoring_keywords_grouped(db)`：按 category 分组；
- `region_kw = grouped.get("地域", [])`；
- `topic_kw = grouped.get("主题", [])`。

随后统一调用：

```python
collector.fetch(
    keywords=monitoring_kw,
    region_kw=region_kw,
    topic_kw=topic_kw,
)
```

关键词并未在所有专用型采集器中固定。生产主链路会动态注入数据库中的启用词，但每个采集器实际消费的参数不同。

### 2.2 缓存与生效时间

- monitoring 扁平、monitoring 分组、sensitive 各自使用进程内 60 秒缓存；
- 关键词 API 的新增、编辑、启停、删除在提交后调用 `clear_keyword_cache()`，当前单 worker 场景可立即失效；
- 若绕过 API 直接修改数据库，最长约 60 秒后生效；
- 多 worker 时缓存互不共享，执行 API 请求的 worker 会立即清理，其他 worker 最长等待 TTL；
- Dashboard 另有 10 秒只读缓存，关键词 CRUD 不直接清理该缓存，因此展示可能短暂延迟。

### 2.3 category 的真实约束

采集服务只识别精确分类名 `地域` 和 `主题`。关键词页面的分类字段目前是自由文本：

- 分类拼写错误的 monitoring 词仍会进入扁平 `monitoring_kw`；
- 但不会进入 `region_kw` 或 `topic_kw`；
- 同一个词因采集器消费参数不同，可能在微博/预警中生效、在地域型采集器中不生效。

---

## 3. 关键词影响矩阵

| 关键词类型 | 数据库来源 | 读取位置 | 影响模块 | 是否影响采集 | 是否影响风险 | 是否影响展示 |
|---|---|---|---|---|---|---|
| monitoring + 地域 | `keywords.type='monitoring' AND category='地域' AND is_enabled=true` | `get_monitoring_keywords_grouped()`；同时进入扁平接口 | CollectorService、地域型采集器、无独立词的 Generic；扁平形式也进入默认预警和 Dashboard | 是。当前直接影响百度、新华、人民网、中新网；政府源除外 | 不直接影响 RuleFallback/RiskEngine；微博准入启用时参与相关性 | 是。关键词页直接展示；Dashboard 热词使用扁平 monitoring |
| monitoring + 主题 | `keywords.type='monitoring' AND category='主题' AND is_enabled=true` | 分组 `topic_kw`；同时进入扁平 `monitoring_kw` | 默认预警、Dashboard；微博八爪鱼启用时按扁平列表过滤并参与准入 | 当前启用采集源中基本不影响采集：国家级三源、百度、Generic 地域模式均忽略；显式 Generic 使用自己的词 | 不直接影响风险评分；仅在微博准入中作为公共事务信号 | 是。关键词页、Dashboard；也会影响未配置自身关键词的预警规则匹配范围 |
| sensitive / 风险词 | `keywords.type='sensitive' AND is_enabled=true` | `get_sensitive_keywords()`、`get_severity_keywords()` | RuleFallbackProvider、RiskEngine 严重度覆盖 | 否 | 是。`weight` 影响规则风险分析；正 `severity_weight` 覆盖内置严重度 | 间接影响 Opinion 的分析关键词、风险因子、风险分值和相关展示 |

### 3.1 职责结论

- 采集过滤条件：monitoring 词；但地域、主题及扁平列表的实际消费范围不同；
- 风险评分条件：sensitive 词及内置风险/严重度词；
- 统计展示条件：Dashboard 热词读取 monitoring 词，统计历史 Opinion 的真实提及；
- monitoring 的 `weight` 当前不参与采集过滤、默认预警查询或 Dashboard 排序；
- sensitive 全部停用也不会关闭全部风险识别，系统会回退内置风险词和内置严重度词。

---

## 4. 数据源关键词策略矩阵

### 4.1 专用型及兼容采集器

| collector | 数据源/状态 | 关键词来源 | 过滤模式 | 是否动态读取 | 说明 |
|---|---|---|---|---|---|
| `GovernmentCollector` | 大厂县政府网站，启用 | 接收三个参数但全部忽略 | Option B 全量采集 | 否 | 关键词管理启停不改变其抓取 |
| `BaiduNewsCollector` | 百度新闻，启用 | `region_kw` | 每个启用地域词作为百度新闻搜索词 | 是 | `topic_kw` 忽略；`keywords` 只用于无 `region_kw` 的旧调用 |
| `XinhuaCollector` | 新华网，启用 | `region_kw` | 列表/正文解析后地域 OR 过滤 | 是 | 当前忽略 `topic_kw`；`keywords` 仅旧调用兼容 |
| `PeopleCollector` | 人民网，启用 | `region_kw` | 列表/正文解析后地域 OR 过滤 | 是 | 当前忽略 `topic_kw`；`keywords` 仅旧调用兼容 |
| `ChinanewsCollector` | 中国新闻网，启用 | `region_kw` | RSS 标题+摘要地域 OR 过滤 | 是 | 当前忽略 `topic_kw`；`keywords` 仅旧调用兼容 |
| `HebeiNewsCollector` | 河北新闻网，停用 | `region_kw` | 地域 OR 过滤 | 是 | `topic_kw` 虽传入，但默认 `region_only` 下不参与；`keywords` 为旧调用兼容 |
| `HebeiDailyCollector` | 河北日报，停用 | `region_kw` | 地域 OR 过滤 | 是 | 同上 |
| `ChangchengCollector` | 长城网，停用 | `region_kw` | 地域 OR 过滤 | 是 | 同上 |
| `HebeiGovCollector` | 河北省人民政府，停用 | `region_kw` | 地域 OR 过滤 | 是 | 同上 |
| `WeiboOctopusCollector` | 微博（八爪鱼 API），停用 | 扁平 `keywords` | 标题+正文命中任一启用 monitoring 词 | 是 | 主动丢弃 `region_kw/topic_kw` 分组；另受 `WEIBO_ENABLED` 双开关控制 |
| `GrokCollector` | Grok 实时搜索，停用 | 设计上为扁平 `keywords` | 每个关键词独立检索 | 设计上是 | 当前 `fetch` 不接受 `region_kw/topic_kw`，按统一 Service 调用会 `TypeError`，启用前存在契约风险 |
| `RSSCollector` | 未注册生产数据源 | 不过滤 | RSS 全量返回 | 否 | `fetch` 仅接受 `keywords` 且不使用；若直接纳入统一 Service 也存在参数契约风险 |
| `MockCollector` | mock 模式 | 固定模拟数据 | 不过滤 | 否 | `fetch` 仅接受 `keywords` 且不使用；统一参数契约存在兼容风险 |
| 旧 `WeiboCollector` | 未注册生产数据源 | 构造时的配置兜底词 | 最多取前三个构造词搜索 | 否 | `fetch(keywords=...)` 实际不消费传入值；已被八爪鱼实现替代 |

说明：`BaseCollector`、`BaseHttpCollector` 和 `common.py` 为抽象/公共实现，不作为独立生产数据源。

### 4.2 GenericSiteCollector 三态语义

当前实现确实存在以下隐式三态：

| `config_json` 形态 | 内部判定 | 最终关键词来源 | 实际过滤语义 |
|---|---|---|---|
| 存在且 `keywords` 非空 | `keywords_explicit=True` | 数据源自身配置 | 标题+正文命中任一 source keyword |
| 完全不存在 `keywords` 字段 | `keywords_explicit=False` | `region_kw` | 使用全局启用地域词；虽然传入 `topic_kw`，默认模式仍为 `region_only` |
| 存在且 `keywords=""` | `keywords_explicit=True` 且词列表为空 | 空列表 | `matches_keywords()` 对空列表返回 True，即 no_filter 全量放行 |

因此用户提出的隐式语义判断成立：

1. 字段存在且非空 = `source_keywords`；
2. 字段缺失 = `global_region`；
3. 空字符串 = `no_filter`。

但这三个模式没有在模型、API 或前端中以业务字段命名，只由 JSON 字段形态推断。

### 4.3 当前生产配置影响

- 当前不存在 `keywords` 字段缺失的 Generic 数据源；
- 当前 11 条启用 Generic 全部为 `source_keywords`；
- 因此关键词管理页中的 monitoring 启停目前不会改变任何启用 Generic 的采集过滤；
- 部分 Generic 独立词包含已经在全局关键词管理中停用的词，例如“河北”，管理员停用全局词并不会停用数据源独立副本；
- 3 条 `keywords=""` 的 no_filter 数据源当前均为停用状态，但未来启用即会全量放行。

---

## 5. 全部停用行为分析

### 5.1 monitoring 全部停用

`get_monitoring_keywords()` 只查询启用记录。结果为空时无法区分“表从未初始化”和“表中记录被全部停用”，两种场景都会回退 `.env COLLECTOR_KEYWORDS`。

`get_monitoring_keywords_grouped()` 同样查询启用记录，结果为空时返回：

```python
{"general": [环境变量兜底词...]}
```

CollectorService 只读取键名 `地域` 和 `主题`，因此最终得到：

```text
monitoring_kw = .env 兜底词
region_kw = []
topic_kw = []
```

这使同一次采集运行中的扁平链路与分组链路产生相反语义。

### 5.2 全部停用场景行为矩阵

| 链路 | 全部停用结果 | 是否符合管理员通常预期 |
|---|---|---|
| 关键词管理 API | 数据库记录仍返回，状态均为 `false`；筛选“启用”返回 0 条 | 是 |
| API 后缓存 | 正常 API 启停会立即清理关键词缓存；绕过 API 最长等待 60 秒 | 基本符合 |
| `get_monitoring_keywords()` | 返回 `.env COLLECTOR_KEYWORDS`，不是 `[]` | 否 |
| `get_monitoring_keywords_grouped()` | 返回 `general` 兜底组；`地域/主题` 均缺失 | 不直观 |
| CollectorService | 同时持有非空兜底 `monitoring_kw` 与空 `region_kw/topic_kw` | 否，内部语义分裂 |
| 地域过滤公共函数 | 空 `region_kw` fail-safe，全部拦截 | 对地域型采集器符合“停用后不采”；但被记录为配置异常 |
| 百度新闻 | 0 次搜索、0 条结果 | 是 |
| 新华/人民网/中新网 | 空地域导致 0 条结果 | 是 |
| 河北系列专用源 | 若启用，空地域导致 0 条结果 | 是 |
| GovernmentCollector | 继续 Option B 全量采集 | 若管理员认为停词等于停采，则不符合；按源策略本身则符合 |
| Generic + source keywords | 继续按数据源独立词采集 | UI 未解释时不符合 |
| Generic + 字段缺失 | 空地域导致 0 条结果 | 是 |
| Generic + `keywords=""` | 继续全量采集 | UI 未解释时不符合，风险高 |
| 微博八爪鱼 | 若启用，继续按 `.env` 兜底 monitoring 词过滤 | 否 |
| 默认预警规则 | 无规则独立词时继续按 `.env` 兜底 monitoring 词匹配 | 否 |
| 有独立关键词的预警规则 | 继续按规则自身关键词匹配 | 取决于规则设计，但与全局停用无关 |
| Dashboard 热门关键词 | 继续统计 `.env` 兜底词；另可能有最长约 10 秒展示缓存 | 否 |
| 仅停用 monitoring 时的风险评分 | sensitive 独立读取，不受影响 | 符合职责分离 |
| sensitive 全部停用 | RuleFallback 回退内置风险词；RiskEngine 仍以内置严重度词为底座 | 若期望关闭风险识别则不符合；按系统安全兜底设计则符合 |

### 5.3 语义风险判断

存在“管理员点击全部停用，但系统仍继续采集”的真实语义风险，来源包括：

1. GovernmentCollector 明确全量采集；
2. 当前所有启用 Generic 都使用数据源独立词；
3. `keywords=""` 的 Generic 启用后会全量放行；
4. 微博等扁平消费者会得到 `.env` 兜底词而非空列表；
5. 默认预警和 Dashboard 也继续消费 `.env` 词。

问题不是所有继续行为都错误，而是前端没有展示这些例外，且“全部停用”的服务契约本身不一致。

---

## 6. 当前设计风险

| 等级 | 问题 | 影响 |
|---|---|---|
| P0 | 全部停用 monitoring 与“表未初始化”不可区分，扁平接口自动回退 `.env` | 管理员停用意图被覆盖；采集、预警、Dashboard 行为不一致 |
| P0 | 审计背景仍称国家级源为 Option C，但当前代码已是 region-only | 策略文档、测试口径与生产行为可能漂移，后续审计结论失真 |
| P1 | Generic 关键词模式由 JSON 字段存在性和空字符串隐式推断 | 配置可读性差，空字符串误操作可导致全量放行 |
| P1 | 所有启用 Generic 均绕过全局 monitoring 词 | 管理员在关键词页启停后无法预期这些来源不受影响 |
| P1 | 全局词与数据源独立词存在重复副本 | 全局停用“河北”等词无法停用 Generic 中的同名词 |
| P1 | category 为自由文本，但采集只识别精确的 `地域/主题` | 拼写或分类错误会造成部分链路生效、部分链路失效 |
| P1 | Grok/RSS/Mock 等 `fetch` 参数契约未与统一 Service 对齐 | 停用源未来启用或 mock 模式运行时可能直接失败，无法进入关键词语义判断 |
| P2 | 关键词页不展示作用范围；数据源页只展示原始 JSON | 配置正确也无法由管理员验证最终有效行为 |
| P2 | 关键词缓存与 Dashboard 缓存分别失效 | 修改后展示可能短暂不一致；多 worker 下最长等待关键词 TTL |

---

## 7. 是否需要改造

建议进入实施阶段，但应限定为“小范围语义治理”，不进行采集策略优化。

### 7.1 是否需要显式 `keyword_mode`

建议增加显式模式。优先放入现有 `config_json`，无需新增数据库字段或迁移：

```text
global_region      使用全局启用地域词
global_monitoring  使用全部全局启用 monitoring 词
source_keywords    使用数据源独立关键词
no_filter          不做关键词过滤
```

理由：

- 当前已经存在四种业务语义，只是没有命名；
- 显式字段能区分“漏填”和“有意 no_filter”；
- 可在不改变现有数据库结构的前提下完成；
- 可以对现有配置做兼容映射，先展示、后治理，不必立即批量修改数据。

专用型数据源仍应保持 `config_json={}`。其模式可由后端根据 collector 类声明/映射后只读返回，不要求管理员编辑专用采集器配置。

---

## 8. 最小治理方案

### P0：统一停用语义

1. 区分“keywords 表无 monitoring 记录”和“存在记录但全部停用”；
2. 仅在真正未初始化时允许 `.env` 应急兜底；
3. 存在记录但全部停用时，monitoring 扁平与分组接口应表达同一个空状态；
4. 为采集、默认预警和 Dashboard 分别补充空状态契约测试，避免简单返回 `[]` 后默认预警反而取消关键词条件、扩大匹配范围；
5. sensitive 的内置安全兜底保持独立，不与 monitoring 停用语义混合。

### P0：建立策略基线

1. 记录国家级三源当前真实模式为 region-only；
2. 将报告、测试名称和运行基线与当前代码对齐；
3. 是否恢复 Option C 另行决策，本阶段不切换。

### P1：显式化数据源模式

1. 在 Generic `config_json` 支持 `keyword_mode`，并加入 API 白名单校验；
2. 兼容映射现有配置：非空 `keywords` → `source_keywords`，字段缺失 → `global_region`，空字符串 → `no_filter`；
3. 新建/编辑时不再以空字符串隐式表达 no_filter；
4. 不批量删除现有独立词，不自动切换数据源策略。

### P1：增加只读可解释结果

建议在现有数据源列表响应中计算并返回，无需新表：

```text
keyword_mode
keyword_source
effective_keywords
effective_keyword_count
```

关键词列表可增加只读影响摘要：

```text
collection_scope
affected_source_count
used_by_alert_fallback
used_by_risk
```

这些字段均可运行时推导，不要求数据库迁移。

### P2：输入约束与测试

1. monitoring 分类使用受控选项，至少约束 `地域/主题`；
2. 为所有可注册采集器增加统一 `fetch(keywords, region_kw, topic_kw)` 契约测试；
3. 增加 Generic 三态/四模式测试；
4. 前端明确区分“监测词”“敏感风险词”，避免把启停理解成全系统总开关。

---

## 9. 前端可解释性与明确不做事项

### 9.1 前端缺失项

| 能力 | 当前状态 | 建议 |
|---|---|---|
| 数据源有效关键词展示 | 缺失。列表只显示类型、质量和状态；配置弹窗只展示原始 `config_json` | 在现有数据源页展示模式、来源和有效词数量；详情/提示中展示有效词 |
| 关键词影响范围展示 | 缺失。关键词页只显示类型、来源、状态、权重和分类 | 展示影响的数据源数量及“全局/独立/未使用”范围 |
| 采集/风险职责区分 | 不足。仅用“监测词/敏感词”标签，未解释地域、主题的真实消费链路 | 增加职责列：采集地域、采集扁平、默认预警、风险评分、统计展示 |
| 全部停用后果提示 | 缺失 | 在最后一个启用词停用前展示实际影响摘要，不把它描述成“停止全部采集” |
| no_filter 风险提示 | 缺失。只能从 JSON 空字符串推断 | 显式显示 `no_filter` 并标记全量放行风险 |
| 专用型有效策略 | 缺失。当前只提示“使用系统内置逻辑” | 显示“全量/全局地域/全局 monitoring”等实际模式 |

管理员当前无法可靠回答：

1. 一个数据源最终使用哪些关键词；
2. 一个关键词影响哪些数据源；
3. 一个词参与采集、预警、风险还是仅统计展示。

### 9.2 明确不做事项

本报告不建议在本阶段进行以下工作：

- 不恢复或切换 Option C/C+/C++；
- 不调整现有关键词内容或启停状态；
- 不批量修改 Generic 数据源配置；
- 不修改 RiskEngine、Alert 或 Event 业务模型；
- 不新增数据库字段或迁移；
- 不引入 AI、ES、Redis、MQ；
- 不建设独立监控平台；
- 不以一次大范围重构替代最小语义治理。

## 最终结论

关键词管理的单条启停写库和缓存失效机制是有效的，但“启停影响范围”并非全局统一。当前最大问题是：管理员界面展示的是关键词状态，系统执行的是多套隐式作用域和兜底规则。

建议进入实施阶段，推荐最小修改范围为：

1. 修正 monitoring 全部停用与未初始化无法区分的问题；
2. 为 Generic 增加 `config_json.keyword_mode` 显式语义及兼容映射；
3. 在现有数据源页和关键词页增加只读有效策略/影响范围展示；
4. 补充空关键词、Generic 模式和 collector 参数契约测试；
5. 不改变任何采集召回策略、风险模型、预警模型或数据库结构。
