# Phase Foreign-Source-1 审计报告（Phase 0）

> 审计日期：2026-08-07
> 角色：Senior Backend Engineer
> 范围：只读审计，未改动任何代码 / 数据库 / 配置。
> 目标：确认「在不修改既有中文源 / 廊坊·全国视图 / 风险模型 / 看板逻辑的前提下，新增国外新闻 RSS 数据源（CNN / Fox News / NYT / WSJ）」的可复用链路、修改点与风险点，并在编码前暴露阻塞项。

---

## 一、结论摘要

| 维度 | 结论 |
|------|------|
| 是否复用既有采集框架 | ✅ 能。`BaseCollector` + `registry` 表驱动装配 + `CollectorService` 闭环可直接复用；新增 `foreign_rss.py` 与 4 个数据源行即可上线，无需改 registry / CollectorService 主流程。 |
| 区域归属是否符合「河北省 (id=2)」要求 | ✅ 已实测确认。`Region.code='130000' → id=2 (河北省)`；`collection_mode="regional"` + `scope_region_codes=["130000"]` 经 `OpinionRegionService.decide` 落到 id=2，**不进入全国哨兵 (id=24)**。 |
| 准入是否放行国外稿 | ✅ 国外条目 `source_type` 为空（非 weibo）、`collection_mode="regional"`（非 national）→ `OpinionAdmissionService.evaluate` 走 `default_allow_non_weibo` 分支 `accepted=True`，**不依赖中文关键词重过滤**。 |
| 既有中文源是否受影响 | ✅ 本方案全部为 additive（新文件 / 新数据行 / 新类型枚举值 / 新前端 tab），既有 `regional` / `national` 语义与中文关键词消费逻辑逐字节不变。 |
| 🔴 最大阻塞项 | **管理后台 API（`admin_data_sources.py`）会把任何「非 generic、非 MediaCrawler」的采集器归类为「专用型（dedicated）」并拒绝其 config_json 含 `is_foreign/keywords/feeds`**。若不新增 foreign 分类与校验分支，Phase 3/6 经后台创建/更新外网源会被 422 拒绝。 |
| 第二风险 | **`validate_data_source_config`（Phase 7 计划复用）是 MediaCrawler 专属校验器**，会拒绝 `is_foreign` 等未知键，且只对 MediaCrawler 源调用。直接复用它与本方案冲突，需在独立的 foreign 校验分支实现「is_foreign ⇒ keywords 非空」。 |

**总体判定**：技术路线可行，区域/准入链路经代码与 DB 双重验证成立；落地前须先解决管理后台分类网关（M4）与 Phase 7 校验落点（M7）两处设计对齐问题。

---

## 二、当前可复用链路（逐项核对要求清单）

| # | 审计对象 | 文件 | 复用结论 |
|---|---------|------|---------|
| 1 | Collector 架构 | `collectors/base.py` | `BaseCollector` 抽象 `fetch() -> list[dict]`，约定「采集器不碰 DB、流程 fetch→Service→DB」。ForeignRSSCollector 直接继承即可。✅ |
| 2 | RSSCollector | `collectors/rss_collector.py` | 提供惰性 `feedparser` 范式；但其 `source_name` 恒为 `"rss"`、feeds 来自 env，不满足「每源独立 source_name」要求 → **不直接复用类，仅参考其惰性导入方式**。`common.parse_rss` / `_feed_publish_time` 可直接复用解析 RSS。✅ |
| 3 | ChinanewsCollector | `collectors/chinanews_collector.py` | **最佳范本**：专属 `source_name` + config 驱动 + RSS 解析 + 关键词过滤 + `apply_keyword_scope`。仿照新建 4 个薄子类。✅ |
| 4 | registry.resolve_collectors | `collectors/registry.py` | `import_class` 动态装配 + 读 `data_sources` 表；`_build_collector` 先把 `STRATEGY_KEYS`(max_items/filter_mode/keyword_scope) 剥离后再 `cls(**kwargs)`，并注入 `scope_region_codes` 与 `source_config`。新增源 = 插一行 + 薄类，registry 零改动。✅ 但注意：`collection_mode` 不在 STRATEGY_KEYS，会被透传到 `__init__`（见风险 R2）。 |
| 5 | CollectorService | `collectors/service.py` | `_process_collector` 对非 MediaCrawler 采集器执行 `collector.fetch(keywords=monitoring_kw, region_kw=region_kw, topic_kw=topic_kw)`，随后用 `OpinionRegionService.decide(scope_region_codes, collection_mode)` 与 `OpinionAdmissionService.evaluate` 闭环。链路对新增采集器透明。✅ |
| 6 | DataSourceConfig | `collectors/source_config.py` | `collection_mode()` 从 config_json 读 `collection_scope`/`collection_mode`；`COLLECTION_MODES={"regional","national"}` 已含 `regional`。无需改动。✅ 但 `collection_mode` 必须由 config_json 承载（见 M2 说明：DataSource 模型无该列）。 |
| 7 | Keywords API | `api/keywords.py` | `ALLOWED_TYPES={"monitoring","sensitive"}`，`KeywordCreate.model_post_init` 校验。新增 `monitoring_en` 仅需在此集合追加一项。Keyword 模型 `type` 为 `String(16)`、**无 CHECK 约束**，DB 层天然接受新值。✅ |
| 8 | Keywords.vue | `frontend/src/views/Keywords.vue` | 已具备完整 CRUD + 筛选；新增 `el-tabs`（中文 / 外网），外网页默认 `type="monitoring_en"` 复用同一套查询/新增/编辑/删除/启停即可，不复制 CRUD。✅ |
| 9 | Sources.vue | `frontend/src/views/Sources.vue` | 已具备列表/配置/新建弹窗；新增 `el-tabs`（国内 / 外网），外网页按 `config_json.is_foreign=true` 过滤、新建时默认 `collection_mode=regional` + `scope=["130000"]`。✅ 但后台列表接口目前**无 is_foreign 过滤参数**，需配套（见 M6）。 |

**区域路由与准入的端到端验证（代码 + DB）**：
- `OpinionRegionService.decide`：`collection_mode="regional"` → `national=False`；英文文本不含中文廊坊别名 → `hits=[]` → 回落 `_default_scope_region(["130000"])` → `Region.code='130000'` → **id=2（河北省）**。
- 实测 SQL：`SELECT id,code,name FROM regions WHERE code='130000'` → `(2, '130000', '河北省')` ✅。
- `OpinionAdmissionService.evaluate`：非 weibo、非 national → `default_allow_non_weibo` → `accepted=True, relevance_score=100`。国外稿不被中文关键词门槛拦截。

---

## 三、修改点（实现阶段必须改动的文件）

### M1 · 新增 `backend/app/collectors/foreign_rss.py`（Phase 1/2）
- `class ForeignRSSCollector(BaseCollector)`，4 个薄子类 `CNNCollector / FoxNewsCollector / NYTCollector / WSJCollector`，各设独立 `source_name`（CNN / Fox News / New York Times / Wall Street Journal），`feeds` 从 config_json 读取（不硬编码 URL）。
- **`__init__(self, feeds=None, keywords=None, is_foreign=False, **kwargs)`**：必须吸收 registry 可能透传的 `collection_mode` / `collection_scope` / `region_kw` 等额外键（参考 `GenericSiteCollector.__init__(config=None, **kwargs)` 的吸收范式），避免 `TypeError`。
- **`fetch(self, **kwargs)`**：必须吸收 `keywords / region_kw / topic_kw` 等调用参数但**忽略其语义**（这些都是中文监测词，不得用于外网过滤）。仅用 `self.keywords`（来自 config_json 的英文词）做过滤。
- 过滤逻辑：若 `config_json.keywords` 非空 → 仅保留 `title/content` 命中**英文关键词**的条目（建议大小写不敏感匹配）；若为空 → **返回 `[]`**（禁止全量入库）。不复用中文 `matches_keywords`。
- 复用 `common.parse_rss` / `_feed_publish_time` 解析 RSS，产出统一结构 `{title, content, url, source, publish_time}`，`source` 取各子类 `source_name`。

### M2 · 新增 4 条 `data_sources`（Phase 3，默认 `enabled=false`）
- `collection_mode` 必须放在 **config_json** 内（DataSource 模型无该列，Service 经 `source_config.collection_mode()` 从 config_json 读取）。
- 行结构：`type` 可设新值（如 `foreign_rss`，但需在 M4 的 `_TYPE_CLASS_PATH` 注册）；`class_path='app.collectors.foreign_rss.XXXCollector'`；`scope_region_codes='130000'`；`config_json={"is_foreign":true,"keywords":["Hebei","Langfang","Xiongan","Shijiazhuang"],"feeds":[],"collection_mode":"regional"}`。

### M3 · 英文关键词命名空间（Phase 4）
- `api/keywords.py`：`ALLOWED_TYPES` 增加 `"monitoring_en"`（仅扩展集合，不改动既有值）。
- `services/keyword_service.py`：新增 `get_monitoring_en_keywords_grouped()`（参考 `get_monitoring_keywords_grouped`，按 `category` 分组、`type='monitoring_en'` 过滤）；**不修改**既有 `get_monitoring_keywords()`。

### M4 · 🔴 管理后台分类网关（Phase 3/6/7 必须，否则后台不可用）
- `api/admin_data_sources.py`：
  - 新增 `_is_foreign(class_path)` 判定（`collector_capability` 或 class_path 包含 `foreign_rss`）。
  - 在 `_validate_create` 与 `update_data_source` 的「专用型 else 分支」中，**新增 foreign 分支**：允许 config_json 含 `{is_foreign, keywords, feeds, collection_mode, collection_scope, filter_mode, keyword_scope, max_items}`；复用 `_validate_collection_config` 做 filter_mode/keyword_scope 语义组合校验。
  - `_TYPE_CLASS_PATH` 增加 `"foreign_rss" → "app.collectors.foreign_rss.ForeignRSSCollector"`，使前端可选取。
  - 应用「is_foreign ⇒ keywords 非空」强制规则（见 M7）。
- 不改动：generic / mediacrawler / 现有专用型（Government/Xinhua/...）路径。

### M5 · Keywords.vue 增加外网页签（Phase 5）
- 增加 `el-tabs`：中文关键词 | 外网数据源关键词。
- 中文页完全保持现状；外网页默认 `filters.type / form.type = "monitoring_en"`，复用现有查询/新增/编辑/删除/启停，**不复制 CRUD**。

### M6 · Sources.vue 增加外网页签（Phase 6）
- 增加 `el-tabs`：国内数据源 | 外网数据源。
- 国内页行为完全不变。
- 外网页：`config_json.is_foreign=true` 过滤（建议后台列表接口新增 `?is_foreign=true` 参数；或前端从全量列表客户端过滤）。
- 新建外网源时默认 `collection_mode=regional`、`scope_region_codes=["130000"]`、`config_json={"is_foreign":true}`；不新增数据库字段。

### M7 · 校验规则落点（Phase 7，对齐设计）
- 计划「复用 `validate_data_source_config` 增加 is_foreign 规则」**与本方案冲突**：该函数在 `source_config.py` 中为 MediaCrawler 专属（未知键按 `MEDIACRAWLER_CONFIG_KEYS` 拒绝，`is_foreign/feeds` 不在其中会被拒；且 registry 仅对 MediaCrawler 源调用它）。
- **建议**：将「is_foreign ⇒ keywords 非空，否则禁止启用」规则实现在 M4 的 `_validate_foreign_config` 分支内（create/update 校验 + 灰度放行前校验）。若坚持进 `validate_data_source_config`，须先放宽其 unknown-key 网关以放行通用键，但会削弱 MediaCrawler 校验强度——不推荐。

---

## 四、风险点（编码前必须知悉）

- **R1（阻塞·最高优先级）管理后台分类网关**：未做 M4 时，所有外网源的 create/update 会被 `DEDICATED_EMPTY_HINT`（「当前采集器为专用型采集器，仅允许空配置」）拦截。这是 Phase 3/6 经后台落地的唯一硬阻塞。
- **R2（collection_mode 透传）**：`collection_mode` 不在 `STRATEGY_KEYS`，registry `_build_collector` 会将其作为 kwarg 传给 `cls(**kwargs)`。若 ForeignRSSCollector `__init__` 不接受该键 → `TypeError` → 该源装配失败（记为 `CollectorRun(status=failed)`）。**必须用 `__init__(..., **kwargs)` 吸收**（已写入 M1）。
- **R3（GFW 出口，运营风险）**：CNN/Fox 多数时段可达；NYT/WSJ 境内通常不可达（见既往评估方案）。代码层面不可解，按 Phase 8 灰度顺序 CNN→Fox→NYT→WSJ 推进，WSJ 不稳定则保持 disabled。
- **R4（英文风险/情感模型失效）**：`RiskEngine` 与 `RuleFallbackProvider` 100% 基于中文词表，英文稿 `risk_score≈20 / sentiment=neutral / risk_category=other`。本期已知限制，**非 bug**，报告须写明。
- **R5（杜绝中文关键词污染）**：`CollectorService` 会向 `fetch()` 传入 `region_kw/topic_kw`（中文监测词）。ForeignRSSCollector.fetch 必须**显式忽略**这些参数、只用自身 config 的英文 `keywords` 过滤，否则会触发「中文词对外文零命中 → 全量丢弃」或误用中文词。这是「不污染关键词体系」红线在代码层的具体落点。
- **R6（既有中文源零影响）**：已确认所有改动均为 additive。既有河北源（scope 130000）与新国外源走同一条 `regional → id=2` 路由，互不干扰；`national` 视图逻辑、中文 `type='monitoring'` 消费、告警与热词均不被触碰。
- **R7（区域 id 已验证）**：`Region.code='130000' → id=2`，国外稿落河北省桶、不进全国桶（id=24）。✅ 已实测。
- **R8（采集运行 warning 误标，轻微）**：`CollectorService` 在 `region_kw` 为空时会把该次运行标 `status="warning"`。外网源本身不依赖中文 `region_kw`（区域由 scope 决定），但若中文监测词被全部停用，`region_kw=[]` 会触发该 cosmetic warning，不影响入库，仅需在验收时注意区分。

---

## 五、Phase 0 确认清单（进入编码前需你拍板）

1. **M4 分类网关**：确认新增 `_is_foreign` 分类 + `_validate_foreign_config` 分支（而非复用 MediaCrawler 校验器）——这是后台可用性的前提。
2. **`collection_mode` 落点**：确认放在 `config_json`（非数据库列），且 ForeignRSSCollector 用 `__init__(**kwargs)` 吸收透传键。
3. **`DataSource.type` 取值**：外网源用新类型 `foreign_rss`（需在 M4 注册）还是复用 `rss`？建议新增 `foreign_rss` 以便后台明确区分与路由。
4. **Phase 7 规则落点**：确认「is_foreign ⇒ keywords 非空」写在 `_validate_foreign_config`（推荐），而非改造 MediaCrawler 专属的 `validate_data_source_config`。
5. **外网页过滤**：确认后台列表接口新增 `?is_foreign=` 参数（推荐，与现有 `region_code` 过滤一致）还是纯前端过滤。

以上 5 项确认后，即可按 Phase 1→7 顺序落地；Phase 8 灰度验证聚焦 `region_id=2`、不入全国桶、中文源计数/关键词查询无变化。
