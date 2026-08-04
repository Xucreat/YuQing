# Phase DataSource-Filter-Config-4 预审计（PreAudit · 只读）

> 本文件仅记录审计发现，不含任何代码/数据修改。所有 DB 查询均为 `SELECT`，
> 未执行任何 `INSERT/UPDATE/DELETE/DDL`。

## 1. 当前策略解析链路

```
data_sources.config_json
        │  (registry 装配时剥离 STRATEGY_KEYS: max_items/filter_mode/keyword_scope)
        ▼
DataSourceConfig（只读访问器，注入 collector.source_config）
        │
        ▼
collector.fetch() 内部调用：
        cfg.filter_mode(<collector 自带默认>)
        cfg.keyword_scope(<collector 自带默认|None>)
        apply_keyword_scope(...) 裁剪关键词集
        │
        ▼
实际搜索关键词选择（采集行为）
```

### 默认值来源（写在各 collector `fetch()` 内，传入 `DataSourceConfig` getter）

| 采集器（class_path） | 默认 filter_mode | 默认 keyword_scope | 代码位置 |
|---|---|---|---|
| baidu_news | `region_only` | `region` | `baidu_news_collector.py:37/39` 常量 `DEFAULT_FILTER_MODE`/`DEFAULT_KEYWORD_SCOPE` |
| xinhua | `region_or_topic` | `None`（不裁剪=原行为） | `xinhua_collector.py:46` 常量 |
| people | `region_or_topic` | `None` | `people_collector.py:41` 常量 |
| chinanews | `region_or_topic` | `None` | `chinanews_collector.py:49` inline 默认 |
| generic_site | `region_only` | `None` | `generic_site.py:114` inline 默认 |
| government / hebei_news / hebei_daily / changcheng / hebei_gov / weibo_octopus / grok | **不读取** filter_mode/keyword_scope | — | 采集器内置策略 / 全量，未调用 `apply_keyword_scope` |

### 不同 collector 默认差异

- **百度新闻**：默认仅地域词（`region_only` + `region`）。
- **新华/人民/中国新闻**：默认地域+主题（`region_or_topic`），keyword_scope 未声明。
- **通用型（27 个 GenericSite）**：默认仅地域（`region_only`），keyword_scope 未声明。
- **其余采集器**：不应用此策略，使用各自内置逻辑（全量或站点自身栏目过滤）。

### 当前「无法展示」的信息（本阶段要补齐）

- 前端列表**看不到**某源"实际生效"的过滤模式/关键词范围。
- 前端**看不到**策略来源（是管理员显式配置，还是采集器默认）。
- 前端**看不到**默认策略的语义解释（如"仅地域 = 只搜地域词"）。
- 配置弹窗选择 `topic_only`/`region_only` 时**无风险提示**。

## 2. 前端现状（`frontend/src/views/Sources.vue`）

- 配置弹窗（编辑）与新建弹窗：已有 `filter_mode` / `keyword_scope` 两个 `el-select`（Phase 3 增加）。
- 数据源**列表表格无「过滤策略」列**。
- 弹窗/详情**无"生效策略解释"区块**。
- 选择 `topic_only` / `region_only` 时**无前端提示**。

结论：本阶段前端仅需"展示增强 + 提示"，不新增接口、不改保存逻辑。

## 3. 数据库现状（只读 · 生产 `127.0.0.1:5432/opinion_db`）

| 指标 | 数值 |
|---|---|
| data_sources 总数 | **38** |
| config_json 非空 | 27（均为 GenericSite 类源） |
| 使用 filter_mode | **0** |
| 使用 keyword_scope | **0** |
| opinions | 1032 |
| events | 176 |
| alert_records | 11 |
| collector_runs | 8208 |
| regions | 24 |

class_path 分布（共 38）：

```
GenericSiteCollector          27
BaiduNewsCollector            1
XinhuaCollector              1
PeopleCollector              1
ChinanewsCollector           1
GovernmentCollector          1   (全量)
HebeiDailyCollector          1   (内置策略)
ChangchengCollector          1   (内置策略)
HebeiGovCollector            1   (内置策略)
HebeiNewsCollector           1   (内置策略)
WeiboOctopusCollector        1   (内置策略)
GrokCollector                1   (辅助源，默认 disabled)
```

> 关键结论：**当前 38 个源均处于默认策略（无任何源显式配置 filter_mode/keyword_scope）**。
> 本阶段只做"展示/解析透明化"，不修改任何 `config_json`，生产采集行为零变化。

## 4. 设计决策（最小改动，严守红线）

为计算"实际生效策略"，必须知道**各采集器默认 filter_mode/keyword_scope**。这些默认值
当前写在各 collector 的 `fetch()` 内。为避免触碰 collector 抓取逻辑 / 默认行为：

- 在 `source_config.py` 新增 **只读镜像映射** `COLLECTOR_DEFAULT_STRATEGY`
  （`class_path -> (默认 filter_mode, 默认 keyword_scope)`），与现有 collector 默认
  **逐字一致**，仅用于前端"生效策略"透明化展示，**不参与采集**。
- 新增 `DataSourceConfig.effective_filter_strategy(default_filter_mode, default_keyword_scope)`
  纯读取方法，返回：
  - `configured_filter_mode` / `configured_keyword_scope`（config_json 显式值，未配置为 None）
  - `effective_filter_mode` / `effective_keyword_scope`（显式优先，否则回退采集器默认）
  - `source`：`"config"`（管理员配置） / `"collector_default"`（采集器默认） / `"not_applicable"`（采集器内置，不应用本策略）
- 后端 GET `/api/admin/data-sources` 列表/详情序列化中附加 `effective_filter_strategy` 字段，**复用既有接口，不新增端点**。
- 不新增数据库字段、不新增 migration、不改任何 `data_sources.config_json`、不进入 National-Mode。

> 关于目标中的"变更历史 / 安全回滚"：本阶段红线禁止新增字段/migration，故不新建历史表。
> 现有 `user_operation_logs`（audit_write）**已对每次 PATCH config_json 记录变更键**，
> 即为"变更历史"来源；"安全回滚"= 通过 UI/接口将 config_json 重新 PATCH 为先前值（非破坏性）。
> 报告中会明确此边界。
