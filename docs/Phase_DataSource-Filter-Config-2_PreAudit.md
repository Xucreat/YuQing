# Phase DataSource-Filter-Config-2 只读预审计

> 阶段目标：将「专用型数据源过滤策略」从代码硬编码升级为完全由 `data_sources.config_json` 控制，
> 同时保持当前廊坊区域舆情监测能力与生产采集量完全不变。
> 本文件为 **Step 1 只读审计产物**，所有结论基于源码与数据库只读查询，未做任何修改。

---

## A. 专用型采集器过滤策略硬编码审计

| 采集器 | 是否读取 `filter_mode`/`keyword_scope` | 当前默认行为 | 是否完全配置化 | 结论 |
|--------|----------------------------------------|--------------|----------------|------|
| `xinhua_collector.py`（新华网） | ✅ `cfg.filter_mode("region_or_topic")` + `cfg.keyword_scope()` | `region_or_topic`（地域或主题命中即通过） | ✅ 已配置化 | 仅需确认默认保留 |
| `people_collector.py`（人民网） | ✅ 同 xinhua | `region_or_topic` | ✅ 已配置化 | 仅需确认默认保留 |
| `chinanews_collector.py`（中国新闻网） | ✅ `cfg.filter_mode("region_or_topic")` + `cfg.keyword_scope()` | `region_or_topic` | ✅ 已配置化 | 仅需确认默认保留 |
| `baidu_news_collector.py`（百度新闻） | ❌ **完全不读取** `filter_mode`/`keyword_scope` | 硬编码 `region_only`（直接 `kws = region_kw`） | ❌ **未配置化** | **本阶段主要改造点** |
| `government_collector.py`（大厂县政府网站） | ❌ 故意全量采集（Option B），`region_kw`/`topic_kw` 不参与任何过滤 | 全量（无地域/主题前置） | N/A（设计如此） | **超出本阶段范围**（见下） |

### 百度新闻硬编码细节

`baidu_news_collector.py::fetch` 当前逻辑（节选）：

```python
cfg = self.source_config
max_items = cfg.max_items(MAX_ARTICLES)          # 已配置化
# 注意：没有 cfg.filter_mode(...) / cfg.keyword_scope(...)
if region_kw is not None:
    kws = region_kw                              # 硬编码：仅用地域词搜索
else:
    kws = keywords if keywords is not None else self.keywords
```

- 没有 `filter_mode` 读取 → 永远是 `region_only` 语义；
- 没有 `keyword_scope` 读取 → 无法通过配置切换「地域/主题」关键词集；
- 因此「百度新闻的过滤策略」**不来自 `config_json`**，违反「统一来源」目标。

### 政府网站为何不在范围内

`government_collector.py` 注释明确声明：

> region_kw / topic_kw 仅为与统一 collector 接口（service.py 注入）兼容而保留，
> 不参与任何过滤逻辑；government 维持 Option B 全量采集策略。

其设计就是「全量采集 + 后续入库/事件聚合按地域归并」，刻意不做采集期地域/主题过滤。
本任务 4 个目标源为「百度新闻、新华社、人民网、中国新闻网」，政府网站属于另一类（全量源），
将其改为按 `filter_mode` 过滤会**改变生产采集量**，违反红线「禁止扩大/改变采集范围」与 Goal 3，
故列入「已知、刻意、不改」清单，仅做审计记录。

---

## B. 统一过滤策略来源现状

目标（Goal 2）格式：

```
区域型：    { "filter_mode": "region_or_topic", "keyword_scope": "region_topic" }
仅地域：    { "filter_mode": "region_only",     "keyword_scope": "region" }
仅主题：    { "filter_mode": "topic_only",      "keyword_scope": "topic" }
```

现状：

- xinhua / people / chinanews：已在 `fetch` 中通过 `DataSourceConfig` 读取 `filter_mode`/`keyword_scope`，
  来源已统一为 `config_json`，**仅缺「空配置即回退历史默认」的文档化保障**（实际代码已做到）。
- baidu_news：**来源仍是代码分支**，未统一。→ 主要缺口。
- 前端/管理接口：`admin_data_sources.py` 的 `DEDICATED_ALLOWED_KEYS = STRATEGY_KEYS | {collection_mode}`
  已包含 `filter_mode`/`keyword_scope`，专用型源可写入这些键，`POST`/`PATCH` 均经 `_validate_collection_config`
  → `validate_data_source_config` 校验。**接口层已支持，只待 baidu 运行时真正读取。**

---

## C. 专用型默认行为（Goal 3 必须保持不变）

| 数据源 | 改造前硬编码默认 | 改造后空 `config_json` 应解析为 | 是否一致 |
|--------|------------------|----------------------------------|----------|
| 百度新闻 | `region_only`（仅地域词搜索） | `region_only` + `keyword_scope=region` | ✅ 需新增 `DEFAULT_FILTER_MODE="region_only"` / `DEFAULT_KEYWORD_SCOPE="region"` |
| 新华网 | `region_or_topic` | `region_or_topic` | ✅ 已有 `DEFAULT_FILTER_MODE="region_or_topic"` |
| 人民网 | `region_or_topic` | `region_or_topic` | ✅ 已有 |
| 中国新闻网 | `region_or_topic` | `region_or_topic` | ✅ 已有 |

结论：只要在 baidu 新增与 xinhua 同构的「配置优先、代码默认兜底」读取，且默认取 `region_only`，
生产采集行为（默认空配置）零变化。显式配置 `topic_only` 等属于**管理员主动变更采集范围**，属设计预期，
非本阶段副作用。

---

## D. 配置校验缺口（Goal 4）

当前 `validate_data_source_config`（source_config.py）仅校验 `collection_mode`：

- `collection_mode` 合法性；
- `collection_mode == "national"` 时 `filter_mode`/`keyword_scope` 约束为 `topic_only`/`topic`。

**未覆盖**：regional（或缺省）模式下 `filter_mode` 与 `keyword_scope` 的**交叉一致性**。
例如以下矛盾组合当前被放行：

```json
{ "filter_mode": "region_only", "keyword_scope": "topic" }   // 仅地域过滤却用纯主题词范围
{ "filter_mode": "topic_only",  "keyword_scope": "region" }  // 纯主题过滤却用纯地域词范围
```

这两类应被明确拒绝（422，不静默修正）。`FILTER_MODES` / `KEYWORD_SCOPES` 常量已存在，
仅需补充跨字段一致性判断。

---

## E. 管理接口支持（Goal 5）

只读核对 `admin_data_sources.py`：

- `GENERIC_ALLOWED_KEYS` 已含 `filter_mode` / `keyword_scope` / `collection_mode` → 通用型可配置。
- `DEDICATED_ALLOWED_KEYS = STRATEGY_KEYS | {"collection_mode"}`（STRATEGY_KEYS 含 `filter_mode`/`keyword_scope`）
  → 专用型可配置。
- `POST /admin/data-sources`（`_validate_create`）与 `PATCH /admin/data-sources/{id}`（update 分支）
  均对含策略键的配置调用 `_validate_collection_config` → `validate_data_source_config`。
- **`source_type` / `class_path` / `key` 均不在 PATCH 可变字段列表中**（PATCH 仅改 enabled / priority /
  config_json / schedule_enabled / schedule_interval_minutes）→ 「不允许修改 source_type / 系统约束」已天然满足。

结论：管理接口层已具备能力，本阶段**无需改动 admin_data_sources.py 的允许清单**，
仅需在 `validate_data_source_config` 补 regional 交叉校验即被接口复用。

---

## F. 数据库只读基线（Phase 开始前）

```
regions      = 24   （含 National-2 全国哨兵 code=000000）
opinions     = 1027
events       = 175
alert_records= 11
5 个专用型源 config_json 均为 '{}'（空），无任何现有配置冲突。
```

---

## 审计结论

1. **真正未配置化的专用型源只有 `baidu_news`**；xinhua/people/chinanews 已配置化，默认行为正确。
2. 改造只需两处最小改动：
   - `baidu_news_collector.py`：新增 `DEFAULT_FILTER_MODE="region_only"` / `DEFAULT_KEYWORD_SCOPE="region"`，
     读取 `filter_mode`/`keyword_scope`，按 `filter_mode` 选择搜索关键词集（默认 `region_only` 与现状一致）。
   - `source_config.validate_data_source_config`：补充 regional 模式下 `filter_mode`/`keyword_scope` 交叉一致性校验。
3. `government` 为刻意全量源，超出本阶段 4 个目标源范围，不改动。
4. 管理接口已支持，无需改 allowlist。
5. 所有改动均属「配置读取逻辑 / 校验逻辑」，不触碰 Opinion/Event/Risk 模型、scheduler、registry、
   collector 数据获取机制（HTTP 抓取不变）、数据库结构/数据，符合全部红线。
